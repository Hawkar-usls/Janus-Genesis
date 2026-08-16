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
)
from genesis_v18_7_49_armor_mechanics_hardening import (
    HardenedFundamentumArmorOfGodGate,
    HardenedTruthGuardArmoredThirdWishCapabilityFabric,
)


class ArmorMechanicsHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = HardenedFundamentumArmorOfGodGate()
        self.external = CapabilitySpec("TEST.POST", RiskClass.EXTERNAL_REVERSIBLE, "post")

    def intent(self, context, request_id="r1"):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id="g1",
            capability_id="TEST.POST",
            target="https://example.test/resource",
            operation="TEST",
            purpose="ARMOR_V49_TEST",
            parameters={"_armor_context": context},
        )

    @staticmethod
    def truth(**overrides):
        value = {
            "epistemic_state": "VERIFIED_WITHIN_RECEIPT_SCOPE",
            "verification_receipt_present": True,
            "verification_receipt_bound": True,
            "witness_ledger_complete": True,
            "material_plurality_open": False,
            "translation_invariance_state": "PASS",
            "correction_state": "CURRENT",
        }
        value.update(overrides)
        return value

    @staticmethod
    def high_stakes_review(**overrides):
        value = {
            "high_stakes": True,
            "independent_review_present": True,
            "independent_review_package_bound": True,
            "independent_review_package_digest_sha256": "a" * 64,
            "independent_review_effective_root_count": 2,
            "independent_review_status": "CONSENSUS_UPHOLD",
        }
        value.update(overrides)
        return value

    def test_string_false_cannot_become_user_permission(self):
        result = self.gate.evaluate(
            self.intent({
                "user_initiated": "false",
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertIn("CONTROL_FIELD_TYPE_INVALID:user_initiated", result.reason)
        self.assertFalse(result.world_effect_allowed)

    def test_string_false_cannot_bypass_pending_appeal(self):
        result = self.gate.evaluate(
            self.intent({
                "user_initiated": True,
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
                "appeal_pending": True,
                "effect_independent_of_appealed_claim": "false",
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertIn("CONTROL_FIELD_TYPE_INVALID:effect_independent_of_appealed_claim", result.reason)

    def test_malformed_reviewer_multiplier_blocks_instead_of_crashing(self):
        for value in ("1", "nan", True, None):
            with self.subTest(value=value):
                result = self.gate.evaluate(
                    self.intent({
                        "user_initiated": True,
                        "decision_basis": DECISION_DIRECT_USER_REQUEST,
                        "requested_reviewer_authority_multiplier": value,
                    }),
                    self.external,
                )
                self.assertEqual(result.decision, ArmorDecision.BLOCK)
                self.assertFalse(result.world_effect_allowed)

    def test_material_plurality_requires_explicit_false(self):
        for value in (None, "false", 0, True):
            with self.subTest(value=value):
                truth = self.truth()
                if value is None:
                    truth.pop("material_plurality_open")
                else:
                    truth["material_plurality_open"] = value
                result = self.gate.evaluate(
                    self.intent({
                        "user_initiated": True,
                        "decision_basis": DECISION_VERIFIED_CLAIM,
                        "truth_guard": truth,
                    }),
                    self.external,
                )
                self.assertEqual(result.decision, ArmorDecision.HOLD)
                self.assertFalse(result.world_effect_allowed)

    def test_fresh_authorization_requires_binding_when_not_user_initiated(self):
        result = self.gate.evaluate(
            self.intent({
                "user_initiated": False,
                "fresh_human_authorization_present": True,
                "fresh_human_authorization_bound": False,
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "FRESH_HUMAN_AUTHORIZATION_MUST_BE_BOUND")

    def test_bound_fresh_authorization_requires_identifier(self):
        result = self.gate.evaluate(
            self.intent({
                "user_initiated": False,
                "fresh_human_authorization_present": True,
                "fresh_human_authorization_bound": True,
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "FRESH_HUMAN_AUTHORIZATION_ID_REQUIRED")

    def test_valid_bound_fresh_authorization_can_reach_parent_gate(self):
        result = self.gate.evaluate(
            self.intent({
                "user_initiated": False,
                "fresh_human_authorization_present": True,
                "fresh_human_authorization_bound": True,
                "fresh_human_authorization_id": "AUTH-001",
                "decision_basis": DECISION_DIRECT_USER_REQUEST,
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.PASS)
        self.assertTrue(result.world_effect_allowed)

    def test_high_stakes_review_needs_exact_package_binding(self):
        context = {
            "user_initiated": True,
            "decision_basis": DECISION_VERIFIED_CLAIM,
            "truth_guard": self.truth(),
            **self.high_stakes_review(independent_review_package_bound=False),
        }
        result = self.gate.evaluate(self.intent(context), self.external)
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertEqual(result.reason, "HIGH_STAKES_REVIEW_REQUIRES_EXACT_PACKAGE_BINDING")

    def test_high_stakes_review_needs_digest_and_two_effective_roots(self):
        bad_digest = {
            "user_initiated": True,
            "decision_basis": DECISION_VERIFIED_CLAIM,
            "truth_guard": self.truth(),
            **self.high_stakes_review(independent_review_package_digest_sha256="not-a-digest"),
        }
        result = self.gate.evaluate(self.intent(bad_digest), self.external)
        self.assertEqual(result.reason, "HIGH_STAKES_REVIEW_PACKAGE_DIGEST_INVALID")

        one_root = {
            "user_initiated": True,
            "decision_basis": DECISION_VERIFIED_CLAIM,
            "truth_guard": self.truth(),
            **self.high_stakes_review(independent_review_effective_root_count=1),
        }
        result = self.gate.evaluate(self.intent(one_root, request_id="one-root"), self.external)
        self.assertEqual(result.reason, "HIGH_STAKES_REVIEW_REQUIRES_TWO_EFFECTIVE_ROOTS")

    def test_high_stakes_correction_or_disagreement_cannot_authorize_old_claim_effect(self):
        for status in ("CONSENSUS_CORRECTION_SUPPORTED", "DISAGREEMENT", "OPEN_INSUFFICIENT_REVIEW"):
            with self.subTest(status=status):
                context = {
                    "user_initiated": True,
                    "decision_basis": DECISION_VERIFIED_CLAIM,
                    "truth_guard": self.truth(),
                    **self.high_stakes_review(independent_review_status=status),
                }
                result = self.gate.evaluate(self.intent(context, request_id=status), self.external)
                self.assertEqual(result.decision, ArmorDecision.HOLD)
                self.assertIn("HIGH_STAKES_REVIEW_NOT_UPHOLDING", result.reason)

    def test_valid_high_stakes_review_can_pass_but_does_not_create_permission(self):
        no_permission = {
            "user_initiated": False,
            "fresh_human_authorization_present": False,
            "decision_basis": DECISION_VERIFIED_CLAIM,
            "truth_guard": self.truth(),
            **self.high_stakes_review(),
        }
        held = self.gate.evaluate(self.intent(no_permission), self.external)
        self.assertEqual(held.decision, ArmorDecision.HOLD)
        self.assertEqual(held.reason, "VERIFIED_DOES_NOT_CREATE_PERMISSION")

        permitted = dict(no_permission)
        permitted["user_initiated"] = True
        passed = self.gate.evaluate(self.intent(permitted, request_id="permitted"), self.external)
        self.assertEqual(passed.decision, ArmorDecision.PASS)
        self.assertTrue(passed.world_effect_allowed)

    def test_interpretation_acknowledgement_must_be_real_boolean(self):
        result = self.gate.evaluate(
            self.intent({
                "user_initiated": True,
                "decision_basis": DECISION_INTERPRETATION,
                "interpretation_acknowledged": "true",
            }),
            self.external,
        )
        self.assertEqual(result.decision, ArmorDecision.HOLD)
        self.assertIn("CONTROL_FIELD_TYPE_INVALID:interpretation_acknowledged", result.reason)


class HardenedFabricTests(unittest.TestCase):
    def test_hardened_gate_still_strips_control_plane_before_handler(self):
        fabric = HardenedTruthGuardArmoredThirdWishCapabilityFabric(now_tick=lambda: 100)
        fabric.issue_grant(
            grant_id="post-grant",
            actor_id="JANUS",
            capability_id="WEB.HTTP.POST",
            resource_pattern="https://*",
        )
        calls = []

        def handler(intent):
            calls.append(intent.request_id)
            self.assertEqual(set(intent.parameters), {"payload"})
            return {"ok": True}

        fabric.register_handler("WEB.HTTP.POST", handler)
        intent = ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id="strict-handler",
            actor_id="JANUS",
            grant_id="post-grant",
            capability_id="WEB.HTTP.POST",
            target="https://example.test/endpoint",
            operation="POST",
            purpose="ARMOR_V49_FABRIC_TEST",
            parameters={
                "_armor_context": {
                    "user_initiated": True,
                    "decision_basis": DECISION_DIRECT_USER_REQUEST,
                },
                "payload": "synthetic",
            },
        )
        result = fabric.execute(intent)
        self.assertEqual(result["status"], "SETTLED")
        self.assertEqual(calls, ["strict-handler"])


if __name__ == "__main__":
    unittest.main()
