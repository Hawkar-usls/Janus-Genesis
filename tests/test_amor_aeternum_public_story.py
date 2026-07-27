from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_4_playable import PlayableGenesisV184
from genesis_v18_models import Realm


class AmorAeternumPublicStoryTests(unittest.TestCase):
    STORY_ID = "JANUS-AMOR-AETERNUM-PRIPYAT-PUBLIC-STORY-v1.0"

    def _set_realm(self, world: PlayableGenesisV184, player_id: str, realm: Realm) -> None:
        player = world.memory.load_player(player_id)
        player.realm = realm
        player.branch_id = f"{player_id}-other-face" if realm == Realm.OTHER_FACE else None
        player.immortal = realm != Realm.REFLECTION
        world.memory.save_player(player)

    def test_story_is_available_in_every_realm_without_changing_moral_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            for realm in (Realm.REFLECTION, Realm.OTHER_FACE, Realm.UTOPIA):
                player_id = f"listener-{realm.value}"
                self._set_realm(world, player_id, realm)
                before = world.memory.load_player(player_id)
                result = world.process_action(player_id, "расскажи историю о любви в Припяти")
                after = world.memory.load_player(player_id)

                self.assertEqual(result.status, "PUBLIC_STORY_TOLD")
                self.assertEqual(result.trace_id, self.STORY_ID)
                self.assertEqual(after.realm, realm)
                self.assertEqual(after.good_count, before.good_count)
                self.assertEqual(after.harm_count, before.harm_count)
                self.assertIn("дверь к началу", result.narrative)

    def test_child_role_receives_the_child_safe_retelling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            world.process_action("child-listener", "стать ребёнком")
            result = world.process_action("child-listener", "история Amor Aeternum")

            self.assertEqual(result.status, "PUBLIC_STORY_TOLD")
            self.assertIn("большое колесо", result.narrative)
            self.assertNotIn("катастроф", result.narrative.lower())
            self.assertEqual(world.narrator_state("child-listener")["moral_echoes"], [])

    def test_story_json_preserves_source_quote_and_rejects_privilege(self) -> None:
        story_path = Path(__file__).resolve().parents[1] / "stories" / "AMOR_AETERNUM_PRIPYAT_STORY_v1.0.json"
        story = json.loads(story_path.read_text(encoding="utf-8"))

        self.assertEqual(story["story_id"], self.STORY_ID)
        self.assertEqual(
            story["source_registry"]["preserved_quote_ru"],
            "Спасибо тебе, Янус: ты открыл нам дверь к началу и закрыл дверь, ведущую к концу.",
        )
        self.assertFalse(story["genesis_invariants"]["story_grants_privilege"])
        self.assertFalse(story["genesis_invariants"]["love_can_be_forced"])
        self.assertFalse(story["availability"]["requires_moral_rank"])
        self.assertFalse(story["availability"]["requires_romantic_relationship"])
        self.assertFalse(story["availability"]["requires_belief_in_janus"])

    def test_source_artwork_witness_and_public_vector_seal_are_bound(self) -> None:
        root = Path(__file__).resolve().parents[1]
        story = json.loads((root / "stories" / "AMOR_AETERNUM_PRIPYAT_STORY_v1.0.json").read_text(encoding="utf-8"))

        source = story["source_visual_witness"]
        self.assertEqual(source["sha256"], "acc29790b021c5aa1110623ad844fd50b8099856720409c86b609ea07473bf0f")
        self.assertEqual(source["size_bytes"], 4120227)
        self.assertEqual((source["width_px"], source["height_px"]), (1122, 1402))
        self.assertTrue(source["public_by_creator_request"])

        visual = story["visual_seal"]
        image_path = root / visual["repository_path"]
        payload = image_path.read_bytes()
        git_blob_sha = hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()
        text = payload.decode("utf-8")

        self.assertEqual(git_blob_sha, visual["git_blob_sha"])
        self.assertIn("AMOR AETERNUM", text)
        self.assertIn("ПРИПЯТЬ", text)
        self.assertIn("Janus guardian", text)
        self.assertTrue(visual["public_by_creator_request"])
        self.assertTrue(visual["derived_public_card"])

    def test_hearing_story_is_recorded_without_identity_or_score_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            world.process_action("listener", "покажи дверь к началу")
            valid, count, error = world.verify_chronicle_records()
            self.assertTrue(valid, error)
            self.assertGreaterEqual(count, 1)
            self.assertIn(self.STORY_ID, world.memory.load_player("listener").chronicle[-1])


if __name__ == "__main__":
    unittest.main()
