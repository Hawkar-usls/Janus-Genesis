# -*- coding: utf-8 -*-
"""Bounded runtime adapter for exact JANUS Memory + Power components.

This layer owns lifecycle ordering only:

    MEMORY.start -> POWER.start -> work -> POWER.shutdown -> MEMORY.close

It does not promote RAM-buffered telemetry to persisted evidence. Power may
complete even when telemetry admission/persistence fails; that failure remains
visible through Power metrics and/or Memory state.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Optional

from tools.janus_hippocampus_hdd_buffer import JanusHippocampusBufferedJournal
from tools.janus_power_compute_fabric_v1_1 import JanusPowerCoreV11


class RuntimeAdapterError(RuntimeError):
    pass


class RuntimeAdapterClosedError(RuntimeAdapterError):
    pass


class RuntimeAdapterShutdownError(RuntimeAdapterError):
    pass


@dataclass(frozen=True)
class RuntimePins:
    compatibility_power_merge_sha: str = "c8e3ddba158934cefaadb0af1ad0d069f3ce61a9"
    power_v1_1_sha: str = "719d54d9f5aceced3b8df48aacd527ac3155fab3"
    memory_v2_sha: str = "938adb84975fa6a91cf6db89e9c95bf08c8fbdc9"
    integration_parent_sha: str = "19d2809e698d397090a0b92d25403da1bbb27e0f"


class JanusPowerMemoryRuntimeAdapter:
    """Lifecycle binder for the tested Memory and Power primitives.

    The adapter intentionally exposes no cloud/GPU/distributed registration
    helper and no source-writeback capability. ``compute`` delegates to the
    bounded Power core. Memory persistence remains explicit via
    ``force_memory_save`` or final shutdown.
    """

    PINS = RuntimePins()

    def __init__(
        self,
        db_path: str | Path,
        *,
        memory_options: Optional[dict[str, Any]] = None,
        power_options: Optional[dict[str, Any]] = None,
        worker_count: int = 1,
        kernel: Any = None,
    ) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be >= 1")
        self.db_path = Path(db_path)
        self.memory_options = dict(memory_options or {})
        self.power_options = dict(power_options or {})
        self.worker_count = worker_count
        self.kernel = kernel if kernel is not None else SimpleNamespace()
        self.memory: Optional[JanusHippocampusBufferedJournal] = None
        self.power: Optional[JanusPowerCoreV11] = None
        self._start_lock = asyncio.Lock()
        self._shutdown_lock = asyncio.Lock()
        self._started = False
        self._closed = False
        self._memory_flush_generation = 0
        self._last_memory_flush_count = 0

    async def __aenter__(self) -> "JanusPowerMemoryRuntimeAdapter":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.shutdown()

    async def start(self) -> None:
        if self._closed:
            raise RuntimeAdapterClosedError("RUNTIME_ADAPTER_ALREADY_CLOSED")
        if self._started:
            return
        async with self._start_lock:
            if self._started:
                return
            memory = JanusHippocampusBufferedJournal(
                self.db_path, **self.memory_options
            )
            power: Optional[JanusPowerCoreV11] = None
            try:
                await memory.start()
                self.kernel.memory = memory
                power = JanusPowerCoreV11(self.kernel, **self.power_options)
                await power.start(worker_count=self.worker_count)
                self.kernel.power = power
            except Exception:
                if power is not None:
                    try:
                        await power.shutdown()
                    except Exception:
                        # If Power cannot prove it stopped, keep Memory open; a
                        # later writer must never target an already-closed journal.
                        self.memory = memory
                        self.power = power
                        raise RuntimeAdapterShutdownError(
                            "START_ROLLBACK_POWER_SHUTDOWN_UNCONFIRMED_MEMORY_LEFT_OPEN"
                        )
                await memory.close()
                raise

            self.memory = memory
            self.power = power
            self._started = True

    def _require_started(self) -> tuple[JanusHippocampusBufferedJournal, JanusPowerCoreV11]:
        if self._closed:
            raise RuntimeAdapterClosedError("RUNTIME_ADAPTER_CLOSED")
        if not self._started or self.memory is None or self.power is None:
            raise RuntimeAdapterError("RUNTIME_ADAPTER_NOT_STARTED")
        return self.memory, self.power

    async def compute(self, blueprint: Mapping[str, Any], priority: str = "normal") -> str:
        _, power = self._require_started()
        return await power.compute(blueprint, priority=priority)

    async def get_result(
        self,
        task_id: str,
        *,
        wait: bool = False,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        _, power = self._require_started()
        return await power.get_result(task_id, wait=wait, timeout=timeout)

    async def cancel(self, task_id: str) -> bool:
        _, power = self._require_started()
        return await power.cancel(task_id)

    async def force_memory_save(self) -> dict[str, Any]:
        memory, _ = self._require_started()
        count = await memory.force_save()
        self._memory_flush_generation += 1
        self._last_memory_flush_count = count
        return {
            "flushed_records": count,
            "flush_generation": self._memory_flush_generation,
            "persistence_boundary": "SQLITE_TRANSACTION_COMMITTED",
            "backup_claimed": False,
            "replication_claimed": False,
        }

    async def status(self) -> dict[str, Any]:
        memory, power = self._require_started()
        memory_stats = await memory.stats()
        return {
            "schema": "janus.power_memory.runtime_adapter.v1",
            "pins": {
                "power_compatibility_merge_sha": self.PINS.compatibility_power_merge_sha,
                "power_v1_1_sha": self.PINS.power_v1_1_sha,
                "memory_v2_sha": self.PINS.memory_v2_sha,
                "integration_parent_sha": self.PINS.integration_parent_sha,
            },
            "memory": memory_stats,
            "power": {
                "tasks_total": len(power.tasks),
                "queue_size": power._queue.qsize(),
                "available_tiers": [tier.name for tier in power.available_tiers],
            },
            "last_memory_flush_count": self._last_memory_flush_count,
            "memory_flush_generation": self._memory_flush_generation,
            "runtime_started": self._started and not self._closed,
            "external_executor_registered_by_adapter": False,
            "source_writeback": False,
        }

    async def shutdown(self) -> None:
        if self._closed:
            return
        if not self._started:
            self._closed = True
            return
        async with self._shutdown_lock:
            if self._closed:
                return
            assert self.power is not None
            assert self.memory is not None

            # Ordering is the safety property: no component capable of emitting
            # Power telemetry may remain live after Memory's final close/flush.
            try:
                await self.power.shutdown()
            except Exception as exc:
                # Fail closed: do NOT close Memory if Power stop is unconfirmed.
                raise RuntimeAdapterShutdownError(
                    f"POWER_SHUTDOWN_UNCONFIRMED_MEMORY_LEFT_OPEN:{type(exc).__name__}"
                ) from exc

            await self.memory.close()
            self._closed = True
            self._started = False

    async def close(self) -> None:
        await self.shutdown()
