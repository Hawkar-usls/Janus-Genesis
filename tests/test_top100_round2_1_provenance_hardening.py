# -*- coding: utf-8 -*-
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
            config_path=CONFIG,
            critical_path=CRITICAL,
            pack_path=PACK,
        )
        self.assertEqual(hard.PROVENANCE_STATUS, receipt["status"])
        self.assertTrue(receipt["receipt_fields_derived_from_verified_declarations"])
        self.assertTrue(receipt["single_snapshot_consumption"])
        self.assertTrue(receipt["verified_bytes_are_execution_bytes"])
        self.assertTrue(receipt["repository_root_independent_of_process_cwd"])
        self.assertEqual(hard.git_blob_sha1(CONFIG), receipt["observed_config_git_blob_sha1"])

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

    def test_absolute_repository_inputs_are_stable_outside_repository_cwd(self) -> None:
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                receipt = hard.validate_provenance(
                    self.config,
                    self.critical,
                    config_path=CONFIG,
                    critical_path=CRITICAL,
                    pack_path=PACK,
                )
            finally:
                os.chdir(old_cwd)
        self.assertEqual(
            self.config["critical_reference"],
            receipt["critical_reference_path"],
        )
        self.assertEqual(self.config["round1_pack"], receipt["round1_pack_path"])
        self.assertTrue(receipt["repository_root_independent_of_process_cwd"])

    def test_main_uses_direct_execute_not_historical_rereading_cli(self) -> None:
        argv = [
            "--config", str(CONFIG),
            "--critical-reference", str(CRITICAL),
            "--pack", str(PACK),
            "--endpoint", "http://127.0.0.1:11434",
            "--docker-image", "python:3.11-alpine",
            "--timeout", "1",
        ]
        fake_report = {"schema": "unit-test-report"}
        with mock.patch.object(
            hard.gate,
            "main",
            side_effect=AssertionError("historical CLI must not be called"),
        ) as old_main, mock.patch.object(
            hard.gate,
            "execute",
            return_value=fake_report.copy(),
        ) as execute, io.StringIO() as out, contextlib.redirect_stdout(out):
            rc = hard.main(argv)
            payload = json.loads(out.getvalue())

        self.assertEqual(0, rc)
        old_main.assert_not_called()
        execute.assert_called_once()
        self.assertEqual(
            hard.PROVENANCE_STATUS,
            payload["provenance_verification"]["status"],
        )
        self.assertTrue(payload["provenance_verification"]["single_snapshot_consumption"])
        self.assertTrue(payload["provenance_verification"]["verified_bytes_are_execution_bytes"])
        self.assertTrue(payload["provenance_verification"]["repository_root_independent_of_process_cwd"])


if __name__ == "__main__":
    unittest.main()
