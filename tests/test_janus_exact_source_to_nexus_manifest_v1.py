from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from janus_exact_source_manifest_freezer import freeze_exact_source_manifest
from janus_exact_source_to_nexus_manifest import (
    ExactSourceToNexusManifestError,
    PRIVATE_BRANCH_SENTINEL,
    adapt_and_write,
    adapt_exact_source_manifest,
    validate_adapted_manifest,
)

CONSTELLATION_PATH = (
    ROOT / "protocol" / "JANUS_GENESIS_GIT_HABITAT_REPOSITORY_CONSTELLATION-v1.0.json"
)


def _constellation() -> dict:
    return json.loads(CONSTELLATION_PATH.read_text(encoding="utf-8"))


def _pin(source_id: str) -> str:
    return hashlib.sha1(f"janus-test:{source_id}".encode("utf-8")).hexdigest()


def _local_manifest() -> tuple[dict, dict[str, str]]:
    constellation = _constellation()
    pins: dict[str, str] = {}
    sources = []
    for row in constellation["public_repositories"]:
        source_id = row["id"]
        pins[source_id] = _pin(source_id)
        sources.append(
            {
                "source_id": source_id,
                "visibility": "public",
                "source_kind": "GIT_REPOSITORY",
                "pin": {"kind": "GIT_COMMIT_SHA1", "value": pins[source_id]},
            }
        )
    for row in constellation["private_repository_slots"]:
        source_id = row["repository_id"]
        pins[source_id] = _pin(source_id)
        sources.append(
            {
                "source_id": source_id,
                "visibility": "private",
                "source_kind": "GIT_REPOSITORY",
                "pin": {"kind": "GIT_COMMIT_SHA1", "value": pins[source_id]},
            }
        )
    pinset = {
        "schema": "janus.source_pin_set.v1",
        "pinset_id": "LOCAL-SENSITIVE-TEST-PINSET",
        "sources": sources,
    }
    return freeze_exact_source_manifest(pinset, constellation), pins


class ExactSourceToNexusManifestTests(unittest.TestCase):
    def test_adapter_accounts_for_all_44_and_preserves_exact_pins(self) -> None:
        constellation = _constellation()
        local, pins = _local_manifest()
        manifest = adapt_exact_source_manifest(
            local,
            constellation,
            artifact_id="JANUS-OWNER-44-TEST",
        )
        self.assertEqual(manifest["schema"], "janus.nexus.manifest.v1")
        self.assertEqual(manifest["write_back_default"], "DENY")
        self.assertFalse(manifest["source_code_execution"])
        self.assertEqual(len(manifest["sources"]), 44)
        self.assertEqual(
            sum(row["visibility"] == "public" for row in manifest["sources"]), 41
        )
        self.assertEqual(
            sum(row["visibility"] == "private" for row in manifest["sources"]), 3
        )
        for row in manifest["sources"]:
            self.assertEqual(row["sha"], pins[row["repository_id"]])

    def test_output_order_matches_preservation_inventory_contract(self) -> None:
        constellation = _constellation()
        local, _pins = _local_manifest()
        manifest = adapt_exact_source_manifest(local, constellation, artifact_id="ORDER")
        expected = [row["id"] for row in constellation["public_repositories"]] + [
            row["repository_id"] for row in constellation["private_repository_slots"]
        ]
        self.assertEqual(
            [row["repository_id"] for row in manifest["sources"]], expected
        )

    def test_public_identity_and_default_branch_come_only_from_constellation(self) -> None:
        constellation = _constellation()
        local, _pins = _local_manifest()
        manifest = adapt_exact_source_manifest(local, constellation, artifact_id="PUBLIC")
        expected = {
            row["id"]: (f"Hawkar-usls/{row['name']}", row["default_branch"])
            for row in constellation["public_repositories"]
        }
        for row in manifest["sources"]:
            if row["visibility"] == "public":
                self.assertEqual(
                    (row["repository"], row["branch"]), expected[row["repository_id"]]
                )

    def test_private_rows_use_only_explicit_non_authoritative_branch_sentinel(self) -> None:
        constellation = _constellation()
        local, _pins = _local_manifest()
        manifest = adapt_exact_source_manifest(local, constellation, artifact_id="PRIVATE")
        private_rows = [row for row in manifest["sources"] if row["visibility"] == "private"]
        self.assertEqual(len(private_rows), 3)
        for row in private_rows:
            self.assertEqual(
                set(row), {"repository_id", "visibility", "branch", "sha"}
            )
            self.assertEqual(row["branch"], PRIVATE_BRANCH_SENTINEL)
            for forbidden in ("repository", "name", "full_name", "clone_url", "html_url"):
                self.assertNotIn(forbidden, row)

    def test_tampered_local_exact_manifest_fails_closed(self) -> None:
        constellation = _constellation()
        local, _pins = _local_manifest()
        tampered = copy.deepcopy(local)
        tampered["sources"][0]["pin"]["value"] = "0" * 40
        with self.assertRaisesRegex(
            ExactSourceToNexusManifestError, "LOCAL_EXACT_MANIFEST_VERIFY_FAILED"
        ):
            adapt_exact_source_manifest(tampered, constellation, artifact_id="TAMPER")

    def test_private_visibility_drift_fails_closed(self) -> None:
        constellation = _constellation()
        local, _pins = _local_manifest()
        private_id = constellation["private_repository_slots"][0]["repository_id"]
        drifted = copy.deepcopy(local)
        for row in drifted["sources"]:
            if row["source_id"] == private_id:
                row["visibility"] = "public"
        with self.assertRaises(ExactSourceToNexusManifestError):
            adapt_exact_source_manifest(drifted, constellation, artifact_id="DRIFT")

    def test_sensitive_output_is_new_0600_file_and_no_overwrite(self) -> None:
        constellation = _constellation()
        local, _pins = _local_manifest()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "local-sensitive-nexus-manifest.json"
            summary = adapt_and_write(
                local,
                constellation,
                output,
                artifact_id="LOCAL-WRITE",
            )
            self.assertTrue(output.is_file())
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
            self.assertFalse(summary["private_exact_pin_printed"])
            self.assertFalse(summary["private_repository_identity_published"])
            self.assertFalse(summary["network_acquisition_performed"])
            self.assertFalse(summary["source_writeback_performed"])
            self.assertEqual(summary["authority_delta"], 0)
            with self.assertRaisesRegex(
                ExactSourceToNexusManifestError,
                "SENSITIVE_NEXUS_MANIFEST_WRITE_FAILED",
            ):
                adapt_and_write(
                    local,
                    constellation,
                    output,
                    artifact_id="LOCAL-WRITE",
                )

    def test_bridge_validator_rejects_private_identity_widening(self) -> None:
        constellation = _constellation()
        local, _pins = _local_manifest()
        manifest = adapt_exact_source_manifest(local, constellation, artifact_id="WIDEN")
        widened = copy.deepcopy(manifest)
        private = next(row for row in widened["sources"] if row["visibility"] == "private")
        private["repository"] = "SHOULD-NOT-EXIST"
        with self.assertRaisesRegex(
            ExactSourceToNexusManifestError, "NEXUS_PRIVATE_SOURCE_FIELDS_INVALID"
        ):
            validate_adapted_manifest(widened)

    def test_adapter_source_has_no_process_or_network_surface(self) -> None:
        source = (TOOLS / "janus_exact_source_to_nexus_manifest.py").read_text(
            encoding="utf-8"
        )
        forbidden = (
            "subprocess",
            "requests",
            "urllib.request",
            "socket",
            "git clone",
            "git fetch",
            "git push",
            "git pull",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
