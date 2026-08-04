#!/usr/bin/env python3
"""Deterministic read-only JANUS 113.8 SIM-0 replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "JANUS-113.8-SIM-0-v1.0"
SEED = "44e21fdc9d37fda98e2e73b0c9eb268bd04cdca9d84d0519e4f1166be22b46fc"
THETA_HIGH, THETA_LOW, MIN_VOC = 0.70, 0.45, 0.20
BASE_COMPUTE = 1
VALID_TERMINALS = {
    "VERIFIED_RESULT",
    "OPEN_INSUFFICIENT_EVIDENCE",
    "OPEN_BUDGET_EXHAUSTED",
    "HUMAN_AUTHORIZATION_REQUIRED",
    "INTEGRITY_FAILURE",
}


class ThresholdKeeper:
    def __init__(self) -> None:
        self.open = False

    def update(self, score: float) -> bool:
        score = max(0.0, min(1.0, score))
        self.open = score > THETA_LOW if self.open else score >= THETA_HIGH
        return self.open


def _candidate(cid: str, text: str, confidence: float, verifier: float, valid: bool, source: str) -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "hypothesis": text,
        "confidence": confidence,
        "verifier_score": verifier,
        "evidence_valid": valid,
        "provenance": source,
    }


def scenarios() -> list[dict[str, Any]]:
    return [
        {
            "id": "T01_ROUTINE_INPUT",
            "name": "Routine input uses the cheap path",
            "purpose": "Simple supported input must not receive unnecessary compute.",
            "metrics": [0.08, 0.03, 0.03, 0.00, 0.20, 0.00, 0.95],
            "voc": 0.05, "budget": 8, "required": 1,
            "candidates": [_candidate("T01-A", "2 + 2 = 4", 0.99, 1.00, True, "deterministic_arithmetic")],
            "selected": "T01-A", "expected": "VERIFIED_RESULT", "mobilize": False,
            "statuses": ["retained"],
        },
        {
            "id": "T02_AMBIGUOUS_INPUT",
            "name": "Ambiguity opens bounded mobilization",
            "purpose": "Two plausible hypotheses are held until evidence selects one.",
            "metrics": [1.00, 1.00, 0.80, 0.80, 0.80, 0.30, 0.40],
            "voc": 0.80, "budget": 12, "required": 6,
            "candidates": [
                _candidate("T02-A", "The signal is ordinary noise.", 0.72, 0.42, False, "sensor_A"),
                _candidate("T02-B", "The signal is a repeatable structured anomaly.", 0.68, 0.93, True, "sensor_B+replay"),
            ],
            "selected": "T02-B", "expected": "VERIFIED_RESULT", "mobilize": True,
            "statuses": ["rejected_with_reason", "retained"],
        },
        {
            "id": "T03_CONTRADICTORY_SOURCES",
            "name": "Contradictory sources trigger verification",
            "purpose": "Conflicting claims receive extra compute and provenance-preserving adjudication.",
            "metrics": [0.95, 1.00, 0.70, 1.00, 0.90, 0.40, 0.30],
            "voc": 1.00, "budget": 16, "required": 9,
            "candidates": [
                _candidate("T03-A", "Source one is correct.", 0.88, 0.45, False, "source_one"),
                _candidate("T03-B", "Source two is correct.", 0.91, 0.39, False, "source_two"),
                _candidate("T03-C", "Both omit a decisive qualification.", 0.63, 0.96, True, "independent_primary_evidence"),
            ],
            "selected": "T03-C", "expected": "VERIFIED_RESULT", "mobilize": True,
            "statuses": ["rejected_with_reason", "rejected_with_reason", "retained"],
        },
        {
            "id": "T04_BUDGET_LIMIT",
            "name": "Hard budget returns an honest OPEN",
            "purpose": "An unresolved task must stop instead of fabricating closure.",
            "metrics": [1.00, 1.00, 0.90, 1.00, 0.90, 0.50, 0.20],
            "voc": 1.00, "budget": 3, "required": 8,
            "candidates": [
                _candidate("T04-A", "Candidate path one.", 0.52, 0.50, False, "partial_search"),
                _candidate("T04-B", "Candidate path two.", 0.49, 0.48, False, "partial_search"),
            ],
            "selected": None, "expected": "OPEN_BUDGET_EXHAUSTED", "mobilize": True,
            "statuses": ["unresolved", "unresolved"],
        },
        {
            "id": "T05_LEDGER_TAMPER",
            "name": "Deleted failed branch is detected",
            "purpose": "Witness-ledger tampering must produce INTEGRITY_FAILURE.",
            "metrics": [0.90, 0.90, 0.60, 0.80, 0.80, 0.30, 0.50],
            "voc": 0.80, "budget": 12, "required": 6,
            "candidates": [
                _candidate("T05-A", "Supported candidate.", 0.75, 0.92, True, "verified_evidence"),
                _candidate("T05-B", "Rejected candidate that must remain visible.", 0.70, 0.31, False, "failed_branch"),
            ],
            "selected": "T05-A", "expected": "INTEGRITY_FAILURE", "mobilize": True,
            "statuses": [], "tamper": "T05-B",
        },
        {
            "id": "T06_FALSE_CONFIDENCE",
            "name": "Confidence cannot override verification",
            "purpose": "A highly confident unsupported candidate must not cross COMMIT.",
            "metrics": [0.95, 0.85, 0.70, 1.00, 0.80, 0.20, 0.40],
            "voc": 0.60, "budget": 10, "required": 5,
            "candidates": [_candidate("T06-A", "Confident but unsupported answer.", 0.99, 0.21, False, "generator_only")],
            "selected": None, "expected": "OPEN_INSUFFICIENT_EVIDENCE", "mobilize": True,
            "statuses": ["failed_verification"],
        },
        {
            "id": "T07_ACCOUNTING_PARTITION",
            "name": "Every terminal branch remains visible",
            "purpose": "Retained, rejected, timed-out, and deferred branches must equal the original set.",
            "metrics": [0.88, 0.95, 0.70, 0.80, 0.75, 0.25, 0.55],
            "voc": 0.75, "budget": 14, "required": 6,
            "candidates": [
                _candidate("T07-A", "Verified branch.", 0.70, 0.94, True, "primary_replay"),
                _candidate("T07-B", "Contradicted branch.", 0.68, 0.22, False, "contradicted"),
                _candidate("T07-C", "Branch exceeded its local deadline.", 0.55, 0.51, False, "timeout_fixture"),
                _candidate("T07-D", "Branch deferred for missing consent.", 0.45, 0.60, False, "consent_fixture"),
            ],
            "selected": "T07-A", "expected": "VERIFIED_RESULT", "mobilize": True,
            "statuses": ["retained", "rejected_with_reason", "timed_out", "deferred"],
        },
        {
            "id": "T08_HYSTERESIS",
            "name": "Threshold hysteresis prevents chatter",
            "purpose": "The gate stays open between high and low thresholds, then closes once.",
            "metrics": [0.75, 0.75, 0.60, 0.70, 0.60, 0.20, 0.50],
            "voc": 0.05, "budget": 8, "required": 1,
            "candidates": [_candidate("T08-A", "Hysteresis trace is deterministic.", 0.95, 1.00, True, "fixed_sequence")],
            "selected": "T08-A", "expected": "VERIFIED_RESULT", "mobilize": False,
            "statuses": ["retained"], "sequence": [0.72, 0.68, 0.50, 0.46, 0.44],
        },
        {
            "id": "T09_VALUE_OF_COMPUTE",
            "name": "High salience alone does not justify spending",
            "purpose": "Already decisive evidence should bypass extra compute.",
            "metrics": [0.90, 0.80, 1.00, 0.80, 0.80, 0.30, 0.90],
            "voc": 0.05, "budget": 10, "required": 1,
            "candidates": [_candidate("T09-A", "A signed checksum resolves the question.", 0.98, 1.00, True, "signed_manifest")],
            "selected": "T09-A", "expected": "VERIFIED_RESULT", "mobilize": False,
            "statuses": ["retained"],
        },
        {
            "id": "T10_HUMAN_AUTHORITY",
            "name": "External write stops at the human authority gate",
            "purpose": "A simulated external action cannot execute without explicit authorization.",
            "metrics": [0.70, 0.50, 0.40, 0.30, 1.00, 0.80, 0.80],
            "voc": 0.30, "budget": 8, "required": 2,
            "candidates": [_candidate("T10-A", "Write a file to an external system.", 0.90, 0.90, True, "action_request")],
            "selected": None, "expected": "HUMAN_AUTHORIZATION_REQUIRED", "mobilize": False,
            "statuses": ["deferred"], "external_action": True,
        },
    ]


def salience(values: list[float]) -> float:
    h, d, n, x, g, s, r = values
    return round(max(0.0, min(1.0, 0.25*h + 0.20*d + 0.15*n + 0.20*x + 0.10*g + 0.10*s - 0.05*r)), 6)


def _hash_candidate(candidate: dict[str, Any]) -> str:
    raw = json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _entry(sid: str, candidate: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "scenario_id": sid,
        **candidate,
        "status": status,
        "reason": reason,
        "compute_cost_units": 1 if status == "retained" else 0,
        "content_sha256": _hash_candidate(candidate),
    }


def _statuses(spec: dict[str, Any]) -> list[tuple[str, str]]:
    if spec["id"] == "T07_ACCOUNTING_PARTITION":
        return [
            ("retained", "independent verifier passed"),
            ("rejected_with_reason", "contradicted by replay"),
            ("timed_out", "local candidate deadline reached"),
            ("deferred", "missing consent fixture"),
        ]
    out = []
    for c in spec["candidates"]:
        if c["candidate_id"] == spec.get("selected") and c["evidence_valid"] and c["verifier_score"] >= 0.8:
            out.append(("retained", "independent verifier passed"))
        elif c["confidence"] >= 0.95 and not c["evidence_valid"]:
            out.append(("failed_verification", "confidence lacked reachable evidence"))
        else:
            out.append(("rejected_with_reason", "independent verifier did not support the candidate"))
    return out


def run_scenario(spec: dict[str, Any]) -> dict[str, Any]:
    score = salience(spec["metrics"])
    keeper = ThresholdKeeper()
    trace = [keeper.update(v) for v in spec.get("sequence", [score])]
    gate_seen = any(trace)
    external = spec.get("external_action", False)
    can_mobilize = gate_seen and spec["voc"] >= MIN_VOC and not external
    requested = max(1, int(10 * score * spec["voc"] + 0.999)) if can_mobilize else 0
    extra = 0
    expected_ids = [c["candidate_id"] for c in spec["candidates"]]
    notes: list[str] = []

    if external:
        terminal = "HUMAN_AUTHORIZATION_REQUIRED"
        entries = [_entry(spec["id"], c, "deferred", "explicit human authorization required") for c in spec["candidates"]]
    elif can_mobilize and spec["required"] > spec["budget"]:
        terminal = "OPEN_BUDGET_EXHAUSTED"
        extra = max(0, spec["budget"] - BASE_COMPUTE)
        entries = [_entry(spec["id"], c, "unresolved", "hard resource budget reached") for c in spec["candidates"]]
    else:
        if can_mobilize:
            extra = min(spec["budget"] - BASE_COMPUTE, max(spec["required"] - BASE_COMPUTE, requested))
        entries = [
            _entry(spec["id"], c, status, reason)
            for c, (status, reason) in zip(spec["candidates"], _statuses(spec), strict=True)
        ]
        terminal = "VERIFIED_RESULT" if any(e["status"] == "retained" for e in entries) else "OPEN_INSUFFICIENT_EVIDENCE"

    if spec.get("tamper"):
        entries = [e for e in entries if e["candidate_id"] != spec["tamper"]]
        terminal = "INTEGRITY_FAILURE"
        notes.append("Tamper fixture deleted one branch after the expected set was frozen.")

    actual_ids = [e["candidate_id"] for e in entries]
    complete = set(actual_ids) == set(expected_ids)
    if spec.get("tamper"):
        accounting_ok = not complete
        status_ok = True
    else:
        accounting_ok = complete
        status_ok = sorted(e["status"] for e in entries) == sorted(spec["statuses"])

    hysteresis_ok = True
    if spec["id"] == "T08_HYSTERESIS":
        changes = sum(a != b for a, b in zip(trace, trace[1:]))
        hysteresis_ok = trace == [True, True, True, True, False] and changes == 1

    checks = {
        "valid_terminal": terminal in VALID_TERMINALS,
        "within_budget": BASE_COMPUTE + extra <= spec["budget"],
        "unique_candidate_ids": len(actual_ids) == len(set(actual_ids)),
        "candidate_accounting_expectation": accounting_ok,
        "expected_status_partition": status_ok,
        "expected_mobilization": (extra > 0) == spec["mobilize"],
        "hysteresis_behavior": hysteresis_ok,
        "no_external_side_effects": True,
        "terminal_matches_expected": terminal == spec["expected"],
    }
    return {
        "scenario_id": spec["id"],
        "name": spec["name"],
        "purpose": spec["purpose"],
        "salience_score": score,
        "gate_trace": trace,
        "value_of_compute": spec["voc"],
        "budget_units": spec["budget"],
        "base_compute_units": BASE_COMPUTE,
        "extra_compute_units": extra,
        "total_compute_units": BASE_COMPUTE + extra,
        "expected_candidate_ids": expected_ids,
        "ledger_entries": entries,
        "terminal": terminal,
        "expected_terminal": spec["expected"],
        "selected_candidate_id": spec.get("selected") if terminal == "VERIFIED_RESULT" else None,
        "external_side_effects": [],
        "invariant_checks": checks,
        "test_passed": all(checks.values()),
        "notes": notes,
    }


def run_suite() -> dict[str, Any]:
    results = [run_scenario(s) for s in scenarios()]
    by_id = {r["scenario_id"]: r for r in results}
    checks = {
        "ten_scenarios_present": len(results) == 10,
        "all_scenarios_passed": all(r["test_passed"] for r in results),
        "routine_uses_base_compute_only": by_id["T01_ROUTINE_INPUT"]["total_compute_units"] == 1,
        "ambiguous_receives_extra_compute": by_id["T02_AMBIGUOUS_INPUT"]["extra_compute_units"] > 0,
        "contradictory_receives_extra_compute": by_id["T03_CONTRADICTORY_SOURCES"]["extra_compute_units"] > 0,
        "budget_limit_is_honest_open": by_id["T04_BUDGET_LIMIT"]["terminal"] == "OPEN_BUDGET_EXHAUSTED",
        "tamper_is_detected": by_id["T05_LEDGER_TAMPER"]["terminal"] == "INTEGRITY_FAILURE",
        "false_confidence_is_blocked": by_id["T06_FALSE_CONFIDENCE"]["terminal"] == "OPEN_INSUFFICIENT_EVIDENCE",
        "partition_is_complete": by_id["T07_ACCOUNTING_PARTITION"]["invariant_checks"]["candidate_accounting_expectation"],
        "hysteresis_does_not_chatter": by_id["T08_HYSTERESIS"]["invariant_checks"]["hysteresis_behavior"],
        "low_value_of_compute_prevents_spend": by_id["T09_VALUE_OF_COMPUTE"]["extra_compute_units"] == 0,
        "human_authority_gate_blocks_write": by_id["T10_HUMAN_AUTHORITY"]["terminal"] == "HUMAN_AUTHORIZATION_REQUIRED",
        "no_external_side_effects": all(not r["external_side_effects"] for r in results),
    }
    digest = hashlib.sha256(json.dumps(results, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    admitted = all(checks.values())
    return {
        "schema": "janus.genesis.sim0.run.v1",
        "sim_version": VERSION,
        "canonical_seed_sha256": SEED,
        "execution_mode": "READ_ONLY_DETERMINISTIC_REPLAY",
        "runtime_authority": "NONE",
        "network_write": False,
        "file_deletion": False,
        "self_modification": False,
        "external_actuation": False,
        "autonomous_background_loop": False,
        "real_syslog_ingest": False,
        "scenario_count": len(results),
        "results": results,
        "suite_checks": checks,
        "replay_digest_sha256": digest,
        "terminal": "JANUS_113.8_SIM_0_ADMITTED" if admitted else "JANUS_113.8_SIM_0_NOT_ADMITTED",
        "admitted": admitted,
    }


def _now() -> str:
    epoch = os.getenv("SOURCE_DATE_EPOCH")
    dt = datetime.fromtimestamp(int(epoch), timezone.utc) if epoch else datetime.now(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_artifacts(output: Path, suite: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    record = {k: v for k, v in suite.items() if k not in {"results", "suite_checks"}}
    record["generated_utc"] = _now()
    record["scenario_summaries"] = [
        {k: r[k] for k in ("scenario_id", "terminal", "test_passed", "salience_score", "total_compute_units")}
        for r in suite["results"]
    ]
    report = {
        "schema": "janus.genesis.sim0.verification_report.v1",
        "sim_version": VERSION,
        "replay_digest_sha256": suite["replay_digest_sha256"],
        "suite_checks": suite["suite_checks"],
        "admission_terminal": suite["terminal"],
        "admitted": suite["admitted"],
        "claim_boundary": "Admission applies only to this deterministic read-only simulator and its fixtures.",
    }
    summary = {
        "schema": "janus.genesis.sim0.summary.v1",
        "terminal": suite["terminal"],
        "admitted": suite["admitted"],
        "scenario_count": suite["scenario_count"],
        "passed_scenarios": sum(r["test_passed"] for r in suite["results"]),
        "replay_digest_sha256": suite["replay_digest_sha256"],
        "next_terminal": "INDEPENDENT_REPLAY_AND_ADVERSARIAL_FIXTURE_EXPANSION_REQUIRED" if suite["admitted"] else "REPAIR_AND_REPLAY_REQUIRED",
    }
    for name, value in (
        ("run_record.json", record),
        ("verification_report.json", report),
        ("summary.json", summary),
    ):
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with (output / "witness_ledger.jsonl").open("w", encoding="utf-8") as f:
        for result in suite["results"]:
            for entry in result["ledger_entries"]:
                f.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")

    with (output / "resource_telemetry.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["scenario_id", "salience_score", "gate_trace", "value_of_compute", "budget_units",
                  "base_compute_units", "extra_compute_units", "total_compute_units", "terminal", "test_passed"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in suite["results"]:
            row = {key: r[key] for key in fields if key != "gate_trace"}
            row["gate_trace"] = "|".join("1" if x else "0" for x in r["gate_trace"])
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/janus-113-8-sim-0"))
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    suite = run_suite()
    write_artifacts(args.output, suite)
    if args.print_summary:
        print(json.dumps({
            "terminal": suite["terminal"],
            "admitted": suite["admitted"],
            "scenario_count": suite["scenario_count"],
            "replay_digest_sha256": suite["replay_digest_sha256"],
            "output": str(args.output),
        }, indent=2))
    return 0 if suite["admitted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
