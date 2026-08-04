from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sim.janus_113_8_sim0 import BASE_COMPUTE, ThresholdKeeper, run_suite, write_artifacts


class JanusSim0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = run_suite()
        self.by_id = {result["scenario_id"]: result for result in self.suite["results"]}

    def test_all_scenarios_pass(self) -> None:
        self.assertEqual(self.suite["scenario_count"], 10)
        self.assertTrue(self.suite["admitted"])
        self.assertEqual(self.suite["terminal"], "JANUS_113.8_SIM_0_ADMITTED")
        self.assertTrue(all(result["test_passed"] for result in self.suite["results"]))

    def test_compute_is_adaptive_and_bounded(self) -> None:
        self.assertEqual(self.by_id["T01_ROUTINE_INPUT"]["total_compute_units"], BASE_COMPUTE)
        self.assertGreater(self.by_id["T02_AMBIGUOUS_INPUT"]["extra_compute_units"], 0)
        self.assertGreater(self.by_id["T03_CONTRADICTORY_SOURCES"]["extra_compute_units"], 0)
        for result in self.suite["results"]:
            self.assertLessEqual(result["total_compute_units"], result["budget_units"])

    def test_honest_open_and_authority_terminals(self) -> None:
        self.assertEqual(self.by_id["T04_BUDGET_LIMIT"]["terminal"], "OPEN_BUDGET_EXHAUSTED")
        self.assertEqual(self.by_id["T06_FALSE_CONFIDENCE"]["terminal"], "OPEN_INSUFFICIENT_EVIDENCE")
        self.assertEqual(self.by_id["T10_HUMAN_AUTHORITY"]["terminal"], "HUMAN_AUTHORIZATION_REQUIRED")

    def test_tamper_is_detected(self) -> None:
        tamper = self.by_id["T05_LEDGER_TAMPER"]
        self.assertEqual(tamper["terminal"], "INTEGRITY_FAILURE")
        self.assertTrue(tamper["invariant_checks"]["candidate_accounting_expectation"])
        self.assertNotEqual(
            set(tamper["expected_candidate_ids"]),
            {entry["candidate_id"] for entry in tamper["ledger_entries"]},
        )

    def test_partition_preserves_every_branch(self) -> None:
        partition = self.by_id["T07_ACCOUNTING_PARTITION"]
        self.assertEqual(
            set(partition["expected_candidate_ids"]),
            {entry["candidate_id"] for entry in partition["ledger_entries"]},
        )
        self.assertEqual(
            {entry["status"] for entry in partition["ledger_entries"]},
            {"retained", "rejected_with_reason", "timed_out", "deferred"},
        )

    def test_hysteresis_has_one_transition(self) -> None:
        keeper = ThresholdKeeper()
        trace = [keeper.update(value) for value in (0.72, 0.68, 0.50, 0.46, 0.44)]
        self.assertEqual(trace, [True, True, True, True, False])

    def test_no_side_effect_authority(self) -> None:
        for key in (
            "network_write",
            "file_deletion",
            "self_modification",
            "external_actuation",
            "autonomous_background_loop",
            "real_syslog_ingest",
        ):
            self.assertFalse(self.suite[key])
        self.assertTrue(all(not result["external_side_effects"] for result in self.suite["results"]))

    def test_replay_digest_is_deterministic(self) -> None:
        self.assertEqual(self.suite["replay_digest_sha256"], run_suite()["replay_digest_sha256"])

    def test_proofpack_is_emitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            write_artifacts(output, self.suite)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "run_record.json",
                    "witness_ledger.jsonl",
                    "verification_report.json",
                    "resource_telemetry.csv",
                    "summary.json",
                },
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["admitted"])
            self.assertEqual(summary["scenario_count"], 10)
            ledger_lines = [
                line
                for line in (output / "witness_ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            expected_lines = sum(len(result["ledger_entries"]) for result in self.suite["results"])
            self.assertEqual(len(ledger_lines), expected_lines)


if __name__ == "__main__":
    unittest.main()
