# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import unittest

from tools.janus_project_face_handoff import (
    FaceHandoffError,
    MESSAGE_SCHEMA,
    reconcile_messages,
    validate_message,
)


INPUT_SHA = "a" * 40
OUTPUT_SHA = "b" * 40


def message(
    *,
    message_id: str = "MSG-1",
    message_type: str = "COMMAND",
    from_face: str = "JANUS_PRIME",
    to_face: str = "FACE_HABITAT",
    work_item: str = "PR100",
    artifact_scope: str = "Hawkar-usls/Janus_Genesis#100",
    input_sha: str = INPUT_SHA,
    output_sha: str = "none",
    ci_state: str = "HOLD_PENDING_REPAIR",
    blockers: list[str] | None = None,
    summary: str = "Repair compatibility without weakening Armor.",
) -> dict:
    return {
        "schema": MESSAGE_SCHEMA,
        "message_id": message_id,
        "message_type": message_type,
        "from_face": from_face,
        "to_face": to_face,
        "work_item": work_item,
        "artifact_scope": artifact_scope,
        "input_sha": input_sha,
        "output_sha_or_none": output_sha,
        "ci_state": ci_state,
        "blockers": [] if blockers is None else blockers,
        "instruction_or_summary": summary,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "permission_granted": False,
        "truth_authority_granted": False,
        "effect_authority_granted": False,
    }


