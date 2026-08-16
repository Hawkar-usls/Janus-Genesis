# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import unittest

from tools.janus_power_compute_fabric import ComputeTier
from tools.janus_power_compute_fabric_v1_1 import JanusPowerCoreV11


class TagOnlyMemory:
    def __init__(self) -> None:
        self.events = []

    async def remember(self, tag, content):
        self.events.append((tag, content))


class SourceMemoryWithInternalTypeError:
    def __init__(self) -> None:
        self.calls = 0

    async def remember(self, source, content):
        self.calls += 1
        raise TypeError("internal backend bug")


class Kernel:
    def __init__(self, memory) -> None:
        self.memory = memory


class PowerV11HardeningTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.cores = []

    async def asyncTearDown(self) -> None:
        for core in reversed(self.cores):
            await core.shutdown()

    def make_core(self, memory=None, **kwargs):
        core = JanusPowerCoreV11(Kernel(memory) if memory is not None else None, **kwargs)
        self.cores.append(core)
        return core

    async def test_cooperative_deadline_is_timeout_not_failed(self) -> None:
        core = self.make_core(max_task_seconds=1.0)

        async def cooperative_deadline(request):
            # Deterministically cross the local cooperative deadline before the
            # outer wait_for timeout can decide the classification.
            await core._cooperate(request, deadline=0.0)
            return {"unreachable": True}

        core.register_executor(
            name="cooperative-deadline-test",
            tier=ComputeTier.LOCAL_GPU,
            capabilities={"deadline_test"},
            handler=cooperative_deadline,
            external_effect=False,
        )
        await core.start(worker_count=1)
        task_id = await core.compute({"type": "deadline_test"})
        response = await core.get_result(task_id, wait=True, timeout=1)
        self.assertEqual(response["task"]["status"], "timeout")
        self.assertEqual(response["task"]["error"], "TASK_TIMEOUT")

    async def test_user_seed_tag_memory_api_is_supported_without_adapter(self) -> None:
        memory = TagOnlyMemory()
        core = self.make_core(memory)
        await core.start(worker_count=1)
        task_id = await core.compute(
            {
                "type": "matrix_operations",
                "operation": "add",
                "data": {"A": [[1]], "B": [[2]]},
            }
        )
        response = await core.get_result(task_id, wait=True, timeout=1)
        self.assertEqual(response["task"]["status"], "completed")
        self.assertEqual([tag for tag, _ in memory.events], ["JANUS-POWER", "JANUS-POWER"])
        self.assertEqual(
            [event["event"] for _, event in memory.events],
            ["COMPUTE_QUEUED", "COMPUTE_TERMINAL"],
        )

    async def test_internal_typeerror_is_not_retried_as_different_memory_api(self) -> None:
        memory = SourceMemoryWithInternalTypeError()
        core = self.make_core(memory)
        await core.start(worker_count=1)
        task_id = await core.compute(
            {
                "type": "matrix_operations",
                "operation": "add",
                "data": {"A": [[1]], "B": [[2]]},
            }
        )
        response = await core.get_result(task_id, wait=True, timeout=1)
        self.assertEqual(response["task"]["status"], "completed")
        # One call for QUEUED + one call for TERMINAL, never a second API-shape
        # retry for either event.
        self.assertEqual(memory.calls, 2)
        self.assertEqual(response["task"]["metrics"]["memory_log_error"], "TypeError")

    async def test_unsupported_memory_signature_is_non_authoritative(self) -> None:
        class UnsupportedMemory:
            async def remember(self, only_one_argument):
                raise AssertionError("must not be called")

        core = self.make_core(UnsupportedMemory())
        await core.start(worker_count=1)
        task_id = await core.compute(
            {
                "type": "matrix_operations",
                "operation": "add",
                "data": {"A": [[1]], "B": [[2]]},
            }
        )
        response = await core.get_result(task_id, wait=True, timeout=1)
        self.assertEqual(response["task"]["status"], "completed")
        self.assertEqual(
            response["task"]["metrics"]["memory_log_error"],
            "UNSUPPORTED_MEMORY_API",
        )


if __name__ == "__main__":
    unittest.main()
