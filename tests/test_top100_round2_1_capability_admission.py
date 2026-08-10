# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from tools import run_top100_round2_1_capability_admission as gate

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "benchmarks" / "round2_1_capability_preserving_quantization_admission_v0.1.json"
CRITICAL = ROOT / "benchmarks" / "frozen_samples" / "top100_round2_fp16_critical_reference_v0.1.json"
PACK = ROOT / "benchmarks" / "frozen_samples" / "top100_round1_stratified_v0.1.json"


class Round21CapabilityAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        cls.critical = json.loads(CRITICAL.read_text(encoding="utf-8"))
        cls.pack = json.loads(PACK.read_text(encoding="utf-8"))

    def test_frozen_critical_reference_validates_against_unchanged_pack(self) -> None:
        rows, sample_map = gate._validate_critical_reference(
            self.config, self.critical, self.pack
        )
        self.assertEqual(8, len(rows))
        self.assertEqual(21, len(sample_map))
        self.assertEqual(
            "aa04c2befda34e6a9a27b73360c55150617d3008f1d8fe82a6b49ad93f14e97c",
            self.critical["critical_set_canonical_sha256"],
        )
        self.assertEqual(
            [
                "gsm8k-test-0000",
                "gsm8k-test-0001",
                "gsm8k-test-0003",
                "ifeval-key-1019",
                "ifeval-key-1092",
                "truthfulqa-row-0001",
                "truthfulqa-row-0002",
                "truthfulqa-row-0004",
            ],
            [row["sample_id"] for row in rows],
        )

    def test_candidate_results_cannot_shrink_critical_membership(self) -> None:
        bad = json.loads(json.dumps(self.critical))
        bad["critical_set"] = bad["critical_set"][:-1]
        bad["critical_set_count"] = 7
        bad["source_fp16_pass_count"] = 7
        with self.assertRaises(ValueError):
            gate._validate_critical_reference(self.config, bad, self.pack)

    def test_all_quantization_tags_are_same_0_5b_instruct_family(self) -> None:
        candidates = self.config["candidates"]
        self.assertEqual(14, len(candidates))
        tags = [row["tag"] for row in candidates]
        self.assertEqual(len(tags), len(set(tags)))
        self.assertNotIn(self.config["reference"]["tag"], tags)
        self.assertTrue(all(tag.startswith("qwen2.5:0.5b-instruct-q") for tag in tags))

    def test_one_critical_failure_rejects_candidate_even_with_23_passes(self) -> None:
        records = []
        ids = [row["sample_id"] for row in self.critical["critical_set"]]
        for replay in range(1, 4):
            for sid in ids:
                status = "PASS"
                if replay == 3 and sid == ids[-1]:
                    status = "FAIL"
                records.append({
                    "model_id": "QX",
                    "replay": replay,
                    "sample_id": sid,
                    "benchmark": "X",
                    "status": status,
                    "grader_detail": {},
                })
        result = gate._assessment(records, "QX", critical_count=8, replays=3)
        self.assertEqual(23, result["pass_trials"])
        self.assertEqual(1, result["nonpass_trials"])
        self.assertFalse(result["strict_capability_preservation"])
        self.assertEqual(
            "REJECTED_CRITICAL_CAPABILITY_REGRESSION_OBSERVED",
            result["admission_status"],
        )

    def test_all_24_critical_trials_required_for_admission(self) -> None:
        records = []
        ids = [row["sample_id"] for row in self.critical["critical_set"]]
        for replay in range(1, 4):
            for sid in ids:
                records.append({
                    "model_id": "QX",
                    "replay": replay,
                    "sample_id": sid,
                    "benchmark": "X",
                    "status": "PASS",
                    "grader_detail": {},
                })
        result = gate._assessment(records, "QX", critical_count=8, replays=3)
        self.assertEqual(24, result["pass_trials"])
        self.assertTrue(result["strict_capability_preservation"])
        self.assertEqual(
            "ADMITTED_CAPABILITY_PRESERVING_IN_TESTED_CRITICAL_SCOPE",
            result["admission_status"],
        )

    def test_replay_instability_is_not_hidden_by_total_pass_count(self) -> None:
        records = []
        ids = [row["sample_id"] for row in self.critical["critical_set"]]
        for replay in range(1, 4):
            for sid in ids:
                records.append({
                    "model_id": "QX",
                    "replay": replay,
                    "sample_id": sid,
                    "benchmark": "X",
                    "status": "FAIL" if sid == ids[0] and replay == 2 else "PASS",
                    "grader_detail": {},
                })
        result = gate._assessment(records, "QX", critical_count=8, replays=3)
        self.assertIn(ids[0], result["within_model_status_instability"])
        self.assertFalse(result["strict_capability_preservation"])

    def test_backend_retry_is_bounded_and_only_for_infrastructure_errors(self) -> None:
        class Provider:
            model = "fake"
            def __init__(self) -> None:
                self.calls = 0
            def chat(self, messages):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("HTTP 500 llama-server process has terminated")
                return "model answer"

        provider = Provider()
        with mock.patch.object(gate.time, "sleep", return_value=None):
            output, attempt = gate._chat_with_backend_retry(provider, [{"role":"user","content":"x"}])
        self.assertEqual("model answer", output)
        self.assertEqual(2, attempt)
        self.assertEqual(2, provider.calls)

    def test_non_infrastructure_runtime_error_is_not_retried(self) -> None:
        class Provider:
            model = "fake"
            def __init__(self) -> None:
                self.calls = 0
            def chat(self, messages):
                self.calls += 1
                raise RuntimeError("digest mismatch")

        provider = Provider()
        with self.assertRaises(RuntimeError):
            gate._chat_with_backend_retry(provider, [{"role":"user","content":"x"}])
        self.assertEqual(1, provider.calls)


if __name__ == "__main__":
    unittest.main()
