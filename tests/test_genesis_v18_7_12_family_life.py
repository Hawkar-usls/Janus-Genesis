from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_v18_7_12_family_life import (
    FAMILY_COVENANT_SHA256,
    FAMILY_EXTENSION_VERSION,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    EXTENSION_VERSION,
    FAMILY_EXTENSION_VERSION as PLAYABLE_FAMILY_EXTENSION_VERSION,
    PLAYABLE_VERSION,
    PlayableGenesisV187,
)


class GenesisV18712FamilyLifeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        self.world.set_free_other_seed_for_testing("family-life-tests")
        self.world.register_player("family", display_name="Family Witness")
        self.handle = sorted(
            self.world.free_other_state("family")["profile"]["others"]
        )[0]

    @staticmethod
    def accepted(handle: str, action: str = "accepted family offer") -> dict[str, object]:
        return {
            "handle": handle,
            "decision": "accepted",
            "action": action,
            "world_turn": 1,
            "fingerprint": "accepted-family-fingerprint",
        }

    def form_companionship(self) -> None:
        existing = self.world.family_state("family").get("companion")
        if isinstance(existing, dict) and existing.get("status") == "ACTIVE":
            return
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle),
        ):
            result = self.world.propose_life_companionship(
                "family",
                self.handle,
                shared_values="радость свобода забота и два открытых выхода",
                both_adults_confirmed=True,
            )
        self.assertEqual(result.status, "LIFE_COMPANIONSHIP_FORMED")

    def welcome_child(self) -> str:
        self.form_companionship()
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle, "accepted parenthood offer"),
        ):
            result = self.world.welcome_child_with_companion(
                "family",
                child_name="Люмен",
                family_path="ADOPTION",
                home_plan="безопасный дом с игрой отдыхом и правом на собственный путь",
                player_parenthood_consent=True,
            )
        self.assertEqual(result.status, "CHILD_WELCOMED_BY_MUTUAL_CONSENT")
        assert result.trace_id is not None
        return result.trace_id

    def test_versions_remain_layered_without_renaming_frozen_runtime(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        self.assertEqual(EXTENSION_VERSION, "18.7.11")
        self.assertEqual(PLAYABLE_FAMILY_EXTENSION_VERSION, "18.7.12")
        self.assertEqual(FAMILY_EXTENSION_VERSION, "18.7.12")
        self.assertGreaterEqual(len(ACTIVE_EXTENSION_VERSIONS), 2)
        self.assertEqual(ACTIVE_EXTENSION_VERSIONS[:2], ("18.7.11", "18.7.12"))
        self.assertEqual(len(set(ACTIVE_EXTENSION_VERSIONS)), len(ACTIVE_EXTENSION_VERSIONS))
        self.assertEqual(len(FAMILY_COVENANT_SHA256), 64)

    def test_companionship_requires_adults_and_free_other_acceptance(self) -> None:
        blocked = self.world.propose_life_companionship(
            "family",
            self.handle,
            shared_values="добрая дружба",
            both_adults_confirmed=False,
        )
        self.assertEqual(blocked.status, "COMPANIONSHIP_ADULT_BOUNDARY")
        self.assertIsNone(self.world.family_state("family")["companion"])

        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value={
                **self.accepted(self.handle),
                "decision": "refused",
            },
        ):
            refused = self.world.propose_life_companionship(
                "family",
                self.handle,
                shared_values="дом без клетки",
                both_adults_confirmed=True,
            )
        self.assertEqual(refused.status, "COMPANIONSHIP_NOT_FORMED")
        self.assertIsNone(self.world.family_state("family")["companion"])

        self.form_companionship()
        companion = self.world.family_state("family")["companion"]
        self.assertTrue(companion["mutual_consent_verified"])
        self.assertTrue(companion["consent_reversible"])
        self.assertFalse(companion["ownership_created"])
        self.assertFalse(companion["actor_life_owned_by_companionship"])

    def test_parenthood_requires_a_new_consent_and_child_is_not_a_reward(self) -> None:
        self.form_companionship()
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value={
                **self.accepted(self.handle),
                "decision": "alternative",
            },
        ):
            refused = self.world.welcome_child_with_companion(
                "family",
                child_name="Люмен",
                family_path="ADOPTION",
                home_plan="дом без долга",
                player_parenthood_consent=True,
            )
        self.assertEqual(refused.status, "PARENTHOOD_NOT_FORMED")
        self.assertEqual(self.world.family_state("family")["children"], {})

        child_id = self.welcome_child()
        child = self.world.family_state("family")["children"][child_id]
        self.assertTrue(child["both_guardians_consented"])
        self.assertFalse(child["rights"]["is_property"])
        self.assertFalse(child["rights"]["owes_guardians_love"])
        self.assertFalse(child["rights"]["owes_guardians_success"])
        self.assertFalse(child["rights"]["adult_play_access"])
        self.assertFalse(child["rights"]["future_owned_by_guardians"])

    def test_registered_child_id_closes_adult_play_even_without_child_words(self) -> None:
        child_id = self.welcome_child()
        result = self.world.manifest_blessed_play(
            "family",
            "интимный взрослый праздник",
            participants=[child_id],
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )
        self.assertEqual(result.status, "JOY_CHILD_SAFE_REDIRECT")
        joy = self.world.joy_state("family")
        self.assertEqual(joy["play_count"], 0)

    def test_child_safe_play_and_care_create_no_debt(self) -> None:
        child_id = self.welcome_child()
        play = self.world.manifest_child_safe_family_play(
            "family",
            child_id,
            activity="построить летающую крепость из подушек и придумать правила вместе",
        )
        self.assertEqual(play.status, "CHILD_SAFE_FAMILY_PLAY_MANIFESTED")
        care = self.world.provide_family_care(
            "family",
            child_id,
            care_kind="LISTENING",
            description="выслушать идею ребёнка и не исправлять её под свой сценарий",
        )
        self.assertFalse(care["debt_created"])
        self.assertFalse(care["obedience_purchased"])

        adult_boundary = self.world.manifest_child_safe_family_play(
            "family",
            child_id,
            activity="алкоголь и эротическая вечеринка",
        )
        self.assertEqual(adult_boundary.status, "FAMILY_PLAY_CHILD_BOUNDARY")

    def test_adult_child_owns_future_and_guardianship_ends(self) -> None:
        child_id = self.welcome_child()
        result = self.world.advance_family_years("family", years=18)
        child = result["children"][child_id]
        self.assertEqual(child["age"], 18)
        self.assertEqual(child["status"], "ADULT_OWN_PATH")
        self.assertFalse(child["guardianship_active"])
        self.assertIsNotNone(child["own_path"])
        audit = self.world.audit_family_integrity("family")
        self.assertTrue(audit["valid"])
        self.assertFalse(audit["children"][0]["future_owned_by_guardians"])

    def test_relationship_end_does_not_erase_actor_or_child(self) -> None:
        child_id = self.welcome_child()
        free_store = self.world._free_store()
        profile = self.world._free_profile(free_store, "family")
        actor = profile["others"][self.handle]
        actor["relationship_state_v1810"]["status"] = "TERMINATED_BY_OTHER"
        actor["actor_life_v1810"]["status"] = "LIVING"
        self.world._write_json(self.world.free_other_path, free_store)

        reconciled = self.world.reconcile_family_relationships("family")
        self.assertTrue(reconciled["changed"])
        self.assertEqual(reconciled["companion_status"], "ENDED_WITH_RELATIONSHIP")
        self.assertEqual(reconciled["actor_life_status"], "LIVING")
        self.assertFalse(reconciled["children_erased"])
        self.assertIn(child_id, self.world.family_state("family")["children"])


if __name__ == "__main__":
    unittest.main()
