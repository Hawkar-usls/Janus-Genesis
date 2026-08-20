from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import janus_handoff_reliability_v1_gate as gate


class HandoffReliabilityGateTests(unittest.TestCase):
    def test_structural_preregistration_passes_without_live_evidence(self) -> None:
        rc, receipt = gate.evaluate("structural")
        self.assertEqual(rc, 0)
        self.assertEqual(receipt["status"], "PASS_PREREGISTRATION_ONLY")
        self.assertFalse(receipt["issue_162_runnable_contribution"])

    def test_admission_holds_without_live_binding(self) -> None:
        rc, receipt = gate.evaluate("admission")
        self.assertEqual(rc, 2)
        self.assertEqual(receipt["status"], "HOLD")
        self.assertIn("live_binding_receipt_missing", receipt["errors"])
        self.assertIn("live_gate_results_missing", receipt["errors"])

    def test_unattested_local_probe_cannot_admit(self) -> None:
        contract = json.loads(gate.CONTRACT.read_text(encoding="utf-8"))
        results = {
            "evidence_kind": "LIVE",
            "gates": {name: "PASS" for name in contract["required_gates"]},
            "failure_vectors": {name: "PASS" for name in contract["required_failure_vectors"]},
        }
        binding = {
            "evidence_kind": "LOCAL_PROBE_UNATTESTED",
            "receiver_service": "janus_nas_brain",
            "process_identity": {"pid": 1},
            "source_identity": {"sha256": "00" * 32, "git_applicable": False},
            "port_8008_owner": "janus_nas_brain",
            "network_namespace": "fixture",
            "service_owner_reconciled": True,
        }
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            bp = td / "binding.json"
            rp = td / "results.json"
            bp.write_text(json.dumps(binding), encoding="utf-8")
            rp.write_text(json.dumps(results), encoding="utf-8")
            rc, receipt = gate.evaluate("admission", binding_path=bp, gate_results_path=rp)
        self.assertEqual(rc, 2)
        self.assertEqual(receipt["status"], "HOLD")
        self.assertIn("binding_not_live_evidence", receipt["errors"])

    def test_complete_live_shaped_evidence_is_the_only_admission_shape(self) -> None:
        contract = json.loads(gate.CONTRACT.read_text(encoding="utf-8"))
        binding = {
            "evidence_kind": "LIVE",
            "receiver_service": "janus_nas_brain",
            "process_identity": {"pid": 123, "cmdline": ["python", "receiver.py"]},
            "source_identity": {
                "sha256": "11" * 32,
                "git_applicable": True,
                "repository": "fixture/repo",
                "commit": "22" * 20,
                "blob": "33" * 20,
            },
            "port_8008_owner": "janus_nas_brain",
            "network_namespace": "fixture-live-shape",
            "service_owner_reconciled": True,
        }
        results = {
            "evidence_kind": "LIVE",
            "gates": {name: "PASS" for name in contract["required_gates"]},
            "failure_vectors": {name: "PASS" for name in contract["required_failure_vectors"]},
        }
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            bp = td / "binding.json"
            rp = td / "results.json"
            bp.write_text(json.dumps(binding), encoding="utf-8")
            rp.write_text(json.dumps(results), encoding="utf-8")
            rc, receipt = gate.evaluate("admission", binding_path=bp, gate_results_path=rp)
        self.assertEqual(rc, 0)
        self.assertEqual(receipt["status"], "PASS")
        self.assertTrue(receipt["issue_162_runnable_contribution"])


if __name__ == "__main__":
    unittest.main()
