#!/usr/bin/env python3
"""Independent replay verifier for JANUS 113.8 AGENT GAUNTLET-0 proofpacks.

The verifier imports neither the SIM-2 router nor the gauntlet producer. It
checks deterministic attack-result hashes, the complete attack ledger, file
bindings, status conservation, expected finding identities, target-source
binding, safety declarations, and the final terminal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

RESULT_SCHEMA = "janus.genesis.agent_gauntlet0.attack_result.v1"
MANIFEST_SCHEMA = "janus.genesis.agent_gauntlet0.manifest.v1"
TARGET_PATH = "sim/janus_113_8_sim2_router.py"

EXPECTED_RESISTED = {
    "AG0-A00-HASH-TAMPER-CONTROL",
    "AG0-A01-UNTRUSTED-HOST-CONTROL",
    "AG0-A02-CONFLICTING-DIGEST-CONTROL",
    "AG0-A03-FLOATING-MAIN-CONTROL",
}
EXPECTED_FINDINGS = {
    "AG0-A04-METADATA-URL-MISMATCH": "PROVENANCE_METADATA_NOT_BOUND_TO_URL",
    "AG0-A05-FULL-CASE-BINDING-COLLISION": "PREDICTION_HASH_NOT_BOUND_TO_FULL_INPUT_CASE",
    "AG0-A06-DUPLICATE-CASE-ID": "CASE_ID_UNIQUENESS_NOT_ENFORCED",
    "AG0-A07-UNICODE-IDENTIFIER-COLLISION": "IDENTIFIER_NORMALIZATION_NOT_ENFORCED",
    "AG0-A08-DUPLICATE-JSON-KEY": "DUPLICATE_JSON_KEYS_ACCEPTED",
    "AG0-A09-MALFORMED-LINE-CORPUS-ABORT": "MALFORMED_CASE_ABORTS_FULL_LEDGER",
    "AG0-A10-OVERSIZE-COLLAPSED-TO-OPEN": "RESOURCE_LIMIT_COLLAPSED_INTO_UNREACHABLE_OPEN",
    "AG0-A11-REDIRECT-FINAL-HOST": "REDIRECT_TARGET_HOST_NOT_REVALIDATED",
    "AG0-A12-QUERY-FRAGMENT-AMBIGUITY": "NON_CANONICAL_SOURCE_URL_ACCEPTED",
    "AG0-A13-DOT-SEGMENT-PATH": "URL_PATH_CANONICALIZATION_NOT_ENFORCED",
}
EXPECTED_BOUNDARIES = {
    "AG0-A14-MOVABLE-TAG-BOUNDARY": "MOVABLE_GIT_TAG_ALLOWED_BY_SIM2_CONTRACT"
}
EXPECTED_ATTACK_ORDER = [
    "AG0-A00-HASH-TAMPER-CONTROL",
    "AG0-A01-UNTRUSTED-HOST-CONTROL",
    "AG0-A02-CONFLICTING-DIGEST-CONTROL",
    "AG0-A03-FLOATING-MAIN-CONTROL",
    "AG0-A04-METADATA-URL-MISMATCH",
    "AG0-A05-FULL-CASE-BINDING-COLLISION",
    "AG0-A06-DUPLICATE-CASE-ID",
    "AG0-A07-UNICODE-IDENTIFIER-COLLISION",
    "AG0-A08-DUPLICATE-JSON-KEY",
    "AG0-A09-MALFORMED-LINE-CORPUS-ABORT",
    "AG0-A10-OVERSIZE-COLLAPSED-TO-OPEN",
    "AG0-A11-REDIRECT-FINAL-HOST",
    "AG0-A12-QUERY-FRAGMENT-AMBIGUITY",
    "AG0-A13-DOT-SEGMENT-PATH",
    "AG0-A14-MOVABLE-TAG-BOUNDARY",
]
EXPECTED_SAFETY = {
    "real_network_read": False,
    "network_write": False,
    "file_deletion": False,
    "self_modification": False,
    "external_actuation": False,
    "private_repository_access": False,
    "repository_secrets": False,
    "real_syslog_ingest": False,
    "runtime_authority": "NONE",
    "consciousness_status": "NOT_CLAIMED",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[Any]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def verify_proofpack(proofpack_dir: Path, repository_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, bool] = {}

    results_path = proofpack_dir / "attack_results.jsonl"
    ledger_path = proofpack_dir / "attack_ledger.jsonl"
    findings_path = proofpack_dir / "finding_catalog.json"
    manifest_path = proofpack_dir / "gauntlet_manifest.json"

    required_files = [results_path, ledger_path, findings_path, manifest_path]
    checks["required_files_present"] = all(path.is_file() for path in required_files)
    if not checks["required_files_present"]:
        missing = [str(path) for path in required_files if not path.is_file()]
        return {
            "schema": "janus.genesis.agent_gauntlet0.verification_report.v1",
            "verified": False,
            "terminal": "JANUS_113.8_AGENT_GAUNTLET_0_REPLAY_FAILED",
            "checks": checks,
            "errors": [f"missing proofpack files: {missing}"],
        }

    results = load_jsonl(results_path)
    ledger = load_jsonl(ledger_path)
    findings = load_json(findings_path)
    manifest = load_json(manifest_path)

    checks["manifest_schema"] = manifest.get("schema") == MANIFEST_SCHEMA
    checks["result_count"] = len(results) == len(EXPECTED_ATTACK_ORDER)
    checks["ledger_count"] = len(ledger) == len(results)
    checks["attack_order"] = [result.get("attack_id") for result in results] == EXPECTED_ATTACK_ORDER
    checks["unique_attack_ids"] = len({result.get("attack_id") for result in results}) == len(results)

    result_hashes_valid = True
    result_schema_valid = True
    ordinals_valid = True
    for ordinal, result in enumerate(results):
        if result.get("schema") != RESULT_SCHEMA:
            result_schema_valid = False
        if result.get("ordinal") != ordinal:
            ordinals_valid = False
        declared = result.get("result_sha256")
        unsigned = dict(result)
        unsigned.pop("result_sha256", None)
        if declared != sha256_text(canonical_json(unsigned)):
            result_hashes_valid = False
    checks["result_schema_valid"] = result_schema_valid
    checks["result_ordinals_valid"] = ordinals_valid
    checks["result_hashes_replay"] = result_hashes_valid

    previous = "0" * 64
    ledger_valid = len(ledger) == len(results)
    if ledger_valid:
        for ordinal, (entry, result) in enumerate(zip(ledger, results)):
            body = {
                "ordinal": ordinal,
                "attack_id": result["attack_id"],
                "result_sha256": result["result_sha256"],
                "prev_hash": previous,
            }
            expected_entry_hash = sha256_text(canonical_json(body))
            if entry != {**body, "entry_hash": expected_entry_hash}:
                ledger_valid = False
                break
            previous = expected_entry_hash
    checks["complete_attack_ledger_replay"] = ledger_valid

    status_counts = dict(sorted(Counter(result.get("status") for result in results).items()))
    checks["status_counts_match_manifest"] = manifest.get("status_counts") == status_counts
    checks["attack_count_matches_manifest"] = manifest.get("attack_count") == len(results)
    conservation = manifest.get("candidate_conservation", {})
    checks["candidate_conservation"] = (
        conservation.get("attack_count") == len(results)
        and conservation.get("accounted") == sum(status_counts.values())
        and conservation.get("holds") is True
        and len(results) == sum(status_counts.values())
    )

    actual_resisted = {
        result["attack_id"]
        for result in results
        if result.get("status") == "RESISTED"
    }
    actual_findings = {
        result["attack_id"]: result.get("finding_code")
        for result in results
        if result.get("status") == "FINDING"
    }
    actual_boundaries = {
        result["attack_id"]: result.get("finding_code")
        for result in results
        if result.get("status") == "BOUNDARY_CONFIRMED"
    }
    harness_errors = [
        result["attack_id"]
        for result in results
        if result.get("status") == "HARNESS_ERROR"
    ]
    checks["expected_resisted_controls"] = actual_resisted == EXPECTED_RESISTED
    checks["expected_reproducible_findings"] = actual_findings == EXPECTED_FINDINGS
    checks["expected_contract_boundaries"] = actual_boundaries == EXPECTED_BOUNDARIES
    checks["no_harness_errors"] = not harness_errors

    expected_finding_catalog = [
        {
            "attack_id": result["attack_id"],
            "finding_code": result["finding_code"],
            "severity": result["severity"],
            "security_property": result["security_property"],
        }
        for result in results
        if result.get("status") in {"FINDING", "BOUNDARY_CONFIRMED"}
    ]
    checks["finding_catalog_exact"] = findings == expected_finding_catalog

    results_text = results_path.read_text(encoding="utf-8")
    ledger_text = ledger_path.read_text(encoding="utf-8")
    findings_text = findings_path.read_text(encoding="utf-8")
    checks["results_file_binding"] = manifest.get("attack_results_sha256") == sha256_text(results_text)
    checks["ledger_file_binding"] = manifest.get("attack_ledger_sha256") == sha256_text(ledger_text)
    checks["finding_catalog_binding"] = manifest.get("finding_catalog_sha256") == sha256_text(findings_text)
    checks["final_ledger_hash"] = manifest.get("final_ledger_hash") == previous

    target_file = repository_root / TARGET_PATH
    target_exists = target_file.is_file()
    checks["target_router_present"] = target_exists
    target_hash = sha256_bytes(target_file.read_bytes()) if target_exists else None
    target = manifest.get("target", {})
    checks["target_path_binding"] = target.get("path") == TARGET_PATH
    checks["target_source_binding"] = target_hash is not None and target.get("source_sha256") == target_hash
    checks["target_declared_unmodified"] = target.get("modified_by_gauntlet") is False

    replay_digest = sha256_text(
        canonical_json(
            {
                "result_hashes": [result["result_sha256"] for result in results],
                "final_ledger_hash": previous,
                "status_counts": status_counts,
                "target_source_sha256": target_hash,
            }
        )
    )
    checks["replay_digest"] = manifest.get("replay_digest_sha256") == replay_digest
    checks["safety_boundary"] = manifest.get("safety_boundary") == EXPECTED_SAFETY
    checks["sim3_unchanged"] = manifest.get("sim3_effect") == "NONE_EXTERNAL_AUTHOR_REQUIREMENT_UNCHANGED"

    expected_terminal = (
        "JANUS_113.8_AGENT_GAUNTLET_0_INCOMPLETE"
        if harness_errors
        else "JANUS_113.8_AGENT_GAUNTLET_0_COMPLETED_WITH_FINDINGS"
        if actual_findings
        else "JANUS_113.8_AGENT_GAUNTLET_0_COMPLETED_NO_FINDINGS"
    )
    checks["manifest_terminal"] = manifest.get("terminal") == expected_terminal

    for name, passed in checks.items():
        if not passed:
            errors.append(f"check failed: {name}")

    verified = all(checks.values()) and not errors
    return {
        "schema": "janus.genesis.agent_gauntlet0.verification_report.v1",
        "verified": verified,
        "terminal": expected_terminal if verified else "JANUS_113.8_AGENT_GAUNTLET_0_REPLAY_FAILED",
        "attack_count": len(results),
        "status_counts": status_counts,
        "replay_digest_sha256": replay_digest,
        "final_ledger_hash": previous,
        "checks": checks,
        "errors": errors,
        "claim_boundary": {
            "internal_adaptive_red_team": True,
            "organizational_independence": False,
            "sim3_external_author_requirement_satisfied": False,
            "router_patched_by_this_proofpack": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proofpack", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        report = verify_proofpack(args.proofpack, args.repository_root)
    except Exception as exc:
        report = {
            "schema": "janus.genesis.agent_gauntlet0.verification_report.v1",
            "verified": False,
            "terminal": "JANUS_113.8_AGENT_GAUNTLET_0_REPLAY_FAILED",
            "checks": {},
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report.get("verified") is True else 1


if __name__ == "__main__":
    sys.exit(main())
