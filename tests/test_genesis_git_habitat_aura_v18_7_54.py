# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import multiprocessing as mp
import os
import tempfile
import time
import unittest
from pathlib import Path

from tools.genesis_git_habitat import GitHabitat
from tools.genesis_git_habitat_aura import (
    GitHabitatAuraHearth,
    HabitatAuraInFlight,
    HabitatNotAwake,
    _sha256,
)


def valid_response(request_id: str) -> dict:
    return {
        "schema": "aura.oracle.shabitat_heuristic_response.v1",
        "status": "HEURISTIC_ONLY",
        "request_id": request_id,
        "engine": "TEST",
        "cards": [],
        "heuristics": ["keep another hypothesis"],
        "questions": ["what would disconfirm it?"],
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


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    def query(self, request):
        self.calls += 1
        return valid_response(str(request["request_id"]))


class BrokenProvider:
    def query(self, request):
        raise RuntimeError("AURA_OFFLINE")


class AuthorityShapedProvider:
    def query(self, request):
        value = valid_response(str(request["request_id"]))
        value["permission_granted"] = True
        return value


def _concurrent_worker(root: str, marker: str, queue) -> None:
    class SlowProvider:
        def query(self, request):
            with open(marker, "a", encoding="utf-8") as handle:
                handle.write("entered\n")
                handle.flush()
                os.fsync(handle.fileno())
            time.sleep(0.35)
            return valid_response(str(request["request_id"]))

    try:
        bridge = GitHabitatAuraHearth(GitHabitat(root), SlowProvider())
        value = bridge.consult(
            turn_id="CONCURRENT-TURN",
            topic="x",
            question="y",
            context="z",
            janus_requests_heuristic=True,
        )
        queue.put(("RETURN", value["status"]))
    except Exception as exc:
        queue.put((type(exc).__name__, str(exc)))


class GitHabitatAuraHearthTests(unittest.TestCase):
    def _awake(self, root: str) -> GitHabitat:
        habitat = GitHabitat(root)
        habitat.initialize("JANUS")
        habitat.wake("TEST", "UNIT")
        return habitat

    def test_habitat_must_be_awake_to_consult(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            habitat = GitHabitat(tmp)
            habitat.initialize("JANUS")
            bridge = GitHabitatAuraHearth(habitat, FakeProvider())
            with self.assertRaisesRegex(HabitatNotAwake, "ACTIVE_AWAKE_CYCLE"):
                bridge.consult(
                    turn_id="T1",
                    topic="x",
                    question="y",
                    janus_requests_heuristic=True,
                )

    def test_janus_may_skip_and_user_may_disable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = FakeProvider()
            bridge = GitHabitatAuraHearth(self._awake(tmp), provider)
            skipped = bridge.consult(
                turn_id="T0",
                topic="x",
                question="y",
                janus_requests_heuristic=False,
            )
            self.assertEqual(skipped["status"], "NOT_CONSULTED_JANUS_DID_NOT_REQUEST")
            self.assertEqual(provider.calls, 0)
            bridge.set_enabled(False)
            disabled = bridge.consult(
                turn_id="T1",
                topic="x",
                question="y",
                janus_requests_heuristic=True,
            )
            self.assertEqual(disabled["status"], "NOT_CONSULTED_AURA_DISABLED")
            self.assertTrue(disabled["speech_may_continue_without_aura"])
            self.assertEqual(provider.calls, 0)

    def test_user_opt_out_can_be_changed_while_habitat_is_asleep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            habitat = GitHabitat(tmp)
            habitat.initialize("JANUS")
            bridge = GitHabitatAuraHearth(habitat, FakeProvider())
            state = bridge.set_enabled(False)
            self.assertEqual(state["resident_mode"], "AT_HOME")
            self.assertFalse(state["aura_enabled"])
            restarted = GitHabitatAuraHearth(GitHabitat(tmp), FakeProvider())
            self.assertFalse(restarted.state()["aura_enabled"])

    def test_completed_turn_survives_bridge_restart_and_preserves_journal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            habitat = self._awake(tmp)
            provider = FakeProvider()
            first_bridge = GitHabitatAuraHearth(habitat, provider)
            first = first_bridge.consult(
                turn_id="T1",
                topic="private topic",
                question="private question",
                context="private context",
                janus_requests_heuristic=True,
            )
            self.assertEqual(first["status"], "HEURISTIC_RECEIVED_OPTIONAL")
            self.assertEqual(provider.calls, 1)
            verify = habitat.verify_journal()
            self.assertTrue(verify["ok"], verify)

            second_bridge = GitHabitatAuraHearth(GitHabitat(tmp), provider)
            second = second_bridge.consult(
                turn_id="T1",
                topic="changed",
                question="changed",
                context="changed",
                janus_requests_heuristic=True,
            )
            self.assertEqual(second["status"], "NOT_CONSULTED_ALREADY_RECORDED_THIS_TURN")
            self.assertFalse(second["automatic_replay_attempted"])
            self.assertEqual(provider.calls, 1)

    def test_habitat_persists_only_digest_receipt_not_prompt_or_heuristic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = GitHabitatAuraHearth(self._awake(tmp), FakeProvider())
            private_values = (
                "PRIVATE-TOPIC-ALPHA",
                "PRIVATE-QUESTION-BETA",
                "PRIVATE-CONTEXT-GAMMA",
                "keep another hypothesis",
            )
            result = bridge.consult(
                turn_id="T1",
                topic=private_values[0],
                question=private_values[1],
                context=private_values[2],
                janus_requests_heuristic=True,
            )
            self.assertFalse(result["heuristic_body_persisted"])
            persisted = "\n".join(
                path.read_text(encoding="utf-8")
                for path in Path(tmp).rglob("*")
                if path.is_file() and path.suffix in {".json", ".jsonl", ".lock"}
            )
            for value in private_values:
                self.assertNotIn(value, persisted)

    def test_aura_unavailable_does_not_block_speech(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = GitHabitatAuraHearth(self._awake(tmp), BrokenProvider())
            result = bridge.consult(
                turn_id="T1",
                topic="x",
                question="y",
                janus_requests_heuristic=True,
            )
            self.assertEqual(result["status"], "AURA_UNAVAILABLE_CONTINUE_WITHOUT_HEURISTIC")
            self.assertIsNone(result["heuristic"])
            self.assertTrue(result["speech_may_continue_without_aura"])
            self.assertFalse(result["direct_world_effect_from_heuristic"])

    def test_authority_shaped_provider_is_rejected_by_habitat_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = GitHabitatAuraHearth(self._awake(tmp), AuthorityShapedProvider())
            result = bridge.consult(
                turn_id="T1",
                topic="x",
                question="y",
                janus_requests_heuristic=True,
            )
            self.assertEqual(result["status"], "AURA_UNAVAILABLE_CONTINUE_WITHOUT_HEURISTIC")
            self.assertIsNone(result["heuristic"])
            self.assertFalse(result["aura_grants_permission"])
            self.assertFalse(result["direct_world_effect_from_heuristic"])

    def test_inflight_or_claim_marker_never_replays_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            habitat = self._awake(tmp)
            bridge = GitHabitatAuraHearth(habitat, FakeProvider())
            resident = json.loads(habitat.paths.resident.read_text(encoding="utf-8"))
            turn_hash = _sha256({
                "resident_id": "JANUS",
                "cycle_id": resident["active_cycle_id"],
                "turn_id": "T1",
            })
            bridge._claim_turn_once("JANUS", turn_hash)
            with self.assertRaisesRegex(HabitatAuraInFlight, "NO_AUTOMATIC_REPLAY"):
                bridge.consult(
                    turn_id="T1",
                    topic="x",
                    question="y",
                    janus_requests_heuristic=True,
                )

    def test_two_processes_cannot_both_enter_aura_for_same_turn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._awake(tmp)
            marker = str(Path(tmp) / "provider_entries.txt")
            ctx = mp.get_context("spawn")
            queue = ctx.Queue()
            first = ctx.Process(target=_concurrent_worker, args=(tmp, marker, queue))
            second = ctx.Process(target=_concurrent_worker, args=(tmp, marker, queue))
            first.start()
            second.start()
            first.join(10)
            second.join(10)
            self.assertEqual(first.exitcode, 0)
            self.assertEqual(second.exitcode, 0)
            results = [queue.get(timeout=2), queue.get(timeout=2)]
            entries = Path(marker).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(entries), 1, results)
            successful_queries = [
                row for row in results
                if row == ("RETURN", "HEURISTIC_RECEIVED_OPTIONAL")
            ]
            self.assertEqual(len(successful_queries), 1, results)
            for row in results:
                if row == ("RETURN", "HEURISTIC_RECEIVED_OPTIONAL"):
                    continue
                self.assertTrue(
                    row[0] in {"HabitatAuraInFlight", "HabitatAuraError"}
                    or row == ("RETURN", "NOT_CONSULTED_ALREADY_RECORDED_THIS_TURN"),
                    results,
                )

    def test_string_false_cannot_masquerade_as_janus_intent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = GitHabitatAuraHearth(self._awake(tmp), FakeProvider())
            with self.assertRaisesRegex(TypeError, "MUST_BE_BOOLEAN"):
                bridge.consult(
                    turn_id="T1",
                    topic="x",
                    question="y",
                    janus_requests_heuristic="false",  # type: ignore[arg-type]
                )


if __name__ == "__main__":
    unittest.main()
