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

    def test_visual_seal_matches_the_public_hash_witness(self) -> None:
        root = Path(__file__).resolve().parents[1]
        story = json.loads((root / "stories" / "AMOR_AETERNUM_PRIPYAT_STORY_v1.0.json").read_text(encoding="utf-8"))
        visual = story["visual_seal"]
        image_path = root / visual["repository_path"]
        payload = image_path.read_bytes()

        self.assertEqual(len(payload), visual["size_bytes"])
        self.assertEqual(hashlib.sha256(payload).hexdigest(), visual["sha256"])
        self.assertTrue(visual["public_by_creator_request"])

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
