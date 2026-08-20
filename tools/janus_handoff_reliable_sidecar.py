# -*- coding: utf-8 -*-
"""Durable fail-closed handoff reliability sidecar for JANUS #164.

This module owns receipt/dedupe/persistence semantics only. It deliberately has
no network sender, model loader, executor, source write-back, or external-effect
authority. A live receiver must bind to this implementation (or prove equivalent
semantics) before #164 can use its evidence for admission.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "janus.handoff.reliable_sidecar.v1"


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_receipt_id(event_id: str, dedupe_key: str, digest: str) -> str:
    material = event_id + "\0" + dedupe_key + "\0" + digest
    return "hr-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def fsync_append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one canonical operation durably with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (canonical(row) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)


@dataclass(frozen=True)
class IngestResult:
    receipt_id: str
    disposition: str
    digest: str
    bytes: int
    persisted_via: str


class ReliableHandoffSidecar:
    """Receipt-first persistence and recovery surface with zero send authority."""

    def __init__(self, root: Path | str, *, sqlite_timeout: float = 0.05) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass
        self.db_path = self.root / "handoff.sqlite3"
        self.fallback_path = self.root / "handoff-fallback.jsonl"
        self.conflict_path = self.root / "handoff-conflicts.jsonl"
        self.sqlite_timeout = float(sqlite_timeout)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path, timeout=self.sqlite_timeout)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute(
            f"PRAGMA busy_timeout={max(1, int(self.sqlite_timeout * 1000))}"
        )
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS receipts(
                  receipt_id TEXT PRIMARY KEY,
                  event_id TEXT NOT NULL UNIQUE,
                  dedupe_key TEXT NOT NULL UNIQUE,
                  arrival_sha256 TEXT NOT NULL,
                  arrival_bytes INTEGER NOT NULL,
                  parse_status TEXT NOT NULL,
                  admission_status TEXT NOT NULL,
                  load_status TEXT NOT NULL,
                  execute_status TEXT NOT NULL,
                  terminal_state TEXT NOT NULL,
                  created_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fallback_ops(
                  op_id TEXT PRIMARY KEY,
                  applied_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS downstream_consumption(
                  receipt_id TEXT PRIMARY KEY,
                  consumed_ns INTEGER NOT NULL,
                  FOREIGN KEY(receipt_id) REFERENCES receipts(receipt_id)
                );
                CREATE TABLE IF NOT EXISTS hrain_queue(
                  queue_id TEXT PRIMARY KEY,
                  receipt_id TEXT NOT NULL UNIQUE,
                  payload_json TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0,
                  next_attempt_ns INTEGER NOT NULL DEFAULT 0,
                  state TEXT NOT NULL DEFAULT 'QUEUED',
                  last_error_class TEXT,
                  FOREIGN KEY(receipt_id) REFERENCES receipts(receipt_id)
                );
                """
            )
        try:
            self.db_path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _receipt_row(
        *,
        receipt_id: str,
        event_id: str,
        dedupe_key: str,
        digest: str,
        size: int,
        parse_status: str,
        admission_status: str,
        terminal_state: str,
        created_ns: int,
    ) -> dict[str, Any]:
        return {
            "receipt_id": receipt_id,
            "event_id": event_id,
            "dedupe_key": dedupe_key,
            "arrival_sha256": digest,
            "arrival_bytes": size,
            "parse_status": parse_status,
            "admission_status": admission_status,
            "load_status": "NOT_ATTEMPTED",
            "execute_status": "NOT_ATTEMPTED",
            "terminal_state": terminal_state,
            "created_ns": created_ns,
        }

    def _conflict(
        self,
        existing: list[sqlite3.Row],
        row: dict[str, Any],
        reason: str,
    ) -> IngestResult:
        evidence = {
            "schema": SCHEMA_VERSION + ".conflict",
            "reason": reason,
            "event_id": row["event_id"],
            "dedupe_key": row["dedupe_key"],
            "conflicting_sha256": row["arrival_sha256"],
            "conflicting_bytes": row["arrival_bytes"],
            "existing": [
                {
                    "receipt_id": item["receipt_id"],
                    "event_id": item["event_id"],
                    "dedupe_key": item["dedupe_key"],
                    "sha256": item["arrival_sha256"],
                }
                for item in existing
            ],
            "state": "HOLD_RECONCILE",
        }
        fsync_append_jsonl(self.conflict_path, evidence)
        receipt_id = existing[0]["receipt_id"] if existing else row["receipt_id"]
        return IngestResult(
            receipt_id,
            "HOLD_RECONCILE",
            row["arrival_sha256"],
            row["arrival_bytes"],
            "CONFLICT_JSONL",
        )

    def _insert_receipt(
        self,
        con: sqlite3.Connection,
        row: dict[str, Any],
    ) -> IngestResult:
        matches = con.execute(
            """SELECT receipt_id,event_id,dedupe_key,arrival_sha256,
                      arrival_bytes,terminal_state
               FROM receipts
               WHERE event_id=? OR dedupe_key=?
               ORDER BY receipt_id""",
            (row["event_id"], row["dedupe_key"]),
        ).fetchall()
        distinct = {item["receipt_id"] for item in matches}
        if len(distinct) > 1:
            return self._conflict(matches, row, "IDENTITY_SPLIT")
        if matches:
            existing = matches[0]
            same_identity = (
                existing["event_id"] == row["event_id"]
                and existing["dedupe_key"] == row["dedupe_key"]
            )
            same_digest = existing["arrival_sha256"] == row["arrival_sha256"]
            if same_identity and same_digest:
                return IngestResult(
                    existing["receipt_id"],
                    "IDEMPOTENT_EXISTING",
                    existing["arrival_sha256"],
                    int(existing["arrival_bytes"]),
                    "SQLITE",
                )
            return self._conflict(matches, row, "IDENTITY_OR_DIGEST_REBIND")

        con.execute(
            """INSERT INTO receipts(
                 receipt_id,event_id,dedupe_key,arrival_sha256,arrival_bytes,
                 parse_status,admission_status,load_status,execute_status,
                 terminal_state,created_ns
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            tuple(
                row[key]
                for key in (
                    "receipt_id",
                    "event_id",
                    "dedupe_key",
                    "arrival_sha256",
                    "arrival_bytes",
                    "parse_status",
                    "admission_status",
                    "load_status",
                    "execute_status",
                    "terminal_state",
                    "created_ns",
                )
            ),
        )
        return IngestResult(
            row["receipt_id"],
            row["terminal_state"],
            row["arrival_sha256"],
            row["arrival_bytes"],
            "SQLITE",
        )

    def ingest_bytes(
        self,
        data: bytes,
        *,
        event_id: str,
        dedupe_key: str,
        complete: bool = True,
        require_json_object: bool = False,
        enqueue_hrain: bool = True,
        inject_sqlite_busy: bool = False,
    ) -> IngestResult:
        event_id = str(event_id).strip()
        dedupe_key = str(dedupe_key).strip()
        if not event_id or not dedupe_key:
            raise ValueError("event_id and dedupe_key are required")

        digest = sha256_bytes(data)
        size = len(data)
        parse_status = "NOT_REQUESTED"
        admission_status = "PASS"
        terminal_state = "RECEIPT_COMMITTED"

        if not complete:
            parse_status = "NOT_ATTEMPTED_PARTIAL"
            admission_status = "HOLD"
            terminal_state = "HOLD_PARTIAL"
        elif require_json_object:
            try:
                value = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parse_status = "FAIL"
                admission_status = "HOLD"
                terminal_state = "HOLD_PARSE"
            else:
                if not isinstance(value, dict):
                    parse_status = "FAIL_NOT_OBJECT"
                    admission_status = "HOLD"
                    terminal_state = "HOLD_PARSE"
                else:
                    parse_status = "PASS"

        receipt_id = make_receipt_id(event_id, dedupe_key, digest)
        row = self._receipt_row(
            receipt_id=receipt_id,
            event_id=event_id,
            dedupe_key=dedupe_key,
            digest=digest,
            size=size,
            parse_status=parse_status,
            admission_status=admission_status,
            terminal_state=terminal_state,
            created_ns=time.time_ns(),
        )
        fallback_op = {
            "schema": SCHEMA_VERSION + ".fallback_op",
            "op_id": "op-" + uuid.uuid4().hex,
            "kind": "INGEST",
            "row": row,
            "enqueue_hrain": bool(
                enqueue_hrain and terminal_state == "RECEIPT_COMMITTED"
            ),
        }

        if inject_sqlite_busy:
            fsync_append_jsonl(self.fallback_path, fallback_op)
            return IngestResult(
                receipt_id,
                "QUEUED_DURABLE_FALLBACK",
                digest,
                size,
                "JSONL",
            )

        try:
            with self._connect() as con:
                result = self._insert_receipt(con, row)
                if result.disposition == "RECEIPT_COMMITTED" and enqueue_hrain:
                    self._enqueue_hrain_tx(
                        con,
                        receipt_id,
                        {
                            "receipt_id": receipt_id,
                            "event_id": event_id,
                            "arrival_sha256": digest,
                        },
                    )
                return result
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            fallback_op["error_class"] = exc.__class__.__name__
            fsync_append_jsonl(self.fallback_path, fallback_op)
            return IngestResult(
                receipt_id,
                "QUEUED_DURABLE_FALLBACK",
                digest,
                size,
                "JSONL",
            )

    def ingest_file(
        self,
        path: Path | str,
        *,
        event_id: str,
        dedupe_key: str,
        stable_interval: float = 0.02,
        require_json_object: bool = False,
        enqueue_hrain: bool = True,
    ) -> IngestResult:
        """Hash only after a bounded size/mtime stability observation."""
        path = Path(path)
        first = path.stat()
        if stable_interval > 0:
            time.sleep(stable_interval)
        second = path.stat()
        complete = (first.st_size, first.st_mtime_ns) == (
            second.st_size,
            second.st_mtime_ns,
        )
        data = path.read_bytes()
        return self.ingest_bytes(
            data,
            event_id=event_id,
            dedupe_key=dedupe_key,
            complete=complete,
            require_json_object=require_json_object,
            enqueue_hrain=enqueue_hrain,
        )

    def _enqueue_hrain_tx(
        self,
        con: sqlite3.Connection,
        receipt_id: str,
        payload: dict[str, Any],
    ) -> None:
        queue_id = "hq-" + hashlib.sha256(receipt_id.encode("utf-8")).hexdigest()[:32]
        con.execute(
            """INSERT OR IGNORE INTO hrain_queue(
                 queue_id,receipt_id,payload_json,attempts,next_attempt_ns,state
               ) VALUES(?,?,?,?,?,?)""",
            (queue_id, receipt_id, canonical(payload), 0, 0, "QUEUED"),
        )

    def replay_fallback(self) -> dict[str, int]:
        """Idempotently reconcile append-only fallback operations into SQLite."""
        if not self.fallback_path.exists():
            return {
                "seen": 0,
                "applied": 0,
                "already_applied": 0,
                "conflicts": 0,
            }

        seen = applied = already = conflicts = 0
        for line in self.fallback_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            seen += 1
            op = json.loads(line)
            op_id = op["op_id"]
            with self._connect() as con:
                if con.execute(
                    "SELECT 1 FROM fallback_ops WHERE op_id=?",
                    (op_id,),
                ).fetchone():
                    already += 1
                    continue

                result = self._insert_receipt(con, op["row"])
                if result.disposition == "HOLD_RECONCILE":
                    conflicts += 1
                if (
                    result.disposition
                    in {"RECEIPT_COMMITTED", "IDEMPOTENT_EXISTING"}
                    and op.get("enqueue_hrain")
                ):
                    self._enqueue_hrain_tx(
                        con,
                        result.receipt_id,
                        {
                            "receipt_id": result.receipt_id,
                            "event_id": op["row"]["event_id"],
                            "arrival_sha256": op["row"]["arrival_sha256"],
                        },
                    )
                con.execute(
                    "INSERT INTO fallback_ops(op_id,applied_ns) VALUES(?,?)",
                    (op_id, time.time_ns()),
                )
                applied += 1

        return {
            "seen": seen,
            "applied": applied,
            "already_applied": already,
            "conflicts": conflicts,
        }

    def consume_once(self, receipt_id: str) -> str:
        """Commit a downstream consumption identity at most once."""
        with self._connect() as con:
            row = con.execute(
                "SELECT terminal_state FROM receipts WHERE receipt_id=?",
                (receipt_id,),
            ).fetchone()
            if not row:
                return "HOLD_UNKNOWN_RECEIPT"
            if row["terminal_state"] != "RECEIPT_COMMITTED":
                return "HOLD_NOT_ADMITTED"
            cur = con.execute(
                """INSERT OR IGNORE INTO downstream_consumption(
                     receipt_id,consumed_ns
                   ) VALUES(?,?)""",
                (receipt_id, time.time_ns()),
            )
            return (
                "CONSUMED_EXACTLY_ONCE"
                if cur.rowcount == 1
                else "DUPLICATE_CONSUME_REJECTED"
            )

    def due_hrain(self, *, now_ns: int | None = None) -> list[dict[str, Any]]:
        """Return durable due messages without performing any network effect."""
        now_ns = time.time_ns() if now_ns is None else int(now_ns)
        with self._connect() as con:
            rows = con.execute(
                """SELECT queue_id,receipt_id,payload_json,attempts,
                          next_attempt_ns,state,last_error_class
                   FROM hrain_queue
                   WHERE state='QUEUED' AND next_attempt_ns<=?
                   ORDER BY queue_id""",
                (now_ns,),
            ).fetchall()
        return [
            {
                "queue_id": row["queue_id"],
                "receipt_id": row["receipt_id"],
                "payload": json.loads(row["payload_json"]),
                "attempts": int(row["attempts"]),
                "next_attempt_ns": int(row["next_attempt_ns"]),
                "state": row["state"],
                "last_error_class": row["last_error_class"],
            }
            for row in rows
        ]

    def record_hrain_attempt(
        self,
        queue_id: str,
        *,
        success: bool,
        error_class: str | None = None,
        now_ns: int | None = None,
        base_delay_ns: int = 1_000_000_000,
        max_delay_ns: int = 60_000_000_000,
    ) -> dict[str, Any]:
        """Record sender outcome with bounded deterministic-jitter backoff."""
        now_ns = time.time_ns() if now_ns is None else int(now_ns)
        with self._connect() as con:
            row = con.execute(
                "SELECT attempts,state FROM hrain_queue WHERE queue_id=?",
                (queue_id,),
            ).fetchone()
            if not row:
                return {"status": "HOLD_UNKNOWN_QUEUE"}
            if row["state"] == "DELIVERED":
                return {"status": "ALREADY_DELIVERED"}

            attempts = int(row["attempts"]) + 1
            if success:
                con.execute(
                    """UPDATE hrain_queue
                       SET attempts=?,state='DELIVERED',last_error_class=NULL
                       WHERE queue_id=?""",
                    (attempts, queue_id),
                )
                return {"status": "DELIVERED", "attempts": attempts}

            exponential = min(
                max_delay_ns,
                base_delay_ns * (2 ** min(attempts - 1, 20)),
            )
            jitter = (
                int(
                    hashlib.sha256(
                        f"{queue_id}:{attempts}".encode("utf-8")
                    ).hexdigest()[:8],
                    16,
                )
                % max(1, exponential // 4)
            )
            delay = min(max_delay_ns, exponential + jitter)
            next_attempt_ns = now_ns + delay
            con.execute(
                """UPDATE hrain_queue
                   SET attempts=?,next_attempt_ns=?,state='QUEUED',last_error_class=?
                   WHERE queue_id=?""",
                (
                    attempts,
                    next_attempt_ns,
                    str(error_class or "UNAVAILABLE"),
                    queue_id,
                ),
            )
            return {
                "status": "RETRY_QUEUED",
                "attempts": attempts,
                "delay_ns": delay,
                "next_attempt_ns": next_attempt_ns,
            }

    def receipt(self, receipt_id: str) -> dict[str, Any] | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM receipts WHERE receipt_id=?",
                (receipt_id,),
            ).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict[str, int]:
        with self._connect() as con:
            return {
                "receipts": int(
                    con.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
                ),
                "consumed": int(
                    con.execute(
                        "SELECT COUNT(*) FROM downstream_consumption"
                    ).fetchone()[0]
                ),
                "hrain_queued": int(
                    con.execute(
                        "SELECT COUNT(*) FROM hrain_queue WHERE state='QUEUED'"
                    ).fetchone()[0]
                ),
                "hrain_delivered": int(
                    con.execute(
                        "SELECT COUNT(*) FROM hrain_queue WHERE state='DELIVERED'"
                    ).fetchone()[0]
                ),
                "fallback_applied": int(
                    con.execute("SELECT COUNT(*) FROM fallback_ops").fetchone()[0]
                ),
            }
