from __future__ import annotations

import multiprocessing
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from janus_portable_lock_v2 import PortableProcessLockV2


def _hold_lock(path: str, ready, release) -> None:
    lock = PortableProcessLockV2(path)
    with lock.exclusive():
        ready.set()
        release.wait(10)


class PortableProcessLockV2Gates(unittest.TestCase):
    def test_distinct_instances_same_process_never_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "local.lock"
            a = PortableProcessLockV2(path)
            b = PortableProcessLockV2(path)
            start = threading.Barrier(2)
            guard = threading.Lock()
            active = 0
            max_active = 0

            def worker(lock):
                nonlocal active, max_active
                start.wait(timeout=5)
                with lock.exclusive():
                    with guard:
                        active += 1
                        max_active = max(max_active, active)
                    time.sleep(0.08)
                    with guard:
                        active -= 1

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker, a), pool.submit(worker, b)]
                for future in futures:
                    future.result(timeout=10)
            self.assertEqual(max_active, 1)

    def test_nonblocking_probe_sees_other_local_instance(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "probe.lock"
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

    def test_spawned_process_contention_remains_visible(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "process.lock")
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            release = ctx.Event()
            process = ctx.Process(target=_hold_lock, args=(path, ready, release))
            process.start()
            try:
                self.assertTrue(ready.wait(10))
                self.assertFalse(PortableProcessLockV2(path).try_acquire())
            finally:
                release.set()
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
            self.assertEqual(process.exitcode, 0)


if __name__ == "__main__":
    unittest.main()