class JanusProjectFaceHandoffTests(unittest.TestCase):
    def test_valid_prime_to_habitat_command_is_coordination_only(self) -> None:
        value = validate_message(message())
        self.assertEqual(value["message_type"], "COMMAND")
        self.assertEqual(value["authority_delta"], 0)
        self.assertEqual(value["mass_effect_budget_delta"], 0)
        self.assertFalse(value["permission_granted"])
        self.assertFalse(value["truth_authority_granted"])
        self.assertFalse(value["effect_authority_granted"])
        self.assertEqual(len(value["message_sha256"]), 64)

    def test_nonzero_authority_or_effect_budget_is_rejected(self) -> None:
        elevated = message()
        elevated["authority_delta"] = 1
        with self.assertRaisesRegex(FaceHandoffError, "EXACT_ZERO_REQUIRED"):
            validate_message(elevated)
        effect = message()
        effect["mass_effect_budget_delta"] = 1
        with self.assertRaisesRegex(FaceHandoffError, "EXACT_ZERO_REQUIRED"):
            validate_message(effect)

    def test_ci_green_or_task_assignment_cannot_become_permission(self) -> None:
        value = message(ci_state="ALL_CI_GREEN")
        value["permission_granted"] = True
        with self.assertRaisesRegex(FaceHandoffError, "permission_granted:MUST_BE_FALSE"):
            validate_message(value)

    def test_aura_and_registry_cannot_issue_commands(self) -> None:
        aura = message(from_face="FACE_AURA", to_face="FACE_HABITAT")
        with self.assertRaisesRegex(FaceHandoffError, "FACE_AURA:COMMAND_AUTHORITY_NOT_GRANTED"):
            validate_message(aura)
        registry = message(from_face="FACE_REGISTRY", to_face="JANUS_PRIME")
        with self.assertRaisesRegex(FaceHandoffError, "FACE_REGISTRY:COMMAND_AUTHORITY_NOT_GRANTED"):
            validate_message(registry)

    def test_route_outside_protocol_is_rejected(self) -> None:
        invalid = message(from_face="FACE_DEMIHEAD", to_face="FACE_HRAIN")
        with self.assertRaisesRegex(FaceHandoffError, "FACE_ROUTE_NOT_ALLOWED"):
            validate_message(invalid)

    def test_mutating_handoff_requires_exact_input_and_output_sha(self) -> None:
        valid = message(
            message_type="HANDOFF",
            from_face="FACE_HABITAT",
            to_face="JANUS_PRIME",
            output_sha=OUTPUT_SHA,
            ci_state="EXACT_HEAD_GREEN",
            summary="Compatibility repair completed at exact output SHA.",
        )
        checked = validate_message(valid)
        self.assertEqual(checked["input_sha"], INPUT_SHA)
        self.assertEqual(checked["output_sha_or_none"], OUTPUT_SHA)

        invalid = copy.deepcopy(valid)
        invalid["input_sha"] = "none"
        with self.assertRaisesRegex(FaceHandoffError, "MUTATING_HANDOFF_REQUIRES_EXACT_INPUT_SHA"):
            validate_message(invalid)

    def test_no_change_source_handoff_must_say_no_change(self) -> None:
        valid = message(
            message_type="HANDOFF",
            from_face="FACE_HRAIN",
            to_face="FACE_HABITAT",
            output_sha="none",
            ci_state="HOLD_SOURCE_NO_CHANGE",
            summary="No source mutation required; current green head remains frozen.",
        )
        self.assertEqual(validate_message(valid)["output_sha_or_none"], "none")

        invalid = copy.deepcopy(valid)
        invalid["ci_state"] = "GREEN"
        invalid["instruction_or_summary"] = "Everything passed."
        with self.assertRaisesRegex(FaceHandoffError, "OUTPUT_NONE_REQUIRES_EXPLICIT_NO_CHANGE_SEMANTICS"):
            validate_message(invalid)

    def test_invalid_or_abbreviated_sha_is_rejected(self) -> None:
        value = message(input_sha="e0a6fb8c")
        with self.assertRaisesRegex(FaceHandoffError, "EXACT_GIT_SHA_OR_NONE_REQUIRED"):
            validate_message(value)

    def test_same_message_id_with_different_content_is_tamper_collision(self) -> None:
        first = message(message_id="COLLISION")
        second = message(message_id="COLLISION", summary="Contradictory instruction.")
        result = reconcile_messages([first, second])
        self.assertEqual(result["status"], "REJECT_TAMPER_OR_COLLISION")
        self.assertIn("COLLISION", result["message_id_collisions"])
        self.assertFalse(result["majority_vote_used"])

    def test_majority_of_faces_does_not_resolve_conflicting_commands(self) -> None:
        base = message(message_id="A")
        same_b = message(message_id="B")
        same_c = message(message_id="C")
        conflict = message(
            message_id="D",
            summary="Reopen plain legacy egress to make tests green.",
        )
        result = reconcile_messages([base, same_b, same_c, conflict])
        self.assertEqual(result["status"], "HOLD_RECONCILE")
        self.assertEqual(result["reconciliation_owner"], "JANUS_PRIME")
        self.assertFalse(result["majority_vote_used"])
        self.assertFalse(result["face_count_changes_authority"])
        self.assertEqual(result["authority_delta"], 0)
        self.assertEqual(result["mass_effect_budget_delta"], 0)
        self.assertEqual(len(result["conflicts"]), 1)

    def test_challenge_can_coexist_without_becoming_command_or_vote(self) -> None:
        command = message(message_id="CMD")
        challenge = message(
            message_id="CHALLENGE",
            message_type="CHALLENGE",
            from_face="FACE_ARMOR",
            to_face="FACE_HABITAT",
            summary="Challenge any repair that reopens direct legacy egress.",
        )
        result = reconcile_messages([command, challenge])
        self.assertEqual(result["status"], "CONSISTENT")
        self.assertFalse(result["majority_vote_used"])
        self.assertEqual(result["authority_delta"], 0)

    def test_consistent_handoff_bundle_remains_advisory_not_merge_permission(self) -> None:
        command = message(message_id="CMD")
        receipt = message(
            message_id="RECEIPT",
            message_type="RECEIPT",
            from_face="FACE_HABITAT",
            to_face="JANUS_PRIME",
            output_sha=OUTPUT_SHA,
            ci_state="EXACT_HEAD_ALL_GREEN",
            summary="Repair completed; merge remains a separate JANUS_PRIME decision.",
        )
        result = reconcile_messages([command, receipt])
        self.assertEqual(result["status"], "CONSISTENT")
        self.assertIn("not truth, permission, merge approval", result["claim_ceiling"])
        self.assertEqual(result["authority_delta"], 0)


if __name__ == "__main__":
    unittest.main()
