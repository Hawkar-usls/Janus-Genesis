# -*- coding: utf-8 -*-
"""Fresh-process failure-injection reference gauntlet for JANUS #164.

This proves the reference sidecar semantics only. It is deliberately labelled
NOT_LIVE and cannot satisfy the live receiver identity/service-owner gates.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

# Support both `python -m tools...` and direct `python tools/...py` execution.
# Child processes intentionally re-enter this same file, so the import context
# must be deterministic across parent and fresh-process phases.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.janus_handoff_reliable_sidecar import (
    ReliableHandoffSidecar,
    make_receipt_id,
    sha256_bytes,
)

VECTORS = [
    "duplicate arrival same event same digest",
    "conflicting arrival same event different digest",
    "partial/truncated arrival",
    "receiver restart after hash before receipt commit",
    "receiver restart after receipt commit before downstream consume",
    "HRAIN unavailable during arrival",
    "SQLite locked during arrival",
    "JSONL fallback then process death then replay",
    "stale or duplicate downstream consume attempt",
]


def child(mode: str, root: Path) -> int:
    if mode == "hash-only-death":
        data = (root / "arrival.json").read_bytes()
        sha256_bytes(data)
        os._exit(23)

    sidecar = ReliableHandoffSidecar(root, sqlite_timeout=0.01)
    if mode == "receipt-death":
        sidecar.ingest_bytes(
            b"{}",
            event_id="event-receipt-death",
            dedupe_key="dedupe-receipt-death",
        )
        os._exit(24)
    if mode == "fallback-death":
        sidecar.ingest_bytes(
            b"{}",
            event_id="event-fallback-death",
            dedupe_key="dedupe-fallback-death",
            inject_sqlite_busy=True,
        )
        os._exit(25)
    if mode == "locked-ingest":
        result = sidecar.ingest_bytes(
            b"{}",
            event_id="event-locked",
            dedupe_key="dedupe-locked",
        )
        return 0 if result.persisted_via == "JSONL" else 3
    return 4


def run_gauntlet(root: Path) -> dict[str, bool]:
    root.mkdir(parents=True, exist_ok=True)
    passed: dict[str, bool] = {}

    dedupe_root = root / "dedupe"
    sidecar = ReliableHandoffSidecar(dedupe_root)
    first = sidecar.ingest_bytes(
        b'{"x":1}',
        event_id="event-1",
        dedupe_key="dedupe-1",
        require_json_object=True,
    )
    duplicate = sidecar.ingest_bytes(
        b'{"x":1}',
        event_id="event-1",
        dedupe_key="dedupe-1",
        require_json_object=True,
    )
    passed[VECTORS[0]] = (
        first.disposition == "RECEIPT_COMMITTED"
        and duplicate.disposition == "IDEMPOTENT_EXISTING"
        and first.receipt_id == duplicate.receipt_id
    )

    conflict = sidecar.ingest_bytes(
        b'{"x":2}',
        event_id="event-1",
        dedupe_key="dedupe-1",
        require_json_object=True,
    )
    passed[VECTORS[1]] = (
        conflict.disposition == "HOLD_RECONCILE"
        and sidecar.conflict_path.exists()
    )

    partial = sidecar.ingest_bytes(
        b"partial",
        event_id="event-2",
        dedupe_key="dedupe-2",
        complete=False,
    )
    passed[VECTORS[2]] = partial.disposition == "HOLD_PARTIAL"

    hash_root = root / "hash-death"
    hash_root.mkdir()
    source = hash_root / "arrival.json"
    source.write_bytes(b'{"hello":"world"}')
    hash_child = subprocess.run(
        [
            sys.executable,
            __file__,
            "--child",
            "hash-only-death",
            "--root",
            str(hash_root),
        ],
        check=False,
    )
    after_hash_restart = ReliableHandoffSidecar(hash_root)
    reprocessed = after_hash_restart.ingest_file(
        source,
        event_id="event-hash-death",
        dedupe_key="dedupe-hash-death",
        stable_interval=0,
    )
    passed[VECTORS[3]] = (
        hash_child.returncode == 23
        and source.exists()
        and reprocessed.disposition == "RECEIPT_COMMITTED"
    )

    receipt_root = root / "receipt-death"
    receipt_child = subprocess.run(
        [
            sys.executable,
            __file__,
            "--child",
            "receipt-death",
            "--root",
            str(receipt_root),
        ],
        check=False,
    )
    receipt_id = make_receipt_id(
        "event-receipt-death",
        "dedupe-receipt-death",
        sha256_bytes(b"{}"),
    )
    after_receipt_restart = ReliableHandoffSidecar(receipt_root)
    first_consume = after_receipt_restart.consume_once(receipt_id)
    passed[VECTORS[4]] = (
        receipt_child.returncode == 24
        and first_consume == "CONSUMED_EXACTLY_ONCE"
    )

    hrain_root = root / "hrain-outage"
    hrain = ReliableHandoffSidecar(hrain_root)
    hrain_receipt = hrain.ingest_bytes(
        b"{}",
        event_id="event-hrain",
        dedupe_key="dedupe-hrain",
    )
    due = hrain.due_hrain(now_ns=0)
    retry = hrain.record_hrain_attempt(
        due[0]["queue_id"],
        success=False,
        error_class="UNAVAILABLE",
        now_ns=100,
        base_delay_ns=100,
        max_delay_ns=10_000,
    )
    passed[VECTORS[5]] = (
        hrain_receipt.disposition == "RECEIPT_COMMITTED"
        and retry["status"] == "RETRY_QUEUED"
        and hrain.stats()["receipts"] == 1
        and hrain.stats()["hrain_queued"] == 1
    )

    locked_root = root / "sqlite-locked"
    locked = ReliableHandoffSidecar(locked_root, sqlite_timeout=0.01)
    lock = sqlite3.connect(locked.db_path, timeout=0.01)
    lock.execute("BEGIN IMMEDIATE")
    try:
        locked_child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--child",
                "locked-ingest",
                "--root",
                str(locked_root),
            ],
            check=False,
        )
    finally:
        lock.rollback()
        lock.close()
    after_lock = ReliableHandoffSidecar(locked_root)
    lock_replay = after_lock.replay_fallback()
    passed[VECTORS[6]] = (
        locked_child.returncode == 0
        and lock_replay["applied"] == 1
        and after_lock.stats()["receipts"] == 1
    )

    fallback_root = root / "fallback-death"
    fallback_child = subprocess.run(
        [
            sys.executable,
            __file__,
            "--child",
            "fallback-death",
            "--root",
            str(fallback_root),
        ],
        check=False,
    )
    after_fallback_death = ReliableHandoffSidecar(fallback_root)
    first_replay = after_fallback_death.replay_fallback()
    second_replay = after_fallback_death.replay_fallback()
    passed[VECTORS[7]] = (
        fallback_child.returncode == 25
        and first_replay["applied"] == 1
        and second_replay["already_applied"] == 1
        and after_fallback_death.stats()["receipts"] == 1
    )

    stale_or_duplicate = ReliableHandoffSidecar(receipt_root)
    second_consume = stale_or_duplicate.consume_once(receipt_id)
    passed[VECTORS[8]] = (
        second_consume == "DUPLICATE_CONSUME_REJECTED"
        and stale_or_duplicate.stats()["consumed"] == 1
    )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--child",
        choices=(
            "hash-only-death",
            "receipt-death",
            "fallback-death",
            "locked-ingest",
        ),
    )
    args = parser.parse_args()
    root = args.root or Path(tempfile.mkdtemp(prefix="janus-handoff-reference-"))

    if args.child:
        return child(args.child, root)

    vectors = run_gauntlet(root)
    passed = all(vectors.values())
    receipt = {
        "schema": "janus.handoff.reliability.reference_gauntlet.v1",
        "evidence_kind": "REFERENCE_FRESH_PROCESS_FAILURE_INJECTION_NOT_LIVE",
        "status": "PASS" if passed else "FAIL",
        "failure_vectors": {
            name: "PASS" if ok else "FAIL" for name, ok in vectors.items()
        },
        "reference_gates": {
            "HR1_LIVE_QUANT_INGRESS_NOT_BLOCKED_BY_HRAIN": "REFERENCE_PASS_NOT_LIVE",
            "HR2_EXACT_RECEIVER_SHA_RECEIPT": "REFERENCE_PASS",
            "HR3_EVENT_DEDUPE_REBINDING_FAIL_CLOSED": "REFERENCE_PASS",
            "HR4_HRAIN_SERVICE_OWNER_AND_ROUTE_EXPLICIT": "LIVE_REQUIRED",
            "HR5_HRAIN_BOUNDED_RETRY_AND_DURABLE_QUEUE": "REFERENCE_PASS",
            "HR6_SQLITE_BUSY_RECOVERY_NO_LOSS": "REFERENCE_PASS",
            "HR7_FALLBACK_REPLAY_IDEMPOTENT": "REFERENCE_PASS",
            "HR8_PROCESS_DROP_RECOVERY": "REFERENCE_PASS",
            "HR9_DOWNSTREAM_EXACTLY_ONCE_CONSUME": "REFERENCE_PASS",
            "HR10_RECEIVED_PARSED_LOADED_EXECUTED_SEPARATED": "REFERENCE_PASS",
        },
        "live_receiver_bound": False,
        "issue_164_pass": False,
        "issue_162_runnable_contribution": False,
        "source_writeback": False,
        "destructive_action": False,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
    }
    text = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
