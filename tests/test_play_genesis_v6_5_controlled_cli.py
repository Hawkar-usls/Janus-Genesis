from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import play_genesis
from genesis_v18_7_playable import PlayableGenesisV187


class ControlledOneShotCLITests(unittest.TestCase):
    @staticmethod
    def run_main(argv):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = play_genesis.main(argv)
        return code, json.loads(stream.getvalue())

    def test_same_explicit_request_replays_without_second_world_tick(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = [
                "--data-dir", str(root),
                "--player", "mira",
                "--action", "создать тихий сад",
                "--request-id", "CLI-REQ-1",
            ]
            before = PlayableGenesisV187(root).memory.load_player("mira").tick
            code1, first = self.run_main(base)
            after_first = PlayableGenesisV187(root).memory.load_player("mira").tick
            code2, second = self.run_main(base)
            after_second = PlayableGenesisV187(root).memory.load_player("mira").tick

            self.assertEqual(code1, 0)
            self.assertEqual(code2, 0)
            self.assertGreater(after_first, before)
            self.assertEqual(after_second, after_first)
            self.assertEqual(first["_janus_control"]["request_id"], "CLI-REQ-1")
            self.assertEqual(second["_janus_control"]["request_state"]["state"], "SETTLED")
            self.assertEqual(first["status"], second["status"])
            self.assertEqual(first["narrative"], second["narrative"])

    def test_same_request_different_action_returns_control_block_without_second_world_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            common = ["--data-dir", str(root), "--player", "mira"]
            code1, _ = self.run_main(
                common + ["--action", "создать сад", "--request-id", "CLI-CONFLICT"]
            )
            tick = PlayableGenesisV187(root).memory.load_player("mira").tick
            code2, blocked = self.run_main(
                common + ["--action", "создать мост", "--request-id", "CLI-CONFLICT"]
            )
            self.assertEqual(code1, 0)
            self.assertEqual(code2, 2)
            self.assertEqual(blocked["status"], "JANUS_CONTROL_BLOCKED")
            self.assertEqual(blocked["error_type"], "PortableRequestConflict")
            self.assertEqual(PlayableGenesisV187(root).memory.load_player("mira").tick, tick)

    def test_implicit_request_id_is_returned_and_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            code, payload = self.run_main(
                [
                    "--data-dir", str(root),
                    "--player", "mira",
                    "--action", "создать музыку",
                ]
            )
            self.assertEqual(code, 0)
            request_id = payload["_janus_control"]["request_id"]
            self.assertTrue(request_id.startswith("ACTION-"))
            self.assertEqual(payload["_janus_control"]["request_state"]["state"], "SETTLED")

            state_code, state = self.run_main(
                [
                    "--data-dir", str(root),
                    "--request-state", request_id,
                ]
            )
            self.assertEqual(state_code, 0)
            self.assertEqual(state["request_id"], request_id)
            self.assertEqual(state["state"], "SETTLED")
            self.assertTrue(state["full_result_receipt_persisted"])

    def test_same_text_with_different_request_ids_is_two_intents(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            common = [
                "--data-dir", str(root),
                "--player", "mira",
                "--action", "создать музыку",
            ]
            self.run_main(common + ["--request-id", "INTENT-A"])
            tick_a = PlayableGenesisV187(root).memory.load_player("mira").tick
            self.run_main(common + ["--request-id", "INTENT-B"])
            tick_b = PlayableGenesisV187(root).memory.load_player("mira").tick
            self.assertGreater(tick_b, tick_a)


if __name__ == "__main__":
    unittest.main()
