# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.39 — typed auxiliary mutation request boundaries.

v6.5 protected the default normal ``process_action`` path, while v6.6 found two
remaining user-facing world mutations in the CLI: ``force_exit`` and
``set_display_name``. Their causal semantics are not identical to a normal world
action, so v18.7.39 gives them typed request/receipt contracts rather than
pretending one generic action envelope describes every effect.

Cooperating process_action, forced-exit and display-name operations share the
same canonical world lock path used by the portable receipt runtime. Each typed
request is durably bound to mutation kind + actor + normalized payload before raw
world entry. A settled request replays its stored receipt without re-entering the
world. A surviving CALL_ENTERING after the predecessor releases the shared world
lock is UNDETERMINED and is not automatically executed again.

``ControlledGenesisMutationFacade`` is a canonical *cooperating API construction
path*, not a Python security sandbox. Code that deliberately constructs or keeps
a raw ``PlayableGenesisV187`` object can still bypass the facade. Therefore this
module does not claim global world-authority sealing or multi-host consensus.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

from genesis_v18_7_33_inflight_duplicate_reconciliation import (
    ReconciledPortableReceiptRuntimeAdapter,
)
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_models import Realm, WorldResult
from janus_portable_lock_v2 import PortableProcessLockV2

TYPED_MUTATION_VERSION = "18.7.39"
TYPED_MUTATION_SCHEMA = "janus.genesis.typed_mutation_authority.v1"
SHARED_WORLD_LOCK_NAME = "canonical_world_execution_v18_7_31.lock"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class TypedMutationError(RuntimeError):
    code = "TYPED_MUTATION_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class TypedMutationRequestConflict(TypedMutationError):
    code = "TYPED_MUTATION_REQUEST_CONFLICT"


class TypedMutationOutcomeUndetermined(TypedMutationError):
    code = "TYPED_MUTATION_OUTCOME_UNDETERMINED"


class TypedMutationReceiptIntegrityError(TypedMutationError):
    code = "TYPED_MUTATION_RECEIPT_INTEGRITY_ERROR"


class TypedMutationKind(str, Enum):
    FORCE_EXIT = "FORCE_EXIT"
    SET_DISPLAY_NAME = "SET_DISPLAY_NAME"


class TypedMutationCrashPoint(str, Enum):
    AFTER_CALL_ENTERING_BEFORE_WORLD = "AFTER_CALL_ENTERING_BEFORE_WORLD"
    AFTER_WORLD_BEFORE_RECEIPT = "AFTER_WORLD_BEFORE_RECEIPT"
    AFTER_RECEIPT = "AFTER_RECEIPT"


class TypedMutationCrashInjector:
    def __init__(self, *points: TypedMutationCrashPoint | str) -> None:
        self.remaining = {
            TypedMutationCrashPoint(
                point.value if isinstance(point, TypedMutationCrashPoint) else str(point)
            )
            for point in points
        }

    def hit(self, point: TypedMutationCrashPoint) -> None:
        if point in self.remaining:
            self.remaining.remove(point)
            raise TypedMutationError(f"INJECTED_TYPED_MUTATION_CRASH:{point.value}")


@dataclass(frozen=True)
class TypedMutationRecord:
    client_id: str
    request_id: str
    mutation_kind: str
    actor_id: str
    payload_sha256: str
    state: str
    result_json: str | None
    result_sha256: str | None
    exception_sha256: str | None


