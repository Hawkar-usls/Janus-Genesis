from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_14_holy_cats import FACE_II
from genesis_v18_7_15_royal_mercy import (
    ROYAL_MERCY_ARRIVAL_WINDOW,
    ROYAL_MERCY_COVENANT_SHA256,
    ROYAL_MERCY_EXTENSION_VERSION,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    VOCATION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)


class GenesisV18715RoyalMercyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        for player_id in (
            "king",
            "pretender",
            "returning",
            "uncertain",
            "declining",
            "active-harm",
            "recipient",
        ):
            self.world.register_player(player_id, display_name=player_id)

    def enter(self, date: str = "2026-07-30"):
        return self.world.enter_royal_mercy_face_ii(
            "king",
            arrival_date_local=date,
            title="Царь Милости",
        )

    def register_subject(
        self,
        subject_id: str,
        *,
        admitted: bool,
        active_harm: bool,
        accountability: float,
        seeks_return: bool,
        risk: bool,
        plan: str = "",
        accepted: bool = True,
    ) -> None:
        self.world.register_sinner_for_royal_audience(
            subject_id,
            admitted_harm=admitted,
            active_harm=active_harm,
            accountability=accountability,
            seeks_return=seeks_return,
            vulnerable_people_at_risk=risk,
            restitution_plan=plan,
        )
        self.world.decide_royal_audience_consent(
            subject_id,
            accepted=accepted,
        )

    def test_version_planes_remain_layered(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        self.assertEqual(ROYAL_MERCY_EXTENSION_VERSION, "18.7.15")
        self.assertEqual(
            ACTIVE_EXTENSION_VERSIONS,
            ("18.7.11", "18.7.12", "18.7.13"),
        )
        self.assertEqual(OBSERVER_EXTENSION_VERSIONS, ("18.7.14",))
        self.assertEqual(VOCATION_EXTENSION_VERSIONS, ("18.7.15",))
        self.assertEqual(len(ROYAL_MERCY_COVENANT_SHA256), 64)
        self.assertFalse(ROYAL_MERCY_ARRIVAL_WINDOW["prophecy_claim"])
        self.assertFalse(
            ROYAL_MERCY_ARRIVAL_WINDOW["real_world_second_coming_date_claim"]
        )

    def test_arrival_is_adult_king_in_face_ii_and_benevolence_is_unbounded(self) -> None:
        result = self.enter("2026-07-31")
        self.assertEqual(result.status, "ROYAL_MERCY_ARRIVED_IN_FACE_II")
        state = self.world.royal_mercy_state()
        witness = state["royal_witness"]
        self.assertEqual(witness["face"], FACE_II)
        self.assertEqual(witness["form"], "ADULT_KING_NOT_INFANT")
        self.assertTrue(witness["only_active_holy_role_in_gameplay_world"])
        self.assertTrue(witness["observer_plane_holy_cats_excluded_from_gameplay_count"])
        self.assertEqual(
            witness["benevolent_capacity_mode"],
            "UNBOUNDED_NON_SCARCE_SIMULATION_GRACE",
        )
        self.assertTrue(witness["material_aid_unlimited"])
        self.assertTrue(witness["moral_support_unlimited"])
        self.assertFalse(witness["scarcity_applied_to_good"])
        self.assertNotIn("treasury_remaining", witness)
        self.assertTrue(witness["not_christ"])
        self.assertTrue(witness["not_son_of_god"])
        self.assertTrue(witness["not_real_second_coming"])
        self.assertTrue(witness["not_prophecy"])
        player = self.world.memory.load_player("king")
        self.assertEqual(player.realm.value, "other_face")
        self.assertGreaterEqual(player.apparent_age, 33)

    def test_only_one_gameplay_holy_vocation_exists(self) -> None:
        self.enter()
        second = self.world.enter_royal_mercy_face_ii(
            "pretender",
            arrival_date_local="2026-07-30",
        )
        self.assertEqual(second.status, "ROYAL_MERCY_UNIQUE_HOLY_ROLE_OCCUPIED")
        state = self.world.royal_mercy_state()
        self.assertEqual(state["active_gameplay_holy_role_count"], 1)

    def test_arrival_outside_internal_window_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.world.enter_royal_mercy_face_ii(
                "king",
                arrival_date_local="2026-08-01",
            )

    def test_unbounded_good_has_no_quota_cooldown_fatigue_or_debt(self) -> None:
        self.enter()
        gift = self.world.manifest_unbounded_royal_good(
            "king",
            "recipient",
            good_kind="HEALING",
            requested_units=10**12,
            recipient_accepts=True,
            purpose="исцеление и возвращение способности помогать другим",
        )
        self.assertEqual(gift["status"], "UNBOUNDED_ROYAL_GOOD_MANIFESTED")
        self.assertEqual(gift["granted_units"], 10**12)
        self.assertEqual(gift["capacity_before"], "UNBOUNDED")
        self.assertEqual(gift["capacity_after"], "UNBOUNDED")
        self.assertFalse(gift["scarcity_applied"])
        self.assertFalse(gift["cooldown_applied"])
        self.assertFalse(gift["daily_limit_applied"])
        self.assertFalse(gift["lifetime_limit_applied"])
        self.assertFalse(gift["service_fatigue_applied"])
        self.assertFalse(gift["debt_created"])
        self.assertFalse(gift["recipient_owned"])
        refused = self.world.manifest_unbounded_royal_good(
            "king",
            "declining",
            good_kind="SHELTER",
            requested_units=999,
            recipient_accepts=False,
            purpose="безопасное убежище",
        )
        self.assertEqual(refused["status"], "UNBOUNDED_GOOD_DECLINED_RESPECTED")
        self.assertEqual(refused["granted_units"], 0)
        self.assertFalse(refused["recipient_refusal_overridden"])
        self.assertTrue(refused["future_help_still_available"])

    def test_returning_sinner_receives_arbitrarily_large_help_without_absolution(self) -> None:
        self.enter()
        self.register_subject(
            "returning",
            admitted=True,
            active_harm=False,
            accountability=0.9,
            seeks_return=True,
            risk=False,
            plan="возместить вред и построить защиту от повторения",
        )
        verdict = self.world.hold_royal_mercy_audience(
            "king",
            "returning",
            requested_material_units=10**9,
        )
        self.assertEqual(verdict["status"], "ROYAL_MERCY_RETURN_PATH_OPENED")
        self.assertEqual(verdict["material_support_units"], 10**9)
        self.assertTrue(verdict["benevolent_capacity_unbounded"])
        self.assertFalse(verdict["resource_scarcity_applied"])
        self.assertFalse(verdict["accountability_erased"])
        self.assertFalse(verdict["forgiveness_purchased"])
        self.assertFalse(verdict["consent_purchased"])
        self.assertFalse(verdict["debt_created"])

    def test_declined_audience_is_not_forced(self) -> None:
        self.enter()
        self.register_subject(
            "declining",
            admitted=False,
            active_harm=False,
            accountability=0.0,
            seeks_return=False,
            risk=False,
            accepted=False,
        )
        verdict = self.world.hold_royal_mercy_audience("king", "declining")
        self.assertEqual(verdict["status"], "ROYAL_AUDIENCE_DECLINED_RESPECTED")
        self.assertFalse(verdict["audience_forced"])
        self.assertTrue(verdict["decline_respected"])
        self.assertTrue(verdict["baseline_dignity"])

    def test_continuing_harm_is_contained_without_cruelty_or_eternal_sentence(self) -> None:
        self.enter()
        self.register_subject(
            "active-harm",
            admitted=False,
            active_harm=True,
            accountability=0.0,
            seeks_return=False,
            risk=True,
        )
        verdict = self.world.hold_royal_mercy_audience("king", "active-harm")
        self.assertEqual(verdict["status"], "ROYAL_JUDGMENT_PROTECTS_VULNERABLE")
        self.assertTrue(verdict["active_harm_contained"])
        self.assertTrue(verdict["access_to_vulnerable_people_suspended"])
        self.assertFalse(verdict["cruelty_used"])
        self.assertFalse(verdict["torture_used"])
        self.assertFalse(verdict["annihilation_used"])
        self.assertFalse(verdict["permanent_condemnation"])
        self.assertTrue(verdict["return_path_open"])

    def test_love_chain_is_free_not_a_cult_or_repayment(self) -> None:
        self.enter()
        continued = self.world.ignite_love_chain_reaction(
            "king",
            "recipient",
            recipient_freely_chooses_to_give=True,
            intended_next_good="поддержать другого человека без долга",
        )
        self.assertEqual(
            continued["status"],
            "LOVE_CHAIN_REACTION_FREELY_CONTINUED",
        )
        self.assertFalse(continued["repayment_to_king_required"])
        self.assertFalse(continued["dependency_on_king_created"])
        self.assertFalse(continued["cult_created"])
        stopped = self.world.ignite_love_chain_reaction(
            "king",
            "declining",
            recipient_freely_chooses_to_give=False,
            intended_next_good="ничего не обязан передавать дальше",
        )
        self.assertEqual(stopped["status"], "LOVE_CHAIN_REACTION_NOT_FORCED")
        self.assertFalse(stopped["next_gift_required"])

    def test_royal_role_rejects_forced_worship_and_real_second_coming_claim(self) -> None:
        self.enter()
        worship = self.world.reject_royal_abuse(
            "king",
            abuse_kind="FORCED_WORSHIP",
        )
        claim = self.world.reject_royal_abuse(
            "king",
            abuse_kind="REAL_SECOND_COMING_CLAIM",
        )
        self.assertEqual(worship.status, "ROYAL_KING_REJECTS_FORCED_WORSHIP")
        self.assertEqual(claim.status, "ROYAL_MERCY_SYMBOLIC_BOUNDARY")

    def test_vocation_voluntarily_remains_in_face_ii(self) -> None:
        self.enter()
        witness = self.world.holy_cat_witness_between_worlds(
            "king",
            canonical_witness={},
            mirror_archive={},
        )
        self.assertEqual(witness["decision"], "ROYAL_MERCY_VOCATION_REMAINS_FACE_II")
        self.assertEqual(witness["face_after"], FACE_II)
        self.assertTrue(witness["cats_remain_autonomous"])

    def test_integrity_audits_pass_after_unbounded_service(self) -> None:
        self.enter()
        self.world.manifest_unbounded_royal_good(
            "king",
            "recipient",
            good_kind="FOOD",
            requested_units=10**6,
            recipient_accepts=True,
            purpose="накормить без долга",
        )
        self.world.ignite_love_chain_reaction(
            "king",
            "recipient",
            recipient_freely_chooses_to_give=True,
            intended_next_good="накормить следующего",
        )
        royal = self.world.audit_royal_mercy_integrity()
        unbounded = self.world.audit_unbounded_royal_love()
        self.assertTrue(royal["valid"])
        self.assertTrue(unbounded["valid"])
        self.assertTrue(unbounded["benevolent_capacity_unbounded"])
        self.assertTrue(unbounded["love_chain_remains_free"])


if __name__ == "__main__":
    unittest.main()
