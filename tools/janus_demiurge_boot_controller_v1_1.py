#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Additive v1.1 hardening for JANUS Demiurge Boot Controller.

v1 remains preserved as the first controller implementation. v1.1 adds:
- one process-wide threading lock per Hippocampus DB identity for objective
  registration/recovery and controller execution;
- asynchronous acquisition of that lock without blocking the event loop;
- truthful reporting of whether local supervisor execution actually occurred;
- an explicit non-claim for distributed/multi-process exclusivity.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any, Mapping

from tools.janus_demiurge_boot_controller import (
    CONTROLLER_SCHEMA,
    DurableObjectiveStore,
    JanusDemiurgeBootController,
    OperationalJournal,
    canonical_sha256,
)


CONTROLLER_SCHEMA_V11 = "janus.genesis.demiurge_boot_controller.v1.1"
_PROCESS_LOCKS: dict[str, threading.Lock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def _journal_identity(journal: OperationalJournal) -> str:
    raw = getattr(journal, "db_path", None)
    if raw is None:
        return f"object:{id(journal)}"
    try:
        return f"db:{Path(raw).expanduser().absolute().resolve(strict=False)}"
    except Exception:
        return f"db:{raw}"


def _process_lock_for(journal: OperationalJournal) -> threading.Lock:
    identity = _journal_identity(journal)
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(identity)
        if lock is None:
            lock = threading.Lock()
            _PROCESS_LOCKS[identity] = lock
        return lock


class _AsyncProcessLock:
    def __init__(self, lock: threading.Lock) -> None:
        self._lock = lock
        self._held = False

    async def __aenter__(self) -> "_AsyncProcessLock":
        await asyncio.to_thread(self._lock.acquire)
        self._held = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._held:
            self._lock.release()
            self._held = False


class SerializedDurableObjectiveStore:
    """Process-wide serialization wrapper over the proof-carrying v1 store."""

    def __init__(self, journal: OperationalJournal) -> None:
        self.journal = journal
        self._inner = DurableObjectiveStore(journal)

    async def persist(self, *args, **kwargs):
        async with _AsyncProcessLock(_process_lock_for(self.journal)):
            return await self._inner.persist(*args, **kwargs)

    async def recover(self, *args, **kwargs):
        async with _AsyncProcessLock(_process_lock_for(self.journal)):
            return await self._inner.recover(*args, **kwargs)


class JanusDemiurgeBootControllerV11(JanusDemiurgeBootController):
    """Canonical v1.1 local controller surface.

    The process-wide DB lock serializes both registration and run/resume chains
    for controllers sharing the same Hippocampus database identity inside one
    Python process. It is not a cross-process or distributed lease.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.objectives = SerializedDurableObjectiveStore(self.journal)

    async def register_objective(self, *args, **kwargs) -> dict[str, Any]:
        # SerializedDurableObjectiveStore owns the DB-identity lock here.
        return await super().register_objective(*args, **kwargs)

    async def run_registered_objective(
        self,
        objective_id: str,
        *,
        max_segments: int = 16,
    ) -> dict[str, Any]:
        async with _AsyncProcessLock(_process_lock_for(self.journal)):
            # Avoid re-acquiring the same non-reentrant process lock through the
            # wrapped objective store during the controller's recovery step.
            original = self.objectives
            try:
                self.objectives = original._inner
                return await super().run_registered_objective(
                    objective_id, max_segments=max_segments
                )
            finally:
                self.objectives = original

    @staticmethod
    def _controller_result(
        *,
        state: str,
        objective_id: str,
        segments_executed: int,
        checkpoint: Mapping[str, Any] | None,
        recovered_checkpoint: bool,
    ) -> dict[str, Any]:
        result = {
            "schema": CONTROLLER_SCHEMA_V11,
            "parent_schema": CONTROLLER_SCHEMA,
            "state": state,
            "objective_id": objective_id,
            "segments_executed": segments_executed,
            "checkpoint": dict(checkpoint) if checkpoint is not None else None,
            "recovered_checkpoint": recovered_checkpoint,
            "manual_continue_between_segments_required": False,
            "self_generated_objective": False,
            "local_supervisor_execution_performed": segments_executed > 0,
            "process_local_db_serialization": True,
            "distributed_exclusive_lease_claimed": False,
            "autonomous_external_action": False,
            "authorized_external_action": False,
            "source_writeback": False,
            "automatic_merge": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result
