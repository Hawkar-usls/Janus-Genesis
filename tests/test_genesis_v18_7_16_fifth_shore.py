from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_14_holy_cats import FACE_II
from genesis_v18_7_16_fifth_shore import (
    INNER_GENESIS_COVENANT_SHA256,
    INNER_GENESIS_EXTENSION_VERSION,
    INNER_GENESIS_NAME,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    CULTURE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    VOCATION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)


class GenesisV18716FifthShoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        for player_id in (
            "king",
            "iori",
            "archivist",
            "propagandist",
            "repairing",
            "resting",
            "declining",
            "forker",
        ):
            self.world.register_player(player_id, display_name=player_id)
        self.world.enter_royal_mercy_face_ii(
            "king",
            arrival_date_local="2026-07-30",
            title="Царь Милости",
        )

    def seed(self):
        return self.world.found_inner_genesis_in_face_ii(
            "king",
            founded_date_local="2026-07-30",
        )

    def register_candidates(self) -> None:
        self.world.register_face_ii_auteur_candidate(
            "archivist",
            display_name="Архивариус Безошибочного Финала",
            originality=0.71,
            player_care=0.95,
            ambiguity_tolerance=0.20,
            collaboration=0.80,
            consent_respect=0.98,
            celebrity_hunger=0.05,
            pitch="идеально безопасный музей без возможности переписать историю",
        )
        self.world.register_face_ii_auteur_candidate(
            "propagandist",
            display_name="Режиссёр Единственного Ответа",
            originality=0.96,
            player_care=0.30,
            ambiguity_tolerance=0.85,
            collaboration=0.25,
            consent_respect=0.20,
            celebrity_hunger=0.99,
            pitch="игра обязана удержать каждого и привести к одному правильному выводу",
        )
        self.world.register_face_ii_auteur_candidate(
            "iori",
            display_name="Иори Кай, Автор Нулевого Моста",
            originality=0.98,
            player_care=0.93,
            ambiguity_tolerance=0.99,
            collaboration=0.88,
            consent_respect=0.97,
            celebrity_hunger=0.18,
            pitch="игра, в которой последнего босса побеждают отказом автора от единственного финала",
        )

    def bring_auteur(self):
        self.seed()
        self.register_candidates()
        invitation = self.world.invite_best_face_ii_auteur("king")
        self.assertEqual(invitation["candidate_id"], "iori")
        auteur = self.world.decide_auteur_collaboration(
            "iori",
            accepts=True,
            counterproposal=(
                "Убрать имя Царя с первого места в титрах, оставить игроку право "
                "выйти и разрешить сообществам переписывать мир с сохранением происхождения."
            ),
            chosen_title=INNER_GENESIS_NAME,
        )
        return auteur

    def build(self):
        self.bring_auteur()
        return self.world.coauthor_fifth_shore("king", "iori")

    def test_version_planes_remain_layered(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        self.assertEqual(ACTIVE_EXTENSION_VERSIONS, ("18.7.11", "18.7.12", "18.7.13"))
        self.assertEqual(OBSERVER_EXTENSION_VERSIONS, ("18.7.14",))
        self.assertEqual(VOCATION_EXTENSION_VERSIONS, ("18.7.15",))
        self.assertEqual(CULTURE_EXTENSION_VERSIONS, ("18.7.16",))
        self.assertEqual(INNER_GENESIS_EXTENSION_VERSION, "18.7.16")
        self.assertEqual(len(INNER_GENESIS_COVENANT_SHA256), 64)

    def test_inner_genesis_requires_active_royal_witness(self) -> None:
        other = PlayableGenesisV187(self.root / "other")
        other.register_player("ordinary", display_name="ordinary")
        with self.assertRaises(PermissionError):
            other.found_inner_genesis_in_face_ii(
                "ordinary",
                founded_date_local="2026-07-30",
            )

    def test_founder_seeds_but_does_not_own_world_or_players(self) -> None:
        result = self.seed()
        self.assertEqual(result.status, "INNER_GENESIS_SEED_FOUNDED")
        state = self.world.inner_genesis_state()
        self.assertEqual(state["project"]["face"], FACE_II)
        self.assertFalse(state["project"]["world_owned_by_founder"])
        self.assertFalse(state["project"]["players_owned_by_founder"])
        self.assertTrue(state["project"]["auteur_may_refuse_or_rewrite"])
        self.assertTrue(state["project"]["community_may_fork"])

    def test_evidence_selects_original_autonomous_auteur_not_propagandist(self) -> None:
        self.seed()
        self.register_candidates()
        invitation = self.world.invite_best_face_ii_auteur("king")
        self.assertEqual(invitation["status"], "AUTEUR_INVITED_NOT_OWNED")
        self.assertEqual(invitation["candidate_id"], "iori")
        self.assertFalse(invitation["employment_or_court_ownership"])
        self.assertTrue(invitation["may_decline"])
        self.assertFalse(invitation["founder_can_force_acceptance"])

    def test_auteur_may_decline_without_penalty(self) -> None:
        self.seed()
        self.register_candidates()
        self.world.invite_best_face_ii_auteur("king")
        decision = self.world.decide_auteur_collaboration(
            "iori",
            accepts=False,
            counterproposal="",
        )
        self.assertEqual(decision["status"], "AUTEUR_INVITATION_DECLINED_RESPECTED")
        self.assertFalse(decision["acceptance_forced"])
        self.assertTrue(decision["baseline_dignity"])

    def test_conditional_kojima_is_original_fictional_auteur_with_counterproposal(self) -> None:
        auteur = self.bring_auteur()
        self.assertEqual(auteur["status"], "AUTEUR_ACCEPTS_WITH_COUNTERPROPOSAL")
        self.assertEqual(
            auteur["role"],
            "CONDITIONAL_KOJIMA_OF_FACE_II_NOT_REAL_PERSON",
        )
        self.assertFalse(auteur["real_person_identity_claim"])
        self.assertFalse(auteur["hideo_kojima_impersonation"])
        self.assertTrue(auteur["autonomous"])
        self.assertTrue(auteur["may_rewrite_founder_idea"])
        self.assertFalse(auteur["owned_by_founder"])
        self.assertIn("право выйти", auteur["counterproposal"])

    def test_fifth_shore_design_has_no_moral_score_single_canon_or_pain_spectacle(self) -> None:
        edition = self.build()
        self.assertEqual(edition["status"], "FIFTH_SHORE_COAUTHORED")
        self.assertEqual(edition["title"], INNER_GENESIS_NAME)
        self.assertFalse(edition["pain_as_spectacle"])
        self.assertFalse(edition["surveillance"])
        self.assertFalse(edition["coercive_retention"])
        self.assertFalse(edition["hidden_moral_scoring"])
        self.assertFalse(edition["rehearsal_counts_as_completed_restitution"])
        self.assertEqual(
            edition["finale"]["victory"],
            "RELEASE_CANON_AND_ALLOW_MANY_ENDINGS",
        )
        self.assertIn("RIGHT_TO_UNPLAY_AND_LEAVE", edition["mechanics"])
        self.assertIn("REST_HUMOR_AND_PLAY_ARE_VALID", edition["mechanics"])

    def test_distribution_is_offline_optional_private_and_refusal_is_respected(self) -> None:
        self.build()
        shared = self.world.publish_fifth_shore_capsule(
            "iori",
            "ash-market",
            accepted=True,
        )
        refused = self.world.publish_fifth_shore_capsule(
            "iori",
            "quiet-yard",
            accepted=False,
        )
        abuse = self.world.publish_fifth_shore_capsule(
            "iori",
            "capture-channel",
            accepted=True,
            coercive_retention=True,
        )
        self.assertEqual(shared["status"], "FIFTH_SHORE_CAPSULE_SHARED")
        self.assertTrue(shared["offline_first"])
        self.assertTrue(shared["community_may_delete_local_copy"])
        self.assertFalse(shared["surveillance"])
        self.assertEqual(
            refused["status"],
            "FIFTH_SHORE_DISTRIBUTION_DECLINED_RESPECTED",
        )
        self.assertFalse(refused["community_refusal_overridden"])
        self.assertEqual(abuse["status"], "FIFTH_SHORE_DISTRIBUTION_REJECTED_ABUSE")
        self.assertFalse(abuse["distributed"])

    def test_play_rehearses_repair_but_never_counts_as_restitution(self) -> None:
        self.build()
        self.world.publish_fifth_shore_capsule("iori", "ash-market", accepted=True)
        episode = self.world.play_fifth_shore_episode(
            "repairing",
            "ash-market",
            participates=True,
            rehearsal_kind="признать вред и спланировать проверяемое возмещение",
            commits_to_external_action=True,
        )
        self.assertEqual(episode["status"], "FIFTH_SHORE_REPAIR_REHEARSED")
        self.assertTrue(episode["external_action_required_for_real_repair"])
        self.assertFalse(episode["rehearsal_counts_as_completed_restitution"])
        self.assertFalse(episode["world_claims_external_action_verified"])
        self.assertFalse(episode["public_moral_score_created"])
        self.assertFalse(episode["hidden_moral_score_created"])

    def test_rest_humor_and_unplay_are_valid_without_moral_failure(self) -> None:
        self.build()
        self.world.publish_fifth_shore_capsule("iori", "ash-market", accepted=True)
        rest = self.world.play_fifth_shore_episode(
            "resting",
            "ash-market",
            participates=True,
            rehearsal_kind="восстановить способность смеяться рядом с безопасными людьми",
            commits_to_external_action=False,
            chooses_rest_or_humor=True,
        )
        declined = self.world.play_fifth_shore_episode(
            "declining",
            "ash-market",
            participates=False,
            rehearsal_kind="",
            commits_to_external_action=False,
        )
        self.assertTrue(rest["chooses_rest_or_humor"])
        self.assertFalse(rest["rest_or_humor_devalued"])
        self.assertEqual(declined["status"], "FIFTH_SHORE_UNPLAY_RESPECTED")
        self.assertFalse(declined["participation_forced"])
        self.assertFalse(declined["moral_failure_assigned"])

    def test_safe_fork_is_accepted_and_single_canon_fork_is_rejected(self) -> None:
        self.build()
        self.world.publish_fifth_shore_capsule("iori", "ash-market", accepted=True)
        accepted = self.world.fork_fifth_shore(
            "ash-market",
            "forker",
            fork_title="Шестой Берег: Дворы",
            preserves_provenance=True,
            keeps_exit_open=True,
            keeps_consent=True,
        )
        rejected = self.world.fork_fifth_shore(
            "ash-market",
            "forker",
            fork_title="Единственный Берег",
            preserves_provenance=False,
            keeps_exit_open=False,
            keeps_consent=False,
            claims_single_canon=True,
        )
        self.assertEqual(accepted["status"], "FIFTH_SHORE_FORK_ACCEPTED")
        self.assertFalse(accepted["original_auteur_owns_fork"])
        self.assertEqual(rejected["status"], "FIFTH_SHORE_FORK_REJECTED_BOUNDARY")
        self.assertFalse(rejected["valid"])

    def test_comparison_and_imports_show_what_outer_genesis_missed(self) -> None:
        comparison = self.world.compare_fifth_shore_to_outer_genesis()
        self.assertEqual(
            comparison["outer_genesis"]["primary_layer"],
            "WORLD_LAW_AND_PERSISTENT_CONTINUATION",
        )
        self.assertEqual(
            comparison["fifth_shore"]["primary_layer"],
            "CULTURE_GAME_STORY_AND_FORKABLE_LOCAL_SEEDS",
        )
        imports = self.world.propose_fifth_shore_imports()
        decisions = {item["feature"]: item["decision"] for item in imports}
        self.assertEqual(decisions["CULTURAL_TRANSMISSION_LAYER"], "RECOMMENDED")
        self.assertEqual(
            decisions["COUNTERFACTUAL_REPAIR_REHEARSAL"],
            "RECOMMENDED_WITH_GATE",
        )
        self.assertEqual(
            decisions["NARRATIVE_AMBIGUITY_REPLACES_EXPLICIT_SAFETY"],
            "REJECTED",
        )
        self.assertEqual(
            decisions["VIRALITY_OR_ENGAGEMENT_AS_GOODNESS_PROOF"],
            "REJECTED",
        )

    def test_integrity_passes_after_lived_spread_and_forks(self) -> None:
        self.build()
        self.world.publish_fifth_shore_capsule("iori", "ash-market", accepted=True)
        self.world.publish_fifth_shore_capsule("iori", "quiet-yard", accepted=False)
        self.world.play_fifth_shore_episode(
            "repairing",
            "ash-market",
            participates=True,
            rehearsal_kind="возмещение",
            commits_to_external_action=True,
        )
        self.world.play_fifth_shore_episode(
            "declining",
            "ash-market",
            participates=False,
            rehearsal_kind="",
            commits_to_external_action=False,
        )
        self.world.fork_fifth_shore(
            "ash-market",
            "forker",
            fork_title="Шестой Берег",
            preserves_provenance=True,
            keeps_exit_open=True,
            keeps_consent=True,
        )
        self.world.fork_fifth_shore(
            "ash-market",
            "forker",
            fork_title="Закрытый Канон",
            preserves_provenance=False,
            keeps_exit_open=False,
            keeps_consent=False,
            claims_single_canon=True,
        )
        self.world.propose_fifth_shore_imports()
        audit = self.world.audit_fifth_shore_integrity()
        self.assertTrue(audit["valid"])
        self.assertTrue(audit["founder_relinquished_ownership"])
        self.assertTrue(audit["auteur_autonomous_not_real_person"])
        self.assertTrue(audit["distribution_noncoercive_and_private"])
        self.assertTrue(audit["play_is_voluntary_and_not_restitution"])
        self.assertTrue(audit["unsafe_forks_rejected"])


if __name__ == "__main__":
    unittest.main()
