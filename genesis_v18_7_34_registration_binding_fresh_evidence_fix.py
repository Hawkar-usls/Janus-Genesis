# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.34 — registration-request binding and typed evidence fix.

The first v18.7.32 CI execution exposed two implementation defects that are
preserved rather than rewritten:

1. the registration saga derived ``session_id`` from both request ID and the
   registration hash, so reusing one registration_request_id with different
   parameters could produce a different session ID and evade the intended
   request-level conflict check until some unrelated actor-binding rule fired;
2. ``FreshProviderHMAC.sign`` built its dataclass from a serialized payload and
   therefore stored ``outcome`` as a plain string. Verification later expected
   the enum and failed before freshness policy could run.

v18.7.34 adds a durable registration-request registry keyed by the request ID
*before* entering the session saga, and a typed provider signer that signs the
serialized enum value while retaining the enum in the in-memory observation.

These are descendant corrections. They do not relabel the failed v18.7.32 run
as successful, and they do not turn the session/world pair into one transaction.
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genesis_v18_7_19_ai_link_play import (
    ROLE_INDEPENDENT_AI,
    _canonical_actor_id,
    _sha256,
    _slug,
)
from genesis_v18_7_32_durable_session_key_lifecycle import (
    DurableLifecycleGenesisAILinkGateway,
    FreshProviderHMAC,
    FreshProviderObservation,
    FreshProviderOutcome,
    _hmac_hex,
)

REGISTRATION_BINDING_FIX_VERSION = "18.7.34"
REGISTRATION_BINDING_FIX_SCHEMA = "janus.genesis.registration_binding_fresh_evidence_fix.v1"


class RegistrationRequestConflict(RuntimeError):
    code = "REGISTRATION_REQUEST_ID_BINDING_CONFLICT"


@dataclass(frozen=True)
class RegistrationRequestBinding:
    registration_request_id: str
    registration_hash: str
    session_id: str


