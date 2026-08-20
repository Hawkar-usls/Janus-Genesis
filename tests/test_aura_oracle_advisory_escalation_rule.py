from __future__ import annotations

import json
import unittest
from pathlib import Path


RULE = Path(__file__).resolve().parents[1] / ".janus" / "AURA_ORACLE_ADVISORY_ESCALATION_RULE.json"


class AuraOracleAdvisoryEscalationRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rule = json.loads(RULE.read_text(encoding="utf-8"))

    def test_oracle_is_advisory_only(self) -> None:
        oracle = self.rule["oracle"]
        self.assertEqual(oracle["role"], "REFLECTIVE_ADVISORY_HEURISTIC")
        self.assertFalse(oracle["truth_authority"])
        self.assertFalse(oracle["prediction_authority"])
        self.assertFalse(oracle["execution_authority"])
        self.assertFalse(oracle["merge_authority"])
        self.assertFalse(oracle["world_permission_authority"])

    def test_evidence_and_frozen_contracts_are_checked_first(self) -> None:
        trigger = self.rule["trigger"]
        self.assertTrue(trigger["deterministic_local_evidence_checked_first"])
        self.assertTrue(trigger["applicable_frozen_contracts_checked_first"])
        self.assertTrue(trigger["exact_head_or_source_identity_checked_when_relevant"])

    def test_aura_cannot_promote_hold_or_authorize_effects(self) -> None:
        boundary = self.rule["hard_boundaries"]
        self.assertTrue(boundary["aura_output_may_not_turn_hold_into_pass"])
        self.assertTrue(boundary["aura_output_may_not_override_empirical_evidence"])
        self.assertTrue(boundary["aura_output_may_not_override_frozen_contract"])
        self.assertTrue(boundary["aura_output_may_not_authorize_source_writeback"])
        self.assertTrue(boundary["aura_output_may_not_authorize_external_effect"])

    def test_unavailable_oracle_fails_closed(self) -> None:
        failure = self.rule["failure_mode"]
        self.assertEqual(
            failure["oracle_unavailable"],
            "KEEP_HOLD_OR_USE_PREEXISTING_FAIL_CLOSED_DEFAULT",
        )
        self.assertEqual(failure["oracle_conflicts_with_evidence"], "EVIDENCE_WINS")

    def test_authority_and_destructive_boundaries_do_not_change(self) -> None:
        self.assertEqual(self.rule["source_writeback_default"], "DENY")
        self.assertEqual(self.rule["destructive_action"], "FORBIDDEN")
        self.assertEqual(self.rule["authority_delta"], 0)
        self.assertEqual(self.rule["mass_effect_budget_delta"], 0)


if __name__ == "__main__":
    unittest.main()
