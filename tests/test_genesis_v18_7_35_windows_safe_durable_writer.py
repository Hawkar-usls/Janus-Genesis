from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_ai_link_play import MODE_NARRATIVE, ROLE_HUMAN_THROUGH_AI
from genesis_v18_7_32_durable_session_key_lifecycle import (
    FreshProviderOutcome,
    FreshProviderReconciler,
    SessionSagaCrashInjector,
    SessionSagaCrashPoint,
    TrustKeyRegistry,
)
from genesis_v18_7_34_registration_binding_fresh_evidence_fix import (
    FreshProviderHMACV2,
    RegistrationRequestConflict,
)
from genesis_v18_7_35_windows_safe_durable_writer import (
    WindowsSafeBoundRegistrationLifecycleGateway,
    WindowsSafeDurableJsonWriter,
)
from genesis_v18_7_playable import PlayableGenesisV187


class FakeWorld:
    def __init__(self):
        self.registrations = []
        self.seen = {}

    def register_player(self, actor_id: str, *, display_name: str):
        self.registrations.append((actor_id, display_name))
        known = self.seen.get(actor_id)
        if known is not None and known != display_name:
            raise ValueError("actor rebound")
        self.seen[actor_id] = display_name

    def process_action(self, actor_id: str, action: str):
        raise AssertionError("registration test must not process a turn")


class WindowsSafeDurableWriterTests(unittest.TestCase):
    def test_final_file_fsync_uses_portable_descriptor_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "state.json"
            receipt = WindowsSafeDurableJsonWriter().write(
                path, {"schema": "v35", "value": 1}
            )
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["value"], 1)
            self.assertTrue(receipt.temp_was_unique)
            self.assertTrue(receipt.temp_file_fsynced)
            self.assertTrue(receipt.final_file_fsynced)
            if os.name == "nt":
                self.assertFalse(receipt.directory_fsync_supported)
                self.assertFalse(receipt.directory_fsynced)
            else:
                self.assertTrue(receipt.directory_fsync_supported)
                self.assertTrue(receipt.directory_fsynced)

    def test_writer_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            WindowsSafeDurableJsonWriter().write(root / "x.json", {"x": 1})
            leftovers = [p for p in root.iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [])


class WindowsSafeRegistrationSagaTests(unittest.TestCase):
    @staticmethod
    def narrative_kwargs(**overrides):
        values = dict(
            registration_request_id="REG-1",
            role=ROLE_HUMAN_THROUGH_AI,
            execution_mode=MODE_NARRATIVE,
            display_name="Mira",
            provider="test",
            model="model",
            actor_id="mira",
        )
        values.update(overrides)
        return values

    def test_request_binding_conflict_is_rejected_before_second_session_creation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gateway = WindowsSafeBoundRegistrationLifecycleGateway(FakeWorld(), root)
            first = gateway.register_session_saga(**self.narrative_kwargs())
            with self.assertRaises(RegistrationRequestConflict):
                gateway.register_session_saga(
                    **self.narrative_kwargs(display_name="Changed")
                )
            store = json.loads((root / "ai_link_sessions_v18_7_19.json").read_text(encoding="utf-8"))
            self.assertEqual(len(store["sessions"]), 1)
            self.assertIn(first["session_id"], store["sessions"])

    def test_same_request_same_parameters_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gateway = WindowsSafeBoundRegistrationLifecycleGateway(FakeWorld(), root)
            first = gateway.register_session_saga(**self.narrative_kwargs())
            second = gateway.register_session_saga(**self.narrative_kwargs())
            self.assertEqual(first["session_id"], second["session_id"])

    def test_fake_world_crash_after_world_before_activation_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            kwargs = self.narrative_kwargs(
                registration_request_id="REG-CRASH",
                execution_mode="AUTHORITATIVE_RUNTIME",
            )
            crashing = WindowsSafeBoundRegistrationLifecycleGateway(
                world,
                root,
                crash_injector=SessionSagaCrashInjector(
                    SessionSagaCrashPoint.AFTER_WORLD_BEFORE_ACTIVATION
                ),
            )
            with self.assertRaises(RuntimeError):
                crashing.register_session_saga(**kwargs)
            recovered = WindowsSafeBoundRegistrationLifecycleGateway(
                world, root
            ).register_session_saga(**kwargs)
            self.assertEqual(recovered["status"], "ACTIVE")
            self.assertEqual(len(world.registrations), 2)

    def test_real_world_registration_recovery_cross_platform(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            kwargs = self.narrative_kwargs(
                registration_request_id="REAL-V35",
                execution_mode="AUTHORITATIVE_RUNTIME",
            )
            crashing = WindowsSafeBoundRegistrationLifecycleGateway(
                world,
                root,
                crash_injector=SessionSagaCrashInjector(
                    SessionSagaCrashPoint.AFTER_WORLD_BEFORE_ACTIVATION
                ),
            )
            with self.assertRaises(RuntimeError):
                crashing.register_session_saga(**kwargs)
            recovered = WindowsSafeBoundRegistrationLifecycleGateway(
                world, root
            ).register_session_saga(**kwargs)
            self.assertEqual(recovered["status"], "ACTIVE")


class TypedFreshEvidenceRegressionTests(unittest.TestCase):
    def test_v34_typed_no_effect_and_key_revocation_survive_v35(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            registry = TrustKeyRegistry(root / "keys.sqlite3")
            registry.register_key(
                key_id="BANK-K1",
                purpose="provider:BANK-X",
                generation=1,
                not_before_tick=0,
                not_after_tick=1000,
            )
            signer = FreshProviderHMACV2(
                provider_id="BANK-X",
                key_id="BANK-K1",
                key_generation=1,
                secret=b"v35-provider-secret-32bytes!!",
                registry=registry,
                max_age_ticks=20,
            )

            class Binding:
                provider_id = "BANK-X"
                effect_key = "PAYMENT:1"
                authorization_id = "AUTH-1"
                idempotency_key = "idem-1"

            reconciler = FreshProviderReconciler(
                registry=registry,
                verifiers={("BANK-X", "BANK-K1"): signer},
            )
            observation = signer.sign(
                effect_key="PAYMENT:1",
                authorization_id="AUTH-1",
                idempotency_key="idem-1",
                outcome=FreshProviderOutcome.NO_EFFECT,
                evidence_ref="LOOKUP",
                observed_at_tick=100,
                expires_at_tick=115,
                nonce="V35-NONCE",
            )
            decision = reconciler.reconcile(
                binding=Binding(), observation=observation, now_tick=105
            )
            self.assertTrue(decision.evidence_verified)
            self.assertTrue(decision.safe_automatic_retry)
            registry.revoke("BANK-K1", revoked_at_tick=106)
            after_revoke = reconciler.reconcile(
                binding=Binding(), observation=observation, now_tick=106
            )
            self.assertFalse(after_revoke.evidence_verified)
            self.assertFalse(after_revoke.safe_automatic_retry)


if __name__ == "__main__":
    unittest.main()