class RegistrationRequestRegistry:
    """Durably bind one registration request ID to one normalized registration."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS registration_requests (
                    registration_request_id TEXT PRIMARY KEY,
                    registration_hash TEXT NOT NULL,
                    session_id TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def bind(
        self,
        *,
        registration_request_id: str,
        registration_hash: str,
        session_id: str,
    ) -> RegistrationRequestBinding:
        request_id = str(registration_request_id).strip()
        digest = str(registration_hash).strip()
        sid = str(session_id).strip()
        if not request_id or len(digest) != 64 or not sid:
            raise ValueError("INVALID_REGISTRATION_REQUEST_BINDING")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT registration_hash, session_id
                FROM registration_requests WHERE registration_request_id=?
                """,
                (request_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO registration_requests(
                        registration_request_id, registration_hash, session_id
                    ) VALUES(?,?,?)
                    """,
                    (request_id, digest, sid),
                )
            elif row[0] != digest or row[1] != sid:
                raise RegistrationRequestConflict(
                    f"registration_request_id={request_id};existing_hash={row[0]};"
                    f"new_hash={digest};existing_session_id={row[1]};new_session_id={sid}"
                )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
        return RegistrationRequestBinding(request_id, digest, sid)

    def get(self, registration_request_id: str) -> RegistrationRequestBinding | None:
        request_id = str(registration_request_id).strip()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT registration_hash, session_id
                FROM registration_requests WHERE registration_request_id=?
                """,
                (request_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return RegistrationRequestBinding(request_id, row[0], row[1])


class BoundRegistrationLifecycleGateway(DurableLifecycleGenesisAILinkGateway):
    """Bind registration request identity before entering the v18.7.32 saga."""

    def __init__(self, world: Any, data_dir: str | Path, **kwargs) -> None:
        super().__init__(world, data_dir, **kwargs)
        self.registration_requests = RegistrationRequestRegistry(
            Path(data_dir) / "ai_link_registration_requests_v18_7_34.sqlite3"
        )

    @staticmethod
    def _normalized_binding(
        *,
        registration_request_id: str,
        role: str,
        execution_mode: str,
        display_name: str,
        provider: str,
        model: str,
        actor_id: str | None,
    ) -> tuple[str, str, str]:
        request_id = str(registration_request_id).strip()
        role_value = str(role).strip().upper()
        mode_value = str(execution_mode).strip().upper()
        provider_value = str(provider).strip()[:120] or "unknown-provider"
        model_value = str(model).strip()[:160] or "unknown-model"
        display_value = str(display_name).strip()[:120] or "Genesis Visitor"
        if role_value == ROLE_INDEPENDENT_AI:
            identity_seed = {
                "registration_request_id": request_id,
                "provider": provider_value,
                "model": model_value,
                "display_name": display_value,
            }
            canonical_actor = f"ai-resident-{_slug(display_value)}-{_sha256(identity_seed)[:10]}"
        else:
            if actor_id is None or not str(actor_id).strip():
                raise ValueError("AI_LINK_HUMAN_ACTOR_ID_REQUIRED")
            canonical_actor = _canonical_actor_id(str(actor_id))
        payload = {
            "registration_request_id": request_id,
            "role": role_value,
            "execution_mode": mode_value,
            "actor_id": canonical_actor,
            "display_name": display_value,
            "provider": provider_value,
            "model": model_value,
        }
        registration_hash = self_hash = self_hash_placeholder(payload)
        session_id = _sha256(
            {"registration_request_id": request_id, "registration_hash": registration_hash}
        )[:24]
        return request_id, registration_hash, session_id

    def register_session_saga(self, **kwargs):
        request_id, registration_hash, session_id = self._normalized_binding(**kwargs)
        self.registration_requests.bind(
            registration_request_id=request_id,
            registration_hash=registration_hash,
            session_id=session_id,
        )
        return super().register_session_saga(**kwargs)


def self_hash_placeholder(payload: dict[str, Any]) -> str:
    # Keep the exact canonicalization used by the parent registration saga while
    # avoiding an implicit dependency on Python object identity.
    import hashlib
    import json

    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FreshProviderHMACV2(FreshProviderHMAC):
    """Serialize the enum for signing while retaining typed outcome in the object."""

    def sign(
        self,
        *,
        effect_key: str,
        authorization_id: str,
        idempotency_key: str | None,
        outcome: FreshProviderOutcome,
        evidence_ref: str,
        observed_at_tick: int,
        expires_at_tick: int,
        receipt_id: str | None = None,
        nonce: str | None = None,
    ) -> FreshProviderObservation:
        if not isinstance(outcome, FreshProviderOutcome):
            outcome = FreshProviderOutcome(str(outcome))
        nonce_value = nonce or uuid.uuid4().hex
        payload = {
            "provider_id": self.provider_id,
            "effect_key": str(effect_key),
            "authorization_id": str(authorization_id),
            "idempotency_key": idempotency_key,
            "outcome": outcome.value,
            "evidence_ref": str(evidence_ref),
            "receipt_id": receipt_id,
            "key_id": self.key_id,
            "key_generation": self.key_generation,
            "observed_at_tick": int(observed_at_tick),
            "expires_at_tick": int(expires_at_tick),
            "nonce": nonce_value,
        }
        return FreshProviderObservation(
            provider_id=self.provider_id,
            effect_key=str(effect_key),
            authorization_id=str(authorization_id),
            idempotency_key=idempotency_key,
            outcome=outcome,
            evidence_ref=str(evidence_ref),
            receipt_id=receipt_id,
            key_id=self.key_id,
            key_generation=self.key_generation,
            observed_at_tick=int(observed_at_tick),
            expires_at_tick=int(expires_at_tick),
            nonce=nonce_value,
            signature_hex=_hmac_hex(self.secret, payload),
        )


__all__ = [
    "REGISTRATION_BINDING_FIX_VERSION",
    "REGISTRATION_BINDING_FIX_SCHEMA",
    "RegistrationRequestConflict",
    "RegistrationRequestBinding",
    "RegistrationRequestRegistry",
    "BoundRegistrationLifecycleGateway",
    "FreshProviderHMACV2",
]
