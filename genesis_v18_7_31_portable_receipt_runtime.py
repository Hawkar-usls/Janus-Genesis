# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.31 — portable stable-request runtime with full receipts.

This descendant removes the default-client dependency on the historical
POSIX-only v18.7.25/v18.7.26 lock chain. It wraps the same canonical
``PlayableGenesisV187.process_action`` boundary with:

- caller-supplied stable request identity;
- durable SQLite request state before canonical entry;
- one process-global + OS world-execution lock per data directory;
- conservative CALL_ENTERING -> UNDETERMINED crash semantics;
- a full canonical runtime result envelope plus SHA-256 receipt;
- settled replay from the stored receipt without a second world call.

The design deliberately prefers false uncertainty to duplicate world execution.
A crash after CALL_ENTERING and before a durable receipt is not automatically
retried, even if the crash actually occurred before the world call.

Claim boundaries:
- SQLite FULL synchronous mode and the local lock are same-host persistence /
  coordination mechanisms, not multi-host consensus or formal exactly-once
  proof across arbitrary storage failures;
- callers must preserve the same logical request_id for a retry. Identical
  action text with a new request_id is a new intent;
- this layer protects ``process_action``. Other mutating entry points need their
  own explicit request boundary rather than being assumed covered.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_models import Realm, WorldResult
from janus_portable_lock_v2 import PortableProcessLockV2

PORTABLE_RECEIPT_RUNTIME_VERSION = "18.7.31"
PORTABLE_RECEIPT_RUNTIME_SCHEMA = "janus.genesis.portable_receipt_runtime.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _action_sha256(action: str) -> str:
    return hashlib.sha256(str(action).encode("utf-8")).hexdigest()


class PortableRuntimeControlError(RuntimeError):
    code = "PORTABLE_RUNTIME_CONTROL_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class PortableRequestConflict(PortableRuntimeControlError):
    code = "PORTABLE_REQUEST_ID_BINDING_CONFLICT"


class PortableRuntimeOutcomeUndetermined(PortableRuntimeControlError):
    code = "PORTABLE_RUNTIME_OUTCOME_UNDETERMINED"


class PortableRuntimeReceiptIntegrityError(PortableRuntimeControlError):
    code = "PORTABLE_RUNTIME_RECEIPT_INTEGRITY_ERROR"


class PortableCrashPoint(str, Enum):
    AFTER_BOUND = "AFTER_BOUND"
    AFTER_CALL_ENTERING_BEFORE_WORLD = "AFTER_CALL_ENTERING_BEFORE_WORLD"
    AFTER_WORLD_BEFORE_RECEIPT = "AFTER_WORLD_BEFORE_RECEIPT"
    AFTER_RECEIPT = "AFTER_RECEIPT"


class PortableCrashInjector:
    """Deterministic one-shot crash injection for boundary verification."""

    def __init__(self, *points: PortableCrashPoint | str) -> None:
        self._remaining = {
            PortableCrashPoint(p.value if isinstance(p, PortableCrashPoint) else str(p))
            for p in points
        }

    def hit(self, point: PortableCrashPoint) -> None:
        if point in self._remaining:
            self._remaining.remove(point)
            raise PortableRuntimeControlError(f"INJECTED_CRASH:{point.value}")


@dataclass(frozen=True)
class PortableRuntimeRequestRecord:
    client_id: str
    request_id: str
    effect_key: str
    actor_id: str
    action_sha256: str
    state: str
    result_json: str | None
    result_sha256: str | None
    exception_sha256: str | None


