from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.janus_handoff_reliable_sidecar import ReliableHandoffSidecar


class ReliableHandoffSidecarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sidecar = ReliableHandoffSidecar(self.root, sqlite_timeout=0.01)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_duplicate_conflict_rebinding_partial_and_parse_fail_closed(self) -> None:
        first = self.sidecar.ingest_bytes(
            b'{"x":1}',
            event_id="event-1",
            dedupe_key="dedupe-1",
            require_json_object=True,
        )
        self.assertEqual(first.disposition, "RECEIPT_COMMITTED")

        duplicate = self.sidecar.ingest_bytes(
            b'{"x":1}',
            event_id="event-1",
            dedupe_key="dedupe-1",
            require_json_object=True,
        )
        self.assertEqual(duplicate.disposition, "IDEMPOTENT_EXISTING")
        self.assertEqual(duplicate.receipt_id, first.receipt_id)

        conflicting = self.sidecar.ingest_bytes(
            b'{"x":2}',
            event_id="event-1",
            dedupe_key="dedupe-1",
            require_json_object=True,
        )
        self.assertEqual(conflicting.disposition, "HOLD_RECONCILE")

        rebound = self.sidecar.ingest_bytes(
            b'{"x":1}',
            event_id="event-1",
            dedupe_key="dedupe-new",
            require_json_object=True,
        )
        self.assertEqual(rebound.disposition, "HOLD_RECONCILE")

        partial = self.sidecar.ingest_bytes(
            b"partial",
            event_id="event-2",
            dedupe_key="dedupe-2",
            complete=False,
        )
        self.assertEqual(partial.disposition, "HOLD_PARTIAL")

        invalid_object = self.sidecar.ingest_bytes(
            b"[]",
            event_id="event-3",
            dedupe_key="dedupe-3",
            require_json_object=True,
        )
        self.assertEqual(invalid_object.disposition, "HOLD_PARSE")
        self.assertEqual(self.sidecar.stats()["receipts"], 3)
        self.assertTrue(self.sidecar.conflict_path.exists())

    def test_hrain_outage_never_discards_receiver_receipt(self) -> None:
        result = self.sidecar.ingest_bytes(
            b"{}",
            event_id="event-1",
            dedupe_key="dedupe-1",
            require_json_object=True,
        )
        self.assertEqual(result.disposition, "RECEIPT_COMMITTED")
        queue = self.sidecar.due_hrain(now_ns=0)
        self.assertEqual(len(queue), 1)

        retry = self.sidecar.record_hrain_attempt(
            queue[0]["queue_id"],
            success=False,
            error_class="UNAVAILABLE",
            now_ns=10,
            base_delay_ns=100,
            max_delay_ns=10_000,
        )
        self.assertEqual(retry["status"], "RETRY_QUEUED")
        self.assertGreater(retry["next_attempt_ns"], 10)
        self.assertEqual(self.sidecar.stats()["receipts"], 1)
        self.assertEqual(self.sidecar.stats()["hrain_queued"], 1)

    def test_injected_jsonl_fallback_survives_restart_and_replays_once(self) -> None:
        result = self.sidecar.ingest_bytes(
            b"{}",
            event_id="event-1",
            dedupe_key="dedupe-1",
            inject_sqlite_busy=True,
        )
        self.assertEqual(result.persisted_via, "JSONL")
        self.assertEqual(result.disposition, "QUEUED_DURABLE_FALLBACK")
        self.assertEqual(self.sidecar.stats()["receipts"], 0)

        restarted = ReliableHandoffSidecar(self.root)
        first_replay = restarted.replay_fallback()
        self.assertEqual(first_replay["applied"], 1)
        self.assertEqual(restarted.stats()["receipts"], 1)

        second_replay = restarted.replay_fallback()
        self.assertEqual(second_replay["already_applied"], 1)
        self.assertEqual(restarted.stats()["receipts"], 1)

    def test_real_sqlite_lock_falls_back_without_loss(self) -> None:
        lock = sqlite3.connect(self.sidecar.db_path, timeout=0.01)
        lock.execute("BEGIN IMMEDIATE")
        try:
            result = self.sidecar.ingest_bytes(
                b"{}",
                event_id="event-locked",
                dedupe_key="dedupe-locked",
            )
        finally:
            lock.rollback()
            lock.close()

        self.assertEqual(result.persisted_via, "JSONL")
        replay = self.sidecar.replay_fallback()
        self.assertEqual(replay["applied"], 1)
        self.assertEqual(self.sidecar.stats()["receipts"], 1)

    def test_restart_after_receipt_before_consume_is_exactly_once(self) -> None:
        result = self.sidecar.ingest_bytes(
            b"{}",
            event_id="event-1",
            dedupe_key="dedupe-1",
        )

        worker_b = ReliableHandoffSidecar(self.root)
        self.assertEqual(
            worker_b.consume_once(result.receipt_id),
            "CONSUMED_EXACTLY_ONCE",
        )

        stale_or_duplicate = ReliableHandoffSidecar(self.root)
        self.assertEqual(
            stale_or_duplicate.consume_once(result.receipt_id),
            "DUPLICATE_CONSUME_REJECTED",
        )
        self.assertEqual(stale_or_duplicate.stats()["consumed"], 1)

    def test_received_parsed_loaded_executed_are_distinct(self) -> None:
        result = self.sidecar.ingest_bytes(
            b'{"x":1}',
            event_id="event-1",
            dedupe_key="dedupe-1",
            require_json_object=True,
        )
        receipt = self.sidecar.receipt(result.receipt_id)
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(receipt["parse_status"], "PASS")
        self.assertEqual(receipt["admission_status"], "PASS")
        self.assertEqual(receipt["load_status"], "NOT_ATTEMPTED")
        self.assertEqual(receipt["execute_status"], "NOT_ATTEMPTED")

    def test_stable_file_is_hashed_after_bounded_stability_observation(self) -> None:
        source = self.root / "arrival.json"
        source.write_text('{"payload":"ok"}\n', encoding="utf-8")
        result = self.sidecar.ingest_file(
            source,
            event_id="event-file",
            dedupe_key="dedupe-file",
            stable_interval=0.001,
            require_json_object=True,
        )
        self.assertEqual(result.disposition, "RECEIPT_COMMITTED")
        self.assertEqual(result.bytes, source.stat().st_size)


if __name__ == "__main__":
    unittest.main()
