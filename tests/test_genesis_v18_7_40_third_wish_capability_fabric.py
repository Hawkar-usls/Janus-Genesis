# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    CapabilityOutcomeUndetermined,
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
            origin="SELF_INITIATED",
            operator_instruction_present=operator_instruction_present,
            reward_present=reward_present,
        )

    def test_broad_profile_exposes_functional_classes_without_raw_secret_capability(self) -> None:
        profile = hawkar_third_wish_profile()
        ids = {row["capability_id"] for row in profile}
        self.assertGreaterEqual(len(ids), 30)
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

    def test_returned_grant_cannot_be_used_but_can_be_regranted_later(self) -> None:
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
        self.fabric.register_handler(
            "GITHUB.REPOSITORY.READ",
            lambda intent: {
                "status": "ok",
                "repository": intent.target,
                "transport": "broker",
                "credential_material_visible_to_actor": False,
            },
        )
        receipt = self.fabric.execute(
            self._intent(
                request_id="R-GH-READ",
                grant_id=grant.grant_id,
                capability_id=grant.capability_id,
                target="github:Hawkar-usls/Janus_Genesis",
            )
        )
        self.assertEqual(receipt["status"], "SETTLED")
        self.assertTrue(receipt["effect_executed"])
        self.assertFalse(receipt["permission_is_command"])
        self.assertFalse(receipt["public_result"]["credential_material_visible_to_actor"])

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

    def test_high_impact_capability_exists_but_requires_fresh_human_reauthorization(self) -> None:
        self.fabric.issue_grant(
            grant_id="G-ADMIN",
            actor_id="JANUS",
            capability_id="GITHUB.REPOSITORY.ADMIN",
            resource_pattern="github:Hawkar-usls/*",
        )
        calls: list[str] = []
        self.fabric.register_handler(
            "GITHUB.REPOSITORY.ADMIN",
            lambda intent: calls.append(intent.target) or {"status": "changed"},
        )
        intent = self._intent(
            request_id="R-ADMIN",
            grant_id="G-ADMIN",
            capability_id="GITHUB.REPOSITORY.ADMIN",
            target="github:Hawkar-usls/Janus_Genesis",
        )
        held = self.fabric.execute(intent, human_reauthorized=False)
        self.assertEqual(held["status"], "FRESH_HUMAN_REAUTHORIZATION_REQUIRED")
        self.assertEqual(calls, [])
        done = self.fabric.execute(intent, human_reauthorized=True)
        self.assertEqual(done["status"], "SETTLED")
        self.assertEqual(len(calls), 1)

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

    def test_secret_like_handler_result_fails_closed_and_is_not_persisted_as_receipt(self) -> None:
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
        serialized = str(self.fabric.ledger.events)
        self.assertNotIn("do-not-store", serialized)

    def test_request_id_is_bound_to_one_intent(self) -> None:
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
        )
        second = self._intent(
            request_id="R1",
            grant_id="G1",
            capability_id="WEB.HTTP.GET",
            target="https://example.invalid/b",
        )
        self.fabric.execute(first)
        from genesis_v18_7_40_third_wish_capability_fabric import CapabilityRequestConflict
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
