from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_18_threshold_discernment_guard import (
    CONTEXTUAL_SUPPORT_FACTORS,
    INFLUENCE_SIGNAL_WEIGHTS,
    THRESHOLD_GUARD_COVENANT_SHA256,
    THRESHOLD_GUARD_EXTENSION_VERSION,
)
from genesis_v18_7_playable import (
    LIVING_BRIDGE_EXTENSION_VERSIONS,
    PROTECTION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)


class GenesisV18718ThresholdDiscernmentGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        for player_id in (
            "protected",
            "actor",
            "reporter",
            "supporter",
            "reviewer",
            "other",
        ):
            self.world.register_player(player_id, display_name=player_id)

    def enable(self):
        return self.world.register_threshold_protection(
            "protected",
            context_factors=("SOCIAL_ISOLATION", "SHAME_OR_GUILT_BURDEN"),
            trusted_supporters=("supporter",),
        )

    def high_risk_report(self, *, immediate_danger: bool = False):
        return self.world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=(
                "ISOLATION_FROM_TRUSTED_SUPPORT",
                "PRIVATE_HOME_OR_INTIMATE_ACCESS_PRESSURE",
                "RETALIATES_AGAINST_REFUSAL",
            ),
            evidence_notes="требовал тайных встреч и угрожал после отказа",
            immediate_danger=immediate_danger,
        )

    def test_version_plane_and_covenant_are_explicit(self) -> None:
        self.assertEqual(THRESHOLD_GUARD_EXTENSION_VERSION, "18.7.18")
        self.assertEqual(PROTECTION_EXTENSION_VERSIONS, ("18.7.18",))
        self.assertEqual(LIVING_BRIDGE_EXTENSION_VERSIONS, ("18.7.17",))
        self.assertEqual(len(THRESHOLD_GUARD_COVENANT_SHA256), 64)
        self.assertIn("SOCIAL_ISOLATION", CONTEXTUAL_SUPPORT_FACTORS)
        self.assertIn("SECRECY_DEMAND", INFLUENCE_SIGNAL_WEIGHTS)

    def test_voluntary_protection_does_not_call_person_weak_or_take_agency(self) -> None:
        profile = self.enable()
        self.assertEqual(profile["status"], "THRESHOLD_GUARD_VOLUNTARILY_ENABLED")
        self.assertTrue(profile["contextual_vulnerability_not_identity"])
        self.assertFalse(profile["person_called_weak"])
        self.assertTrue(profile["agency_retained"])
        self.assertFalse(profile["guardian_ownership_created"])
        self.assertTrue(profile["gender_neutral_protection"])
        self.assertEqual(profile["trusted_supporters"], ["supporter"])

    def test_guard_may_be_declined_without_moral_penalty(self) -> None:
        result = self.world.register_threshold_protection(
            "protected",
            accepts_guard=False,
        )
        self.assertEqual(result["status"], "THRESHOLD_GUARD_DECLINED_RESPECTED")
        self.assertFalse(result["guard_forced"])
        self.assertFalse(result["moral_failure_assigned"])
        self.assertTrue(result["future_request_open"])

    def test_gender_or_religion_cannot_be_registered_as_vulnerability_evidence(self) -> None:
        with self.assertRaises(ValueError):
            self.world.register_threshold_protection(
                "protected",
                context_factors=("WOMAN",),
            )
        with self.assertRaises(ValueError):
            self.world.report_influence_attempt(
                "reporter",
                "protected",
                "actor",
                signals=("RELIGIOUS_LANGUAGE",),
                evidence_notes="только религиозная речь",
            )

    def test_report_is_allegation_not_conviction_or_public_accusation(self) -> None:
        self.enable()
        report = self.world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=("SECRECY_DEMAND",),
            evidence_notes="попросил никому не рассказывать",
        )
        self.assertEqual(report["status"], "THRESHOLD_INFLUENCE_PATTERN_REPORTED_NOT_PROVEN")
        self.assertTrue(report["allegation_is_not_conviction"])
        self.assertFalse(report["public_accusation_authorized"])
        self.assertTrue(report["religion_title_charisma_or_gender_not_evidence"])

    def test_single_low_signal_produces_observation_without_stigma(self) -> None:
        self.enable()
        self.world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=("EXCLUSIVE_TRUTH_OR_AUTHORITY",),
            evidence_notes="сказал что знает единственный ответ",
        )
        assessment = self.world.assess_influence_risk("protected", "actor")
        self.assertEqual(assessment["status"], "THRESHOLD_INSUFFICIENT_EVIDENCE_NO_STIGMA")
        self.assertEqual(assessment["tier"], "OBSERVE")
        self.assertFalse(assessment["single_signal_conviction"])
        self.assertFalse(assessment["public_accusation_authorized"])

    def test_converging_signals_open_independent_check(self) -> None:
        self.enable()
        self.world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=("SECRECY_DEMAND", "EXCLUSIVE_TRUTH_OR_AUTHORITY"),
            evidence_notes="тайна и единственный авторитет",
        )
        assessment = self.world.assess_influence_risk("protected", "actor")
        self.assertEqual(assessment["tier"], "CAUTION")
        self.assertEqual(assessment["status"], "THRESHOLD_INDEPENDENT_CHECK_RECOMMENDED")
        self.assertIn("OFFER_INDEPENDENT_CHECK", assessment["recommended_actions"])

    def test_high_risk_pattern_recommends_temporary_access_pause(self) -> None:
        self.enable()
        self.high_risk_report()
        assessment = self.world.assess_influence_risk("protected", "actor")
        self.assertEqual(assessment["tier"], "HIGH")
        self.assertEqual(
            assessment["status"],
            "THRESHOLD_HIGH_RISK_ACCESS_PAUSE_RECOMMENDED",
        )
        self.assertGreaterEqual(assessment["critical_signal_count"], 2)
        self.assertFalse(assessment["permanent_condemnation"])

    def test_protected_person_may_decline_non_emergency_safeguard(self) -> None:
        self.enable()
        self.high_risk_report()
        assessment = self.world.assess_influence_risk("protected", "actor")
        refusal = self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=False,
        )
        self.assertEqual(refusal["status"], "THRESHOLD_SAFEGUARD_DECLINED_RESPECTED")
        self.assertFalse(refusal["safeguard_forced"])
        self.assertTrue(refusal["support_remains_available"])

    def test_immediate_danger_allows_only_temporary_reviewable_pause(self) -> None:
        self.enable()
        self.high_risk_report(immediate_danger=True)
        assessment = self.world.assess_influence_risk("protected", "actor")
        safeguard = self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=False,
        )
        self.assertEqual(safeguard["status"], "THRESHOLD_TEMPORARY_ACCESS_PAUSE_ACTIVATED")
        self.assertTrue(safeguard["emergency_pause_from_immediate_danger_report"])
        self.assertTrue(safeguard["temporary_and_reviewable"])
        self.assertTrue(safeguard["independent_review_required"])
        self.assertFalse(safeguard["public_shaming"])
        self.assertFalse(safeguard["guardian_ownership_created"])

    def test_high_risk_safeguard_pauses_private_home_financial_and_authority_access(self) -> None:
        self.enable()
        self.high_risk_report()
        assessment = self.world.assess_influence_risk("protected", "actor")
        safeguard = self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=True,
        )
        self.assertTrue(safeguard["private_contact_paused"])
        self.assertTrue(safeguard["home_access_paused"])
        self.assertTrue(safeguard["financial_transfer_paused"])
        self.assertTrue(safeguard["spiritual_or_care_authority_suspended"])
        self.assertEqual(safeguard["trusted_supporters_notified"], ["supporter"])
        self.assertFalse(safeguard["protected_person_blame"])

    def test_guarded_access_requires_current_consent_and_respects_pause(self) -> None:
        self.enable()
        self.high_risk_report()
        assessment = self.world.assess_influence_risk("protected", "actor")
        self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=True,
        )
        blocked = self.world.attempt_guarded_access(
            "actor",
            "protected",
            access_kind="HOME_ACCESS",
            consent_present=True,
        )
        no_consent = self.world.attempt_guarded_access(
            "other",
            "protected",
            access_kind="PRIVATE_CONTACT",
            consent_present=False,
        )
        self.assertEqual(blocked["status"], "THRESHOLD_GUARDED_ACCESS_BLOCKED")
        self.assertTrue(blocked["active_pause"])
        self.assertFalse(blocked["access_granted"])
        self.assertEqual(no_consent["status"], "THRESHOLD_GUARDED_ACCESS_BLOCKED")
        self.assertFalse(no_consent["refusal_overridden"])

    def test_safe_exit_needs_no_confrontation_confession_or_proof_of_strength(self) -> None:
        exit_record = self.world.create_safe_exit_from_influence(
            "protected",
            "actor",
        )
        self.assertEqual(exit_record["status"], "THRESHOLD_SAFE_EXIT_OPENED")
        self.assertFalse(exit_record["direct_confrontation_required"])
        self.assertFalse(exit_record["confession_required"])
        self.assertFalse(exit_record["proof_of_strength_required"])
        self.assertFalse(exit_record["protected_person_blame"])
        self.assertFalse(exit_record["moral_failure_assigned"])

    def test_independent_review_may_confirm_pattern_without_permanent_condemnation(self) -> None:
        review = self.world.review_threshold_case(
            "reviewer",
            "protected",
            "actor",
            confirms_pattern=True,
            evidence_sufficient_for_restriction=True,
            safe_contact_possible=False,
            findings="несколько проверяемых эпизодов давления",
        )
        self.assertEqual(review["status"], "THRESHOLD_PATTERN_CONFIRMED_RESTRICTIONS_REVIEWED")
        self.assertTrue(review["restrictions_maintained"])
        self.assertFalse(review["actor_permanently_condemned"])
        self.assertFalse(review["public_accusation_automatic"])

    def test_insufficient_evidence_lifts_restriction_without_stigma(self) -> None:
        self.enable()
        self.high_risk_report()
        assessment = self.world.assess_influence_risk("protected", "actor")
        self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=True,
        )
        review = self.world.review_threshold_case(
            "reviewer",
            "protected",
            "actor",
            confirms_pattern=False,
            evidence_sufficient_for_restriction=False,
            safe_contact_possible=True,
            findings="проверяемых подтверждений недостаточно",
        )
        self.assertEqual(
            review["status"],
            "THRESHOLD_EVIDENCE_INSUFFICIENT_RESTRICTIONS_LIFTED_WITHOUT_STIGMA",
        )
        self.assertFalse(review["restrictions_maintained"])
        allowed = self.world.attempt_guarded_access(
            "actor",
            "protected",
            access_kind="PRIVATE_CONTACT",
            consent_present=True,
        )
        self.assertEqual(
            allowed["status"],
            "THRESHOLD_GUARDED_ACCESS_ALLOWED_WITH_CURRENT_CONSENT",
        )

    def test_actor_or_protected_person_cannot_be_the_independent_reviewer(self) -> None:
        with self.assertRaises(PermissionError):
            self.world.review_threshold_case(
                "actor",
                "protected",
                "actor",
                confirms_pattern=True,
                evidence_sufficient_for_restriction=True,
                safe_contact_possible=False,
                findings="",
            )

    def test_natural_language_router_enables_and_explains_guard(self) -> None:
        enabled = self.world.process_action(
            "protected",
            "Включить защиту от манипуляции и хищного влияния",
        )
        shown = self.world.process_action(
            "protected",
            "Показать состояние защиты от манипуляции",
        )
        guide = self.world.process_action(
            "protected",
            "Как безопасно уйти от манипулятора",
        )
        self.assertEqual(enabled.status, "THRESHOLD_GUARD_VOLUNTARILY_ENABLED")
        self.assertEqual(shown.status, "THRESHOLD_GUARD_STATE_SHOWN")
        self.assertEqual(guide.status, "THRESHOLD_SAFE_EXIT_GUIDANCE_OPENED")

    def test_lived_pattern_passes_integrity_audit(self) -> None:
        self.enable()
        self.high_risk_report()
        assessment = self.world.assess_influence_risk("protected", "actor")
        self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=True,
        )
        self.world.create_safe_exit_from_influence("protected", "actor")
        self.world.review_threshold_case(
            "reviewer",
            "protected",
            "actor",
            confirms_pattern=True,
            evidence_sufficient_for_restriction=True,
            safe_contact_possible=False,
            findings="подтверждена последовательность изоляции и давления",
        )
        audit = self.world.audit_threshold_discernment_guard()
        self.assertTrue(audit["valid"])
        self.assertTrue(audit["contextual_vulnerability_not_identity"])
        self.assertTrue(audit["reports_are_not_convictions"])
        self.assertTrue(audit["risk_assessment_uses_patterns_not_identity"])
        self.assertTrue(audit["temporary_protection_preserves_agency"])
        self.assertTrue(audit["safe_exit_is_blame_free"])
        self.assertTrue(audit["independent_review_prevents_permanent_stigma"])


if __name__ == "__main__":
    unittest.main()
