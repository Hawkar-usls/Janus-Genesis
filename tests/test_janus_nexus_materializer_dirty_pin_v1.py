# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.janus_nexus_materializer import NexusMaterializer, NexusMaterializerError


class JanusNexusDirtyPinTests(unittest.TestCase):
    def test_dirty_tracked_checkout_is_rejected_under_exact_head_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "sources"
            repo = sources / "1001"
            repo.mkdir(parents=True)
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "nexus-test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "JANUS Nexus Test"], check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("committed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True, stdout=subprocess.DEVNULL)
            sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode("ascii").strip()

            # HEAD is still the exact declared pin, but worktree bytes no longer match it.
            tracked.write_text("dirty-uncommitted\n", encoding="utf-8")
            manifest = {
                "schema": "janus.nexus.manifest.v1",
                "write_back_default": "DENY",
                "source_code_execution": False,
                "sources": [
                    {
                        "repository_id": "1001",
                        "visibility": "public",
                        "repository": "Hawkar-usls/Alpha",
                        "branch": "main",
                        "sha": sha,
                    }
                ],
            }
            output = root / "nexus"
            with self.assertRaisesRegex(
                NexusMaterializerError,
                "NEXUS_SOURCE_TRACKED_WORKTREE_DIRTY:1001",
            ):
                NexusMaterializer(manifest, sources, output).materialize()
            self.assertFalse((output / "faces").exists())


if __name__ == "__main__":
    unittest.main()
