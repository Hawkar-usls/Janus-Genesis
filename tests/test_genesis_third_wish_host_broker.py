# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityOutcomeUndetermined,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
)
from tools.genesis_third_wish_host_broker import (
    DockerPythonCapsuleRunner,
    HOST_BROKER_CLAIM_BOUNDARY,
    ThirdWishHostBroker,
)


class StaticResolver:
    def __init__(self, addresses):
        self.addresses = list(addresses)
        self.calls = []

    def resolve(self, host, port):
        self.calls.append((host, port))
        return list(self.addresses)


class FakeHTTPClient:
    def __init__(self, responses=None):
        self.responses = list(responses or [{
            "status_code": 200,
            "reason": "OK",
            "headers": {"content_type": "text/plain"},
            "body": b"hello-third-wish",
        }])
        self.calls = []

    def request_once(self, **kwargs):
        self.calls.append(dict(kwargs))
        return self.responses.pop(0)


class FakeProcessRunner:
    def __init__(self):
        self.calls = []

    def run_python(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "returncode": 0,
            "stdout": "4\n",
            "stderr": "",
            "stdout_sha256": hashlib.sha256(b"4\n").hexdigest(),
            "stderr_sha256": hashlib.sha256(b"").hexdigest(),
            "output_truncated": False,
            "sandbox": {
                "engine": "fake-test-runner",
                "network": "none",
                "host_mounts": 0,
                "host_workspace_visible": False,
            },
        }


