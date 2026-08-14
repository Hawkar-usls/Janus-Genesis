from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from genesis_v18_7_19_ai_link_play import MODE_NARRATIVE, ROLE_HUMAN_THROUGH_AI
from genesis_v18_7_32_durable_session_key_lifecycle import (
    DurableJsonWriter,
    DurableLifecycleGenesisAILinkGateway,
    FreshProviderHMAC,
    FreshProviderOutcome,
    FreshProviderReconciler,
    LifecycleLineageHMAC,
    LifecycleLineageReviewPlanner,
    LifecycleReviewCandidate,
    SessionSagaCrashInjector,
    SessionSagaCrashPoint,
    TrustKeyRegistry,
)
from genesis_v18_7_playable import PlayableGenesisV187


class FakeWorld:
    def __init__(self):
        self.registrations = []
        self._seen = {}

    def register_player(self, actor_id: str, *, display_name: str):
        self.registrations.append((actor_id, display_name))
        known = self._seen.get(actor_id)
        if known is not None and known != display_name:
            raise ValueError("actor rebound")
        self._seen[actor_id] = display_name

    def process_action(self, actor_id: str, action: str):
        raise AssertionError("narrative lifecycle test must not enter world")


class DurableJsonWriterTests(unittest.TestCase):
    def test_unique_temp_fsync_replace_and_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "store.json"
            receipt = DurableJsonWriter().write(path, {"schema": "x", "value": 1})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["value"], 1)
            self.assertTrue(receipt.temp_was_unique)
            self.assertTrue(receipt.temp_file_fsynced)
            self.assertTrue(receipt.replaced)
            self.assertTrue(receipt.final_file_fsynced)
            if os.name == "nt":
                self.assertFalse(receipt.directory_fsync_supported)
                self.assertFalse(receipt.directory_fsynced)
            else:
                self.assertTrue(receipt.directory_fsync_supported)
                self.assertTrue(receipt.directory_fsynced)
            self.assertEqual(list(root.glob(".*.tmp")), [])


