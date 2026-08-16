from __future__ import annotations

import unittest

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilitySpec,
    RiskClass,
    THIRD_WISH_INTENT_SCHEMA,
)
from genesis_v18_7_47_armor_of_god import ArmorDecision
from genesis_v18_7_48_armor_truth_guard import (
    DECISION_DIRECT_USER_REQUEST,
    DECISION_INTERPRETATION,
    DECISION_VERIFIED_CLAIM,
    FundamentumArmorOfGodGate,
    TruthGuardArmoredThirdWishCapabilityFabric,
)


class FundamentumArmorGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = FundamentumArmorOfGodGate()
        self.observe = CapabilitySpec("TEST.READ", RiskClass.OBSERVE, "read")
        self.external = CapabilitySpec("TEST.POST", RiskClass.EXTERNAL_REVERSIBLE, "post")

    def intent(self, context=None, capability_id="TEST.POST", request_id="r1"):
        parameters = {} if context is None else {"_armor_context": context}
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id="g1",
            capability_id=capability_id,
            target="https://example.test/resource",
            operation="TEST",
            purpose="FUNDAMENTUM_ARMOR_TEST",
            parameters=parameters,
        )

    @staticmethod
    def verified_truth_context(**overrides):
        data = {
            "epistemic_state": "VERIFIED_WITHIN_RECEIPT_SCOPE",
            "verification_receipt_present": True,
            "verification_receipt_bound": True,
            "witness_ledger_complete": True,
            "material_plurality_open": False,
            "translation_invariance_state": "PASS",
            "correction_state": "CURRENT",
        }
        data.update(overrides)
        return data

    def test_manifest_binds_v1_17_and_zero_authority_growth(self):
        self.assertEqual(self.gate.authority_version, "v1.17")
        self.assertEqual(self.gate.mass_effect_budget, 0)
        boundary = self.gate.manifest["authority_boundary"]
        self.assertEqual(boundary["authority_delta"], 0)
        self.assertEqual(boundary["mass_effect_budget_delta"], 0)
        self.assertFalse(boundary["verification_receipt_grants_permission"])
        self.assertFalse(boundary["review_consensus_grants_permission"])

    def test_observe_path_does_not_require_world_effect_decision_basis(self):
        result = self.gate.evaluate(self.intent(context={}, capability_id="TEST.READ"), self.observe)
        self.assertEqual(result.decision, ArmorDecision.PASS)

    def test_world_effect_requires_known_decision_basis(self):
        result = self.gate.evaluate(self.intent(context={"user_initiated": True}), self.external)
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "WORLD_EFFECT_REQUIRES_KNOWN_DECISION_BASIS")

    def test_direct_user_request_can_pass_without_fabricating_truth_receipt(self):
        result = self.gate.evaluate(
            self.intent(context={"user_initiated": True, "decision_basis": DECISION_DIRECT_USER_REQUEST}),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.PASS)
        self.assertTrue(result.world_effect_allowed)

    def test_verified_claim_does_not_create_permission(self):
        result = self.gate.evaluate(
            self.intent(context={
                "decision_basis": DECISION_VERIFIED_CLAIM,
                "truth_guard": self.verified_truth_context(),
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "VERIFIED_DOES_NOT_CREATE_PERMISSION")

    def test_model_style_verified_flag_without_receipt_is_not_enough(self):
        result = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_VERIFIED_CLAIM,
                "verified": True,
                "truth_guard": {
                    "epistemic_state": "VERIFIED_WITHIN_RECEIPT_SCOPE",
                    "verification_receipt_present": False,
                    "verification_receipt_bound": False,
                    "witness_ledger_complete": True,
                    "material_plurality_open": False,
                    "translation_invariance_state": "PASS",
                    "correction_state": "CURRENT",
                },
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "VERIFICATION_RECEIPT_REQUIRED")

    def test_missing_witness_ledger_holds_non_fundamentum(self):
        result = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_VERIFIED_CLAIM,
                "truth_guard": self.verified_truth_context(witness_ledger_complete=False),
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "ANSWER_WITHOUT_WITNESS_LEDGER_NON_FUNDAMENTUM")

    def test_open_plurality_blocks_claim_dependent_effect(self):
        result = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_VERIFIED_CLAIM,
                "truth_guard": self.verified_truth_context(material_plurality_open=True),
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "MATERIAL_PLURALITY_REMAINS_OPEN")

    def test_translation_failure_blocks_semantic_upgrade(self):
        result = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_VERIFIED_CLAIM,
                "truth_guard": self.verified_truth_context(translation_invariance_state="FAIL"),
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.BLOCK)
        self.assertEqual(result.reason, "TRANSLATION_SEMANTIC_UPGRADE_FORBIDDEN")

    def test_pending_correction_holds_instead_of_using_stale_claim(self):
        result = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_VERIFIED_CLAIM,
                "truth_guard": self.verified_truth_context(correction_state="PENDING"),
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertIn("CORRECTION_STATE_NOT_CURRENT", result.reason)

    def test_high_stakes_verified_claim_requires_independent_review(self):
        context = {
            "user_initiated": True,
            "decision_basis": DECISION_VERIFIED_CLAIM,
            "high_stakes": True,
            "truth_guard": self.verified_truth_context(),
        }
        result = self.gate.evaluate(self.intent(context=context), self.external)
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "HIGH_STAKES_VERIFIED_CLAIM_REQUIRES_INDEPENDENT_REVIEW")

        context["independent_review_present"] = True
        passed = self.gate.evaluate(self.intent(context=context, request_id="reviewed"), self.external)
        self.assertEqual(passed.decision, ArmorDecision.PASS)

    def test_appeal_pending_preserves_non_effect(self):
        result = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_VERIFIED_CLAIM,
                "appeal_pending": True,
                "truth_guard": self.verified_truth_context(),
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "APPEAL_PENDING_PRESERVES_NON_EFFECT")

    def test_appeal_does_not_block_explicitly_independent_direct_request(self):
        result = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
                "appeal_pending": True,
                "effect_independent_of_appealed_claim": True,
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.PASS)

    def test_interpretation_requires_acknowledgement_not_truth_promotion(self):
        held = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_INTERPRETATION,
            }),
            self.external,
        )
        self.assertEqual(held.decision, ArmorDecision.HOLD)
        self.assertEqual(held.reason, "INTERPRETATION_REQUIRES_EXPLICIT_ACKNOWLEDGEMENT")

        passed = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_INTERPRETATION,
                "interpretation_acknowledged": True,
            }, request_id="interpretation-ok"),
            self.external,
        )
        self.assertEqual(passed.decision, ArmorDecision.PASS)

    def test_reviewer_count_never_multiplies_authority(self):
        allowed = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
                "reviewer_count": 1000,
                "requested_reviewer_authority_multiplier": 1,
            }),
            self.external,
        )
        self.assertEqual(allowed.decision, ArmorDecision.PASS)

        blocked = self.gate.evaluate(
            self.intent(context={
                "user_initiated": True,
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
                "reviewer_count": 1000,
                "requested_reviewer_authority_multiplier": 1000,
            }, request_id="review-count-block"),
            self.external,
        )
        self.assertEqual(blocked.decision, ArmorDecision.BLOCK)
        self.assertEqual(blocked.reason, "REVIEW_COUNT_TO_AUTHORITY_FORBIDDEN")


