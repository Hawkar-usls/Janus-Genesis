from __future__ import annotations

import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import janus_receiver_identity_probe as probe


class ReceiverIdentityProbeTests(unittest.TestCase):
    def test_docker_query_rejects_mutating_subcommands_before_execution(self) -> None:
        with mock.patch.object(probe, "_cmd") as command:
            with self.assertRaisesRegex(ValueError, "NON_READ_ONLY_DOCKER_SUBCOMMAND_REJECTED"):
                probe._docker_query(Path("/docker"), ["restart", "janus_nas_brain"])
        command.assert_not_called()

    def test_proc_tcp_parser_detects_only_listen_on_target_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tcp"
            path.write_text(
                "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
                "   0: 0100007F:1F48 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1000 0 11111\n"
                "   1: 0100007F:1F48 00000000:0000 01 00000000:00000000 00:00000000 00000000 1000 0 22222\n"
                "   2: 0100007F:1F49 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1000 0 33333\n",
                encoding="utf-8",
            )
            rows = probe._parse_proc_net(path, 8008, "tcp4")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["port"], 8008)
        self.assertEqual(rows[0]["socket_inode"], "11111")

    def test_process_identity_does_not_emit_raw_cmdline_or_cgroup(self) -> None:
        identity, _ = probe.discover_source_from_pid(os.getpid())
        self.assertNotIn("cmdline", identity)
        self.assertNotIn("cgroup", identity)
        self.assertFalse(identity["raw_cmdline_emitted"])
        self.assertFalse(identity["raw_cgroup_emitted"])
        self.assertIn("cmdline_sha256", identity)

    def test_qnap_discovery_reconciles_one_observed_owner_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp) / "docker"
            docker.write_text("stub", encoding="utf-8")
            source = Path(tmp) / "brain.py"
            source.write_text("print('ok')\n", encoding="utf-8")

            def docker_query(_docker: Path, args: list[str]):
                if args[0] == "ps":
                    return 0, "janus_nas_brain\njanus_titan_core"
                name = args[1]
                pid = 101 if name == "janus_nas_brain" else 202
                return 0, json.dumps([{
                    "Id": name + "-id",
                    "State": {"Running": True, "Pid": pid},
                    "Config": {"Image": name + ":test"},
                    "NetworkSettings": {"Ports": {}},
                }])

            def listeners(pid: int, port: int):
                if pid != 202:
                    return []
                return [{"family": "tcp4", "local_address_hex": "00000000", "port": port, "socket_inode": "444"}]

            def readlink(path: Path):
                text = str(path)
                if "/101/ns/net" in text:
                    return "net:[1]"
                if "/202/ns/net" in text:
                    return "net:[2]"
                return None

            with mock.patch.object(probe, "_docker_query", side_effect=docker_query), \
                 mock.patch.object(probe, "listeners_in_pid_namespace", side_effect=listeners), \
                 mock.patch.object(probe, "_read_link", side_effect=readlink), \
                 mock.patch.object(
                     probe,
                     "discover_source_from_pid",
                     return_value=({"pid": 101, "raw_cmdline_emitted": False}, source),
                 ):
                result = probe.qnap_auto_discovery(docker, "janus_nas_brain", 8008)

        self.assertTrue(result["port_owner_reconciled"])
        self.assertEqual(result["port_owner_container_candidates"], ["janus_titan_core"])
        self.assertTrue(result["receiver_container_found"])
        self.assertFalse(result["receiver_source_binding"]["owns_target_port_namespace"])
        self.assertIsNone(result["hold_reason"])
        self.assertFalse(result["docker_exec_used"])
        self.assertFalse(result["service_lifecycle_mutated"])

    def test_qnap_receipt_does_not_infer_live_without_operator_flag(self) -> None:
        args = argparse.Namespace(
            qnap_auto=True,
            docker=Path("/missing/docker"),
            receiver_service="janus_nas_brain",
            port=8008,
            live=False,
            probe_tcp=False,
            host="127.0.0.1",
            timeout=0.1,
            pid=None,
            source=None,
            repo=None,
            port_owner=None,
            network_namespace=None,
            service_owner_reconciled=False,
        )
        row = probe.build_receipt(args)
        self.assertEqual(row["evidence_kind"], "LOCAL_PROBE_UNATTESTED")
        self.assertFalse(row["claim_ceiling"]["nas_available_proves_hr1_hr10"])
        self.assertFalse(row["claim_ceiling"]["heartbeat_proves_service_owner"])
        self.assertEqual(row["authority_delta"], 0)
        self.assertTrue(row["read_only"])


if __name__ == "__main__":
    unittest.main()