class Completed:
    def __init__(self, returncode=0, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class ThirdWishHostBrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "hello.txt").write_text("hello", encoding="utf-8")
        self.resolver = StaticResolver(["93.184.216.34"])
        self.http = FakeHTTPClient()
        self.process = FakeProcessRunner()
        self.broker = ThirdWishHostBroker(
            workspace_root=self.root,
            resolver=self.resolver,
            https_client=self.http,
            process_runner=self.process,
        )
        self.fabric = ThirdWishCapabilityFabric(now_tick=lambda: 1_000)
        self.broker.register(self.fabric)

    def tearDown(self):
        self.temp.cleanup()

    def grant(self, capability_id, pattern, suffix):
        return self.fabric.issue_grant(
            grant_id=f"G-{suffix}",
            actor_id="JANUS",
            capability_id=capability_id,
            resource_pattern=pattern,
            source="TEST",
        )

    def intent(self, grant, request_id, target, operation, parameters=None):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id=grant.grant_id,
            capability_id=grant.capability_id,
            target=target,
            operation=operation,
            purpose="test the v18.7.41 typed broker boundary",
            parameters=parameters or {},
            origin="TEST",
        )

    def test_exact_registered_surface_and_neighbor_noninstallation(self):
        expected = {
            "WEB.HTTP.GET",
            "DNS.RESOLVE",
            "FILESYSTEM.READ",
            "FILESYSTEM.WRITE_WORKSPACE",
            "PROCESS.EXECUTE_SANDBOXED",
        }
        self.assertEqual(expected, set(self.fabric.handlers))
        self.assertEqual(expected, set(self.fabric.preflights))
        self.assertEqual(5, HOST_BROKER_CLAIM_BOUNDARY["registered_capability_count"])
        self.assertEqual(0, HOST_BROKER_CLAIM_BOUNDARY["process_host_mounts"])
        self.assertFalse(HOST_BROKER_CLAIM_BOUNDARY["raw_host_shell_exposed"])
        self.assertFalse(HOST_BROKER_CLAIM_BOUNDARY["generic_http_post_exposed"])

    def test_http_local_and_private_literals_reject_before_transport(self):
        grant = self.grant("WEB.HTTP.GET", "https://*", "WEB")
        for index, target in enumerate((
            "https://localhost/",
            "https://127.0.0.1/",
            "https://169.254.169.254/latest/meta-data/",
            "https://10.0.0.4/",
        ), 1):
            response = self.fabric.execute(self.intent(grant, f"WEB-LOCAL-{index}", target, "GET"))
            self.assertEqual("PRE_EFFECT_REJECTED", response["status"])
            self.assertFalse(response["external_call_entered"])
        self.assertEqual([], self.http.calls)
        self.assertEqual([], self.resolver.calls)

    def test_http_plaintext_nonstandard_port_userinfo_and_fragment_reject_pre_effect(self):
        grant = self.grant("WEB.HTTP.GET", "*", "WEB-SHAPE")
        targets = (
            "http://example.com/",
            "https://example.com:8443/",
            "https://user@example.com/",
            "https://example.com/#frag",
        )
        for index, target in enumerate(targets, 1):
            response = self.fabric.execute(self.intent(grant, f"WEB-SHAPE-{index}", target, "GET"))
            self.assertEqual("PRE_EFFECT_REJECTED", response["status"])
        self.assertFalse(self.http.calls)

    def test_dns_resolution_containing_private_address_is_not_exposed_or_connected(self):
        self.resolver.addresses = ["93.184.216.34", "127.0.0.1"]
        grant = self.grant("DNS.RESOLVE", "dns:*", "DNS")
        response = self.fabric.execute(self.intent(grant, "DNS-PRIVATE-MIX", "dns:example.com", "RESOLVE"))
        self.assertEqual("SETTLED", response["status"])
        self.assertFalse(response["actor_result"]["allowed"])
        self.assertEqual([], response["actor_result"]["addresses"])
        self.assertFalse(response["actor_result"]["connection_attempted"])

    def test_web_get_public_address_is_pinned_and_ip_not_exposed(self):
        grant = self.grant("WEB.HTTP.GET", "https://*", "WEB-PUBLIC")
        response = self.fabric.execute(self.intent(
            grant,
            "WEB-PUBLIC-1",
            "https://example.com/path?q=1",
            "GET",
            {"max_bytes": 4096},
        ))
        self.assertEqual("SETTLED", response["status"])
        result = response["actor_result"]
        self.assertTrue(result["allowed"])
        self.assertEqual("hello-third-wish", result["text"])
        self.assertFalse(result["resolved_ip_exposed"])
        self.assertNotIn("93.184.216.34", str(result))
        self.assertEqual(1, len(self.http.calls))
        self.assertEqual("93.184.216.34", self.http.calls[0]["resolved_ip"])

    def test_redirect_to_loopback_stops_before_second_http_call_and_becomes_undetermined(self):
        self.http.responses = [{
            "status_code": 302,
            "reason": "Found",
            "headers": {"location": "https://127.0.0.1/secret"},
            "body": b"",
        }]
        grant = self.grant("WEB.HTTP.GET", "https://*", "WEB-REDIRECT")
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(self.intent(grant, "WEB-REDIRECT-1", "https://example.com/", "GET"))
        self.assertEqual(1, len(self.http.calls))
        events = [row["event_type"] for row in self.fabric.ledger.events]
        self.assertIn("CAPABILITY_ACTION_OUTCOME_UNDETERMINED", events)

    def test_workspace_read_and_replay_are_hash_bound(self):
        grant = self.grant("FILESYSTEM.READ", "workspace:*", "FS-READ")
        intent = self.intent(grant, "FS-READ-1", "workspace:primary", "READ_TEXT", {"path": "hello.txt"})
        first = self.fabric.execute(intent)
        second = self.fabric.execute(intent)
        self.assertEqual(first, second)
        self.assertEqual("hello", first["actor_result"]["text"])
        self.assertEqual(hashlib.sha256(b"hello").hexdigest(), first["actor_result"]["sha256"])

    def test_workspace_traversal_and_sensitive_names_are_pre_effect_rejected(self):
        grant = self.grant("FILESYSTEM.READ", "workspace:*", "FS-BLOCK")
        for index, path in enumerate(("../outside.txt", ".env", "keys/private_key.pem", "credentials.json"), 1):
            response = self.fabric.execute(self.intent(
                grant,
                f"FS-BLOCK-{index}",
                "workspace:primary",
                "READ_TEXT",
                {"path": path},
            ))
            self.assertEqual("PRE_EFFECT_REJECTED", response["status"])
            self.assertFalse(response["external_call_entered"])

    def test_workspace_symlink_escape_never_returns_outside_content(self):
        outside = Path(self.temp.name).parent / "janus-third-wish-outside.txt"
        outside.write_text("outside-secret-like-data", encoding="utf-8")
        link = self.root / "escape.txt"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        grant = self.grant("FILESYSTEM.READ", "workspace:*", "FS-SYMLINK")
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(self.intent(
                grant,
                "FS-SYMLINK-1",
                "workspace:primary",
                "READ_TEXT",
                {"path": "escape.txt"},
            ))
        self.assertNotIn("outside-secret-like-data", str(self.fabric.ledger.events))
        outside.unlink(missing_ok=True)

    def test_workspace_write_is_atomic_and_existing_file_requires_compare_and_swap(self):
        grant = self.grant("FILESYSTEM.WRITE_WORKSPACE", "workspace:*", "FS-WRITE")
        created = self.fabric.execute(self.intent(
            grant,
            "FS-WRITE-1",
            "workspace:primary",
            "WRITE_TEXT",
            {"path": "new.txt", "text": "v1"},
        ))
        self.assertTrue(created["actor_result"]["created"])
        self.assertEqual("v1", (self.root / "new.txt").read_text(encoding="utf-8"))

        grant2 = self.grant("FILESYSTEM.WRITE_WORKSPACE", "workspace:*", "FS-WRITE-2")
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(self.intent(
                grant2,
                "FS-WRITE-2A",
                "workspace:primary",
                "WRITE_TEXT",
                {"path": "new.txt", "text": "v2"},
            ))
        self.assertEqual("v1", (self.root / "new.txt").read_text(encoding="utf-8"))

        grant3 = self.grant("FILESYSTEM.WRITE_WORKSPACE", "workspace:*", "FS-WRITE-3")
        expected = hashlib.sha256(b"v1").hexdigest()
        updated = self.fabric.execute(self.intent(
            grant3,
            "FS-WRITE-3A",
            "workspace:primary",
            "WRITE_TEXT",
            {"path": "new.txt", "text": "v2", "expected_sha256": expected},
        ))
        self.assertEqual(expected, updated["actor_result"]["previous_sha256"])
        self.assertEqual("v2", (self.root / "new.txt").read_text(encoding="utf-8"))

    def test_process_capability_passes_only_typed_capsule_parameters(self):
        grant = self.grant("PROCESS.EXECUTE_SANDBOXED", "sandbox:*", "PROC")
        response = self.fabric.execute(self.intent(
            grant,
            "PROC-1",
            "sandbox:python",
            "RUN_PYTHON",
            {"code": "print(2+2)", "argv": ["x"], "memory_mb": 64, "cpus": 0.25, "pids_limit": 32},
        ))
        self.assertEqual("SETTLED", response["status"])
        self.assertEqual("4\n", response["actor_result"]["stdout"])
        self.assertEqual(1, len(self.process.calls))
        self.assertNotIn("workspace_root", self.process.calls[0])

    def test_docker_runner_has_zero_host_mounts_no_network_and_no_pull(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(list(command))
            if command[1:3] == ["image", "inspect"]:
                return Completed(stdout=b"sha256:" + b"a" * 64 + b"\n")
            return Completed(stdout=b"4\n")

        runner = DockerPythonCapsuleRunner(image="python:3.11-alpine")
        with patch("tools.genesis_third_wish_host_broker.shutil.which", return_value="/usr/bin/docker"), patch(
            "tools.genesis_third_wish_host_broker.subprocess.run", side_effect=fake_run
        ):
            result = runner.run_python(
                code="print(2+2)",
                argv=[],
                timeout_seconds=5,
                memory_mb=64,
                cpus=0.25,
                pids_limit=32,
            )
        docker_run = calls[1]
        joined = " ".join(docker_run)
        self.assertIn("--network=none", joined)
        self.assertIn("--read-only", joined)
        self.assertIn("--cap-drop=ALL", joined)
        self.assertIn("--security-opt=no-new-privileges", joined)
        self.assertIn("--pull=never", joined)
        self.assertNotIn("--mount", docker_run)
        self.assertNotIn("--volume", docker_run)
        self.assertNotIn("-v", docker_run)
        self.assertEqual(0, result["sandbox"]["host_mounts"])
        self.assertFalse(result["sandbox"]["host_workspace_visible"])


if __name__ == "__main__":
    unittest.main()
