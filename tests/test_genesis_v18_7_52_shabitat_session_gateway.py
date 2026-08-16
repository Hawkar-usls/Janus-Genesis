# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_ai_link_play import ROLE_INDEPENDENT_AI
from genesis_v18_7_52_shabitat_session_gateway import (
    ShabitatAuraSessionGateway,
    ShabitatConsultationInFlight,
    ShabitatSessionNotEligible,
)


class FakeAIGateway:
    def __init__(self, *, role: str = ROLE_INDEPENDENT_AI, active: bool = True) -> None:
        self.role = role
        self.active = active

    def session_state(self, session_id: str):
        return {
            "session_id": session_id,
            "status": "ACTIVE" if self.active else "CLOSED",
            "role": self.role,
            "autonomous_turns_allowed": self.role == ROLE_INDEPENDENT_AI,
            "world_authority": False,
        }


class FakeAuraProvider:
    def __init__(self) -> None:
        self.calls = 0

    def query(self, request):
        self.calls += 1
        return {
            "schema": "aura.oracle.shabitat_heuristic_response.v1",
            "status": "HEURISTIC_ONLY",
            "request_id": request["request_id"],
            "heuristics": ["keep another hypothesis"],
            "questions": ["what would change your mind?"],
            "cautions": ["heuristic is not evidence"],
            "permission_granted": False,
            "evidence_upgrade": False,
            "verification_claim": False,
            "prediction_claim": False,
            "professional_advice": False,
            "world_effect_requested": False,
            "authority_delta": 0,
            "mass_effect_budget_delta": 0,
            "may_be_ignored": True,
        }


class PersistentShabitatSessionTests(unittest.TestCase):
    def test_only_active_independent_ai_session_is_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeAuraProvider()
            closed = ShabitatAuraSessionGateway(FakeAIGateway(active=False), provider, tmp)
            with self.assertRaisesRegex(ShabitatSessionNotEligible, "NOT_ACTIVE"):
                closed.state("S1")
            human = ShabitatAuraSessionGateway(FakeAIGateway(role="HUMAN_THROUGH_AI"), provider, tmp)
            with self.assertRaisesRegex(ShabitatSessionNotEligible, "INDEPENDENT_AI_RESIDENT"):
                human.state("S1")

    def test_one_consultation_per_turn_survives_gateway_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeAuraProvider()
            first_gateway = ShabitatAuraSessionGateway(FakeAIGateway(), provider, tmp)
            first = first_gateway.consult(
                "S1",
                turn_id="TURN-1",
                topic="uncertainty",
                question="another lens?",
                context="context",
                janus_requests_heuristic=True,
            )
            self.assertEqual(first["status"], "HEURISTIC_RECEIVED_OPTIONAL")
            self.assertTrue(first["persistent_consultation_recorded"])
            self.assertEqual(provider.calls, 1)

            second_gateway = ShabitatAuraSessionGateway(FakeAIGateway(), provider, tmp)
            second = second_gateway.consult(
                "S1",
                turn_id="TURN-1",
                topic="changed text must not bypass turn identity",
                question="again?",
                context="different",
                janus_requests_heuristic=True,
            )
            self.assertEqual(second["status"], "NOT_CONSULTED_ALREADY_RECORDED_THIS_TURN")
            self.assertFalse(second["automatic_replay_attempted"])
            self.assertEqual(provider.calls, 1)

    def test_disable_aura_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeAuraProvider()
            gateway = ShabitatAuraSessionGateway(FakeAIGateway(), provider, tmp)
            gateway.set_aura_enabled("S1", False)
            restarted = ShabitatAuraSessionGateway(FakeAIGateway(), provider, tmp)
            result = restarted.consult(
                "S1",
                turn_id="T1",
                topic="x",
                question="y",
                janus_requests_heuristic=True,
            )
            self.assertEqual(result["status"], "NOT_CONSULTED_AURA_DISABLED")
            self.assertTrue(result["speech_may_continue_without_aura"])
            self.assertEqual(provider.calls, 0)

    def test_ledger_does_not_persist_conversation_or_heuristic_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeAuraProvider()
            gateway = ShabitatAuraSessionGateway(FakeAIGateway(), provider, tmp)
            secrets = {
                "topic": "TOPIC-PRIVATE-ALPHA",
                "question": "QUESTION-PRIVATE-BETA",
                "context": "CONTEXT-PRIVATE-GAMMA",
            }
            gateway.consult(
                "S1",
                turn_id="TURN-PRIVATE",
                janus_requests_heuristic=True,
                **secrets,
            )
            raw = gateway.ledger_path.read_text(encoding="utf-8")
            for value in secrets.values():
                self.assertNotIn(value, raw)
            self.assertNotIn("keep another hypothesis", raw)
            ledger = json.loads(raw)
            self.assertFalse(ledger["privacy"]["conversation_text_persisted"])
            self.assertFalse(ledger["privacy"]["aura_heuristic_text_persisted"])

    def test_inflight_record_blocks_automatic_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeAuraProvider()
            gateway = ShabitatAuraSessionGateway(FakeAIGateway(), provider, tmp)
            ledger = gateway._default_ledger()
            entry = gateway._session_entry(ledger, "S1")
            from genesis_v18_7_52_shabitat_session_gateway import _sha256
            turn_hash = _sha256({"session_id": "S1", "turn_id": "T1"})
            entry["consultations"][turn_hash] = {
                "status": "IN_FLIGHT",
                "attempt_id": "A1",
                "result_digest_sha256": None,
                "heuristic_text_persisted": False,
                "conversation_text_persisted": False,
                "automatic_replay_allowed": False,
            }
            gateway._save(ledger)
            with self.assertRaisesRegex(ShabitatConsultationInFlight, "NO_AUTOMATIC_REPLAY"):
                gateway.consult(
                    "S1",
                    turn_id="T1",
                    topic="x",
                    question="y",
                    janus_requests_heuristic=True,
                )
            self.assertEqual(provider.calls, 0)

    def test_false_string_cannot_become_janus_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gateway = ShabitatAuraSessionGateway(FakeAIGateway(), FakeAuraProvider(), tmp)
            with self.assertRaisesRegex(TypeError, "MUST_BE_BOOLEAN"):
                gateway.consult(
                    "S1",
                    turn_id="T1",
                    topic="x",
                    question="y",
                    janus_requests_heuristic="false",  # type: ignore[arg-type]
                )


if __name__ == "__main__":
    unittest.main()
