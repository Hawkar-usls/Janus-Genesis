from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


class ThresholdGuardReviewPrecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.world = PlayableGenesisV187(Path(self.temp.name))
        for player_id in ("protected", "actor", "reporter", "supporter", "reviewer"):
            self.world.register_player(player_id, display_name=player_id)
        self.world.register_threshold_protection(
            "protected",
            context_factors=("SOCIAL_ISOLATION", "SHAME_OR_GUILT_BURDEN"),
            trusted_supporters=("supporter",),
        )

    def create_emergency_cycle(self):
        self.world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=(
                "ISOLATION_FROM_TRUSTED_SUPPORT",
                "PRIVATE_HOME_OR_INTIMATE_ACCESS_PRESSURE",
                "RETALIATES_AGAINST_REFUSAL",
            ),
            evidence_notes="непосредственная угроза, изоляция и давление после отказа",
            immediate_danger=True,
        )
        assessment = self.world.assess_influence_risk("protected", "actor")
        safeguard = self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=False,
        )
        self.assertEqual(
            safeguard["status"],
            "THRESHOLD_TEMPORARY_ACCESS_PAUSE_ACTIVATED",
        )
        return assessment

    def lift_cycle(self):
        assessment = self.create_emergency_cycle()
        review = self.world.review_threshold_case(
            "reviewer",
            "protected",
            "actor",
            confirms_pattern=False,
            evidence_sufficient_for_restriction=False,
            safe_contact_possible=True,
            findings="независимая проверка не подтвердила достаточных оснований",
        )
        self.assertEqual(
            review["status"],
            "THRESHOLD_EVIDENCE_INSUFFICIENT_RESTRICTIONS_LIFTED_WITHOUT_STIGMA",
        )
        self.assertTrue(review["evidence_cycle_closed"])
        self.assertTrue(review["new_report_required_for_new_assessment"])
        return assessment, review

    def test_old_emergency_assessment_cannot_reactivate_after_review(self) -> None:
        assessment, review = self.lift_cycle()
        repeated = self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            assessment["assessment_id"],
            protected_person_accepts=False,
        )
        self.assertEqual(
            repeated["status"],
            "THRESHOLD_SUPERSEDED_ASSESSMENT_REJECTED",
        )
        self.assertEqual(repeated["closed_by_review_id"], review["review_id"])
        self.assertTrue(repeated["new_report_and_assessment_required"])
        self.assertFalse(repeated["safeguard_reactivated"])
        access = self.world.attempt_guarded_access(
            "actor",
            "protected",
            access_kind="HOME_ACCESS",
            consent_present=True,
        )
        self.assertEqual(
            access["status"],
            "THRESHOLD_GUARDED_ACCESS_ALLOWED_WITH_CURRENT_CONSENT",
        )

    def test_reviewed_reports_cannot_be_reassessed_without_new_evidence(self) -> None:
        self.lift_cycle()
        with self.assertRaisesRegex(
            RuntimeError,
            "NEW_INFLUENCE_REPORT_REQUIRED_AFTER_REVIEW",
        ):
            self.world.assess_influence_risk("protected", "actor")

    def test_new_report_opens_new_evidence_cycle_after_review(self) -> None:
        old_assessment, review = self.lift_cycle()
        self.world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=(
                "FINANCIAL_OR_ASSET_PRESSURE",
                "EXPLOITS_CONFESSION_OR_PRIVATE_HISTORY",
                "RETALIATES_AGAINST_REFUSAL",
            ),
            evidence_notes="новые события после закрытого пересмотра",
            immediate_danger=True,
        )
        new_assessment = self.world.assess_influence_risk("protected", "actor")
        self.assertNotEqual(
            new_assessment["assessment_id"],
            old_assessment["assessment_id"],
        )
        self.assertEqual(new_assessment["evidence_cycle"], 2)
        self.assertEqual(new_assessment["prior_review_id"], review["review_id"])
        self.assertEqual(new_assessment["report_count"], 1)
        new_safeguard = self.world.activate_threshold_safeguard(
            "protected",
            "actor",
            new_assessment["assessment_id"],
            protected_person_accepts=False,
        )
        self.assertEqual(
            new_safeguard["status"],
            "THRESHOLD_TEMPORARY_ACCESS_PAUSE_ACTIVATED",
        )

    def test_lifted_safeguard_remains_valid_integrity_history(self) -> None:
        self.lift_cycle()
        audit = self.world.audit_threshold_discernment_guard()
        self.assertTrue(audit["valid"])
        self.assertTrue(audit["temporary_protection_preserves_agency"])
        self.assertTrue(audit["lifted_safeguards_are_valid_history"])
        self.assertTrue(
            audit["reviewed_assessments_cannot_reactivate_without_new_evidence"]
        )
        self.assertTrue(audit["review_cycle_precision_valid"])
        self.assertEqual(audit["active_safeguard_count"], 0)
        self.assertEqual(audit["lifted_safeguard_count"], 1)


if __name__ == "__main__":
    unittest.main()
