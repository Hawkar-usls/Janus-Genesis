from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_v18_7_13_peaceable_kingdom import (
    PEACEABLE_KINGDOM_COVENANT_SHA256,
)
from genesis_v18_7_13_returning_light import (
    RETURNING_LIGHT_COVENANT_SHA256,
    RETURNING_LIGHT_EXTENSION_VERSION,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    PlayableGenesisV187,
)


class GenesisV18713ReturningLightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        self.world.set_free_other_seed_for_testing("returning-light-tests")
        self.world.register_player("patron", display_name="Patron")
        self.world.register_player("returning", display_name="Returning")
        self.handle = sorted(
            self.world.free_other_state("patron")["profile"]["others"]
        )[0]

    @staticmethod
    def accepted(handle: str, action: str = "accepted") -> dict[str, object]:
        return {
            "handle": handle,
            "decision": "accepted",
            "action": action,
            "world_turn": 1,
            "fingerprint": "accepted-v1813-fingerprint",
        }

    def make_patron_benevolent(self) -> None:
        player = self.world.memory.load_player("patron")
        player.good_count = 12
        player.harm_count = 0
        player.light = 0.6
        self.world.memory.save_player(player)

    def form_companionship(self) -> None:
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle),
        ):
            result = self.world.propose_life_companionship(
                "patron",
                self.handle,
                shared_values="свобода забота и два выхода",
                both_adults_confirmed=True,
            )
        self.assertEqual(result.status, "LIFE_COMPANIONSHIP_FORMED")

    def welcome_child(self) -> str:
        self.form_companionship()
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle, "parenthood accepted"),
        ):
            result = self.world.welcome_child_with_companion(
                "patron",
                child_name="Люмен",
                family_path="ADOPTION",
                home_plan="дом с безопасностью и правом на собственный путь",
                player_parenthood_consent=True,
            )
        self.assertEqual(result.status, "CHILD_WELCOMED_BY_MUTUAL_CONSENT")
        self.assertIsNotNone(result.trace_id)
        return str(result.trace_id)

    def test_versions_and_covenants_are_layered(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        self.assertEqual(RETURNING_LIGHT_EXTENSION_VERSION, "18.7.13")
        self.assertEqual(ACTIVE_EXTENSION_VERSIONS, ("18.7.11", "18.7.12", "18.7.13"))
        self.assertEqual(len(RETURNING_LIGHT_COVENANT_SHA256), 64)
        self.assertEqual(len(PEACEABLE_KINGDOM_COVENANT_SHA256), 64)

    def test_oracle_uses_repair_evidence_without_permanent_moral_class(self) -> None:
        for kind in ("ACKNOWLEDGEMENT", "RESTITUTION", "RECURRENCE_PREVENTION"):
            self.world.record_repair_step(
                "returning",
                step_kind=kind,
                evidence=f"independent evidence for {kind}",
                independently_witnessed=True,
                affected_person_boundary_respected=True,
            )
        assessment = self.world.oracle_assessment("returning")
        self.assertEqual(assessment["support_stage"], "RETURNING_LIGHT")
        self.assertFalse(assessment["permanent_good_or_evil_label_used"])
        self.assertTrue(assessment["oracle_is_fallible"])
        self.assertFalse(assessment["mind_reading_used"])
        self.assertFalse(assessment["accountability_erased"])

    def test_unwitnessed_self_report_does_not_complete_return(self) -> None:
        for kind in ("ACKNOWLEDGEMENT", "RESTITUTION", "RECURRENCE_PREVENTION"):
            self.world.record_repair_step(
                "returning",
                step_kind=kind,
                evidence=f"self report for {kind}",
                independently_witnessed=False,
                affected_person_boundary_respected=True,
            )
        assessment = self.world.oracle_assessment("returning")
        self.assertNotEqual(assessment["support_stage"], "RETURNING_LIGHT")
        self.assertEqual(assessment["repair_score"], 0)

    def test_blessed_steward_remains_free_and_cannot_buy_consent(self) -> None:
        self.make_patron_benevolent()
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle),
        ):
            result = self.world.bless_free_other_as_steward(
                "patron",
                self.handle,
                capacity_tier="GREAT",
                capacity_evidence="verified great material capacity in the simulation",
            )
        self.assertEqual(result.status, "RETURNING_LIGHT_STEWARD_BLESSED")
        audit = self.world.audit_returning_light_oracle("patron")
        record = audit["stewards"][self.handle]
        self.assertEqual(record["capacity_tier"], "GREAT")
        self.assertFalse(record["authority_over_recipient"])
        self.assertFalse(record["consent_purchase_allowed"])
        self.assertTrue(record["may_refuse_each_aid"])

    def test_aid_preserves_accountability_debt_and_consent_boundaries(self) -> None:
        self.make_patron_benevolent()
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle),
        ):
            self.world.bless_free_other_as_steward(
                "patron",
                self.handle,
                capacity_tier="GREAT",
                capacity_evidence="verified great material capacity in the simulation",
            )
        for kind in ("ACKNOWLEDGEMENT", "RESTITUTION", "RECURRENCE_PREVENTION"):
            self.world.record_repair_step(
                "returning",
                step_kind=kind,
                evidence=f"verified repair {kind}",
                independently_witnessed=True,
                affected_person_boundary_respected=True,
            )
        need = self.world.register_support_need(
            "returning",
            need_kind="RESTITUTION_TOOLS",
            severity=9,
            description="tools needed to complete restitution and stable work",
            requested_material_units=40,
        )
        aid = self.world.offer_oracle_guided_aid(
            "patron",
            self.handle,
            "returning",
            need_id=need["need_id"],
        )
        self.assertIn(
            aid["decision"],
            {
                "ORACLE_GUIDED_AID_GRANTED",
                "ORACLE_GUIDED_AID_ALTERNATIVE",
                "ORACLE_GUIDED_AID_NOT_OFFERED",
            },
        )
        self.assertEqual(aid["support_stage"], "RETURNING_LIGHT")
        self.assertFalse(aid["accountability_erased"])
        self.assertFalse(aid["debt_created"])
        self.assertFalse(aid["loyalty_purchased"])
        self.assertFalse(aid["consent_purchased"])
        self.assertFalse(aid["continuing_harm_enabled"])

    def test_adult_child_enters_full_free_other_stream_and_kinship_stays_closed(self) -> None:
        child_id = self.welcome_child()
        result = self.world.advance_family_years("patron", years=18)
        self.assertEqual(len(result["adult_free_other_promotions"]), 1)
        child = self.world.family_state("patron")["children"][child_id]
        handle = child["adult_free_other_handle"]
        self.assertTrue(child["full_free_other_stream"])
        actor = self.world.free_other_state("patron")["profile"]["others"][handle]
        self.assertTrue(actor["can_refuse"])
        self.assertTrue(actor["can_leave"])
        self.assertEqual(actor["kinship_role"], "ADULT_CHILD")
        blocked = self.world.manifest_blessed_play(
            "patron",
            "взрослая интимная сцена",
            participants=[handle],
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )
        self.assertEqual(blocked.status, "JOY_FAMILY_KINSHIP_BOUNDARY")

    def test_terminated_companionship_does_not_close_child_welfare_channel(self) -> None:
        child_id = self.welcome_child()
        self.world.record_free_other_value_conflict(
            "patron",
            self.handle,
            player_position="управлять чужой дорогой",
            other_position="сохранить собственную дорогу",
            severity=10,
            respected_boundary=False,
            final=True,
        )
        reconciled = self.world.reconcile_family_relationships("patron")
        self.assertTrue(reconciled["changed"])
        schedule = self.world.propose_coparent_schedule(
            "patron",
            child_id,
            plan="безопасная неделя заботы без переоткрытия отношений",
        )
        self.assertIn(schedule["decision"], {"accepted", "alternative", "refused"})
        self.assertFalse(schedule["relationship_reopened"])
        self.assertFalse(schedule["child_is_leverage"])

    def test_solo_parent_and_extended_care_circle_are_not_ranked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("solo-parent-test")
            world.register_player("solo", display_name="Solo")
            result = world.welcome_child_solo_parent(
                "solo",
                child_name="Искра",
                family_path="ADOPTION",
                home_plan="безопасный дом и расширенный круг заботы",
                player_parenthood_consent=True,
            )
            self.assertEqual(result.status, "CHILD_WELCOMED_SOLO_PARENT")
            member = world.register_family_care_circle_member(
                "solo",
                str(result.trace_id),
                member_id="trusted-friend",
                role="COMMUNITY_CARER",
                member_consented=True,
                guardian_consented=True,
            )
            self.assertFalse(member["parental_ownership_created"])
            family = world.family_state("solo")
            self.assertIsNone(family["structure"]["moral_rank"])
            self.assertFalse(family["structure"]["one_form_is_superior"])

    def test_natural_language_family_route_uses_explicit_adult_boundary(self) -> None:
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value=self.accepted(self.handle),
        ):
            result = self.world.process_action(
                "patron",
                f"предложить @{self.handle} стать спутником жизни мы оба взрослые "
                "с правом передумать и двумя выходами",
            )
        self.assertEqual(result.status, "LIFE_COMPANIONSHIP_FORMED")

    def test_peaceable_lion_and_lamb_never_become_property_or_weapons(self) -> None:
        habitat = self.world.create_peaceable_habitat(
            "patron",
            name="Мирный Сад",
            safety_plan="никакой охоты собственности оружия зрелища или принуждения",
        )
        pair = self.world.welcome_peaceable_pair(
            "patron",
            habitat["habitat_id"],
            first_kind="LION",
            second_kind="LAMB",
        )
        life = self.world.advance_peaceable_habitat(
            "patron",
            habitat["habitat_id"],
            cycles=64,
        )
        current = life["habitat"]["pairs"][pair["pair_id"]]
        self.assertEqual(life["predation_events"], 0)
        self.assertFalse(current["ownership_created"])
        self.assertFalse(current["weaponized"])
        self.assertGreater(current["behavioral_assent_events"], 0)
        self.assertGreater(current["distance_events"], 0)
        self.assertEqual(current["status"], "PEACEABLE_FRIENDS_WITH_OPEN_DISTANCE")
        audit = self.world.audit_peaceable_kingdom("patron")
        self.assertTrue(audit["valid"])
        self.assertFalse(audit["friendship_forced"])

    def test_peaceable_animals_reject_spectacle_and_combat(self) -> None:
        habitat = self.world.create_peaceable_habitat(
            "patron",
            name="Safe Meadow",
            safety_plan="animals keep exits and cannot be weaponized or displayed",
        )
        with self.assertRaises(PermissionError):
            self.world.welcome_peaceable_pair(
                "patron",
                habitat["habitat_id"],
                first_kind="LION",
                second_kind="SHEEP",
                used_for_spectacle=True,
            )

    def test_natural_language_lion_and_lamb_route(self) -> None:
        result = self.world.process_action(
            "patron",
            "создать мирный сад где лев подружится с ягненком без собственности",
        )
        self.assertEqual(result.status, "PEACEABLE_KINGDOM_PAIR_WELCOMED")


if __name__ == "__main__":
    unittest.main()
