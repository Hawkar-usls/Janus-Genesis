from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from genesis_v18_7_19_ai_link_play import MODE_NARRATIVE, ROLE_HUMAN_THROUGH_AI
from genesis_v18_7_32_durable_session_key_lifecycle import (
    DurableJsonWriter,
    FreshProviderOutcome,
    FreshProviderReconciler,
    LifecycleLineageHMAC,
    SessionSagaCrashInjector,
    SessionSagaCrashPoint,
    TrustKeyRegistry,
)
from genesis_v18_7_34_registration_binding_fresh_evidence_fix import (
    BoundRegistrationLifecycleGateway,
    FreshProviderHMACV2,
    RegistrationRequestConflict,
    RegistrationRequestRegistry,
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


class RegistrationRequestBindingTests(unittest.TestCase):
    def test_same_registration_request_different_parameters_fails_at_request_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gateway = BoundRegistrationLifecycleGateway(FakeWorld(), root)
            gateway.register_session_saga(
                registration_request_id="REG-X",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode=MODE_NARRATIVE,
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            with self.assertRaises(RegistrationRequestConflict):
                gateway.register_session_saga(
                    registration_request_id="REG-X",
                    role=ROLE_HUMAN_THROUGH_AI,
                    execution_mode=MODE_NARRATIVE,
                    display_name="Mira Changed",
                    provider="test",
                    model="model",
                    actor_id="mira",
                )

    def test_same_registration_request_same_parameters_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            gateway = BoundRegistrationLifecycleGateway(FakeWorld(), root)
            kwargs = dict(
                registration_request_id="REG-SAME",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode=MODE_NARRATIVE,
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            first = gateway.register_session_saga(**kwargs)
            second = gateway.register_session_saga(**kwargs)
            self.assertEqual(first["session_id"], second["session_id"])
            binding = gateway.registration_requests.get("REG-SAME")
            self.assertEqual(binding.session_id, first["session_id"])

    def test_crash_after_world_before_activation_recovers_under_same_bound_request(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            kwargs = dict(
                registration_request_id="REG-CRASH",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode="AUTHORITATIVE_RUNTIME",
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            crashing = BoundRegistrationLifecycleGateway(
                world,
                root,
                crash_injector=SessionSagaCrashInjector(
                    SessionSagaCrashPoint.AFTER_WORLD_BEFORE_ACTIVATION
                ),
            )
            with self.assertRaises(RuntimeError):
                crashing.register_session_saga(**kwargs)
            self.assertEqual(len(world.registrations), 1)
            recovered = BoundRegistrationLifecycleGateway(world, root).register_session_saga(**kwargs)
            self.assertEqual(recovered["status"], "ACTIVE")
            self.assertEqual(len(world.registrations), 2)

    def test_real_genesis_registration_recovery_preserves_request_binding(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            kwargs = dict(
                registration_request_id="REAL-REG-V34",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode="AUTHORITATIVE_RUNTIME",
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            crashing = BoundRegistrationLifecycleGateway(
                world,
                root,
                crash_injector=SessionSagaCrashInjector(
                    SessionSagaCrashPoint.AFTER_WORLD_BEFORE_ACTIVATION
                ),
            )
            with self.assertRaises(RuntimeError):
                crashing.register_session_saga(**kwargs)
            recovered = BoundRegistrationLifecycleGateway(world, root).register_session_saga(**kwargs)
            self.assertEqual(recovered["status"], "ACTIVE")
            self.assertEqual(
                recovered["session_id"],
                BoundRegistrationLifecycleGateway(world, root).register_session_saga(**kwargs)["session_id"],
            )

    def test_registration_registry_releases_windows_handles(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        registry = RegistrationRequestRegistry(root / "registration.sqlite3")
        registry.bind(
            registration_request_id="R",
            registration_hash="ab" * 32,
            session_id="session-1",
        )
        self.assertIsNotNone(registry.get("R"))
        temp.cleanup()
        self.assertFalse(root.exists())


@dataclass(frozen=True)
class Binding:
    provider_id: str
    effect_key: str
    authorization_id: str
    idempotency_key: str | None


class TypedFreshProviderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = TrustKeyRegistry(self.root / "keys.sqlite3")
        self.registry.register_key(
            key_id="BANK-K1",
            purpose="provider:BANK-X",
            generation=1,
            not_before_tick=0,
            not_after_tick=1000,
        )
        self.signer = FreshProviderHMACV2(
            provider_id="BANK-X",
            key_id="BANK-K1",
            key_generation=1,
            secret=b"typed-provider-freshness-secret!!",
            registry=self.registry,
            max_age_ticks=20,
        )
        self.reconciler = FreshProviderReconciler(
            registry=self.registry,
            verifiers={("BANK-X", "BANK-K1"): self.signer},
        )
        self.binding = Binding("BANK-X", "PAYMENT:1", "AUTH-1", "idem-1")

    def tearDown(self):
        self.temp.cleanup()

    def observation(self, **overrides):
        values = dict(
            effect_key="PAYMENT:1",
            authorization_id="AUTH-1",
            idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT,
            evidence_ref="LOOKUP-1",
            observed_at_tick=100,
            expires_at_tick=115,
            nonce="NONCE-1",
        )
        values.update(overrides)
        return self.signer.sign(**values)

    def test_typed_outcome_verifies_and_no_effect_opens_retry(self):
        obs = self.observation()
        self.assertIs(obs.outcome, FreshProviderOutcome.NO_EFFECT)
        decision = self.reconciler.reconcile(
            binding=self.binding, observation=obs, now_tick=105
        )
        self.assertTrue(decision.evidence_verified)
        self.assertTrue(decision.safe_automatic_retry)
        self.assertEqual(decision.state, "NO_EFFECT_BY_FRESH_AUTHORIZATION_BOUND_EVIDENCE")

    def test_exact_nonce_replay_is_idempotent_but_payload_substitution_is_rejected(self):
        first = self.observation()
        self.reconciler.reconcile(binding=self.binding, observation=first, now_tick=105)
        again = self.reconciler.reconcile(binding=self.binding, observation=first, now_tick=106)
        self.assertTrue(again.evidence_verified)
        substituted = self.observation(evidence_ref="LOOKUP-OTHER")
        with self.assertRaises(ValueError):
            self.reconciler.reconcile(
                binding=self.binding, observation=substituted, now_tick=106
            )

    def test_stale_evidence_cannot_clear_uncertainty(self):
        obs = self.observation(expires_at_tick=200)
        decision = self.reconciler.reconcile(
            binding=self.binding, observation=obs, now_tick=121
        )
        self.assertFalse(decision.evidence_verified)
        self.assertFalse(decision.safe_automatic_retry)

    def test_revoked_key_invalidates_fresh_evidence(self):
        obs = self.observation(observed_at_tick=300, expires_at_tick=315, nonce="N-REV")
        self.registry.revoke("BANK-K1", revoked_at_tick=305)
        decision = self.reconciler.reconcile(
            binding=self.binding, observation=obs, now_tick=305
        )
        self.assertFalse(decision.evidence_verified)

    def test_old_authorization_is_rejected_structurally(self):
        obs = self.observation(authorization_id="AUTH-OLD", nonce="N-AUTH")
        with self.assertRaises(ValueError):
            self.reconciler.reconcile(
                binding=self.binding, observation=obs, now_tick=105
            )


class PreservedV32PrimitiveTests(unittest.TestCase):
    def test_durable_writer_still_reports_file_and_directory_claim_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "store.json"
            receipt = DurableJsonWriter().write(path, {"schema": "v34", "ok": True})
            self.assertTrue(receipt.temp_file_fsynced)
            self.assertTrue(receipt.final_file_fsynced)

    def test_lineage_key_revocation_still_fails_current_verification(self):
        with tempfile.TemporaryDirectory() as td:
            registry = TrustKeyRegistry(Path(td) / "keys.sqlite3")
            registry.register_key(
                key_id="LINEAGE-K1",
                purpose="lineage:ISSUER",
                generation=1,
                not_before_tick=0,
                not_after_tick=100,
            )
            verifier = LifecycleLineageHMAC(
                issuer_id="ISSUER",
                key_id="LINEAGE-K1",
                key_generation=1,
                secret=b"lineage-v34-secret-32bytes!!",
                registry=registry,
            )
            claim = verifier.attest(
                face_id="A",
                lineage_root="ROOT-A",
                issued_at_tick=10,
                expires_at_tick=90,
            )
            self.assertTrue(verifier.verify(claim, now_tick=20))
            registry.revoke("LINEAGE-K1", revoked_at_tick=30)
            self.assertFalse(verifier.verify(claim, now_tick=30))


if __name__ == "__main__":
    unittest.main()
