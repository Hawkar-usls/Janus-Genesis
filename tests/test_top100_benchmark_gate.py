from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.run_top100_benchmark_gate import (
    SAMPLE_SCHEMA,
    grade_answer,
    readiness_report,
    run_sample_pack,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "benchmarks" / "top100_public_ai_benchmarks_v0.1.json"


class FakeProvider:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.replies.pop(0)


class Top100BenchmarkGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_is_exactly_100_unique_benchmarks(self) -> None:
        result = validate_manifest(self.manifest)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["benchmark_count"], 100)
        self.assertEqual(
            result["target_counts"],
            {"external_environment": 16, "provider": 68, "system_plus_provider": 16},
        )

    def test_manifest_rejects_duplicate_name(self) -> None:
        broken = copy.deepcopy(self.manifest)
        broken["benchmarks"][1]["name"] = broken["benchmarks"][0]["name"]
        result = validate_manifest(broken)
        self.assertFalse(result["valid"])
        self.assertIn("benchmark names must be unique", result["errors"])

    def test_no_provider_is_blocked_not_failed(self) -> None:
        report = readiness_report(
            self.manifest,
            provider_available=False,
            universal_chat_executor_available=False,
            external_environment_available=False,
        )
        self.assertEqual(report["status_counts"]["BLOCKED_NO_PROVIDER"], 68)
        self.assertEqual(report["status_counts"]["BLOCKED_NO_COMPOSITE_EXECUTOR"], 16)
        self.assertEqual(report["status_counts"]["BLOCKED_NO_EXTERNAL_ENV"], 16)
        self.assertFalse(report["official_dataset_accuracy_claimed"])
        self.assertFalse(report["canonical_world_state_mutated"])
        self.assertFalse(any(item["status"] == "FAIL" for item in report["benchmarks"]))

    def test_provider_readiness_does_not_unlock_external_environment(self) -> None:
        report = readiness_report(
            self.manifest,
            provider_available=True,
            universal_chat_executor_available=True,
            external_environment_available=False,
        )
        self.assertEqual(report["status_counts"]["READY_FOR_DATASET_EXECUTION"], 68)
        self.assertEqual(report["status_counts"]["READY_FOR_COMPOSITE_EXECUTION"], 16)
        self.assertEqual(report["status_counts"]["BLOCKED_NO_EXTERNAL_ENV"], 16)

    def test_graders(self) -> None:
        self.assertTrue(grade_answer("  Paris\n", "Paris", "exact")[0])
        self.assertTrue(grade_answer("answer: 42", "42", "contains")[0])
        self.assertTrue(grade_answer("A=17", r"A=\d+", "regex")[0])
        with self.assertRaises(ValueError):
            grade_answer("x", "x", "unknown")

    def test_sample_pack_executes_provider_sample_but_not_external_env_sample(self) -> None:
        pack = {
            "schema": SAMPLE_SCHEMA,
            "pack_id": "UNIT-SMOKE-ONLY",
            "samples": [
                {
                    "sample_id": "smoke-provider-1",
                    "benchmark": "MMLU",
                    "prompt": "Return exactly Paris",
                    "expected": "Paris",
                    "grader": "exact"
                },
                {
                    "sample_id": "smoke-external-1",
                    "benchmark": "HumanEval",
                    "prompt": "This is not executed in this unit test",
                    "expected": "unused",
                    "grader": "exact"
                }
            ]
        }
        provider = FakeProvider(["Paris"])
        report = run_sample_pack(pack, self.manifest, provider)
        self.assertEqual(report["scored"], 1)
        self.assertEqual(report["passed"], 1)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["score_label"], "SAMPLE_PACK_ONLY")
        self.assertFalse(report["official_dataset_accuracy_claimed"])
        self.assertFalse(report["canonical_world_state_mutated"])
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(
            report["receipts"][1]["status"],
            "NOT_EXECUTED_EXTERNAL_ENV_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()
