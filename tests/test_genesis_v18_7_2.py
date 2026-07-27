from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_2 import VOICE_CONTRACT
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187


class GenesisV1872RememberingVoiceTests(unittest.TestCase):
    def test_primary_runtime_includes_remembering_voice(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.5")

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
            self.assertEqual(actor["dialogue_memory"][-1]["topic"], "дорога")

    def test_all_feminine_catalog_names_receive_stable_dynamic_refusal_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("voice-audit-all-feminine-handles")
            feminine_handles = {"nera", "mara", "sol", "rada", "sana"}
            located: dict[str, tuple[str, dict, dict]] = {}

            for index in range(40):
                player_id = f"voice-audit-{index}"
                store = world._free_store()
                profile = world._free_profile(store, player_id)
                for handle in feminine_handles & set(profile["others"]):
                    located.setdefault(handle, (player_id, store, profile))
                world._write_json(world.free_other_path, store)
                if set(located) == feminine_handles:
                    break

            self.assertEqual(set(located), feminine_handles)
            forbidden = re.compile(
                r"\b(?:Нера|Мара|Соль|Рада|Сана)\s+(?:отказался|принял|ушёл|вернулся|завершил|выбрал)\b",
                flags=re.IGNORECASE,
            )
            for handle, (player_id, store, profile) in located.items():
                actor = profile["others"][handle]
                store["world_turn"] = int(store.get("world_turn", 0)) + 1
                action = f"предложить @{handle} поговорить о дороге"
                decision = {
                    "handle": handle,
                    "decision": "refused",
                    "action": action,
                    "world_turn": store["world_turn"],
                    "fingerprint": world._free_fingerprint(action),
                    "topic": "дорога",
                    "intent": "question",
                    "repeated_too_soon": False,
                    "reason": world._context_reason(
                        actor,
                        decision="refused",
                        action=action,
                        topic="дорога",
                        repeated=False,
                    ),
                    "action_excerpt": action,
                }
                event = world._apply_contact_decision(
                    store,
                    player_id,
                    profile,
                    decision,
                    action_realized=False,
                )
                self.assertIsNone(forbidden.search(event["text"]), event)
                self.assertIn("отвечает отказом", event["text"])

    def test_mara_departure_return_and_calling_change_keep_stable_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("jesus-messenger-mercy-remembers-v18.7.1")
            store = world._free_store()
            profile = world._free_profile(store, "jesus-messenger")
            actor = profile["others"]["mara"]

            departure_turn = next(
                turn for turn in range(1, 500)
                if world._free_number(store, "jesus-messenger", "mara", turn, "remembered-progress") % 100 < 39
            )
            store["world_turn"] = departure_turn
            actor["status"] = "active"
            actor["progress"] = 5
            actor["stage_index"] = 2
            departure_events = world._advance_one_profile(store, "jesus-messenger", profile)
            departure = next(item for item in departure_events if item["handle"] == "mara" and item["kind"] == "departure")
            self.assertIn("Мара уходит", departure["text"])
            self.assertNotIn("Мара ушёл", departure["text"])
            departure_context = actor["departure_context"]

            return_turn = next(
                turn for turn in range(departure_turn + 5, departure_turn + 800)
                if world._free_number(store, "jesus-messenger", "mara", turn, "remembered-return") % 100 < 31
            )
            store["world_turn"] = return_turn
            actor["left_world_turn"] = departure_turn
            return_events = world._advance_one_profile(store, "jesus-messenger", profile)
            returned = next(item for item in return_events if item["handle"] == "mara" and item["kind"] == "return")
            self.assertIn("Мара возвращается", returned["text"])
            self.assertIn(departure_context, returned["text"])
            self.assertNotIn("Мара вернулся", returned["text"])

            calling_turn = next(
                turn for turn in range(return_turn + 1, return_turn + 800)
                if world._free_number(store, "jesus-messenger", "mara", turn, "remembered-calling") % 100 < 21
            )
            store["world_turn"] = calling_turn
            actor["status"] = "active"
            actor["stage_index"] = 4
            actor["calling_changes"] = 0
            calling_events = world._advance_one_profile(store, "jesus-messenger", profile)
            changed = next(item for item in calling_events if item["handle"] == "mara" and item["kind"] == "calling_changed")
            self.assertIn("Мара завершает", changed["text"])
            self.assertIn("и выбирает", changed["text"])
            self.assertNotIn("Мара завершил", changed["text"])

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
