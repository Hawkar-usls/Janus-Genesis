from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_1 import MEMORY_LIMIT
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187


class GenesisV1871RememberingOtherTests(unittest.TestCase):
    def test_primary_runtime_includes_remembering_other_or_later(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.7")

    def test_repeated_offer_is_contextually_refused_and_remembered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("remember-the-instrument")
            handle = world.public_state("messenger")["free_other_handles"][0]
            action = f"предложить @{handle} вместе изменить незавершённый инструмент"

            world.process_action("messenger", action)
            second = world.process_action("messenger", action)
            actor = world.free_other_state("messenger")["profile"]["others"][handle]

            self.assertEqual(second.status, "OTHER_REFUSED")
            self.assertIn("повторилось раньше", second.narrative)
            self.assertIn("инструмент", second.narrative)
            self.assertGreaterEqual(len(actor["dialogue_memory"]), 2)
            self.assertEqual(actor["dialogue_memory"][-1]["topic"], "инструмент")
            self.assertTrue(actor["dialogue_memory"][-1]["reason"])
            self.assertFalse(actor["dialogue_memory"][-1]["player_controlled_response"])

    def test_dialogue_memory_is_long_but_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("bounded-long-memory")
            handle = world.public_state("pilgrim")["free_other_handles"][0]

            for index in range(MEMORY_LIMIT + 19):
                world.process_action(
                    "pilgrim",
                    f"предложить @{handle} обсудить инструмент и дорогу, вариант {index}",
                )

            actor = world.free_other_state("pilgrim")["profile"]["others"][handle]
            self.assertEqual(len(actor["dialogue_memory"]), MEMORY_LIMIT)
            self.assertGreater(actor["conversation_topics"]["инструмент"]["count"], MEMORY_LIMIT)
            self.assertTrue(world.verify_free_other_state()[0])

    def test_initiatives_have_actor_cooldown_and_no_immediate_text_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("cooldown-and-variety")
            world.register_free_player("listener")

            for index in range(240):
                world.process_action("listener", f"наблюдать небо без толкования, ход {index}")

            actors = world.free_other_state("listener")["profile"]["others"].values()
            total = 0
            for actor in actors:
                initiatives = [item for item in actor["history"] if item["kind"] == "initiative"]
                total += len(initiatives)
                turns = [int(item["world_turn"]) for item in initiatives]
                self.assertTrue(all(b - a >= 6 for a, b in zip(turns, turns[1:])))
                base_texts = [item["text"].split(" Инициатива", 1)[0] for item in initiatives]
                self.assertEqual(len(base_texts), len(set(base_texts)))
            self.assertGreater(total, 0)

    def test_return_remembers_why_the_other_left(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("departure-has-memory")
            world.register_free_player("witness")

            found = None
            for index in range(600):
                world.process_action("witness", f"продолжить наблюдение собственной дороги {index}")
                actors = world.free_other_state("witness")["profile"]["others"].values()
                found = next((actor for actor in actors if actor["returns"] > 0), None)
                if found:
                    break

            self.assertIsNotNone(found)
            assert found is not None
            self.assertTrue(found["departure_context"])
            self.assertTrue(found["return_context"])
            returns = [item for item in found["history"] if item["kind"] == "return"]
            self.assertTrue(returns)
            self.assertIn(found["departure_context"], returns[-1]["text"])

    def test_old_v18_7_profile_is_upgraded_without_losing_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            world = PlayableGenesisV187(root)
            world.set_free_other_seed_for_testing("migration-preserves-life")
            handle = world.public_state("legacy")["free_other_handles"][0]
            world.process_action("legacy", f"предложить @{handle} поговорить о дороге")

            store_path = root / "free_other_v18_7.json"
            store = json.loads(store_path.read_text(encoding="utf-8"))
            actor = store["players"]["legacy"]["others"][handle]
            old_history = list(actor["history"])
            for key in (
                "dialogue_memory",
                "conversation_topics",
                "initiative_cooldown_until",
                "recent_initiative_fingerprints",
                "memory_contract_version",
                "departure_context",
                "return_context",
                "voice_contract",
            ):
                actor.pop(key, None)
            store["players"]["legacy"].pop("dialogue_contract_version", None)
            store["players"]["legacy"].pop("voice_contract_version", None)
            store_path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            restored = PlayableGenesisV187(root)
            upgraded = restored.free_other_state("legacy")["profile"]["others"][handle]
            self.assertEqual(upgraded["history"], old_history)
            self.assertEqual(upgraded["memory_contract_version"], "18.7.1")
            self.assertEqual(upgraded["voice_contract"], "gender_neutral_ru_v1")
            self.assertIn("dialogue_memory", upgraded)
            self.assertTrue(restored.verify_free_other_state()[0])


if __name__ == "__main__":
    unittest.main()
