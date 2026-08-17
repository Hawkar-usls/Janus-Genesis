from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from goldprompt_intent_guard import (  # noqa: E402
    build_handoff,
    build_intent_anchor,
    evaluate_answer,
    osiris_christ_regression_fixture,
    self_test,
    should_emit,
    verify_handoff,
    verify_intent_anchor,
)


class GoldPromptIntentGuardTests(unittest.TestCase):
    def fixture(self):
        return osiris_christ_regression_fixture()

    def test_historical_context_bleed_fixture_is_blocked(self):
        fixture = self.fixture()
        self.assertEqual(fixture["bad_receipt"]["final_alignment_state"], "HOLD_CONTEXT_BLEED")
        self.assertFalse(should_emit(fixture["bad_receipt"]))
        self.assertIn("UNRESOLVED_STALE_CONTINUATION_OPENER", fixture["bad_receipt"]["strong_signals"])

    def test_direct_answer_passes_before_optional_association(self):
        fixture = self.fixture()
        receipt = fixture["good_receipt"]
        self.assertEqual(receipt["final_alignment_state"], "PASS")
        self.assertTrue(receipt["first_paragraph_alignment_pass"])
        self.assertTrue(receipt["answer_contract_evidence_pass"])
        self.assertTrue(receipt["emergent_insight_separated"])
        self.assertTrue(should_emit(receipt))

    def test_keyword_stuffing_is_not_task_completion(self):
        fixture = self.fixture()
        receipt = fixture["keyword_stuffed_bad_receipt"]
        self.assertEqual(receipt["final_alignment_state"], "HOLD_CONTEXT_BLEED")
        self.assertFalse(receipt["answer_contract_evidence_pass"])
        self.assertIn("ANSWER_CONTRACT_EVIDENCE_INCOMPLETE", receipt["strong_signals"])

    def test_optional_association_cannot_seize_primary_lane(self):
        fixture = self.fixture()
        receipt = fixture["early_association_bad_receipt"]
        self.assertEqual(receipt["final_alignment_state"], "HOLD_CONTEXT_BLEED")
        self.assertFalse(receipt["emergent_insight_separated"])
        self.assertIn("OPTIONAL_ASSOCIATION_ENTERED_PRIMARY_ANSWER_LANE", receipt["strong_signals"])

    def test_intent_anchor_is_content_addressed(self):
        anchor = self.fixture()["anchor"]
        self.assertTrue(verify_intent_anchor(anchor))
        tampered = copy.deepcopy(anchor)
        tampered["requested_operation"] = "SUMMARIZE"
        self.assertFalse(verify_intent_anchor(tampered))

    def test_face_handoff_must_preserve_intent_identity(self):
        anchor = self.fixture()["anchor"]
        handoff = build_handoff(anchor, face_id="RIGHT_INAIHR", context_tier_used=2)
        self.assertTrue(verify_handoff(anchor, handoff))

        for field, value in (
            ("intent_id", "0" * 64),
            ("current_turn_digest", "0" * 64),
            ("requested_operation", "SUMMARIZE"),
            ("primary_entities", ["BD101"]),
        ):
            drifted = copy.deepcopy(handoff)
            drifted[field] = value
            self.assertFalse(verify_handoff(anchor, drifted), field)

    def test_deep_context_is_allowed_only_after_primary_answer_lane(self):
        anchor = self.fixture()["anchor"]
        answer = (
            "Осирис и Иисус Христос имеют сходство в преодолении смерти, но модели различаются: "
            "Осирис восстанавливается, Христос воскресает, а Второе пришествие является отдельным будущим событием.\n\n"
            "После прямого сравнения можно отдельно обсудить JANUS и BD101."
        )
        self.assertEqual(evaluate_answer(anchor, answer)["final_alignment_state"], "PASS")

    def test_self_test_passes(self):
        self.assertEqual(self_test()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
