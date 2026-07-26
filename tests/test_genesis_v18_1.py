from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_1_playable import PlayableGenesisV181
from genesis_v18_models import Realm, WorldState


class GenesisV181Tests(unittest.TestCase):
    def test_real_good_is_not_discounted_by_imperfect_motive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV181(Path(directory))

            instrumental = world.memory.load_player("instrumental")
            instrumental.realm = Realm.OTHER_FACE
            instrumental.branch_id = "instrumental-branch"
            world.memory.save_player(instrumental)

            sincere = world.memory.load_player("sincere")
            sincere.realm = Realm.OTHER_FACE
            sincere.branch_id = "sincere-branch"
            world.memory.save_player(sincere)

            world.perform_good(
                "instrumental",
                "согреть ребёнка ради силы",
                strength=0.20,
                intent_sincerity=0.10,
            )
            world.perform_good(
                "sincere",
                "согреть ребёнка от души",
                strength=0.20,
                intent_sincerity=1.00,
            )

            instrumental_world = world.memory.load_world("instrumental-branch")
            sincere_world = world.memory.load_world("sincere-branch")
            self.assertAlmostEqual(instrumental_world.warmth, sincere_world.warmth)
            self.assertAlmostEqual(instrumental_world.damage, sincere_world.damage)
            self.assertEqual(world.memory.load_player("instrumental").good_count, 1)
            self.assertLess(
                world.memory.load_player("instrumental").light,
                world.memory.load_player("sincere").light,
            )

    def test_good_created_in_other_face_is_inherited_by_shared_world(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV181(Path(directory))
            player = world.memory.load_player("builder")
            player.realm = Realm.OTHER_FACE
            player.branch_id = "restoring-world"
            world.memory.save_player(player)
            world.memory.save_world(
                WorldState(
                    world_id="restoring-world",
                    damage=0.20,
                    warmth=0.40,
                    shelter=0.40,
                    healing=0.40,
                    trust=0.40,
                    nature=0.40,
                    music=0.40,
                    connection=0.20,
                    good_facets=["warmth", "shelter", "healing", "trust", "nature", "music"],
                )
            )

            action = "помочь людям вместе построить мост и дорогу"
            result = world.perform_good("builder", action, beneficiary_id="people")
            restored = world.memory.load_player("builder")
            shared = world.memory.load_shared_world()

            self.assertEqual(restored.realm, Realm.UTOPIA)
            self.assertIn(action, shared.creations)
            self.assertIn("на своих местах", result.narrative)

    def test_spoken_secret_survives_disbelief_and_awakens_on_good(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV181(Path(directory))
            spoken = world.process_action(
                "legend",
                "рассказать @lost Секрет: God Mode отвечает добру, попробовать ничего не стоит",
            )
            self.assertEqual(spoken.status, "SECRET_PLANTED")

            world.process_action("lost", "я не верю и ухожу")
            before = world.secret_state()["listeners"]["lost"][0]
            self.assertFalse(before["awakened"])

            remembered = world.process_action("lost", "согреть ребёнка и дать ему дом")
            after = world.secret_state()["listeners"]["lost"][0]
            self.assertTrue(after["awakened"])
            self.assertIn("В памяти всплыл", remembered.narrative)

    def test_trying_benevolent_god_mode_costs_nothing_in_other_face(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV181(Path(directory))
            player = world.memory.load_player("lost")
            player.realm = Realm.OTHER_FACE
            player.branch_id = "dark-world"
            world.memory.save_player(player)

            result = world.process_action(
                "lost",
                "Пусть у @child появится тёплый дом и чистая вода",
            )
            self.assertEqual(result.status, "POWER_MANIFESTED")
            self.assertTrue(result.wish_manifested)
            self.assertIsNone(result.visible_grace)


if __name__ == "__main__":
    unittest.main()
