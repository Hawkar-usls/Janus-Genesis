# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.janus_nexus_materializer import NexusMaterializer


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class JanusNexusForgedReceiptTests(unittest.TestCase):
    def test_self_consistent_rewrite_cannot_impersonate_pinned_git_objects(self) -> None:
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
            tracked = repo / "tracked.txt"
            tracked.write_text("committed-source-bytes\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "--all"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-m", "fixture"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            sha = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD"],
                stderr=subprocess.STDOUT,
            ).decode("ascii").strip()

            manifest = {
                "schema": "janus.nexus.manifest.v1",
                "artifact_id": "TEST-NEXUS-FORGED-RECEIPT",
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
            materializer = NexusMaterializer(manifest, sources, output)
            materializer.materialize()
            self.assertTrue(materializer.verify()["ok"])

            # Forge a different body, then rewrite every unsigned receipt/hash so
            # the Nexus remains internally self-consistent while the manifest pin
            # still claims the original Git commit.
            forged_raw = b"forged-but-self-consistent\n"
            body_file = output / "faces" / "public-1001" / "tracked.txt"
            body_file.write_bytes(forged_raw)

            source_path = output / "faces" / "public-1001" / "SOURCE.json"
            source_receipt = json.loads(source_path.read_text(encoding="utf-8"))
            file_receipt = source_receipt["files"][0]
            file_receipt["bytes"] = len(forged_raw)
            file_receipt["sha256"] = hashlib.sha256(forged_raw).hexdigest()
            # Deliberately leave git_blob_sha/git_mode unchanged. A verifier that
            # trusts receipt labels instead of the pinned Git object can be fooled.
            source_receipt["tree_sha256"] = _sha256_json(source_receipt["files"])
            source_path.write_text(
                json.dumps(source_receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )

            nexus_path = output / "NEXUS_ID.json"
            nexus_receipt = json.loads(nexus_path.read_text(encoding="utf-8"))
            nexus_receipt["sources"][0] = source_receipt
            basis = {
                "schema": nexus_receipt["schema"],
                "manifest_sha256": nexus_receipt["manifest_sha256"],
                "sources": [
                    {
                        "repository_id": source_receipt["repository_id"],
                        "sha": source_receipt["sha"],
                        "tree_sha256": source_receipt["tree_sha256"],
                    }
                ],
            }
            nexus_receipt["nexus_digest"] = _sha256_json(basis)
            nexus_path.write_text(
                json.dumps(nexus_receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )

            result = materializer.verify()
            self.assertFalse(result["ok"])
            self.assertIn("NEXUS_SOURCE_OBJECT_BINDING_MISMATCH:1001", result["errors"])


if __name__ == "__main__":
    unittest.main()
