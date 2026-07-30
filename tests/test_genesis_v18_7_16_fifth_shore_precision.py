from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


class FifthShoreRestHumorPrecisionTests(unittest.TestCase):
    def test_rest_and_humor_receive_a_distinct_non_repair_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            for player_id in ("king", "iori", "resting"):
                world.register_player(player_id, display_name=player_id)
            world.enter_royal_mercy_face_ii(
                "king",
                arrival_date_local="2026-07-30",
                title="Царь Милости",
            )
            world.found_inner_genesis_in_face_ii(
                "king",
                founded_date_local="2026-07-30",
            )
            world.register_face_ii_auteur_candidate(
                "iori",
                display_name="Иори Кай, Автор Нулевого Моста",
                originality=0.98,
                player_care=0.93,
                ambiguity_tolerance=0.99,
                collaboration=0.88,
                consent_respect=0.97,
                celebrity_hunger=0.18,
                pitch="позволить многим финалам жить одновременно",
            )
            world.invite_best_face_ii_auteur("king")
            world.decide_auteur_collaboration(
                "iori",
                accepts=True,
                counterproposal="Сохранить право игрока выйти и право мира иметь много финалов.",
                chosen_title="Пятый Берег",
            )
            world.coauthor_fifth_shore("king", "iori")
            world.publish_fifth_shore_capsule(
                "iori",
                "bridge-station",
                accepted=True,
            )
            outcome = world.play_fifth_shore_episode(
                "resting",
                "bridge-station",
                participates=True,
                rehearsal_kind="вернуть безопасный смех",
                commits_to_external_action=False,
                chooses_rest_or_humor=True,
            )
            self.assertEqual(
                outcome["status"],
                "FIFTH_SHORE_REST_HUMOR_RESTORED",
            )
            self.assertFalse(outcome["repair_claimed"])
            self.assertTrue(outcome["rest_humor_is_valid_good"])
            state = world.inner_genesis_state()
            matching = [
                event
                for event in state["events"]
                if event.get("kind")
                == "FIFTH_SHORE_REST_HUMOR_OUTCOME_REFINED"
            ]
            self.assertEqual(len(matching), 1)


if __name__ == "__main__":
    unittest.main()
