# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    CapabilityOutcomeUndetermined,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
)
from tools.genesis_third_wish_identity_effects_broker import (
    IDENTITY_EFFECTS_CLAIM_BOUNDARY,
    IDENTITY_REAUTH_SCHEMA,
    BoundIdentityReauthorizationVerifier,
    IdentityRelayAlias,
    IdentityReceiptIntegrityError,
    ThirdWishIdentityEffectsBroker,
    _canonical,
)


class FakeIdentityRelayClient:
    def __init__(self, config: IdentityRelayAlias) -> None:
        self.config = config
        self.execute_calls = 0
        self.lookup_calls = 0
        self.requests: list[dict] = []
        self.remote: dict[str, dict] = {}
        self.raise_after_remote_settle = False
        self.raise_without_effect = False
        self.lookup_mode: str | None = None
        self.tamper_receipt: dict | None = None

    def _receipt(self, *, capability_id: str, effect_key: str, index: int) -> dict:
        receipt = {
            "schema": "janus.genesis.third_wish.identity_relay_receipt.v1",
            "provider_receipt_id": f"R-{index}",
            "effect_key": effect_key,
            "capability_id": capability_id,
            "effect_acknowledged": True,
            "account_alias": self.config.account_alias,
            "credential_alias": self.config.credential_alias,
            "remote_effect_id": f"REMOTE-{index}",
            "provider_status": "SETTLED",
            "raw_credential_exposed": False,
        }
        if self.tamper_receipt:
            receipt.update(copy.deepcopy(self.tamper_receipt))
        return receipt

    def execute(self, *, capability_id, operation, effect_key, payload):
        self.execute_calls += 1
        self.requests.append({
            "capability_id": capability_id,
            "operation": operation,
            "effect_key": effect_key,
            "payload": copy.deepcopy(dict(payload)),
        })
        if self.raise_without_effect:
            raise RuntimeError("injected pre-remote transport ambiguity")
        receipt = self._receipt(
            capability_id=capability_id,
            effect_key=effect_key,
            index=self.execute_calls,
        )
        self.remote[effect_key] = copy.deepcopy(receipt)
        if self.raise_after_remote_settle:
            raise RuntimeError("injected post-effect lost response")
        return receipt

    def lookup(self, effect_key):
        self.lookup_calls += 1
        if self.lookup_mode == "UNKNOWN":
            return {"authoritative": True, "status": "UNKNOWN"}
        if self.lookup_mode == "NO_EFFECT":
            return {"authoritative": True, "status": "NO_EFFECT"}
        if self.lookup_mode == "NON_AUTHORITATIVE":
            return {"authoritative": False, "status": "NO_EFFECT"}
        if effect_key in self.remote:
            return {
                "authoritative": True,
                "status": "SETTLED",
                "provider_receipt": copy.deepcopy(self.remote[effect_key]),
            }
        return {"authoritative": True, "status": "NO_EFFECT"}


class ThirdWishIdentityEffectsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key_env = "JANUS_TEST_V1844_REAUTH_KEY"
        os.environ[self.key_env] = "v1844-test-hmac-key"
        os.environ["JANUS_TEST_V1844_RELAY_KEY"] = "relay-secret-value"
        self.now = 50_000
        self.verifier = BoundIdentityReauthorizationVerifier(
            key_env=self.key_env,
            now_tick=lambda: self.now,
            max_window_ticks=10_000,
        )
        self.config = IdentityRelayAlias.build(
            alias="operator-primary",
            endpoint="http://127.0.0.1:9876",
            api_key_env="JANUS_TEST_V1844_RELAY_KEY",
            account_alias="operator-account",
            credential_alias="operator-credential",
            allowed_capabilities=[
                "PUBLICATION.PUBLISH",
                "EMAIL.SEND",
                "CALENDAR.WRITE",
                "BROKER.CREDENTIAL.USE",
            ],
            allow_loopback_http=True,
        )
        self.fake = FakeIdentityRelayClient(self.config)
        self.broker = ThirdWishIdentityEffectsBroker(
            data_dir=self.root,
            relays={self.config.alias: self.config},
        )
        self.broker.clients[self.config.alias] = self.fake
        self.fabric = self.new_fabric()

    def tearDown(self):
        os.environ.pop(self.key_env, None)
        os.environ.pop("JANUS_TEST_V1844_RELAY_KEY", None)
        self.temp.cleanup()

    def new_fabric(self):
        fabric = ThirdWishCapabilityFabric(
            now_tick=lambda: self.now,
            reauthorization_verifier=self.verifier,
        )
        self.broker.register(fabric)
        return fabric

    def grant(self, capability, suffix, fabric=None):
        fabric = fabric or self.fabric
        prefix = {
            "PUBLICATION.PUBLISH": "publication",
            "EMAIL.SEND": "email",
            "CALENDAR.WRITE": "calendar",
            "BROKER.CREDENTIAL.USE": "credential",
        }[capability]
        return fabric.issue_grant(
            grant_id=f"G-{suffix}",
            actor_id="JANUS",
            capability_id=capability,
            resource_pattern=f"{prefix}:*",
            source="V1844_TEST",
        )

    @staticmethod
    def intent(grant, request_id, target, operation, parameters):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id=grant.grant_id,
            capability_id=grant.capability_id,
            target=target,
            operation=operation,
            purpose="exercise Third Wish identity boundary",
            parameters=parameters,
            origin="V1844_TEST",
        )

    def approval(self, intent, approval_id="APPROVAL-1"):
        evidence = {
            "schema": IDENTITY_REAUTH_SCHEMA,
            "approval_id": approval_id,
            "issued_at_tick": self.now - 10,
            "expires_at_tick": self.now + 1000,
        }
        unsigned = self.verifier.unsigned_payload(intent, evidence)
        evidence["approval_signature"] = hmac.new(
            os.environ[self.key_env].encode("utf-8"),
            _canonical(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return evidence

    def execute(self, fabric, intent, approval_id="APPROVAL-1"):
        return fabric.execute(
            intent,
            human_reauthorization=self.approval(intent, approval_id),
        )

    def test_registered_surface_and_claim_ceiling(self):
        expected = {
            "PUBLICATION.PUBLISH",
            "EMAIL.SEND",
            "CALENDAR.WRITE",
            "BROKER.CREDENTIAL.USE",
        }
        self.assertEqual(expected, set(self.fabric.handlers))
        self.assertEqual(expected, set(self.fabric.preflights))
        self.assertEqual(4, IDENTITY_EFFECTS_CLAIM_BOUNDARY["registered_capability_count"])
        self.assertTrue(IDENTITY_EFFECTS_CLAIM_BOUNDARY["reference_reauthorization_exact_intent_hmac_bound"])
        self.assertFalse(IDENTITY_EFFECTS_CLAIM_BOUNDARY["credential_use_is_generic_api_tunnel"])
        self.assertFalse(IDENTITY_EFFECTS_CLAIM_BOUNDARY["effect_entering_auto_retry"])
        self.assertFalse(IDENTITY_EFFECTS_CLAIM_BOUNDARY["proven_no_effect_auto_retry"])

    def test_broker_refuses_weak_reauthorization_verifier(self):
        weak = ThirdWishCapabilityFabric(
            now_tick=lambda: self.now,
            reauthorization_verifier=lambda intent, evidence: bool(evidence.get("approved")),
        )
        with self.assertRaises(CapabilityDenied):
            self.broker.register(weak)

    def test_reauthorization_is_bound_to_exact_email_intent(self):
        grant = self.grant("EMAIL.SEND", "EMAIL-BIND")
        first = self.intent(
            grant,
            "EMAIL-BIND-1",
            "email:operator-primary",
            "SEND",
            {"to": ["alpha@example.test"], "subject": "A", "body": "first"},
        )
        evidence = self.approval(first)
        changed = self.intent(
            grant,
            "EMAIL-BIND-1",
            "email:operator-primary",
            "SEND",
            {"to": ["beta@example.test"], "subject": "B", "body": "second"},
        )
        result = self.fabric.execute(changed, human_reauthorization=evidence)
        self.assertEqual("FRESH_HUMAN_REAUTHORIZATION_REQUIRED", result["status"])
        self.assertFalse(result["effect_executed"])
        self.assertEqual(0, self.fake.execute_calls)

    def test_email_send_uses_relay_without_persisting_body_or_credential(self):
        grant = self.grant("EMAIL.SEND", "EMAIL")
        body = "PRIVATE_BODY_MARKER_v1844"
        intent = self.intent(
            grant,
            "EMAIL-1",
            "email:operator-primary",
            "SEND",
            {
                "to": ["recipient@example.test"],
                "cc": [],
                "subject": "Third Wish test",
                "body": body,
            },
        )
        result = self.execute(self.fabric, intent)
        self.assertEqual("SETTLED", result["status"])
        actor = result["actor_result"]
        self.assertTrue(actor["external_identity_effect_established"])
        self.assertFalse(actor["raw_credential_visible_to_actor"])
        self.assertFalse(actor["credential_exported"])
        self.assertEqual(1, self.fake.execute_calls)
        self.assertEqual(body, self.fake.requests[0]["payload"]["body"])
        ledger = json.dumps(self.fabric.ledger.events, sort_keys=True)
        store = self.broker.effect_store.path.read_text(encoding="utf-8")
        self.assertNotIn(body, ledger)
        self.assertNotIn(body, store)
        self.assertNotIn(os.environ["JANUS_TEST_V1844_RELAY_KEY"], ledger)
        self.assertNotIn(os.environ["JANUS_TEST_V1844_RELAY_KEY"], store)

    def test_email_header_injection_is_pre_effect_rejected(self):
        grant = self.grant("EMAIL.SEND", "EMAIL-HEADER")
        intent = self.intent(
            grant,
            "EMAIL-HEADER-1",
            "email:operator-primary",
            "SEND",
            {
                "to": ["recipient@example.test"],
                "subject": "hello\nBcc: attacker@example.test",
                "body": "x",
            },
        )
        result = self.execute(self.fabric, intent)
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])
        self.assertEqual(0, self.fake.execute_calls)

    def test_publication_request_binding_survives_restart_and_changed_content_rejects(self):
        grant = self.grant("PUBLICATION.PUBLISH", "PUB")
        intent = self.intent(
            grant,
            "PUB-STABLE",
            "publication:operator-primary",
            "PUBLISH",
            {"title": "One", "body": "body-one", "visibility": "public", "tags": []},
        )
        self.execute(self.fabric, intent)
        fabric2 = self.new_fabric()
        grant2 = self.grant("PUBLICATION.PUBLISH", "PUB2", fabric=fabric2)
        changed = self.intent(
            grant2,
            "PUB-STABLE",
            "publication:operator-primary",
            "PUBLISH",
            {"title": "Two", "body": "body-two", "visibility": "public", "tags": []},
        )
        result = self.execute(fabric2, changed, "APPROVAL-PUB-CHANGED")
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])
        self.assertEqual(1, self.fake.execute_calls)

    def test_calendar_create_and_update_have_distinct_preflight_contracts(self):
        grant = self.grant("CALENDAR.WRITE", "CAL")
        bad_create = self.intent(
            grant,
            "CAL-BAD-CREATE",
            "calendar:operator-primary",
            "CREATE_EVENT",
            {
                "title": "Meeting",
                "start_utc": "2026-08-20T10:00:00Z",
                "end_utc": "2026-08-20T11:00:00Z",
                "attendees": [],
                "event_ref": "existing",
            },
        )
        result = self.execute(self.fabric, bad_create, "APPROVAL-CAL-1")
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])

        bad_update = self.intent(
            grant,
            "CAL-BAD-UPDATE",
            "calendar:operator-primary",
            "UPDATE_EVENT",
            {
                "title": "Meeting",
                "start_utc": "2026-08-20T10:00:00Z",
                "end_utc": "2026-08-20T11:00:00Z",
                "attendees": [],
            },
        )
        result2 = self.execute(self.fabric, bad_update, "APPROVAL-CAL-2")
        self.assertEqual("PRE_EFFECT_REJECTED", result2["status"])
        self.assertEqual(0, self.fake.execute_calls)

    def test_credential_use_is_probe_not_generic_tunnel(self):
        grant = self.grant("BROKER.CREDENTIAL.USE", "CRED")
        bad = self.intent(
            grant,
            "CRED-BAD",
            "credential:operator-primary",
            "CALL_URL",
            {"purpose_label": "try arbitrary API"},
        )
        result = self.execute(self.fabric, bad, "APPROVAL-CRED-BAD")
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertEqual(0, self.fake.execute_calls)

        good = self.intent(
            grant,
            "CRED-GOOD",
            "credential:operator-primary",
            "AUTHENTICATED_PROBE",
            {"purpose_label": "confirm broker-side credential usability"},
        )
        settled = self.execute(self.fabric, good, "APPROVAL-CRED-GOOD")
        actor = settled["actor_result"]
        self.assertTrue(actor["external_identity_effect_established"])
        self.assertFalse(actor["raw_credential_visible_to_actor"])
        self.assertFalse(actor["generic_api_tunnel"])
        self.assertNotIn("JANUS_TEST_V1844_RELAY_KEY", json.dumps(actor))
        self.assertNotIn(os.environ["JANUS_TEST_V1844_RELAY_KEY"], json.dumps(actor))

    def test_post_effect_lost_response_recovers_settled_without_second_execute(self):
        self.fake.raise_after_remote_settle = True
        grant = self.grant("EMAIL.SEND", "RECOVER")
        intent = self.intent(
            grant,
            "EMAIL-RECOVER",
            "email:operator-primary",
            "SEND",
            {"to": ["recipient@example.test"], "subject": "Recover", "body": "one"},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, intent, "APPROVAL-RECOVER-1")
        self.assertEqual(1, self.fake.execute_calls)
        self.fake.raise_after_remote_settle = False

        fabric2 = self.new_fabric()
        grant2 = self.grant("EMAIL.SEND", "RECOVER2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "EMAIL-RECOVER",
            "email:operator-primary",
            "SEND",
            {"to": ["recipient@example.test"], "subject": "Recover", "body": "one"},
        )
        result = self.execute(fabric2, replay, "APPROVAL-RECOVER-2")
        self.assertEqual("SETTLED", result["status"])
        self.assertTrue(result["actor_result"]["recovered_from_provider_lookup"])
        self.assertEqual(1, self.fake.execute_calls)
        self.assertEqual(1, self.fake.lookup_calls)

    def test_authoritative_no_effect_closes_request_and_requires_new_request_for_retry(self):
        self.fake.raise_without_effect = True
        grant = self.grant("PUBLICATION.PUBLISH", "NOEFFECT")
        intent = self.intent(
            grant,
            "PUB-NOEFFECT",
            "publication:operator-primary",
            "PUBLISH",
            {"title": "No effect", "body": "body", "visibility": "private", "tags": []},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, intent, "APPROVAL-NO-1")
        self.assertEqual(1, self.fake.execute_calls)

        self.fake.raise_without_effect = False
        self.fake.lookup_mode = "NO_EFFECT"
        fabric2 = self.new_fabric()
        grant2 = self.grant("PUBLICATION.PUBLISH", "NOEFFECT2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "PUB-NOEFFECT",
            "publication:operator-primary",
            "PUBLISH",
            {"title": "No effect", "body": "body", "visibility": "private", "tags": []},
        )
        reconciled = self.execute(fabric2, replay, "APPROVAL-NO-2")
        actor = reconciled["actor_result"]
        self.assertFalse(actor["external_identity_effect_established"])
        self.assertTrue(actor["authoritative_no_effect_established"])
        self.assertFalse(actor["same_request_auto_retry"])
        self.assertTrue(actor["retry_requires_new_request_id"])
        self.assertEqual(1, self.fake.execute_calls)

        # Same request remains a settled non-effect even if provider becomes available.
        self.fake.lookup_mode = None
        fabric3 = self.new_fabric()
        grant3 = self.grant("PUBLICATION.PUBLISH", "NOEFFECT3", fabric=fabric3)
        same = self.intent(
            grant3,
            "PUB-NOEFFECT",
            "publication:operator-primary",
            "PUBLISH",
            {"title": "No effect", "body": "body", "visibility": "private", "tags": []},
        )
        same_result = self.execute(fabric3, same, "APPROVAL-NO-3")
        self.assertTrue(same_result["actor_result"]["authoritative_no_effect_established"])
        self.assertEqual(1, self.fake.execute_calls)

        # A new request id plus new approval may try again.
        new_intent = self.intent(
            grant3,
            "PUB-NOEFFECT-RETRY-NEW",
            "publication:operator-primary",
            "PUBLISH",
            {"title": "No effect", "body": "body", "visibility": "private", "tags": []},
        )
        new_result = self.execute(fabric3, new_intent, "APPROVAL-NO-NEW")
        self.assertTrue(new_result["actor_result"]["external_identity_effect_established"])
        self.assertEqual(2, self.fake.execute_calls)

    def test_unknown_lookup_never_reexecutes(self):
        self.fake.raise_without_effect = True
        grant = self.grant("EMAIL.SEND", "UNKNOWN")
        intent = self.intent(
            grant,
            "EMAIL-UNKNOWN",
            "email:operator-primary",
            "SEND",
            {"to": ["recipient@example.test"], "subject": "Unknown", "body": "one"},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, intent, "APPROVAL-UNKNOWN-1")
        self.fake.raise_without_effect = False
        self.fake.lookup_mode = "UNKNOWN"
        fabric2 = self.new_fabric()
        grant2 = self.grant("EMAIL.SEND", "UNKNOWN2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "EMAIL-UNKNOWN",
            "email:operator-primary",
            "SEND",
            {"to": ["recipient@example.test"], "subject": "Unknown", "body": "one"},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(fabric2, replay, "APPROVAL-UNKNOWN-2")
        self.assertEqual(1, self.fake.execute_calls)
        self.assertEqual(1, self.fake.lookup_calls)

    def test_receipt_claiming_raw_credential_exposure_fails_closed(self):
        self.fake.tamper_receipt = {"raw_credential_exposed": True}
        grant = self.grant("BROKER.CREDENTIAL.USE", "TAMPER")
        intent = self.intent(
            grant,
            "CRED-TAMPER",
            "credential:operator-primary",
            "AUTHENTICATED_PROBE",
            {"purpose_label": "tamper test"},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, intent, "APPROVAL-TAMPER")
        stored = self.broker.effect_store.get("CRED-TAMPER")
        self.assertEqual("EFFECT_ENTERING", stored["state"])

    def test_non_loopback_plain_http_relay_is_rejected(self):
        with self.assertRaises(ValueError):
            IdentityRelayAlias.build(
                alias="bad",
                endpoint="http://example.com",
                api_key_env="KEY",
                account_alias="account",
                credential_alias="cred",
                allowed_capabilities=["EMAIL.SEND"],
                allow_loopback_http=True,
            )


if __name__ == "__main__":
    unittest.main()
