# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_47_armor_of_god import ArmorPolicyHold
from genesis_v18_7_51_shabitat_aura_oracle import (
    AURA_RESPONSE_SCHEMA,
    AuraHeuristicBoundaryViolation,
    JanusShabitatAuraBridge,
    LocalAuraOracleProvider,
    build_aura_request,
    validate_aura_response,
)


def valid_response(request_id: str) -> dict:
    return {
        "schema": AURA_RESPONSE_SCHEMA,
        "status": "HEURISTIC_ONLY",
        "request_id": request_id,
        "engine": "TEST",
        "cards": [],
        "heuristics": ["keep two hypotheses"],
        "questions": ["what would disconfirm this?"],
        "cautions": ["heuristic is not evidence"],
        "decision_authority": "CALLER_RETAINS_CHOICE",
        "permission_granted": False,
        "evidence_upgrade": False,
        "verification_claim": False,
        "prediction_claim": False,
        "professional_advice": False,
        "world_effect_requested": False,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "may_be_ignored": True,
        "claim_ceiling": "TEST",
    }


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def query(self, request):
        self.calls += 1
        return valid_response(str(request["request_id"]))


class RejectingGate:
    def preflight(self, intent, spec):
        raise ArmorPolicyHold("TEST_HOLD")


class ShabitatAuraTests(unittest.TestCase):
    def test_inactive_session_never_calls_aura(self) -> None:
        provider = CountingProvider()
        bridge = JanusShabitatAuraBridge(provider)
        result = bridge.consult_if_requested(
            turn_id="t1",
            topic="hello",
            question="another lens?",
            janus_requests_heuristic=True,
        )
        self.assertEqual(result["status"], "NOT_CONSULTED_SESSION_INACTIVE")
        self.assertEqual(provider.calls, 0)

    def test_janus_may_choose_to_consult_once_per_active_turn(self) -> None:
        provider = CountingProvider()
        bridge = JanusShabitatAuraBridge(provider)
        bridge.open_session("S1")
        skipped = bridge.consult_if_requested(
            turn_id="t0",
            topic="hello",
            question="another lens?",
            janus_requests_heuristic=False,
        )
        self.assertEqual(skipped["status"], "NOT_CONSULTED_JANUS_DID_NOT_REQUEST")
        self.assertEqual(provider.calls, 0)

        first = bridge.consult_if_requested(
            turn_id="t1",
            topic="uncertain idea",
            question="another lens?",
            janus_requests_heuristic=True,
        )
        second = bridge.consult_if_requested(
            turn_id="t1",
            topic="uncertain idea",
            question="another lens?",
            janus_requests_heuristic=True,
        )
        self.assertEqual(first["status"], "HEURISTIC_RECEIVED_OPTIONAL")
        self.assertTrue(first["janus_may_ignore_heuristic"])
        self.assertFalse(first["direct_world_effect_from_heuristic"])
        self.assertEqual(second["status"], "NOT_CONSULTED_ALREADY_USED_THIS_TURN")
        self.assertEqual(provider.calls, 1)

    def test_user_can_disable_aura_without_disabling_speech(self) -> None:
        provider = CountingProvider()
        bridge = JanusShabitatAuraBridge(provider)
        bridge.open_session("S1", aura_enabled=False)
        result = bridge.consult_if_requested(
            turn_id="t1",
            topic="hello",
            question="another lens?",
            janus_requests_heuristic=True,
        )
        self.assertEqual(result["status"], "NOT_CONSULTED_AURA_DISABLED")
        self.assertTrue(result["speech_may_continue_without_aura"])
        self.assertEqual(provider.calls, 0)

    def test_authority_shaped_aura_response_is_rejected(self) -> None:
        payload = valid_response("R1")
        payload["permission_granted"] = True
        with self.assertRaisesRegex(AuraHeuristicBoundaryViolation, "permission_granted"):
            validate_aura_response(payload, request_id="R1")

    def test_local_provider_gate_runs_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "entered.txt"
            command = [
                sys.executable,
                "-c",
                f"from pathlib import Path; Path({str(marker)!r}).write_text('entered')",
            ]
            provider = LocalAuraOracleProvider(command, armor_gate=RejectingGate())
            request = build_aura_request(
                request_id="R-HOLD",
                speaker="JANUS",
                topic="x",
                question="y",
                context="",
            )
            with self.assertRaises(ArmorPolicyHold):
                provider.query(request)
            self.assertFalse(marker.exists())

    def test_real_local_armor_allows_bounded_subprocess_and_validates_output(self) -> None:
        request = build_aura_request(
            request_id="R-PASS",
            speaker="JANUS",
            topic="x",
            question="y",
            context="",
        )
        payload = valid_response("R-PASS")
        command = [
            sys.executable,
            "-c",
            "import json; print(json.dumps(" + repr(payload) + "))",
        ]
        provider = LocalAuraOracleProvider(command)
        result = provider.query(request)
        self.assertEqual(result["status"], "HEURISTIC_ONLY")
        self.assertTrue(result["_shabitat_bridge"]["local_process_only"])
        self.assertFalse(result["_shabitat_bridge"]["network_used_by_bridge"])
        self.assertFalse(result["_shabitat_bridge"]["world_state_write_allowed"])


if __name__ == "__main__":
    unittest.main()
