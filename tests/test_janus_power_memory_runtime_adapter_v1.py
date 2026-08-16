# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.janus_hippocampus_hdd_buffer import MemoryPersistenceError
from tools.janus_power_memory_runtime_adapter import (
    JanusPowerMemoryRuntimeAdapter,
    RuntimeAdapterShutdownError,
)


class PowerMemoryRuntimeAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "janus" / "cortex.db"
        self.adapters: list[JanusPowerMemoryRuntimeAdapter] = []

    async def asyncTearDown(self) -> None:
        for adapter in reversed(self.adapters):
            if not adapter._closed:
                try:
                    await adapter.shutdown()
                except Exception:
                    pass
        self.tmp.cleanup()

    async def make_adapter(self, **kwargs) -> JanusPowerMemoryRuntimeAdapter:
        adapter = JanusPowerMemoryRuntimeAdapter(
            self.db,
            memory_options={
                "batch_size": 500,
                "flush_interval_seconds": 60,
                **kwargs.pop("memory_options", {}),
            },
            power_options=kwargs.pop("power_options", {}),
            worker_count=kwargs.pop("worker_count", 1),
            **kwargs,
        )
        self.adapters.append(adapter)
        await adapter.start()
        return adapter

    def disk_rows(self) -> list[tuple[int, str, str]]:
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(
                "SELECT id, source, content FROM thoughts ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

    async def one_compute(self, adapter: JanusPowerMemoryRuntimeAdapter) -> tuple[str, dict]:
        task_id = await adapter.compute(
            {
                "type": "matrix_operations",
                "operation": "add",
                "data": {"A": [[1, 2]], "B": [[3, 4]]},
            }
        )
        result = await adapter.get_result(task_id, wait=True, timeout=2)
        return task_id, result

    async def stop_memory_background_flusher(self, adapter) -> None:
        memory = adapter.memory
        assert memory is not None
        memory._stop_event.set()
        memory._flush_event.set()
        if memory._flush_task is not None:
            await memory._flush_task
            memory._flush_task = None

    async def test_start_binds_memory_before_exposing_power(self) -> None:
        adapter = await self.make_adapter()
        self.assertIs(adapter.kernel.memory, adapter.memory)
        self.assertIs(adapter.kernel.power, adapter.power)
        status = await adapter.status()
        self.assertTrue(status["runtime_started"])
        self.assertEqual(
            status["power"]["available_tiers"],
            ["LOCAL_CPU", "QUANTUM_SIM", "HYBRID"],
        )
        self.assertFalse(status["external_executor_registered_by_adapter"])

    async def test_compute_truth_can_complete_while_telemetry_is_only_ram_buffered(self) -> None:
        adapter = await self.make_adapter()
        _, result = await self.one_compute(adapter)
        self.assertEqual(result["task"]["status"], "completed")
        self.assertEqual(result["result"], [[4.0, 6.0]])

        status = await adapter.status()
        self.assertEqual(status["memory"]["buffered_records"], 2)
        self.assertEqual(self.disk_rows(), [])
        self.assertEqual(status["memory_flush_generation"], 0)

    async def test_force_save_persists_exact_queued_and_terminal_events_once(self) -> None:
        adapter = await self.make_adapter()
        task_id, result = await self.one_compute(adapter)
        receipt = await adapter.force_memory_save()
        self.assertEqual(receipt["flushed_records"], 2)
        self.assertEqual(receipt["persistence_boundary"], "SQLITE_TRANSACTION_COMMITTED")
        self.assertFalse(receipt["backup_claimed"])
        self.assertFalse(receipt["replication_claimed"])

        rows = self.disk_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual([row[1] for row in rows], ["JANUS-POWER", "JANUS-POWER"])
        payloads = [json.loads(row[2]) for row in rows]
        self.assertEqual(
            [payload["event"] for payload in payloads],
            ["COMPUTE_QUEUED", "COMPUTE_TERMINAL"],
        )
        self.assertEqual([payload["task_id"] for payload in payloads], [task_id, task_id])
        self.assertEqual(payloads[-1]["status"], "completed")
        self.assertEqual(result["task"]["status"], "completed")

        second = await adapter.force_memory_save()
        self.assertEqual(second["flushed_records"], 0)
        self.assertEqual(len(self.disk_rows()), 2)

    async def test_disk_flush_failure_does_not_rewrite_compute_truth(self) -> None:
        adapter = await self.make_adapter()
        task_id, result = await self.one_compute(adapter)
        self.assertEqual(result["task"]["status"], "completed")
        memory = adapter.memory
        assert memory is not None
        original = memory._write_batch_sync

        def fail(batch):
            raise OSError("synthetic disk failure")

        memory._write_batch_sync = fail  # type: ignore[method-assign]
        with self.assertRaises(MemoryPersistenceError):
            await adapter.force_memory_save()
        self.assertEqual(adapter.power.tasks[task_id].status.value, "completed")  # type: ignore[union-attr]
        self.assertEqual((await memory.stats())["buffered_records"], 2)
        self.assertEqual(self.disk_rows(), [])

        memory._write_batch_sync = original  # type: ignore[method-assign]
        saved = await adapter.force_memory_save()
        self.assertEqual(saved["flushed_records"], 2)

    async def test_memory_admission_failure_is_telemetry_failure_not_compute_failure(self) -> None:
        adapter = await self.make_adapter(
            memory_options={
                "batch_size": 1,
                "flush_interval_seconds": 60,
                "max_buffer_records": 1,
            }
        )
        await self.stop_memory_background_flusher(adapter)
        task_id, result = await self.one_compute(adapter)
        self.assertEqual(result["task"]["status"], "completed")
        self.assertEqual(result["result"], [[4.0, 6.0]])
        self.assertEqual(
            result["task"]["metrics"]["memory_log_error"],
            "MemoryBufferFullError",
        )
        memory = adapter.memory
        assert memory is not None
        self.assertEqual((await memory.stats())["buffered_records"], 1)
        self.assertEqual(self.disk_rows(), [])
        self.assertEqual(adapter.power.tasks[task_id].status.value, "completed")  # type: ignore[union-attr]

    async def test_shutdown_orders_power_before_memory_final_close(self) -> None:
        adapter = await self.make_adapter()
        await self.one_compute(adapter)
        order = []
        power = adapter.power
        memory = adapter.memory
        assert power is not None and memory is not None
        original_power_shutdown = power.shutdown
        original_memory_close = memory.close

        async def power_shutdown():
            order.append("POWER_SHUTDOWN_BEGIN")
            await original_power_shutdown()
            order.append("POWER_SHUTDOWN_END")

        async def memory_close():
            order.append("MEMORY_CLOSE_BEGIN")
            await original_memory_close()
            order.append("MEMORY_CLOSE_END")

        power.shutdown = power_shutdown  # type: ignore[method-assign]
        memory.close = memory_close  # type: ignore[method-assign]
        await adapter.shutdown()
        self.assertEqual(
            order,
            [
                "POWER_SHUTDOWN_BEGIN",
                "POWER_SHUTDOWN_END",
                "MEMORY_CLOSE_BEGIN",
                "MEMORY_CLOSE_END",
            ],
        )
        self.assertEqual(len(self.disk_rows()), 2)

    async def test_unconfirmed_power_shutdown_keeps_memory_open_fail_closed(self) -> None:
        adapter = await self.make_adapter()
        power = adapter.power
        memory = adapter.memory
        assert power is not None and memory is not None
        original_power_shutdown = power.shutdown

        async def fail_shutdown():
            raise RuntimeError("synthetic power shutdown failure")

        power.shutdown = fail_shutdown  # type: ignore[method-assign]
        with self.assertRaises(RuntimeAdapterShutdownError):
            await adapter.shutdown()
        self.assertFalse(memory._closed)
        self.assertTrue((await memory.stats())["accepting_writes"])
        self.assertFalse(adapter._closed)

        power.shutdown = original_power_shutdown  # type: ignore[method-assign]
        await adapter.shutdown()
        self.assertTrue(memory._closed)

    async def test_pins_bind_exact_component_and_integration_parents(self) -> None:
        adapter = await self.make_adapter()
        status = await adapter.status()
        self.assertEqual(
            status["pins"],
            {
                "power_compatibility_merge_sha": "c8e3ddba158934cefaadb0af1ad0d069f3ce61a9",
                "power_v1_1_sha": "719d54d9f5aceced3b8df48aacd527ac3155fab3",
                "memory_v2_sha": "938adb84975fa6a91cf6db89e9c95bf08c8fbdc9",
                "integration_parent_sha": "19d2809e698d397090a0b92d25403da1bbb27e0f",
            },
        )


if __name__ == "__main__":
    unittest.main()
