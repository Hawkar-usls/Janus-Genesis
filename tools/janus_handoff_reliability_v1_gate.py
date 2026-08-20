#!/usr/bin/env python3
"""Fail-closed structural/admission gate for JANUS handoff reliability #164."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "protocol" / "JANUS_HANDOFF_RELIABILITY_V1_PREREGISTRATION.json"
REQUIRED = [f"HR{i}_" for i in range(1, 11)]


def evaluate(mode: str) -> tuple[int, dict]:
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gates = c["required_gates"]
    errors: list[str] = []

    if c.get("status") != "FROZEN_SCOPE_BLOCKED_BY_LIVE_RECEIVER_SOURCE_IDENTITY":
        errors.append("unexpected_contract_status")
    if c["observed_boundary"].get("live_receiver_source_identity") != "UNRESOLVED":
        errors.append("receiver_identity_claim_changed_without_revalidation")
    if c["observed_boundary"].get("private_janus_io_proven_to_own_live_receiver") is not False:
        errors.append("unproven_private_repo_owner_upgrade")
    if c["observed_boundary"].get("service_owner_reconciled") is not False:
        errors.append("unproven_service_owner_upgrade")
    if len(gates) != 10:
        errors.append("required_gate_count_must_be_10")
    for prefix in REQUIRED:
        matches = [k for k in gates if k.startswith(prefix)]
        if len(matches) != 1:
            errors.append(f"missing_or_duplicate_gate:{prefix}")
    if any(v not in {"OPEN", "PASS", "FAIL", "HOLD"} for v in gates.values()):
        errors.append("invalid_gate_state")
    if len(c.get("required_failure_vectors", [])) != 9:
        errors.append("failure_vector_count_must_be_9")
    safety = c.get("safety", {})
    if safety.get("SOURCE_WRITEBACK_DEFAULT") != "DENY":
        errors.append("source_writeback_must_remain_deny")
    if safety.get("DESTRUCTIVE_ACTION") != "FORBIDDEN":
        errors.append("destructive_action_must_remain_forbidden")
    if safety.get("AUTHORITY_DELTA") != 0:
        errors.append("authority_delta_must_be_zero")
    if safety.get("MASS_EFFECT_BUDGET_DELTA") != 0:
        errors.append("mass_effect_budget_delta_must_be_zero")

    open_gates = sorted(k for k, v in gates.items() if v != "PASS")
    identity_bound = c["observed_boundary"].get("live_receiver_source_identity") not in {None, "", "UNRESOLVED"}
    all_pass = not open_gates

    if errors:
        status, rc = "FAIL", 1
    elif mode == "structural":
        status, rc = "PASS_PREREGISTRATION_ONLY", 0
    elif identity_bound and all_pass:
        status, rc = "PASS", 0
    else:
        status, rc = "HOLD", 2

    receipt = {
        "schema": "janus.handoff_reliability.receipt.v1",
        "mode": mode,
        "status": status,
        "contract_id": c["contract_id"],
        "live_receiver_source_identity_bound": identity_bound,
        "service_owner_reconciled": c["observed_boundary"]["service_owner_reconciled"],
        "open_or_nonpass_gates": open_gates,
        "required_gate_count": len(gates),
        "failure_vector_count": len(c["required_failure_vectors"]),
        "errors": errors,
        "issue_162_runnable_contribution": status == "PASS",
        "source_writeback_default": safety["SOURCE_WRITEBACK_DEFAULT"],
        "authority_delta": safety["AUTHORITY_DELTA"],
        "mass_effect_budget_delta": safety["MASS_EFFECT_BUDGET_DELTA"]
    }
    return rc, receipt


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("structural", "admission"), required=True)
    p.add_argument("--output")
    args = p.parse_args()
    rc, receipt = evaluate(args.mode)
    text = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(text, end="")
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
