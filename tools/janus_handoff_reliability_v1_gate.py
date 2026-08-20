#!/usr/bin/env python3
"""Fail-closed structural/admission gate for JANUS handoff reliability #164."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "protocol" / "JANUS_HANDOFF_RELIABILITY_V1_PREREGISTRATION.json"
REQUIRED_PREFIXES = [f"HR{i}_" for i in range(1, 11)]
VALID_STATES = {"OPEN", "PASS", "FAIL", "HOLD"}


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_contract(c: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gates = c.get("required_gates", {})
    if c.get("status") != "FROZEN_SCOPE_BLOCKED_BY_LIVE_RECEIVER_SOURCE_IDENTITY":
        errors.append("unexpected_contract_status")
    if c.get("observed_boundary", {}).get("live_receiver_source_identity") != "UNRESOLVED":
        errors.append("frozen_contract_must_not_claim_live_identity")
    if c.get("observed_boundary", {}).get("private_janus_io_proven_to_own_live_receiver") is not False:
        errors.append("unproven_private_repo_owner_upgrade")
    if c.get("observed_boundary", {}).get("service_owner_reconciled") is not False:
        errors.append("unproven_service_owner_upgrade")
    if len(gates) != 10:
        errors.append("required_gate_count_must_be_10")
    for prefix in REQUIRED_PREFIXES:
        matches = [k for k in gates if k.startswith(prefix)]
        if len(matches) != 1:
            errors.append(f"missing_or_duplicate_gate:{prefix}")
    if any(v not in VALID_STATES for v in gates.values()):
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
    return errors


def _validate_binding(binding: dict[str, Any] | None, c: dict[str, Any]) -> tuple[bool, list[str]]:
    if binding is None:
        return False, ["live_binding_receipt_missing"]
    errors: list[str] = []
    req = c.get("binding_receipt_requirements", {})
    if binding.get("evidence_kind") != req.get("evidence_kind", "LIVE"):
        errors.append("binding_not_live_evidence")
    if binding.get("receiver_service") != req.get("receiver_service", "janus_nas_brain"):
        errors.append("binding_receiver_service_mismatch")
    if not binding.get("process_identity"):
        errors.append("binding_process_identity_missing")
    source = binding.get("source_identity") or {}
    if not source.get("sha256"):
        errors.append("binding_source_sha256_missing")
    if source.get("git_applicable") is True:
        if not source.get("repository"):
            errors.append("binding_git_repository_missing")
        if not source.get("commit"):
            errors.append("binding_git_commit_missing")
        if not source.get("blob"):
            errors.append("binding_git_blob_missing")
    if not binding.get("port_8008_owner"):
        errors.append("binding_port_owner_missing")
    if not binding.get("network_namespace"):
        errors.append("binding_network_namespace_missing")
    if binding.get("service_owner_reconciled") is not True:
        errors.append("binding_service_owner_not_reconciled")
    return not errors, errors


def _validate_gate_results(results: dict[str, Any] | None, c: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    required = c.get("required_gates", {})
    if results is None:
        return False, ["live_gate_results_missing"], sorted(required)
    gates = results.get("gates") or {}
    errors: list[str] = []
    missing_or_nonpass: list[str] = []
    for name in required:
        state = gates.get(name)
        if state != "PASS":
            missing_or_nonpass.append(name)
    if results.get("evidence_kind") != "LIVE":
        errors.append("gate_results_not_live_evidence")
    vectors = results.get("failure_vectors") or {}
    required_vectors = c.get("required_failure_vectors", [])
    if set(vectors) != set(required_vectors):
        errors.append("failure_vector_set_mismatch")
    elif any(v != "PASS" for v in vectors.values()):
        errors.append("one_or_more_failure_vectors_nonpass")
    return not errors and not missing_or_nonpass, errors, sorted(missing_or_nonpass)


def evaluate(
    mode: str,
    *,
    contract_path: Path = CONTRACT,
    binding_path: Path | None = None,
    gate_results_path: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    c = json.loads(contract_path.read_text(encoding="utf-8"))
    contract_errors = _validate_contract(c)
    safety = c.get("safety", {})

    binding = _load(binding_path)
    results = _load(gate_results_path)
    binding_ok, binding_errors = _validate_binding(binding, c)
    results_ok, result_errors, open_gates = _validate_gate_results(results, c)

    errors = contract_errors[:]
    if mode == "admission":
        errors.extend(binding_errors)
        errors.extend(result_errors)

    if contract_errors:
        status, rc = "FAIL", 1
    elif mode == "structural":
        status, rc = "PASS_PREREGISTRATION_ONLY", 0
    elif binding_ok and results_ok:
        status, rc = "PASS", 0
    else:
        status, rc = "HOLD", 2

    receipt = {
        "schema": "janus.handoff_reliability.receipt.v1",
        "mode": mode,
        "status": status,
        "contract_id": c.get("contract_id"),
        "genesis_base": c.get("genesis_base"),
        "live_receiver_source_identity_bound": bool(binding_ok),
        "service_owner_reconciled": bool(binding and binding.get("service_owner_reconciled") is True),
        "open_or_nonpass_gates": open_gates if mode == "admission" else sorted(c.get("required_gates", {})),
        "required_gate_count": len(c.get("required_gates", {})),
        "failure_vector_count": len(c.get("required_failure_vectors", [])),
        "errors": errors,
        "issue_162_runnable_contribution": status == "PASS",
        "source_writeback_default": safety.get("SOURCE_WRITEBACK_DEFAULT"),
        "authority_delta": safety.get("AUTHORITY_DELTA"),
        "mass_effect_budget_delta": safety.get("MASS_EFFECT_BUDGET_DELTA"),
    }
    return rc, receipt


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("structural", "admission"), required=True)
    p.add_argument("--contract", type=Path, default=CONTRACT)
    p.add_argument("--binding", type=Path)
    p.add_argument("--gate-results", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    rc, receipt = evaluate(
        args.mode,
        contract_path=args.contract,
        binding_path=args.binding,
        gate_results_path=args.gate_results,
    )
    text = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
