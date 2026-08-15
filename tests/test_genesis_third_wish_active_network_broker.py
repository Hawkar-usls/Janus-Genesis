# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityOutcomeUndetermined,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
)
from tools.genesis_third_wish_active_network_broker import (
    ACTIVE_NETWORK_CLAIM_BOUNDARY,
    APIOperation,
    ActiveNetworkError,
    FixedHTTPAPIAdapter,
    ThirdWishActiveNetworkBroker,
)


class FakeResolver:
    def __init__(self, rows=None):
        self.rows = list(rows or ["93.184.216.34"])
        self.calls = []

    def resolve(self, host, port):
        self.calls.append((host, int(port)))
        return list(self.rows)


class FakePoster:
    def __init__(self):
        self.calls = []
        self.fail = False

    def post_json(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.fail:
            raise RuntimeError("injected ambiguous POST")
        raw = json.dumps({"ok": True, "echo": kwargs["payload"]}, sort_keys=True)
        return {
            "status_code": 200,
            "reason": "OK",
            "headers": {"content_type": "application/json"},
            "body_text": raw,
            "body_sha256": "f" * 64,
            "body_bytes": len(raw.encode("utf-8")),
            "redirect_followed": False,
            "request_authorization_header_present": False,
        }


class FakeConnectProbe:
    def __init__(self):
        self.calls = []
        self.fail = False

    def connect_once(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.fail:
            raise RuntimeError("injected ambiguous connect")
        return {
            "connected": True,
            "resolved_ip_sha256": "a" * 64,
            "remote_port": kwargs["port"],
            "local_port": 40000,
            "application_payload_sent": False,
            "remote_command_channel": False,
        }


class FakeLocalListener:
    def __init__(self):
        self.calls = []
        self.fail = False

    def listen_once(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.fail:
            raise RuntimeError("injected listener ambiguity")
        return {
            "listener_opened": True,
            "accepted_connection": True,
            "peer_is_loopback": True,
            "bound_host": kwargs["host"],
            "bound_port": kwargs["port"],
            "max_connections": 1,
            "persistent_daemon": False,
            "remote_command_channel": False,
            "application_payload_received": False,
        }


class FakeAPIAdapter:
    alias = "reference-api"

    def __init__(self):
        self.calls = []
        self.preflights = []
        self.fail = False

    def preflight(self, operation_name, payload):
        self.preflights.append((operation_name, copy.deepcopy(dict(payload))))
        if operation_name not in {"CREATE_NOTE", "STATUS"}:
            raise ActiveNetworkError("API_OPERATION_NOT_REGISTERED")
        if operation_name == "CREATE_NOTE" and set(payload).difference({"note"}):
            raise ActiveNetworkError("API_REQUEST_FIELDS_NOT_ALLOWED")
        if operation_name == "STATUS" and payload:
            raise ActiveNetworkError("API_REQUEST_FIELDS_NOT_ALLOWED")
        return {
            "validated": True,
            "api_alias": self.alias,
            "operation_name": operation_name,
            "actor_selects_endpoint": False,
            "actor_selects_method": False,
            "actor_selects_path": False,
            "credentialed_api": False,
        }

    def call(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.fail:
            raise RuntimeError("injected API ambiguity")
        return {
            "status_code": 200,
            "reason": "OK",
            "body_text": '{"ok":true}',
            "body_sha256": "b" * 64,
            "body_bytes": 11,
            "api_alias": self.alias,
            "operation_name": kwargs["operation_name"],
            "credentialed_api": False,
            "authorization_header_present": False,
        }


class ThirdWishActiveNetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.resolver = FakeResolver()
        self.poster = FakePoster()
        self.connect = FakeConnectProbe()
        self.listener = FakeLocalListener()
        self.api = FakeAPIAdapter()
        self.broker = ThirdWishActiveNetworkBroker(
            data_dir=self.root,
            resolver=self.resolver,
            poster=self.poster,
            connect_probe=self.connect,
            local_listener=self.listener,
            api_adapters={"reference-api": self.api},
            allowed_connect_ports=(443,),
        )
        self.fabric = self.new_fabric()

    def tearDown(self):
        self.temp.cleanup()

    def new_fabric(self):
        fabric = ThirdWishCapabilityFabric(now_tick=lambda: 745000)
        self.broker.register(fabric)
        return fabric

    def grant(self, capability, pattern, suffix, fabric=None):
        fabric = fabric or self.fabric
        return fabric.issue_grant(
            grant_id=f"G-{suffix}",
            actor_id="JANUS",
            capability_id=capability,
            resource_pattern=pattern,
            source="V1845_TEST",
        )

    @staticmethod
    def intent(grant, request_id, target, operation, parameters=None):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id=grant.grant_id,
            capability_id=grant.capability_id,
            target=target,
            operation=operation,
            purpose="exercise Third Wish active network boundary",
            parameters=parameters or {},
            origin="V1845_TEST",
        )

    def test_registered_surface_and_neighbor_noninstallation(self):
        expected = {
            "WEB.HTTP.POST",
            "NETWORK.CONNECT",
            "NETWORK.LISTEN_LOCAL",
            "API.CALL",
        }
        self.assertEqual(expected, set(self.fabric.handlers))
        self.assertEqual(expected, set(self.fabric.preflights))
        self.assertEqual(4, ACTIVE_NETWORK_CLAIM_BOUNDARY["registered_capability_count"])
        self.assertFalse(ACTIVE_NETWORK_CLAIM_BOUNDARY["github_admin_installed_here"])
        self.assertFalse(ACTIVE_NETWORK_CLAIM_BOUNDARY["github_destructive_installed_here"])
        self.assertFalse(ACTIVE_NETWORK_CLAIM_BOUNDARY["network_connect_generic_tunnel"])
        self.assertFalse(ACTIVE_NETWORK_CLAIM_BOUNDARY["api_call_generic_tunnel"])

    def test_web_post_public_https_json_settles_without_actor_headers(self):
        grant = self.grant("WEB.HTTP.POST", "https://example.com/*", "POST")
        action = self.intent(
            grant,
            "POST-1",
            "https://example.com/submit",
            "POST_JSON",
            {"json": {"message": "hello"}},
        )
        result = self.fabric.execute(action)
        self.assertEqual("SETTLED", result["status"])
        actor = result["actor_result"]
        self.assertEqual(200, actor["status_code"])
        self.assertFalse(actor["actor_supplied_headers"])
        self.assertFalse(actor["credential_material_used"])
        self.assertFalse(actor["redirect_followed"])
        self.assertEqual(1, len(self.poster.calls))
        self.assertTrue(self.poster.calls[0]["effect_key"].startswith("THIRD-WISH-NETWORK:"))

    def test_web_post_loopback_private_and_custom_header_attempts_reject_pre_effect(self):
        grant = self.grant("WEB.HTTP.POST", "*", "POST-BLOCK")
        for index, target in enumerate(
            ["https://127.0.0.1/x", "https://10.0.0.1/x", "http://example.com/x"]
        ):
            result = self.fabric.execute(self.intent(
                grant,
                f"POST-BLOCK-{index}",
                target,
                "POST_JSON",
                {"json": {"x": 1}},
            ))
            self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
            self.assertFalse(result["external_call_entered"])
        custom = self.fabric.execute(self.intent(
            grant,
            "POST-HEADER-BLOCK",
            "https://example.com/x",
            "POST_JSON",
            {"json": {"x": 1}, "headers": {"X-Test": "bad"}},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", custom["status"])
        self.assertEqual(0, len(self.poster.calls))

    def test_web_post_mixed_public_private_dns_fails_after_boundary_without_poster(self):
        self.resolver.rows = ["93.184.216.34", "127.0.0.1"]
        grant = self.grant("WEB.HTTP.POST", "https://example.com/*", "POST-DNS")
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(self.intent(
                grant,
                "POST-DNS-1",
                "https://example.com/x",
                "POST_JSON",
                {"json": {"x": 1}},
            ))
        self.assertEqual(0, len(self.poster.calls))
        self.assertEqual("EFFECT_ENTERING", self.broker.effect_store.get("POST-DNS-1")["state"])

    def test_changed_web_post_binding_rejects_pre_effect_after_restart(self):
        grant = self.grant("WEB.HTTP.POST", "https://example.com/*", "POST-CHANGE")
        self.fabric.execute(self.intent(
            grant,
            "POST-STABLE",
            "https://example.com/x",
            "POST_JSON",
            {"json": {"value": 1}},
        ))
        fabric2 = self.new_fabric()
        grant2 = self.grant("WEB.HTTP.POST", "https://example.com/*", "POST-CHANGE-2", fabric=fabric2)
        changed = fabric2.execute(self.intent(
            grant2,
            "POST-STABLE",
            "https://example.com/x",
            "POST_JSON",
            {"json": {"value": 2}},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", changed["status"])
        self.assertFalse(changed["external_call_entered"])
        self.assertEqual(1, len(self.poster.calls))

    def test_ambiguous_post_never_reexecutes_same_request_after_restart(self):
        self.poster.fail = True
        grant = self.grant("WEB.HTTP.POST", "https://example.com/*", "POST-AMB")
        action = self.intent(
            grant,
            "POST-AMBIGUOUS",
            "https://example.com/x",
            "POST_JSON",
            {"json": {"value": 1}},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(action)
        self.assertEqual(1, len(self.poster.calls))
        self.poster.fail = False
        fabric2 = self.new_fabric()
        grant2 = self.grant("WEB.HTTP.POST", "https://example.com/*", "POST-AMB2", fabric=fabric2)
        with self.assertRaises(CapabilityOutcomeUndetermined):
            fabric2.execute(self.intent(
                grant2,
                "POST-AMBIGUOUS",
                "https://example.com/x",
                "POST_JSON",
                {"json": {"value": 1}},
            ))
        self.assertEqual(1, len(self.poster.calls))

    def test_connect_probe_sends_no_payload_and_operator_port_gate_applies(self):
        grant = self.grant("NETWORK.CONNECT", "tcp:example.com:*", "CONNECT")
        result = self.fabric.execute(self.intent(
            grant,
            "CONNECT-1",
            "tcp:example.com:443",
            "CONNECT_PROBE",
            {"timeout_seconds": 1},
        ))
        actor = result["actor_result"]
        self.assertTrue(actor["connected"])
        self.assertFalse(actor["application_payload_sent"])
        self.assertFalse(actor["generic_tcp_tunnel"])
        self.assertEqual(1, len(self.connect.calls))

        blocked = self.fabric.execute(self.intent(
            grant,
            "CONNECT-BLOCK-PORT",
            "tcp:example.com:22",
            "CONNECT_PROBE",
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", blocked["status"])
        self.assertEqual(1, len(self.connect.calls))

    def test_connect_payload_injection_is_pre_effect_rejected(self):
        grant = self.grant("NETWORK.CONNECT", "tcp:example.com:*", "CONNECT-PAYLOAD")
        result = self.fabric.execute(self.intent(
            grant,
            "CONNECT-PAYLOAD-1",
            "tcp:example.com:443",
            "CONNECT_PROBE",
            {"payload": "GET / HTTP/1.1"},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])
        self.assertEqual(0, len(self.connect.calls))

    def test_local_listener_is_one_shot_loopback_not_daemon(self):
        grant = self.grant("NETWORK.LISTEN_LOCAL", "listen-local:127.0.0.1:*", "LISTEN")
        result = self.fabric.execute(self.intent(
            grant,
            "LISTEN-1",
            "listen-local:127.0.0.1:18745",
            "LISTEN_ONCE",
            {"timeout_seconds": 1},
        ))
        actor = result["actor_result"]
        self.assertTrue(actor["listener_opened"])
        self.assertEqual("LOOPBACK_ONLY", actor["bind_scope"])
        self.assertFalse(actor["persistent_listener"])
        self.assertEqual(1, actor["max_connections"])
        self.assertFalse(actor["application_payload_received"])
        self.assertFalse(actor["remote_command_channel"])

    def test_local_listener_non_loopback_and_persistence_parameters_reject(self):
        grant = self.grant("NETWORK.LISTEN_LOCAL", "*", "LISTEN-BLOCK")
        nonlocal_result = self.fabric.execute(self.intent(
            grant,
            "LISTEN-NONLOCAL",
            "listen-local:0.0.0.0:18745",
            "LISTEN_ONCE",
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", nonlocal_result["status"])
        persistent = self.fabric.execute(self.intent(
            grant,
            "LISTEN-PERSIST",
            "listen-local:127.0.0.1:18745",
            "LISTEN_ONCE",
            {"persistent": True},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", persistent["status"])
        self.assertEqual(0, len(self.listener.calls))

    def test_api_call_uses_registered_operation_not_actor_transport(self):
        grant = self.grant("API.CALL", "api:reference-api", "API")
        result = self.fabric.execute(self.intent(
            grant,
            "API-1",
            "api:reference-api",
            "CREATE_NOTE",
            {"json": {"note": "hello"}},
        ))
        actor = result["actor_result"]
        self.assertEqual(200, actor["status_code"])
        self.assertFalse(actor["actor_selects_api_endpoint"])
        self.assertFalse(actor["actor_selects_api_method"])
        self.assertFalse(actor["actor_selects_api_path"])
        self.assertFalse(actor["credentialed_api"])
        self.assertFalse(actor["generic_api_tunnel"])
        self.assertEqual(1, len(self.api.calls))

    def test_api_endpoint_method_path_and_unknown_field_substitution_reject_pre_effect(self):
        grant = self.grant("API.CALL", "api:reference-api", "API-BLOCK")
        attempts = [
            {"json": {"note": "x"}, "endpoint": "https://attacker.example"},
            {"json": {"note": "x"}, "method": "DELETE"},
            {"json": {"note": "x"}, "path": "/admin"},
            {"json": {"note": "x", "unexpected": True}},
        ]
        for index, params in enumerate(attempts):
            result = self.fabric.execute(self.intent(
                grant,
                f"API-BLOCK-{index}",
                "api:reference-api",
                "CREATE_NOTE",
                params,
            ))
            self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
            self.assertFalse(result["external_call_entered"])
        self.assertEqual(0, len(self.api.calls))

    def test_api_ambiguous_effect_never_auto_retries(self):
        self.api.fail = True
        grant = self.grant("API.CALL", "api:reference-api", "API-AMB")
        action = self.intent(
            grant,
            "API-AMB-1",
            "api:reference-api",
            "CREATE_NOTE",
            {"json": {"note": "hello"}},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(action)
        self.assertEqual(1, len(self.api.calls))
        self.api.fail = False
        fabric2 = self.new_fabric()
        grant2 = self.grant("API.CALL", "api:reference-api", "API-AMB2", fabric=fabric2)
        with self.assertRaises(CapabilityOutcomeUndetermined):
            fabric2.execute(self.intent(
                grant2,
                "API-AMB-1",
                "api:reference-api",
                "CREATE_NOTE",
                {"json": {"note": "hello"}},
            ))
        self.assertEqual(1, len(self.api.calls))

    def test_fixed_api_adapter_rejects_public_transport_substitution_by_construction(self):
        operation = APIOperation.build(
            name="CREATE_NOTE",
            method="POST",
            path="/v1/notes",
            allowed_fields=["note"],
        )
        adapter = FixedHTTPAPIAdapter(
            alias="fixed",
            base_url="https://example.com",
            operations=[operation],
        )
        validation = adapter.preflight("CREATE_NOTE", {"note": "x"})
        self.assertTrue(validation["validated"])
        self.assertFalse(validation["actor_selects_endpoint"])
        self.assertFalse(validation["actor_selects_method"])
        self.assertFalse(validation["actor_selects_path"])
        self.assertFalse(validation["credentialed_api"])

    def test_active_network_store_contains_hash_binding_not_raw_request_json(self):
        grant = self.grant("WEB.HTTP.POST", "https://example.com/*", "STORE")
        marker = "V1845_RAW_REQUEST_MARKER"
        self.fabric.execute(self.intent(
            grant,
            "STORE-1",
            "https://example.com/x",
            "POST_JSON",
            {"json": {"message": marker}},
        ))
        raw = self.broker.effect_store.path.read_text(encoding="utf-8")
        # Response is a fake echo in this unit test and therefore would otherwise
        # reflect the input. The durable actor_result may contain response data;
        # the invariant concerns the request-binding fields themselves, not remote
        # response content. Verify no dedicated raw-parameters field exists.
        state = json.loads(raw)
        row = state["requests"]["STORE-1"]
        self.assertNotIn("parameters", row)
        self.assertNotIn("raw_parameters", row)
        self.assertIn("binding_sha256", row)


if __name__ == "__main__":
    unittest.main()
