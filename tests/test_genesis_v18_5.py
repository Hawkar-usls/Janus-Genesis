from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_5_playable import PlayableGenesisV185


class GenesisV185LivingThreadsTests(unittest.TestCase):
    ACTIONS = [
        "осмотреться",
        "идти по дороге",
        "помочь @visitor починить фонарь",
        "промолчать",
        "послушать дальний звон",
        "продолжить путь",
        "посмотреть на реку",
        "ничего не говорить",
        "вернуться к старому мосту",
        "ждать молча",
        "осмотреть окно",
        "продолжить жизнь",
    ]

    def _run_life(self, directory: str, seed: str) -> tuple[PlayableGenesisV185, list[tuple[str, str]]]:
        world = PlayableGenesisV185(Path(directory))
        world.set_living_threads_seed_for_testing(seed)
        surfaced: list[tuple[str, str]] = []
        for action in self.ACTIONS:
            result = world.process_action("traveler", action)
            if "Нить мира возникла без выбора из меню" in result.narrative:
                surfaced.append((result.status, result.narrative))
        return world, surfaced

    def test_same_seed_and_actions_replay_the_same_life(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            world_a, surfaced_a = self._run_life(first, "replay-seed")
            world_b, surfaced_b = self._run_life(second, "replay-seed")
            self.assertEqual(surfaced_a, surfaced_b)
            self.assertEqual(
                world_a.living_threads_state("traveler")["surfaced"],
                world_b.living_threads_state("traveler")["surfaced"],
            )

    def test_different_world_seed_changes_the_unscripted_stream(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            world_a, _ = self._run_life(first, "world-a")
            world_b, _ = self._run_life(second, "world-b")
            self.assertNotEqual(
                world_a.living_threads_state("traveler")["surfaced"],
                world_b.living_threads_state("traveler")["surfaced"],
            )

    def test_event_surfaces_without_being_selected_from_the_choice_menu(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV185(Path(directory))
            world.set_living_threads_seed_for_testing("outside-menu")
            surfaced = None
            for action in self.ACTIONS:
                result = world.process_action("traveler", action)
                if "Нить мира возникла без выбора из меню" in result.narrative:
                    surfaced = result
                    break
            self.assertIsNotNone(surfaced)
            self.assertEqual(surfaced.choices, [])
            event = world.living_threads_state("traveler")["surfaced"][-1]
            self.assertFalse(event["created_from_visible_menu"])
            self.assertFalse(event["random_victim_created"])

    def test_residents_continue_their_own_fates_during_unrelated_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV185(Path(directory))
            world.set_living_threads_seed_for_testing("independent-residents")
            for index in range(24):
                world.process_action("traveler", f"осмотреть камень {index}")
            residents = world.living_threads_state("traveler")["residents"]
            self.assertTrue(any(item["progress"] > 0 for item in residents.values()))
            self.assertTrue(all(not item["player_controlled"] for item in residents.values()))
            self.assertTrue(all(not item["autonomous_person_claim"] for item in residents.values()))
            self.assertTrue(all(item["fate_is_not_player_reward"] for item in residents.values()))

    def test_a_symbol_appears_and_later_returns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV185(Path(directory))
            world.set_living_threads_seed_for_testing("returning-symbol")
            for index in range(30):
                world.process_action("traveler", f"пройти ещё один шаг {index}")
            state = world.living_threads_state("traveler")
            self.assertTrue(state["symbols"])
            self.assertTrue(any(symbol["seen"] >= 2 for symbol in state["symbols"].values()))
            symbol_events = [event for event in state["surfaced"] if event["kind"] == "symbol"]
            self.assertGreaterEqual(len(symbol_events), 2)

    def test_silence_is_allowed_to_remain_silence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV185(Path(directory))
            world.set_living_threads_seed_for_testing("silence")
            result = world.process_action("traveler", "я молчу")
            self.assertIn("Нить мира возникла без выбора из меню", result.narrative)
            self.assertIn("Молчание осталось настоящим действием", result.narrative)
            event = world.living_threads_state("traveler")["surfaced"][-1]
            self.assertEqual(event["kind"], "silence")
            self.assertFalse(event["predictive_guilt"])

    def test_child_role_receives_only_child_safe_unscripted_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV185(Path(directory))
            world.set_living_threads_seed_for_testing("child-safe")
            world.process_action("child", "стать ребёнком")
            for _ in range(5):
                world.process_action("child", "молчать")
            state = world.living_threads_state("child")
            self.assertTrue(state["surfaced"])
            self.assertTrue(all(event["child_safe"] for event in state["surfaced"]))
            self.assertTrue(all(not event["random_victim_created"] for event in state["surfaced"]))
            self.assertEqual(world.narrator_state("child")["moral_echoes"], [])

    def test_unscripted_events_do_not_change_moral_state_or_core_routing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV185(Path(directory))
            world.set_living_threads_seed_for_testing("moral-invariant")
            before = world.memory.load_player("traveler")
            snapshot = (before.good_count, before.harm_count, before.light, before.trust, before.realm, before.branch_id)
            world.process_action("traveler", "я молчу")
            after = world.memory.load_player("traveler")
            self.assertEqual(snapshot, (after.good_count, after.harm_count, after.light, after.trust, after.realm, after.branch_id))
            invariants = world.living_threads_state("traveler")["invariants"]
            self.assertFalse(invariants["changes_god_mode_law"])
            self.assertFalse(invariants["changes_moral_routing"])
            self.assertFalse(invariants["changes_chronicle_verifier"])
            self.assertFalse(invariants["random_victim_creation"])

    def test_living_thread_events_preserve_the_linked_chronicle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV185(Path(directory))
            world.set_living_threads_seed_for_testing("chronicle")
            for action in self.ACTIONS:
                world.process_action("traveler", action)
            valid, count, error = world.verify_chronicle_records()
            self.assertTrue(valid, error)
            self.assertGreater(count, len(self.ACTIONS))
            self.assertGreater(len(world.living_threads_state("traveler")["surfaced"]), 0)


if __name__ == "__main__":
    unittest.main()
