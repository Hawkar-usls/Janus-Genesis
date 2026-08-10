from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_cognitive_descent import PlayableGenesisV18719
from genesis_v18_7_19_cognitive_memory import JanusCognitiveMemory


class GenesisV18719CognitiveDescentTests(unittest.TestCase):
    def test_return_opens_a_deeper_layer_without_overriding_genesis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_world = PlayableGenesisV18719(root)
            first = first_world.process_action("traveler", "осмотреть зеркало у порога")
            first_state = first_world.cognitive_state("traveler")

            self.assertEqual(first_state["return_count"], 1)
            self.assertGreater(first_state["depth"], 0.0)
            self.assertIn("впервые замечают твой след", first.narrative)
            self.assertTrue(first_world.verify_chronicle_records()[0])
            self.assertTrue(first_world.verify_cognitive_memory("traveler")["valid"])

            second_world = PlayableGenesisV18719(root)
            second = second_world.process_action("traveler", "вернуться к зеркалу и открыть дверь")
            second_state = second_world.cognitive_state("traveler")

            self.assertEqual(second_state["return_count"], 2)
            self.assertGreater(second_state["depth"], first_state["depth"])
            self.assertIn("возвращение №2", second.narrative)
            self.assertEqual(second_state["authority"], "derived_sidecar_only")
            self.assertFalse(second_state["diagnostic_claim"])

    def test_recurring_symbol_becomes_memory_not_a_diagnosis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV18719(Path(directory))
            world.process_action("witness", "посмотреть в зеркало")
            result = world.process_action("witness", "оставить у зеркала маленький свет")
            state = world.cognitive_state("witness")
            mirror = next(item for item in state["themes"] if item["theme"] == "зеркало")

            self.assertEqual(mirror["count"], 2)
            self.assertIn("Символ «зеркало» вернулся", result.narrative)
            self.assertNotIn("психотип", result.narrative.lower())
            self.assertNotIn("диагноз", result.narrative.lower())

    def test_disclosed_api_keys_are_redacted_before_memory_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = JanusCognitiveMemory(Path(directory))
            session = memory.new_session_id()
            exposed = "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            memory.record_turn(
                "keeper",
                session,
                f"я нашёл старый ключ {exposed} возле двери",
                "OBSERVED",
                "Ключ не используется.",
            )
            episode = memory.recent_episodes("keeper", 1)[0]

            self.assertNotIn(exposed, episode["action_excerpt"])
            self.assertIn("[REDACTED_GOOGLE_API_KEY]", episode["action_excerpt"])

    def test_sqlite_uses_wal_and_episode_chain_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = JanusCognitiveMemory(Path(directory))
            session = memory.new_session_id()
            memory.record_turn("audit", session, "открыть дверь", "OPEN", "Дверь открыта.")
            memory.record_turn("audit", session, "перейти мост", "CROSS", "Мост пройден.")

            self.assertEqual(memory.journal_mode(), "wal")
            self.assertTrue(memory.verify("audit")["valid"])

            with sqlite3.connect(memory.db_path) as connection:
                connection.execute(
                    "UPDATE episodes SET action_excerpt = ? WHERE player_id = ? AND turn_index = 1",
                    ("подменённая память", "audit"),
                )
                connection.commit()

            verification = memory.verify("audit")
            self.assertFalse(verification["valid"])
            self.assertIn("episode hash mismatch", verification["error"])

    def test_sidecar_failure_cannot_block_authoritative_gameplay(self) -> None:
        class BrokenMemory:
            @staticmethod
            def record_turn(*args, **kwargs):
                raise RuntimeError("sidecar unavailable")

        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV18719(Path(directory))
            world.cognitive_memory = BrokenMemory()  # type: ignore[assignment]
            result = world.process_action("free", "осмотреться")

            self.assertTrue(result.status)
            self.assertIn("RuntimeError", world._cognitive_last_error or "")
            self.assertTrue(world.verify_chronicle_records()[0])

    def test_public_state_exposes_only_safe_cognitive_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV18719(Path(directory))
            world.process_action("public", "помочь построить мост к саду")
            payload = world.public_state("public")["cognitive_descent"]

            self.assertEqual(payload["version"], "18.7.19")
            self.assertEqual(payload["authority"], "derived_sidecar_only")
            self.assertIn(payload["layer"], {"Порог", "Эхо", "Сон", "Лабиринт", "Разлом", "Чистая глубина"})
            self.assertNotIn("action_excerpt", payload)


if __name__ == "__main__":
    unittest.main()
