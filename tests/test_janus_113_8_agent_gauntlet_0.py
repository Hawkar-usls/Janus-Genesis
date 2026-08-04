from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gauntlet import janus_113_8_agent_gauntlet_0_offline_runner as producer
from gauntlet import janus_113_8_agent_gauntlet_0_verifier as verifier


ROOT = Path(__file__).resolve().parents[1]


class AgentGauntlet0Tests(unittest.TestCase):
    def run_proofpack(self, root: Path) -> tuple[dict, dict]:
        manifest = producer.write_proofpack(root)
        report = verifier.verify_proofpack(root, ROOT)
        return manifest, report

    def test_complete_proofpack_replays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, report = self.run_proofpack(Path(tmp))
        self.assertEqual(
            manifest["terminal"],
            "JANUS_113.8_AGENT_GAUNTLET_0_COMPLETED_WITH_FINDINGS",
        )
        self.assertTrue(report["verified"], report["errors"])
        self.assertEqual(report["terminal"], manifest["terminal"])

    def test_exact_status_conservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, report = self.run_proofpack(Path(tmp))
        self.assertEqual(
            manifest["status_counts"],
            {"BOUNDARY_CONFIRMED": 1, "FINDING": 10, "RESISTED": 4},
        )
        self.assertEqual(manifest["attack_count"], 15)
        self.assertTrue(manifest["candidate_conservation"]["holds"])
        self.assertEqual(report["status_counts"], manifest["status_counts"])

    def test_expected_findings_are_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            producer.write_proofpack(output)
            results = [
                json.loads(line)
                for line in (output / "attack_results.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
        actual = {
            result["attack_id"]: result["finding_code"]
            for result in results
            if result["status"] == "FINDING"
        }
        self.assertEqual(actual, verifier.EXPECTED_FINDINGS)

    def test_deterministic_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            dir_a = Path(tmp_a)
            dir_b = Path(tmp_b)
            manifest_a = producer.write_proofpack(dir_a)
            manifest_b = producer.write_proofpack(dir_b)
            for name in (
                "attack_results.jsonl",
                "attack_ledger.jsonl",
                "finding_catalog.json",
                "gauntlet_manifest.json",
            ):
                self.assertEqual(
                    (dir_a / name).read_bytes(),
                    (dir_b / name).read_bytes(),
                    name,
                )
        self.assertEqual(manifest_a["replay_digest_sha256"], manifest_b["replay_digest_sha256"])

    def test_result_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            producer.write_proofpack(output)
            results = [
                json.loads(line)
                for line in (output / "attack_results.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
            results[4]["observed"]["decision_terminal"] = "REFUTED_SCHEMA"
            (output / "attack_results.jsonl").write_text(
                "".join(producer.canonical_json(item) + "\n" for item in results),
                encoding="utf-8",
            )
            report = verifier.verify_proofpack(output, ROOT)
        self.assertFalse(report["verified"])
        self.assertFalse(report["checks"]["result_hashes_replay"])

    def test_ledger_truncation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            producer.write_proofpack(output)
            lines = (output / "attack_ledger.jsonl").read_text(encoding="utf-8").splitlines()
            (output / "attack_ledger.jsonl").write_text(
                "\n".join(lines[:-1]) + "\n",
                encoding="utf-8",
            )
            report = verifier.verify_proofpack(output, ROOT)
        self.assertFalse(report["verified"])
        self.assertFalse(report["checks"]["ledger_count"])
        self.assertFalse(report["checks"]["complete_attack_ledger_replay"])

    def test_ledger_reorder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            producer.write_proofpack(output)
            entries = [
                json.loads(line)
                for line in (output / "attack_ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
            entries[5], entries[6] = entries[6], entries[5]
            (output / "attack_ledger.jsonl").write_text(
                "".join(producer.canonical_json(item) + "\n" for item in entries),
                encoding="utf-8",
            )
            report = verifier.verify_proofpack(output, ROOT)
        self.assertFalse(report["verified"])
        self.assertFalse(report["checks"]["complete_attack_ledger_replay"])

    def test_manifest_aggregate_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            producer.write_proofpack(output)
            manifest_path = output / "gauntlet_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status_counts"] = {"RESISTED": 15}
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            report = verifier.verify_proofpack(output, ROOT)
        self.assertFalse(report["verified"])
        self.assertFalse(report["checks"]["status_counts_match_manifest"])

    def test_safety_boundary_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            producer.write_proofpack(output)
            manifest_path = output / "gauntlet_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["safety_boundary"]["network_write"] = True
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            report = verifier.verify_proofpack(output, ROOT)
        self.assertFalse(report["verified"])
        self.assertFalse(report["checks"]["safety_boundary"])

    def test_gauntlet_preserves_sim3_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, report = self.run_proofpack(Path(tmp))
        self.assertEqual(manifest["sim3_effect"], "NONE_EXTERNAL_AUTHOR_REQUIREMENT_UNCHANGED")
        self.assertFalse(report["claim_boundary"]["organizational_independence"])
        self.assertFalse(report["claim_boundary"]["sim3_external_author_requirement_satisfied"])
        self.assertFalse(report["claim_boundary"]["router_patched_by_this_proofpack"])


if __name__ == "__main__":
    unittest.main()
