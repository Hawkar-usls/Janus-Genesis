# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.28 — client request ledger, lifecycle serialization,
lineage attestation, and verified provider lookup evidence.

This module is deliberately dependency-light so its control primitives can be
verified on both POSIX and Windows without importing older POSIX-only runtime
modules. Linux integration tests may compose these primitives with v18.7.26.

Claim boundaries:
- PortableProcessLock is same-host/shared-filesystem coordination, not multi-host
  consensus.
- Client request identity is safe only when the caller preserves/reuses the same
  logical request_id; JANUS does not infer that two identical actions are the
  same intent.
- HMAC lineage/provider verifiers are reference trust-boundary implementations.
  They prove that a configured issuer/verifier signed the bound fields, not that
  the issuer's genealogy or provider-world statement is objectively true.
- Verified review seats have zero world authority.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from janus_portable_lock import PortableProcessLock

CLIENT_CONTROL_VERSION = "18.7.28"
CLIENT_CONTROL_SCHEMA = "janus.genesis.client_ledger_attestation.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _action_sha256(action: str) -> str:
    return hashlib.sha256(str(action).encode("utf-8")).hexdigest()


class ClientControlError(RuntimeError):
    code = "CLIENT_CONTROL_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ClientRequestConflict(ClientControlError):
    code = "CLIENT_REQUEST_ID_BINDING_CONFLICT"


class LineageAttestationError(ClientControlError):
    code = "LINEAGE_ATTESTATION_FAILED"


class IndependentAttestedReviewUnavailable(ClientControlError):
    code = "ATTESTED_INDEPENDENT_REVIEW_LINEAGES_UNAVAILABLE"


class ProviderEvidenceContractError(ClientControlError):
    code = "PROVIDER_EVIDENCE_CONTRACT_ERROR"


@dataclass(frozen=True)
class ClientRequestBinding:
    client_id: str
    request_id: str
    runtime_request_id: str
    actor_id: str
    action_sha256: str
    state: str
    result_sha256: str | None


class PersistentClientRequestLedger:
    """SQLite binding from caller request identity to one actor/action hash.

    The ledger does not deduplicate by action text. Two intentionally repeated
    identical actions remain distinct unless the caller explicitly reuses the
    same request_id.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_requests (
                    client_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    runtime_request_id TEXT NOT NULL UNIQUE,
                    actor_id TEXT NOT NULL,
                    action_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result_sha256 TEXT,
                    PRIMARY KEY(client_id, request_id)
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @staticmethod
    def runtime_request_id(client_id: str, request_id: str) -> str:
        return "CLIENT:" + _sha256({"client_id": client_id, "request_id": request_id})[:40]

    def bind(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        action: str,
    ) -> ClientRequestBinding:
        client = str(client_id).strip()
        request = str(request_id).strip()
        actor = str(actor_id).strip()
        action_text = str(action).strip()
        if not client or not request or not actor or not action_text:
            raise ValueError("CLIENT_REQUEST_ACTOR_ACTION_REQUIRED")
        if len(client) > 160 or len(request) > 240 or len(actor) > 240:
            raise ValueError("CLIENT_REQUEST_IDENTITY_TOO_LONG")
        action_hash = _action_sha256(action_text)
        runtime_id = self.runtime_request_id(client, request)

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT runtime_request_id, actor_id, action_sha256, state, result_sha256
                FROM client_requests WHERE client_id=? AND request_id=?
                """,
                (client, request),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO client_requests(
                        client_id, request_id, runtime_request_id, actor_id,
                        action_sha256, state, result_sha256
                    ) VALUES(?,?,?,?,?,'BOUND',NULL)
                    """,
                    (client, request, runtime_id, actor, action_hash),
                )
                state = "BOUND"
                result_hash = None
            else:
                known_runtime, known_actor, known_action, state, result_hash = row
                if (
                    known_runtime != runtime_id
                    or known_actor != actor
                    or known_action != action_hash
                ):
                    raise ClientRequestConflict(
                        f"client_id={client}; request_id={request}; existing_actor={known_actor}; "
                        f"existing_action_sha256={known_action}; new_actor={actor}; "
                        f"new_action_sha256={action_hash}"
                    )
            conn.execute("COMMIT")
            return ClientRequestBinding(
                client_id=client,
                request_id=request,
                runtime_request_id=runtime_id,
                actor_id=actor,
                action_sha256=action_hash,
                state=str(state),
                result_sha256=result_hash,
            )
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    def mark_settled(
        self,
        binding: ClientRequestBinding,
        *,
        result: Any,
    ) -> ClientRequestBinding:
        if hasattr(result, "to_dict"):
            try:
                result_value = result.to_dict(internal=True)
            except TypeError:
                result_value = result.to_dict()
        else:
            result_value = result
        result_hash = _sha256(result_value)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE client_requests SET state='SETTLED', result_sha256=?
                WHERE client_id=? AND request_id=? AND runtime_request_id=?
                  AND actor_id=? AND action_sha256=?
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
                raise ClientRequestConflict("CLIENT_REQUEST_BINDING_CHANGED_BEFORE_SETTLE")
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

    def get(self, *, client_id: str, request_id: str) -> ClientRequestBinding | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT runtime_request_id, actor_id, action_sha256, state, result_sha256
                FROM client_requests WHERE client_id=? AND request_id=?
                """,
                (str(client_id).strip(), str(request_id).strip()),
            ).fetchone()
        if row is None:
            return None
        runtime_id, actor_id, action_hash, state, result_hash = row
        return ClientRequestBinding(
            client_id=str(client_id).strip(),
            request_id=str(request_id).strip(),
            runtime_request_id=runtime_id,
            actor_id=actor_id,
            action_sha256=action_hash,
            state=state,
            result_sha256=result_hash,
        )


