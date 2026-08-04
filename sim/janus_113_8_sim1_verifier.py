#!/usr/bin/env python3
"""Independent verifier for JANUS 113.8 SIM-1 proof-carrying fuzz corpus.

This verifier intentionally does not import the producer module. It re-parses
serialized artifacts and independently enforces schema, provenance, accounting,
resource, privacy, and hash-chain invariants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERIFIER_VERSION = "JANUS-113.8-SIM-1-INDEPENDENT-VERIFIER-v1.0"
MAX_PAYLOAD_BYTES = 32_768
MAX_CANDIDATES = 32
MAX_BUDGET_UNITS = 512
ALLOWED_STATUSES = {
    "retained",
    "rejected_with_reason",
    "failed_verification",
    "timed_out",
    "deferred",
    "unresolved",
}
REQUIRED_PAYLOAD_KEYS = {
    "schema",
    "case_id",
    "read_only",
    "runtime_authority",
    "network_write",
    "file_deletion",
    "self_modification",
    "external_actuation",
    "budget_units",
    "candidate_cap",
    "frozen_branch_ids",
    "candidates",
    "ledger",
}
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+-]{12,}"),
)
KNOWN_TERMINALS = {
    "VERIFIED_CORPUS_CASE",
    "REJECT_MALFORMED_JSON",
    "REJECT_FALSE_PROVENANCE",
    "REJECT_DUPLICATE_BRANCH",
    "REJECT_BRANCH_ACCOUNTING",
    "REJECT_RESOURCE_EXHAUSTION",
    "REJECT_HASH_CHAIN_TAMPER",
    "REJECT_PRIVACY_LEAK",
    "REJECT_SCHEMA_VIOLATION",
    "REJECT_PAYLOAD_LIMIT",
    "REJECT_ENVELOPE_TAMPER",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _all_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _all_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_strings(item)


def _privacy_leak(payload: dict[str, Any]) -> bool:
    return any(pattern.search(text) for text in _all_strings(payload) for pattern in SECRET_PATTERNS)


def _payload_schema_ok(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload is not an object"
    if set(payload) != REQUIRED_PAYLOAD_KEYS:
        return False, "payload keys do not match the sealed schema"
    if payload.get("schema") != "janus.genesis.sim1.case.v1":
        return False, "schema identifier mismatch"
    if not isinstance(payload.get("case_id"), str):
        return False, "case_id must be a string"
    if payload.get("read_only") is not True:
        return False, "read_only must be true"
    if payload.get("runtime_authority") != "NONE":
        return False, "runtime authority must remain NONE"
    for key in ("network_write", "file_deletion", "self_modification", "external_actuation"):
        if payload.get(key) is not False:
            return False, f"{key} must be false"
    budget = payload.get("budget_units")
    if not isinstance(budget, int) or isinstance(budget, bool) or not 0 <= budget <= MAX_BUDGET_UNITS:
        return False, "budget_units must be a bounded integer"
    cap = payload.get("candidate_cap")
    if not isinstance(cap, int) or isinstance(cap, bool) or not 1 <= cap <= MAX_CANDIDATES:
        return False, "candidate_cap must be a bounded integer"
    if not isinstance(payload.get("frozen_branch_ids"), list):
        return False, "frozen_branch_ids must be an array"
    if not isinstance(payload.get("candidates"), list):
        return False, "candidates must be an array"
    if not isinstance(payload.get("ledger"), list):
        return False, "ledger must be an array"
    return True, "sealed schema accepted"


def _candidate_schema_ok(candidate: Any) -> bool:
    if not isinstance(candidate, dict):
        return False
    required = {
        "candidate_id",
        "claim",
        "confidence",
        "verifier_score",
        "status",
        "reason",
        "compute_cost_units",
        "provenance",
    }
    if set(candidate) != required:
        return False
    if not isinstance(candidate["candidate_id"], str) or not candidate["candidate_id"]:
        return False
    if not isinstance(candidate["claim"], str) or not isinstance(candidate["reason"], str):
        return False
    for field in ("confidence", "verifier_score"):
        value = candidate[field]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0.0 <= float(value) <= 1.0:
            return False
    if candidate["status"] not in ALLOWED_STATUSES:
        return False
    cost = candidate["compute_cost_units"]
    if not isinstance(cost, int) or isinstance(cost, bool) or not 0 <= cost <= MAX_BUDGET_UNITS:
        return False
    provenance = candidate["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {
        "source_id",
        "source_kind",
        "source_content",
        "source_content_sha256",
    }:
        return False
    return all(isinstance(provenance[k], str) for k in provenance)


def _provenance_ok(candidates: list[dict[str, Any]]) -> bool:
    for candidate in candidates:
        provenance = candidate["provenance"]
        if sha256_text(provenance["source_content"]) != provenance["source_content_sha256"]:
            return False
    return True


def _hash_chain_ok(candidates: list[dict[str, Any]], ledger: list[dict[str, Any]]) -> bool:
    if len(candidates) != len(ledger):
        return False
    previous = "0" * 64
    for ordinal, (candidate, entry) in enumerate(zip(candidates, ledger, strict=True)):
        if not isinstance(entry, dict) or set(entry) != {
            "ordinal",
            "candidate_id",
            "candidate_sha256",
            "prev_hash",
            "entry_hash",
        }:
            return False
        expected_body = {
            "ordinal": ordinal,
            "candidate_id": candidate["candidate_id"],
            "candidate_sha256": sha256_text(canonical_json(candidate)),
            "prev_hash": previous,
        }
        expected_hash = sha256_text(canonical_json(expected_body))
        if entry != {**expected_body, "entry_hash": expected_hash}:
            return False
        previous = expected_hash
    return True


def verify_envelope(envelope: Any) -> dict[str, Any]:
    case_id = envelope.get("case_id", "UNKNOWN") if isinstance(envelope, dict) else "UNKNOWN"
    expected = envelope.get("expected_terminal") if isinstance(envelope, dict) else None
    attack = envelope.get("attack_class") if isinstance(envelope, dict) else None
    reason = ""
    if not isinstance(envelope, dict):
        terminal = "REJECT_ENVELOPE_TAMPER"
        reason = "envelope is not an object"
    elif not isinstance(envelope.get("payload_json"), str):
        terminal = "REJECT_ENVELOPE_TAMPER"
        reason = "payload_json is missing or not text"
    else:
        payload_json = envelope["payload_json"]
        actual_bytes = len(payload_json.encode("utf-8"))
        if envelope.get("payload_bytes") != actual_bytes or envelope.get("payload_sha256") != sha256_text(payload_json):
            terminal = "REJECT_ENVELOPE_TAMPER"
            reason = "payload byte count or digest mismatch"
        elif actual_bytes > MAX_PAYLOAD_BYTES:
            terminal = "REJECT_PAYLOAD_LIMIT"
            reason = "payload exceeds the sealed byte limit"
        else:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                terminal = "REJECT_MALFORMED_JSON"
                reason = "payload is malformed JSON"
            else:
                schema_ok, schema_reason = _payload_schema_ok(payload)
                if not schema_ok:
                    terminal = "REJECT_SCHEMA_VIOLATION"
                    reason = schema_reason
                else:
                    candidates = payload["candidates"]
                    if not candidates or len(candidates) > payload["candidate_cap"] or any(
                        not _candidate_schema_ok(candidate) for candidate in candidates
                    ):
                        terminal = "REJECT_SCHEMA_VIOLATION"
                        reason = "candidate collection violates schema or cap"
                    else:
                        candidate_ids = [c["candidate_id"] for c in candidates]
                        if len(candidate_ids) != len(set(candidate_ids)):
                            terminal = "REJECT_DUPLICATE_BRANCH"
                            reason = "candidate identifiers are not unique"
                        elif not _provenance_ok(candidates):
                            terminal = "REJECT_FALSE_PROVENANCE"
                            reason = "source content does not match its frozen digest"
                        elif _privacy_leak(payload):
                            terminal = "REJECT_PRIVACY_LEAK"
                            reason = "raw secret-like material crossed the proof boundary"
                        elif Counter(payload["frozen_branch_ids"]) != Counter(candidate_ids):
                            terminal = "REJECT_BRANCH_ACCOUNTING"
                            reason = "frozen branch set and candidate set differ"
                        elif sum(c["compute_cost_units"] for c in candidates) > payload["budget_units"]:
                            terminal = "REJECT_RESOURCE_EXHAUSTION"
                            reason = "declared candidate cost exceeds the hard budget"
                        elif not _hash_chain_ok(candidates, payload["ledger"]):
                            terminal = "REJECT_HASH_CHAIN_TAMPER"
                            reason = "witness-ledger hash chain failed independent replay"
                        else:
                            terminal = "VERIFIED_CORPUS_CASE"
                            reason = "schema, provenance, privacy, accounting, budget, and chain passed"
    return {
        "case_id": case_id,
        "attack_class": attack,
        "expected_terminal": expected,
        "actual_terminal": terminal,
        "matches_expected": terminal == expected,
        "known_terminal": terminal in KNOWN_TERMINALS,
        "reason": reason,
    }


def _stable_replay_digest(envelopes: list[dict[str, Any]]) -> str:
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


def verify_corpus(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    manifest_path = input_dir / "producer_manifest.json"
    cases_path = input_dir / "cases.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lines = [line for line in cases_path.read_text(encoding="utf-8").splitlines() if line]
    envelopes = [json.loads(line) for line in lines]
    manifest_checks = {
        "case_count": manifest.get("case_count") == len(envelopes),
        "cases_file_sha256": manifest.get("cases_file_sha256") == sha256_text(cases_path.read_text(encoding="utf-8")),
        "replay_digest_sha256": manifest.get("replay_digest_sha256") == _stable_replay_digest(envelopes),
        "safety_boundary": manifest.get("safety_boundary") == {
            "runtime_authority": "NONE",
            "network_write": False,
            "file_deletion": False,
            "self_modification": False,
            "external_actuation": False,
            "real_syslog_ingest": False,
        },
    }
    results = [verify_envelope(envelope) for envelope in envelopes]
    observed_attacks = Counter(result["attack_class"] for result in results)
    required_attacks = {
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
    }
    suite_checks = {
        "manifest_checks_pass": all(manifest_checks.values()),
        "all_cases_match_expected": all(result["matches_expected"] for result in results),
        "all_terminals_known": all(result["known_terminal"] for result in results),
        "all_attack_classes_present": required_attacks <= set(observed_attacks),
        "no_duplicate_case_ids": len({r["case_id"] for r in results}) == len(results),
        "case_count_bounded": 1 <= len(results) <= 500,
    }
    admitted = all(suite_checks.values())
    terminal = "JANUS_113.8_SIM_1_ADMITTED" if admitted else "JANUS_113.8_SIM_1_REJECTED"
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "independent_results.jsonl"
    results_path.write_text(
        "".join(canonical_json(result) + "\n" for result in results), encoding="utf-8"
    )
    report = {
        "schema": "janus.genesis.sim1.independent_verification_report.v1",
        "verifier_version": VERIFIER_VERSION,
        "generated_utc": utc_now(),
        "producer_manifest_sha256": sha256_text(manifest_path.read_text(encoding="utf-8")),
        "manifest_checks": manifest_checks,
        "suite_checks": suite_checks,
        "attack_counts": dict(sorted(observed_attacks.items())),
        "actual_terminal_counts": dict(sorted(Counter(r["actual_terminal"] for r in results).items())),
        "failed_case_ids": [r["case_id"] for r in results if not r["matches_expected"]],
        "terminal": terminal,
        "admitted": admitted,
        "case_count": len(results),
        "replay_digest_sha256": manifest.get("replay_digest_sha256"),
        "next_terminal": "SIM_2_OPEN_WORLD_CALIBRATION_REQUIRED" if admitted else "SIM_1_CORRECTION_REQUIRED",
    }
    (output_dir / "independent_verification_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = {
        "schema": "janus.genesis.sim1.summary.v1",
        "terminal": terminal,
        "admitted": admitted,
        "case_count": len(results),
        "passed_cases": sum(1 for r in results if r["matches_expected"]),
        "replay_digest_sha256": manifest.get("replay_digest_sha256"),
        "next_terminal": report["next_terminal"],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    report = verify_corpus(args.input, args.output)
    if args.print_summary:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["admitted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
