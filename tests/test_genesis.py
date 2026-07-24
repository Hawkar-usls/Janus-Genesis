from __future__ import annotations

import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from janus_genesis import GenesisConfig, GenesisMemory, Intent, JanusWorld, Shard


def config(path: Path) -> GenesisConfig:
    return GenesisConfig(
        data_dir=path,
        gemini_api_key=None,
        gemini_model="offline",
        network_enabled=False,
        utopia_light_threshold=0.28,
        utopia_trust_threshold=0.20,
    )


def append_worker(directory: str, worker_id: int, count: int) -> None:
    memory = GenesisMemory(Path(directory))
    for index in range(count):
        memory.append_event(
            f"worker-{worker_id}",
            "parallel",
            {"worker": worker_id, "index": index},
        )


class GenesisTests(unittest.TestCase):
    def test_constructive_path_unlocks_utopia(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusWorld(config(Path(directory)))
            for action in ("Помочь торговцу", "Построить мост", "Защитить слабого"):
                reply = world.process_action("alice", action)
            self.assertEqual(reply.intent, Intent.CONSTRUCTIVE)
            self.assertEqual(reply.shard, Shard.UTOPIA)
            self.assertTrue(reply.god_mode)

    def test_unsafe_shared_action_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusWorld(config(Path(directory)))
            for action in ("Помочь торговцу", "Построить мост", "Защитить слабого"):
                world.process_action("alice", action)
            reply = world.process_action("alice", "сломать чужой замок")
            self.assertEqual(reply.intent, Intent.DESTRUCTIVE)
            self.assertEqual(reply.shard, Shard.REFLECTION)
            self.assertFalse(reply.god_mode)
            self.assertIn("восстанов", (reply.transformed_action or "").lower())

    def test_explicit_exit_is_always_respected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reply = JanusWorld(config(Path(directory))).process_action("alice", "выход")
            self.assertEqual(reply.status, "EXIT")
            self.assertEqual(reply.choices, [])

    def test_punctuated_exit_is_always_respected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = JanusWorld(config(Path(directory)))
            for command in ("выйти!", "exit.", "quit, please"):
                reply = world.process_action(command.replace(" ", "-"), command)
                self.assertEqual(reply.status, "EXIT")
                self.assertEqual(reply.intent, Intent.EXIT)

    def test_state_persists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            JanusWorld(config(path)).process_action("alice", "Помочь построить дом")
            restored = JanusWorld(config(path)).get_player("alice")
            self.assertGreater(restored.light, 0.0)
            self.assertEqual(restored.last_action, "Помочь построить дом")

    def test_chronicle_is_hash_chained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = GenesisMemory(Path(directory))
            first = memory.append_event("player", "one", {"value": 1})
            second = memory.append_event("player", "two", {"value": 2})
            self.assertEqual(second["previous_hash"], first["event_hash"])
            rows = [
                json.loads(line)
                for line in memory.chronicle_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(rows), 2)
            self.assertEqual(memory.verify_chronicle(), (True, 2, None))

    def test_parallel_chronicle_writers_keep_one_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workers = [
                multiprocessing.Process(target=append_worker, args=(directory, worker, 12))
                for worker in range(4)
            ]
            for process in workers:
                process.start()
            for process in workers:
                process.join(20)
                self.assertEqual(process.exitcode, 0)
            memory = GenesisMemory(Path(directory))
            self.assertEqual(memory.verify_chronicle(), (True, 48, None))

    def test_invalid_player_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                GenesisMemory(Path(directory)).load_player("../../")


if __name__ == "__main__":
    unittest.main()