class RuntimeRequestExecutor(Protocol):
    def execute(self, *, actor_id: str, action: str, request_id: str) -> Any: ...


class ControlledClientExecutor:
    """Bind a caller request durably before delegating to a controlled runtime."""

    def __init__(self, *, ledger: PersistentClientRequestLedger, runtime: RuntimeRequestExecutor) -> None:
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
        # If the runtime raises or the process dies, the BOUND record remains.
        # Retry with the same caller request identity reaches the same runtime
        # request_id; the runtime layer, not this ledger, decides receipt replay
        # versus UNDETERMINED blocking.
        result = self.runtime.execute(
            actor_id=binding.actor_id,
            action=str(action).strip(),
            request_id=binding.runtime_request_id,
        )
        self.ledger.mark_settled(binding, result=result)
        return result


class LifecycleSerializedGateway:
    """Serialize every known AI-link session-store mutation through one lock.

    The wrapped gateway may be the v18.7.26 controlled gateway. This wrapper is
    intentionally composition-based so it does not add a second world authority.
    """

    def __init__(self, gateway: Any, data_dir: str | Path) -> None:
        self.gateway = gateway
        self.lock = PortableProcessLock(Path(data_dir) / "ai_link_session_lifecycle_v18_7_28.lock")

    def register_session(self, **kwargs):
        with self.lock.exclusive():
            return self.gateway.register_session(**kwargs)

    def register_independent_agent(self, **kwargs):
        with self.lock.exclusive():
            return self.gateway.register_independent_agent(**kwargs)

    def process_turn(self, *args, **kwargs):
        with self.lock.exclusive():
            return self.gateway.process_turn(*args, **kwargs)

    def close_session(self, *args, **kwargs):
        with self.lock.exclusive():
            return self.gateway.close_session(*args, **kwargs)

    def session_state(self, *args, **kwargs):
        with self.lock.shared():
            return self.gateway.session_state(*args, **kwargs)

    def export_capsule(self, *args, **kwargs):
        with self.lock.shared():
            return self.gateway.export_capsule(*args, **kwargs)

    def verify_store(self, *args, **kwargs):
        with self.lock.shared():
            return self.gateway.verify_store(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.gateway, name)


@dataclass(frozen=True)
class LineageAttestation:
    issuer_id: str
    attestation_id: str
    face_id: str
    lineage_root: str
    parent_face_id: str | None
    signature_hex: str

    def payload(self) -> dict[str, Any]:
        return {
            "issuer_id": self.issuer_id,
            "attestation_id": self.attestation_id,
            "face_id": self.face_id,
            "lineage_root": self.lineage_root,
            "parent_face_id": self.parent_face_id,
        }


