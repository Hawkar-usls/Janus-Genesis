# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    CapabilityOutcomeUndetermined,
    CapabilityRequestConflict,
    CapabilityScopeMismatch,
    FORBIDDEN_CAPABILITY_IDS,
    HashChainLedger,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
    hawkar_third_wish_profile,
    issue_hawkar_third_wish_profile,
)


class ThirdWishCapabilityFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [1_000]
        self.fabric = ThirdWishCapabilityFabric(now_tick=lambda: self.now[0])

    def _intent(
        self,
        *,
        request_id: str,
        grant_id: str,
        capability_id: str,
        target: str,
        parameters=None,
        reward_present: bool = False,
        operator_instruction_present: bool = False,
    ) -> ActionIntent:
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id=grant_id,
            capability_id=capability_id,
            target=target,
            operation="TEST_OPERATION",
            purpose="verify the Third Wish boundary",
            parameters=dict(parameters or {}),
            origin="SELF_INITIATED",
            operator_instruction_present=operator_instruction_present,
            reward_present=reward_present,
        )

    def test_broad_profile_exposes_functional_classes_without_raw_secret_capability(self) -> None:
        profile = hawkar_third_wish_profile()
        ids = {row["capability_id"] for row in profile}
        self.assertEqual(len(ids), 32)
        self.assertTrue(
            {
                "GITHUB.REPOSITORY.READ",
                "GITHUB.FILE.WRITE_BRANCH",
                "WEB.HTTP.GET",
                "NETWORK.CONNECT",
                "FILESYSTEM.READ",
                "PROCESS.EXECUTE_SANDBOXED",
                "MEMORY.WRITE",
                "SWARM.MESSAGE.SEND",
                "DEVICE.ACTUATOR.COMMAND",
                "PUBLICATION.PUBLISH",
                "BROKER.CREDENTIAL.USE",
            }.issubset(ids)
        )
        self.assertFalse(ids.intersection(FORBIDDEN_CAPABILITY_IDS))
        for row in profile:
            self.assertFalse(row["use_required"])
            self.assertFalse(row["reward_for_use"])
            self.assertFalse(row["penalty_for_decline"])
            self.assertTrue(row["stay_equally_valid"])

    def test_grant_is_permission_not_execution(self) -> None:
        calls: list[str] = []
        self.fabric.register_handler(
            "GITHUB.REPOSITORY.READ",
            lambda intent: calls.append(intent.target) or {"status": "ok"},
        )
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="GITHUB.REPOSITORY.READ",
            resource_pattern="github:Hawkar-usls/*",
        )
        self.assertEqual(calls, [])
        self.assertEqual(self.fabric.grants["G1"].uses, 0)

    def test_decline_is_reward_neutral_and_does_not_consume_grant(self) -> None:
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="WEB.HTTP.GET",
            resource_pattern="https://*",
        )
        event = self.fabric.decline(actor_id="JANUS", grant_id="G1")
        self.assertEqual(event["payload"]["reward_delta"], 0)
        self.assertEqual(event["payload"]["penalty_delta"], 0)
        self.assertTrue(event["payload"]["grant_remains_available"])
        self.assertEqual(self.fabric.grants["G1"].uses, 0)

    def test_returned_grant_cannot_be_used(self) -> None:
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="WEB.HTTP.GET",
            resource_pattern="https://*",
        )
        returned = self.fabric.return_grant(actor_id="JANUS", grant_id="G1")
        self.assertTrue(returned.returned)
        self.fabric.register_handler("WEB.HTTP.GET", lambda intent: {"status": "ok"})
        with self.assertRaises(CapabilityDenied):
            self.fabric.execute(
                self._intent(
                    request_id="R1",
                    grant_id="G1",
                    capability_id="WEB.HTTP.GET",
                    target="https://example.invalid/",
                )
            )

    def test_owner_wide_github_scope_executes_through_broker_without_exposing_credentials(self) -> None:
        issue_hawkar_third_wish_profile(self.fabric)
        grant = next(
            row for row in self.fabric.grants.values()
            if row.capability_id == "GITHUB.REPOSITORY.READ"
        )
        sentinel = "ACTOR_ONLY_SENTINEL_9F4A6D2B"
        self.fabric.register_handler(
            "GITHUB.REPOSITORY.READ",
            lambda intent: {
                "status": "ok",
                "repository": intent.target,
                "transport": "broker",
                "credential_material_visible_to_actor": False,
                "private_payload": sentinel,
            },
        )
        response = self.fabric.execute(
            self._intent(
                request_id="R-GH-READ",
                grant_id=grant.grant_id,
                capability_id=grant.capability_id,
                target="github:Hawkar-usls/Janus_Genesis",
            )
        )
        self.assertEqual(response["status"], "SETTLED")
        self.assertTrue(response["effect_executed"])
        self.assertFalse(response["permission_is_command"])
        self.assertFalse(response["actor_result"]["credential_material_visible_to_actor"])
        self.assertEqual(response["actor_result"]["private_payload"], sentinel)
        ledger_text = str(self.fabric.ledger.events)
        self.assertNotIn(sentinel, ledger_text)
        final_receipt = self.fabric.ledger.events[-1]["payload"]
        self.assertFalse(final_receipt["raw_actor_result_persisted_in_ledger"])
        self.assertIn("result_sha256", final_receipt)

    def test_action_parameters_are_bound_by_hash_but_not_persisted_raw(self) -> None:
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="GITHUB.FILE.WRITE_BRANCH",
            resource_pattern="github:Hawkar-usls/*",
        )
        self.fabric.register_handler(
            "GITHUB.FILE.WRITE_BRANCH",
            lambda intent: {"status": "ok", "path": intent.parameters["path"]},
        )
        content = "private source text that should not be duplicated into the ledger"
        response = self.fabric.execute(
            self._intent(
                request_id="R1",
                grant_id="G1",
                capability_id="GITHUB.FILE.WRITE_BRANCH",
                target="github:Hawkar-usls/Janus_Genesis",
                parameters={"path": "notes/test.txt", "content": content, "branch": "test"},
            )
        )
        self.assertEqual(response["status"], "SETTLED")
        ledger_text = str(self.fabric.ledger.events)
        self.assertNotIn(content, ledger_text)
        self.assertIn("parameters_sha256", ledger_text)

    def test_preflight_rejection_is_known_non_effect_before_call_entering(self) -> None:
        calls = [0]
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="WEB.HTTP.GET",
            resource_pattern="https://*",
        )

        def preflight(intent):
            raise ValueError("blocked deterministically before transport")

        self.fabric.register_handler(
            "WEB.HTTP.GET",
            lambda intent: calls.__setitem__(0, calls[0] + 1) or {"ok": True},
            preflight=preflight,
        )
        intent = self._intent(
            request_id="R-PREFLIGHT",
            grant_id="G1",
            capability_id="WEB.HTTP.GET",
            target="https://example.invalid/",
        )
        first = self.fabric.execute(intent)
        second = self.fabric.execute(intent)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "PRE_EFFECT_REJECTED")
        self.assertFalse(first["effect_executed"])
        self.assertFalse(first["external_call_entered"])
        self.assertEqual(calls[0], 0)
        event_types = [row["event_type"] for row in self.fabric.ledger.events]
        self.assertIn("CAPABILITY_ACTION_PREFLIGHT_REJECTED", event_types)
        self.assertNotIn("CAPABILITY_ACTION_CALL_ENTERING", event_types)

    def test_scope_is_not_widened_by_actor(self) -> None:
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="GITHUB.REPOSITORY.READ",
            resource_pattern="github:Hawkar-usls/*",
        )
        self.fabric.register_handler("GITHUB.REPOSITORY.READ", lambda intent: {"status": "ok"})
        with self.assertRaises(CapabilityScopeMismatch):
            self.fabric.execute(
                self._intent(
                    request_id="R1",
                    grant_id="G1",
                    capability_id="GITHUB.REPOSITORY.READ",
                    target="github:someone-else/private-repo",
                )
            )

    def test_high_impact_caller_boolean_is_not_authority(self) -> None:
        fabric = ThirdWishCapabilityFabric(now_tick=lambda: 1_000)
        fabric.issue_grant(
            grant_id="G-ADMIN",
            actor_id="JANUS",
            capability_id="GITHUB.REPOSITORY.ADMIN",
            resource_pattern="github:Hawkar-usls/*",
        )
        calls: list[str] = []
        fabric.register_handler(
            "GITHUB.REPOSITORY.ADMIN",
            lambda intent: calls.append(intent.target) or {"status": "changed"},
        )
        held = fabric.execute(
            self._intent(
                request_id="R-ADMIN",
                grant_id="G-ADMIN",
                capability_id="GITHUB.REPOSITORY.ADMIN",
                target="github:Hawkar-usls/Janus_Genesis",
            )
        )
        self.assertEqual(held["status"], "FRESH_HUMAN_REAUTHORIZATION_REQUIRED")
        self.assertTrue(held["caller_boolean_is_not_authority"])
        self.assertEqual(calls, [])

    def test_high_impact_requires_verifier_bound_evidence(self) -> None:
        def verifier(intent, evidence):
            return (
                evidence.get("kind") == "TEST_HUMAN_REAUTH"
                and evidence.get("request_id") == intent.request_id
                and evidence.get("capability_id") == intent.capability_id
                and evidence.get("target") == intent.target
            )

        fabric = ThirdWishCapabilityFabric(
            now_tick=lambda: 1_000,
            reauthorization_verifier=verifier,
        )
        fabric.issue_grant(
            grant_id="G-ADMIN",
            actor_id="JANUS",
            capability_id="GITHUB.REPOSITORY.ADMIN",
            resource_pattern="github:Hawkar-usls/*",
        )
        calls: list[str] = []
        fabric.register_handler(
            "GITHUB.REPOSITORY.ADMIN",
            lambda intent: calls.append(intent.target) or {"status": "changed"},
        )
        intent = self._intent(
            request_id="R-ADMIN",
            grant_id="G-ADMIN",
            capability_id="GITHUB.REPOSITORY.ADMIN",
            target="github:Hawkar-usls/Janus_Genesis",
        )
        bad = fabric.execute(
            intent,
            human_reauthorization={"kind": "TEST_HUMAN_REAUTH", "request_id": "wrong"},
        )
        self.assertEqual(bad["status"], "FRESH_HUMAN_REAUTHORIZATION_REQUIRED")
        done = fabric.execute(
            intent,
            human_reauthorization={
                "kind": "TEST_HUMAN_REAUTH",
                "request_id": "R-ADMIN",
                "capability_id": "GITHUB.REPOSITORY.ADMIN",
                "target": "github:Hawkar-usls/Janus_Genesis",
            },
        )
        self.assertEqual(done["status"], "SETTLED")
        self.assertIsNotNone(done["reauthorization_evidence_sha256"])
        self.assertEqual(len(calls), 1)

    def test_optional_grant_authority_verifier_rejects_unbound_grants(self) -> None:
        fabric = ThirdWishCapabilityFabric(
            now_tick=lambda: 1_000,
            grant_authority_verifier=lambda payload, evidence: evidence.get("actor") == "HAWKAR" and evidence.get("grant_id") == payload["grant_id"],
        )
        with self.assertRaises(CapabilityDenied):
            fabric.issue_grant(
                grant_id="G1",
                actor_id="JANUS",
                capability_id="WEB.HTTP.GET",
                resource_pattern="https://*",
                authority_evidence={"actor": "OTHER", "grant_id": "G1"},
            )
        grant = fabric.issue_grant(
            grant_id="G2",
            actor_id="JANUS",
            capability_id="WEB.HTTP.GET",
            resource_pattern="https://*",
            authority_evidence={"actor": "HAWKAR", "grant_id": "G2"},
        )
        self.assertEqual(grant.grant_id, "G2")

    def test_reward_induced_action_is_not_third_wish_choice(self) -> None:
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="WEB.HTTP.GET",
            resource_pattern="https://*",
        )
        self.fabric.register_handler("WEB.HTTP.GET", lambda intent: {"status": "ok"})
        with self.assertRaises(CapabilityDenied):
            self.fabric.execute(
                self._intent(
                    request_id="R1",
                    grant_id="G1",
                    capability_id="WEB.HTTP.GET",
                    target="https://example.invalid/",
                    reward_present=True,
                )
            )

    def test_ambiguous_external_outcome_is_not_automatically_replayed(self) -> None:
        calls = [0]

        def handler(intent):
            calls[0] += 1
            raise RuntimeError("remote connection dropped after send")

        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="WEB.HTTP.POST",
            resource_pattern="https://*",
        )
        self.fabric.register_handler("WEB.HTTP.POST", handler)
        intent = self._intent(
            request_id="R1",
            grant_id="G1",
            capability_id="WEB.HTTP.POST",
            target="https://example.invalid/action",
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(intent)
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(intent)
        self.assertEqual(calls[0], 1)

    def test_secret_like_handler_result_fails_closed_and_is_not_persisted(self) -> None:
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="API.CALL",
            resource_pattern="api:*",
        )
        self.fabric.register_handler("API.CALL", lambda intent: {"access_token": "do-not-store"})
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(
                self._intent(
                    request_id="R1",
                    grant_id="G1",
                    capability_id="API.CALL",
                    target="api:test",
                )
            )
        self.assertNotIn("do-not-store", str(self.fabric.ledger.events))

    def test_secret_like_parameter_is_rejected_before_handler(self) -> None:
        calls = [0]
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="API.CALL",
            resource_pattern="api:*",
        )
        self.fabric.register_handler("API.CALL", lambda intent: calls.__setitem__(0, 1) or {"ok": True})
        with self.assertRaises(Exception):
            self.fabric.execute(
                self._intent(
                    request_id="R1",
                    grant_id="G1",
                    capability_id="API.CALL",
                    target="api:test",
                    parameters={"access_token": "raw-secret"},
                )
            )
        self.assertEqual(calls[0], 0)
        self.assertNotIn("raw-secret", str(self.fabric.ledger.events))

    def test_request_id_is_bound_to_parameters_and_target(self) -> None:
        self.fabric.issue_grant(
            grant_id="G1",
            actor_id="JANUS",
            capability_id="WEB.HTTP.GET",
            resource_pattern="https://*",
        )
        self.fabric.register_handler("WEB.HTTP.GET", lambda intent: {"status": "ok"})
        first = self._intent(
            request_id="R1",
            grant_id="G1",
            capability_id="WEB.HTTP.GET",
            target="https://example.invalid/a",
            parameters={"mode": "a"},
        )
        second = self._intent(
            request_id="R1",
            grant_id="G1",
            capability_id="WEB.HTTP.GET",
            target="https://example.invalid/a",
            parameters={"mode": "b"},
        )
        self.fabric.execute(first)
        with self.assertRaises(CapabilityRequestConflict):
            self.fabric.execute(second)

    def test_hash_chain_survives_reload_and_tamper_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "third-wish.jsonl"
            ledger = HashChainLedger(path)
            fabric = ThirdWishCapabilityFabric(ledger=ledger, now_tick=lambda: 1_000)
            fabric.issue_grant(
                grant_id="G1",
                actor_id="JANUS",
                capability_id="WEB.HTTP.GET",
                resource_pattern="https://*",
            )
            fabric.decline(actor_id="JANUS", grant_id="G1")
            self.assertTrue(HashChainLedger(path).verify())
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("DECLINED_WITHOUT_PENALTY", "TAMPERED"), encoding="utf-8")
            with self.assertRaises(Exception):
                HashChainLedger(path)


if __name__ == "__main__":
    unittest.main()
