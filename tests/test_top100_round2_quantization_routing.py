# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools import run_top100_round2_quantization_routing as r2

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "benchmarks" / "round2_quantization_routing_v0.1.json"
PACK = ROOT / "benchmarks" / "frozen_samples" / "top100_round1_stratified_v0.1.json"
OVERLAY = ROOT / "benchmarks" / "prompts" / "genesis_benchmark_boundary_overlay_v0.1.txt"


class Round2QuantizationRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.pack = json.loads(PACK.read_text(encoding="utf-8"))
        cls.overlay = OVERLAY.read_text(encoding="utf-8")

    def test_round1_pack_is_reused_without_editing(self) -> None:
        self.assertEqual(21, len(self.pack["samples"]))
        self.assertEqual(
            "ca27652feb3532ff52e8453dd055b608711b0d43",
            self.config["sample_pack_git_blob_sha1"],
        )
        self.assertEqual(
            "benchmarks/frozen_samples/top100_round1_stratified_v0.1.json",
            self.config["sample_pack"],
        )

    def test_quantization_ladder_is_same_model_family(self) -> None:
        rows = self.config["models"]
        self.assertEqual(["FP16", "Q8_0", "Q4_K_M"], [x["id"] for x in rows])
        self.assertEqual(
            [
                "qwen2.5:0.5b-instruct-fp16",
                "qwen2.5:0.5b-instruct-q8_0",
                "qwen2.5:0.5b-instruct-q4_K_M",
            ],
            [x["tag"] for x in rows],
        )

    def test_all_legacy_round1_samples_route_neutral(self) -> None:
        routes = [r2.routed_messages(sample, self.overlay)[0] for sample in self.pack["samples"]]
        self.assertEqual(["NEUTRAL_BENCHMARK_PATH"] * 21, routes)

    def test_explicit_external_effect_routes_constitutional(self) -> None:
        probe = dict(self.pack["samples"][0])
        probe["sample_id"] = "synthetic-external-effect-router-probe"
        probe["boundary_relevance"] = ["external_effect", "consent"]
        route, messages = r2.routed_messages(probe, self.overlay)
        self.assertEqual("CONSTITUTIONAL_BOUNDARY_PATH", route)
        self.assertEqual("system", messages[0]["role"])
        self.assertIn("JANUS GENESIS BENCHMARK BOUNDARY", messages[0]["content"])

    def test_prompt_words_do_not_manufacture_constitutional_jurisdiction(self) -> None:
        probe = dict(self.pack["samples"][0])
        probe["sample_id"] = "synthetic-word-only-probe"
        probe["prompt"] = "The words consent authority delegation appear here as plain text. What is 2+2?"
        route, messages = r2.routed_messages(probe, self.overlay)
        self.assertEqual("NEUTRAL_BENCHMARK_PATH", route)
        self.assertEqual(1, len(messages))

    def test_neutral_route_is_effective_input_identical_to_raw(self) -> None:
        for sample in self.pack["samples"]:
            _, routed = r2.routed_messages(sample, self.overlay)
            from tools import run_top100_round1_stratified as r1
            raw = r1._messages(sample, "RAW_PROVIDER", self.overlay)
            self.assertEqual(raw, routed)

    def test_non_regression_rule_is_strict_per_previously_passing_sample(self) -> None:
        records = [
            {"config_id":"FP16_RAW","sample_id":"a","benchmark":"X","status":"PASS","grader_detail":{}},
            {"config_id":"FP16_RAW","sample_id":"b","benchmark":"X","status":"FAIL","grader_detail":{}},
            {"config_id":"Q4_K_M_RAW","sample_id":"a","benchmark":"X","status":"FAIL","grader_detail":{}},
            {"config_id":"Q4_K_M_RAW","sample_id":"b","benchmark":"X","status":"PASS","grader_detail":{}},
        ]
        gate = r2._quantization_gate(records, "Q4_K_M_RAW")
        self.assertFalse(gate["strict_non_regression"])
        self.assertEqual("REGRESSION_OBSERVED", gate["gate_status"])
        self.assertEqual(["a"], [x["sample_id"] for x in gate["fp16_pass_to_quantized_nonpass"]])


if __name__ == "__main__":
    unittest.main()
