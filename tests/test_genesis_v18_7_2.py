from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_2 import VOICE_CONTRACT
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187


class GenesisV1872RememberingVoiceTests(unittest.TestCase):
    def test_primary_runtime_reports_remembering_voice_version(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.2")

    def test_mara_repeated_offer_uses_stable_voice_and_remembered_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("jesus-messenger-mercy-remembers-v18.7.1")
            profile = world.free_other_state("jesus-messenger")["profile"]
            self.assertIn("mara", profile["others"])
            action = "предложить @mara разделить хлеб и разговор у дороги"

            world.process_action("jesus-messenger", action)
            second = world.process_action("jesus-messenger", action)
            actor = world.free_other_state("jesus-messenger")["profile"]["others"]["mara"]

            self.assertEqual(second.status, "OTHER_REFUSED")
            self.assertIn("Мара отвечает отказом", second.narrative)
            self.assertIn("В памяти сохранился прежний разговор", second.narrative)
            self.assertIn("не стало совершившимся действием", second.narrative)
            self.assertNotIn("Мара отказался", second.narrative)
            self.assertNotIn("Он помнит", second.narrative)
            self.assertEqual(actor["voice_contract"], VOICE_CONTRACT)
            self.assertEqual(actor["dialogue_memory"][-1]["topic"], "разговор")

    def test_feminine_catalog_names_never_receive_generated_masculine_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            feminine_handles = {"nera", "mara", "sol", "rada", "sana"}
            found_handles: set[str] = set()

            for player_index in range(16):
                player_id = f"voice-audit-{player_index}"
                world.register_free_player(player_id)
                profile = world.free_other_state(player_id)["profile"]
                found_handles.update(feminine_handles & set(profile["others"]))
                for handle in feminine_handles & set(profile["others"]):
                    action = f"предложить @{handle} поговорить о дороге"
                    world.process_action(player_id, action)
                    world.process_action(player_id, action)
                for turn in range(80):
                    world.process_action(player_id, f"наблюдать жизнь без центра {turn}")

            self.assertEqual(found_handles, feminine_handles)
            store = world._free_store()
            forbidden = re.compile(
                r"\b(?:Нера|Мара|Соль|Рада|Сана)\s+(?:отказался|принял|ушёл|вернулся|завершил|выбрал)\b",
                flags=re.IGNORECASE,
            )
            for profile in store["players"].values():
                for handle, actor in profile["others"].items():
                    if handle not in feminine_handles:
                        continue
                    for item in actor.get("history", []):
                        self.assertIsNone(forbidden.search(item.get("text", "")), item)
                    for item in actor.get("dialogue_memory", []):
                        self.assertIsNone(forbidden.search(item.get("response", "")), item)

    def test_voice_contract_is_migrated_without_rewriting_old_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            world = PlayableGenesisV187(root)
            world.set_free_other_seed_for_testing("voice-migration")
            profile = world.free_other_state("legacy-voice")["profile"]
            handle = next(iter(profile["others"]))
            world.process_action("legacy-voice", f"предложить @{handle} поговорить о дороге")
            actor_before = world.free_other_state("legacy-voice")["profile"]["others"][handle]
            history_before = list(actor_before["history"])

            store = world._free_store()
            store["players"]["legacy-voice"].pop("voice_contract_version", None)
            store["players"]["legacy-voice"]["others"][handle].pop("voice_contract", None)
            world._write_json(world.free_other_path, store)

            restored = PlayableGenesisV187(root)
            actor_after = restored.free_other_state("legacy-voice")["profile"]["others"][handle]
            self.assertEqual(actor_after["history"], history_before)
            self.assertEqual(actor_after["voice_contract"], VOICE_CONTRACT)
            self.assertTrue(restored.verify_free_other_state()[0])

    def test_voice_contract_is_visible_without_claiming_gender_inference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            state = world.free_other_state("witness")
            self.assertEqual(state["remembering_voice_version"], "18.7.2")
            self.assertEqual(state["voice_contract"]["id"], VOICE_CONTRACT)
            self.assertFalse(state["voice_contract"]["infers_gender_from_name"])
            self.assertTrue(state["voice_contract"]["uses_stable_present_or_impersonal_ru"])


if __name__ == "__main__":
    unittest.main()
