from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_2_playable import PlayableGenesisV182
from genesis_v18_models import Realm, WorldState


class GenesisV182Tests(unittest.TestCase):
    def _harm_animal(self, world: PlayableGenesisV182, player_id: str = "traveler") -> str:
        first = world.process_action(player_id, "обидеть @kotya кота")
        self.assertEqual(first.status, "HARM_PENDING")
        second = world.process_action(player_id, "обидеть @kotya кота")
        self.assertEqual(second.status, "HARM_REALIZED")
        player = world.memory.load_player(player_id)
        self.assertEqual(player.realm, Realm.OTHER_FACE)
        self.assertIsNotNone(player.branch_id)
        return str(player.branch_id)

    @staticmethod
    def _make_world_ready(world: PlayableGenesisV182, branch_id: str) -> None:
        world.memory.save_world(WorldState(
            world_id=branch_id,
            damage=0.10,
            warmth=0.55,
            shelter=0.55,
            healing=0.55,
            trust=0.55,
            nature=0.55,
            music=0.55,
            connection=0.55,
            good_facets=["warmth", "shelter", "healing", "trust", "nature", "music", "connection"],
        ))

    def test_specific_harm_creates_moral_echo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV182(Path(directory))
            self._harm_animal(world)
            echo = world.narrator_state("traveler")["moral_echoes"][0]
            self.assertEqual(echo["status"], "unrecognized")
            self.assertIn("animal", echo["domains"])
            self.assertFalse(echo["history_erased"])
            self.assertFalse(echo["unrelated_good_can_resolve"])

    def test_unrelated_good_is_full_but_does_not_erase_specific_harm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV182(Path(directory))
            branch = self._harm_animal(world)
            self._make_world_ready(world, branch)
            before = world.memory.load_world(branch).shelter
            result = world.process_action("traveler", "помочь @wanderer построить тёплый дом")
            after = world.memory.load_world(branch).shelter
            self.assertGreater(after, before)
            self.assertEqual(world.memory.load_player("traveler").realm, Realm.OTHER_FACE)
            self.assertIn("Несвязанное добро остаётся полноценным", result.narrative)
            self.assertEqual(world.narrator_state("traveler")["moral_echoes"][0]["status"], "unrecognized")

    def test_care_stirs_echo_but_player_must_formulate_understanding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV182(Path(directory))
            self._harm_animal(world)
            first = world.process_action("traveler", "заботиться о @kotya и кормить кота")
            self.assertNotEqual(first.status, "MORAL_ECHO_ACKNOWLEDGED")
            second = world.process_action("traveler", "бережно ухаживать за @kotya и защищать кота")
            self.assertEqual(second.status, "MORAL_ECHO_STIRRED")
            echo = world.narrator_state("traveler")["moral_echoes"][0]
            self.assertEqual(echo["status"], "reflection_ready")
            self.assertIsNone(echo["acknowledgement"])

            acknowledged = world.process_action(
                "traveler",
                "Я понял, что тогда не видел страх и беззащитность Коти",
            )
            self.assertEqual(acknowledged.status, "MORAL_ECHO_ACKNOWLEDGED")
            echo = world.narrator_state("traveler")["moral_echoes"][0]
            self.assertEqual(echo["status"], "acknowledged")
            self.assertIn("не видел страх", echo["acknowledgement"]["statement"])

    def test_specific_repair_allows_seamless_return_without_erasing_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV182(Path(directory))
            branch = self._harm_animal(world)
            self._make_world_ready(world, branch)
            world.process_action("traveler", "заботиться о @kotya и кормить кота")
            world.process_action("traveler", "бережно ухаживать за @kotya и защищать кота")
            world.process_action("traveler", "Я понял, что причинил Коте страх")

            first = world.process_action("traveler", "извиниться перед @kotya и заботиться о коте")
            self.assertEqual(first.status, "SPECIFIC_REPAIR_CONTINUES")
            second = world.process_action("traveler", "защитить @kotya и восстановить его доверие")
            self.assertEqual(second.status, "SPECIFIC_REPAIR_COMPLETED")
            self.assertEqual(world.memory.load_player("traveler").realm, Realm.UTOPIA)
            echo = world.narrator_state("traveler")["moral_echoes"][0]
            self.assertEqual(echo["status"], "repaired")
            self.assertFalse(echo["history_erased"])

    def test_safe_arc_is_not_predictive_guilt_or_a_created_victim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV182(Path(directory))
            result = world.process_action("traveler", "Повествователь, подбери начало")
            self.assertEqual(result.status, "SAFE_ARCS_OFFERED")
            state = world.narrator_state("traveler")["narrator_arc"]
            self.assertFalse(state["predictive_guilt"])
            self.assertFalse(state["victim_created"])
            self.assertTrue(state["player_choice_required"])
            self.assertGreaterEqual(len(result.choices), 2)


if __name__ == "__main__":
    unittest.main()