class LineageAttestationVerifier(Protocol):
    issuer_id: str

    def verify(self, attestation: LineageAttestation) -> bool: ...


class HMACLineageAttestor:
    """Reference issuer/verifier that cryptographically binds a lineage claim."""

    def __init__(self, *, issuer_id: str, secret: bytes) -> None:
        self.issuer_id = str(issuer_id).strip()
        self.secret = bytes(secret)
        if not self.issuer_id or len(self.secret) < 16:
            raise ValueError("LINEAGE_ISSUER_AND_SECRET_REQUIRED")

    def _signature(self, payload: Mapping[str, Any]) -> str:
        return hmac.new(
            self.secret,
            _canonical_json(dict(payload)).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def attest(
        self,
        *,
        face_id: str,
        lineage_root: str,
        parent_face_id: str | None = None,
        attestation_id: str | None = None,
    ) -> LineageAttestation:
        face = str(face_id).strip()
        root = str(lineage_root).strip()
        if not face or not root:
            raise ValueError("FACE_AND_LINEAGE_ROOT_REQUIRED")
        payload = {
            "issuer_id": self.issuer_id,
            "attestation_id": attestation_id or f"LINEAGE-{uuid.uuid4().hex}",
            "face_id": face,
            "lineage_root": root,
            "parent_face_id": None if parent_face_id is None else str(parent_face_id).strip() or None,
        }
        return LineageAttestation(**payload, signature_hex=self._signature(payload))

    def verify(self, attestation: LineageAttestation) -> bool:
        if attestation.issuer_id != self.issuer_id:
            return False
        expected = self._signature(attestation.payload())
        return hmac.compare_digest(expected, attestation.signature_hex)


@dataclass(frozen=True)
class AttestedReviewCandidate:
    face_id: str
    attestation: LineageAttestation
    routing_priority: float = 1.0
    novel_counterevidence: bool = False
    red_team_capable: bool = True


@dataclass(frozen=True)
class AttestedReviewAssignment:
    face_id: str
    lineage_root: str
    attestation_id: str
    issuer_id: str
    role: str
    routing_priority: float
    novel_counterevidence: bool
    authority_weight: int = 0
    world_authority_granted: bool = False


class VerifiedLineageReviewPlanner:
    """Count review seats only after lineage attestations verify."""

    def __init__(self, verifiers: Mapping[str, LineageAttestationVerifier]) -> None:
        self.verifiers = dict(verifiers)

    def _verified(self, candidate: AttestedReviewCandidate) -> tuple[str, LineageAttestation]:
        claim = candidate.attestation
        if claim.face_id != candidate.face_id:
            raise LineageAttestationError("LINEAGE_ATTESTATION_FACE_ID_MISMATCH")
        verifier = self.verifiers.get(claim.issuer_id)
        if verifier is None or verifier.issuer_id != claim.issuer_id or not verifier.verify(claim):
            raise LineageAttestationError("LINEAGE_ATTESTATION_UNVERIFIED")
        return claim.lineage_root, claim

    def plan(
        self,
        *,
        origin_lineage_root: str,
        candidates: Sequence[AttestedReviewCandidate],
        required_reviews: int = 2,
        require_red_team: bool = True,
    ) -> tuple[AttestedReviewAssignment, ...]:
        origin_root = str(origin_lineage_root).strip()
        if not origin_root:
            raise ValueError("ORIGIN_LINEAGE_ROOT_REQUIRED")
        if required_reviews < 1:
            raise ValueError("REQUIRED_REVIEWS_MUST_BE_POSITIVE")

        by_lineage: dict[str, list[tuple[AttestedReviewCandidate, LineageAttestation]]] = {}
        for candidate in candidates:
            root, claim = self._verified(candidate)
            if root == origin_root:
                continue
            by_lineage.setdefault(root, []).append((candidate, claim))

        representatives: list[tuple[AttestedReviewCandidate, LineageAttestation]] = []
        for members in by_lineage.values():
            representatives.append(
                min(
                    members,
                    key=lambda pair: (
                        0 if pair[0].novel_counterevidence else 1,
                        -float(pair[0].routing_priority),
                        pair[0].face_id,
                    ),
                )
            )
        representatives.sort(
            key=lambda pair: (
                0 if pair[0].novel_counterevidence else 1,
                -float(pair[0].routing_priority),
                pair[1].lineage_root,
                pair[0].face_id,
            )
        )
        if len(representatives) < required_reviews:
            raise IndependentAttestedReviewUnavailable(
                f"required={required_reviews}; verified_independent_lineages={len(representatives)}"
            )

        selected = representatives[:required_reviews]
        if require_red_team and not any(candidate.red_team_capable for candidate, _ in selected):
            replacement = next(
                (
                    pair
                    for pair in representatives[required_reviews:]
                    if pair[0].red_team_capable
                ),
                None,
            )
            if replacement is None:
                raise IndependentAttestedReviewUnavailable("ATTESTED_RED_TEAM_LINEAGE_UNAVAILABLE")
            selected[-1] = replacement

        red_team_assigned = False
        out: list[AttestedReviewAssignment] = []
        for candidate, claim in selected:
            if require_red_team and candidate.red_team_capable and not red_team_assigned:
                role = "COUNTEREXAMPLE_CHALLENGE"
                red_team_assigned = True
            else:
                role = "INDEPENDENT_REVIEW"
            out.append(
                AttestedReviewAssignment(
                    face_id=candidate.face_id,
                    lineage_root=claim.lineage_root,
                    attestation_id=claim.attestation_id,
                    issuer_id=claim.issuer_id,
                    role=role,
                    routing_priority=float(candidate.routing_priority),
                    novel_counterevidence=bool(candidate.novel_counterevidence),
                    authority_weight=0,
                    world_authority_granted=False,
                )
            )
        return tuple(out)


class VerifiedProviderOutcome(str, Enum):
    SETTLED = "SETTLED"
    NO_EFFECT = "NO_EFFECT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VerifiedProviderObservation:
    provider_id: str
    effect_key: str
    idempotency_key: str | None
    outcome: VerifiedProviderOutcome
    evidence_ref: str
    receipt_id: str | None
    verifier_key_id: str
    signature_hex: str

    def payload(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "effect_key": self.effect_key,
            "idempotency_key": self.idempotency_key,
            "outcome": self.outcome.value,
            "evidence_ref": self.evidence_ref,
            "receipt_id": self.receipt_id,
            "verifier_key_id": self.verifier_key_id,
        }


class VerifiedProviderAdapter(Protocol):
    provider_id: str

    def lookup(self, binding: Any) -> VerifiedProviderObservation: ...


class ProviderEvidenceVerifier(Protocol):
    provider_id: str
    key_id: str
    authoritative_contract: bool

    def verify(self, observation: VerifiedProviderObservation) -> bool: ...


class HMACProviderEvidenceVerifier:
    """Reference provider-evidence signer/verifier for adapter contract tests."""

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
        idempotency_key: str | None,
        outcome: VerifiedProviderOutcome,
        evidence_ref: str,
        receipt_id: str | None = None,
    ) -> VerifiedProviderObservation:
        payload = {
            "provider_id": self.provider_id,
            "effect_key": str(effect_key),
            "idempotency_key": idempotency_key,
            "outcome": outcome.value,
            "evidence_ref": str(evidence_ref),
            "receipt_id": receipt_id,
            "verifier_key_id": self.key_id,
        }
        return VerifiedProviderObservation(
            provider_id=self.provider_id,
            effect_key=str(effect_key),
            idempotency_key=idempotency_key,
            outcome=outcome,
            evidence_ref=str(evidence_ref),
            receipt_id=receipt_id,
            verifier_key_id=self.key_id,
            signature_hex=self._signature(payload),
        )

    def verify(self, observation: VerifiedProviderObservation) -> bool:
        if observation.provider_id != self.provider_id or observation.verifier_key_id != self.key_id:
            return False
        return hmac.compare_digest(self._signature(observation.payload()), observation.signature_hex)


