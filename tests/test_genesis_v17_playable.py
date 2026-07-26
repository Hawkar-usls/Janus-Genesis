from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v17 import Realm
from genesis_v17_playable import PlayableGenesisV17


class PlayableGenesisV17Tests(unittest.TestCase):
    def test_natural_language_help_creates_trace_for_named_player(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV17(Path(directory))
            result = world.process_action(
                "alice", "помочь @bob починить крышу после пожара"
            )
            self.assertEqual(result.status, "GRACE_PENDING")
            self.assertIsNotNone(result.trace_id)
            trace = world.memory.load_trace(result.trace_id or "")
            self.assertEqual(trace.beneficiary_id, "bob")

    def test_destructive_action_enters_other_face(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = PlayableGenesisV17(Path(directory)).process_action(
                "alice", "сломать ворота деревни"
            )
            self.assertEqual(result.status, "SEVERED")
            self.assertEqual(result.realm, Realm.OTHER_FACE)

    def test_exit_with_punctuation_is_respected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = PlayableGenesisV17(Path(directory)).process_action("alice", "выйти!")
            self.assertEqual(result.status, "EXIT")
            self.assertEqual(result.choices, [])

    def test_public_state_hides_numeric_grace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV17(Path(directory))
            world.process_action("alice", "помочь @bob починить мост")
            state = world.public_state("alice")
            self.assertNotIn("grace", state)
            self.assertIn("world_response", state)

    def test_delayed_consequence_settles_during_normal_play(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV17(Path(directory))
            first = world.process_action(
                "alice", "спасти @bob из опасности и вернуть ему дом"
            )
            world.process_action("alice", "осмотреть последствия")
            world.process_action("alice", "продолжить путь")
            self.assertTrue(world.memory.load_trace(first.trace_id or "").settled)

    def test_chronicle_record_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV17(Path(directory))
            world.process_action("alice", "осмотреться")
            world.process_action("alice", "помочь @bob починить мост")
            valid, count, error = world.verify_chronicle_records()
            self.assertTrue(valid)
            self.assertGreater(count, 0)
            self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
