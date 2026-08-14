# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.25 — durable control journal, local process fencing,
provider idempotency binding, and deadline-aware bounded fairness.

This additive layer addresses crash/replay and same-host multi-process races in
the v6 face microcontrol line. It still executes no external world effect.

Claim boundary:
- the JSONL hash journal is durable only to the guarantees of the local
  filesystem and fsync implementation;
- SQLite fencing coordinates processes sharing the same SQLite database/file,
  not arbitrary distributed hosts;
- provider idempotency is a declared adapter contract, not something JANUS can
  infer or prove by itself;
- deadline/fairness scheduling grants attention only, never world authority.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DURABLE_CONTROL_VERSION = "18.7.25"
DURABLE_CONTROL_SCHEMA = "janus.genesis.durable_control.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class DurableControlError(RuntimeError):
    code = "DURABLE_CONTROL_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class JournalIntegrityError(DurableControlError):
    code = "JOURNAL_INTEGRITY_ERROR"


class FenceBusyError(DurableControlError):
    code = "EFFECT_FENCE_BUSY"


class StaleFenceTokenError(DurableControlError):
    code = "STALE_EFFECT_FENCE_TOKEN"


class ProviderBindingError(DurableControlError):
    code = "PROVIDER_IDEMPOTENCY_BINDING_ERROR"


@dataclass(frozen=True)
class JournalEntry:
    sequence: int
    event_type: str
    payload: Mapping[str, Any]
    prev_hash: str
    event_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
        }


