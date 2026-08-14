from __future__ import annotations

import json
import multiprocessing
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

from genesis_v18_7_28_client_ledger_attestation import (
    AttestedReviewCandidate,
    ClientRequestConflict,
    ControlledClientExecutor,
    HMACLineageAttestor,
    HMACProviderEvidenceVerifier,
    IndependentAttestedReviewUnavailable,
    LifecycleSerializedGateway,
    LineageAttestationError,
    PersistentClientRequestLedger,
    ProviderEvidenceContractError,
    VerifiedLineageReviewPlanner,
    VerifiedProviderLookupReconciler,
    VerifiedProviderOutcome,
)
from janus_portable_lock import PortableProcessLock


def _hold_process_lock(path: str, ready, release) -> None:
    lock = PortableProcessLock(path)
    with lock.exclusive():
        ready.set()
        release.wait(10)


class PortableLockTests(unittest.TestCase):
    def test_process_contention_is_visible_across_spawned_process(self):
        with tempfile.TemporaryDirectory() as td:
            lock_path = str(Path(td) / "portable.lock")
            ctx = multiprocessing.get_context("spawn")
            ready = ctx.Event()
            release = ctx.Event()
            proc = ctx.Process(target=_hold_process_lock, args=(lock_path, ready, release))
            proc.start()
            try:
                self.assertTrue(ready.wait(10), "child never acquired lock")
                probe = PortableProcessLock(lock_path)
                self.assertFalse(probe.try_acquire())
            finally:
                release.set()
                proc.join(10)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(5)
            self.assertEqual(proc.exitcode, 0)
            self.assertTrue(PortableProcessLock(lock_path).try_acquire())


class RecordingRuntime:
    def __init__(self, *, fail_first: bool = False):
        self.fail_first = fail_first
        self.calls = []

    def execute(self, *, actor_id: str, action: str, request_id: str):
        self.calls.append((actor_id, action, request_id))
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("simulated crash boundary before outer settlement")
        return {"status": "OK", "actor_id": actor_id, "request_id": request_id}