@dataclass(frozen=True)
class VerifiedProviderDecision:
    provider_id: str
    effect_key: str
    state: str
    evidence_ref: str | None
    receipt_id: str | None
    safe_automatic_retry: bool
    evidence_verified: bool


class VerifiedProviderLookupReconciler:
    """Require provider evidence verification before clearing uncertainty."""

    def __init__(self, verifiers: Mapping[tuple[str, str], ProviderEvidenceVerifier]) -> None:
        self.verifiers = dict(verifiers)

    def reconcile(self, *, binding: Any, adapter: VerifiedProviderAdapter) -> VerifiedProviderDecision:
        # Preflight the adapter identity before any provider lookup call.
        if adapter.provider_id != binding.provider_id:
            raise ProviderEvidenceContractError("ADAPTER_PROVIDER_ID_MISMATCH_BEFORE_LOOKUP")

        observation = adapter.lookup(binding)
        if observation.provider_id != binding.provider_id:
            raise ProviderEvidenceContractError("OBSERVATION_PROVIDER_ID_MISMATCH")
        if observation.effect_key != binding.effect_key:
            raise ProviderEvidenceContractError("OBSERVATION_EFFECT_KEY_MISMATCH")
        if observation.idempotency_key != binding.idempotency_key:
            raise ProviderEvidenceContractError("OBSERVATION_IDEMPOTENCY_KEY_MISMATCH")

        verifier = self.verifiers.get((observation.provider_id, observation.verifier_key_id))
        verified = bool(
            verifier is not None
            and verifier.provider_id == observation.provider_id
            and verifier.key_id == observation.verifier_key_id
            and verifier.authoritative_contract
            and verifier.verify(observation)
        )
        if not verified:
            return VerifiedProviderDecision(
                provider_id=binding.provider_id,
                effect_key=binding.effect_key,
                state="UNDETERMINED_PROVIDER_EVIDENCE_UNVERIFIED",
                evidence_ref=observation.evidence_ref or None,
                receipt_id=None,
                safe_automatic_retry=False,
                evidence_verified=False,
            )

        if observation.outcome is VerifiedProviderOutcome.SETTLED:
            if not observation.receipt_id:
                raise ProviderEvidenceContractError("VERIFIED_SETTLED_REQUIRES_RECEIPT_ID")
            return VerifiedProviderDecision(
                provider_id=binding.provider_id,
                effect_key=binding.effect_key,
                state="SETTLED_BY_VERIFIED_PROVIDER_EVIDENCE",
                evidence_ref=observation.evidence_ref,
                receipt_id=observation.receipt_id,
                safe_automatic_retry=False,
                evidence_verified=True,
            )
        if observation.outcome is VerifiedProviderOutcome.NO_EFFECT:
            return VerifiedProviderDecision(
                provider_id=binding.provider_id,
                effect_key=binding.effect_key,
                state="NO_EFFECT_BY_VERIFIED_PROVIDER_EVIDENCE",
                evidence_ref=observation.evidence_ref,
                receipt_id=None,
                safe_automatic_retry=True,
                evidence_verified=True,
            )
        return VerifiedProviderDecision(
            provider_id=binding.provider_id,
            effect_key=binding.effect_key,
            state="UNDETERMINED_VERIFIED_PROVIDER_UNKNOWN",
            evidence_ref=observation.evidence_ref or None,
            receipt_id=None,
            safe_automatic_retry=False,
            evidence_verified=True,
        )


__all__ = [
    "CLIENT_CONTROL_VERSION",
    "CLIENT_CONTROL_SCHEMA",
    "ClientControlError",
    "ClientRequestConflict",
    "ClientRequestBinding",
    "PersistentClientRequestLedger",
    "RuntimeRequestExecutor",
    "ControlledClientExecutor",
    "LifecycleSerializedGateway",
    "LineageAttestation",
    "LineageAttestationVerifier",
    "HMACLineageAttestor",
    "LineageAttestationError",
    "AttestedReviewCandidate",
    "AttestedReviewAssignment",
    "VerifiedLineageReviewPlanner",
    "IndependentAttestedReviewUnavailable",
    "VerifiedProviderOutcome",
    "VerifiedProviderObservation",
    "VerifiedProviderAdapter",
    "ProviderEvidenceVerifier",
    "HMACProviderEvidenceVerifier",
    "ProviderEvidenceContractError",
    "VerifiedProviderDecision",
    "VerifiedProviderLookupReconciler",
]
