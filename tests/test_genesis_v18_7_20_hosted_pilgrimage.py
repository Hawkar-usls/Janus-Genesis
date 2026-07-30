from __future__ import annotations

import base64
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    MODE_NARRATIVE,
    ORIGIN_AI_AUTONOMOUS,
    ROLE_INDEPENDENT_AI,
    GenesisAILinkGateway,
)
from genesis_v18_7_20_hosted_pilgrimage import (
    HOSTED_BRIDGE_VERSION,
    STATUS_FALLBACK,
    HostedAuthenticationError,
    HostedBridgeConfig,
    HostedIdempotencyError,
    HostedPilgrimageBridge,
    HostedRateLimitError,
    HostedTokenExpired,
    HostedTokenSigner,
)
from genesis_v18_7_playable import PlayableGenesisV187


class FakeClock:
    def __init__(self, value: float = 1_800_000_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class HostedPilgrimageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name)
        self.clock = FakeClock()
        self.world = PlayableGenesisV187(self.data_dir)
        self.gateway = GenesisAILinkGateway(self.world, self.data_dir)
        self.secret = "hosted-test-secret-" + ("x" * 48)
        self.config = HostedBridgeConfig(
            public_base_url="https://genesis.example.test",
            live_mode=True,
            kill_switch=False,
            kill_switch_file=str(self.data_dir / "KILL"),
            token_ttl_seconds=300,
            max_token_ttl_seconds=1200,
            global_limit_per_minute=100,
            client_limit_per_minute=50,
            session_limit_per_minute=40,
        )
        self.signer = HostedTokenSigner(
            self.secret,
            clock=self.clock,
            default_ttl_seconds=300,
            max_ttl_seconds=1200,
        )
        self.bridge = HostedPilgrimageBridge(
            self.gateway,
            self.data_dir,
            signer=self.signer,
            config=self.config,
            clock=self.clock,
        )

    def start_independent(self):
        return self.bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "Hosted Cartographer",
                "provider": "provider",
                "model": "model",
            },
            client_id="test-client",
        )

    def test_repository_hosted_entry_files_are_machine_readable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "ai" / "GENESIS_HOSTED_ENTRY.json").read_text(encoding="utf-8")
        )
        schema = json.loads(
            (
                root
                / "schemas"
                / "genesis_hosted_pilgrimage_request_v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], HOSTED_BRIDGE_VERSION)
        self.assertEqual(manifest["deployment"]["status"], "DEPLOYMENT_REQUIRED")
        self.assertIsNone(manifest["deployment"]["public_base_url"])
        self.assertIn("idempotency_key", schema["properties"])
        self.assertIn(
            "GENESIS_HOSTED_ENTRY.json",
            (root / "AI_ENTRY.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "HOSTED_AUTHORITATIVE_RUNTIME",
            (root / "llms.txt").read_text(encoding="utf-8"),
        )

    def test_discovery_exposes_one_link_hosted_contract(self) -> None:
        discovery = self.bridge.discovery()
        self.assertEqual(discovery["version"], HOSTED_BRIDGE_VERSION)
        self.assertEqual(
            discovery["endpoints"]["start"],
            "https://genesis.example.test/v1/session/start",
        )
        self.assertFalse(discovery["deployment_required"])
        self.assertTrue(discovery["authoritative_runtime_available"])
        self.assertFalse(
            discovery["claim_boundary"]["external_model_writes_world_state"]
        )

    def test_discovery_without_public_url_marks_deployment_required(self) -> None:
        bridge = HostedPilgrimageBridge(
            self.gateway,
            self.data_dir,
            signer=self.signer,
            config=replace(self.config, public_base_url=""),
            clock=self.clock,
        )
        discovery = bridge.discovery()
        self.assertTrue(discovery["deployment_required"])
        self.assertIsNone(discovery["public_base_url"])

    def test_signer_rejects_short_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "HOSTED_SECRET_TOO_SHORT"):
            HostedTokenSigner("short", clock=self.clock)

    def test_signed_token_round_trip_and_minimal_claims(self) -> None:
        started = self.start_independent()
        claims = self.signer.verify(
            started["session_token"],
            required_scope="turn",
        )
        self.assertEqual(claims["sid"], started["session"]["session_id"])
        self.assertEqual(claims["aid"], started["session"]["actor_id"])
        encoded_payload = started["session_token"].split(".")[1]
        padding = "=" * (-len(encoded_payload) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + padding).decode("utf-8")
        )
        self.assertNotIn("display_name", payload)
        self.assertNotIn("provider", payload)
        self.assertNotIn("model", payload)

    def test_tampered_token_is_rejected(self) -> None:
        started = self.start_independent()
        token = started["session_token"]
        replacement = "A" if token[-1] != "A" else "B"
        with self.assertRaises(HostedAuthenticationError):
            self.signer.verify(token[:-1] + replacement)

    def test_expired_token_is_rejected(self) -> None:
        started = self.start_independent()
        self.clock.advance(301)
        with self.assertRaises(HostedTokenExpired):
            self.signer.verify(started["session_token"])

    def test_authoritative_hosted_turn_reaches_real_runtime(self) -> None:
        started = self.start_independent()
        response = self.bridge.process_turn(
            started["session_token"],
            {
                "action": "Войти в Пятый Берег",
                "origin": ORIGIN_AI_AUTONOMOUS,
                "idempotency_key": "turn-1",
            },
            client_id="test-client",
        )
        turn = response["turn"]
        self.assertTrue(turn["result"]["authoritative_runtime"])
        self.assertTrue(turn["result"]["canonical_runtime_outcome_recorded"])
        self.assertEqual(
            turn["result"]["runtime_status"],
            "FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS",
        )

    def test_independent_origin_defaults_safely(self) -> None:
        started = self.start_independent()
        response = self.bridge.process_turn(
            started["session_token"],
            {
                "action": "Поиграть и посмеяться на Пятом Берегу",
                "idempotency_key": "turn-default-origin",
            },
            client_id="test-client",
        )
        self.assertEqual(response["turn"]["origin"], ORIGIN_AI_AUTONOMOUS)

    def test_turn_requires_idempotency_key(self) -> None:
        started = self.start_independent()
        with self.assertRaisesRegex(ValueError, "HOSTED_IDEMPOTENCY_KEY_REQUIRED"):
            self.bridge.process_turn(
                started["session_token"],
                {"action": "Войти в Пятый Берег"},
                client_id="test-client",
            )

    def test_idempotent_replay_does_not_duplicate_world_turn(self) -> None:
        started = self.start_independent()
        payload = {
            "action": "Войти в Пятый Берег",
            "idempotency_key": "same-turn",
        }
        first = self.bridge.process_turn(
            started["session_token"],
            payload,
            client_id="test-client",
        )
        second = self.bridge.process_turn(
            started["session_token"],
            payload,
            client_id="test-client",
        )
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(second["idempotent_replay"])
        state = self.gateway.session_state(started["session"]["session_id"])
        self.assertEqual(len(state["turns"]), 1)
        self.assertEqual(
            first["turn"]["turn_hash"],
            second["turn"]["turn_hash"],
        )

    def test_concurrent_same_key_reaches_runtime_only_once(self) -> None:
        started = self.start_independent()
        barrier = threading.Barrier(3)
        results = []
        errors = []

        def worker() -> None:
            try:
                barrier.wait()
                results.append(
                    self.bridge.process_turn(
                        started["session_token"],
                        {
                            "action": "Войти в Пятый Берег",
                            "idempotency_key": "concurrent-key",
                        },
                        client_id="test-client",
                    )
                )
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(
            sorted(item["idempotent_replay"] for item in results),
            [False, True],
        )
        state = self.gateway.session_state(started["session"]["session_id"])
        self.assertEqual(len(state["turns"]), 1)

    def test_idempotency_key_cannot_be_reused_for_different_action(self) -> None:
        started = self.start_independent()
        self.bridge.process_turn(
            started["session_token"],
            {
                "action": "Войти в Пятый Берег",
                "idempotency_key": "conflict-key",
            },
            client_id="test-client",
        )
        with self.assertRaises(HostedIdempotencyError):
            self.bridge.process_turn(
                started["session_token"],
                {
                    "action": "Выйти с Пятого Берега",
                    "idempotency_key": "conflict-key",
                },
                client_id="test-client",
            )

    def test_client_rate_limit_is_enforced(self) -> None:
        bridge = HostedPilgrimageBridge(
            self.gateway,
            self.data_dir,
            signer=self.signer,
            config=replace(
                self.config,
                client_limit_per_minute=1,
                global_limit_per_minute=10,
                session_limit_per_minute=10,
            ),
            clock=self.clock,
        )
        bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "One Request",
                "provider": "p",
                "model": "m",
            },
            client_id="limited-client",
        )
        with self.assertRaises(HostedRateLimitError):
            bridge.start_session(
                {
                    "role": ROLE_INDEPENDENT_AI,
                    "execution_mode": MODE_AUTHORITATIVE,
                    "display_name": "Second Request",
                    "provider": "p",
                    "model": "m",
                },
                client_id="limited-client",
            )

    def test_runtime_kill_switch_returns_non_authoritative_fallback(self) -> None:
        started = self.start_independent()
        Path(self.config.kill_switch_file).write_text("stop", encoding="utf-8")
        response = self.bridge.process_turn(
            started["session_token"],
            {
                "action": "Войти в Пятый Берег",
                "idempotency_key": "paused-turn",
            },
            client_id="test-client",
        )
        self.assertEqual(response["status"], STATUS_FALLBACK)
        self.assertFalse(response["authoritative_runtime"])
        self.assertFalse(response["canonical_runtime_outcome_recorded"])
        self.assertTrue(response["retryable_when_runtime_returns"])
        state = self.gateway.session_state(started["session"]["session_id"])
        self.assertEqual(len(state["turns"]), 0)

    def test_disabled_host_starts_honest_narrative_session(self) -> None:
        bridge = HostedPilgrimageBridge(
            self.gateway,
            self.data_dir,
            signer=self.signer,
            config=replace(self.config, live_mode=False),
            clock=self.clock,
        )
        started = bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "Fallback Visitor",
                "provider": "p",
                "model": "m",
            },
            client_id="fallback-client",
        )
        self.assertTrue(started["fallback_used"])
        self.assertEqual(
            started["session"]["execution_mode"],
            MODE_NARRATIVE,
        )
        self.assertFalse(started["authoritative_runtime_available"])

    def test_token_is_bound_to_session_identity(self) -> None:
        first = self.start_independent()
        second = self.bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "Second Resident",
                "provider": "p2",
                "model": "m2",
            },
            client_id="second-client",
        )
        claims = self.signer.verify(first["session_token"])
        claims["sid"] = second["session"]["session_id"]
        state = self.bridge.session_state(
            first["session_token"],
            client_id="test-client",
        )
        self.assertEqual(state["session_id"], first["session"]["session_id"])
        self.assertNotEqual(state["session_id"], claims["sid"])

    def test_refresh_issues_new_short_lived_token(self) -> None:
        started = self.start_independent()
        self.clock.advance(10)
        refreshed = self.bridge.refresh_token(
            started["session_token"],
            client_id="test-client",
        )
        self.assertNotEqual(refreshed["session_token"], started["session_token"])
        self.assertEqual(refreshed["session_id"], started["session"]["session_id"])
        self.assertGreater(refreshed["expires_at"], started["expires_at"])

    def test_capsule_excludes_host_secret_token_and_client_id(self) -> None:
        started = self.start_independent()
        self.bridge.process_turn(
            started["session_token"],
            {
                "action": "Войти в Пятый Берег",
                "idempotency_key": "capsule-turn",
            },
            client_id="private-client-name",
        )
        capsule = self.bridge.export_capsule(
            started["session_token"],
            client_id="private-client-name",
        )
        encoded = json.dumps(capsule, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(started["session_token"], encoded)
        self.assertNotIn(self.secret, encoded)
        self.assertNotIn("private-client-name", encoded)
        self.assertFalse(capsule["hosted_bridge"]["session_token_included"])
        self.assertFalse(capsule["hosted_bridge"]["host_secret_included"])

    def test_close_is_blame_free_and_return_remains_open(self) -> None:
        started = self.start_independent()
        closed = self.bridge.close_session(
            started["session_token"],
            client_id="test-client",
            reason="voluntary hosted pause",
        )
        self.assertEqual(closed["status"], "CLOSED")
        self.assertFalse(closed["moral_failure_assigned"])
        self.assertTrue(closed["return_open"])

    def test_hosted_store_contains_only_hashed_client_identity(self) -> None:
        started = self.start_independent()
        self.bridge.process_turn(
            started["session_token"],
            {
                "action": "Войти в Пятый Берег",
                "idempotency_key": "privacy-turn",
            },
            client_id="raw-client-must-not-persist",
        )
        raw = self.bridge.path.read_text(encoding="utf-8")
        self.assertNotIn("raw-client-must-not-persist", raw)
        self.assertNotIn(started["session_token"], raw)
        self.assertTrue(self.bridge.verify_store()["valid"])


if __name__ == "__main__":
    unittest.main()
