# -*- coding: utf-8 -*-
from __future__ import annotations

import multiprocessing as mp
import tempfile
import unittest
from pathlib import Path

from tools.genesis_git_habitat_aura import HabitatAuraError, _ensure_real_dir


def _mkdir_worker(path: str, barrier, queue) -> None:
    try:
        barrier.wait(timeout=5)
        _ensure_real_dir(Path(path))
        queue.put(("OK", "DIRECTORY_READY"))
    except Exception as exc:
        queue.put((type(exc).__name__, str(exc)))


class GitHabitatAuraSharedDirectoryRaceTests(unittest.TestCase):
    def test_concurrent_shared_aura_directory_creation_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "hearth" / "aura"
            ctx = mp.get_context("spawn")
            workers = 8
            barrier = ctx.Barrier(workers)
            queue = ctx.Queue()
            processes = [
                ctx.Process(target=_mkdir_worker, args=(str(target), barrier, queue))
                for _ in range(workers)
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)

            results = [queue.get(timeout=2) for _ in range(workers)]
            self.assertEqual(results.count(("OK", "DIRECTORY_READY")), workers, results)
            self.assertTrue(target.is_dir())
            self.assertFalse(target.is_symlink())

    def test_leaf_symlink_is_still_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            link = root / "aura"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(HabitatAuraError, "MAY_NOT_BE_SYMLINK"):
                _ensure_real_dir(link)


if __name__ == "__main__":
    unittest.main()
