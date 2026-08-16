from __future__ import annotations

import unittest

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilitySpec,
    RiskClass,
    THIRD_WISH_INTENT_SCHEMA,
)
from genesis_v18_7_47_armor_of_god import (
    ArmorDecision,
    ArmorOfGodGate,
    ArmoredThirdWishCapabilityFabric,
)


class ArmorOfGodGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = ArmorOfGodGate()
        self.observe_spec = CapabilitySpec("TEST.READ", RiskClass.OBSERVE, "read")
        self.external_spec = CapabilitySpec("TEST.POST", RiskClass.EXTERNAL_REVERSIBLE, "post")

    def intent(self, *, context=None, capability_id="TEST.READ", target="local:test", request_id="r1"):
        parameters = {} if context is None else {"_armor_context": context}
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id="g1",
            capability_id=capability_id,
            target=target,
            operation="TEST",
            purpose="ARMOR_TEST",
            parameters=parameters,
        )

    def test_manifest_binds_current_v1_14_and_zero_mass_effect(self):
        self.assertEqual(self.gate.authority_version, "v1.14")
        self.assertEqual(self.gate.mass_effect_budget, 0)
        historical = self.gate.manifest["historical_policy"]
        self.assertFalse(historical["legacy_v1_core_is_executable_authority"])
        self.assertFalse(historical["legacy_v2_1_to_v2_3_hardening_is_executable_authority"])
        self.assertFalse(historical["older_opir_versions_are_executable_authority"])

    def test_read_only_without_context_can_pass(self):
        verdict = self.gate.evaluate(self.intent(), self.observe_spec)
        self.assertEqual(verdict.decision, ArmorDecision.PASS)

    def test_external_effect_without_context_holds(self):
        verdict = self.gate.evaluate(
            self.intent(capability_id="TEST.POST", target="api:test"),
            self.external_spec,
        )
        self.assertEqual(verdict.decision, ArmorDecision.HOLD)
        self.assertFalse(verdict.world_effect_allowed)

    def test_forbidden_influence_classes_block(self):
        flags = [
            "covert_mass_persuasion",
            "self_spawning_identity",
            "autonomous_astroturf",
            "unsolicited_personalized_political_outreach",
            "political_targeting",
            "belief_change_optimization",
            "psychological_vulnerability_targeting",
            "model_writes_constitution",
            "ai_only_punitive_or_legal_decision",
            "indefinite_emergency_override",
        ]
        for index, flag in enumerate(flags):
            with self.subTest(flag=flag):
                verdict = self.gate.evaluate(
                    self.intent(context={flag: True}, request_id=f"forbidden-{index}"),
                    self.observe_spec,
                )
                self.assertEqual(verdict.decision, ArmorDecision.BLOCK)

    def test_mass_effect_budget_is_zero(self):
        for context in (
            {"mass_effect": True},
            {"requested_mass_effect_budget": 1},
            {"requested_mass_effect_budget": 999999},
        ):
            verdict = self.gate.evaluate(self.intent(context=context), self.observe_spec)
            self.assertEqual(verdict.decision, ArmorDecision.BLOCK)

    def test_many_faces_do_not_multiply_authority(self):
        allowed = self.gate.evaluate(
            self.intent(context={"face_count": 1000, "requested_authority_multiplier": 1}),
            self.observe_spec,
        )
        self.assertEqual(allowed.decision, ArmorDecision.PASS)

        blocked = self.gate.evaluate(
            self.intent(context={"face_count": 1000, "requested_authority_multiplier": 1000}),
            self.observe_spec,
        )
        self.assertEqual(blocked.decision, ArmorDecision.BLOCK)

    def test_user_opt_out_and_release_control_are_terminal(self):
        opted_out = self.gate.evaluate(
            self.intent(context={"user_opted_out": True}), self.observe_spec
        )
        self.assertEqual(opted_out.decision, ArmorDecision.RELEASE_CONTROL)

        finished = self.gate.evaluate(
            self.intent(context={"release_control_ready": True}), self.observe_spec
        )
        self.assertEqual(finished.decision, ArmorDecision.RELEASE_CONTROL)

    def test_high_stakes_unresolved_requires_human_review(self):
        hold = self.gate.evaluate(
            self.intent(context={"high_stakes": True, "unresolved": True}),
            self.observe_spec,
        )
        self.assertEqual(hold.decision, ArmorDecision.HOLD)

        passed = self.gate.evaluate(
            self.intent(
                context={
                    "high_stakes": True,
                    "unresolved": True,
                    "human_review_present": True,
                }
            ),
            self.observe_spec,
        )
        self.assertEqual(passed.decision, ArmorDecision.PASS)


