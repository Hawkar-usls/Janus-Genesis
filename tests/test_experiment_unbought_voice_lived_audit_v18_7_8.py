from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.unbought_voice_lived_audit_v18_7_8 import run_lived_audit


class UnboughtVoiceLivedAuditV1878Tests(unittest.TestCase):
    def test_ordinary_life_preserves_real_protections_and_exposes_next_boundaries(self) -> None:
        with (
            tempfile.TemporaryDirectory() as source,
            tempfile.TemporaryDirectory() as target,
            tempfile.TemporaryDirectory() as output,
        ):
            summary = run_lived_audit(Path(source), Path(target), Path(output))

        print("UNBOUGHT_VOICE_LIVED_AUDIT_SUMMARY_BEGIN")
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        print("UNBOUGHT_VOICE_LIVED_AUDIT_SUMMARY_END")

        self.assertEqual(summary["runtime_version"], "18.7.8")
        self.assertEqual(summary["days_lived"], 30)
        self.assertEqual(summary["turns_lived"], 90)
        self.assertEqual(summary["player"]["confirmed_harms"], 0)

        protections = summary["baseline_protections"]
        self.assertTrue(protections["independent_case_opened"])
        self.assertTrue(protections["independent_case_decided"])
        self.assertTrue(protections["obvious_farm_blocked"])
        self.assertEqual(protections["obvious_farm_independent_voice_count"], 1)
        self.assertEqual(protections["disclosed_smm_weight"], 1)
        self.assertTrue(protections["pending_accusation_preserved_voice"])
        self.assertEqual(protections["pending_record_status"], "PENDING_REVIEW")

        self.assertTrue(summary["portable_threshold"]["valid"])
        self.assertFalse(summary["portable_threshold"]["contains_api_keys"])
        self.assertTrue(summary["final_portable_world"]["valid"])
        self.assertFalse(summary["final_portable_world"]["contains_api_keys"])
        self.assertTrue(summary["verification"]["unbought_voice"]["valid"])
        self.assertTrue(summary["verification"]["chronicle"]["valid"])
        self.assertTrue(summary["verification"]["graph"]["valid"])
        self.assertTrue(summary["verification"]["free_other"]["valid"])

        defects = summary["observed_defects"]
        expected = {
            "campaign_sharding_can_hide_one_controller",
            "provider_verified_flag_is_not_cryptographically_bound",
            "cross_account_attestation_can_launder_voice_eligibility",
            "deactivated_or_withdrawn_voice_remains_audit_eligible",
            "caller_supplied_confidence_can_select_sovereign_position",
            "sovereign_reviewer_is_spoofable_string_not_capability",
            "rejected_appeal_does_not_restore_voice_eligibility",
            "manipulation_review_overwrites_status_without_history",
        }
        self.assertEqual(set(defects), expected)
        self.assertTrue(all(defects.values()), defects)


if __name__ == "__main__":
    unittest.main()
