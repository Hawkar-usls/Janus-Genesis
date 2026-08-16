# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.janus_nexus_materializer import NexusMaterializer, NexusMaterializerError


class JanusNexusReservedPathTests(unittest.TestCase):
    def test_source_root_source_json_cannot_collide_with_nexus_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / "sources"
            repo = sources / "1001"
            repo.mkdir(parents=True)
            subprocess.run(
                ["git", "init", "-b", "main", str(repo)],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "nexus-test@example.invalid"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "JANUS Nexus Test"],
                check=True,
            )
            (repo / "SOURCE.json").write_text(
                '{"this":"belongs to the historical source"}\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(repo), "add", "SOURCE.json"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "reserved path fixture"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            sha = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                stderr=subprocess.STDOUT,
            ).decode("ascii").strip()

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

            with self.assertRaisesRegex(
                NexusMaterializerError,
                "NEXUS_SOURCE_RESERVED_PATH_REJECTED:SOURCE.json",
            ):
                NexusMaterializer(manifest, sources, root / "nexus").materialize()

            # Fail before any source blob can be represented under a path that is
            # also owned by the Nexus receipt namespace.
            self.assertFalse((root / "nexus" / "faces" / "public-1001" / "SOURCE.json").exists())


if __name__ == "__main__":
    unittest.main()
