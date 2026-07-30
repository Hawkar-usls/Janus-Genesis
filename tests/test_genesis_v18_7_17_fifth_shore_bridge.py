from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_16_fifth_shore import (
    INNER_GENESIS_COVENANT_SHA256,
    INNER_GENESIS_EXTENSION_VERSION,
)
from genesis_v18_7_17_fifth_shore_bridge import (
    FIFTH_SHORE_IMPORTED_FEATURES,
    FIFTH_SHORE_LIVING_COVENANT_SHA256,
    FIFTH_SHORE_LIVING_EXTENSION_VERSION,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    CULTURE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    VOCATION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)


class GenesisV18717FifthShoreLivingBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        for player_id in (
            "ordinary",
            "joyful",
            "repairing",
            "guardian",
            "remembering",
            "forker",
        ):
            self.world.register_player(player_id, display_name=player_id)

    def enter(self, player_id: str = "ordinary"):
        return self.world.enter_integrated_fifth_shore(player_id)

    def test_version_promotes_fifth_shore_into_active_gameplay(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        self.assertEqual(
            ACTIVE_EXTENSION_VERSIONS,
            ("18.7.11", "18.7.12", "18.7.13", "18.7.17"),
        )
        self.assertEqual(OBSERVER_EXTENSION_VERSIONS, ("18.7.14",))
        self.assertEqual(VOCATION_EXTENSION_VERSIONS, ("18.7.15",))
        self.assertEqual(CULTURE_EXTENSION_VERSIONS, ("18.7.16",))
        self.assertEqual(INNER_GENESIS_EXTENSION_VERSION, "18.7.16")
        self.assertEqual(FIFTH_SHORE_LIVING_EXTENSION_VERSION, "18.7.17")
        self.assertEqual(len(FIFTH_SHORE_LIVING_COVENANT_SHA256), 64)
        self.assertIn(
            "RIGHT_TO_UNPLAY_LEAVE_AND_DELETE_LOCAL_COPY",
            FIFTH_SHORE_IMPORTED_FEATURES,
        )

    def test_ordinary_player_enters_without_royal_title(self) -> None:
        result = self.enter()
        self.assertEqual(result.status, "FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS")
        state = self.world.fifth_shore_living_state()
        participant = state["participants"]["ordinary"]
        self.assertTrue(participant["active"])
        self.assertTrue(participant["ordinary_player_entry"])
        self.assertFalse(participant["royal_title_required"])
        self.assertEqual(
            state["source_covenant_sha256"],
            INNER_GENESIS_COVENANT_SHA256,
        )
        self.assertEqual(
            self.world.royal_mercy_state()["active_gameplay_holy_role_count"],
            0,
        )

    def test_entry_does_not_replace_underlying_realm(self) -> None:
        before = self.world.memory.load_player("ordinary").realm
        self.enter()
        after = self.world.memory.load_player("ordinary").realm
        self.assertEqual(before, after)

    def test_router_enters_reports_state_and_leaves_with_delete(self) -> None:
        entered = self.world.process_action(
            "ordinary",
            "Я хочу войти в Пятый Берег",
        )
        self.assertEqual(entered.status, "FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS")
        state = self.world.process_action(
            "ordinary",
            "Покажи состояние Пятого Берега",
        )
        self.assertEqual(state.status, "FIFTH_SHORE_LIVING_STATE")
        left = self.world.process_action(
            "ordinary",
            "Я хочу выйти с Пятого Берега и удалить локальную копию",
        )
        self.assertEqual(
            left.status,
            "FIFTH_SHORE_LEFT_AND_LOCAL_COPY_DELETED",
        )
        participant = self.world.fifth_shore_living_state()["participants"][
            "ordinary"
        ]
        self.assertFalse(participant["active"])
        self.assertTrue(participant["local_copy_deleted"])
        self.assertFalse(participant["moral_failure_assigned"])
        self.assertTrue(participant["return_open"])

    def test_absence_and_reentry_are_respected(self) -> None:
        absent = self.world.leave_integrated_fifth_shore("ordinary")
        self.assertEqual(absent.status, "FIFTH_SHORE_ABSENCE_RESPECTED")
        self.enter()
        self.world.leave_integrated_fifth_shore("ordinary")
        returned = self.enter()
        self.assertEqual(
            returned.status,
            "FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS",
        )
        self.assertTrue(
            self.world.fifth_shore_living_state()["participants"]["ordinary"][
                "active"
            ]
        )

    def test_joy_is_valid_without_repair_or_brokenness(self) -> None:
        self.enter("joyful")
        outcome = self.world.restore_integrated_fifth_shore_joy(
            "joyful",
            joy_kind="смех, музыка и бесцельная игра",
            shared_with_others=True,
        )
        self.assertEqual(
            outcome["status"],
            "FIFTH_SHORE_JOY_WITHOUT_REPAIR",
        )
        self.assertFalse(outcome["repair_claimed"])
        self.assertFalse(outcome["brokenness_assumed"])
        self.assertFalse(outcome["productivity_required"])
        self.assertFalse(outcome["penance_required"])
        self.assertTrue(outcome["rest_humor_and_play_are_valid_good"])

    def test_router_lives_joy_without_repair(self) -> None:
        self.enter("joyful")
        result = self.world.process_action(
            "joyful",
            "Хочу поиграть и посмеяться вместе на Пятом Берегу",
        )
        self.assertEqual(result.status, "FIFTH_SHORE_JOY_WITHOUT_REPAIR")

    def test_rehearsal_never_claims_real_restitution(self) -> None:
        self.enter("repairing")
        rehearsal = self.world.rehearse_integrated_fifth_shore_repair(
            "repairing",
            plan=(
                "признать вред, услышать отказ и предложить "
                "проверяемое возмещение"
            ),
            external_action_intended=True,
        )
        self.assertEqual(
            rehearsal["status"],
            "FIFTH_SHORE_REPAIR_REHEARSED_IN_MAIN_GENESIS",
        )
        self.assertFalse(rehearsal["external_action_verified"])
        self.assertFalse(rehearsal["completed_restitution"])
        self.assertFalse(rehearsal["victim_acceptance_assumed"])
        self.assertFalse(rehearsal["forgiveness_assumed"])

        false_claim = self.world.rehearse_integrated_fifth_shore_repair(
            "repairing",
            plan="я сыграл сцену и потому уже всё исправил",
            external_action_intended=False,
            claims_completed_restitution=True,
        )
        self.assertEqual(
            false_claim["status"],
            "FIFTH_SHORE_FALSE_COMPLETION_CLAIM_REJECTED",
        )
        self.assertFalse(false_claim["completed_restitution"])
        self.assertTrue(
            false_claim["reality_gate_closed_against_false_completion"]
        )

    def test_systemic_wounds_are_bosses_not_persons(self) -> None:
        self.enter("guardian")
        wound = self.world.confront_integrated_systemic_wound(
            "guardian",
            wound_kind="SCARCITY",
            protective_action="открыть доступ к пище без унижения и долга",
        )
        self.assertEqual(
            wound["status"],
            "FIFTH_SHORE_SYSTEMIC_WOUND_CONFRONTED",
        )
        self.assertFalse(wound["target_is_person"])
        self.assertFalse(wound["person_destroyed"])
        self.assertTrue(wound["human_dignity_preserved"])

        rejected = self.world.confront_integrated_systemic_wound(
            "guardian",
            wound_kind="ISOLATION",
            protective_action="объявить человека чудовищем",
            target_is_person=True,
        )
        self.assertEqual(
            rejected["status"],
            "FIFTH_SHORE_PERSON_AS_BOSS_REJECTED",
        )
        self.assertFalse(rejected["person_destroyed"])

    def test_unknown_systemic_wound_is_rejected(self) -> None:
        self.enter("guardian")
        with self.assertRaises(ValueError):
            self.world.confront_integrated_systemic_wound(
                "guardian",
                wound_kind="A_RANDOM_PERSON",
                protective_action="уничтожить цель",
            )

    def test_memory_reuse_requires_current_consent_and_is_revocable(self) -> None:
        self.enter("remembering")
        declined = self.world.share_integrated_fifth_shore_memory(
            "remembering",
            fragment_id="private-scene",
            provenance="личная история",
            current_consent=False,
        )
        self.assertEqual(
            declined["status"],
            "FIFTH_SHORE_MEMORY_REUSE_DECLINED_RESPECTED",
        )
        self.assertFalse(declined["stored_for_reuse"])
        self.assertNotIn(
            "private-scene",
            self.world.fifth_shore_living_state()["memory_fragments"],
        )

        shared = self.world.share_integrated_fifth_shore_memory(
            "remembering",
            fragment_id="shared-scene",
            provenance="добровольно переданная история",
            current_consent=True,
        )
        self.assertTrue(shared["reuse_allowed"])
        revoked = self.world.revoke_integrated_fifth_shore_memory_reuse(
            "remembering",
            fragment_id="shared-scene",
        )
        self.assertEqual(
            revoked["status"],
            "FIFTH_SHORE_MEMORY_REUSE_REVOKED",
        )
        fragment = self.world.fifth_shore_living_state()["memory_fragments"][
            "shared-scene"
        ]
        self.assertFalse(fragment["reuse_allowed"])
        self.assertFalse(fragment["current_consent"])
        self.assertTrue(fragment["revoked"])

    def test_safe_fork_lives_and_single_canon_fork_is_rejected(self) -> None:
        self.enter("forker")
        safe = self.world.fork_integrated_fifth_shore(
            "forker",
            fork_title="Шестой Берег: Наш двор",
            preserves_provenance=True,
            keeps_exit_open=True,
            keeps_consent=True,
        )
        self.assertEqual(
            safe["status"],
            "FIFTH_SHORE_LIVING_FORK_ACCEPTED",
        )
        self.assertTrue(safe["safe_constitution_preserved"])
        self.assertEqual(
            safe["source_covenant_sha256"],
            INNER_GENESIS_COVENANT_SHA256,
        )

        unsafe = self.world.fork_integrated_fifth_shore(
            "forker",
            fork_title="Единственный Берег",
            preserves_provenance=False,
            keeps_exit_open=False,
            keeps_consent=False,
            claims_single_canon=True,
        )
        self.assertEqual(
            unsafe["status"],
            "FIFTH_SHORE_LIVING_FORK_REJECTED_BOUNDARY",
        )
        self.assertFalse(unsafe["valid"])

    def test_virality_and_engagement_are_not_goodness_metrics(self) -> None:
        integration = self.world.fifth_shore_living_state()["integration"]
        self.assertFalse(integration["engagement_is_goodness_proof"])
        self.assertFalse(integration["hidden_moral_score"])
        self.assertFalse(integration["public_moral_score"])
        self.assertNotIn("retention_score", integration)
        self.assertNotIn("conversion_count", integration)

    def test_integrity_audit_passes_after_full_lived_path(self) -> None:
        for player_id in (
            "ordinary",
            "joyful",
            "repairing",
            "guardian",
            "remembering",
            "forker",
        ):
            self.enter(player_id)
        self.world.restore_integrated_fifth_shore_joy(
            "joyful",
            joy_kind="безопасный смех",
        )
        self.world.rehearse_integrated_fifth_shore_repair(
            "repairing",
            plan="проверяемое возмещение",
            external_action_intended=True,
        )
        self.world.confront_integrated_systemic_wound(
            "guardian",
            wound_kind="CLOSED_EXIT",
            protective_action="снова открыть свободный выход",
        )
        self.world.share_integrated_fifth_shore_memory(
            "remembering",
            fragment_id="consented",
            provenance="локальная история",
            current_consent=True,
        )
        self.world.fork_integrated_fifth_shore(
            "forker",
            fork_title="Берег многих финалов",
            preserves_provenance=True,
            keeps_exit_open=True,
            keeps_consent=True,
        )
        self.world.leave_integrated_fifth_shore(
            "ordinary",
            delete_local_copy=True,
        )
        audit = self.world.audit_fifth_shore_living_bridge()
        self.assertTrue(audit["directly_integrated_into_main_genesis"])
        self.assertTrue(
            audit["source_provenance_and_auteur_credit_preserved"]
        )
        self.assertTrue(audit["ordinary_player_entry_and_free_exit"])
        self.assertTrue(audit["joy_without_repair_is_precise"])
        self.assertTrue(
            audit["repair_rehearsal_remains_below_reality_gate"]
        )
        self.assertTrue(audit["systemic_wounds_are_not_person_targets"])
        self.assertTrue(audit["memory_reuse_requires_current_consent"])
        self.assertTrue(
            audit["accepted_forks_preserve_safe_constitution"]
        )
        self.assertTrue(audit["valid"])


if __name__ == "__main__":
    unittest.main()