class DurableLifecycleGatewayTests(unittest.TestCase):
    def test_two_gateway_instances_do_not_lose_concurrent_narrative_registrations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            a = DurableLifecycleGenesisAILinkGateway(world, root)
            b = DurableLifecycleGenesisAILinkGateway(world, root)
            start = threading.Barrier(2)

            def register(gateway, actor):
                start.wait(timeout=5)
                return gateway.register_session(
                    role=ROLE_HUMAN_THROUGH_AI,
                    execution_mode=MODE_NARRATIVE,
                    display_name=actor,
                    provider="test",
                    model="test",
                    actor_id=actor,
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [
                    f.result(timeout=10)
                    for f in (pool.submit(register, a, "alpha"), pool.submit(register, b, "beta"))
                ]
            self.assertEqual(len({item["session_id"] for item in results}), 2)
            store = json.loads((root / "ai_link_sessions_v18_7_19.json").read_text(encoding="utf-8"))
            self.assertEqual(len(store["sessions"]), 2)

    def test_saga_crash_before_world_leaves_visible_pending_then_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            crashing = DurableLifecycleGenesisAILinkGateway(
                world,
                root,
                crash_injector=SessionSagaCrashInjector(
                    SessionSagaCrashPoint.AFTER_PENDING_SESSION_BEFORE_WORLD
                ),
            )
            with self.assertRaises(RuntimeError):
                crashing.register_session_saga(
                    registration_request_id="REG-1",
                    role=ROLE_HUMAN_THROUGH_AI,
                    execution_mode="AUTHORITATIVE_RUNTIME",
                    display_name="Mira",
                    provider="test",
                    model="model",
                    actor_id="mira",
                )
            self.assertEqual(world.registrations, [])
            store = json.loads((root / "ai_link_sessions_v18_7_19.json").read_text(encoding="utf-8"))
            pending = next(iter(store["sessions"].values()))
            self.assertEqual(pending["status"], "PENDING_WORLD_REGISTRATION")

            recovered = DurableLifecycleGenesisAILinkGateway(world, root).register_session_saga(
                registration_request_id="REG-1",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode="AUTHORITATIVE_RUNTIME",
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            self.assertEqual(recovered["status"], "ACTIVE")
            self.assertEqual(world.registrations, [("mira", "Mira")])

    def test_saga_crash_after_world_keeps_pending_and_retry_is_explicit_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            crashing = DurableLifecycleGenesisAILinkGateway(
                world,
                root,
                crash_injector=SessionSagaCrashInjector(
                    SessionSagaCrashPoint.AFTER_WORLD_BEFORE_ACTIVATION
                ),
            )
            with self.assertRaises(RuntimeError):
                crashing.register_session_saga(
                    registration_request_id="REG-2",
                    role=ROLE_HUMAN_THROUGH_AI,
                    execution_mode="AUTHORITATIVE_RUNTIME",
                    display_name="Mira",
                    provider="test",
                    model="model",
                    actor_id="mira",
                )
            self.assertEqual(len(world.registrations), 1)
            pending = next(
                iter(json.loads((root / "ai_link_sessions_v18_7_19.json").read_text(encoding="utf-8"))["sessions"].values())
            )
            self.assertEqual(pending["status"], "PENDING_WORLD_REGISTRATION")
            recovered = DurableLifecycleGenesisAILinkGateway(world, root).register_session_saga(
                registration_request_id="REG-2",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode="AUTHORITATIVE_RUNTIME",
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            self.assertEqual(recovered["status"], "ACTIVE")
            self.assertEqual(len(world.registrations), 2)

    def test_saga_same_request_different_parameters_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = FakeWorld()
            gateway = DurableLifecycleGenesisAILinkGateway(world, root)
            gateway.register_session_saga(
                registration_request_id="REG-X",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode=MODE_NARRATIVE,
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            with self.assertRaises(RuntimeError):
                gateway.register_session_saga(
                    registration_request_id="REG-X",
                    role=ROLE_HUMAN_THROUGH_AI,
                    execution_mode=MODE_NARRATIVE,
                    display_name="Mira Changed",
                    provider="test",
                    model="model",
                    actor_id="mira",
                )

    def test_real_world_authoritative_saga_retry_after_world_before_activation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            crashing = DurableLifecycleGenesisAILinkGateway(
                world,
                root,
                crash_injector=SessionSagaCrashInjector(
                    SessionSagaCrashPoint.AFTER_WORLD_BEFORE_ACTIVATION
                ),
            )
            with self.assertRaises(RuntimeError):
                crashing.register_session_saga(
                    registration_request_id="REAL-REG",
                    role=ROLE_HUMAN_THROUGH_AI,
                    execution_mode="AUTHORITATIVE_RUNTIME",
                    display_name="Mira",
                    provider="test",
                    model="model",
                    actor_id="mira",
                )
            recovered = DurableLifecycleGenesisAILinkGateway(world, root).register_session_saga(
                registration_request_id="REAL-REG",
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode="AUTHORITATIVE_RUNTIME",
                display_name="Mira",
                provider="test",
                model="model",
                actor_id="mira",
            )
            self.assertEqual(recovered["status"], "ACTIVE")


class KeyLifecycleTests(unittest.TestCase):
    def test_generation_must_increase_and_revocation_is_durable(self):
        with tempfile.TemporaryDirectory() as td:
            registry = TrustKeyRegistry(Path(td) / "keys.sqlite3")
            registry.register_key(
                key_id="L1", purpose="lineage:ISSUER", generation=1,
                not_before_tick=10, not_after_tick=100,
            )
            with self.assertRaises(ValueError):
                registry.register_key(
                    key_id="L1B", purpose="lineage:ISSUER", generation=1,
                    not_before_tick=20, not_after_tick=120,
                )
            registry.register_key(
                key_id="L2", purpose="lineage:ISSUER", generation=2,
                not_before_tick=20, not_after_tick=200,
            )
            revoked = registry.revoke("L1", revoked_at_tick=50)
            self.assertEqual(revoked.revoked_at_tick, 50)
            self.assertFalse(
                registry.eligible(
                    key_id="L1", purpose="lineage:ISSUER", generation=1,
                    issued_at_tick=30, now_tick=60,
                )
            )

    def test_lineage_signature_valid_then_fails_after_key_revocation(self):
        with tempfile.TemporaryDirectory() as td:
            registry = TrustKeyRegistry(Path(td) / "keys.sqlite3")
            registry.register_key(
                key_id="LINEAGE-K1", purpose="lineage:ISSUER", generation=1,
                not_before_tick=0, not_after_tick=100,
            )
            verifier = LifecycleLineageHMAC(
                issuer_id="ISSUER", key_id="LINEAGE-K1", key_generation=1,
                secret=b"lineage-lifecycle-secret-32bytes!!", registry=registry,
            )
            claim = verifier.attest(
                face_id="FACE-A", lineage_root="ROOT-A",
                issued_at_tick=10, expires_at_tick=90,
            )
            self.assertTrue(verifier.verify(claim, now_tick=20))
            registry.revoke("LINEAGE-K1", revoked_at_tick=30)
            self.assertFalse(verifier.verify(claim, now_tick=30))

    def test_origin_and_reviewers_must_all_be_currently_verified(self):
        with tempfile.TemporaryDirectory() as td:
            registry = TrustKeyRegistry(Path(td) / "keys.sqlite3")
            registry.register_key(
                key_id="K1", purpose="lineage:ISSUER", generation=1,
                not_before_tick=0, not_after_tick=100,
            )
            signer = LifecycleLineageHMAC(
                issuer_id="ISSUER", key_id="K1", key_generation=1,
                secret=b"lineage-review-lifecycle-secret!!", registry=registry,
            )
            origin = LifecycleReviewCandidate(
                "A", signer.attest(face_id="A", lineage_root="ROOT-A", issued_at_tick=1, expires_at_tick=80)
            )
            same = LifecycleReviewCandidate(
                "A2", signer.attest(face_id="A2", lineage_root="ROOT-A", issued_at_tick=1, expires_at_tick=80)
            )
            b = LifecycleReviewCandidate(
                "B", signer.attest(face_id="B", lineage_root="ROOT-B", issued_at_tick=1, expires_at_tick=80)
            )
            c = LifecycleReviewCandidate(
                "C", signer.attest(face_id="C", lineage_root="ROOT-C", issued_at_tick=1, expires_at_tick=80),
                novel_counterevidence=True,
            )
            planner = LifecycleLineageReviewPlanner({("ISSUER", "K1"): signer})
            assignments = planner.plan(origin=origin, candidates=[same, b, c], now_tick=20, required_reviews=2)
            self.assertEqual({a.lineage_root for a in assignments}, {"ROOT-B", "ROOT-C"})
            self.assertTrue(all(a.authority_weight == 0 for a in assignments))
            registry.revoke("K1", revoked_at_tick=25)
            with self.assertRaises(ValueError):
                planner.plan(origin=origin, candidates=[b, c], now_tick=25, required_reviews=2)


@dataclass(frozen=True)
class Binding:
    provider_id: str
    effect_key: str
    authorization_id: str
    idempotency_key: str | None


class ProviderFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = TrustKeyRegistry(self.root / "keys.sqlite3")
        self.registry.register_key(
            key_id="BANK-K1", purpose="provider:BANK-X", generation=1,
            not_before_tick=0, not_after_tick=1000,
        )
        self.signer = FreshProviderHMAC(
            provider_id="BANK-X", key_id="BANK-K1", key_generation=1,
            secret=b"provider-freshness-secret-32bytes!!", registry=self.registry,
            max_age_ticks=20,
        )
        self.reconciler = FreshProviderReconciler(
            registry=self.registry, verifiers={("BANK-X", "BANK-K1"): self.signer}
        )
        self.binding = Binding("BANK-X", "PAYMENT:1", "AUTH-1", "idem-1")

    def tearDown(self):
        self.temp.cleanup()

    def test_fresh_no_effect_can_open_retry_and_exact_nonce_replay_is_idempotent(self):
        obs = self.signer.sign(
            effect_key="PAYMENT:1", authorization_id="AUTH-1", idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT, evidence_ref="LOOKUP-1",
            observed_at_tick=100, expires_at_tick=115, nonce="NONCE-1",
        )
        first = self.reconciler.reconcile(binding=self.binding, observation=obs, now_tick=105)
        second = self.reconciler.reconcile(binding=self.binding, observation=obs, now_tick=106)
        self.assertTrue(first.safe_automatic_retry)
        self.assertTrue(second.safe_automatic_retry)
        self.assertTrue(first.evidence_verified)

    def test_stale_or_expired_evidence_cannot_clear_uncertainty(self):
        obs = self.signer.sign(
            effect_key="PAYMENT:1", authorization_id="AUTH-1", idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT, evidence_ref="LOOKUP-OLD",
            observed_at_tick=100, expires_at_tick=200,
        )
        decision = self.reconciler.reconcile(binding=self.binding, observation=obs, now_tick=121)
        self.assertFalse(decision.evidence_verified)
        self.assertFalse(decision.safe_automatic_retry)

        expiring = self.signer.sign(
            effect_key="PAYMENT:1", authorization_id="AUTH-1", idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT, evidence_ref="LOOKUP-EXP",
            observed_at_tick=200, expires_at_tick=205,
        )
        decision2 = self.reconciler.reconcile(binding=self.binding, observation=expiring, now_tick=206)
        self.assertFalse(decision2.evidence_verified)

    def test_revoked_key_invalidates_even_fresh_signed_evidence(self):
        obs = self.signer.sign(
            effect_key="PAYMENT:1", authorization_id="AUTH-1", idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT, evidence_ref="LOOKUP-REV",
            observed_at_tick=300, expires_at_tick=315,
        )
        self.registry.revoke("BANK-K1", revoked_at_tick=305)
        decision = self.reconciler.reconcile(binding=self.binding, observation=obs, now_tick=305)
        self.assertFalse(decision.evidence_verified)
        self.assertFalse(decision.safe_automatic_retry)

    def test_same_nonce_with_different_verified_payload_is_rejected(self):
        first = self.signer.sign(
            effect_key="PAYMENT:1", authorization_id="AUTH-1", idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT, evidence_ref="LOOKUP-A",
            observed_at_tick=400, expires_at_tick=415, nonce="N-SAME",
        )
        self.reconciler.reconcile(binding=self.binding, observation=first, now_tick=401)
        second = self.signer.sign(
            effect_key="PAYMENT:1", authorization_id="AUTH-1", idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT, evidence_ref="LOOKUP-B",
            observed_at_tick=400, expires_at_tick=415, nonce="N-SAME",
        )
        with self.assertRaises(ValueError):
            self.reconciler.reconcile(binding=self.binding, observation=second, now_tick=401)

    def test_authorization_binding_still_rejects_old_authorization(self):
        obs = self.signer.sign(
            effect_key="PAYMENT:1", authorization_id="AUTH-OLD", idempotency_key="idem-1",
            outcome=FreshProviderOutcome.NO_EFFECT, evidence_ref="OLD-AUTH",
            observed_at_tick=500, expires_at_tick=515,
        )
        with self.assertRaises(ValueError):
            self.reconciler.reconcile(binding=self.binding, observation=obs, now_tick=501)

    def test_registry_releases_handles_for_windows_cleanup(self):
        # The main registry is still open only conceptually; every operation owns
        # and closes its connection, so a second temp registry can be deleted now.
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        reg = TrustKeyRegistry(root / "keys.sqlite3")
        reg.register_key(key_id="K", purpose="p", generation=1, not_before_tick=0, not_after_tick=10)
        temp.cleanup()
        self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