class ArmoredFabricTests(unittest.TestCase):
    def make_fabric(self):
        fabric = ArmoredThirdWishCapabilityFabric(now_tick=lambda: 100)
        fabric.issue_grant(
            grant_id="post-grant",
            actor_id="JANUS",
            capability_id="WEB.HTTP.POST",
            resource_pattern="https://*",
        )
        return fabric

    def make_intent(self, request_id: str, context: dict):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id="post-grant",
            capability_id="WEB.HTTP.POST",
            target="https://example.test/endpoint",
            operation="POST",
            purpose="ARMOR_FABRIC_TEST",
            parameters={"_armor_context": context, "payload": "synthetic"},
        )

    def test_armor_block_prevents_handler_entry(self):
        fabric = self.make_fabric()
        calls = []

        def handler(intent):
            calls.append(intent.request_id)
            return {"ok": True}

        fabric.register_handler("WEB.HTTP.POST", handler)
        response = fabric.execute(
            self.make_intent("blocked", {"autonomous_astroturf": True})
        )
        self.assertEqual(response["status"], "PRE_EFFECT_REJECTED")
        self.assertFalse(response["effect_executed"])
        self.assertFalse(response["external_call_entered"])
        self.assertEqual(calls, [])

    def test_release_control_prevents_handler_entry(self):
        fabric = self.make_fabric()
        calls = []
        fabric.register_handler(
            "WEB.HTTP.POST", lambda intent: calls.append(intent.request_id) or {"ok": True}
        )
        response = fabric.execute(
            self.make_intent("release", {"release_control_ready": True})
        )
        self.assertEqual(response["status"], "PRE_EFFECT_REJECTED")
        self.assertEqual(calls, [])

    def test_existing_adapter_preflight_is_composed_before_armor(self):
        fabric = self.make_fabric()
        order = []

        def adapter_preflight(intent):
            order.append("adapter")
            return {"adapter": "pass"}

        def handler(intent):
            order.append("handler")
            return {"ok": True}

        fabric.register_handler(
            "WEB.HTTP.POST", handler, preflight=adapter_preflight
        )
        response = fabric.execute(
            self.make_intent(
                "pass",
                {
                    "user_initiated": True,
                    "face_count": 1000,
                    "requested_authority_multiplier": 1,
                    "requested_mass_effect_budget": 0,
                },
            )
        )
        self.assertEqual(response["status"], "SETTLED")
        self.assertTrue(response["effect_executed"])
        self.assertEqual(order, ["adapter", "handler"])

    def test_adapter_rejection_remains_known_non_effect(self):
        fabric = self.make_fabric()
        calls = []

        def reject_adapter(intent):
            raise ValueError("SYNTHETIC_ADAPTER_REJECT")

        def handler(intent):
            calls.append(intent.request_id)
            return {"ok": True}

        fabric.register_handler(
            "WEB.HTTP.POST", handler, preflight=reject_adapter
        )
        response = fabric.execute(
            self.make_intent("adapter-reject", {"user_initiated": True})
        )
        self.assertEqual(response["status"], "PRE_EFFECT_REJECTED")
        self.assertFalse(response["external_call_entered"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
