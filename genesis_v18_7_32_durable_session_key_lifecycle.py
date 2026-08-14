# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.32 — durable session writes and key/freshness lifecycle.

This descendant addresses two different persistence boundaries without claiming
that they are one transaction:

1. AI-link session JSON writes use a unique same-directory temporary file,
   flush+fsync before ``os.replace``, final-file fsync, and POSIX directory fsync
   where the platform exposes it. Windows receives file-level fsync and atomic
   same-volume replacement, but directory-entry power-loss durability is kept
   outside the claim ceiling.
2. Reference HMAC lineage/provider evidence is admitted only through a durable
   key-policy registry with generation, not-before, not-after and revocation.
   Provider evidence additionally binds observation time, expiry and a nonce;
   accepted nonces are idempotently recorded so the same signed observation can
   be retried while nonce substitution is rejected.

A separate saga registration API writes a PENDING session intent before an
AUTHORITATIVE world registration. It prevents an *invisible* world-first
registration attempt: after a crash, a durable pending session remains available
for reconciliation. It is not a shared cross-store transaction and therefore is
not described as atomic.

Cryptographic claim boundary: HMAC proves binding to a configured key and the
key policy proves local eligibility. Neither proves objective genealogy nor the
truth of an external provider-world statement.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis_v18_7_19_ai_link_play import (
    AI_LINK_PROTOCOL_SCHEMA,
    AI_LINK_STORE_SCHEMA,
    AI_LINK_INTERFACE_VERSION,
    MODE_AUTHORITATIVE,
    MODE_NARRATIVE,
    ROLE_AI_INTERFACE,
    ROLE_HUMAN_THROUGH_AI,
    ROLE_INDEPENDENT_AI,
    SUPPORTED_EXECUTION_MODES,
    SUPPORTED_ROLES,
    GenesisAILinkGateway,
    _canonical_actor_id,
    _sha256,
    _slug,
)
from janus_portable_lock_v2 import PortableProcessLockV2

DURABLE_SESSION_KEY_VERSION = "18.7.32"
DURABLE_SESSION_KEY_SCHEMA = "janus.genesis.durable_session_key_lifecycle.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hmac_hex(secret: bytes, payload: Mapping[str, Any]) -> str:
    return hmac.new(secret, _canonical_json(dict(payload)).encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class DurableWriteReceipt:
    path: str
    temp_was_unique: bool
    temp_file_fsynced: bool
    replaced: bool
    final_file_fsynced: bool
    directory_fsynced: bool
    directory_fsync_supported: bool


class DurableJsonWriter:
    """Best-effort crash-durable same-directory JSON replacement."""

    def write(self, path: str | Path, value: Mapping[str, Any]) -> DurableWriteReceipt:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # NamedTemporaryFile is opened in the destination directory so replace
        # stays on one filesystem. delete=False permits os.replace on Windows.
        temp_path: Path | None = None
        directory_synced = False
        directory_supported = os.name != "nt"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_path, target)
            temp_path = None

            # Re-open the final name and fsync the file itself on both platforms.
            with target.open("rb") as final_handle:
                os.fsync(final_handle.fileno())

            if directory_supported:
                flags = os.O_RDONLY
                if hasattr(os, "O_DIRECTORY"):
                    flags |= os.O_DIRECTORY
                dir_fd = os.open(str(target.parent), flags)
                try:
                    os.fsync(dir_fd)
                    directory_synced = True
                finally:
                    os.close(dir_fd)

            return DurableWriteReceipt(
                path=str(target),
                temp_was_unique=True,
                temp_file_fsynced=True,
                replaced=True,
                final_file_fsynced=True,
                directory_fsynced=directory_synced,
                directory_fsync_supported=directory_supported,
            )
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass


class SessionSagaCrashPoint(str, Enum):
    AFTER_PENDING_SESSION_BEFORE_WORLD = "AFTER_PENDING_SESSION_BEFORE_WORLD"
    AFTER_WORLD_BEFORE_ACTIVATION = "AFTER_WORLD_BEFORE_ACTIVATION"


class SessionSagaCrashInjector:
    def __init__(self, *points: SessionSagaCrashPoint | str) -> None:
        self.remaining = {
            SessionSagaCrashPoint(p.value if isinstance(p, SessionSagaCrashPoint) else str(p))
            for p in points
        }

    def hit(self, point: SessionSagaCrashPoint) -> None:
        if point in self.remaining:
            self.remaining.remove(point)
            raise RuntimeError(f"INJECTED_SESSION_SAGA_CRASH:{point.value}")


