# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.30 — second-order trust-boundary hardening.

This additive descendant responds to audit findings that remained after v18.7.29:
- the origin lineage must be attested too; candidate-only attestation is not
  sufficient to prevent a caller from lying about the origin root;
- provider evidence must bind the authorization lineage in addition to provider,
  effect, and idempotency identity;
- first client settlement is immutable, and a fully SETTLED caller request is
  never sent through a generic runtime again merely to reproduce its output.

Claim boundaries:
- HMAC remains a reference verifier/issuer mechanism, not objective proof that
  the issuer's lineage statement or provider-world statement is true;
- a BOUND-but-not-SETTLED retry still requires a runtime with safe stable-request
  recovery semantics. This module does not manufacture exactly-once execution;
- SETTLED replay is fail-closed at the client boundary because only a result hash,
  not a full replayable result envelope, is persisted here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from genesis_v18_7_28_client_ledger_attestation import (
    AttestedReviewAssignment,
    AttestedReviewCandidate,
    LineageAttestation,
    ProviderEvidenceContractError,
    VerifiedLineageReviewPlanner,
)
from genesis_v18_7_29_portable_resource_lifetime import (
    ClientRequestBinding,
    ClientRequestConflict,
    PersistentClientRequestLedger,
)

TRUST_BOUNDARY_HARDENING_VERSION = "18.7.30"
TRUST_BOUNDARY_HARDENING_SCHEMA = "janus.genesis.trust_boundary_hardening.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class ClientSettlementConflict(ClientRequestConflict):
    code = "CLIENT_SETTLEMENT_RESULT_CONFLICT"


class ClientRequestAlreadySettled(RuntimeError):
    code = "CLIENT_REQUEST_ALREADY_SETTLED_NO_GENERIC_REEXECUTION"

    def __init__(self, binding: ClientRequestBinding) -> None:
        self.binding = binding
        super().__init__(
            f"{self.code}:client_id={binding.client_id};request_id={binding.request_id};"
            f"result_sha256={binding.result_sha256}"
        )


