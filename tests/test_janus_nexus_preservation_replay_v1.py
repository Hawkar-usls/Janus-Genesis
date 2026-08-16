# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.janus_nexus_materializer import NexusMaterializer
from tools.janus_nexus_preservation_replay import (
    PreservationReplay,
    PreservationReplayError,
    validate_inventory_binding,
)


class JanusNexusPreservationReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._temp.name)
        cls.sources = cls.root / "sources"
        cls.sources.mkdir()
        cls.constellation = {
            "schema": "janus.genesis.git_habitat.repository_constellation.v1",
            "artifact_id": "SYNTHETIC-44-CONSTELLATION",
            "inventory_owner": "Hawkar-usls",
            "repository_count": 44,
            "public_repository_count": 41,
            "private_repository_count": 3,
            "public_repositories": [],
            "private_repository_slots": [],
        }
        cls.nexus_manifest = {
            "schema": "janus.nexus.manifest.v1",
            "artifact_id": "SYNTHETIC-44-NEXUS-MANIFEST",
            "write_back_default": "DENY",
            "source_code_execution": False,
            "sources": [],
        }
        cls.private_secrets: list[str] = []

        for index in range(1, 42):
            repo_id = str(100000 + index)
            name = f"SyntheticPublic{index:02d}"
            sha = cls._make_repo(repo_id, f"public-payload-{index:02d}\n")
            cls.constellation["public_repositories"].append(
                {"id": repo_id, "name": name, "default_branch": "main"}
            )
            cls.nexus_manifest["sources"].append(
                {
                    "repository_id": repo_id,
                    "visibility": "public",
                    "repository": f"Hawkar-usls/{name}",
                    "branch": "main",
                    "sha": sha,
                }
            )

        for index in range(1, 4):
            repo_id = str(200000 + index)
            secret = f"PRIVATE-SYNTHETIC-CONTENT-{index}-DO-NOT-PUBLISH"
            sha = cls._make_repo(repo_id, secret + "\n")
            cls.private_secrets.append(secret)
            cls.constellation["private_repository_slots"].append(
                {
                    "repository_id": repo_id,
                    "visibility": "private",
                    "resolution": "AUTHENTICATED_RESOLUTION_REQUIRED",
                }
            )
            cls.nexus_manifest["sources"].append(
                {
                    "repository_id": repo_id,
                    "visibility": "private",
                    "branch": "main",
                    "sha": sha,
                }
            )

        cls.nexus_root = cls.root / "nexus"
        result = NexusMaterializer(
            cls.nexus_manifest, cls.sources, cls.nexus_root
        ).materialize()
        assert result["source_count"] == 44
        cls.local_receipt = json.loads(
            (cls.nexus_root / "NEXUS_ID.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    @classmethod
    def _make_repo(cls, repo_id: str, payload: str) -> str:
        repo = cls.sources / repo_id
        repo.mkdir()
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(repo)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "nexus@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "JANUS Nexus Test"],
            check=True,
        )
        (repo / "payload.txt").write_text(payload, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "payload.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", "fixture"],
            check=True,
        )
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"]
        ).decode("ascii").strip()

    def _replay(self, nexus_root: Path | None = None) -> PreservationReplay:
        return PreservationReplay(
            self.constellation,
            self.nexus_manifest,
            self.sources,
            nexus_root or self.nexus_root,
        )

    def test_complete_44_slot_local_replay_emits_redacted_public_receipt(self) -> None:
        receipt = self._replay().public_receipt()
        self.assertTrue(receipt["local_exact_replay_passed"])
        self.assertEqual(receipt["repository_count"], 44)
        self.assertEqual(len(receipt["public_sources"]), 41)
        self.assertEqual(len(receipt["private_repository_slots"]), 3)
        self.assertFalse(receipt["empirical_owner_wide_replay_promoted"])
        self.assertFalse(receipt["private_exact_pin_public_proof_claimed"])
        self.assertFalse(receipt["source_writeback_performed"])
        self.assertFalse(receipt["source_code_executed"])

    def test_private_exact_pins_trees_content_and_whole_nexus_digest_do_not_leak(self) -> None:
        receipt = self._replay().public_receipt()
        serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
        local_private = [
            row for row in self.local_receipt["sources"] if row["visibility"] == "private"
        ]
        self.assertEqual(len(local_private), 3)
        for row in local_private:
            self.assertNotIn(row["sha"], serialized)
            self.assertNotIn(row["tree_sha256"], serialized)
            for file_row in row["files"]:
                self.assertNotIn(file_row["sha256"], serialized)
                self.assertNotIn(file_row["git_blob_sha"], serialized)
        for secret in self.private_secrets:
            self.assertNotIn(secret, serialized)
        self.assertNotIn(self.local_receipt["nexus_digest"], serialized)
        self.assertNotIn("nexus_digest", receipt)
        self.assertNotIn("manifest_sha256", receipt)
        self.assertTrue(receipt["public_sources"][0]["sha"])
        self.assertTrue(receipt["public_sources"][0]["tree_sha256"])

    def test_public_receipt_digest_binds_only_redacted_projection(self) -> None:
        receipt = self._replay().public_receipt()
        digest = receipt.pop("public_receipt_digest")
        expected = hashlib.sha256(
            json.dumps(
                receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(digest, expected)

    def test_missing_or_reordered_source_is_rejected_before_local_replay(self) -> None:
        missing = json.loads(json.dumps(self.nexus_manifest))
        missing["sources"].pop()
        with self.assertRaisesRegex(
            PreservationReplayError, "PRESERVATION_SOURCE_SET_OR_ORDER_MISMATCH"
        ):
            validate_inventory_binding(self.constellation, missing)

        reordered = json.loads(json.dumps(self.nexus_manifest))
        reordered["sources"][0], reordered["sources"][1] = (
            reordered["sources"][1],
            reordered["sources"][0],
        )
        with self.assertRaisesRegex(
            PreservationReplayError, "PRESERVATION_SOURCE_SET_OR_ORDER_MISMATCH"
        ):
            validate_inventory_binding(self.constellation, reordered)

    def test_materialized_body_tamper_blocks_preservation_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "nexus"
            shutil.copytree(self.nexus_root, clone)
            first_public_id = self.constellation["public_repositories"][0]["id"]
            target = clone / "faces" / f"public-{first_public_id}" / "payload.txt"
            target.write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(
                PreservationReplayError, "PRESERVATION_LOCAL_REPLAY_FAILED"
            ):
                self._replay(clone).public_receipt()

    def test_public_privacy_validator_rejects_private_pin_injection(self) -> None:
        receipt = self._replay().public_receipt()
        receipt["private_repository_slots"][0]["sha"] = "a" * 40
        with self.assertRaisesRegex(
            PreservationReplayError, "PRESERVATION_PUBLIC_PRIVATE_METADATA_LEAK"
        ):
            PreservationReplay.validate_public_receipt_privacy(receipt)


if __name__ == "__main__":
    unittest.main()