class PortableRuntimeRequestStore:
    """SQLite state machine for stable caller request identity and receipts."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_requests (
                    client_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    effect_key TEXT NOT NULL UNIQUE,
                    actor_id TEXT NOT NULL,
                    action_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result_json TEXT,
                    result_sha256 TEXT,
                    exception_sha256 TEXT,
                    PRIMARY KEY(client_id, request_id)
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

    @staticmethod
    def effect_key(client_id: str, request_id: str) -> str:
        return "GENESIS-PORTABLE:" + _sha256(
            {"client_id": str(client_id), "request_id": str(request_id)}
        )[:40]

    @staticmethod
    def _record(client: str, request: str, row) -> PortableRuntimeRequestRecord:
        return PortableRuntimeRequestRecord(
            client_id=client,
            request_id=request,
            effect_key=row[0],
            actor_id=row[1],
            action_sha256=row[2],
            state=row[3],
            result_json=row[4],
            result_sha256=row[5],
            exception_sha256=row[6],
        )

    def bind(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        action: str,
    ) -> PortableRuntimeRequestRecord:
        client = str(client_id).strip()
        request = str(request_id).strip()
        actor = str(actor_id).strip()
        action_text = str(action).strip()
        if not client or not request or not actor or not action_text:
            raise ValueError("CLIENT_REQUEST_ACTOR_ACTION_REQUIRED")
        if len(client) > 160 or len(request) > 240 or len(actor) > 240 or len(action_text) > 4000:
            raise ValueError("PORTABLE_REQUEST_FIELD_TOO_LONG")
        effect_key = self.effect_key(client, request)
        action_hash = _action_sha256(action_text)

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT effect_key, actor_id, action_sha256, state,
                       result_json, result_sha256, exception_sha256
                FROM runtime_requests WHERE client_id=? AND request_id=?
                """,
                (client, request),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO runtime_requests(
                        client_id, request_id, effect_key, actor_id, action_sha256,
                        state, result_json, result_sha256, exception_sha256
                    ) VALUES(?,?,?,?,?,'BOUND',NULL,NULL,NULL)
                    """,
                    (client, request, effect_key, actor, action_hash),
                )
                row = (effect_key, actor, action_hash, "BOUND", None, None, None)
            else:
                if row[0] != effect_key or row[1] != actor or row[2] != action_hash:
                    raise PortableRequestConflict(
                        f"client_id={client};request_id={request};existing_actor={row[1]};"
                        f"existing_action_sha256={row[2]};new_actor={actor};"
                        f"new_action_sha256={action_hash}"
                    )
            conn.execute("COMMIT")
            return self._record(client, request, row)
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()

    def get(self, *, client_id: str, request_id: str) -> PortableRuntimeRequestRecord | None:
        client = str(client_id).strip()
        request = str(request_id).strip()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT effect_key, actor_id, action_sha256, state,
                       result_json, result_sha256, exception_sha256
                FROM runtime_requests WHERE client_id=? AND request_id=?
                """,
                (client, request),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else self._record(client, request, row)

    def transition_call_entering(self, record: PortableRuntimeRequestRecord) -> PortableRuntimeRequestRecord:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE runtime_requests SET state='CALL_ENTERING'
                WHERE client_id=? AND request_id=? AND effect_key=? AND actor_id=?
                  AND action_sha256=? AND state='BOUND'
                """,
                (
                    record.client_id,
                    record.request_id,
                    record.effect_key,
                    record.actor_id,
                    record.action_sha256,
                ),
            )
            if cur.rowcount != 1:
                raise PortableRuntimeControlError("CALL_ENTERING_COMPARE_AND_SET_FAILED")
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
        current = self.get(client_id=record.client_id, request_id=record.request_id)
        assert current is not None
        return current

    def mark_undetermined_exception(
        self,
        record: PortableRuntimeRequestRecord,
        exc: BaseException,
    ) -> None:
        exception_hash = hashlib.sha256(
            f"{type(exc).__name__}:{exc}".encode("utf-8")
        ).hexdigest()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE runtime_requests
                SET state='UNDETERMINED_EXCEPTION', exception_sha256=?
                WHERE client_id=? AND request_id=? AND effect_key=?
                  AND state='CALL_ENTERING'
                """,
                (exception_hash, record.client_id, record.request_id, record.effect_key),
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

    def settle(
        self,
        record: PortableRuntimeRequestRecord,
        *,
        result_internal: Mapping[str, Any],
    ) -> PortableRuntimeRequestRecord:
        result_json = _canonical_json(dict(result_internal))
        result_hash = hashlib.sha256(result_json.encode("utf-8")).hexdigest()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT state, result_json, result_sha256 FROM runtime_requests
                WHERE client_id=? AND request_id=? AND effect_key=?
                """,
                (record.client_id, record.request_id, record.effect_key),
            ).fetchone()
            if row is None:
                raise PortableRuntimeControlError("REQUEST_MISSING_AT_SETTLEMENT")
            state, existing_json, existing_hash = row
            if state == "SETTLED":
                if existing_json != result_json or existing_hash != result_hash:
                    raise PortableRuntimeReceiptIntegrityError("SETTLED_RECEIPT_IMMUTABILITY_VIOLATION")
            elif state == "CALL_ENTERING":
                cur = conn.execute(
                    """
                    UPDATE runtime_requests
                    SET state='SETTLED', result_json=?, result_sha256=?, exception_sha256=NULL
                    WHERE client_id=? AND request_id=? AND effect_key=? AND state='CALL_ENTERING'
                    """,
                    (
                        result_json,
                        result_hash,
                        record.client_id,
                        record.request_id,
                        record.effect_key,
                    ),
                )
                if cur.rowcount != 1:
                    raise PortableRuntimeControlError("SETTLEMENT_COMPARE_AND_SET_FAILED")
            else:
                raise PortableRuntimeOutcomeUndetermined(f"cannot settle from state={state}")
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
        finally:
            conn.close()
        current = self.get(client_id=record.client_id, request_id=record.request_id)
        assert current is not None
        return current

    def list_records(self, *, client_id: str | None = None) -> tuple[PortableRuntimeRequestRecord, ...]:
        conn = self._connect()
        try:
            if client_id is None:
                rows = conn.execute(
                    """
                    SELECT client_id, request_id, effect_key, actor_id, action_sha256,
                           state, result_json, result_sha256, exception_sha256
                    FROM runtime_requests ORDER BY rowid
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT client_id, request_id, effect_key, actor_id, action_sha256,
                           state, result_json, result_sha256, exception_sha256
                    FROM runtime_requests WHERE client_id=? ORDER BY rowid
                    """,
                    (str(client_id).strip(),),
                ).fetchall()
        finally:
            conn.close()
        return tuple(
            PortableRuntimeRequestRecord(
                client_id=row[0], request_id=row[1], effect_key=row[2], actor_id=row[3],
                action_sha256=row[4], state=row[5], result_json=row[6],
                result_sha256=row[7], exception_sha256=row[8]
            )
            for row in rows
        )


class PortableReceiptRuntimeAdapter:
    """Stable-request wrapper around one canonical Genesis world object."""

    def __init__(
        self,
        world: Any,
        data_dir: str | Path,
        *,
        store: PortableRuntimeRequestStore | None = None,
        crash_injector: PortableCrashInjector | None = None,
    ) -> None:
        self.world = world
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = store or PortableRuntimeRequestStore(
            self.data_dir / "portable_runtime_requests_v18_7_31.sqlite3"
        )
        self.world_lock = PortableProcessLockV2(
            self.data_dir / "canonical_world_execution_v18_7_31.lock"
        )
        self.crash_injector = crash_injector or PortableCrashInjector()

    @staticmethod
    def _world_result_from_internal(data: Mapping[str, Any]) -> WorldResult:
        return WorldResult(
            status=str(data["status"]),
            narrative=str(data["narrative"]),
            realm=Realm(str(data["realm"])),
            visible_grace=None,
            choices=list(data.get("choices") or []),
            branch_id=data.get("branch_id"),
            trace_id=data.get("trace_id"),
            wish_manifested=bool(data.get("wish_manifested", False)),
        )

    @staticmethod
    def _replay(record: PortableRuntimeRequestRecord) -> WorldResult:
        if record.state != "SETTLED" or record.result_json is None or record.result_sha256 is None:
            raise PortableRuntimeOutcomeUndetermined(f"request state={record.state}")
        actual = hashlib.sha256(record.result_json.encode("utf-8")).hexdigest()
        if actual != record.result_sha256:
            raise PortableRuntimeReceiptIntegrityError("STORED_RESULT_HASH_MISMATCH")
        try:
            data = json.loads(record.result_json)
        except json.JSONDecodeError as exc:
            raise PortableRuntimeReceiptIntegrityError("STORED_RESULT_JSON_INVALID") from exc
        if not isinstance(data, dict):
            raise PortableRuntimeReceiptIntegrityError("STORED_RESULT_NOT_OBJECT")
        return PortableReceiptRuntimeAdapter._world_result_from_internal(data)

    @staticmethod
    def _assert_retryable_state(record: PortableRuntimeRequestRecord) -> None:
        if record.state in {"CALL_ENTERING", "UNDETERMINED_EXCEPTION"}:
            raise PortableRuntimeOutcomeUndetermined(
                f"effect_key={record.effect_key};state={record.state};automatic_reexecution_blocked"
            )
        if record.state not in {"BOUND", "SETTLED"}:
            raise PortableRuntimeControlError(f"UNKNOWN_REQUEST_STATE:{record.state}")

    def execute(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        action: str,
    ) -> WorldResult:
        action_text = str(action).strip()
        record = self.store.bind(
            client_id=client_id,
            request_id=request_id,
            actor_id=actor_id,
            action=action_text,
        )
        # A concurrently executing peer may already have moved the row to
        # CALL_ENTERING while still holding the shared world lock. Do not label
        # that live in-flight request as crash residue before we have waited on
        # the same lock and re-read the row. A persisted CALL_ENTERING with no
        # live holder is still rejected by _assert_retryable_state() below.
        if record.state == "SETTLED":
            return self._replay(record)
        if record.state == "UNDETERMINED_EXCEPTION":
            self._assert_retryable_state(record)
        if record.state not in {"BOUND", "CALL_ENTERING"}:
            raise PortableRuntimeControlError(f"UNKNOWN_REQUEST_STATE:{record.state}")
        self.crash_injector.hit(PortableCrashPoint.AFTER_BOUND)

        # All canonical process_action entries sharing this data directory pass
        # through one local lock. The request row is re-read after lock entry so
        # a waiter observes any receipt or uncertainty produced by its predecessor.
        with self.world_lock.exclusive():
            current = self.store.get(client_id=record.client_id, request_id=record.request_id)
            if current is None:
                raise PortableRuntimeControlError("REQUEST_DISAPPEARED")
            self._assert_retryable_state(current)
            if current.state == "SETTLED":
                return self._replay(current)

            entering = self.store.transition_call_entering(current)
            self.crash_injector.hit(PortableCrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD)
            try:
                result = self.world.process_action(entering.actor_id, action_text)
            except BaseException as exc:
                self.store.mark_undetermined_exception(entering, exc)
                raise

            self.crash_injector.hit(PortableCrashPoint.AFTER_WORLD_BEFORE_RECEIPT)
            internal = result.to_dict(internal=True)
            settled = self.store.settle(entering, result_internal=internal)
            self.crash_injector.hit(PortableCrashPoint.AFTER_RECEIPT)
            # Validate the just-written receipt through the same replay path.
            replayed = self._replay(settled)
            if replayed.to_dict(internal=True) != internal:
                raise PortableRuntimeReceiptIntegrityError("POST_SETTLEMENT_REPLAY_DRIFT")
            return result

    def request_state(self, *, client_id: str, request_id: str) -> dict[str, Any] | None:
        record = self.store.get(client_id=client_id, request_id=request_id)
        if record is None:
            return None
        return {
            "client_id": record.client_id,
            "request_id": record.request_id,
            "effect_key": record.effect_key,
            "actor_id": record.actor_id,
            "action_sha256": record.action_sha256,
            "state": record.state,
            "result_sha256": record.result_sha256,
            "exception_sha256": record.exception_sha256,
            "full_result_receipt_persisted": record.result_json is not None,
            "automatic_reexecution_allowed": record.state == "BOUND",
        }


__all__ = [
    "PORTABLE_RECEIPT_RUNTIME_VERSION",
    "PORTABLE_RECEIPT_RUNTIME_SCHEMA",
    "PortableRuntimeControlError",
    "PortableRequestConflict",
    "PortableRuntimeOutcomeUndetermined",
    "PortableRuntimeReceiptIntegrityError",
    "PortableCrashPoint",
    "PortableCrashInjector",
    "PortableRuntimeRequestRecord",
    "PortableRuntimeRequestStore",
    "PortableReceiptRuntimeAdapter",
]
