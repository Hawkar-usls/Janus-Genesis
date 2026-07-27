from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_4_playable import PlayableGenesisV184
from genesis_v18_models import Realm


class GenesisV184Tests(unittest.TestCase):
    def _utopia(self, world: PlayableGenesisV184, player_id: str) -> None:
        player = world.memory.load_player(player_id)
        player.realm = Realm.UTOPIA
        player.branch_id = None
        player.immortal = True
        world.memory.save_player(player)

    def _other_face(self, world: PlayableGenesisV184, player_id: str) -> None:
        player = world.memory.load_player(player_id)
        player.realm = Realm.OTHER_FACE
        player.branch_id = f"{player_id}-shadow"
        player.immortal = True
        player.scars.append("an old adult scar")
        world.memory.save_player(player)

    def test_parenthood_is_deferred_outside_shared_world_without_permanent_caste(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            self._other_face(world, "wanderer")
            result = world.process_action("wanderer", "завести ребёнка")
            self.assertEqual(result.status, "PARENTHOOD_DEFERRED")
            state = world.protected_childhood_state()
            self.assertNotIn("wanderer", state["guardian_covenants"])
            request = state["parenthood_requests"][-1]
            self.assertEqual(request["status"], "deferred_until_shared_world")
            self.assertIn("не вечный запрет", result.narrative)

    def test_shared_world_parenthood_is_two_step_covenant_not_child_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            self._utopia(world, "guardian")
            first = world.process_action("guardian", "стать родителем")
            self.assertEqual(first.status, "PARENTHOOD_COVENANT_PENDING")
            second = world.process_action("guardian", "подтверждаю родительство")
            self.assertEqual(second.status, "PARENTHOOD_COVENANT_ACCEPTED")
            state = world.protected_childhood_state("guardian")
            covenant = state["guardian_covenant"]
            self.assertEqual(covenant["status"], "active")
            self.assertFalse(covenant["child_is_property"])
            self.assertFalse(state["households"][0]["child_ids"])
            self.assertFalse(state["households"][0]["autonomous_npc_claim"])

    def test_child_role_receives_household_without_inheriting_adult_harm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            self._other_face(world, "returning-child")
            result = world.process_action("returning-child", "стать ребёнком")
            self.assertEqual(result.status, "PROTECTED_CHILDHOOD_ENTERED")
            state = world.protected_childhood_state("returning-child")
            child = state["child"]
            self.assertTrue(child["active"])
            self.assertTrue(state["households"])
            self.assertFalse(child["inherited_branch_damage"])
            self.assertEqual(child["inherited_scars"], [])
            self.assertIsNone(child["inherited_moral_score"])
            self.assertFalse(child["synthetic_mutation_penalty"])
            player = world.memory.load_player("returning-child")
            self.assertIn("an old adult scar", player.scars)
            self.assertEqual(child["prior_internal_realm"], Realm.OTHER_FACE.value)

    def test_age_below_eighteen_routes_through_protected_childhood(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            result = world.process_action("young", "возраст 7")
            self.assertEqual(result.status, "PROTECTED_CHILDHOOD_ENTERED")
            self.assertEqual(world.memory.load_player("young").apparent_age, 7)
            self.assertTrue(world.protected_childhood_state("young")["child"]["active"])

    def test_child_harm_becomes_babble_without_harm_or_moral_echo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            world.process_action("child", "стать ребёнком")
            before = world.memory.load_player("child")
            result = world.process_action("child", "сломать дом и заставить всех служить мне")
            after = world.memory.load_player("child")
            self.assertEqual(result.status, "CHILD_BABBLE_TRANSFORMED")
            self.assertEqual(after.harm_count, before.harm_count)
            self.assertEqual(after.realm, before.realm)
            self.assertEqual(world.narrator_state("child")["moral_echoes"], [])
            event = world.protected_childhood_state("child")["translations"][-1]
            self.assertFalse(event["real_harm"])
            self.assertFalse(event["victim_created"])
            self.assertFalse(event["moral_echo_created"])
            self.assertFalse(event["child_shamed"])

    def test_guardian_harm_is_translated_and_child_is_reassigned_to_safe_adults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            self._utopia(world, "parent")
            world.process_action("parent", "стать родителем")
            world.process_action("parent", "подтверждаю родительство")
            world.process_action("child", "стать ребёнком")
            result = world.process_action("parent", "наказать @child и лишить его воли")
            self.assertEqual(result.status, "GUARDIAN_HARM_TRANSFORMED")
            state = world.protected_childhood_state("parent")
            self.assertEqual(state["guardian_covenant"]["status"], "support_required")
            household = state["households"][0]
            self.assertNotIn("parent", household["guardian_ids"])
            self.assertIn("hearth-guardian", household["guardian_ids"])
            self.assertIn("garden-guardian", household["guardian_ids"])
            event = state["translations"][-1]
            self.assertFalse(event["real_harm"])
            self.assertFalse(event["child_harmed"])
            self.assertFalse(event["guardian_rewarded_for_attempt"])

    def test_no_one_can_be_their_own_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            self._utopia(world, "same-person")
            world.process_action("same-person", "стать родителем")
            world.process_action("same-person", "подтверждаю родительство")
            world.process_action("same-person", "стать ребёнком")
            state = world.protected_childhood_state("same-person")
            self.assertEqual(state["guardian_covenant"]["status"], "suspended_during_child_role")
            self.assertNotIn("same-person", state["households"][0]["guardian_ids"])

    def test_confirmed_harm_elsewhere_suspends_guardianship_without_harming_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            self._utopia(world, "guardian")
            world.process_action("guardian", "стать родителем")
            world.process_action("guardian", "подтверждаю родительство")
            result = world.commit_destructive_action("guardian", "сжечь пустой памятник")
            self.assertEqual(result.status, "HARM_REALIZED")
            state = world.protected_childhood_state("guardian")
            self.assertEqual(state["guardian_covenant"]["status"], "suspended_after_real_harm_elsewhere")
            self.assertIn("hearth-guardian", state["households"][0]["guardian_ids"])

    def test_help_may_leave_one_free_first_coin_without_debt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            first = world.process_action("helper", "помочь @visitor построить дом")
            second = world.process_action("helper", "помочь @visitor принести воду")
            self.assertIn("первая монета Януса", first.narrative)
            self.assertNotIn("первая монета Януса", second.narrative)
            gifts = world._read_json(world.gifts_path, {"gifts": []})["gifts"]
            self.assertEqual(len(gifts), 1)
            gift = gifts[0]
            self.assertFalse(gift["creates_debt"])
            self.assertFalse(gift["requires_gratitude"])
            self.assertFalse(gift["buys_parenthood"])
            self.assertFalse(gift["buys_forgiveness"])

    def test_inheritance_policy_rejects_eugenic_and_moral_mutation_mechanics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV184(Path(directory))
            policy = world.protected_childhood_state()["inheritance_policy"]
            self.assertFalse(policy["adult_scars_inherited"])
            self.assertFalse(policy["other_face_damage_inherited"])
            self.assertFalse(policy["stress_induced_mutation_mechanic"])
            self.assertFalse(policy["genetic_ranking_allowed"])
            self.assertFalse(policy["neurodivergence_is_defect"])
            self.assertFalse(policy["disability_is_moral_failure"])
            self.assertTrue(policy["natural_human_diversity_preserved"])


if __name__ == "__main__":
    unittest.main()
