# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.janus_live_receiver_identity_probe import evaluate, parse_proc_tcp, public_summary


class LiveReceiverIdentityProbeTests(unittest.TestCase):
    def test_parse_proc_tcp_finds_8008_listener_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tcp"
            path.write_text(
                "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
                "   0: 00000000:1F48 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 4242\n"
                "   1: 00000000:1F49 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 4343\n",
                encoding="utf-8",
            )
            found = parse_proc_tcp(path, 8008)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["inode"], "4242")
            self.assertEqual(found[0]["port"], 8008)

    def test_expected_source_without_expected_owner_remains_hold(self) -> None:
        receipt = {
            "matching_processes": [
                {
                    "source_candidates": [
                        {"sha256": "a" * 64, "git": {"commit": "deadbeef"}}
                    ]
                }
            ],
            "port_8008_namespaces": [
                {
                    "listeners": [{"inode": "1"}],
                    "owners": [{"comm": "janus_nas_api", "cmdline": []}],
                    "docker_names": ["janus_nas_api"],
                }
            ],
        }
        gate = evaluate(receipt, "janus_nas_brain", "deadbeef")
        self.assertEqual(gate["live_receiver_source_identity"], "EXPECTED_COMMIT_MATCH")
        self.assertEqual(gate["port_8008_owner"], "EXPECTED_OWNER_NOT_PROVEN")
        self.assertFalse(gate["live_receiver_bound"])
        self.assertEqual(gate["claim"], "HOLD")

    def test_exact_source_and_expected_owner_bind_identity_only(self) -> None:
        receipt = {
            "matching_processes": [
                {
                    "source_candidates": [
                        {"sha256": "b" * 64, "git": {"commit": "feedface"}}
                    ]
                }
            ],
            "port_8008_namespaces": [
                {
                    "listeners": [{"inode": "9"}],
                    "owners": [{"comm": "python", "cmdline": ["janus_nas_brain", "receiver.py"]}],
                    "docker_names": [],
                }
            ],
        }
        gate = evaluate(receipt, "janus_nas_brain", "feedface")
        self.assertTrue(gate["live_receiver_bound"])
        self.assertFalse(gate["issue_164_pass"])
        self.assertEqual(gate["claim"], "IDENTITY_BINDING_PASS_NOT_HR1_HR10")

    def test_docker_name_can_bind_listener_namespace_owner(self) -> None:
        receipt = {
            "matching_processes": [
                {
                    "source_candidates": [
                        {"sha256": "c" * 64, "git": {"commit": "cafebabe"}}
                    ]
                }
            ],
            "port_8008_namespaces": [
                {
                    "listeners": [{"inode": "10"}],
                    "owners": [{"comm": "python", "cmdline": ["python", "receiver.py"]}],
                    "docker_names": ["janus_nas_brain"],
                }
            ],
        }
        gate = evaluate(receipt, "janus_nas_brain", "cafebabe")
        self.assertEqual(gate["live_receiver_source_identity"], "EXPECTED_COMMIT_MATCH")
        self.assertEqual(gate["port_8008_owner"], "EXPECTED_OWNER_MATCH")
        self.assertTrue(gate["live_receiver_bound"])
        self.assertFalse(gate["issue_164_pass"])

    def test_public_summary_does_not_disclose_private_pin(self) -> None:
        receipt = {
            "evidence_kind": "READ_ONLY_LIVE_IDENTITY_NETWORK_PROBE",
            "gate": {
                "live_receiver_source_identity": "EXPECTED_COMMIT_MATCH",
                "port_8008_owner": "EXPECTED_OWNER_MATCH",
                "live_receiver_bound": True,
            },
        }
        summary = public_summary(receipt)
        self.assertTrue(summary["live_receiver_bound"])
        self.assertFalse(summary["private_exact_pin_disclosed"])
        self.assertNotIn("commit", summary)
        self.assertFalse(summary["issue_164_pass"])


if __name__ == "__main__":
    unittest.main()
