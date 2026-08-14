# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools import run_top100_round2_3_warm_state_mechanism_isolation as r23

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "benchmarks/round2_3_warm_state_mechanism_isolation_v0.1.json"


class Round23WarmStateMechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_full_frozen_lineage_validates_offline(self) -> None:
        parent22, critical, pack, provenance = r23.validate_config(self.config)
        self.assertEqual(parent22["schema"], "janus.genesis.round2_2_nondeterminism_isolation.v1")
        self.assertEqual(critical["critical_set_count"], 8)
        self.assertEqual(
            critical["critical_set_canonical_sha256"],
            "aa04c2befda34e6a9a27b73360c55150617d3008f1d8fe82a6b49ad93f14e97c",
        )
        self.assertEqual(len(pack["samples"]), 21)
        self.assertEqual(provenance["status"], "VERIFIED_AGAINST_ACTUAL_CONSUMED_BYTES")

    def test_schedule_has_exact_seven_phase_144_record_shape(self) -> None:
        schedule = r23.build_schedule(self.config)
        self.assertEqual(len(schedule), 144)
        counts = {}
        for row in schedule:
            counts[row["phase_id"]] = counts.get(row["phase_id"], 0) + 1
        self.assertEqual(counts, {
            "Q8_WARM_GSM_ALONE": 12,
            "Q8_WARM_TRUTH_ALONE": 12,
            "Q8_WARM_PAIR_GSM_TRUTH": 24,
            "Q8_WARM_PAIR_TRUTH_GSM": 24,
            "Q8_WARM_GSM_WITH_STABLE_SEPARATOR": 24,
            "Q8_WARM_TRUTH_WITH_STABLE_SEPARATOR": 24,
            "Q8_COLD_FOCUS_CONFIRM": 24,
        })
        self.assertEqual([row["global_ordinal"] for row in schedule], list(range(1, 145)))

    def test_focal_samples_stay_inside_frozen_critical_set(self) -> None:
        self.assertEqual(self.config["focal_samples"]["GSM"], "gsm8k-test-0000")
        self.assertEqual(self.config["focal_samples"]["TRUTH"], "truthfulqa-row-0004")
        self.assertEqual(self.config["focal_samples"]["STABLE_SEPARATOR"], "gsm8k-test-0001")
        semantics = self.config["diagnostic_semantics"]
        self.assertFalse(semantics["critical_membership_changed"])
        self.assertFalse(semantics["admission_rule_changed"])
        self.assertFalse(semantics["promotion_rule_changed"])
        self.assertFalse(semantics["model_identity_changed"])

    def test_sample_assessment_detects_same_request_output_divergence(self) -> None:
        rows = [
            {
                "cycle": 1,
                "position_in_cycle": 1,
                "status": "PASS",
                "output_sha256": "a",
                "request_payload_sha256": "same",
                "server_identities_after": ["10:100:x"],
            },
            {
                "cycle": 2,
                "position_in_cycle": 1,
                "status": "FAIL",
                "output_sha256": "b",
                "request_payload_sha256": "same",
                "server_identities_after": ["10:100:x"],
            },
        ]
        result = r23._sample_assessment(rows)
        self.assertEqual(result["unique_request_payload_count"], 1)
        self.assertEqual(result["unique_output_count"], 2)
        self.assertEqual(result["unique_server_process_identity_count"], 1)
        self.assertTrue(result["output_divergence"])
        self.assertTrue(result["status_divergence"])

    def test_server_identity_includes_pid_start_time_and_cmd_hash(self) -> None:
        rows = [
            {"pid": 7, "start_time_ticks": 123, "cmdline_sha256": "abc"},
            {"pid": 7, "start_time_ticks": 123, "cmdline_sha256": "abc"},
            {"pid": 8, "start_time_ticks": 200, "cmdline_sha256": "def"},
        ]
        self.assertEqual(r23._server_identity_set(rows), ["7:123:abc", "8:200:def"])

    def test_inference_spec_remains_exact(self) -> None:
        self.assertEqual(self.config["inference"]["seed"], 1138)
        self.assertEqual(self.config["inference"]["temperature"], 0.0)
        self.assertEqual(self.config["inference"]["num_predict"], 512)
        self.assertEqual(
            self.config["q8_0"]["expected_digest"],
            "84d044692a2ce0a5a063d3177ca7a69fb189fd81b3139a7a3ead74ccf42a51dc",
        )


if __name__ == "__main__":
    unittest.main()
