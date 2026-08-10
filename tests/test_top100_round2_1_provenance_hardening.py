# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools import run_top100_round2_1_capability_admission_hardened as hard

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "benchmarks" / "round2_1_capability_preserving_quantization_admission_v0.1.json"
CRITICAL = ROOT / "benchmarks" / "frozen_samples" / "top100_round2_fp16_critical_reference_v0.1.json"
PACK = ROOT / "benchmarks" / "frozen_samples" / "top100_round1_stratified_v0.1.json"


class Round21ProvenanceHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.critical = json.loads(CRITICAL.read_text(encoding="utf-8"))

    def test_actual_git_blobs_are_the_frozen_identities(self) -> None:
        self.assertEqual(
            "ca27652feb3532ff52e8453dd055b608711b0d43",
            hard.git_blob_sha1(PACK),
        )
        self.assertEqual(
            "6743337b8a6357783858c71fad01720d034b63ca",
            hard.git_blob_sha1(CRITICAL),
        )

    def test_declared_provenance_matches_actual_consumed_bytes(self) -> None:
        receipt = hard.validate_provenance(
            self.config,
            self.critical,
            config_path=Path(self.config.get("campaign", "config")),
            critical_path=Path(self.config["critical_reference"]),
            pack_path=Path(self.config["round1_pack"]),
        )
        self.assertEqual(hard.PROVENANCE_STATUS, receipt["status"])
        self.assertTrue(receipt["receipt_fields_derived_from_verified_declarations"])

    def test_tampered_config_critical_blob_is_rejected(self) -> None:
        bad = copy.deepcopy(self.config)
        bad["critical_reference_git_blob_sha1"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "critical reference blob mismatch"):
            hard.validate_provenance(
                bad,
                self.critical,
                config_path=CONFIG,
                critical_path=CRITICAL,
                pack_path=PACK,
            )

    def test_tampered_config_round1_blob_is_rejected(self) -> None:
        bad = copy.deepcopy(self.config)
        bad["round1_pack_git_blob_sha1"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "round1 pack blob mismatch"):
            hard.validate_provenance(
                bad,
                self.critical,
                config_path=CONFIG,
                critical_path=CRITICAL,
                pack_path=PACK,
            )

    def test_tampered_critical_source_round1_blob_is_rejected(self) -> None:
        bad = copy.deepcopy(self.critical)
        bad["source"]["round1_pack_git_blob_sha1"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "critical source round1 pack blob mismatch"):
            hard.validate_provenance(
                self.config,
                bad,
                config_path=CONFIG,
                critical_path=CRITICAL,
                pack_path=PACK,
            )

    def test_path_substitution_is_rejected(self) -> None:
        bad = copy.deepcopy(self.config)
        bad["round1_pack"] = "benchmarks/frozen_samples/not-the-pack.json"
        with self.assertRaisesRegex(ValueError, "round1_pack path mismatch"):
            hard.validate_provenance(
                bad,
                self.critical,
                config_path=CONFIG,
                critical_path=CRITICAL,
                pack_path=PACK,
            )


if __name__ == "__main__":
    unittest.main()