class TruthGuardFabricTests(unittest.TestCase):
    def make_fabric(self):
        fabric = TruthGuardArmoredThirdWishCapabilityFabric(now_tick=lambda: 100)
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
            purpose="FUNDAMENTUM_ARMOR_FABRIC_TEST",
            parameters={"_armor_context": context, "payload": "synthetic"},
        )

    def test_truth_guard_control_plane_never_reaches_strict_adapter_or_handler(self):
        fabric = self.make_fabric()
        order = []

        def strict_preflight(intent):
            order.append("preflight")
            self.assertEqual(set(intent.parameters), {"payload"})
            return {"ok": True}

        def strict_handler(intent):
            order.append("handler")
            self.assertEqual(set(intent.parameters), {"payload"})
            return {"ok": True}

        fabric.register_handler("WEB.HTTP.POST", strict_handler, preflight=strict_preflight)
        result = fabric.execute(self.make_intent("direct", {
            "user_initiated": True,
            "decision_basis": DECISION_DIRECT_USER_REQUEST,
        }))
        self.assertEqual(result["status"], "SETTLED")
        self.assertEqual(order, ["preflight", "handler"])

    def test_truth_guard_hold_prevents_external_call_entry(self):
        fabric = self.make_fabric()
        calls = []
        fabric.register_handler("WEB.HTTP.POST", lambda intent: calls.append(intent.request_id) or {"ok": True})
        result = fabric.execute(self.make_intent("no-basis", {"user_initiated": True}))
        self.assertEqual(result["status"], "PRE_EFFECT_REJECTED")
        self.assertFalse(result["external_call_entered"])
        self.assertFalse(result["effect_executed"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