class PersistentClientRequestLedgerTests(unittest.TestCase):
    def test_same_caller_request_reuses_runtime_identity_but_cannot_change_action(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = PersistentClientRequestLedger(Path(td) / "client-requests.sqlite3")
            first = ledger.bind(
                client_id="cli-main",
                request_id="REQ-77",
                actor_id="mira",
                action="создать сад",
            )
            again = ledger.bind(
                client_id="cli-main",
                request_id="REQ-77",
                actor_id="mira",
                action="создать сад",
            )
            self.assertEqual(first.runtime_request_id, again.runtime_request_id)
            with self.assertRaises(ClientRequestConflict):
                ledger.bind(
                    client_id="cli-main",
                    request_id="REQ-77",
                    actor_id="mira",
                    action="создать мост",
                )

    def test_request_namespace_includes_client_identity(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = PersistentClientRequestLedger(Path(td) / "client-requests.sqlite3")
            a = ledger.bind(client_id="client-a", request_id="1", actor_id="mira", action="x")
            b = ledger.bind(client_id="client-b", request_id="1", actor_id="mira", action="x")
            self.assertNotEqual(a.runtime_request_id, b.runtime_request_id)

    def test_failed_outer_call_keeps_bound_identity_for_retry(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = PersistentClientRequestLedger(Path(td) / "client-requests.sqlite3")
            runtime = RecordingRuntime(fail_first=True)
            executor = ControlledClientExecutor(ledger=ledger, runtime=runtime)
            with self.assertRaises(RuntimeError):
                executor.execute(
                    client_id="cli-main",
                    request_id="REQ-88",
                    actor_id="mira",
                    action="создать музыку",
                )
            bound = ledger.get(client_id="cli-main", request_id="REQ-88")
            self.assertIsNotNone(bound)
            self.assertEqual(bound.state, "BOUND")

            result = executor.execute(
                client_id="cli-main",
                request_id="REQ-88",
                actor_id="mira",
                action="создать музыку",
            )
            self.assertEqual(result["status"], "OK")
            self.assertEqual(runtime.calls[0][2], runtime.calls[1][2])
            settled = ledger.get(client_id="cli-main", request_id="REQ-88")
            self.assertEqual(settled.state, "SETTLED")
            self.assertIsNotNone(settled.result_sha256)


class UnsafeFileGateway:
    """Deliberately racy store used to prove the wrapper owns one lock domain."""

    def __init__(self, path: Path, start: threading.Barrier):
        self.path = path
        self.start = start

    def _mutate(self, kind: str):
        self.start.wait(timeout=5)
        if self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            state = {"count": 0, "events": []}
        current = state["count"]
        time.sleep(0.05)
        state["count"] = current + 1
        state["events"].append(kind)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(self.path)
        return state["count"]

    def register_session(self, **kwargs):
        return self._mutate("register")

    def register_independent_agent(self, **kwargs):
        return self._mutate("register-independent")

    def process_turn(self, *args, **kwargs):
        return self._mutate("turn")

    def close_session(self, *args, **kwargs):
        return self._mutate("close")

    def session_state(self, *args, **kwargs):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def export_capsule(self, *args, **kwargs):
        return self.session_state()

    def verify_store(self, *args, **kwargs):
        return {"valid": True}


class LifecycleSerializationTests(unittest.TestCase):
    def test_register_and_close_share_one_lifecycle_lock_domain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = root / "unsafe.json"
            start = threading.Barrier(2)
            a = LifecycleSerializedGateway(UnsafeFileGateway(store, start), root)
            b = LifecycleSerializedGateway(UnsafeFileGateway(store, start), root)

            with ThreadPoolExecutor(max_workers=2) as pool:
                f1 = pool.submit(a.register_session)
                f2 = pool.submit(b.close_session, "session")
                self.assertEqual(sorted([f1.result(timeout=10), f2.result(timeout=10)]), [1, 2])

            state = json.loads(store.read_text(encoding="utf-8"))
            self.assertEqual(state["count"], 2)
            self.assertEqual(set(state["events"]), {"register", "close"})


class LineageAttestationTests(unittest.TestCase):
    def setUp(self):
        self.attestor = HMACLineageAttestor(
            issuer_id="JANUS-LINEAGE-REGISTRY",
            secret=b"lineage-unit-test-secret-32-bytes!!",
        )
        self.planner = VerifiedLineageReviewPlanner({self.attestor.issuer_id: self.attestor})

    def candidate(self, face: str, root: str, **kwargs):
        return AttestedReviewCandidate(
            face_id=face,
            attestation=self.attestor.attest(face_id=face, lineage_root=root),
            **kwargs,
        )

    def test_two_clones_with_valid_same_root_still_count_as_one_seat(self):
        with self.assertRaises(IndependentAttestedReviewUnavailable):
            self.planner.plan(
                origin_lineage_root="LINEAGE-A",
                candidates=[
                    self.candidate("B1", "LINEAGE-B"),
                    self.candidate("B2", "LINEAGE-B"),
                ],
                required_reviews=2,
            )

    def test_forged_root_change_is_rejected_even_when_face_id_is_unchanged(self):
        valid = self.attestor.attest(face_id="B1", lineage_root="LINEAGE-B")
        forged = replace(valid, lineage_root="FAKE-FRESH-ROOT")
        with self.assertRaises(LineageAttestationError):
            self.planner.plan(
                origin_lineage_root="LINEAGE-A",
                candidates=[AttestedReviewCandidate(face_id="B1", attestation=forged)],
                required_reviews=1,
            )

    def test_verified_independent_lineages_preserve_zero_authority_and_novel_dissent(self):
        assignments = self.planner.plan(
            origin_lineage_root="LINEAGE-A",
            candidates=[
                self.candidate("B", "LINEAGE-B", routing_priority=10.0),
                self.candidate(
                    "C",
                    "LINEAGE-C",
                    routing_priority=0.1,
                    novel_counterevidence=True,
                ),
            ],
            required_reviews=2,
        )
        self.assertEqual({a.lineage_root for a in assignments}, {"LINEAGE-B", "LINEAGE-C"})
        self.assertTrue(all(a.authority_weight == 0 for a in assignments))
        self.assertTrue(all(not a.world_authority_granted for a in assignments))


@dataclass(frozen=True)
class FakeBinding:
    provider_id: str
    effect_key: str
    idempotency_key: str | None


class StaticProviderAdapter:
    def __init__(self, provider_id: str, observation):
        self.provider_id = provider_id
        self.observation = observation
        self.calls = 0

    def lookup(self, binding):
        self.calls += 1
        return self.observation


class ExplodingWrongProviderAdapter:
    provider_id = "WRONG-PROVIDER"

    def __init__(self):
        self.calls = 0

    def lookup(self, binding):
        self.calls += 1
        raise AssertionError("lookup must not be called after provider preflight mismatch")


class ProviderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.binding = FakeBinding("BANK-X", "PAYMENT:200", "idem-200")
        self.verifier = HMACProviderEvidenceVerifier(
            provider_id="BANK-X",
            key_id="bank-x-test-key",
            secret=b"provider-evidence-unit-test-secret!!",
            authoritative_contract=True,
        )
        self.reconciler = VerifiedProviderLookupReconciler(
            {("BANK-X", "bank-x-test-key"): self.verifier}
        )

    def test_verified_no_effect_can_open_retry(self):
        observation = self.verifier.sign_observation(
            effect_key="PAYMENT:200",
            idempotency_key="idem-200",
            outcome=VerifiedProviderOutcome.NO_EFFECT,
            evidence_ref="BANK-X-LOOKUP-200",
        )
        decision = self.reconciler.reconcile(
            binding=self.binding,
            adapter=StaticProviderAdapter("BANK-X", observation),
        )
        self.assertTrue(decision.evidence_verified)
        self.assertTrue(decision.safe_automatic_retry)
        self.assertEqual(decision.state, "NO_EFFECT_BY_VERIFIED_PROVIDER_EVIDENCE")

    def test_tampered_signed_observation_fails_closed(self):
        observation = self.verifier.sign_observation(
            effect_key="PAYMENT:200",
            idempotency_key="idem-200",
            outcome=VerifiedProviderOutcome.NO_EFFECT,
            evidence_ref="BANK-X-LOOKUP-200",
        )
        tampered = replace(observation, signature_hex="00" * 32)
        decision = self.reconciler.reconcile(
            binding=self.binding,
            adapter=StaticProviderAdapter("BANK-X", tampered),
        )
        self.assertFalse(decision.evidence_verified)
        self.assertFalse(decision.safe_automatic_retry)
        self.assertTrue(decision.state.startswith("UNDETERMINED"))

    def test_wrong_provider_is_rejected_before_lookup_call(self):
        adapter = ExplodingWrongProviderAdapter()
        with self.assertRaises(ProviderEvidenceContractError):
            self.reconciler.reconcile(binding=self.binding, adapter=adapter)
        self.assertEqual(adapter.calls, 0)

    def test_verified_settled_requires_receipt(self):
        observation = self.verifier.sign_observation(
            effect_key="PAYMENT:200",
            idempotency_key="idem-200",
            outcome=VerifiedProviderOutcome.SETTLED,
            evidence_ref="BANK-X-LOOKUP-SETTLED-200",
            receipt_id=None,
        )
        with self.assertRaises(ProviderEvidenceContractError):
            self.reconciler.reconcile(
                binding=self.binding,
                adapter=StaticProviderAdapter("BANK-X", observation),
            )

    def test_non_authoritative_verifier_contract_cannot_clear_uncertainty(self):
        weak = HMACProviderEvidenceVerifier(
            provider_id="BANK-X",
            key_id="weak-key",
            secret=b"provider-evidence-weak-test-secret!!",
            authoritative_contract=False,
        )
        observation = weak.sign_observation(
            effect_key="PAYMENT:200",
            idempotency_key="idem-200",
            outcome=VerifiedProviderOutcome.NO_EFFECT,
            evidence_ref="WEAK-LOOKUP",
        )
        reconciler = VerifiedProviderLookupReconciler({("BANK-X", "weak-key"): weak})
        decision = reconciler.reconcile(
            binding=self.binding,
            adapter=StaticProviderAdapter("BANK-X", observation),
        )
        self.assertFalse(decision.evidence_verified)
        self.assertFalse(decision.safe_automatic_retry)


if __name__ == "__main__":
    unittest.main()
