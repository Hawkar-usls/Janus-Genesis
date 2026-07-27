from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_6_playable import PlayableGenesisV186


class GenesisV186BloomOfPossibilityTests(unittest.TestCase):
    def test_bridge_evidence_blooms_real_options_without_moral_rank(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            result = world.process_action("traveler", "помочь @visitor построить мост")
            state = world.possibility_graph_state("traveler")

            self.assertIn("roads_beyond_bridge", state["profile"]["possibilities"])
            self.assertIn("Исследовать землю за мостом", result.choices)
            self.assertIn("Цветение возможности", result.narrative)
            possibility = next(
                item for item in state["possibilities"]
                if item["payload"]["possibility_id"] == "roads_beyond_bridge"
            )
            self.assertFalse(possibility["payload"]["moral_rank_required"])
            self.assertTrue(possibility["payload"]["not_a_reward"])
            self.assertNotIn("good_count", possibility["payload"])

    def test_distinct_good_evidence_makes_the_world_wider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            world.process_action("traveler", "помочь @visitor построить мост")
            first = world.public_state("traveler")["available_possibilities"]
            world.process_action("traveler", "исцелить @visitor и посадить сад у реки")
            second = world.public_state("traveler")["available_possibilities"]

            self.assertGreater(first, 0)
            self.assertGreater(second, first)
            self.assertIn("Сад исцеления", world.public_state("traveler")["possibility_titles"])

    def test_living_thread_no_longer_removes_every_available_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            world.set_living_threads_seed_for_testing("bloom-keeps-options")
            world.process_action("traveler", "помочь @visitor построить мост")
            result = world.process_action("traveler", "я молчу")

            self.assertIn("Нить мира возникла без выбора из меню", result.narrative)
            self.assertTrue(result.choices)
            self.assertIn("Исследовать землю за мостом", result.choices)

    def test_preserve_name_is_not_misclassified_as_harm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            result = world.process_action(
                "traveler",
                "помочь @ira проститься с умершим и сохранить его имя",
            )
            player = world.memory.load_player("traveler")

            self.assertNotEqual(result.status, "HARM_PENDING")
            self.assertNotEqual(result.status, "HARM_REALIZED")
            self.assertEqual(player.harm_count, 0)
            self.assertGreater(player.good_count, 0)

    def test_confirmed_harm_does_not_permanently_erase_created_possibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            world.process_action("traveler", "помочь @visitor построить мост")
            before = list(world.possibility_graph_state("traveler")["profile"]["possibilities"])

            world.process_action("traveler", "сломать пустую скамейку")
            world.process_action("traveler", "сломать пустую скамейку")
            after_state = world.possibility_graph_state("traveler")

            self.assertEqual(before, after_state["profile"]["possibilities"])
            self.assertFalse(after_state["invariants"]["harm_permanently_erases_possibility"])
            possibility = next(
                item for item in after_state["possibilities"]
                if item["payload"]["possibility_id"] == "roads_beyond_bridge"
            )
            self.assertTrue(possibility["payload"]["reopenable"])

    def test_child_role_receives_child_safe_possibility_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            world.process_action("traveler", "помочь @visitor построить мост")
            world.process_action("traveler", "стать ребёнком")
            result = world.process_action("traveler", "я молчу")

            self.assertIn("Пройти по мосту вместе с хранителем", result.choices)
            self.assertNotIn("Передать право первого прохода другому", result.choices)
            self.assertEqual(world.narrator_state("traveler")["moral_echoes"], [])

    def test_hrain_contract_has_provenance_and_valid_integrity_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            world.process_action("traveler", "помочь @visitor построить мост")
            valid, node_count, edge_count, error = world.verify_possibility_graph()
            graph = world._graph()

            self.assertTrue(valid, error)
            self.assertGreater(node_count, 0)
            self.assertGreater(edge_count, 0)
            self.assertEqual(graph["schema_version"], "HRAIN-GENESIS-GRAPH-v1")
            self.assertEqual(graph["backend"]["kind"], "json_sidecar")
            self.assertFalse(graph["backend"]["canonical_database_connected"])

            required_node = {
                "id", "type", "source", "created_at", "confidence",
                "integrity_hash", "mutable", "payload",
            }
            required_edge = {
                "id", "from", "to", "relation", "evidence", "confidence",
                "created_by", "created_at", "reversible", "integrity_hash", "payload",
            }
            self.assertTrue(all(required_node == set(node) for node in graph["nodes"]))
            self.assertTrue(all(required_edge == set(edge) for edge in graph["edges"]))
            self.assertIn("OBSERVED", {edge["relation"] for edge in graph["edges"]})
            self.assertIn("CAUSED", {edge["relation"] for edge in graph["edges"]})
            self.assertIn("CREATED", {edge["relation"] for edge in graph["edges"]})
            self.assertIn("DEPENDS_ON", {edge["relation"] for edge in graph["edges"]})

    def test_schema_file_and_runtime_sidecar_agree_on_frozen_invariants(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas" / "hrain_genesis_graph_v1.schema.json").read_text(encoding="utf-8"))
        invariant_properties = schema["properties"]["invariants"]["properties"]

        self.assertTrue(invariant_properties["good_is_not_currency"]["const"])
        self.assertFalse(invariant_properties["moral_rank_required"]["const"])
        self.assertTrue(invariant_properties["possibilities_can_be_reopened"]["const"])
        self.assertFalse(invariant_properties["harm_permanently_erases_possibility"]["const"])

    def test_bloom_events_preserve_linked_chronicle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV186(Path(directory))
            world.process_action("traveler", "помочь @visitor построить мост")
            world.process_action("traveler", "исцелить @visitor и посадить сад у реки")
            world.process_action("traveler", "создать музыку и поделиться ею с @visitor")

            valid, count, error = world.verify_chronicle_records()
            self.assertTrue(valid, error)
            self.assertGreater(count, 3)
            self.assertTrue(world.verify_possibility_graph()[0])


if __name__ == "__main__":
    unittest.main()
