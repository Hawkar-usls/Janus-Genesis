#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Additive v1.1 hardening for JANUS Demiurge Boot Controller.

v1 remains preserved as the first controller implementation. v1.1 adds:
- one process-wide asyncio lock per Hippocampus DB identity for objective
  registration/recovery and controller execution;
- truthful reporting of whether local supervisor execution actually occurred;
- an explicit non-claim for distributed/multi-process exclusivity.
"""
from __future__ import annotations

import asyncio
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
_PROCESS_LOCKS: dict[str, asyncio.Lock] = {}
_PROCESS_LOCKS_GUARD = asyncio.Lock()


def _journal_identity(journal: OperationalJournal) -> str:
    raw = getattr(journal, "db_path", None)
    if raw is None:
        return f"object:{id(journal)}"
    try:
        return f"db:{Path(raw).expanduser().absolute().resolve(strict=False)}"
    except Exception:
        return f"db:{raw}"


async def _process_lock_for(journal: OperationalJournal) -> asyncio.Lock:
    identity = _journal_identity(journal)
    async with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(identity)
        if lock is None:
            lock = asyncio.Lock()
            _PROCESS_LOCKS[identity] = lock
        return lock


class SerializedDurableObjectiveStore:
    """Process-local serialization wrapper over the proof-carrying v1 store."""

    def __init__(self, journal: OperationalJournal) -> None:
        self.journal = journal
        self._inner = DurableObjectiveStore(journal)

    async def persist(self, *args, **kwargs):
        lock = await _process_lock_for(self.journal)
        async with lock:
            return await self._inner.persist(*args, **kwargs)

    async def recover(self, *args, **kwargs):
        lock = await _process_lock_for(self.journal)
        async with lock:
            return await self._inner.recover(*args, **kwargs)


class JanusDemiurgeBootControllerV11(JanusDemiurgeBootController):
    """Canonical v1.1 local controller surface.

    The process-local DB lock serializes both registration and run/resume chains
    for controllers sharing the same Hippocampus database identity. It is not a
    cross-process or distributed lease.
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
        lock = await _process_lock_for(self.journal)
        async with lock:
            # Avoid re-acquiring the same non-reentrant lock through the wrapped
            # objective store during recovery.
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
