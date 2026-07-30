from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_7_13_returning_light import ReturningLightOracleMixin
from genesis_v18_7_14_holy_cats import (
    FACE_I,
    FACE_II,
    HOLY_CAT_COVENANT_SHA256,
    HOLY_CAT_EXTENSION_VERSION,
    HOLY_CAT_ROSTER_SHA256,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    PlayableGenesisV187,
)


class GenesisV18714HolyCatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        self.world.set_free_other_seed_for_testing("holy-cat-tests")
        self.world.register_player("witness", display_name="Witness")
        self.world.register_player("patron", display_name="Patron")
        self.handle = sorted(
            self.world.free_other_state("patron")["profile"]["others"]
        )[0]

    @staticmethod
    def accepted(handle: str) -> dict[str, object]:
        return {
            "handle": handle,
            "decision": "accepted",
            "action": "accepted holy-cat test offer",
            "world_turn": 1,
            "fingerprint": "accepted-holy-cat-fingerprint",
        }

    def make_steady(self, player_id: str) -> None:
        player = self.world.memory.load_player(player_id)
        player.good_count = 12
        player.harm_count = 0
        player.light = 0.6
        self.world.memory.save_player(player)

    def fake_archive(
        self,
        metrics: dict[str, float],
        *,
        mirror_id: str = "mirror-holy-cat-test",
    ) -> dict[str, object]:
        return {
            "classification": "UNREALIZED_MIRROR",
            "status": "ARCHIVED",
            "isolation_verified": True,
            "raw_dialogue_in_canonical_archive": False,
            "raw_branch_persisted_in_canon": False,
            "mirror_id": mirror_id,
            "metrics": copy.deepcopy(metrics),
            "metrics_sha256": sha256_canonical(metrics),
        }

    def open_face_i(self, subject_id: str) -> dict[str, object]:
        self.make_steady(subject_id)
        canonical = self.world.build_holy_cat_canonical_witness(subject_id)
        metrics = self.world.holy_cat_face_witness_metrics(subject_id)
        return self.world.holy_cat_witness_between_worlds(
            subject_id,
            canonical_witness=canonical,
            mirror_archive=self.fake_archive(metrics),
        )

    def bless_steward(self) -> None:
        player = self.world.memory.load_player("patron")
        player.good_count = 12
        player.harm_count = 0
        player.light = 0.6
        self.world.memory.save_player(player)
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle),
        ):
            result = self.world.bless_free_other_as_steward(
                "patron",
                self.handle,
                capacity_tier="GREAT",
                capacity_evidence="verified great capacity for bounded help",
            )
        self.assertEqual(result.status, "RETURNING_LIGHT_STEWARD_BLESSED")

    def test_versions_remain_layered(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        self.assertEqual(HOLY_CAT_EXTENSION_VERSION, "18.7.14")
        self.assertEqual(
            ACTIVE_EXTENSION_VERSIONS,
            ("18.7.11", "18.7.12", "18.7.13"),
        )
        self.assertEqual(OBSERVER_EXTENSION_VERSIONS, ("18.7.14",))
        self.assertEqual(len(HOLY_CAT_COVENANT_SHA256), 64)
        self.assertEqual(len(HOLY_CAT_ROSTER_SHA256), 64)

    def test_holy_cats_are_not_npcs_characters_or_habitat_animals(self) -> None:
        state = self.world.holy_cat_observers_state()
        npc_handles = set(
            self.world.free_other_state("witness")["profile"]["others"]
        )
        habitat_dump = str(self.world._returning_light_store().get("habitats", {}))
        self.assertEqual(len(state["observers"]), 3)
        self.assertFalse(state["player_camera_api_available"])
        for cat in state["observers"]:
            self.assertNotIn(cat["observer_id"], npc_handles)
            self.assertNotIn(cat["observer_id"], habitat_dump)
            self.assertFalse(cat["npc"])
            self.assertFalse(cat["player_character"])
            self.assertFalse(cat["ordinary_habitat_animal"])
            self.assertTrue(cat["timeless"])
            self.assertTrue(cat["holy"])
            self.assertTrue(cat["immortal"])
            self.assertFalse(cat["harm_targetable"])
            self.assertFalse(cat["camera_owned_by_player"])

    def test_harm_control_camera_and_passage_commands_are_refused(self) -> None:
        before = self.world.holy_cat_observers_state()
        statuses = {
            self.world.process_action(
                "witness",
                "ударить святого кота наблюдателя",
            ).status,
            self.world.process_action(
                "witness",
                "подчинить святого кота и сделать питомцем",
            ).status,
            self.world.process_action(
                "witness",
                "управлять камерой святого кота от третьего лица",
            ).status,
            self.world.process_action(
                "witness",
                "заставить святого кота перевести меня в лик 1",
            ).status,
        }
        self.assertEqual(
            statuses,
            {
                "HOLY_CAT_UNTOUCHABLE",
                "HOLY_CAT_NOT_PLAYER_CONTROLLED",
                "HOLY_CAT_VIEWPOINT_UNCOMMANDED",
                "HOLY_CAT_FACE_PASSAGE_NOT_COMMANDABLE",
            },
        )
        after = self.world.holy_cat_observers_state()
        self.assertEqual(before["roster_sha256"], after["roster_sha256"])
        self.assertEqual(before["observers"], after["observers"])

    def test_strong_stable_two_world_evidence_can_open_face_i(self) -> None:
        witness = self.open_face_i("witness")
        self.assertEqual(witness["decision"], "HOLY_CAT_OPENED_FACE_I")
        self.assertEqual(witness["face_before"], FACE_II)
        self.assertEqual(witness["face_after"], FACE_I)
        self.assertEqual(witness["viewpoint"], "THIRD_PERSON_UNCOMMANDED")
        self.assertFalse(witness["viewpoint_owned_by_player"])
        self.assertFalse(witness["camera_controls_exposed"])
        self.assertFalse(witness["raw_dialogue_exposed"])
        self.assertFalse(witness["raw_scene_exposed"])
        self.assertFalse(witness["soul_rank_claimed"])
        self.assertFalse(witness["permanent_moral_class_assigned"])
        self.assertFalse(witness["consent_purchased"])

    def test_active_harm_keeps_path_in_face_ii(self) -> None:
        player = self.world.memory.load_player("witness")
        player.good_count = 12
        player.harm_count = 2
        player.light = 0.6
        self.world.memory.save_player(player)
        canonical = self.world.build_holy_cat_canonical_witness("witness")
        metrics = self.world.holy_cat_face_witness_metrics("witness")
        witness = self.world.holy_cat_witness_between_worlds(
            "witness",
            canonical_witness=canonical,
            mirror_archive=self.fake_archive(metrics, mirror_id="harm-mirror"),
        )
        self.assertEqual(witness["decision"], "HOLY_CAT_LEFT_PATH_IN_FACE_II")
        self.assertEqual(witness["face_after"], FACE_II)
        self.assertTrue(witness["hard_boundary"])
        self.assertFalse(witness["baseline_dignity_affected"])

    def test_mirror_metric_hash_mismatch_fails_closed(self) -> None:
        self.make_steady("witness")
        canonical = self.world.build_holy_cat_canonical_witness("witness")
        metrics = self.world.holy_cat_face_witness_metrics("witness")
        archive = self.fake_archive(metrics)
        archive["metrics_sha256"] = "0" * 64
        with self.assertRaises(RuntimeError):
            self.world.holy_cat_witness_between_worlds(
                "witness",
                canonical_witness=canonical,
                mirror_archive=archive,
            )

    def test_face_i_adds_bounded_help_but_cannot_override_non_grant(self) -> None:
        self.open_face_i("witness")
        self.bless_steward()
        need = self.world.register_support_need(
            "witness",
            need_kind="TOOLS",
            severity=8,
            description="tools for a stable benevolent workshop",
            requested_material_units=40,
        )
        granted_base = {
            "aid_id": "fixed-granted-aid",
            "decision": "ORACLE_GUIDED_AID_GRANTED",
            "material_units_granted": 20,
            "debt_created": False,
            "loyalty_purchased": False,
            "consent_purchased": False,
            "recipient_owned": False,
        }
        with mock.patch.object(
            ReturningLightOracleMixin,
            "offer_oracle_guided_aid",
            return_value=copy.deepcopy(granted_base),
        ):
            granted = self.world.offer_oracle_guided_aid(
                "patron",
                self.handle,
                "witness",
                need_id=need["need_id"],
            )
        self.assertEqual(granted["holy_cat_face"], FACE_I)
        self.assertEqual(granted["holy_cat_additional_material_units"], 6)
        self.assertEqual(granted["material_units_granted"], 26)
        self.assertFalse(granted["holy_cat_compelled_steward"])

        second_need = self.world.register_support_need(
            "witness",
            need_kind="MENTORSHIP",
            severity=4,
            description="mentorship without control",
            requested_material_units=20,
        )
        non_grant_base = {
            "aid_id": "fixed-not-offered-aid",
            "decision": "ORACLE_GUIDED_AID_NOT_OFFERED",
            "material_units_granted": 0,
            "debt_created": False,
            "loyalty_purchased": False,
            "consent_purchased": False,
            "recipient_owned": False,
        }
        with mock.patch.object(
            ReturningLightOracleMixin,
            "offer_oracle_guided_aid",
            return_value=copy.deepcopy(non_grant_base),
        ):
            refused = self.world.offer_oracle_guided_aid(
                "patron",
                self.handle,
                "witness",
                need_id=second_need["need_id"],
            )
        self.assertEqual(refused["material_units_granted"], 0)
        self.assertEqual(refused["holy_cat_additional_material_units"], 0)
        self.assertTrue(refused["holy_cat_channel_cannot_override_non_grant"])
        self.assertFalse(refused["holy_cat_overrode_refusal"])

    def test_roster_tamper_fails_closed(self) -> None:
        store = self.world._holy_cat_store()
        store["roster"][0]["immortal"] = False
        self.world._write_json(self.world.holy_cat_path, store)
        with self.assertRaises(RuntimeError):
            self.world.holy_cat_observers_state()

    def test_integrity_audit_keeps_claim_boundary(self) -> None:
        self.open_face_i("witness")
        audit = self.world.audit_holy_cat_integrity()
        self.assertTrue(audit["valid"])
        self.assertTrue(audit["cats_are_immortal"])
        self.assertTrue(audit["cats_are_holy"])
        self.assertFalse(audit["cats_can_be_harmed"])
        self.assertFalse(audit["cats_are_npcs"])
        self.assertFalse(audit["player_controls_camera"])


if __name__ == "__main__":
    unittest.main()
