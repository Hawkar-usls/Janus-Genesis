# -*- coding: utf-8 -*-
"""HDD-friendly buffered thought journal for JANUS Hippocampus.

The primitive preserves the historical ``thoughts`` table used by
``JanusHippocampus`` while batching inserts in RAM and moving synchronous
SQLite I/O off the asyncio event-loop thread.

Boundaries:
- batching reduces commit frequency; it does not prove lower wear or zero
  interference with Storj on a particular host;
- WAL + ``synchronous=NORMAL`` trades some power-loss durability for fewer
  syncs. ``FULL`` is available when stronger commit durability is required;
- no network, subprocess, source-repository writeback, deletion, VACUUM, or
  destructive checkpoint is performed here.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger("JANUS.HIPPOCAMPUS")
SCHEMA_VERSION = "janus.hippocampus.buffered_journal.v2"
_ALLOWED_SYNCHRONOUS = frozenset({"NORMAL", "FULL"})


class MemoryJournalError(RuntimeError):
    pass


class MemoryClosedError(MemoryJournalError):
    pass


class MemoryBufferFullError(MemoryJournalError):
    pass


class MemoryPersistenceError(MemoryJournalError):
    pass


@dataclass(frozen=True)
class BufferedThought:
    timestamp: str
    source: str
    content: str
    tags_json: str
    vector_blob: Optional[bytes]
    content_folded: str

    def sql_row(self) -> tuple[str, str, str, str, Optional[bytes], str]:
        return (
            self.timestamp,
            self.source,
            self.content,
            self.tags_json,
            self.vector_blob,
            self.content_folded,
        )


class JanusHippocampusBufferedJournal:
    """Fail-closed RAM-buffered journal compatible with JANUS ``thoughts``.

    A flush detaches the current batch under ``_buffer_lock`` and writes it in
    one SQLite transaction on a worker thread. If persistence fails, the exact
    detached batch is prepended back before newer records. Old memories are not
    discarded to admit new ones; a full RAM guard rejects the new write.
    """

    def __init__(
        self,
        db_path: str | Path = "janus_data/janus_cortex.db",
        *,
        batch_size: int = 500,
        flush_interval_seconds: float = 300.0,
        max_buffer_records: int = 5000,
        recent_scan_limit: int = 5000,
        synchronous: str = "NORMAL",
        busy_timeout_ms: int = 5000,
        wal_autocheckpoint_pages: int = 4096,
        max_content_bytes: int = 1_048_576,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if flush_interval_seconds <= 0:
            raise ValueError("flush_interval_seconds must be > 0")
        if max_buffer_records < batch_size:
            raise ValueError("max_buffer_records must be >= batch_size")
        if recent_scan_limit < 1:
            raise ValueError("recent_scan_limit must be >= 1")
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be >= 0")
        if wal_autocheckpoint_pages < 1:
            raise ValueError("wal_autocheckpoint_pages must be >= 1")
        if max_content_bytes < 1:
            raise ValueError("max_content_bytes must be >= 1")
        synchronous = synchronous.upper()
        if synchronous not in _ALLOWED_SYNCHRONOUS:
            raise ValueError("synchronous must be NORMAL or FULL")

        self.db_path = Path(db_path)
        self.batch_size = batch_size
        self.flush_interval_seconds = float(flush_interval_seconds)
        self.max_buffer_records = max_buffer_records
        self.recent_scan_limit = recent_scan_limit
        self.synchronous = synchronous
        self.busy_timeout_ms = busy_timeout_ms
        self.wal_autocheckpoint_pages = wal_autocheckpoint_pages
        self.max_content_bytes = max_content_bytes

        self._buffer: list[BufferedThought] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._flush_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._flush_task: Optional[asyncio.Task[None]] = None
        self._started = False
        self._accepting_writes = True
        self._closed = False
        self._last_flush_monotonic = time.monotonic()
        self._last_error: Optional[str] = None

    async def __aenter__(self) -> "JanusHippocampusBufferedJournal":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    async def start(self) -> None:
        if self._closed:
            raise MemoryClosedError("MEMORY_JOURNAL_ALREADY_CLOSED")
        if self._started:
            return
        async with self._start_lock:
            if self._started:
                return
            await asyncio.to_thread(self._init_db_sync)
            self._started = True
            self._flush_task = asyncio.create_task(
                self._flush_loop(), name="janus-hippocampus-flush"
            )

    async def _ensure_started(self) -> None:
        if not self._started:
            await self.start()

    def _connect_sync(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=max(self.busy_timeout_ms / 1000.0, 0.001),
        )
        conn.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)}")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA synchronous={self.synchronous}")
        conn.execute(f"PRAGMA wal_autocheckpoint={int(self.wal_autocheckpoint_pages)}")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _init_db_sync(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect_sync()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS thoughts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    source TEXT,
                    content TEXT,
                    tags TEXT,
                    vector BLOB,
                    content_folded TEXT
                )
                """
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(thoughts)").fetchall()
            }
            if "content_folded" not in columns:
                conn.execute("ALTER TABLE thoughts ADD COLUMN content_folded TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_thoughts_source_id "
                "ON thoughts(source, id DESC)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS janus_memory_meta ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO janus_memory_meta(key, value) VALUES (?, ?)",
                ("buffered_journal_schema", SCHEMA_VERSION),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _normalize_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        return json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @staticmethod
    def _tags_for(content: str) -> str:
        tokens = re.findall(r"\w{4,}", content.casefold(), flags=re.UNICODE)
        return json.dumps(
            list(dict.fromkeys(tokens))[:128],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _vector_blob(vector: Any) -> Optional[bytes]:
        if vector is None:
            return None
        return json.dumps(
            vector,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    async def remember(
        self,
        source: Optional[str] = None,
        content: Any = None,
        vector: Any = None,
        *,
        tag: Optional[str] = None,
    ) -> None:
        """Buffer one thought; ``tag`` is a compatibility alias for ``source``."""
        await self._ensure_started()
        if source is None:
            source = tag
        elif tag is not None and tag != source:
            raise ValueError("source and tag disagree")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source/tag must be a non-empty string")
        source = source.strip()
        if len(source) > 128:
            raise ValueError("source/tag too long")

        text = self._normalize_content(content)
        if len(text.encode("utf-8")) > self.max_content_bytes:
            raise ValueError("content exceeds max_content_bytes")
        thought = BufferedThought(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            content=text,
            tags_json=self._tags_for(text),
            vector_blob=self._vector_blob(vector),
            content_folded=text.casefold(),
        )

        should_wake = False
        async with self._buffer_lock:
            # This check MUST be inside the same lock as append. Otherwise a
            # remember() that passed an earlier check could append after close()
            # performed its final flush.
            if not self._accepting_writes or self._closed:
                raise MemoryClosedError("MEMORY_JOURNAL_NOT_ACCEPTING_WRITES")
            if len(self._buffer) >= self.max_buffer_records:
                raise MemoryBufferFullError(
                    "MEMORY_BUFFER_FULL_PERSISTENCE_REQUIRED_BEFORE_NEW_WRITE"
                )
            self._buffer.append(thought)
            should_wake = len(self._buffer) >= self.batch_size
        if should_wake:
            self._flush_event.set()

    async def _flush_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._flush_event.wait(), timeout=self.flush_interval_seconds
                )
            except asyncio.TimeoutError:
                pass
            self._flush_event.clear()
            if self._stop_event.is_set():
                break
            try:
                await self.flush()
            except MemoryPersistenceError as exc:
                LOGGER.error("[MEMORY] flush failed; batch retained in RAM: %s", exc)

    async def flush(self) -> int:
        await self._ensure_started()
        async with self._flush_lock:
            async with self._buffer_lock:
                if not self._buffer:
                    return 0
                batch = self._buffer
                self._buffer = []
            try:
                await asyncio.to_thread(self._write_batch_sync, batch)
            except Exception as exc:
                async with self._buffer_lock:
                    self._buffer = batch + self._buffer
                self._last_error = f"{type(exc).__name__}: {exc}"
                raise MemoryPersistenceError(self._last_error) from exc
            self._last_error = None
            self._last_flush_monotonic = time.monotonic()
            return len(batch)

    def _write_batch_sync(self, batch: list[BufferedThought]) -> None:
        conn = self._connect_sync()
        try:
            conn.executemany(
                "INSERT INTO thoughts "
                "(timestamp, source, content, tags, vector, content_folded) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [thought.sql_row() for thought in batch],
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def force_save(self) -> int:
        return await self.flush()

    async def close(self) -> None:
        if self._closed:
            return
        await self._ensure_started()
        self._accepting_writes = False
        self._stop_event.set()
        self._flush_event.set()
        if self._flush_task is not None:
            await self._flush_task
            self._flush_task = None
        # Deliberately not best-effort: a shutdown save failure must be visible.
        await self.flush()
        self._closed = True

    def _search_disk_sync(self, keyword_folded: str, limit: int) -> list[dict[str, Any]]:
        conn = self._connect_sync()
        try:
            rows = conn.execute(
                "SELECT id, timestamp, source, content, content_folded "
                "FROM thoughts ORDER BY id DESC LIMIT ?",
                (self.recent_scan_limit,),
            ).fetchall()
        finally:
            conn.close()
        hits: list[dict[str, Any]] = []
        for row_id, timestamp, source, content, content_folded in rows:
            folded = (
                content_folded
                if isinstance(content_folded, str)
                else str(content).casefold()
            )
            if keyword_folded in folded:
                hits.append(
                    {
                        "origin": "HDD",
                        "id": row_id,
                        "timestamp": timestamp,
                        "source": source,
                        "content": content,
                    }
                )
                if len(hits) >= limit:
                    break
        return hits

    async def recall(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search RAM then a bounded recent disk window; not full-disk FTS."""
        await self._ensure_started()
        if not isinstance(keyword, str) or not keyword:
            raise ValueError("keyword must be a non-empty string")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        folded_keyword = keyword.casefold()

        # Serialize against flush: the same thought cannot appear in both the RAM
        # snapshot and the disk query of one recall operation.
        async with self._flush_lock:
            async with self._buffer_lock:
                ram_snapshot = list(self._buffer)
            hits: list[dict[str, Any]] = []
            for thought in reversed(ram_snapshot):
                if folded_keyword in thought.content_folded:
                    hits.append(
                        {
                            "origin": "RAM",
                            "id": None,
                            "timestamp": thought.timestamp,
                            "source": thought.source,
                            "content": thought.content,
                        }
                    )
                    if len(hits) >= limit:
                        return hits
            hits.extend(
                await asyncio.to_thread(
                    self._search_disk_sync, folded_keyword, limit - len(hits)
                )
            )
            return hits

    async def stats(self) -> dict[str, Any]:
        await self._ensure_started()
        async with self._buffer_lock:
            buffered = len(self._buffer)
        return {
            "schema": SCHEMA_VERSION,
            "buffered_records": buffered,
            "batch_size": self.batch_size,
            "max_buffer_records": self.max_buffer_records,
            "flush_interval_seconds": self.flush_interval_seconds,
            "seconds_since_last_successful_flush": max(
                0.0, time.monotonic() - self._last_flush_monotonic
            ),
            "synchronous": self.synchronous,
            "wal_autocheckpoint_pages": self.wal_autocheckpoint_pages,
            "last_error": self._last_error,
            "accepting_writes": self._accepting_writes and not self._closed,
        }