class DurableLifecycleGenesisAILinkGateway(GenesisAILinkGateway):
    """v18.7.19 semantics with one v2 lifecycle lock and durable JSON writes."""

    def __init__(
        self,
        world: Any,
        data_dir: str | Path,
        *,
        crash_injector: SessionSagaCrashInjector | None = None,
    ) -> None:
        super().__init__(world, data_dir)
        self.lifecycle_lock = PortableProcessLockV2(
            Path(data_dir) / "ai_link_session_lifecycle_v18_7_32.lock"
        )
        self.durable_writer = DurableJsonWriter()
        self.last_write_receipt: DurableWriteReceipt | None = None
        self.crash_injector = crash_injector or SessionSagaCrashInjector()

    def _write(self, store: dict[str, Any]) -> None:
        self.last_write_receipt = self.durable_writer.write(self.path, store)

    # Legacy-compatible methods remain available, but only the explicit saga
    # registration method below has the world/session recovery protocol.
    def register_session(self, **kwargs):
        with self.lifecycle_lock.exclusive():
            return GenesisAILinkGateway.register_session(self, **kwargs)

    def register_independent_agent(self, **kwargs):
        # Avoid nested OS-lock acquisition: route directly through the one
        # register_session lock domain rather than locking twice.
        return self.register_session(
            role=ROLE_INDEPENDENT_AI,
            display_name=kwargs["display_name"],
            provider=kwargs["provider"],
            model=kwargs["model"],
            execution_mode=kwargs.get("execution_mode", MODE_AUTHORITATIVE),
        )

    def process_turn(self, *args, **kwargs):
        with self.lifecycle_lock.exclusive():
            return GenesisAILinkGateway.process_turn(self, *args, **kwargs)

    def close_session(self, *args, **kwargs):
        with self.lifecycle_lock.exclusive():
            return GenesisAILinkGateway.close_session(self, *args, **kwargs)

    def session_state(self, *args, **kwargs):
        with self.lifecycle_lock.shared():
            return GenesisAILinkGateway.session_state(self, *args, **kwargs)

    def export_capsule(self, *args, **kwargs):
        with self.lifecycle_lock.shared():
            return GenesisAILinkGateway.export_capsule(self, *args, **kwargs)

    def verify_store(self, *args, **kwargs):
        with self.lifecycle_lock.shared():
            return GenesisAILinkGateway.verify_store(self, *args, **kwargs)

    @staticmethod
    def _registration_hash(payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(_canonical_json(dict(payload)).encode("utf-8")).hexdigest()

    def register_session_saga(
        self,
        *,
        registration_request_id: str,
        role: str,
        execution_mode: str,
        display_name: str,
        provider: str,
        model: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        """Recoverable registration with durable PENDING state before world call.

        Same registration_request_id + different normalized parameters fails
        closed. A PENDING authoritative session cannot process turns.
        """
        request_id = str(registration_request_id).strip()
        if not request_id or len(request_id) > 240:
            raise ValueError("REGISTRATION_REQUEST_ID_REQUIRED")
        role = str(role).strip().upper()
        execution_mode = str(execution_mode).strip().upper()
        if role not in SUPPORTED_ROLES:
            raise ValueError(f"AI_LINK_UNSUPPORTED_ROLE:{role}")
        if execution_mode not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(f"AI_LINK_UNSUPPORTED_EXECUTION_MODE:{execution_mode}")
        provider = str(provider).strip()[:120] or "unknown-provider"
        model = str(model).strip()[:160] or "unknown-model"
        display_name = str(display_name).strip()[:120] or "Genesis Visitor"

        with self.lifecycle_lock.exclusive():
            store = self._load()
            if role == ROLE_INDEPENDENT_AI:
                identity_seed = {
                    "registration_request_id": request_id,
                    "provider": provider,
                    "model": model,
                    "display_name": display_name,
                }
                canonical_actor = f"ai-resident-{_slug(display_name)}-{_sha256(identity_seed)[:10]}"
            else:
                if actor_id is None or not str(actor_id).strip():
                    raise ValueError("AI_LINK_HUMAN_ACTOR_ID_REQUIRED")
                canonical_actor = _canonical_actor_id(str(actor_id))

            registration_payload = {
                "registration_request_id": request_id,
                "role": role,
                "execution_mode": execution_mode,
                "actor_id": canonical_actor,
                "display_name": display_name,
                "provider": provider,
                "model": model,
            }
            registration_hash = self._registration_hash(registration_payload)
            session_id = _sha256(
                {"registration_request_id": request_id, "registration_hash": registration_hash}
            )[:24]

            existing = store["sessions"].get(session_id)
            if isinstance(existing, dict):
                internal = existing.get("internal") if isinstance(existing.get("internal"), dict) else {}
                if internal.get("registration_hash") != registration_hash:
                    raise RuntimeError("AI_LINK_REGISTRATION_REQUEST_CONFLICT")
                if existing.get("status") == "ACTIVE":
                    return self._safe_session(existing)
                if existing.get("status") != "PENDING_WORLD_REGISTRATION":
                    raise RuntimeError("AI_LINK_REGISTRATION_UNKNOWN_PENDING_STATE")
                session = existing
            else:
                # Prevent one actor from being rebound under a different display
                # name through the saga path.
                if role != ROLE_INDEPENDENT_AI:
                    for other in store["sessions"].values():
                        if (
                            isinstance(other, dict)
                            and other.get("actor_id") == canonical_actor
                            and other.get("display_name") != display_name
                        ):
                            raise ValueError("AI_LINK_ACTOR_ID_ALREADY_BOUND_TO_DIFFERENT_NAME")

                autonomous = role == ROLE_INDEPENDENT_AI
                session = {
                    "session_id": session_id,
                    "schema": AI_LINK_PROTOCOL_SCHEMA,
                    "interface_version": AI_LINK_INTERFACE_VERSION,
                    "role": role,
                    "execution_mode": execution_mode,
                    "actor_id": canonical_actor,
                    "display_name": display_name,
                    "model_identity": {
                        "provider_label": provider,
                        "model_label": model,
                        "identity_verified_by_protocol": False,
                    },
                    "status": (
                        "PENDING_WORLD_REGISTRATION"
                        if execution_mode == MODE_AUTHORITATIVE
                        else "ACTIVE"
                    ),
                    "autonomous_turns_allowed": autonomous,
                    "human_confirmation_required": role == ROLE_AI_INTERFACE,
                    "human_identity_claimed": False if autonomous else True,
                    "consciousness_status": (
                        "NOT_ESTABLISHED_BY_PROTOCOL" if autonomous else "NOT_APPLICABLE"
                    ),
                    "legal_personhood_claimed": False,
                    "world_authority": False,
                    "private_human_memory_access": False,
                    "direct_state_write_allowed": False,
                    "runtime_mediation_required": True,
                    "turns": [],
                    "next_sequence": 1,
                    "internal": {
                        "registration_request_id": request_id,
                        "registration_hash": registration_hash,
                        "registration_saga": "PENDING_OR_ACTIVE",
                    },
                }
                session["session_hash"] = _sha256(
                    {k: v for k, v in session.items() if k != "session_hash"}
                )
                store["sessions"][session_id] = session
                store["events"].append(
                    {
                        "kind": "AI_LINK_SESSION_REGISTRATION_INTENT_DURABLE",
                        "session_id": session_id,
                        "registration_request_id": request_id,
                        "execution_mode": execution_mode,
                    }
                )
                self._write(store)

            if execution_mode == MODE_NARRATIVE:
                return self._safe_session(session)

            self.crash_injector.hit(SessionSagaCrashPoint.AFTER_PENDING_SESSION_BEFORE_WORLD)
            # Recovery may call this again after a prior world-first partial
            # attempt. The world implementation must therefore either be
            # idempotent for the same actor/display binding or expose a separate
            # existence/reconciliation contract. This module does not assume
            # cross-store atomicity.
            self.world.register_player(canonical_actor, display_name=display_name)
            self.crash_injector.hit(SessionSagaCrashPoint.AFTER_WORLD_BEFORE_ACTIVATION)

            store = self._load()
            current = store["sessions"].get(session_id)
            if not isinstance(current, dict):
                raise RuntimeError("AI_LINK_PENDING_SESSION_DISAPPEARED")
            internal = current.get("internal") if isinstance(current.get("internal"), dict) else {}
            if internal.get("registration_hash") != registration_hash:
                raise RuntimeError("AI_LINK_REGISTRATION_HASH_DRIFT")
            current["status"] = "ACTIVE"
            internal["registration_saga"] = "SETTLED"
            current["internal"] = internal
            current["session_hash"] = _sha256(
                {k: v for k, v in current.items() if k != "session_hash"}
            )
            store["events"].append(
                {
                    "kind": "AI_LINK_SESSION_REGISTRATION_SETTLED",
                    "session_id": session_id,
                    "registration_request_id": request_id,
                }
            )
            self._write(store)
            return self._safe_session(current)


@dataclass(frozen=True)
class TrustKeyRecord:
    key_id: str
    purpose: str
    generation: int
    not_before_tick: int
    not_after_tick: int
    revoked_at_tick: int | None


class TrustKeyRegistry:
    """Durable local eligibility policy for reference verifier keys."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trust_keys (
                    key_id TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    not_before_tick INTEGER NOT NULL,
                    not_after_tick INTEGER NOT NULL,
                    revoked_at_tick INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accepted_evidence_nonces (
                    namespace TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    evidence_sha256 TEXT NOT NULL,
                    PRIMARY KEY(namespace, nonce)
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

    def register_key(
        self,
        *,
        key_id: str,
        purpose: str,
        generation: int,
        not_before_tick: int,
        not_after_tick: int,
    ) -> TrustKeyRecord:
        key = str(key_id).strip()
        purpose_text = str(purpose).strip()
        if not key or not purpose_text:
            raise ValueError("KEY_ID_AND_PURPOSE_REQUIRED")
        if int(generation) < 1 or int(not_after_tick) <= int(not_before_tick):
            raise ValueError("INVALID_KEY_GENERATION_OR_WINDOW")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            max_generation = conn.execute(
                "SELECT MAX(generation) FROM trust_keys WHERE purpose=?",
                (purpose_text,),
            ).fetchone()[0]
            if max_generation is not None and int(generation) <= int(max_generation):
                raise ValueError("KEY_GENERATION_MUST_INCREASE_PER_PURPOSE")
            conn.execute(
                """
                INSERT INTO trust_keys(
                    key_id,purpose,generation,not_before_tick,not_after_tick,revoked_at_tick
                ) VALUES(?,?,?,?,?,NULL)
                """,
                (key, purpose_text, int(generation), int(not_before_tick), int(not_after_tick)),
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
        return self.get(key)

    def get(self, key_id: str) -> TrustKeyRecord:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT key_id,purpose,generation,not_before_tick,not_after_tick,revoked_at_tick
                FROM trust_keys WHERE key_id=?
                """,
                (str(key_id).strip(),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise KeyError("TRUST_KEY_NOT_FOUND")
        return TrustKeyRecord(
            key_id=row[0], purpose=row[1], generation=int(row[2]),
            not_before_tick=int(row[3]), not_after_tick=int(row[4]),
            revoked_at_tick=None if row[5] is None else int(row[5]),
        )

    def revoke(self, key_id: str, *, revoked_at_tick: int) -> TrustKeyRecord:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE trust_keys SET revoked_at_tick=?
                WHERE key_id=? AND revoked_at_tick IS NULL
                """,
                (int(revoked_at_tick), str(key_id).strip()),
            )
            if cur.rowcount != 1:
                existing = conn.execute(
                    "SELECT revoked_at_tick FROM trust_keys WHERE key_id=?",
                    (str(key_id).strip(),),
                ).fetchone()
                if existing is None:
                    raise KeyError("TRUST_KEY_NOT_FOUND")
                if int(existing[0]) != int(revoked_at_tick):
                    raise ValueError("KEY_ALREADY_REVOKED_AT_DIFFERENT_TICK")
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
        return self.get(key_id)

    def eligible(
        self,
        *,
        key_id: str,
        purpose: str,
        generation: int,
        issued_at_tick: int,
        now_tick: int,
    ) -> bool:
        try:
            record = self.get(key_id)
        except KeyError:
            return False
        if record.purpose != str(purpose) or record.generation != int(generation):
            return False
        if not (record.not_before_tick <= int(issued_at_tick) <= record.not_after_tick):
            return False
        if int(now_tick) > record.not_after_tick:
            return False
        if record.revoked_at_tick is not None and int(now_tick) >= record.revoked_at_tick:
            return False
        return True

    def accept_nonce(self, *, namespace: str, nonce: str, evidence_sha256: str) -> bool:
        ns = str(namespace).strip()
        token = str(nonce).strip()
        digest = str(evidence_sha256).strip()
        if not ns or not token or len(token) > 240 or len(digest) != 64:
            raise ValueError("INVALID_EVIDENCE_NONCE_RECORD")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT evidence_sha256 FROM accepted_evidence_nonces WHERE namespace=? AND nonce=?",
                (ns, token),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO accepted_evidence_nonces(namespace,nonce,evidence_sha256) VALUES(?,?,?)",
                    (ns, token, digest),
                )
            elif row[0] != digest:
                raise ValueError("EVIDENCE_NONCE_REUSED_WITH_DIFFERENT_PAYLOAD")
            conn.execute("COMMIT")
            return True
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()


@dataclass(frozen=True)
class LifecycleLineageAttestation:
    issuer_id: str
    key_id: str
    key_generation: int
    attestation_id: str
    face_id: str
    lineage_root: str
    parent_face_id: str | None
    issued_at_tick: int
    expires_at_tick: int
    signature_hex: str

    def payload(self) -> dict[str, Any]:
        return {
            "issuer_id": self.issuer_id,
            "key_id": self.key_id,
            "key_generation": self.key_generation,
            "attestation_id": self.attestation_id,
            "face_id": self.face_id,
            "lineage_root": self.lineage_root,
            "parent_face_id": self.parent_face_id,
            "issued_at_tick": self.issued_at_tick,
            "expires_at_tick": self.expires_at_tick,
        }


class LifecycleLineageHMAC:
    def __init__(
        self,
        *,
        issuer_id: str,
        key_id: str,
        key_generation: int,
        secret: bytes,
        registry: TrustKeyRegistry,
    ) -> None:
        self.issuer_id = str(issuer_id).strip()
        self.key_id = str(key_id).strip()
        self.key_generation = int(key_generation)
        self.secret = bytes(secret)
        self.registry = registry
        if not self.issuer_id or not self.key_id or len(self.secret) < 16:
            raise ValueError("LINEAGE_LIFECYCLE_KEY_REQUIRED")

    @property
    def purpose(self) -> str:
        return f"lineage:{self.issuer_id}"

    def attest(
        self,
        *,
        face_id: str,
        lineage_root: str,
        issued_at_tick: int,
        expires_at_tick: int,
        parent_face_id: str | None = None,
        attestation_id: str | None = None,
    ) -> LifecycleLineageAttestation:
        payload = {
            "issuer_id": self.issuer_id,
            "key_id": self.key_id,
            "key_generation": self.key_generation,
            "attestation_id": attestation_id or f"LINEAGE-{uuid.uuid4().hex}",
            "face_id": str(face_id).strip(),
            "lineage_root": str(lineage_root).strip(),
            "parent_face_id": None if parent_face_id is None else str(parent_face_id).strip() or None,
            "issued_at_tick": int(issued_at_tick),
            "expires_at_tick": int(expires_at_tick),
        }
        if not payload["face_id"] or not payload["lineage_root"]:
            raise ValueError("FACE_AND_LINEAGE_ROOT_REQUIRED")
        return LifecycleLineageAttestation(
            **payload,
            signature_hex=_hmac_hex(self.secret, payload),
        )

    def verify(self, claim: LifecycleLineageAttestation, *, now_tick: int) -> bool:
        if claim.issuer_id != self.issuer_id or claim.key_id != self.key_id:
            return False
        if claim.key_generation != self.key_generation or int(now_tick) > claim.expires_at_tick:
            return False
        if not self.registry.eligible(
            key_id=claim.key_id,
            purpose=self.purpose,
            generation=claim.key_generation,
            issued_at_tick=claim.issued_at_tick,
            now_tick=now_tick,
        ):
            return False
        return hmac.compare_digest(_hmac_hex(self.secret, claim.payload()), claim.signature_hex)


@dataclass(frozen=True)
class LifecycleReviewCandidate:
    face_id: str
    attestation: LifecycleLineageAttestation
    routing_priority: float = 1.0
    novel_counterevidence: bool = False
    red_team_capable: bool = True


@dataclass(frozen=True)
class LifecycleReviewAssignment:
    face_id: str
    lineage_root: str
    role: str
    authority_weight: int = 0
    world_authority_granted: bool = False


class LifecycleLineageReviewPlanner:
    """Verify origin and reviewers under current key lifecycle before seating."""

    def __init__(self, verifiers: Mapping[tuple[str, str], LifecycleLineageHMAC]) -> None:
        self.verifiers = dict(verifiers)

    def _root(self, candidate: LifecycleReviewCandidate, *, now_tick: int) -> str:
        claim = candidate.attestation
        if claim.face_id != candidate.face_id:
            raise ValueError("LINEAGE_FACE_ID_MISMATCH")
        verifier = self.verifiers.get((claim.issuer_id, claim.key_id))
        if verifier is None or not verifier.verify(claim, now_tick=now_tick):
            raise ValueError("LINEAGE_ATTESTATION_NOT_CURRENTLY_VERIFIED")
        return claim.lineage_root

    def plan(
        self,
        *,
        origin: LifecycleReviewCandidate,
        candidates: Sequence[LifecycleReviewCandidate],
        now_tick: int,
        required_reviews: int = 2,
    ) -> tuple[LifecycleReviewAssignment, ...]:
        origin_root = self._root(origin, now_tick=now_tick)
        by_root: dict[str, LifecycleReviewCandidate] = {}
        for candidate in candidates:
            root = self._root(candidate, now_tick=now_tick)
            if root == origin_root:
                continue
            existing = by_root.get(root)
            if existing is None or (
                bool(candidate.novel_counterevidence), float(candidate.routing_priority)
            ) > (
                bool(existing.novel_counterevidence), float(existing.routing_priority)
            ):
                by_root[root] = candidate
        if len(by_root) < int(required_reviews):
            raise ValueError("CURRENTLY_VERIFIED_INDEPENDENT_LINEAGES_UNAVAILABLE")
        ordered = sorted(
            by_root.items(),
            key=lambda item: (
                0 if item[1].novel_counterevidence else 1,
                -float(item[1].routing_priority),
                item[0],
                item[1].face_id,
            ),
        )[: int(required_reviews)]
        assignments = []
        red_assigned = False
        for root, candidate in ordered:
            role = "INDEPENDENT_REVIEW"
            if candidate.red_team_capable and not red_assigned:
                role = "COUNTEREXAMPLE_CHALLENGE"
                red_assigned = True
            assignments.append(
                LifecycleReviewAssignment(
                    face_id=candidate.face_id,
                    lineage_root=root,
                    role=role,
                    authority_weight=0,
                    world_authority_granted=False,
                )
            )
        return tuple(assignments)


class FreshProviderOutcome(str, Enum):
    SETTLED = "SETTLED"
    NO_EFFECT = "NO_EFFECT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FreshProviderObservation:
    provider_id: str
    effect_key: str
    authorization_id: str
    idempotency_key: str | None
    outcome: FreshProviderOutcome
    evidence_ref: str
    receipt_id: str | None
    key_id: str
    key_generation: int
    observed_at_tick: int
    expires_at_tick: int
    nonce: str
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
            "key_id": self.key_id,
            "key_generation": self.key_generation,
            "observed_at_tick": self.observed_at_tick,
            "expires_at_tick": self.expires_at_tick,
            "nonce": self.nonce,
        }


class FreshProviderHMAC:
    def __init__(
        self,
        *,
        provider_id: str,
        key_id: str,
        key_generation: int,
        secret: bytes,
        registry: TrustKeyRegistry,
        max_age_ticks: int,
    ) -> None:
        self.provider_id = str(provider_id).strip()
        self.key_id = str(key_id).strip()
        self.key_generation = int(key_generation)
        self.secret = bytes(secret)
        self.registry = registry
        self.max_age_ticks = int(max_age_ticks)
        if not self.provider_id or not self.key_id or len(self.secret) < 16 or self.max_age_ticks < 0:
            raise ValueError("PROVIDER_LIFECYCLE_KEY_REQUIRED")

    @property
    def purpose(self) -> str:
        return f"provider:{self.provider_id}"

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
            "nonce": nonce or uuid.uuid4().hex,
        }
        return FreshProviderObservation(**payload, signature_hex=_hmac_hex(self.secret, payload))

    def verify(self, observation: FreshProviderObservation, *, now_tick: int) -> bool:
        if observation.provider_id != self.provider_id or observation.key_id != self.key_id:
            return False
        if observation.key_generation != self.key_generation:
            return False
        if int(now_tick) < observation.observed_at_tick or int(now_tick) > observation.expires_at_tick:
            return False
        if int(now_tick) - observation.observed_at_tick > self.max_age_ticks:
            return False
        if not self.registry.eligible(
            key_id=observation.key_id,
            purpose=self.purpose,
            generation=observation.key_generation,
            issued_at_tick=observation.observed_at_tick,
            now_tick=now_tick,
        ):
            return False
        return hmac.compare_digest(
            _hmac_hex(self.secret, observation.payload()), observation.signature_hex
        )


@dataclass(frozen=True)
class FreshProviderDecision:
    state: str
    safe_automatic_retry: bool
    receipt_id: str | None
    evidence_verified: bool


class FreshProviderReconciler:
    """Admission requires current key policy, freshness and idempotent nonce receipt."""

    def __init__(
        self,
        *,
        registry: TrustKeyRegistry,
        verifiers: Mapping[tuple[str, str], FreshProviderHMAC],
    ) -> None:
        self.registry = registry
        self.verifiers = dict(verifiers)

    def reconcile(self, *, binding: Any, observation: FreshProviderObservation, now_tick: int) -> FreshProviderDecision:
        structural = (
            observation.provider_id == binding.provider_id
            and observation.effect_key == binding.effect_key
            and observation.authorization_id == binding.authorization_id
            and observation.idempotency_key == binding.idempotency_key
        )
        if not structural:
            raise ValueError("FRESH_PROVIDER_EVIDENCE_BINDING_MISMATCH")
        verifier = self.verifiers.get((observation.provider_id, observation.key_id))
        verified = bool(verifier is not None and verifier.verify(observation, now_tick=now_tick))
        if not verified:
            return FreshProviderDecision(
                state="UNDETERMINED_PROVIDER_EVIDENCE_NOT_CURRENTLY_VERIFIED",
                safe_automatic_retry=False,
                receipt_id=None,
                evidence_verified=False,
            )

        digest = hashlib.sha256(_canonical_json(observation.payload()).encode("utf-8")).hexdigest()
        self.registry.accept_nonce(
            namespace=f"provider:{observation.provider_id}:{observation.authorization_id}",
            nonce=observation.nonce,
            evidence_sha256=digest,
        )

        if observation.outcome is FreshProviderOutcome.SETTLED:
            if not observation.receipt_id:
                raise ValueError("FRESH_VERIFIED_SETTLED_REQUIRES_RECEIPT")
            return FreshProviderDecision(
                state="SETTLED_BY_FRESH_AUTHORIZATION_BOUND_EVIDENCE",
                safe_automatic_retry=False,
                receipt_id=observation.receipt_id,
                evidence_verified=True,
            )
        if observation.outcome is FreshProviderOutcome.NO_EFFECT:
            return FreshProviderDecision(
                state="NO_EFFECT_BY_FRESH_AUTHORIZATION_BOUND_EVIDENCE",
                safe_automatic_retry=True,
                receipt_id=None,
                evidence_verified=True,
            )
        return FreshProviderDecision(
            state="UNDETERMINED_FRESH_VERIFIED_PROVIDER_UNKNOWN",
            safe_automatic_retry=False,
            receipt_id=None,
            evidence_verified=True,
        )


__all__ = [
    "DURABLE_SESSION_KEY_VERSION",
    "DURABLE_SESSION_KEY_SCHEMA",
    "DurableWriteReceipt",
    "DurableJsonWriter",
    "SessionSagaCrashPoint",
    "SessionSagaCrashInjector",
    "DurableLifecycleGenesisAILinkGateway",
    "TrustKeyRecord",
    "TrustKeyRegistry",
    "LifecycleLineageAttestation",
    "LifecycleLineageHMAC",
    "LifecycleReviewCandidate",
    "LifecycleReviewAssignment",
    "LifecycleLineageReviewPlanner",
    "FreshProviderOutcome",
    "FreshProviderObservation",
    "FreshProviderHMAC",
    "FreshProviderDecision",
    "FreshProviderReconciler",
]
