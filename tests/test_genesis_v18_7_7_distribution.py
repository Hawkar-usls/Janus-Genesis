from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


class GenesisV1877DistributionTests(unittest.TestCase):
    @staticmethod
    def _set_good(world: PlayableGenesisV187, player_id: str, count: int) -> None:
        player = world.memory.load_player(player_id)
        player.good_count = count
        world.memory.save_player(player)

    def test_good_player_receives_more_ordinary_yes_than_no(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("good-yes-distribution-v18.7.7")
            player_id = "known-good-neighbor"
            self._set_good(world, player_id, 18)
            profile = world.register_free_player(player_id)
            handle = next(iter(profile["others"]))
            counts: Counter[str] = Counter()

            for index in range(240):
                decision = world.preflight_free_other_action(
                    player_id,
                    f"поговорить с @{handle} и вместе починить обычную полку, вариант {index}",
                )
                self.assertIsNotNone(decision)
                counts[decision["decision"]] += 1

            self.assertGreater(counts["accepted"], counts["refused"], counts)
            self.assertGreater(counts["accepted"], 120, counts)

    def test_one_bound_proof_cannot_register_several_reader_masks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            first = world.register_witness_voice(
                "reader-one",
                proof="authenticated-reference-subject-42",
                consent=True,
            )
            self.assertEqual(first["verification_status"], "reference_proof_bound")
            self.assertFalse(first["real_world_identity_claimed"])
            with self.assertRaisesRegex(ValueError, "one bound proof"):
                world.register_witness_voice(
                    "reader-two",
                    proof="authenticated-reference-subject-42",
                    consent=True,
                )


if __name__ == "__main__":
    unittest.main()