class TypedMutationRequestStore:
    """Durable request/receipt state for non-process_action typed mutations."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS typed_mutation_requests (
                    client_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    mutation_kind TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
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
    def _record(client: str, request: str, row) -> TypedMutationRecord:
        return TypedMutationRecord(
            client_id=client,
            request_id=request,
            mutation_kind=row[0],
            actor_id=row[1],
            payload_sha256=row[2],
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
        mutation_kind: TypedMutationKind | str,
        actor_id: str,
        payload: Mapping[str, Any],
    ) -> TypedMutationRecord:
        client = str(client_id).strip()
        request = str(request_id).strip()
        actor = str(actor_id).strip()
        kind = TypedMutationKind(
            mutation_kind.value if isinstance(mutation_kind, TypedMutationKind) else str(mutation_kind)
        ).value
        if not client or not request or not actor:
            raise ValueError("TYPED_MUTATION_CLIENT_REQUEST_ACTOR_REQUIRED")
        payload_hash = _sha256(dict(payload))
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT mutation_kind,actor_id,payload_sha256,state,
                       result_json,result_sha256,exception_sha256
                FROM typed_mutation_requests
                WHERE client_id=? AND request_id=?
                """,
                (client, request),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO typed_mutation_requests(
                        client_id,request_id,mutation_kind,actor_id,payload_sha256,
                        state,result_json,result_sha256,exception_sha256
                    ) VALUES(?,?,?,?,?,'BOUND',NULL,NULL,NULL)
                    """,
                    (client, request, kind, actor, payload_hash),
                )
                row = (kind, actor, payload_hash, "BOUND", None, None, None)
            elif row[0] != kind or row[1] != actor or row[2] != payload_hash:
                raise TypedMutationRequestConflict(
                    f"client_id={client};request_id={request};"
                    f"existing_kind={row[0]};new_kind={kind};"
                    f"existing_actor={row[1]};new_actor={actor};"
                    f"existing_payload_sha256={row[2]};new_payload_sha256={payload_hash}"
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

    def get(self, *, client_id: str, request_id: str) -> TypedMutationRecord | None:
        client = str(client_id).strip()
        request = str(request_id).strip()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT mutation_kind,actor_id,payload_sha256,state,
                       result_json,result_sha256,exception_sha256
                FROM typed_mutation_requests
                WHERE client_id=? AND request_id=?
                """,
                (client, request),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else self._record(client, request, row)

    def call_entering(self, record: TypedMutationRecord) -> TypedMutationRecord:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE typed_mutation_requests SET state='CALL_ENTERING'
                WHERE client_id=? AND request_id=? AND mutation_kind=?
                  AND actor_id=? AND payload_sha256=? AND state='BOUND'
                """,
                (
                    record.client_id,
                    record.request_id,
                    record.mutation_kind,
                    record.actor_id,
                    record.payload_sha256,
                ),
            )
            if cur.rowcount != 1:
                raise TypedMutationError("TYPED_MUTATION_CALL_ENTERING_CAS_FAILED")
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

    def mark_exception(self, record: TypedMutationRecord, exc: BaseException) -> None:
        exception_hash = hashlib.sha256(
            f"{type(exc).__name__}:{exc}".encode("utf-8")
        ).hexdigest()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE typed_mutation_requests
                SET state='UNDETERMINED_EXCEPTION', exception_sha256=?
                WHERE client_id=? AND request_id=? AND state='CALL_ENTERING'
                """,
                (exception_hash, record.client_id, record.request_id),
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
        record: TypedMutationRecord,
        *,
        result: Mapping[str, Any],
    ) -> TypedMutationRecord:
        result_json = _canonical_json(dict(result))
        result_hash = hashlib.sha256(result_json.encode("utf-8")).hexdigest()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT state,result_json,result_sha256 FROM typed_mutation_requests
                WHERE client_id=? AND request_id=?
                """,
                (record.client_id, record.request_id),
            ).fetchone()
            if row is None:
                raise TypedMutationError("TYPED_MUTATION_REQUEST_MISSING_AT_SETTLE")
            if row[0] == "SETTLED":
                if row[1] != result_json or row[2] != result_hash:
                    raise TypedMutationReceiptIntegrityError(
                        "TYPED_MUTATION_SETTLEMENT_DRIFT"
                    )
            elif row[0] == "CALL_ENTERING":
                cur = conn.execute(
                    """
                    UPDATE typed_mutation_requests
                    SET state='SETTLED',result_json=?,result_sha256=?,exception_sha256=NULL
                    WHERE client_id=? AND request_id=? AND state='CALL_ENTERING'
                    """,
                    (result_json, result_hash, record.client_id, record.request_id),
                )
                if cur.rowcount != 1:
                    raise TypedMutationError("TYPED_MUTATION_SETTLE_CAS_FAILED")
            else:
                raise TypedMutationOutcomeUndetermined(
                    f"cannot settle from state={row[0]}"
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
        current = self.get(client_id=record.client_id, request_id=record.request_id)
        assert current is not None
        return current


class TypedAuxiliaryMutationAdapter:
    """Typed force-exit/name mutations sharing the canonical process_action lock."""

    def __init__(
        self,
        world: Any,
        data_dir: str | Path,
        *,
        store: TypedMutationRequestStore | None = None,
        crash_injector: TypedMutationCrashInjector | None = None,
    ) -> None:
        self.world = world
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = store or TypedMutationRequestStore(
            self.data_dir / "typed_mutation_requests_v18_7_39.sqlite3"
        )
        self.world_lock = PortableProcessLockV2(
            self.data_dir / SHARED_WORLD_LOCK_NAME
        )
        self.crash_injector = crash_injector or TypedMutationCrashInjector()

    @staticmethod
    def _decode_result(record: TypedMutationRecord) -> dict[str, Any]:
        if record.state != "SETTLED" or record.result_json is None or record.result_sha256 is None:
            raise TypedMutationOutcomeUndetermined(f"state={record.state}")
        actual = hashlib.sha256(record.result_json.encode("utf-8")).hexdigest()
        if actual != record.result_sha256:
            raise TypedMutationReceiptIntegrityError("TYPED_MUTATION_STORED_RESULT_HASH_MISMATCH")
        value = json.loads(record.result_json)
        if not isinstance(value, dict):
            raise TypedMutationReceiptIntegrityError("TYPED_MUTATION_RESULT_NOT_OBJECT")
        return value

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

    def _execute(
        self,
        *,
        client_id: str,
        request_id: str,
        mutation_kind: TypedMutationKind,
        actor_id: str,
        payload: Mapping[str, Any],
        raw_call: Callable[[], Mapping[str, Any]],
    ) -> dict[str, Any]:
        record = self.store.bind(
            client_id=client_id,
            request_id=request_id,
            mutation_kind=mutation_kind,
            actor_id=actor_id,
            payload=payload,
        )
        if record.state == "SETTLED":
            return self._decode_result(record)
        if record.state not in {"BOUND", "CALL_ENTERING", "UNDETERMINED_EXCEPTION"}:
            raise TypedMutationError(f"UNKNOWN_TYPED_MUTATION_STATE:{record.state}")

        # Wait for the exact same local world lock used by v18.7.31/v18.7.33.
        # This lets an active duplicate finish before we classify CALL_ENTERING
        # as crash residue and also serializes cooperating auxiliary mutations
        # against controlled process_action calls.
        with self.world_lock.exclusive():
            current = self.store.get(client_id=record.client_id, request_id=record.request_id)
            if current is None:
                raise TypedMutationError("TYPED_MUTATION_REQUEST_DISAPPEARED")
            if current.state == "SETTLED":
                return self._decode_result(current)
            if current.state in {"CALL_ENTERING", "UNDETERMINED_EXCEPTION"}:
                raise TypedMutationOutcomeUndetermined(
                    f"client_id={current.client_id};request_id={current.request_id};"
                    f"state={current.state};predecessor_lock_released_without_receipt"
                )
            if current.state != "BOUND":
                raise TypedMutationError(f"UNKNOWN_TYPED_MUTATION_STATE:{current.state}")

            entering = self.store.call_entering(current)
            self.crash_injector.hit(
                TypedMutationCrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD
            )
            try:
                result = dict(raw_call())
            except BaseException as exc:
                self.store.mark_exception(entering, exc)
                raise
            self.crash_injector.hit(TypedMutationCrashPoint.AFTER_WORLD_BEFORE_RECEIPT)
            settled = self.store.settle(entering, result=result)
            self.crash_injector.hit(TypedMutationCrashPoint.AFTER_RECEIPT)
            replayed = self._decode_result(settled)
            if replayed != result:
                raise TypedMutationReceiptIntegrityError(
                    "TYPED_MUTATION_POST_SETTLEMENT_REPLAY_DRIFT"
                )
            return result

    def force_exit(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        reason: str = "system_interrupt",
    ) -> WorldResult:
        reason_text = str(reason).strip()[:240] or "system_interrupt"

        def raw() -> Mapping[str, Any]:
            return self.world.force_exit(actor_id, reason=reason_text).to_dict(internal=True)

        value = self._execute(
            client_id=client_id,
            request_id=request_id,
            mutation_kind=TypedMutationKind.FORCE_EXIT,
            actor_id=actor_id,
            payload={"reason": reason_text},
            raw_call=raw,
        )
        return self._world_result_from_internal(value)

    def set_display_name(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        display_name: str,
    ) -> dict[str, Any]:
        clean = str(display_name).strip()[:80]
        if not clean:
            raise ValueError("DISPLAY_NAME_REQUIRED")

        def raw() -> Mapping[str, Any]:
            self.world.set_display_name(actor_id, clean)
            return {
                "status": "DISPLAY_NAME_UPDATED",
                "actor_id": actor_id,
                "display_name": clean,
            }

        return self._execute(
            client_id=client_id,
            request_id=request_id,
            mutation_kind=TypedMutationKind.SET_DISPLAY_NAME,
            actor_id=actor_id,
            payload={"display_name": clean},
            raw_call=raw,
        )

    def request_state(self, *, client_id: str, request_id: str) -> dict[str, Any] | None:
        record = self.store.get(client_id=client_id, request_id=request_id)
        if record is None:
            return None
        return {
            "client_id": record.client_id,
            "request_id": record.request_id,
            "mutation_kind": record.mutation_kind,
            "actor_id": record.actor_id,
            "payload_sha256": record.payload_sha256,
            "state": record.state,
            "result_sha256": record.result_sha256,
            "exception_sha256": record.exception_sha256,
            "full_result_receipt_persisted": record.result_json is not None,
        }


class ControlledGenesisMutationFacade:
    """Canonical cooperating constructor for controlled world mutations.

    This is API discipline, not language-level capability security. The raw world
    remains an implementation object and Python callers can bypass this facade if
    they deliberately instantiate it themselves.
    """

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        self.data_dir = Path(data_dir)
        self._world = PlayableGenesisV187(self.data_dir)
        self._actions = ReconciledPortableReceiptRuntimeAdapter(
            self._world,
            self.data_dir,
        )
        self._auxiliary = TypedAuxiliaryMutationAdapter(
            self._world,
            self.data_dir,
        )

    def process_action(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        action: str,
    ) -> WorldResult:
        return self._actions.execute(
            client_id=client_id,
            request_id=request_id,
            actor_id=actor_id,
            action=action,
        )

    def force_exit(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        reason: str,
    ) -> WorldResult:
        return self._auxiliary.force_exit(
            client_id=client_id,
            request_id=request_id,
            actor_id=actor_id,
            reason=reason,
        )

    def set_display_name(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        display_name: str,
    ) -> dict[str, Any]:
        return self._auxiliary.set_display_name(
            client_id=client_id,
            request_id=request_id,
            actor_id=actor_id,
            display_name=display_name,
        )


__all__ = [
    "TYPED_MUTATION_VERSION",
    "TYPED_MUTATION_SCHEMA",
    "SHARED_WORLD_LOCK_NAME",
    "TypedMutationError",
    "TypedMutationRequestConflict",
    "TypedMutationOutcomeUndetermined",
    "TypedMutationReceiptIntegrityError",
    "TypedMutationKind",
    "TypedMutationCrashPoint",
    "TypedMutationCrashInjector",
    "TypedMutationRecord",
    "TypedMutationRequestStore",
    "TypedAuxiliaryMutationAdapter",
    "ControlledGenesisMutationFacade",
]
