from __future__ import annotations

import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from genesis_v18_7_31_portable_receipt_runtime import (
    PortableCrashInjector,
    PortableCrashPoint,
    PortableRuntimeControlError,
    PortableRuntimeOutcomeUndetermined,
)
from genesis_v18_7_33_inflight_duplicate_reconciliation import (
    ReconciledPortableReceiptRuntimeAdapter,
)
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_models import Realm, WorldResult


class SlowWorld:
    def __init__(self, delay: float = 0.08):
        self.delay = delay
        self.calls = []
        self.guard = threading.Lock()

    def process_action(self, actor_id: str, action: str) -> WorldResult:
        with self.guard:
            self.calls.append((actor_id, action))
            ordinal = len(self.calls)
        time.sleep(self.delay)
        return WorldResult(
            status="OK",
            narrative=f"receipt-{ordinal}",
            realm=Realm.REFLECTION,
            visible_grace=None,
            choices=["continue"],
            trace_id=f"trace-{ordinal}",
        )


class InflightDuplicateReconciliationTests(unittest.TestCase):
    def test_active_duplicate_waits_then_replays_one_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = SlowWorld()
            a = ReconciledPortableReceiptRuntimeAdapter(world, root)
            b = ReconciledPortableReceiptRuntimeAdapter(world, root)
            start = threading.Barrier(2)

            def run(adapter):
                start.wait(timeout=5)
                return adapter.execute(
                    client_id="cli",
                    request_id="REQ-SAME",
                    actor_id="mira",
                    action="создать сад",
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(run, a), pool.submit(run, b)]
                results = [future.result(timeout=10) for future in futures]

            self.assertEqual(len(world.calls), 1)
            self.assertEqual(results[0].to_dict(internal=True), results[1].to_dict(internal=True))

    def test_crash_residue_call_entering_stays_undetermined_after_lock_is_free(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = SlowWorld(delay=0)
            crashing = ReconciledPortableReceiptRuntimeAdapter(
                world,
                root,
                crash_injector=PortableCrashInjector(
                    PortableCrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD
                ),
            )
            with self.assertRaises(PortableRuntimeControlError):
                crashing.execute(
                    client_id="cli", request_id="REQ-CRASH", actor_id="mira", action="сад"
                )
            self.assertEqual(len(world.calls), 0)
            with self.assertRaises(PortableRuntimeOutcomeUndetermined):
                ReconciledPortableReceiptRuntimeAdapter(world, root).execute(
                    client_id="cli", request_id="REQ-CRASH", actor_id="mira", action="сад"
                )
            self.assertEqual(len(world.calls), 0)

    def test_crash_after_world_before_receipt_never_reexecutes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = SlowWorld(delay=0)
            crashing = ReconciledPortableReceiptRuntimeAdapter(
                world,
                root,
                crash_injector=PortableCrashInjector(PortableCrashPoint.AFTER_WORLD_BEFORE_RECEIPT),
            )
            with self.assertRaises(PortableRuntimeControlError):
                crashing.execute(
                    client_id="cli", request_id="REQ-WORLD", actor_id="mira", action="сад"
                )
            self.assertEqual(len(world.calls), 1)
            with self.assertRaises(PortableRuntimeOutcomeUndetermined):
                ReconciledPortableReceiptRuntimeAdapter(world, root).execute(
                    client_id="cli", request_id="REQ-WORLD", actor_id="mira", action="сад"
                )
            self.assertEqual(len(world.calls), 1)

    def test_real_genesis_duplicate_replay_does_not_increment_tick_twice(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = ReconciledPortableReceiptRuntimeAdapter(world, root)
            before = world.memory.load_player("mira").tick
            first = adapter.execute(
                client_id="play-genesis",
                request_id="REAL-V33",
                actor_id="mira",
                action="создать музыку",
            )
            after = world.memory.load_player("mira").tick
            self.assertGreater(after, before)
            second = adapter.execute(
                client_id="play-genesis",
                request_id="REAL-V33",
                actor_id="mira",
                action="создать музыку",
            )
            self.assertEqual(world.memory.load_player("mira").tick, after)
            self.assertEqual(first.to_dict(internal=True), second.to_dict(internal=True))


if __name__ == "__main__":
    unittest.main()
