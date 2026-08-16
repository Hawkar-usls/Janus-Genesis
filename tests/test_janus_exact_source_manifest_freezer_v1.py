from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from janus_exact_source_manifest_freezer import (  # noqa: E402
    ExactSourceManifestError,
    build_public_receipt,
    constellation_binding_digest,
    freeze_exact_source_manifest,
    verify_frozen_manifest,
    write_new_json,
)
from janus_source_pin_contract import (  # noqa: E402
    GIT_COMMIT_SHA1,
    OPAQUE_VERSION_TOKEN,
)


REAL_CONSTELLATION = (
    ROOT / "protocol" / "JANUS_GENESIS_GIT_HABITAT_REPOSITORY_CONSTELLATION-v1.0.json"
)


def sha_for(number: int) -> str:
    return f"{number:040x}"[-40:]


def synthetic_constellation() -> dict:
    public = [
        {"id": str(1000 + i), "name": f"public-{i}", "default_branch": "main"}
        for i in range(41)
    ]
    private = [
        {
            "repository_id": str(2000 + i),
            "visibility": "private",
            "resolution": "AUTHENTICATED_RESOLUTION_REQUIRED",
        }
        for i in range(3)
    ]
    return {
        "schema": "janus.genesis.git_habitat.repository_constellation.v1",
        "repository_count": 44,
        "public_repository_count": 41,
        "private_repository_count": 3,
        "public_repositories": public,
        "private_repository_slots": private,
    }


def pinset_for(constellation: dict, *, pinset_id: str = "LOCAL-SECRET-PINSET") -> dict:
    rows = []
    counter = 1
    for source in constellation["public_repositories"]:
        rows.append(
            {
                "source_id": str(source["id"]),
                "visibility": "public",
                "source_kind": "GIT_REPOSITORY",
                "pin": {"kind": GIT_COMMIT_SHA1, "value": sha_for(counter)},
            }
        )
        counter += 1
    for source in constellation["private_repository_slots"]:
        rows.append(
            {
                "source_id": str(source["repository_id"]),
                "visibility": "private",
                "source_kind": "GIT_REPOSITORY",
                "pin": {"kind": GIT_COMMIT_SHA1, "value": sha_for(counter)},
            }
        )
        counter += 1
    return {
        "schema": "janus.source_pin_set.v1",
        "pinset_id": pinset_id,
        "sources": rows,
    }


