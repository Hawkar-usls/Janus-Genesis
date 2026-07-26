from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v17 import JanusGenesisV17, Realm


class GenesisV17Tests(unittest.TestCase):
    def test_destructive_choice_severs_without_touching_utopia(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV17(Path(directory))
            result = world.process_action("alice", "сломать чужой дом")
            self.assertEqual(result.status, "SEVERED")
            self.assertEqual(result.realm, Realm.OTHER_FACE)
            self.assertIsNotNone(result.branch_id)

    def test_helping_another_is_more_powerful_than_helping_self(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV17(Path(directory))
            self_result = world.perform_good(
                "alice",
                "починить собственный фонарь",
                beneficiary_id="alice",
                utility=0.8,
                need=0.8,
                durability=0.8,
                sacrifice=0.5,
                novelty=1.0,
            )
            other_result = world.perform_good(
                "bob",
                "подарить фонарь голодному страннику",
                beneficiary_id="carol",
                utility=0.8,
                need=0.8,
                durability=0.8,
                sacrifice=0.5,
                novelty=1.0,
            )
            self.assertIsNotNone(self_result.trace_id)
            self.assertIsNotNone(other_result.trace_id)
            alice = world.memory.load_player("alice")
            bob = world.memory.load_player("bob")
            self.assertGreater(bob.grace, alice.grace)

    def test_repeated_pair_exchange_decays_and_flags_abuse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV17(Path(directory))
            awards = []
            for _ in range(5):
                world.perform_good(
                    "alice",
                    "передать тот же камень",
                    beneficiary_id="bob",
                    utility=0.2,
                    need=0.1,
                    durability=0.1,
                    sacrifice=0.0,
                    novelty=0.1,
                )
                awards.append(world.memory.load_player("alice").grace)
            increments = [awards[0]] + [awards[i] - awards[i - 1] for i in range(1, len(awards))]
            self.assertLess(increments[-1], increments[0])

    def test_delayed_good_consequence_can_propagate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV17(Path(directory))
            result = world.perform_good(
                "alice",
                "спасти странника из Второго Лика",
                beneficiary_id="bob",
                utility=1.0,
                need=1.0,
                durability=1.0,
                sacrifice=0.9,
                novelty=1.0,
                chain_depth=1,
            )
            before = world.memory.load_player("alice").grace
            awarded = world.settle_consequence(result.trace_id or "", realized_impact=1.0, propagated_good=2.0)
            after = world.memory.load_player("alice").grace
            self.assertGreater(awarded, 0.0)
            self.assertGreater(after, before)

    def test_grace_is_never_exposed_in_world_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV17(Path(directory))
            result = world.process_action("alice", "осмотреться")
            self.assertIsNone(result.visible_grace)

    def test_memory_can_forget_name_but_keep_residual_trust(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV17(Path(directory))
            relation = world.remember_encounter("alice", "bob", name="Boris", trust_delta=0.7, anchor="старое письмо")
            relation.decay(1000)
            self.assertIsNone(relation.known_name)
            self.assertGreater(relation.residual_trust, 0.0)

    def test_wish_for_another_has_lower_effective_cost(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusGenesisV17(Path(directory))
            player = world.memory.load_player("alice")
            player.grace = 75.0
            world.memory.save_player(player)
            self_wish = world.cast_wish("alice", "создать себе сад", cost=100.0, for_other=False)
            other_wish = world.cast_wish("alice", "вернуть сад деревне", cost=100.0, for_other=True)
            self.assertFalse(self_wish.wish_manifested)
            self.assertTrue(other_wish.wish_manifested)


if __name__ == "__main__":
    unittest.main()
