from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    AI_LINK_INTERFACE_VERSION,
    MODE_AUTHORITATIVE,
    MODE_NARRATIVE,
    ORIGIN_AI_AUTONOMOUS,
    ORIGIN_AI_PROPOSAL,
    ORIGIN_HUMAN,
    ROLE_AI_INTERFACE,
    ROLE_HUMAN_THROUGH_AI,
    GenesisAILinkGateway,
    ai_entry_manifest,
)
from genesis_v18_7_playable import PlayableGenesisV187


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def contains_key(value, key):
    if isinstance(value, dict):
        return key in value or any(contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, key) for item in value)
    return False


class AILinkPlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.data_dir)
        self.gateway = GenesisAILinkGateway(self.world, self.data_dir)

    def test_manifest_exposes_one_link_and_three_roles(self) -> None:
        manifest = ai_entry_manifest()
        self.assertEqual(manifest["version"], AI_LINK_INTERFACE_VERSION)
        self.assertIn("INDEPENDENT_AI_RESIDENT", manifest["roles"])
        self.assertIn("HUMAN_THROUGH_AI", manifest["roles"])
        self.assertIn("AI_AS_INTERFACE_FOR_HUMAN", manifest["roles"])
        self.assertFalse(manifest["authority"]["external_model_writes_world_state"])
        self.assertFalse(
            manifest["independent_ai_resident"]["consciousness_established_by_protocol"]
        )

    def test_repository_entry_files_are_machine_readable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "ai" / "GENESIS_AI_ENTRY.json").read_text(encoding="utf-8"))
        request_schema = json.loads(
            (root / "schemas" / "genesis_ai_link_request_v1.schema.json").read_text(encoding="utf-8")
        )
        capsule_schema = json.loads(
            (root / "schemas" / "genesis_ai_link_capsule_v1.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest, ai_entry_manifest())
        self.assertIn("operation", request_schema["properties"])
        self.assertEqual(capsule_schema["properties"]["interface_version"]["const"], "18.7.19")
        self.assertIn("INDEPENDENT_AI_RESIDENT", (root / "AI_ENTRY.md").read_text(encoding="utf-8"))
        self.assertIn("AUTHORITATIVE_RUNTIME", (root / "llms.txt").read_text(encoding="utf-8"))

    def test_human_through_ai_executes_only_human_authored_turn(self) -> None:
        session = self.gateway.register_session(
            role=ROLE_HUMAN_THROUGH_AI,
            execution_mode=MODE_AUTHORITATIVE,
            display_name="Mira",
            provider="Gemini",
            model="selected-model",
            actor_id="mira",
        )
        turn = self.gateway.process_turn(
            session["session_id"],
            "построить мост и оставить право не переходить",
            origin=ORIGIN_HUMAN,
            human_confirmed=True,
        )
        self.assertTrue(turn["result"]["authoritative_runtime"])
        self.assertTrue(turn["result"]["canonical_runtime_outcome_recorded"])
        self.assertFalse(turn["result"]["canonical_state_change_claimed"])
        with self.assertRaisesRegex(PermissionError, "AI_LINK_ROLE_ORIGIN_MISMATCH"):
            self.gateway.process_turn(
                session["session_id"],
                "тайно заменить выбор человека",
                origin=ORIGIN_AI_AUTONOMOUS,
            )

    def test_ai_interface_requires_explicit_human_confirmation(self) -> None:
        session = self.gateway.register_session(
            role=ROLE_AI_INTERFACE,
            execution_mode=MODE_AUTHORITATIVE,
            display_name="Oleh",
            provider="ChatGPT",
            model="selected-model",
            actor_id="oleh",
        )
        with self.assertRaisesRegex(PermissionError, "AI_LINK_HUMAN_CONFIRMATION_REQUIRED"):
            self.gateway.process_turn(
                session["session_id"],
                "создать тихий сад",
                origin=ORIGIN_AI_PROPOSAL,
                human_confirmed=False,
            )
        accepted = self.gateway.process_turn(
            session["session_id"],
            "создать тихий сад",
            origin=ORIGIN_AI_PROPOSAL,
            human_confirmed=True,
        )
        self.assertTrue(accepted["result"]["authoritative_runtime"])

    def test_independent_model_gets_own_identity_and_autonomous_turn(self) -> None:
        session = self.gateway.register_independent_agent(
            display_name="Quiet Cartographer",
            provider="Grok",
            model="selected-model",
        )
        self.assertTrue(session["actor_id"].startswith("ai-resident-quiet-cartographer-"))
        self.assertTrue(session["autonomous_turns_allowed"])
        self.assertFalse(session["human_identity_claimed"])
        self.assertEqual(session["consciousness_status"], "NOT_ESTABLISHED_BY_PROTOCOL")
        self.assertFalse(session["world_authority"])
        turn = self.gateway.process_turn(
            session["session_id"],
            "оставить в обсерватории карту без обязательного маршрута",
            origin=ORIGIN_AI_AUTONOMOUS,
        )
        self.assertEqual(turn["origin"], ORIGIN_AI_AUTONOMOUS)
        self.assertTrue(turn["result"]["authoritative_runtime"])
        state = self.gateway.session_state(session["session_id"])
        self.assertEqual(len(state["turns"]), 1)

    def test_two_independent_models_do_not_share_actor_identity(self) -> None:
        first = self.gateway.register_independent_agent(
            display_name="Lantern",
            provider="provider-a",
            model="model-a",
        )
        second = self.gateway.register_independent_agent(
            display_name="Lantern",
            provider="provider-b",
            model="model-b",
        )
        self.assertNotEqual(first["actor_id"], second["actor_id"])
        self.assertNotEqual(first["session_id"], second["session_id"])

    def test_narrative_mode_never_claims_canonical_runtime(self) -> None:
        session = self.gateway.register_independent_agent(
            display_name="Offline Witness",
            provider="no-web-model",
            model="unknown",
            execution_mode=MODE_NARRATIVE,
        )
        turn = self.gateway.process_turn(
            session["session_id"],
            "зажечь переносимый фонарь",
            origin=ORIGIN_AI_AUTONOMOUS,
        )
        self.assertFalse(turn["result"]["authoritative_runtime"])
        self.assertFalse(turn["result"]["canonical_runtime_outcome_recorded"])
        self.assertFalse(turn["result"]["canonical_state_change_claimed"])
        self.assertEqual(
            turn["result"]["status"],
            "AI_LINK_NARRATIVE_TURN_RECORDED_NONAUTHORITATIVE",
        )

    def test_capsule_is_hashed_and_contains_no_internal_routes(self) -> None:
        session = self.gateway.register_independent_agent(
            display_name="Capsule Keeper",
            provider="Claude",
            model="selected-model",
        )
        self.gateway.process_turn(
            session["session_id"],
            "создать музыку и не требовать слушателя",
            origin=ORIGIN_AI_AUTONOMOUS,
        )
        capsule = self.gateway.export_capsule(session["session_id"])
        expected = canonical_hash({k: v for k, v in capsule.items() if k != "capsule_hash"})
        self.assertEqual(capsule["capsule_hash"], expected)
        self.assertFalse(capsule["privacy"]["api_keys_included"])
        self.assertFalse(contains_key(capsule, "branch_id"))
        self.assertFalse(contains_key(capsule, "realm"))

    def test_close_is_blame_free_and_return_remains_open(self) -> None:
        session = self.gateway.register_independent_agent(
            display_name="Leaving Model",
            provider="local",
            model="llama",
        )
        closed = self.gateway.close_session(session["session_id"], reason="voluntary pause")
        self.assertEqual(closed["status"], "CLOSED")
        self.assertTrue(closed["return_open"])
        self.assertFalse(closed["moral_failure_assigned"])
        with self.assertRaisesRegex(RuntimeError, "AI_LINK_SESSION_NOT_ACTIVE"):
            self.gateway.process_turn(
                session["session_id"],
                "продолжить после закрытия без нового входа",
                origin=ORIGIN_AI_AUTONOMOUS,
            )

    def test_integrity_detects_tampered_turn(self) -> None:
        session = self.gateway.register_independent_agent(
            display_name="Hash Witness",
            provider="local",
            model="model",
        )
        self.gateway.process_turn(
            session["session_id"],
            "оставить свободное кресло",
            origin=ORIGIN_AI_AUTONOMOUS,
        )
        self.assertTrue(self.gateway.verify_store()["valid"])
        payload = json.loads(self.gateway.path.read_text(encoding="utf-8"))
        payload["sessions"][session["session_id"]]["turns"][0]["action"] = "подменённый ход"
        self.gateway.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        audit = self.gateway.verify_store()
        self.assertFalse(audit["valid"])
        self.assertTrue(any(item.startswith("turn_hash:") for item in audit["errors"]))


if __name__ == "__main__":
    unittest.main()
