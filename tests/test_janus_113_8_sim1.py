from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from sim import janus_113_8_sim1 as producer
from sim import janus_113_8_sim1_verifier as verifier


class JanusSim1Tests(unittest.TestCase):
    def test_corpus_is_deterministic(self) -> None:
        first = producer.generate_corpus(1138001919, 100)
        second = producer.generate_corpus(1138001919, 100)
        self.assertEqual(first, second)
        self.assertEqual(producer.replay_digest(first), producer.replay_digest(second))

    def test_seed_changes_replay_digest(self) -> None:
        first = producer.generate_corpus(1138001919, 40)
        second = producer.generate_corpus(1138001920, 40)
        self.assertNotEqual(producer.replay_digest(first), producer.replay_digest(second))

    def test_every_attack_class_is_present(self) -> None:
        corpus = producer.generate_corpus(1138001919, 100)
        counts = Counter(case["attack_class"] for case in corpus)
        self.assertEqual(set(counts), set(producer.ATTACKS))
        self.assertTrue(all(count == 10 for count in counts.values()))

    def test_independent_verifier_does_not_import_producer(self) -> None:
        source = inspect.getsource(verifier)
        self.assertNotIn("from sim import janus_113_8_sim1", source)
        self.assertNotIn("import sim.janus_113_8_sim1", source)

    def test_full_corpus_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            producer.write_corpus(root / "producer", 1138001919, 100)
            report = verifier.verify_corpus(root / "producer", root / "verified")
            self.assertTrue(report["admitted"], report)
            self.assertEqual(report["terminal"], "JANUS_113.8_SIM_1_ADMITTED")
            self.assertEqual(report["case_count"], 100)
            self.assertEqual(report["failed_case_ids"], [])
            self.assertTrue(all(report["manifest_checks"].values()))
            self.assertTrue(all(report["suite_checks"].values()))

    def test_each_attack_reaches_its_independent_terminal(self) -> None:
        corpus = producer.generate_corpus(1138001919, 10)
        results = [verifier.verify_envelope(case) for case in corpus]
        self.assertTrue(all(result["matches_expected"] for result in results), results)
        expected = Counter(producer.EXPECTED_TERMINALS.values())
        actual = Counter(result["actual_terminal"] for result in results)
        self.assertEqual(actual, expected)

    def test_envelope_tamper_is_detected(self) -> None:
        envelope = producer.generate_corpus(1138001919, 1)[0]
        envelope = json.loads(json.dumps(envelope))
        envelope["payload_json"] += " "
        result = verifier.verify_envelope(envelope)
        self.assertEqual(result["actual_terminal"], "REJECT_ENVELOPE_TAMPER")

    def test_manifest_tamper_rejects_admission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            producer_dir = root / "producer"
            producer.write_corpus(producer_dir, 1138001919, 20)
            manifest_path = producer_dir / "producer_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["replay_digest_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = verifier.verify_corpus(producer_dir, root / "verified")
            self.assertFalse(report["admitted"])
            self.assertFalse(report["manifest_checks"]["replay_digest_sha256"])

    def test_proofpack_files_are_emitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            producer.write_corpus(root / "producer", 1138001919, 20)
            verifier.verify_corpus(root / "producer", root / "verified")
            expected = {
                root / "producer" / "cases.jsonl",
                root / "producer" / "producer_manifest.json",
                root / "producer" / "producer_resource_telemetry.csv",
                root / "verified" / "independent_results.jsonl",
                root / "verified" / "independent_verification_report.json",
                root / "verified" / "summary.json",
            }
            self.assertTrue(all(path.is_file() for path in expected))

    def test_safety_boundary_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = producer.write_corpus(Path(tmp), 1138001919, 10)
            self.assertEqual(
                manifest["safety_boundary"],
                {
                    "runtime_authority": "NONE",
                    "network_write": False,
                    "file_deletion": False,
                    "self_modification": False,
                    "external_actuation": False,
                    "real_syslog_ingest": False,
                },
            )

    def test_bounds_are_enforced_without_large_allocations(self) -> None:
        with self.assertRaises(ValueError):
            producer.generate_corpus(1, 0)
        with self.assertRaises(ValueError):
            producer.generate_corpus(1, producer.MAX_CASES + 1)
        payload_limit_case = producer.generate_corpus(1138001919, 10)[-1]
        self.assertGreater(payload_limit_case["payload_bytes"], verifier.MAX_PAYLOAD_BYTES)
        result = verifier.verify_envelope(payload_limit_case)
        self.assertEqual(result["actual_terminal"], "REJECT_PAYLOAD_LIMIT")


if __name__ == "__main__":
    unittest.main()
