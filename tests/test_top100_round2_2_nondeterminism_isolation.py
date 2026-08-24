# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools import run_top100_round2_2_nondeterminism_isolation as iso


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "benchmarks/round2_2_nondeterminism_isolation_v0.1.json"
CRITICAL = ROOT / "benchmarks/frozen_samples/top100_round2_fp16_critical_reference_v0.1.json"


class Round22NondeterminismIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.critical = json.loads(CRITICAL.read_text(encoding="utf-8"))

    def test_config_preserves_exact_parent_spec_and_model_identities(self) -> None:
        cfg = self.config
        self.assertEqual(cfg["schema"], iso.CONFIG_SCHEMA)
        self.assertEqual(
            cfg["critical_set_canonical_sha256"],
            "aa04c2befda34e6a9a27b73360c55150617d3008f1d8fe82a6b49ad93f14e97c",
        )
        self.assertEqual(cfg["inference"]["seed"], 1138)
        self.assertEqual(cfg["inference"]["temperature"], 0.0)
        self.assertEqual(cfg["inference"]["num_predict"], 512)
        self.assertEqual(
            cfg["models"]["Q8_0"]["expected_digest"],
            "84d044692a2ce0a5a063d3177ca7a69fb189fd81b3139a7a3ead74ccf42a51dc",
        )
        self.assertEqual(
            cfg["models"]["FP16"]["expected_digest"],
            "c82efd44bfdceead1596114a378e8c9f4f3c4509e98af0c034e1dcd5396f0547",
        )

    def test_focused_subset_does_not_redefine_critical_membership(self) -> None:
        critical_ids = [row["sample_id"] for row in self.critical["critical_set"]]
        self.assertEqual(critical_ids, self.config["critical_sample_ids"])
        focus = self.config["focused_diagnostic_sample_ids"]
        self.assertEqual(focus, ["gsm8k-test-0000", "truthfulqa-row-0004"])
        self.assertTrue(set(focus) < set(critical_ids))
        self.assertFalse(self.config["diagnostic_semantics"]["changes_critical_membership"])

    def test_phase_schedule_is_exact_and_unique(self) -> None:
        schedule = iso.build_schedule(self.config, self.critical)
        self.assertEqual(len(schedule), 144)
        keys = {
            (r["phase_id"], r["target_model_id"], r["sample_id"], r["replay"])
            for r in schedule
        }
        self.assertEqual(len(keys), 144)
        counts = {}
        for row in schedule:
            counts[row["phase_id"]] = counts.get(row["phase_id"], 0) + 1
        self.assertEqual(counts, {
            "Q8_WARM_FULL": 24,
            "Q8_COLD_FULL": 24,
            "Q8_SWITCH_FROM_FP16_FULL": 24,
            "FP16_WARM_FULL": 24,
            "Q8_WARM_FOCUS": 24,
            "Q8_COLD_FOCUS": 24,
        })
        primers = [row for row in schedule if row.get("primer_model_id")]
        self.assertEqual(len(primers), 24)
        self.assertTrue(all(row["primer_model_id"] == "FP16" for row in primers))

    def test_phase_assessment_detects_status_and_output_divergence(self) -> None:
        rows = [
            {
                "phase_id": "P",
                "record_role": "TARGET",
                "sample_id": "x",
                "status": "PASS",
                "output_sha256": "a",
                "backend_attempt": 1,
            },
            {
                "phase_id": "P",
                "record_role": "TARGET",
                "sample_id": "x",
                "status": "FAIL",
                "output_sha256": "b",
                "backend_attempt": 1,
            },
        ]
        assessment = iso._phase_assessment(rows, "P")
        self.assertEqual(assessment["pass_count"], 1)
        self.assertEqual(assessment["nonpass_count"], 1)
        self.assertEqual(assessment["within_phase_status_instability"]["x"], ["PASS", "FAIL"])
        self.assertEqual(
            assessment["within_phase_output_divergence"]["x"]["unique_output_count"], 2
        )

    def test_localization_prefers_warm_instability_when_present(self) -> None:
        def a(unstable=()):
            return {"within_phase_status_instability": {sid: ["PASS", "FAIL"] for sid in unstable}}
        assessments = {
            "Q8_WARM_FULL": a(["gsm8k-test-0000"]),
            "Q8_COLD_FULL": a(),
            "Q8_SWITCH_FROM_FP16_FULL": a(),
            "FP16_WARM_FULL": a(),
            "Q8_WARM_FOCUS": a(),
            "Q8_COLD_FOCUS": a(),
        }
        result = iso._localization(assessments)
        self.assertEqual(
            result["classification"],
            "STATUS_INSTABILITY_PERSISTS_WITHOUT_FORCED_MODEL_RELOAD",
        )
        self.assertFalse(result["causal_claimed"])

    def test_localization_can_associate_reload_without_claiming_causation(self) -> None:
        def a(unstable=()):
            return {"within_phase_status_instability": {sid: ["PASS", "FAIL"] for sid in unstable}}
        assessments = {
            "Q8_WARM_FULL": a(),
            "Q8_COLD_FULL": a(["truthfulqa-row-0004"]),
            "Q8_SWITCH_FROM_FP16_FULL": a(),
            "FP16_WARM_FULL": a(),
            "Q8_WARM_FOCUS": a(),
            "Q8_COLD_FOCUS": a(["truthfulqa-row-0004"]),
        }
        result = iso._localization(assessments)
        self.assertEqual(
            result["classification"],
            "STATUS_INSTABILITY_ASSOCIATED_WITH_FORCED_RELOAD_PATH_IN_THIS_RUN",
        )
        self.assertFalse(result["causal_claimed"])

    def test_model_ps_parser_is_exact(self) -> None:
        value = {
            "models": [
                {"name": "qwen2.5:0.5b-instruct-q8_0"},
                {"model": "qwen2.5:0.5b-instruct-fp16"},
            ]
        }
        self.assertEqual(
            iso._model_names_from_ps(value),
            ["qwen2.5:0.5b-instruct-fp16", "qwen2.5:0.5b-instruct-q8_0"],
        )


if __name__ == "__main__":
    unittest.main()
