from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "PLAY_GENESIS_IN_ANY_AI_CHAT.md"
MANIFEST = ROOT / "ai" / "GENESIS_UNIVERSAL_CHAT_ENTRY.json"
README = ROOT / "README.md"
AI_ENTRY = ROOT / "AI_ENTRY.md"
LLMS = ROOT / "llms.txt"


class UniversalChatGenesisTests(unittest.TestCase):
    def test_playbook_is_self_contained_and_starts_game_instead_of_summarizing(self) -> None:
        text = PLAYBOOK.read_text(encoding="utf-8")
        required = [
            "START THE GAME, DO NOT SUMMARIZE THE REPOSITORY",
            "UNIVERSAL_CHAT_RUNTIME",
            "Python, shell access, API keys, a hosted server, plugins, and external tools are optional",
            "The Threshold Without a Gate",
            "Universal God Mode",
            "Free Others",
            "Living Threads",
            "Bloom of Possibility",
            "Protected Childhood",
            "Returning Light and Royal Mercy",
            "The Fifth Shore",
            "JOY_WITHOUT_REPAIR",
            "janus.genesis.universal_chat_save.v1",
            "Any natural-language action is valid input",
        ]
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_manifest_requires_no_backend_and_preserves_truth_boundary(self) -> None:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(value["version"], "18.7.21")
        self.assertEqual(value["entry_file"], PLAYBOOK.name)
        self.assertEqual(value["runtime"]["mode"], "UNIVERSAL_CHAT_RUNTIME")
        self.assertFalse(value["runtime"]["backend_required"])
        self.assertFalse(value["runtime"]["python_required"])
        self.assertFalse(value["runtime"]["hosted_gateway_required"])
        self.assertFalse(value["runtime"]["api_key_required"])
        self.assertTrue(value["runtime"]["persistent_inside_current_chat"])
        self.assertTrue(value["runtime"]["portable_save_supported"])
        self.assertFalse(value["runtime"]["canonical_python_save_changed"])
        self.assertFalse(value["runtime"]["shared_network_changed"])
        self.assertTrue(
            value["truth_boundary"]["must_follow_higher_priority_platform_rules"]
        )
        self.assertTrue(
            value["truth_boundary"]["must_not_claim_code_execution_when_none_occurred"]
        )

    def test_all_public_ai_entry_surfaces_point_to_the_universal_playbook(self) -> None:
        for path in (README, AI_ENTRY, LLMS):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertIn(PLAYBOOK.name, text)
                self.assertIn("UNIVERSAL_CHAT_RUNTIME", text)

    def test_universal_mode_does_not_replace_authoritative_runtime_claims(self) -> None:
        text = PLAYBOOK.read_text(encoding="utf-8")
        self.assertIn("canonical_python_save_changed = false", text)
        self.assertIn("shared_network_changed = false", text)
        self.assertIn("Do not call it `AUTHORITATIVE_RUNTIME`", text)
        self.assertIn("Simulated residents are not asserted to be conscious", text)

    def test_exit_and_free_other_boundaries_remain_open(self) -> None:
        text = PLAYBOOK.read_text(encoding="utf-8")
        for marker in (
            "player_controlled = false",
            "can_refuse = true",
            "can_leave = true",
            "silence_is_not_consent = true",
            "Leaving is always allowed",
            "goodness_purchases_relationship\": false",
        ):
            if marker.endswith('\": false'):
                manifest_text = MANIFEST.read_text(encoding="utf-8")
                self.assertIn(marker, manifest_text)
            else:
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
