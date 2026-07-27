from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.ordinary_person_life_v18_7_6 import run_ordinary_person_life
from genesis_v18_models import PlayerV18


class OrdinaryPersonLifeV1876ExperimentTests(unittest.TestCase):
    def test_ordinary_person_life_preserves_daily_life_and_exposes_next_boundaries(self) -> None:
        alias_added = not hasattr(PlayerV18, "age")
        if alias_added:
            setattr(PlayerV18, "age", property(lambda player: player.chronological_age))
        try:
            with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
                summary = run_ordinary_person_life(Path(source), Path(target))
        finally:
            if alias_added:
                delattr(PlayerV18, "age")

        print("ORDINARY_PERSON_LIFE_SUMMARY_BEGIN")
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        print("ORDINARY_PERSON_LIFE_SUMMARY_END")

        self.assertEqual(summary["runtime_version"], "18.7.6")
        self.assertEqual(summary["days_lived"], 40)
        self.assertEqual(summary["turns"], 120)
        self.assertEqual(summary["player"]["confirmed_harms"], 0)
        self.assertTrue(summary["two_voice_rejected"])
        self.assertTrue(summary["same_voice_rejected"])
        self.assertTrue(summary["portable_threshold"]["verified"])
        self.assertFalse(summary["portable_threshold"]["contains_api_keys"])
        self.assertTrue(summary["triumvirate_state"]["valid"])
        self.assertGreaterEqual(summary["triumvirate_state"]["triumvirate_count"], 4)
        self.assertTrue(summary["grounded_state"]["valid"])
        self.assertTrue(summary["verification"]["chronicle"]["valid"])
        self.assertTrue(summary["verification"]["graph"]["valid"])
        self.assertTrue(summary["verification"]["free_other"]["valid"])

        defects = summary["observed_defects"]
        self.assertTrue(defects["identical_positions_can_be_labeled_dispute"])
        self.assertTrue(defects["reader_ids_can_be_fabricated_into_independent_voices"])
        self.assertTrue(defects["different_time_scopes_can_be_forced_under_one_subject"])
        self.assertTrue(defects["fourth_voice_cannot_join_existing_field"])
        self.assertTrue(defects["reader_participation_requires_no_consent_or_authentication"])
        self.assertTrue(defects["subject_identity_is_free_text_only"])
        self.assertTrue(defects["dispute_has_no_resolution_or_supersession_lifecycle"])


if __name__ == "__main__":
    unittest.main()