class ExactSourceManifestFreezerTests(unittest.TestCase):
    def test_real_constellation_binds_exactly_44_slots_without_private_names(self):
        constellation = json.loads(REAL_CONSTELLATION.read_text(encoding="utf-8"))
        local = freeze_exact_source_manifest(pinset_for(constellation), constellation)
        self.assertEqual(local["source_count"], 44)
        self.assertEqual(local["public_source_count"], 41)
        self.assertEqual(local["private_source_count"], 3)
        self.assertTrue(local["constellation_binding_sha256"])
        receipt = build_public_receipt(local, constellation)
        self.assertEqual(len(receipt["public_sources"]), 41)
        self.assertEqual(len(receipt["private_sources"]), 3)
        self.assertTrue(
            all(
                set(row)
                == {
                    "source_id",
                    "visibility",
                    "local_exact_git_pin_verified",
                    "exact_pin_published",
                    "history_digest_published",
                }
                for row in receipt["private_sources"]
            )
        )

    def test_public_receipt_omits_private_pins_local_digest_and_pinset_id(self):
        constellation = synthetic_constellation()
        pinset = pinset_for(
            constellation, pinset_id="DO-NOT-PUBLISH-THIS-PINSET-ID"
        )
        private_values = [
            row["pin"]["value"]
            for row in pinset["sources"]
            if row["visibility"] == "private"
        ]
        local = freeze_exact_source_manifest(pinset, constellation)
        receipt = build_public_receipt(local, constellation)
        serialized = json.dumps(receipt, sort_keys=True)

        for value in private_values:
            self.assertNotIn(value, serialized)
        self.assertNotIn(local["local_manifest_digest"], serialized)
        self.assertNotIn("DO-NOT-PUBLISH-THIS-PINSET-ID", serialized)
        self.assertNotIn("local_manifest_digest", receipt)
        self.assertNotIn("local_pinset_id", receipt)
        self.assertFalse(receipt["private_exact_pins_published"])
        self.assertFalse(receipt["private_history_digests_published"])
        self.assertFalse(receipt["whole_local_manifest_digest_published"])
        self.assertFalse(receipt["local_pinset_id_published"])

    def test_public_receipt_keeps_public_exact_pins_replayable(self):
        constellation = synthetic_constellation()
        pinset = pinset_for(constellation)
        local = freeze_exact_source_manifest(pinset, constellation)
        receipt = build_public_receipt(local, constellation)
        expected_public = {
            row["source_id"]: row["pin"]["value"]
            for row in pinset["sources"]
            if row["visibility"] == "public"
        }
        observed_public = {
            row["source_id"]: row["exact_commit_sha"]
            for row in receipt["public_sources"]
        }
        self.assertEqual(observed_public, expected_public)
        self.assertTrue(receipt["public_source_set_digest"])

    def test_top_level_private_metadata_cannot_fingerprint_public_binding(self):
        constellation = synthetic_constellation()
        pinset = pinset_for(constellation)
        baseline_local = freeze_exact_source_manifest(pinset, constellation)
        baseline_receipt = build_public_receipt(baseline_local, constellation)

        enriched = json.loads(json.dumps(constellation))
        enriched["LOCAL_PRIVATE_NOTE"] = "PRIVATE-CANARY-DO-NOT-FINGERPRINT"
        enriched["authenticated_local_context"] = {
            "secret": "ANOTHER-PRIVATE-CANARY"
        }
        enriched_local = freeze_exact_source_manifest(pinset, enriched)
        enriched_receipt = build_public_receipt(enriched_local, enriched)

        self.assertEqual(
            constellation_binding_digest(constellation),
            constellation_binding_digest(enriched),
        )
        self.assertEqual(
            baseline_local["constellation_binding_sha256"],
            enriched_local["constellation_binding_sha256"],
        )
        self.assertEqual(
            baseline_local["local_manifest_digest"],
            enriched_local["local_manifest_digest"],
        )
        self.assertEqual(baseline_receipt, enriched_receipt)
        serialized = json.dumps(enriched_receipt, sort_keys=True)
        self.assertNotIn("PRIVATE-CANARY-DO-NOT-FINGERPRINT", serialized)
        self.assertNotIn("ANOTHER-PRIVATE-CANARY", serialized)

    def test_private_row_extra_metadata_is_rejected_before_binding(self):
        constellation = synthetic_constellation()
        constellation["private_repository_slots"][0]["private_name"] = "SECRET-NAME"
        with self.assertRaisesRegex(
            ExactSourceManifestError,
            "CONSTELLATION_PRIVATE_ROW_FIELDS_INVALID",
        ):
            freeze_exact_source_manifest(pinset_for(constellation), constellation)

    def test_public_row_extra_metadata_is_rejected_before_binding(self):
        constellation = synthetic_constellation()
        constellation["public_repositories"][0]["unexpected"] = "not-in-binding"
        with self.assertRaisesRegex(
            ExactSourceManifestError,
            "CONSTELLATION_PUBLIC_ROW_FIELDS_INVALID",
        ):
            freeze_exact_source_manifest(pinset_for(constellation), constellation)

    def test_source_order_does_not_change_local_freeze(self):
        constellation = synthetic_constellation()
        first = pinset_for(constellation)
        second = pinset_for(constellation)
        second["sources"] = list(reversed(second["sources"]))
        self.assertEqual(
            freeze_exact_source_manifest(first, constellation),
            freeze_exact_source_manifest(second, constellation),
        )

    def test_constellation_row_order_does_not_change_binding(self):
        first = synthetic_constellation()
        second = json.loads(json.dumps(first))
        second["public_repositories"] = list(reversed(second["public_repositories"]))
        second["private_repository_slots"] = list(
            reversed(second["private_repository_slots"])
        )
        pins = pinset_for(first)
        self.assertEqual(
            constellation_binding_digest(first),
            constellation_binding_digest(second),
        )
        self.assertEqual(
            freeze_exact_source_manifest(pins, first),
            freeze_exact_source_manifest(pins, second),
        )

    def test_missing_or_extra_source_fails_closed(self):
        constellation = synthetic_constellation()
        missing = pinset_for(constellation)
        missing["sources"].pop()
        with self.assertRaisesRegex(
            ExactSourceManifestError, "PINSET_CONSTELLATION_ID_MISMATCH"
        ):
            freeze_exact_source_manifest(missing, constellation)

        extra = pinset_for(constellation)
        extra["sources"].append(
            {
                "source_id": "999999",
                "visibility": "public",
                "source_kind": "GIT_REPOSITORY",
                "pin": {"kind": GIT_COMMIT_SHA1, "value": "f" * 40},
            }
        )
        with self.assertRaisesRegex(
            ExactSourceManifestError, "PINSET_CONSTELLATION_ID_MISMATCH"
        ):
            freeze_exact_source_manifest(extra, constellation)

    def test_visibility_drift_fails_closed(self):
        constellation = synthetic_constellation()
        pinset = pinset_for(constellation)
        private = next(
            row for row in pinset["sources"] if row["visibility"] == "private"
        )
        private["visibility"] = "public"
        with self.assertRaisesRegex(
            ExactSourceManifestError, "SOURCE_VISIBILITY_MISMATCH"
        ):
            freeze_exact_source_manifest(pinset, constellation)

    def test_sha_shaped_opaque_token_cannot_satisfy_exact_manifest(self):
        constellation = synthetic_constellation()
        pinset = pinset_for(constellation)
        pinset["sources"][0]["pin"] = {
            "kind": OPAQUE_VERSION_TOKEN,
            "value": "a" * 40,
        }
        with self.assertRaisesRegex(ExactSourceManifestError, "PINSET_NOT_EXACT_GIT"):
            freeze_exact_source_manifest(pinset, constellation)

    def test_local_manifest_tamper_is_rejected(self):
        constellation = synthetic_constellation()
        local = freeze_exact_source_manifest(pinset_for(constellation), constellation)
        local["sources"][0]["pin"]["value"] = "e" * 40
        with self.assertRaisesRegex(
            ExactSourceManifestError, "LOCAL_FROZEN_MANIFEST_REPLAY_MISMATCH"
        ):
            verify_frozen_manifest(local, constellation)

    def test_constellation_binding_tamper_is_rejected(self):
        constellation = synthetic_constellation()
        local = freeze_exact_source_manifest(pinset_for(constellation), constellation)
        changed = json.loads(json.dumps(constellation))
        changed["public_repositories"][0]["name"] = "renamed-public-source"
        with self.assertRaisesRegex(
            ExactSourceManifestError,
            "LOCAL_CONSTELLATION_BINDING_DIGEST_MISMATCH",
        ):
            verify_frozen_manifest(local, changed)

    def test_sensitive_local_write_is_0600_and_no_overwrite(self):
        constellation = synthetic_constellation()
        local = freeze_exact_source_manifest(pinset_for(constellation), constellation)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "local-exact-manifest.json"
            write_new_json(path, local, mode=0o600)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaisesRegex(ExactSourceManifestError, "OUTPUT_ALREADY_EXISTS"):
                write_new_json(path, local, mode=0o600)

    def test_symlinked_output_parent_is_rejected(self):
        constellation = synthetic_constellation()
        local = freeze_exact_source_manifest(pinset_for(constellation), constellation)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            try:
                linked.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(
                ExactSourceManifestError,
                "OUTPUT_PARENT_MUST_NOT_CONTAIN_SYMLINKS",
            ):
                write_new_json(linked / "secret.json", local, mode=0o600)

    def test_symlinked_output_ancestor_is_rejected(self):
        constellation = synthetic_constellation()
        local = freeze_exact_source_manifest(pinset_for(constellation), constellation)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real"
            nested = real / "nested"
            nested.mkdir(parents=True)
            linked = root / "linked"
            try:
                linked.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(
                ExactSourceManifestError,
                "OUTPUT_PARENT_MUST_NOT_CONTAIN_SYMLINKS",
            ):
                write_new_json(linked / "nested" / "secret.json", local, mode=0o600)


if __name__ == "__main__":
    unittest.main()