class DurableHashJournal:
    """Append-only JSONL journal with file lock, hash chain, flush, and fsync."""

    GENESIS_HASH = "0" * 64

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._thread_lock = threading.RLock()

    @staticmethod
    def _entry_hash(sequence: int, event_type: str, payload: Mapping[str, Any], prev_hash: str) -> str:
        return _sha256(
            {
                "sequence": int(sequence),
                "event_type": event_type,
                "payload": dict(payload),
                "prev_hash": prev_hash,
            }
        )

    def _parse_text(self, text: str) -> list[JournalEntry]:
        entries: list[JournalEntry] = []
        prev_hash = self.GENESIS_HASH
        expected_sequence = 1
        for raw in text.splitlines():
            if not raw.strip():
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise JournalIntegrityError("INVALID_JSONL") from exc
            required = {"sequence", "event_type", "payload", "prev_hash", "event_hash"}
            if set(item) != required:
                raise JournalIntegrityError("JOURNAL_ENTRY_SCHEMA_MISMATCH")
            sequence = int(item["sequence"])
            event_type = str(item["event_type"])
            payload = item["payload"]
            if not isinstance(payload, dict):
                raise JournalIntegrityError("JOURNAL_PAYLOAD_MUST_BE_OBJECT")
            if sequence != expected_sequence:
                raise JournalIntegrityError("JOURNAL_SEQUENCE_GAP_OR_REORDER")
            if item["prev_hash"] != prev_hash:
                raise JournalIntegrityError("JOURNAL_PREV_HASH_MISMATCH")
            calculated = self._entry_hash(sequence, event_type, payload, prev_hash)
            if item["event_hash"] != calculated:
                raise JournalIntegrityError("JOURNAL_EVENT_HASH_MISMATCH")
            entry = JournalEntry(
                sequence=sequence,
                event_type=event_type,
                payload=dict(payload),
                prev_hash=prev_hash,
                event_hash=calculated,
            )
            entries.append(entry)
            prev_hash = calculated
            expected_sequence += 1
        return entries

    def replay(self) -> tuple[JournalEntry, ...]:
        with self._thread_lock:
            with self.path.open("r", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    text = handle.read()
                    return tuple(self._parse_text(text))
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def append(self, event_type: str, payload: Mapping[str, Any]) -> JournalEntry:
        if not event_type.strip():
            raise ValueError("EVENT_TYPE_REQUIRED")
        if not isinstance(payload, Mapping):
            raise ValueError("PAYLOAD_MAPPING_REQUIRED")
        with self._thread_lock:
            with self.path.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    handle.seek(0)
                    entries = self._parse_text(handle.read())
                    sequence = len(entries) + 1
                    prev_hash = entries[-1].event_hash if entries else self.GENESIS_HASH
                    normalized_payload = dict(payload)
                    event_hash = self._entry_hash(sequence, event_type.strip(), normalized_payload, prev_hash)
                    item = {
                        "sequence": sequence,
                        "event_type": event_type.strip(),
                        "payload": normalized_payload,
                        "prev_hash": prev_hash,
                        "event_hash": event_hash,
                    }
                    handle.seek(0, os.SEEK_END)
                    handle.write(_canonical_json(item) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    return JournalEntry(
                        sequence=sequence,
                        event_type=event_type.strip(),
                        payload=normalized_payload,
                        prev_hash=prev_hash,
                        event_hash=event_hash,
                    )
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def head_hash(self) -> str:
        entries = self.replay()
        return entries[-1].event_hash if entries else self.GENESIS_HASH


class ControlJournalProjection:
    """Deterministic replay projection for recovery-critical control facts."""

    def __init__(self) -> None:
        self.effects: dict[str, dict[str, Any]] = {}
        self.sagas: dict[str, str] = {}
        self.provider_bindings: dict[str, dict[str, Any]] = {}
        self.last_sequence = 0
        self.head_hash = DurableHashJournal.GENESIS_HASH

    def apply(self, entry: JournalEntry) -> None:
        p = dict(entry.payload)
        et = entry.event_type
        if et == "EFFECT_AUTHORIZATION_CANCELED":
            self.effects[p["effect_key"]] = {
                "state": p["state"],
                "authorization_id": p["authorization_id"],
                "cancellation_id": p["cancellation_id"],
            }
        elif et == "EFFECT_RECONCILED_NO_EFFECT":
            state = self.effects.setdefault(p["effect_key"], {})
            state.update(
                {
                    "state": "RECONCILED_NO_EFFECT",
                    "evidence_ref": p["evidence_ref"],
                }
            )
        elif et == "EFFECT_RECOVERY_AUTHORIZED":
            state = self.effects.setdefault(p["effect_key"], {})
            state.update(
                {
                    "state": "RECOVERY_AUTHORIZED",
                    "replacement_authorization_id": p["replacement_authorization_id"],
                    "prior_authorization_id": p["prior_authorization_id"],
                }
            )
        elif et == "EFFECT_RECEIPT_OBSERVED":
            state = self.effects.setdefault(p["effect_key"], {})
            state.update({"state": "SETTLED", "receipt_id": p["receipt_id"]})
        elif et == "SAGA_STATE":
            self.sagas[p["saga_id"]] = p["state"]
        elif et == "PROVIDER_BINDING":
            self.provider_bindings[p["effect_key"]] = dict(p)
        self.last_sequence = entry.sequence
        self.head_hash = entry.event_hash

    @classmethod
    def from_entries(cls, entries: tuple[JournalEntry, ...] | list[JournalEntry]) -> "ControlJournalProjection":
        projection = cls()
        for entry in entries:
            projection.apply(entry)
        return projection


@dataclass(frozen=True)
class FencingToken:
    effect_key: str
    holder_id: str
    generation: int
    lease_expires_tick: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "effect_key": self.effect_key,
            "holder_id": self.holder_id,
            "generation": self.generation,
            "lease_expires_tick": self.lease_expires_tick,
        }


class SQLiteEffectFenceStore:
    """Same-host/process-shared fencing store backed by SQLite transactions."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS effect_fences (
                    effect_key TEXT PRIMARY KEY,
                    holder_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    lease_expires_tick INTEGER NOT NULL,
                    state TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def acquire(
        self,
        *,
        effect_key: str,
        holder_id: str,
        now_tick: int,
        lease_ticks: int,
    ) -> FencingToken:
        if not effect_key or not holder_id:
            raise ValueError("EFFECT_AND_HOLDER_REQUIRED")
        if lease_ticks < 1:
            raise ValueError("LEASE_TICKS_MUST_BE_POSITIVE")
        expires = int(now_tick) + int(lease_ticks)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT holder_id, generation, lease_expires_tick, state FROM effect_fences WHERE effect_key=?",
                (effect_key,),
            ).fetchone()
            if row is None:
                generation = 1
                conn.execute(
                    "INSERT INTO effect_fences(effect_key,holder_id,generation,lease_expires_tick,state) VALUES(?,?,?,?,?)",
                    (effect_key, holder_id, generation, expires, "HELD"),
                )
            else:
                current_holder, current_generation, current_expires, state = row
                expired = int(current_expires) <= int(now_tick)
                if state == "HELD" and not expired:
                    raise FenceBusyError(f"effect={effect_key}; holder={current_holder}")
                generation = int(current_generation) + 1
                conn.execute(
                    "UPDATE effect_fences SET holder_id=?, generation=?, lease_expires_tick=?, state='HELD' WHERE effect_key=?",
                    (holder_id, generation, expires, effect_key),
                )
            conn.execute("COMMIT")
            return FencingToken(effect_key, holder_id, generation, expires)
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    def validate(self, token: FencingToken, *, now_tick: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT holder_id, generation, lease_expires_tick, state FROM effect_fences WHERE effect_key=?",
                (token.effect_key,),
            ).fetchone()
        if row is None:
            raise StaleFenceTokenError("FENCE_MISSING")
        holder, generation, expires, state = row
        if (
            state != "HELD"
            or holder != token.holder_id
            or int(generation) != token.generation
            or int(expires) != token.lease_expires_tick
            or int(expires) <= int(now_tick)
        ):
            raise StaleFenceTokenError()
        return True

    def renew(self, token: FencingToken, *, now_tick: int, lease_ticks: int) -> FencingToken:
        self.validate(token, now_tick=now_tick)
        if lease_ticks < 1:
            raise ValueError("LEASE_TICKS_MUST_BE_POSITIVE")
        new_expires = int(now_tick) + int(lease_ticks)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE effect_fences SET lease_expires_tick=?
                WHERE effect_key=? AND holder_id=? AND generation=? AND state='HELD'
                """,
                (new_expires, token.effect_key, token.holder_id, token.generation),
            )
            if cur.rowcount != 1:
                raise StaleFenceTokenError()
            conn.execute("COMMIT")
            return FencingToken(token.effect_key, token.holder_id, token.generation, new_expires)
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    def release(self, token: FencingToken, *, now_tick: int) -> None:
        self.validate(token, now_tick=now_tick)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE effect_fences SET state='RELEASED', lease_expires_tick=?
                WHERE effect_key=? AND holder_id=? AND generation=? AND state='HELD'
                """,
                (int(now_tick), token.effect_key, token.holder_id, token.generation),
            )
            if cur.rowcount != 1:
                raise StaleFenceTokenError()
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()


@dataclass(frozen=True)
class ProviderIdempotencyContract:
    provider_id: str
    supports_idempotency: bool
    supports_receipt_lookup: bool
    max_key_length: int = 64
    namespace: str = "janus"

    def __post_init__(self) -> None:
        if not self.provider_id or not self.namespace:
            raise ValueError("PROVIDER_AND_NAMESPACE_REQUIRED")
        if self.max_key_length < 24:
            raise ValueError("MAX_KEY_LENGTH_TOO_SMALL")


@dataclass(frozen=True)
class ProviderEffectBinding:
    provider_id: str
    effect_key: str
    authorization_id: str
    idempotency_key: str | None
    retry_policy: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "effect_key": self.effect_key,
            "authorization_id": self.authorization_id,
            "idempotency_key": self.idempotency_key,
            "retry_policy": self.retry_policy,
        }


class ProviderIdempotencyBinder:
    """Binds one JANUS effect key to a provider idempotency namespace."""

    def bind(
        self,
        contract: ProviderIdempotencyContract,
        *,
        effect_key: str,
        authorization_id: str,
    ) -> ProviderEffectBinding:
        if not effect_key or not authorization_id:
            raise ValueError("EFFECT_AND_AUTHORIZATION_REQUIRED")
        if contract.supports_idempotency:
            digest = _sha256(
                {
                    "provider_id": contract.provider_id,
                    "namespace": contract.namespace,
                    "effect_key": effect_key,
                }
            )
            prefix = f"{contract.namespace}-"
            key = (prefix + digest)[: contract.max_key_length]
            policy = "RETRY_ONLY_WITH_SAME_PROVIDER_IDEMPOTENCY_KEY"
        elif contract.supports_receipt_lookup:
            key = None
            policy = "LOOKUP_AUTHORITATIVE_PROVIDER_RECEIPT_BEFORE_RETRY"
        else:
            key = None
            policy = "BLOCK_RETRY_UNTIL_EXTERNAL_RECONCILIATION"
        return ProviderEffectBinding(
            provider_id=contract.provider_id,
            effect_key=effect_key,
            authorization_id=authorization_id,
            idempotency_key=key,
            retry_policy=policy,
        )

    @staticmethod
    def same_effect_same_key(a: ProviderEffectBinding, b: ProviderEffectBinding) -> bool:
        return (
            a.provider_id == b.provider_id
            and a.effect_key == b.effect_key
            and a.idempotency_key is not None
            and a.idempotency_key == b.idempotency_key
        )


@dataclass(frozen=True)
class DurableDispatchIntent:
    intent_id: str
    effect_key: str
    authorization_id: str
    holder_id: str
    fence: FencingToken
    provider_binding: ProviderEffectBinding
    journal_event_hash: str


class JournaledFencedDispatchCoordinator:
    """Durably records intent after acquiring a same-host fencing token.

    Returning a DurableDispatchIntent means only that the control-plane intent is
    journaled and fenced. It does not mean the external effect was executed.
    """

    def __init__(
        self,
        *,
        journal: DurableHashJournal,
        fences: SQLiteEffectFenceStore,
        binder: ProviderIdempotencyBinder | None = None,
    ) -> None:
        self.journal = journal
        self.fences = fences
        self.binder = binder or ProviderIdempotencyBinder()

    def prepare(
        self,
        *,
        effect_key: str,
        authorization_id: str,
        holder_id: str,
        contract: ProviderIdempotencyContract,
        now_tick: int,
        lease_ticks: int = 10,
    ) -> DurableDispatchIntent:
        fence = self.fences.acquire(
            effect_key=effect_key,
            holder_id=holder_id,
            now_tick=now_tick,
            lease_ticks=lease_ticks,
        )
        binding = self.binder.bind(
            contract,
            effect_key=effect_key,
            authorization_id=authorization_id,
        )
        intent_id = "DURABLE-DISPATCH-" + _sha256(
            {
                "effect_key": effect_key,
                "authorization_id": authorization_id,
                "holder_id": holder_id,
                "fence_generation": fence.generation,
                "provider_id": contract.provider_id,
                "provider_key": binding.idempotency_key,
            }
        )[:24]
        entry = self.journal.append(
            "DISPATCH_INTENT_DURABLE",
            {
                "intent_id": intent_id,
                "effect_key": effect_key,
                "authorization_id": authorization_id,
                "holder_id": holder_id,
                "fence_generation": fence.generation,
                "lease_expires_tick": fence.lease_expires_tick,
                "provider_id": binding.provider_id,
                "provider_idempotency_key": binding.idempotency_key,
                "retry_policy": binding.retry_policy,
            },
        )
        self.journal.append("PROVIDER_BINDING", binding.as_dict())
        return DurableDispatchIntent(
            intent_id=intent_id,
            effect_key=effect_key,
            authorization_id=authorization_id,
            holder_id=holder_id,
            fence=fence,
            provider_binding=binding,
            journal_event_hash=entry.event_hash,
        )

    def validate_before_effect(self, intent: DurableDispatchIntent, *, now_tick: int) -> bool:
        return self.fences.validate(intent.fence, now_tick=now_tick)

    def record_receipt(
        self,
        intent: DurableDispatchIntent,
        *,
        receipt_id: str,
        provider_status: str,
        now_tick: int,
    ) -> JournalEntry:
        if not receipt_id or not provider_status:
            raise ValueError("RECEIPT_AND_PROVIDER_STATUS_REQUIRED")
        self.fences.validate(intent.fence, now_tick=now_tick)
        entry = self.journal.append(
            "EFFECT_RECEIPT_OBSERVED",
            {
                "effect_key": intent.effect_key,
                "authorization_id": intent.authorization_id,
                "receipt_id": receipt_id,
                "provider_id": intent.provider_binding.provider_id,
                "provider_idempotency_key": intent.provider_binding.idempotency_key,
                "provider_status": provider_status,
                "fence_generation": intent.fence.generation,
            },
        )
        self.fences.release(intent.fence, now_tick=now_tick)
        return entry


@dataclass
class DeadlineFairTicket:
    ticket_id: str
    effect_key: str
    face_id: str
    routing_priority: float
    deadline_tick: int | None
    risk_rank: int
    sequence: int
    bypass_count: int = 0
    authority_weight: int = 0


class DeadlineBoundedFairQueue:
    """Deadline-aware attention queue with bounded deadline bursts and bypass."""

    RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

    def __init__(self, *, max_bypass: int = 3, max_deadline_burst: int = 2) -> None:
        if max_bypass < 1 or max_deadline_burst < 1:
            raise ValueError("FAIRNESS_BOUNDS_MUST_BE_POSITIVE")
        self.max_bypass = int(max_bypass)
        self.max_deadline_burst = int(max_deadline_burst)
        self._deadline_burst = 0
        self._sequence = 0
        self._tickets: dict[str, DeadlineFairTicket] = {}
        self._lock = threading.RLock()

    def enqueue(
        self,
        *,
        effect_key: str,
        face_id: str,
        routing_priority: float,
        risk_level: str = "LOW",
        deadline_tick: int | None = None,
        ticket_id: str | None = None,
    ) -> DeadlineFairTicket:
        risk = risk_level.upper()
        if risk not in self.RISK_RANK:
            raise ValueError("UNKNOWN_RISK_LEVEL")
        with self._lock:
            self._sequence += 1
            ticket = DeadlineFairTicket(
                ticket_id=ticket_id or f"DEADLINE-REVIEW-{uuid.uuid4().hex}",
                effect_key=effect_key,
                face_id=face_id,
                routing_priority=float(routing_priority),
                deadline_tick=None if deadline_tick is None else int(deadline_tick),
                risk_rank=self.RISK_RANK[risk],
                sequence=self._sequence,
                bypass_count=0,
                authority_weight=0,
            )
            if ticket.ticket_id in self._tickets:
                raise ValueError("DUPLICATE_DEADLINE_TICKET")
            self._tickets[ticket.ticket_id] = ticket
            return ticket

    def next_ticket(self, *, now_tick: int) -> DeadlineFairTicket | None:
        with self._lock:
            if not self._tickets:
                return None
            candidates = list(self._tickets.values())
            mandatory = [t for t in candidates if t.bypass_count >= self.max_bypass]
            overdue = [
                t for t in candidates
                if t.deadline_tick is not None and t.deadline_tick <= int(now_tick)
            ]

            if mandatory and self._deadline_burst >= self.max_deadline_burst:
                selected = min(mandatory, key=lambda t: (t.sequence, t.ticket_id))
                self._deadline_burst = 0
            elif overdue:
                selected = min(
                    overdue,
                    key=lambda t: (
                        t.deadline_tick,
                        -t.risk_rank,
                        -t.routing_priority,
                        t.sequence,
                        t.ticket_id,
                    ),
                )
                self._deadline_burst += 1
            elif mandatory:
                selected = min(mandatory, key=lambda t: (t.sequence, t.ticket_id))
                self._deadline_burst = 0
            else:
                selected = min(
                    candidates,
                    key=lambda t: (-t.risk_rank, -t.routing_priority, t.sequence, t.ticket_id),
                )
                self._deadline_burst = 0

            for ticket in candidates:
                if ticket.ticket_id != selected.ticket_id:
                    ticket.bypass_count += 1
            del self._tickets[selected.ticket_id]
            return selected

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_bypass": self.max_bypass,
                "max_deadline_burst": self.max_deadline_burst,
                "current_deadline_burst": self._deadline_burst,
                "authority_weight_for_all_tickets": 0,
                "pending": [
                    {
                        "ticket_id": t.ticket_id,
                        "effect_key": t.effect_key,
                        "face_id": t.face_id,
                        "routing_priority": t.routing_priority,
                        "deadline_tick": t.deadline_tick,
                        "risk_rank": t.risk_rank,
                        "sequence": t.sequence,
                        "bypass_count": t.bypass_count,
                        "authority_weight": t.authority_weight,
                    }
                    for t in sorted(self._tickets.values(), key=lambda x: x.sequence)
                ],
            }


__all__ = [
    "DURABLE_CONTROL_VERSION",
    "DURABLE_CONTROL_SCHEMA",
    "JournalIntegrityError",
    "FenceBusyError",
    "StaleFenceTokenError",
    "ProviderBindingError",
    "JournalEntry",
    "DurableHashJournal",
    "ControlJournalProjection",
    "FencingToken",
    "SQLiteEffectFenceStore",
    "ProviderIdempotencyContract",
    "ProviderEffectBinding",
    "ProviderIdempotencyBinder",
    "DurableDispatchIntent",
    "JournaledFencedDispatchCoordinator",
    "DeadlineFairTicket",
    "DeadlineBoundedFairQueue",
]
