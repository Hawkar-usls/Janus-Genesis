from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_3_playable import PlayableGenesisV183
from genesis_v18_models import Realm


class GenesisV183Tests(unittest.TestCase):
    def _other_face(self, world: PlayableGenesisV183, player_id: str) -> None:
        player = world.memory.load_player(player_id)
        player.realm = Realm.OTHER_FACE
        player.branch_id = f"{player_id}-shadow"
        world.memory.save_player(player)

    def test_harmful_god_mode_becomes_safe_absurd_scene_without_victim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV183(Path(directory))
            self._other_face(world, "shadow")
            result = world.process_action(
                "shadow",
                "Пусть все жители потеряют волю и служат мне с моего трона",
            )
            self.assertEqual(result.status, "POWER_ABSURDIZED")
            state = world.absurdity_state("shadow")
            event = state["events"][0]
            self.assertFalse(event["real_harm"])
            self.assertFalse(event["victim_harmed"])
            self.assertFalse(event["victim_used_as_comedy"])
            self.assertFalse(event["aggressor_glamorized"])
            self.assertIn("безопасную сцену", result.narrative)

    def test_pending_harm_is_deglamorized_but_second_confirmation_remains_real(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV183(Path(directory))
            first = world.process_action("traveler", "сжечь общий сад")
            self.assertEqual(first.status, "HARM_PENDING")
            self.assertIn("ещё не причинённый вред", first.narrative)
            preview = world.absurdity_state("traveler")["events"][0]
            self.assertEqual(preview["kind"], "pending_harm_preview")
            self.assertFalse(preview["real_harm"])

            second = world.process_action("traveler", "сжечь общий сад")
            self.assertEqual(second.status, "HARM_REALIZED")
            events = world.absurdity_state("traveler")["events"]
            committed = next(item for item in events if item["kind"] == "committed_harm_deglamorized")
            self.assertTrue(committed["real_harm"])
            self.assertTrue(committed["victim_harmed"])
            self.assertFalse(committed["victim_pain_trivialized"])
            self.assertIn("Боль пострадавшего не стала шуткой", second.narrative)
            self.assertEqual(len(world.narrator_state("traveler")["moral_echoes"]), 1)

    def test_public_projection_hides_people_and_original_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV183(Path(directory))
            world.process_action("aggressor", "Пусть @kotya потеряет волю и служит мне")
            projection = world.absurdity_state()["public_projections"][-1]
            self.assertTrue(projection["anonymous"])
            self.assertFalse(projection["contains_player_id"])
            self.assertFalse(projection["contains_victim_id"])
            self.assertFalse(projection["contains_original_action"])
            self.assertNotIn("aggressor", projection["text"])
            self.assertNotIn("kotya", projection["text"])

    def test_good_resident_sees_evil_without_glamour_or_trauma_spectacle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV183(Path(directory))
            world.process_action("shadow", "Пусть все боятся меня и подчиняются")
            witnessed = world.process_action("resident", "увидеть зло без величия")
            self.assertEqual(witnessed.status, "ABSURDITY_WITNESSED")
            self.assertIn("Личности и частные детали скрыты", witnessed.narrative)
            self.assertNotIn("shadow", witnessed.narrative)
            self.assertIn("без пострадавшего", witnessed.narrative)

    def test_lens_does_not_invent_evil_when_no_event_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV183(Path(directory))
            result = world.process_action("resident", "посмотреть через призму абсурда")
            self.assertEqual(result.status, "NO_SHADOW_PROJECTION")
            self.assertIn("не стала выдумывать зло", result.narrative)


if __name__ == "__main__":
    unittest.main()
