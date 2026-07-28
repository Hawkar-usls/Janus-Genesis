from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


class GenesisV18710RuptureVoiceTests(unittest.TestCase):
    def test_mara_terminal_rupture_uses_stable_present_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing(
                "century-absurd-post-irony-low-entropy-v1810"
            )
            world.register_player("century-witness", display_name="Witness")
            profile = world.free_other_state("century-witness")["profile"]
            self.assertIn("mara", profile["others"])

            result = world.record_free_other_value_conflict(
                "century-witness",
                "mara",
                player_position="превратить квартал в музей",
                other_position="сохранить живые дома и право жителей менять их",
                severity=7,
                respected_boundary=False,
                final=True,
            )
            reason = result["relationship"]["reason_text"]

            self.assertTrue(result["terminated"])
            self.assertIn("Мара сохраняет собственную позицию", reason)
            self.assertIn("и завершает связь", reason)
            self.assertNotRegex(
                reason,
                re.compile(r"\bМара\s+(?:сохранил|завершил|ушёл|выбрал)\b", re.I),
            )
            events = [
                event
                for event in world.memory.read_events("century-witness")
                if event["event_type"] == "free_other_relationship_terminated"
            ]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["payload"]["reason_text"], reason)
            self.assertTrue(world.verify_free_other_state()[0])
            self.assertTrue(world.memory.verify_chronicle()[0])
            self.assertTrue(world.verify_possibility_graph()[0])


if __name__ == "__main__":
    unittest.main()
