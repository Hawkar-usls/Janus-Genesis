from __future__ import annotations

import json
import multiprocessing
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from genesis_v18_7_31_portable_receipt_runtime import (
    PortableCrashInjector,
    PortableCrashPoint,
    PortableReceiptRuntimeAdapter,
    PortableRequestConflict,
    PortableRuntimeControlError,
    PortableRuntimeOutcomeUndetermined,
    PortableRuntimeReceiptIntegrityError,
    PortableRuntimeRequestStore,
)
from genesis_v18_models import Realm, WorldResult
from janus_portable_lock_v2 import PortableProcessLockV2


def _hold_v2_lock(path: str, ready, release) -> None:
    lock = PortableProcessLockV2(path)
    with lock.exclusive():
        ready.set()
        release.wait(10)


class PortableLockV2Tests(unittest.TestCase):
    def test_two_distinct_instances_in_one_process_never_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "same-path.lock"
            lock_a = PortableProcessLockV2(path)
            lock_b = PortableProcessLockV2(path)
            start = threading.Barrier(2)
            guard = threading.Lock()
            active = 0
            max_active = 0

            def worker(lock):
                nonlocal active, max_active
                start.wait(timeout=5)  # Synchronize before, never inside, the lock.
                with lock.exclusive():
                    with guard:
                        active += 1
                        max_active = max(max_active, active)
                    time.sleep(0.08)
                    with guard:
                        active -= 1

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker, lock_a), pool.submit(worker, lock_b)]
                for future in futures:
                    future.result(timeout=10)
            self.assertEqual(max_active, 1)

    def test_try_acquire_observes_busy_same_process_other_instance(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "busy.lock"
            a = PortableProcessLockV2(path)
            b = PortableProcessLockV2(path)
            entered = threading.Event()
            release = threading.Event()

            def holder():
                with a.exclusive():
                    entered.set()
                    release.wait(5)

            thread = threading.Thread(target=holder)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                self.assertFalse(b.try_acquire())
            finally:
                release.set()
                thread.join(5)
            self.assertTrue(b.try_acquire())

    def test_spawned_process_contention_is_still_visible(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "cross-process.lock")
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            release = ctx.Event()
            proc = ctx.Process(target=_hold_v2_lock, args=(path, ready, release))
            proc.start()
            try:
                self.assertTrue(ready.wait(10))
                self.assertFalse(PortableProcessLockV2(path).try_acquire())
            finally:
                release.set()
                proc.join(10)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(5)
            self.assertEqual(proc.exitcode, 0)


class FakeWorld:
    def __init__(self, *, delay: float = 0.0):
        self.delay = delay
        self.calls: list[tuple[str, str]] = []
        self._guard = threading.Lock()

    def process_action(self, actor_id: str, action: str) -> WorldResult:
        with self._guard:
            self.calls.append((actor_id, action))
            ordinal = len(self.calls)
        if self.delay:
            time.sleep(self.delay)
        return WorldResult(
            status="OK",
            narrative=f"result-{ordinal}:{action}",
            realm=Realm.REFLECTION,
            visible_grace=None,
            choices=["continue"],
            branch_id=None,
            trace_id=f"trace-{ordinal}",
            wish_manifested=False,
        )


class ExplodingWorld(FakeWorld):
    def process_action(self, actor_id: str, action: str) -> WorldResult:
        self.calls.append((actor_id, action))
        raise RuntimeError("world failed after entry; mutation status unknown")


class PortableReceiptRuntimeTests(unittest.TestCase):
    @staticmethod
    def _adapter(root: Path, world, point=None):
        injector = PortableCrashInjector(point) if point is not None else PortableCrashInjector()
        return PortableReceiptRuntimeAdapter(world, root, crash_injector=injector)

    def test_same_request_replays_full_receipt_without_second_world_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            adapter = self._adapter(root, world)
            first = adapter.execute(
                client_id="cli", request_id="REQ-1", actor_id="mira", action="создать сад"
            )
            second = adapter.execute(
                client_id="cli", request_id="REQ-1", actor_id="mira", action="создать сад"
            )
            self.assertEqual(len(world.calls), 1)
            self.assertEqual(first.to_dict(internal=True), second.to_dict(internal=True))
            state = adapter.request_state(client_id="cli", request_id="REQ-1")
            self.assertEqual(state["state"], "SETTLED")
            self.assertTrue(state["full_result_receipt_persisted"])

    def test_same_request_different_action_fails_closed_before_world(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            adapter = self._adapter(root, world)
            adapter.execute(client_id="cli", request_id="REQ-X", actor_id="mira", action="сад")
            with self.assertRaises(PortableRequestConflict):
                adapter.execute(client_id="cli", request_id="REQ-X", actor_id="mira", action="мост")
            self.assertEqual(len(world.calls), 1)

    def test_identical_text_with_new_request_id_is_new_intent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            adapter = self._adapter(root, world)
            adapter.execute(client_id="cli", request_id="REQ-A", actor_id="mira", action="осмотреться")
            adapter.execute(client_id="cli", request_id="REQ-B", actor_id="mira", action="осмотреться")
            self.assertEqual(len(world.calls), 2)

    def test_crash_after_call_entering_before_world_blocks_automatic_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            adapter = self._adapter(root, world, PortableCrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD)
            with self.assertRaises(PortableRuntimeControlError):
                adapter.execute(client_id="cli", request_id="REQ-2", actor_id="mira", action="сад")
            self.assertEqual(len(world.calls), 0)
            state = adapter.request_state(client_id="cli", request_id="REQ-2")
            self.assertEqual(state["state"], "CALL_ENTERING")
            with self.assertRaises(PortableRuntimeOutcomeUndetermined):
                self._adapter(root, world).execute(
                    client_id="cli", request_id="REQ-2", actor_id="mira", action="сад"
                )
            self.assertEqual(len(world.calls), 0)

    def test_crash_after_world_before_receipt_blocks_second_world_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            adapter = self._adapter(root, world, PortableCrashPoint.AFTER_WORLD_BEFORE_RECEIPT)
            with self.assertRaises(PortableRuntimeControlError):
                adapter.execute(client_id="cli", request_id="REQ-3", actor_id="mira", action="сад")
            self.assertEqual(len(world.calls), 1)
            with self.assertRaises(PortableRuntimeOutcomeUndetermined):
                self._adapter(root, world).execute(
                    client_id="cli", request_id="REQ-3", actor_id="mira", action="сад"
                )
            self.assertEqual(len(world.calls), 1)

    def test_crash_after_receipt_replays_without_second_world_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            adapter = self._adapter(root, world, PortableCrashPoint.AFTER_RECEIPT)
            with self.assertRaises(PortableRuntimeControlError):
                adapter.execute(client_id="cli", request_id="REQ-4", actor_id="mira", action="сад")
            self.assertEqual(len(world.calls), 1)
            replayed = self._adapter(root, world).execute(
                client_id="cli", request_id="REQ-4", actor_id="mira", action="сад"
            )
            self.assertEqual(replayed.status, "OK")
            self.assertEqual(len(world.calls), 1)

    def test_two_threads_same_request_produce_one_world_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld(delay=0.08)
            a = self._adapter(root, world)
            b = self._adapter(root, world)
            start = threading.Barrier(2)

            def run(adapter):
                start.wait(timeout=5)
                return adapter.execute(
                    client_id="cli", request_id="REQ-C", actor_id="mira", action="сад"
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [f.result(timeout=10) for f in (pool.submit(run, a), pool.submit(run, b))]
            self.assertEqual(len(world.calls), 1)
            self.assertEqual(results[0].to_dict(internal=True), results[1].to_dict(internal=True))

    def test_world_exception_is_persisted_as_undetermined(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = ExplodingWorld()
            adapter = self._adapter(root, world)
            with self.assertRaises(RuntimeError):
                adapter.execute(client_id="cli", request_id="REQ-E", actor_id="mira", action="сад")
            state = adapter.request_state(client_id="cli", request_id="REQ-E")
            self.assertEqual(state["state"], "UNDETERMINED_EXCEPTION")
            self.assertIsNotNone(state["exception_sha256"])
            with self.assertRaises(PortableRuntimeOutcomeUndetermined):
                self._adapter(root, world).execute(
                    client_id="cli", request_id="REQ-E", actor_id="mira", action="сад"
                )
            self.assertEqual(len(world.calls), 1)

    def test_tampered_receipt_hash_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            adapter = self._adapter(root, world)
            adapter.execute(client_id="cli", request_id="REQ-T", actor_id="mira", action="сад")
            db = root / "portable_runtime_requests_v18_7_31.sqlite3"
            conn = sqlite3.connect(db)
            try:
                conn.execute(
                    "UPDATE runtime_requests SET result_sha256=? WHERE client_id=? AND request_id=?",
                    ("00" * 32, "cli", "REQ-T"),
                )
                conn.commit()
            finally:
                conn.close()
            with self.assertRaises(PortableRuntimeReceiptIntegrityError):
                adapter.execute(client_id="cli", request_id="REQ-T", actor_id="mira", action="сад")
            self.assertEqual(len(world.calls), 1)

    def test_store_releases_sqlite_handles_for_immediate_cleanup(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        store = PortableRuntimeRequestStore(root / "control.sqlite3")
        store.bind(client_id="cli", request_id="1", actor_id="mira", action="x")
        self.assertEqual(len(store.list_records()), 1)
        temp.cleanup()  # Windows regression gate: must not raise WinError 32.
        self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
