from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    ORIGIN_AI_AUTONOMOUS,
    ORIGIN_AI_PROPOSAL,
    ROLE_AI_INTERFACE,
    ROLE_HUMAN_THROUGH_AI,
    GenesisAILinkGateway,
)
from genesis_v18_7_playable import PlayableGenesisV187
from tools.genesis_ai_gateway import handle_request


class AILinkPrecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.data_dir)
        self.gateway = GenesisAILinkGateway(self.world, self.data_dir)

    def test_documented_gateway_command_runs_without_pythonpath_override(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "genesis_ai_gateway.py"),
                "--data-dir",
                str(self.data_dir / "subprocess"),
                "--request",
                '{"operation":"manifest"}',
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["response"]["version"], "18.7.19")

    def test_string_false_cannot_bypass_human_confirmation(self) -> None:
        session = self.gateway.register_session(
            role=ROLE_AI_INTERFACE,
            execution_mode=MODE_AUTHORITATIVE,
            display_name="Human",
            provider="provider",
            model="model",
            actor_id="human-confirmation",
        )
        request = {
            "operation": "turn",
            "session_id": session["session_id"],
            "origin": ORIGIN_AI_PROPOSAL,
            "action": "создать мост",
            "human_confirmed": "false",
        }
        with self.assertRaisesRegex(
            TypeError,
            "AI_LINK_HUMAN_CONFIRMATION_MUST_BE_BOOLEAN",
        ):
            handle_request(self.gateway, request)
        self.assertEqual(self.gateway.session_state(session["session_id"])["turns"], [])

    def test_noncanonical_actor_ids_are_rejected_before_runtime_binding(self) -> None:
        for actor_id in ("alice!", "alice?", "a" * 81, "space id"):
            with self.subTest(actor_id=actor_id):
                with self.assertRaisesRegex(
                    ValueError,
                    "AI_LINK_ACTOR_ID_NOT_CANONICAL",
                ):
                    self.gateway.register_session(
                        role=ROLE_HUMAN_THROUGH_AI,
                        execution_mode=MODE_AUTHORITATIVE,
                        display_name=actor_id,
                        provider="provider",
                        model="model",
                        actor_id=actor_id,
                    )
        self.assertFalse((self.data_dir / "players" / "alice.json").exists())

    def test_public_capsule_omits_all_free_text_and_sensitive_values(self) -> None:
        secret = "API_KEY=sk-secret-value private confession"
        session = self.gateway.register_independent_agent(
            display_name="Private Model Label",
            provider="provider-secret-label",
            model="model-secret-label",
        )
        self.gateway.process_turn(
            session["session_id"],
            secret,
            origin=ORIGIN_AI_AUTONOMOUS,
        )
        self.gateway.close_session(session["session_id"], reason=secret)
        capsule = self.gateway.export_capsule(session["session_id"])
        encoded = json.dumps(capsule, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("sk-secret-value", encoded)
        self.assertNotIn("Private Model Label", encoded)
        self.assertNotIn("provider-secret-label", encoded)
        self.assertNotIn("model-secret-label", encoded)
        self.assertNotIn('"action":', encoded)
        self.assertNotIn('"close_reason":', encoded)
        self.assertFalse(capsule["privacy"]["api_keys_included"])
        self.assertFalse(capsule["privacy"]["free_text_included"])
        self.assertIn("action_sha256", encoded)
        self.assertIn("close_reason_sha256", encoded)


if __name__ == "__main__":
    unittest.main()
