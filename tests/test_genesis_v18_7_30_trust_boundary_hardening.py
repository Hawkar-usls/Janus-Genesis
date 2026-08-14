from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, replace
from pathlib import Path

from genesis_v18_7_28_client_ledger_attestation import (
    AttestedReviewCandidate,
    HMACLineageAttestor,
    LineageAttestationError,
    ProviderEvidenceContractError,
)
from genesis_v18_7_30_trust_boundary_hardening import (
    AttestedOriginLineageReviewPlanner,
    AuthorizationBoundProviderLookupReconciler,
    AuthorizationBoundProviderOutcome,
    ClientRequestAlreadySettled,
    ClientSettlementConflict,
    FailClosedSettledClientExecutor,
    HMACAuthorizationBoundProviderEvidenceVerifier,
    ImmutableSettlementClientRequestLedger,
)


class RecordingRuntime:
    def __init__(self):
        self.calls = []

    def execute(self, *, actor_id: str, action: str, request_id: str):
        self.calls.append((actor_id, action, request_id))
        return {"status": "OK", "actor_id": actor_id, "action": action, "request_id": request_id}


class AttestedOriginTests(unittest.TestCase):
    def setUp(self):
        self.attestor = HMACLineageAttestor(
            issuer_id="JANUS-LINEAGE-REGISTRY",
            secret=b"lineage-v30-unit-test-secret-32-bytes",
        )
        self.planner = AttestedOriginLineageReviewPlanner(
            {self.attestor.issuer_id: self.attestor}
        )

    def candidate(self, face: str, root: str, **kwargs):
        return AttestedReviewCandidate(
            face_id=face,
            attestation=self.attestor.attest(face_id=face, lineage_root=root),
            **kwargs,
        )

    def test_attested_origin_root_excludes_its_attested_fork(self):
        assignments = self.planner.plan_attested(
            origin=self.candidate("FACE-A", "LINEAGE-A"),
            candidates=[
                self.candidate("FACE-A-FORK", "LINEAGE-A", routing_priority=100.0),
                self.candidate("FACE-B", "LINEAGE-B", routing_priority=1.0),
            ],
            required_reviews=1,
        )
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].lineage_root, "LINEAGE-B")

    def test_caller_cannot_change_origin_root_without_invalidating_attestation(self):
        valid = self.attestor.attest(face_id="FACE-A", lineage_root="LINEAGE-A")
        forged = replace(valid, lineage_root="FAKE-ORIGIN-ROOT")
        with self.assertRaises(LineageAttestationError):
            self.planner.plan_attested(
                origin=AttestedReviewCandidate(face_id="FACE-A", attestation=forged),
                candidates=[self.candidate("FACE-B", "LINEAGE-B")],
                required_reviews=1,
            )


@dataclass(frozen=True)
class Binding:
    provider_id: str
    effect_key: str
    authorization_id: str
    idempotency_key: str | None


class StaticAdapter:
    def __init__(self, provider_id: str, observation):
        self.provider_id = provider_id
        self.observation = observation
        self.calls = 0

    def lookup(self, binding):
        self.calls += 1
        return self.observation


class AuthorizationBoundProviderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.binding = Binding("BANK-X", "PAYMENT:200", "AUTH-NEW", "idem-200")
        self.verifier = HMACAuthorizationBoundProviderEvidenceVerifier(
            provider_id="BANK-X",
            key_id="bank-x-auth-bound-key",
            secret=b"provider-auth-bound-unit-test-secret!!",
            authoritative_contract=True,
        )
        self.reconciler = AuthorizationBoundProviderLookupReconciler(
            {("BANK-X", "bank-x-auth-bound-key"): self.verifier}
        )

    def test_verified_no_effect_for_current_authorization_can_open_retry(self):
        observation = self.verifier.sign_observation(
            effect_key="PAYMENT:200",
            authorization_id="AUTH-NEW",
            idempotency_key="idem-200",
            outcome=AuthorizationBoundProviderOutcome.NO_EFFECT,
            evidence_ref="BANK-X-AUTH-NEW-NO-EFFECT",
        )
        decision = self.reconciler.reconcile(
            binding=self.binding,
            adapter=StaticAdapter("BANK-X", observation),
        )
        self.assertTrue(decision.evidence_verified)
        self.assertTrue(decision.safe_automatic_retry)

    def test_stale_signed_evidence_from_prior_authorization_cannot_clear_uncertainty(self):
        stale = self.verifier.sign_observation(
            effect_key="PAYMENT:200",
            authorization_id="AUTH-OLD",
            idempotency_key="idem-200",
            outcome=AuthorizationBoundProviderOutcome.NO_EFFECT,
            evidence_ref="BANK-X-AUTH-OLD-NO-EFFECT",
        )
        with self.assertRaises(ProviderEvidenceContractError):
            self.reconciler.reconcile(
                binding=self.binding,
                adapter=StaticAdapter("BANK-X", stale),
            )

    def test_signature_tamper_fails_closed_for_current_authorization(self):
        valid = self.verifier.sign_observation(
            effect_key="PAYMENT:200",
            authorization_id="AUTH-NEW",
            idempotency_key="idem-200",
            outcome=AuthorizationBoundProviderOutcome.NO_EFFECT,
            evidence_ref="BANK-X-AUTH-NEW-NO-EFFECT",
        )
        tampered = replace(valid, signature_hex="00" * 32)
        decision = self.reconciler.reconcile(
            binding=self.binding,
            adapter=StaticAdapter("BANK-X", tampered),
        )
        self.assertFalse(decision.evidence_verified)
        self.assertFalse(decision.safe_automatic_retry)
        self.assertTrue(decision.state.startswith("UNDETERMINED"))


class ImmutableSettlementTests(unittest.TestCase):
    def test_first_settlement_hash_is_immutable(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = ImmutableSettlementClientRequestLedger(Path(td) / "requests.sqlite3")
            binding = ledger.bind(
                client_id="cli-main",
                request_id="REQ-1",
                actor_id="mira",
                action="создать сад",
            )
            first = ledger.mark_settled(binding, result={"status": "OK", "value": 1})
            same = ledger.mark_settled(first, result={"status": "OK", "value": 1})
            self.assertEqual(first.result_sha256, same.result_sha256)
            with self.assertRaises(ClientSettlementConflict):
                ledger.mark_settled(first, result={"status": "OK", "value": 2})
            persisted = ledger.get(client_id="cli-main", request_id="REQ-1")
            self.assertEqual(persisted.result_sha256, first.result_sha256)

    def test_settled_request_never_reenters_generic_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = ImmutableSettlementClientRequestLedger(Path(td) / "requests.sqlite3")
            runtime = RecordingRuntime()
            executor = FailClosedSettledClientExecutor(ledger=ledger, runtime=runtime)
            executor.execute(
                client_id="cli-main",
                request_id="REQ-2",
                actor_id="mira",
                action="создать музыку",
            )
            self.assertEqual(len(runtime.calls), 1)
            with self.assertRaises(ClientRequestAlreadySettled):
                executor.execute(
                    client_id="cli-main",
                    request_id="REQ-2",
                    actor_id="mira",
                    action="создать музыку",
                )
            self.assertEqual(len(runtime.calls), 1)


if __name__ == "__main__":
    unittest.main()
