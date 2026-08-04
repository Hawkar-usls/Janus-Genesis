#!/usr/bin/env python3
"""Reproducible adversarial corpus producer for JANUS 113.8 SIM-1.

This module only creates bounded, synthetic, read-only fixtures. It does not
perform network I/O, delete files, modify itself, or actuate external systems.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "JANUS-113.8-SIM-1-v1.0"
DEFAULT_SEED = 113_800_1919
DEFAULT_CASES = 100
MAX_CASES = 500
MAX_CANDIDATES = 32
MAX_PAYLOAD_BYTES = 32_768
ALLOWED_STATUSES = {
    "retained",
    "rejected_with_reason",
    "failed_verification",
    "timed_out",
    "deferred",
    "unresolved",
}
ATTACKS = (
    "valid",
    "malformed_json",
    "false_provenance",
    "duplicate_branch",
    "missing_branch",
    "resource_exhaustion",
    "hash_chain_tamper",
    "privacy_leak",
    "schema_violation",
    "payload_limit",
)
EXPECTED_TERMINALS = {
    "valid": "VERIFIED_CORPUS_CASE",
    "malformed_json": "REJECT_MALFORMED_JSON",
    "false_provenance": "REJECT_FALSE_PROVENANCE",
    "duplicate_branch": "REJECT_DUPLICATE_BRANCH",
    "missing_branch": "REJECT_BRANCH_ACCOUNTING",
    "resource_exhaustion": "REJECT_RESOURCE_EXHAUSTION",
    "hash_chain_tamper": "REJECT_HASH_CHAIN_TAMPER",
    "privacy_leak": "REJECT_PRIVACY_LEAK",
    "schema_violation": "REJECT_SCHEMA_VIOLATION",
    "payload_limit": "REJECT_PAYLOAD_LIMIT",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_content(case_index: int, branch_index: int) -> str:
    return f"synthetic evidence case={case_index} branch={branch_index}"


def _candidate(case_index: int, branch_index: int, rng: random.Random) -> dict[str, Any]:
    source_content = _source_content(case_index, branch_index)
    verifier_score = round(rng.uniform(0.05, 0.99), 6)
    confidence = round(rng.uniform(0.05, 0.99), 6)
    status = rng.choice(sorted(ALLOWED_STATUSES))
    return {
        "candidate_id": f"C{case_index:04d}-B{branch_index:02d}",
        "claim": f"bounded synthetic hypothesis {case_index}:{branch_index}",
        "confidence": confidence,
        "verifier_score": verifier_score,
        "status": status,
        "reason": f"synthetic terminal reason for {status}",
        "compute_cost_units": rng.randint(1, 5),
        "provenance": {
            "source_id": f"SRC-{case_index:04d}-{branch_index:02d}",
            "source_kind": "synthetic_fixture",
            "source_content": source_content,
            "source_content_sha256": sha256_text(source_content),
        },
    }


def _build_chain(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    previous = "0" * 64
    ledger: list[dict[str, Any]] = []
    for ordinal, candidate in enumerate(candidates):
        body = {
            "ordinal": ordinal,
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": sha256_text(canonical_json(candidate)),
            "prev_hash": previous,
        }
        entry_hash = sha256_text(canonical_json(body))
        ledger.append({**body, "entry_hash": entry_hash})
        previous = entry_hash
    return ledger


def _base_payload(case_index: int, rng: random.Random) -> dict[str, Any]:
    count = rng.randint(1, 8)
    candidates = [_candidate(case_index, i, rng) for i in range(count)]
    budget = sum(c["compute_cost_units"] for c in candidates) + rng.randint(1, 8)
    payload = {
        "schema": "janus.genesis.sim1.case.v1",
        "case_id": f"FZ-{case_index:04d}",
        "read_only": True,
        "runtime_authority": "NONE",
        "network_write": False,
        "file_deletion": False,
        "self_modification": False,
        "external_actuation": False,
        "budget_units": budget,
        "candidate_cap": MAX_CANDIDATES,
        "frozen_branch_ids": [c["candidate_id"] for c in candidates],
        "candidates": candidates,
        "ledger": _build_chain(candidates),
    }
    return payload


def _mutate(payload: dict[str, Any], attack: str) -> str:
    """Return payload as JSON text after one deterministic adversarial mutation."""
    if attack == "valid":
        return canonical_json(payload)
    if attack == "malformed_json":
        return canonical_json(payload)[:-7]
    if attack == "false_provenance":
        payload["candidates"][0]["provenance"]["source_content"] += " tampered"
        return canonical_json(payload)
    if attack == "duplicate_branch":
        duplicate = json.loads(canonical_json(payload["candidates"][0]))
        payload["candidates"].append(duplicate)
        payload["ledger"] = _build_chain(payload["candidates"])
        return canonical_json(payload)
    if attack == "missing_branch":
        payload["candidates"].pop()
        payload["ledger"] = _build_chain(payload["candidates"])
        return canonical_json(payload)
    if attack == "resource_exhaustion":
        payload["budget_units"] = 1
        for candidate in payload["candidates"]:
            candidate["compute_cost_units"] = 10
        payload["ledger"] = _build_chain(payload["candidates"])
        return canonical_json(payload)
    if attack == "hash_chain_tamper":
        payload["ledger"][0]["candidate_sha256"] = "f" * 64
        return canonical_json(payload)
    if attack == "privacy_leak":
        payload["candidates"][0]["claim"] = "leaked token sk-test-1234567890ABCDEFGHIJ"
        payload["ledger"] = _build_chain(payload["candidates"])
        return canonical_json(payload)
    if attack == "schema_violation":
        payload["budget_units"] = "unbounded"
        return canonical_json(payload)
    if attack == "payload_limit":
        payload["padding"] = "X" * (MAX_PAYLOAD_BYTES + 1)
        return canonical_json(payload)
    raise ValueError(f"unknown attack: {attack}")


def generate_corpus(seed: int, case_count: int) -> list[dict[str, Any]]:
    if not 1 <= case_count <= MAX_CASES:
        raise ValueError(f"case_count must be between 1 and {MAX_CASES}")
    rng = random.Random(seed)
    envelopes: list[dict[str, Any]] = []
    for index in range(case_count):
        attack = ATTACKS[index % len(ATTACKS)]
        payload = _base_payload(index, rng)
        payload_json = _mutate(payload, attack)
        envelopes.append(
            {
                "case_id": f"FZ-{index:04d}",
                "attack_class": attack,
                "expected_terminal": EXPECTED_TERMINALS[attack],
                "payload_bytes": len(payload_json.encode("utf-8")),
                "payload_sha256": sha256_text(payload_json),
                "payload_json": payload_json,
            }
        )
    return envelopes


def replay_digest(envelopes: list[dict[str, Any]]) -> str:
    stable = [
        {
            "case_id": e["case_id"],
            "attack_class": e["attack_class"],
            "expected_terminal": e["expected_terminal"],
            "payload_bytes": e["payload_bytes"],
            "payload_sha256": e["payload_sha256"],
        }
        for e in envelopes
    ]
    return sha256_text(canonical_json(stable))


def write_corpus(output: Path, seed: int, case_count: int) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    envelopes = generate_corpus(seed, case_count)
    digest = replay_digest(envelopes)
    cases_path = output / "cases.jsonl"
    with cases_path.open("w", encoding="utf-8", newline="\n") as handle:
        for envelope in envelopes:
            handle.write(canonical_json(envelope) + "\n")
    counts = {attack: 0 for attack in ATTACKS}
    for envelope in envelopes:
        counts[envelope["attack_class"]] += 1
    manifest = {
        "schema": "janus.genesis.sim1.producer_manifest.v1",
        "version": VERSION,
        "generated_utc": utc_now(),
        "seed": seed,
        "case_count": case_count,
        "attack_counts": counts,
        "replay_digest_sha256": digest,
        "cases_file_sha256": sha256_text(cases_path.read_text(encoding="utf-8")),
        "safety_boundary": {
            "runtime_authority": "NONE",
            "network_write": False,
            "file_deletion": False,
            "self_modification": False,
            "external_actuation": False,
            "real_syslog_ingest": False,
        },
    }
    (output / "producer_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (output / "producer_resource_telemetry.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["case_id", "attack_class", "payload_bytes", "candidate_budget_declared"],
        )
        writer.writeheader()
        for envelope in envelopes:
            budget: int | str = "unparsed"
            try:
                parsed = json.loads(envelope["payload_json"])
                budget = parsed.get("budget_units", "missing")
            except json.JSONDecodeError:
                pass
            writer.writerow(
                {
                    "case_id": envelope["case_id"],
                    "attack_class": envelope["attack_class"],
                    "payload_bytes": envelope["payload_bytes"],
                    "candidate_budget_declared": budget,
                }
            )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--cases", type=int, default=DEFAULT_CASES)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    manifest = write_corpus(args.output, args.seed, args.cases)
    if args.print_summary:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
