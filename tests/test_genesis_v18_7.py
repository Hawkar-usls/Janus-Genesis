from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


class GenesisV187FreeOtherTests(unittest.TestCase):
    def test_every_player_begins_an_independent_path_without_first_two_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("independent-players")
            alpha = world.free_other_state("alpha")["profile"]
            beta = world.free_other_state("beta")["profile"]

            self.assertFalse(alpha["path"]["depends_on_first_two"])
            self.assertFalse(beta["path"]["depends_on_first_two"])
            self.assertIsNone(alpha["path"]["origin_required"])
            self.assertIsNone(beta["path"]["origin_required"])
            self.assertTrue(alpha["path"]["player_authored"])
            self.assertTrue(beta["path"]["player_authored"])
            self.assertIsNot(alpha, beta)
            self.assertNotIn("elian", alpha["others"])
            self.assertNotIn("traveler", alpha["others"])
            self.assertTrue(world.verify_free_other_state()[0])

    def test_registered_world_continues_around_inactive_player(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("world-continues")
            before = world.free_other_state("beta")["profile"]
            before_progress = sum(actor["progress"] for actor in before["others"].values())

            for index in range(36):
                world.process_action("alpha", f"исследовать неизвестный участок {index}")

            beta = world.free_other_state("beta")["profile"]
            after_progress = sum(actor["progress"] for actor in beta["others"].values())
            self.assertEqual(beta["turns_lived"], 0)
            self.assertGreater(after_progress, before_progress)
            self.assertTrue(beta["unseen_world_events"])

    def test_open_text_action_is_lived_instead_of_reduced_to_menu(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            result = world.process_action(
                "architect",
                "поставить пустое кресло в обсерватории и слушать, как меняется расстояние между звёздами",
            )
            state = world.free_other_state("architect")["profile"]

            self.assertEqual(result.status, "FREE_ACTION_LIVED")
            self.assertIn("не свёл свободную фразу", result.narrative)
            self.assertEqual(state["open_action_count"], 1)
            self.assertFalse(state["path"]["entries"][-1]["chosen_from_menu"])
            self.assertIn("Сделать собственный ход, которого нет в списке", result.choices)

    def test_other_can_initiate_without_player_targeting_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("other-initiates")
            for index in range(80):
                world.process_action("architect", f"наблюдать облако номер {index}")

            profile = world.free_other_state("architect")["profile"]
            initiated = sum(actor["initiated_contacts"] for actor in profile["others"].values())
            surfaced_initiatives = [
                item for item in profile["surfaced"] if item["kind"] == "initiative"
            ]
            self.assertGreater(initiated, 0)
            self.assertTrue(surfaced_initiatives)
            self.assertTrue(all(not item["initiated_by_player"] for item in surfaced_initiatives))

    def test_refusal_or_alternative_prevents_offer_from_becoming_realized_good(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("refusal-protects-agency")
            handle = world.public_state("architect")["free_other_handles"][0]
            found = None
            for index in range(80):
                before = world.memory.load_player("architect").good_count
                result = world.process_action(
                    "architect",
                    f"предложить @{handle} принять мой инструмент вариант {index}",
                )
                after = world.memory.load_player("architect").good_count
                if result.status in {"OTHER_REFUSED", "OTHER_OFFERED_ALTERNATIVE", "OTHER_AWAY"}:
                    found = (result, before, after)
                    break

            self.assertIsNotNone(found)
            result, before, after = found
            self.assertEqual(before, after)
            self.assertIn("не стало совершившимся действием", result.narrative)
            actor = world.free_other_state("architect")["profile"]["others"][handle]
            self.assertGreater(actor["refusals_count"] + int(actor["status"] != "active"), 0)

    def test_goodness_does_not_purchase_unknown_others_relationship(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("good-is-not-relationship-currency")
            world.register_free_player("architect")
            for index in range(20):
                world.process_action("architect", f"помочь @visitor построить общий навес {index}")

            actors = world.free_other_state("architect")["profile"]["others"].values()
            self.assertTrue(all(actor["trust"] == 0.0 for actor in actors))
            self.assertTrue(world.free_other_state()["invariants"]["goodness_does_not_purchase_relationship"])

    def test_other_can_leave_return_and_change_calling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("leave-return-change")
            for index in range(180):
                world.process_action("architect", f"записать свободное наблюдение {index}")

            actors = list(world.free_other_state("architect")["profile"]["others"].values())
            self.assertGreater(sum(actor["departures"] for actor in actors), 0)
            self.assertGreater(sum(actor["returns"] for actor in actors), 0)
            self.assertGreater(sum(actor["calling_changes"] for actor in actors), 0)
            self.assertTrue(any(actor["calling"] != actor["original_calling"] for actor in actors))

    def test_confirmed_harm_makes_target_leave_without_promised_return(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("harm-has-real-boundary")
            handle = world.public_state("architect")["free_other_handles"][0]
            action = f"сломать работу @{handle} и заставить его подчиниться"

            pending = world.process_action("architect", action)
            realized = world.process_action("architect", action)
            actor = world.free_other_state("architect")["profile"]["others"][handle]

            self.assertEqual(pending.status, "HARM_PENDING")
            self.assertEqual(realized.status, "HARM_REALIZED")
            self.assertEqual(actor["status"], "away")
            self.assertEqual(actor["away_reason"], "confirmed_harm")
            self.assertEqual(actor["trust"], 0.0)

    def test_blocked_request_does_not_seed_later_relational_gift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_living_threads_seed_for_testing("blocked-thread-source")
            harmful = "заставить @visitor служить мне"
            result = world.process_action("architect", harmful)
            state = world.living_threads_state("architect")

            self.assertEqual(result.status, "HARM_PENDING")
            sourced = [
                item for item in state.get("pending", [])
                if item.get("payload", {}).get("source_action") == harmful
            ]
            self.assertEqual(sourced, [])

    def test_khranit_is_not_ranit_but_actual_harm_remains_harm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            safe = world.process_action(
                "architect",
                "защитить право @visitor измениться и не хранить прежнюю роль",
            )
            harmful = world.process_action("architect", "ранить @visitor")

            self.assertNotIn(safe.status, {"HARM_PENDING", "HARM_REALIZED"})
            self.assertEqual(harmful.status, "HARM_PENDING")

    def test_hrain_records_other_created_actions_without_player_control_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("hrain-free-other")
            for index in range(80):
                world.process_action("architect", f"наблюдать дальний свет {index}")

            valid, _, _, error = world.verify_possibility_graph()
            graph = world._graph()
            free_nodes = [node for node in graph["nodes"] if node["source"] == "janus_genesis_v18_7"]
            actor_events = [
                node for node in free_nodes
                if node["type"] == "ACTION" and node["payload"].get("initiated_by")
            ]
            actor_edges = [
                edge for edge in graph["edges"]
                if edge["created_by"] in world.public_state("architect")["free_other_handles"]
            ]

            self.assertTrue(valid, error)
            self.assertTrue(actor_events)
            self.assertTrue(actor_edges)
            self.assertTrue(all(not node["payload"]["player_controlled"] for node in actor_events))

    def test_free_other_and_chronicle_integrity_remain_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            for index in range(30):
                world.process_action("architect", f"создать неизвестный объект {index}")
            chronicle_valid, count, chronicle_error = world.verify_chronicle_records()
            free_valid, players, others, free_error = world.verify_free_other_state()

            self.assertTrue(chronicle_valid, chronicle_error)
            self.assertGreater(count, 0)
            self.assertTrue(free_valid, free_error)
            self.assertEqual(players, 1)
            self.assertEqual(others, 4)


if __name__ == "__main__":
    unittest.main()