class ImmutableSettlementClientRequestLedger(PersistentClientRequestLedger):
    """Make the first SETTLED result hash immutable for one caller request."""

    @staticmethod
    def _result_hash(result: Any) -> str:
        if hasattr(result, "to_dict"):
            try:
                value = result.to_dict(internal=True)
            except TypeError:
                value = result.to_dict()
        else:
            value = result
        return _sha256(value)

    def mark_settled(
        self,
        binding: ClientRequestBinding,
        *,
        result: Any,
    ) -> ClientRequestBinding:
        result_hash = self._result_hash(result)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT runtime_request_id, actor_id, action_sha256, state, result_sha256
                FROM client_requests WHERE client_id=? AND request_id=?
                """,
                (binding.client_id, binding.request_id),
            ).fetchone()
            if row is None:
                raise ClientRequestConflict("CLIENT_REQUEST_BINDING_MISSING_AT_SETTLEMENT")
            runtime_id, actor_id, action_hash, state, existing_result_hash = row
            if (
                runtime_id != binding.runtime_request_id
                or actor_id != binding.actor_id
                or action_hash != binding.action_sha256
            ):
                raise ClientRequestConflict("CLIENT_REQUEST_BINDING_CHANGED_BEFORE_SETTLE")

            if state == "SETTLED":
                if existing_result_hash != result_hash:
                    raise ClientSettlementConflict(
                        f"existing_result_sha256={existing_result_hash}; new_result_sha256={result_hash}"
                    )
            elif state == "BOUND":
                cur = conn.execute(
                    """
                    UPDATE client_requests SET state='SETTLED', result_sha256=?
                    WHERE client_id=? AND request_id=? AND runtime_request_id=?
                      AND actor_id=? AND action_sha256=? AND state='BOUND'
                    """,
                    (
                        result_hash,
                        binding.client_id,
                        binding.request_id,
                        binding.runtime_request_id,
                        binding.actor_id,
                        binding.action_sha256,
                    ),
                )
                if cur.rowcount != 1:
                    raise ClientRequestConflict("CLIENT_REQUEST_SETTLEMENT_COMPARE_AND_SET_FAILED")
            else:
                raise ClientRequestConflict(f"CLIENT_REQUEST_UNKNOWN_STATE:{state}")
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
        return ClientRequestBinding(
            client_id=binding.client_id,
            request_id=binding.request_id,
            runtime_request_id=binding.runtime_request_id,
            actor_id=binding.actor_id,
            action_sha256=binding.action_sha256,
            state="SETTLED",
            result_sha256=result_hash,
        )


class StableRequestRuntime(Protocol):
    def execute(self, *, actor_id: str, action: str, request_id: str) -> Any: ...


class FailClosedSettledClientExecutor:
    """Do not re-enter a generic runtime after the client ledger is SETTLED."""

    def __init__(
        self,
        *,
        ledger: ImmutableSettlementClientRequestLedger,
        runtime: StableRequestRuntime,
    ) -> None:
        self.ledger = ledger
        self.runtime = runtime

    def execute(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        action: str,
    ) -> Any:
        binding = self.ledger.bind(
            client_id=client_id,
            request_id=request_id,
            actor_id=actor_id,
            action=action,
        )
        if binding.state == "SETTLED":
            raise ClientRequestAlreadySettled(binding)
        result = self.runtime.execute(
            actor_id=binding.actor_id,
            action=str(action).strip(),
            request_id=binding.runtime_request_id,
        )
        self.ledger.mark_settled(binding, result=result)
        return result


class AttestedOriginLineageReviewPlanner(VerifiedLineageReviewPlanner):
    """Verify the origin lineage through the same attestation boundary as reviewers."""

    def plan_attested(
        self,
        *,
        origin: AttestedReviewCandidate,
        candidates: Sequence[AttestedReviewCandidate],
        required_reviews: int = 2,
        require_red_team: bool = True,
    ) -> tuple[AttestedReviewAssignment, ...]:
        origin_root, _origin_claim = self._verified(origin)
        return super().plan(
            origin_lineage_root=origin_root,
            candidates=candidates,
            required_reviews=required_reviews,
            require_red_team=require_red_team,
        )


class AuthorizationBoundProviderOutcome(str, Enum):
    SETTLED = "SETTLED"
    NO_EFFECT = "NO_EFFECT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AuthorizationBoundProviderObservation:
    provider_id: str
    effect_key: str
    authorization_id: str
    idempotency_key: str | None
    outcome: AuthorizationBoundProviderOutcome
    evidence_ref: str
    receipt_id: str | None
    verifier_key_id: str
    signature_hex: str

    def payload(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "effect_key": self.effect_key,
            "authorization_id": self.authorization_id,
            "idempotency_key": self.idempotency_key,
            "outcome": self.outcome.value,
            "evidence_ref": self.evidence_ref,
            "receipt_id": self.receipt_id,
            "verifier_key_id": self.verifier_key_id,
        }


class AuthorizationBoundProviderAdapter(Protocol):
    provider_id: str

    def lookup(self, binding: Any) -> AuthorizationBoundProviderObservation: ...


class AuthorizationBoundProviderEvidenceVerifier(Protocol):
    provider_id: str
    key_id: str
    authoritative_contract: bool

    def verify(self, observation: AuthorizationBoundProviderObservation) -> bool: ...


class HMACAuthorizationBoundProviderEvidenceVerifier:
    """Reference verifier binding evidence to the authorization lineage too."""

    def __init__(
        self,
        *,
        provider_id: str,
        key_id: str,
        secret: bytes,
        authoritative_contract: bool = True,
    ) -> None:
        self.provider_id = str(provider_id).strip()
        self.key_id = str(key_id).strip()
        self.secret = bytes(secret)
        self.authoritative_contract = bool(authoritative_contract)
        if not self.provider_id or not self.key_id or len(self.secret) < 16:
            raise ValueError("PROVIDER_VERIFIER_ID_KEY_AND_SECRET_REQUIRED")

    def _signature(self, payload: Mapping[str, Any]) -> str:
        return hmac.new(
            self.secret,
            _canonical_json(dict(payload)).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def sign_observation(
        self,
        *,
        effect_key: str,
        authorization_id: str,
        idempotency_key: str | None,
        outcome: AuthorizationBoundProviderOutcome,
        evidence_ref: str,
        receipt_id: str | None = None,
    ) -> AuthorizationBoundProviderObservation:
        payload = {
            "provider_id": self.provider_id,
            "effect_key": str(effect_key),
            "authorization_id": str(authorization_id),
            "idempotency_key": idempotency_key,
            "outcome": outcome.value,
            "evidence_ref": str(evidence_ref),
            "receipt_id": receipt_id,
            "verifier_key_id": self.key_id,
        }
        return AuthorizationBoundProviderObservation(
            provider_id=self.provider_id,
            effect_key=str(effect_key),
            authorization_id=str(authorization_id),
            idempotency_key=idempotency_key,
            outcome=outcome,
            evidence_ref=str(evidence_ref),
            receipt_id=receipt_id,
            verifier_key_id=self.key_id,
            signature_hex=self._signature(payload),
        )

    def verify(self, observation: AuthorizationBoundProviderObservation) -> bool:
        if observation.provider_id != self.provider_id or observation.verifier_key_id != self.key_id:
            return False
        return hmac.compare_digest(self._signature(observation.payload()), observation.signature_hex)


@dataclass(frozen=True)
class AuthorizationBoundProviderDecision:
    state: str
    safe_automatic_retry: bool
    receipt_id: str | None
    evidence_ref: str | None
    evidence_verified: bool


class AuthorizationBoundProviderLookupReconciler:
    """Require verified evidence for the exact current authorization lineage."""

    def __init__(
        self,
        verifiers: Mapping[tuple[str, str], AuthorizationBoundProviderEvidenceVerifier],
    ) -> None:
        self.verifiers = dict(verifiers)

    def reconcile(
        self,
        *,
        binding: Any,
        adapter: AuthorizationBoundProviderAdapter,
    ) -> AuthorizationBoundProviderDecision:
        if adapter.provider_id != binding.provider_id:
            raise ProviderEvidenceContractError("ADAPTER_PROVIDER_ID_MISMATCH_BEFORE_LOOKUP")
        observation = adapter.lookup(binding)
        structural = (
            observation.provider_id == binding.provider_id
            and observation.effect_key == binding.effect_key
            and observation.authorization_id == binding.authorization_id
            and observation.idempotency_key == binding.idempotency_key
        )
        if not structural:
            raise ProviderEvidenceContractError("AUTHORIZATION_BOUND_PROVIDER_EVIDENCE_MISMATCH")

        verifier = self.verifiers.get((observation.provider_id, observation.verifier_key_id))
        verified = bool(
            verifier is not None
            and verifier.provider_id == observation.provider_id
            and verifier.key_id == observation.verifier_key_id
            and verifier.authoritative_contract
            and verifier.verify(observation)
        )
        if not verified:
            return AuthorizationBoundProviderDecision(
                state="UNDETERMINED_PROVIDER_EVIDENCE_UNVERIFIED",
                safe_automatic_retry=False,
                receipt_id=None,
                evidence_ref=observation.evidence_ref or None,
                evidence_verified=False,
            )
        if observation.outcome is AuthorizationBoundProviderOutcome.SETTLED:
            if not observation.receipt_id:
                raise ProviderEvidenceContractError("VERIFIED_SETTLED_REQUIRES_RECEIPT_ID")
            return AuthorizationBoundProviderDecision(
                state="SETTLED_BY_AUTHORIZATION_BOUND_PROVIDER_EVIDENCE",
                safe_automatic_retry=False,
                receipt_id=observation.receipt_id,
                evidence_ref=observation.evidence_ref,
                evidence_verified=True,
            )
        if observation.outcome is AuthorizationBoundProviderOutcome.NO_EFFECT:
            return AuthorizationBoundProviderDecision(
                state="NO_EFFECT_BY_AUTHORIZATION_BOUND_PROVIDER_EVIDENCE",
                safe_automatic_retry=True,
                receipt_id=None,
                evidence_ref=observation.evidence_ref,
                evidence_verified=True,
            )
        return AuthorizationBoundProviderDecision(
            state="UNDETERMINED_VERIFIED_PROVIDER_UNKNOWN",
            safe_automatic_retry=False,
            receipt_id=None,
            evidence_ref=observation.evidence_ref or None,
            evidence_verified=True,
        )


__all__ = [
    "TRUST_BOUNDARY_HARDENING_VERSION",
    "TRUST_BOUNDARY_HARDENING_SCHEMA",
    "ClientSettlementConflict",
    "ClientRequestAlreadySettled",
    "ImmutableSettlementClientRequestLedger",
    "FailClosedSettledClientExecutor",
    "AttestedOriginLineageReviewPlanner",
    "AuthorizationBoundProviderOutcome",
    "AuthorizationBoundProviderObservation",
    "HMACAuthorizationBoundProviderEvidenceVerifier",
    "AuthorizationBoundProviderDecision",
    "AuthorizationBoundProviderLookupReconciler",
]
