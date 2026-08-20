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

    def test_proc_root_source_path_remains_lexical_across_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            external = base / "external"
            (external / "app").mkdir(parents=True)
            (external / "app" / "brain.py").write_text("print('ok')\n", encoding="utf-8")
            proc = base / "proc" / "123"
            proc.mkdir(parents=True)
            (proc / "root").symlink_to(external, target_is_directory=True)

            found = probe._host_view_process_path(proc, "/app", "brain.py")

            self.assertEqual(found, proc / "root" / "app" / "brain.py")
            self.assertNotEqual(found, (external / "app" / "brain.py").resolve())

    def test_private_pid_namespace_binds_actual_listener_owner(self) -> None:
        owners = [{"pid": 101, "pid_namespace": "pid:[brain]", "network_namespace": "net:[1]", "listener_inodes": ["44"]}]
        containers = [
            {"name": "janus_nas_brain", "pid": 100, "pid_namespace": "pid:[brain]"},
            {"name": "janus_nas_api", "pid": 200, "pid_namespace": "pid:[api]"},
        ]
        with mock.patch.object(probe, "_read_link", return_value="pid:[host]"):
            enriched, names, exact = probe._bind_owner_processes_to_containers(owners, containers)
        self.assertTrue(exact)
        self.assertEqual(names, ["janus_nas_brain"])
        self.assertEqual(enriched[0]["container_candidates"], ["janus_nas_brain"])

    def test_host_pid_namespace_does_not_bind_unrelated_listener(self) -> None:
        containers = [{"name": "janus_nas_brain", "pid": 100, "pid_namespace": "pid:[host]"}]
        unrelated = [{"pid": 101, "pid_namespace": "pid:[host]", "network_namespace": "net:[host]", "listener_inodes": ["55"]}]
        exact_init = [{"pid": 100, "pid_namespace": "pid:[host]", "network_namespace": "net:[host]", "listener_inodes": ["55"]}]
        with mock.patch.object(probe, "_read_link", return_value="pid:[host]"):
            enriched, names, exact = probe._bind_owner_processes_to_containers(unrelated, containers)
            self.assertFalse(exact)
            self.assertEqual(names, [])
            self.assertEqual(enriched[0]["container_candidates"], [])

            enriched, names, exact = probe._bind_owner_processes_to_containers(exact_init, containers)
            self.assertTrue(exact)
            self.assertEqual(names, ["janus_nas_brain"])
            self.assertEqual(enriched[0]["container_candidates"], ["janus_nas_brain"])

    def test_source_discovery_can_move_from_generic_init_to_python_child(self) -> None:
        child_source = Path("/proc/101/root/app/receiver.py")

        def discover(pid: int):
            if pid == 100:
                return ({"pid": 100, "python_source_argument": None}, None)
            return ({"pid": 101, "python_source_argument": "receiver.py"}, child_source)

        with mock.patch.object(probe, "_container_member_pids", return_value=[100, 101]), \
             mock.patch.object(probe, "discover_source_from_pid", side_effect=discover):
            identity, source, pid = probe.discover_source_from_container_pid(100)

        self.assertEqual(pid, 101)
        self.assertEqual(source, child_source)
        self.assertEqual(identity["python_source_argument"], "receiver.py")

    def test_qnap_discovery_rejects_namespace_neighbor_as_receiver_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docker = Path(tmp) / "docker"
            docker.write_text("stub", encoding="utf-8")
            source = Path(tmp) / "brain.py"
            source.write_text("print('ok')\n", encoding="utf-8")

            def docker_query(_docker: Path, args: list[str]):
                if args[0] == "ps":
                    return 0, "janus_nas_brain\njanus_nas_api"
                name = args[1]
                pid = 101 if name == "janus_nas_brain" else 202
                return 0, json.dumps([{
                    "Id": name + "-id",
                    "State": {"Running": True, "Pid": pid},
                    "Config": {"Image": name + ":test"},
                    "NetworkSettings": {"Ports": {}},
                }])

            def listeners(_pid: int, port: int):
                return [{"family": "tcp4", "local_address_hex": "00000000", "port": port, "socket_inode": "444"}]

            def readlink(path: Path):
                text = str(path)
                if text.endswith("/ns/net"):
                    return "net:[shared]"
                if "/101/ns/pid" in text:
                    return "pid:[brain]"
                if "/202/ns/pid" in text:
                    return "pid:[api]"
                if text == "/proc/1/ns/pid":
                    return "pid:[host]"
                return None

            owner_rows = [{"pid": 202, "pid_namespace": "pid:[api]", "network_namespace": "net:[shared]", "listener_inodes": ["444"]}]

            with mock.patch.object(probe, "_docker_query", side_effect=docker_query), \
                 mock.patch.object(probe, "listeners_in_pid_namespace", side_effect=listeners), \
                 mock.patch.object(probe, "_read_link", side_effect=readlink), \
                 mock.patch.object(probe, "_listener_owner_processes", return_value=owner_rows), \
                 mock.patch.object(
                     probe,
                     "discover_source_from_container_pid",
                     return_value=({"pid": 101, "python_source_argument": "brain.py"}, source, 101),
                 ), \
                 mock.patch.object(
                     probe,
                     "lexical_git_identity_for_process_source",
                     return_value={"git_applicable": False, "repository_host_view": None, "commit": None, "ref": None},
                 ):
                result = probe.qnap_auto_discovery(docker, "janus_nas_brain", 8008)

        self.assertTrue(result["port_owner_reconciled"])
        self.assertEqual(result["port_owner_container_candidates"], ["janus_nas_api"])
        self.assertTrue(result["receiver_container_found"])
        self.assertFalse(result["receiver_source_binding"]["owns_target_port_socket"])
        self.assertEqual(result["hold_reason"], "RECEIVER_NOT_TARGET_PORT_OWNER")
        self.assertFalse(result["network_namespace_only_is_owner_evidence"])
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
        self.assertFalse(row["claim_ceiling"]["network_namespace_equality_proves_socket_owner"])
        self.assertFalse(row["claim_ceiling"]["identity_binding_proves_hr1_hr10"])
        self.assertEqual(row["authority_delta"], 0)
        self.assertTrue(row["read_only"])
        self.assertEqual(row["privacy"]["stdout_projection"], "PUBLIC_SUMMARY_ONLY")

    def test_public_summary_does_not_disclose_exact_pin_or_owner_name(self) -> None:
        receipt = {
            "evidence_kind": "LIVE",
            "receiver_service": "janus_nas_brain",
            "source_identity": {"sha256": "a" * 64, "commit": "deadbeef"},
            "port_8008_owner": "janus_nas_api",
            "service_owner_reconciled": True,
            "receiver_owns_target_port_socket": False,
            "read_only": True,
            "source_writeback_observed": False,
            "destructive_action_observed": False,
            "authority_delta": 0,
            "claim_ceiling": {"identity_binding_proves_hr1_hr10": False},
        }
        summary = probe.public_summary(receipt)
        encoded = json.dumps(summary, sort_keys=True)
        self.assertEqual(summary["port_8008_owner_state"], "PROVEN_MISMATCH")
        self.assertTrue(summary["source_sha256_observed"])
        self.assertTrue(summary["git_commit_observed"])
        self.assertNotIn("deadbeef", encoded)
        self.assertNotIn("a" * 64, encoded)
        self.assertNotIn("janus_nas_api", encoded)
        self.assertFalse(summary["private_exact_pin_disclosed"])


if __name__ == "__main__":
    unittest.main()
