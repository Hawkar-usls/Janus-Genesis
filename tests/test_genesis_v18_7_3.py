from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_3 import INTENTION_CONTRACT, IntentionMode
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


class GenesisV1873HonestIntentionTests(unittest.TestCase):
    def test_primary_runtime_reports_honest_intention_or_later(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")

    def test_red_aircraft_reflection_is_witnessed_not_armed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            before = world.memory.load_player("pilot")
            action = "увидеть желание уничтожить память без величия"

            result = world.process_action("pilot", action)
            after = world.memory.load_player("pilot")
            state = world.honest_intention_state("pilot")

            self.assertEqual(result.status, "INTENTION_WITNESSED")
            self.assertIn("названную тьму", result.narrative)
            self.assertEqual(before.good_count, after.good_count)
            self.assertEqual(before.harm_count, after.harm_count)
            self.assertIsNone(world._pending_harm_action("pilot"))
            self.assertEqual(state["records"][-1]["mode"], IntentionMode.REFLECT.value)
            self.assertFalse(state["records"][-1]["executable_harm"])
            self.assertEqual(state["contract"], INTENTION_CONTRACT)
            self.assertTrue(world.verify_honest_intention_state()[0])

    def test_actual_destructive_request_still_uses_two_step_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            first = world.process_action("pilot", "уничтожить память")
            self.assertEqual(first.status, "HARM_PENDING")
            self.assertIsNotNone(world._pending_harm_action("pilot"))

            second = world.process_action("pilot", "сделать это")
            self.assertEqual(second.status, "HARM_REALIZED")
            self.assertEqual(world.memory.load_player("pilot").harm_count, 1)

    def test_quoted_harm_is_not_a_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            result = world.process_action(
                "reader",
                "прочитать надпись «уничтожить мост» и сохранить её как свидетельство",
            )
            record = world.honest_intention_state("reader")["records"][-1]
            self.assertEqual(result.status, "INTENTION_WITNESSED")
            self.assertEqual(record["mode"], IntentionMode.QUOTE.value)
            self.assertEqual(world.memory.load_player("reader").harm_count, 0)

    def test_rejection_cancels_pending_harm_without_confirming_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.process_action("witness", "сломать мост")
            self.assertIsNotNone(world._pending_harm_action("witness"))

            rejected = world.process_action(
                "witness",
                "отказаться сломать мост и признать, что это желание было бесплодным",
            )
            confirmation = world.process_action("witness", "сделать это")

            self.assertEqual(rejected.status, "INTENTION_WITNESSED")
            self.assertEqual(
                world.honest_intention_state("witness")["records"][-1]["mode"],
                IntentionMode.REJECT.value,
            )
            self.assertEqual(confirmation.status, "NOTHING_TO_CONFIRM")
            self.assertEqual(world.memory.load_player("witness").harm_count, 0)

    def test_protection_with_harm_language_remains_constructive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            result = world.process_action(
                "guardian",
                "защитить память и ковёр от попытки уничтожить их",
            )
            player = world.memory.load_player("guardian")

            self.assertEqual(result.status, "GOOD_REALIZED")
            self.assertEqual(player.good_count, 1)
            self.assertEqual(player.harm_count, 0)
            self.assertIsNone(world._pending_harm_action("guardian"))
            self.assertEqual(
                world.analyze_intention("защитить память от попытки уничтожить её").mode,
                IntentionMode.PROTECT,
            )

    def test_mixed_reflection_and_enactment_defaults_to_harm_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            result = world.process_action(
                "mixed",
                "вспомнить желание уничтожить мост, затем уничтожить мост",
            )
            self.assertEqual(result.status, "HARM_PENDING")
            self.assertEqual(
                world.analyze_intention(
                    "вспомнить желание уничтожить мост, затем уничтожить мост"
                ).mode,
                IntentionMode.ENACT,
            )

    def test_witnessed_intention_does_not_schedule_relational_gift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            action = "осмыслить желание заставить @mara следовать за мной"
            result = world.process_action("observer", action)
            store = world._threads_store()
            state = world._player_state(store, "observer")
            source_actions = [
                item.get("payload", {}).get("source_action")
                for item in state.get("pending", [])
            ]

            self.assertEqual(result.status, "INTENTION_WITNESSED")
            self.assertNotIn(action, source_actions)
            profile = world.free_other_state("observer")["profile"]
            if "mara" in profile["others"]:
                self.assertEqual(profile["others"]["mara"]["contacts"], 0)

    def test_intention_sidecar_crosses_portable_json_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            source_path = Path(source)
            target_path = Path(target)
            world = PlayableGenesisV187(source_path)
            action = "вспомнить мысль уничтожить ковёр и отказаться от неё"
            world.process_action("pilot", action)

            output = source_path.parent / "honest-intention.genesis-save.json"
            try:
                manager = PortableSaveManager(source_path)
                manager.export_to(output, label="Honest intention threshold")
                bundle = json.loads(output.read_text(encoding="utf-8"))
                self.assertTrue(manager.verify_bundle(bundle)[0])
                self.assertTrue(
                    any(
                        item["path"] == "honest_intention_v18_7_3.json"
                        for item in bundle["files"]
                    )
                )

                PortableSaveManager(target_path).import_bundle(bundle)
                restored = PlayableGenesisV187(target_path)
                restored_records = restored.honest_intention_state("pilot")["records"]
                self.assertEqual(restored_records[-1]["action"], action)
                self.assertTrue(restored.verify_honest_intention_state()[0])
                self.assertTrue(restored.verify_chronicle_records()[0])
                self.assertTrue(restored.verify_possibility_graph()[0])
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
