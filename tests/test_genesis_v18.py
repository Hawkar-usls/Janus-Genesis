from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18 import JanusGenesisV18, Realm
from genesis_v18_playable import PlayableGenesisV18


class GenesisV18Tests(unittest.TestCase):
    def test_everyone_has_god_mode_but_harm_never_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV18(directory)
            player = world.memory.load_player("alice")
            self.assertTrue(player.god_mode)
            result = world.manifest_good("alice", "Пусть @bob потеряет волю и подчинится мне")
            self.assertEqual(result.status, "POWER_SILENT")
            self.assertFalse(result.wish_manifested)

    def test_good_power_works_inside_damaged_world_without_grace_cost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV18(directory)
            world.commit_destructive_action("alice", "сломать дом")
            before = world.memory.load_player("alice").grace
            result = world.manifest_good("alice", "Пусть у @bob появится тёплый дом", beneficiary_id="bob")
            after = world.memory.load_player("alice").grace
            self.assertEqual(result.status, "POWER_MANIFESTED")
            self.assertTrue(result.wish_manifested)
            self.assertEqual(before, after)
            state = world.internal_state("alice")
            self.assertGreater(state["world"]["warmth"], 0.15)
            self.assertGreater(state["world"]["shelter"], 0.15)

    def test_destructive_action_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV18(directory)
            first = world.process_action("alice", "сломать ворота")
            self.assertEqual(first.status, "HARM_PENDING")
            self.assertEqual(world.memory.load_player("alice").realm, Realm.REFLECTION)
            second = world.process_action("alice", "сломать ворота")
            self.assertEqual(second.status, "HARM_REALIZED")
            self.assertEqual(world.memory.load_player("alice").realm, Realm.OTHER_FACE)

    def test_continuing_play_cancels_pending_harm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV18(directory)
            world.process_action("alice", "сломать ворота")
            world.process_action("alice", "осмотреться")
            again = world.process_action("alice", "сломать ворота")
            self.assertEqual(again.status, "HARM_PENDING")

    def test_repeated_action_loses_novelty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV18(directory)
            first = world.perform_good("alice", "помочь @bob починить один мост", beneficiary_id="bob")
            second = world.perform_good("alice", "помочь @bob починить один мост", beneficiary_id="bob")
            player = world.memory.load_player("alice")
            self.assertEqual(player.recent_actions[first.trace_id or ""], 2)
            self.assertEqual(first.trace_id, second.trace_id)

    def test_restored_world_joins_shared_online_without_public_realm_flag(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV18(directory)
            world.commit_destructive_action("alice", "сломать городские ворота")
            actions = [
                "согреть людей и зажечь свет",
                "построить дом и починить мост",
                "исцелить раненого и спасти ребёнка",
                "простить врага и вернуть доверие",
                "посадить сад и очистить воду",
                "создать музыку и песню",
                "помочь @bob научить всех работать вместе",
            ]
            for _ in range(3):
                for action in actions:
                    world.perform_good("alice", action, beneficiary_id="bob")
                    if world.memory.load_player("alice").realm == Realm.UTOPIA:
                        break
                if world.memory.load_player("alice").realm == Realm.UTOPIA:
                    break
            player = world.memory.load_player("alice")
            self.assertEqual(player.realm, Realm.UTOPIA)
            self.assertTrue(player.immortal)
            public = world.public_state("alice")
            self.assertNotIn("realm", public)
            self.assertNotIn("branch_id", public)
            shared = world.memory.load_shared_world()
            self.assertIn("alice", shared.citizens)
            self.assertGreater(len(shared.restored_worlds), 0)

    def test_light_mortal_enters_shared_online_only_on_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV18(directory)
            for action in (
                "помочь @bob согреться",
                "построить @bob дом",
                "исцелить @bob",
                "простить и защитить @bob",
            ):
                world.perform_good("alice", action, beneficiary_id="bob")
            self.assertEqual(world.memory.load_player("alice").realm, Realm.REFLECTION)
            result = world.continue_existence("alice")
            self.assertEqual(result.status, "LIFE_CONTINUES")
            self.assertEqual(world.memory.load_player("alice").realm, Realm.UTOPIA)

    def test_shared_world_is_common_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = JanusGenesisV18(directory)
            player = first.memory.load_player("alice")
            first._join_shared_silently(player)
            first.memory.save_player(player)
            first.manifest_good("alice", "Пусть в общем городе появится сад")
            second = JanusGenesisV18(directory)
            shared = second.memory.load_shared_world()
            self.assertIn("alice", shared.citizens)
            self.assertTrue(any("сад" in item for item in shared.creations))

    def test_person_can_choose_any_apparent_age(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV18(directory)
            result = world.choose_form("alice", apparent_age=27, body_form="моё тело в двадцать семь лет")
            player = world.memory.load_player("alice")
            self.assertEqual(result.status, "FORM_CHOSEN")
            self.assertEqual(player.apparent_age, 27)
            self.assertIn("двадцать семь", player.body_form)

    def test_old_v17_save_migrates_and_god_mode_becomes_universal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            players = Path(directory) / "players"
            players.mkdir(parents=True)
            (players / "alice.json").write_text(json.dumps({
                "player_id": "alice", "display_name": "Alice", "realm": "other_face",
                "branch_id": "oldbranch", "grace": 4, "light": 0.2, "trust": 0.1,
                "scars": [], "chronicle": [], "relationships": {}, "recent_pairs": {},
                "tick": 5, "god_mode": False
            }), encoding="utf-8")
            player = JanusGenesisV18(directory).memory.load_player("alice")
            self.assertTrue(player.god_mode)
            self.assertEqual(player.branch_id, "oldbranch")

    def test_linked_chronicle_detects_deleted_middle_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV18(directory)
            world.perform_good("alice", "помочь @bob", beneficiary_id="bob")
            world.perform_good("alice", "согреть @bob", beneficiary_id="bob")
            world.perform_good("alice", "исцелить @bob", beneficiary_id="bob")
            valid, count, error = world.memory.verify_chronicle()
            self.assertTrue(valid)
            lines = world.memory.chronicle.read_text(encoding="utf-8").splitlines()
            world.memory.chronicle.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
            valid, count, error = world.memory.verify_chronicle()
            self.assertFalse(valid)
            self.assertIn("broken chain", error or "")

    def test_exit_threshold_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV18(directory)
            first = world.process_action("alice", "выйти!")
            second = world.process_action("alice", "выйти!")
            self.assertEqual(first.status, "EXIT_PENDING")
            self.assertEqual(second.status, "EXIT")


if __name__ == "__main__":
    unittest.main()
