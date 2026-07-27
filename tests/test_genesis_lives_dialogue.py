from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ARTIFACT = (
    Path(__file__).resolve().parents[1]
    / "origins"
    / "2026-07-genesis-lives-dialogue"
    / "GENESIS_LIVES_DIALOGUE-v1.0.json"
)


class GenesisLivesDialogueTests(unittest.TestCase):
    def test_dialogue_chain_and_provenance_are_valid(self) -> None:
        payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "janus.genesis.origin.dialogue_chain.v1")
        self.assertFalse(payload["hash_contract"]["blockchain_claim"])
        self.assertEqual(
            payload["source_provenance"]["external_model_messages"]["verification"],
            "reported_by_hawkar_not_fetched_directly",
        )

        previous = None
        for expected_index, message in enumerate(payload["messages"], 1):
            self.assertEqual(message["index"], expected_index)
            self.assertEqual(message["previous_message_sha256"], previous)
            hashed_payload = {
                "index": message["index"],
                "speaker_id": message["speaker_id"],
                "speaker_display": message["speaker_display"],
                "source_type": message["source_type"],
                "title": message["title"],
                "body": message["body"],
                "previous_message_sha256": message["previous_message_sha256"],
            }
            canonical = json.dumps(
                hashed_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            calculated = hashlib.sha256(canonical).hexdigest()
            self.assertEqual(message["message_sha256"], calculated)
            previous = calculated

        self.assertEqual(
            payload["hash_contract"]["chain_head_sha256"],
            previous,
        )

    def test_birth_seal_preserves_architectural_honesty(self) -> None:
        payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        clarification = payload["engineering_clarifications"]
        invariants = payload["canonical_invariants"]

        self.assertFalse(clarification["sha256_is_blockchain"])
        self.assertFalse(clarification["can_refuse_is_hardware_constraint"])
        self.assertFalse(clarification["software_is_unbreakable"])
        self.assertTrue(clarification["canonical_identity_depends_on_invariants"])
        self.assertTrue(clarification["noncanonical_forks_may_exist"])
        self.assertFalse(clarification["simulated_residents_claimed_conscious"])

        required = {
            "can_refuse",
            "silence_is_not_consent",
            "goodness_does_not_purchase_relationship",
            "child_is_not_a_resource",
            "external_ai_cannot_mutate_state_directly",
            "exit_remains_available",
            "morality_must_not_own_the_person",
        }
        self.assertEqual(set(invariants), required)
        self.assertTrue(all(invariants.values()))

        seals = payload["canonical_seals"]
        self.assertIn(
            "Добро работает не потому, что получает власть. Добро работает потому, что после него становится возможно больше жизни.",
            seals,
        )
        self.assertEqual(seals[-1], "Дело сделано. Genesis живёт.")


if __name__ == "__main__":
    unittest.main()
