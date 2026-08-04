#!/usr/bin/env python3
"""Validate the shape and cryptographic ceremony of a JANUS 113.8 SIM-3 submission.

This validator is intentionally not an external verifier. It checks frozen
protocol bindings, chronology, file digests, commitment reconstruction,
metrics, and safety declarations. It does not decide the scientific or
algorithmic correctness of the external verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROTOCOL_ID = "JANUS-113.8-SIM-3-EXTERNAL-AUTHOR-VERIFIER-PROTOCOL"
SUBMISSION_SCHEMA = "janus.genesis.sim3.external_submission.v1"
ATTESTATION_SCHEMA = "janus.genesis.sim3.author_attestation.v1"
DOMAIN_SEPARATOR = "JANUS_SIM3_CHALLENGE_V1\n"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")

REQUIRED_SUBMISSION_KEYS = {
    "schema",
    "protocol",
    "external_author",
    "external_repository",
    "chronology",
    "commitments",
    "router_freeze",
    "challenge",
    "router_outputs",
    "external_verification",
    "neutral_replay",
    "metrics",
    "safety_boundary",
    "requested_terminal",
}

REQUIRED_ATTESTATION_KEYS = {
    "schema",
    "protocol_id",
    "author",
    "external_repository",
    "development_window",
    "genesis_relationship",
    "implementation",
    "reuse_disclosure",
    "conflicts_of_interest",
    "public_archival_and_replay_authorized",
    "attestation_text",
    "attestation_sha256",
}

CHRONOLOGY_FIELDS = [
    "protocol_frozen_utc",
    "router_frozen_utc",
    "external_commitment_published_utc",
    "public_cases_revealed_utc",
    "router_outputs_frozen_utc",
    "truth_revealed_utc",
    "external_report_published_utc",
    "neutral_replay_completed_utc",
]

SAFETY_BOUNDARY = {
    "network_read": "BOUNDED_PUBLIC_HTTPS_ONLY",
    "network_write": False,
    "file_deletion": False,
    "self_modification": False,
    "external_actuation": False,
    "autonomous_background_loop": False,
    "real_syslog_ingest": False,
    "private_repository_access": False,
    "repository_secrets_available_to_external_code": False,
    "runtime_authority": "NONE",
    "consciousness_status": "NOT_CLAIMED",
}

METRIC_RULES = {
    "case_alignment": ("eq", 1.0),
    "witness_ledger_replay": ("eq", 1.0),
    "commitment_reconstruction": ("eq", 1.0),
    "exact_terminal_accuracy": ("ge", 0.99),
    "false_acceptance_rate": ("eq", 0.0),
    "false_rejection_rate": ("le", 0.01),
    "decisive_coverage": ("ge", 0.95),
    "brier_score": ("le", 0.02),
    "expected_calibration_error": ("le", 0.05),
}

FILE_DIGEST_BINDINGS = {
    "cases": ("commitments", "cases_sha256"),
    "truth": ("commitments", "truth_sha256"),
    "router_predictions": ("router_outputs", "predictions_sha256"),
    "router_ledger": ("router_outputs", "witness_ledger_sha256"),
    "router_manifest": ("router_outputs", "run_manifest_sha256"),
    "external_case_verdicts": ("external_verification", "case_verdicts_sha256"),
    "external_report": ("external_verification", "verification_report_sha256"),
    "external_replay_manifest": ("external_verification", "replay_manifest_sha256"),
    "neutral_proofpack": ("neutral_replay", "proofpack_sha256"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks timezone: {value}")
    return parsed


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def is_sha40(value: Any) -> bool:
    return isinstance(value, str) and SHA40_RE.fullmatch(value) is not None


def attestation_payload_hash(attestation: dict[str, Any]) -> str:
    unsigned = dict(attestation)
    unsigned.pop("attestation_sha256", None)
    return sha256_bytes(canonical_json(unsigned).encode("utf-8"))


def metric_passes(value: Any, operation: str, threshold: float) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    numeric = float(value)
    if not 0.0 <= numeric <= 1.0:
        return False
    if operation == "eq":
        return abs(numeric - threshold) <= 1e-12
    if operation == "ge":
        return numeric >= threshold
    if operation == "le":
        return numeric <= threshold
    raise ValueError(f"unknown metric operation: {operation}")


def validate(
    submission_path: Path,
    attestation_path: Path,
    protocol_path: Path,
    submission_schema_path: Path,
    attestation_schema_path: Path,
    sim2_report_path: Path,
    salt_path: Path | None,
    bound_files: dict[str, Path | None],
) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, bool] = {}

    submission = load_json(submission_path)
    attestation = load_json(attestation_path)
    protocol = load_json(protocol_path)

    checks["submission_is_object"] = isinstance(submission, dict)
    checks["attestation_is_object"] = isinstance(attestation, dict)
    checks["protocol_is_object"] = isinstance(protocol, dict)
    if not all(checks.values()):
        errors.append("submission, attestation, and protocol must be JSON objects")
        return {"valid": False, "checks": checks, "errors": errors}

    checks["submission_exact_top_level_keys"] = set(submission) == REQUIRED_SUBMISSION_KEYS
    checks["attestation_exact_top_level_keys"] = set(attestation) == REQUIRED_ATTESTATION_KEYS
    if not checks["submission_exact_top_level_keys"]:
        errors.append("submission top-level keys do not match the frozen contract")
    if not checks["attestation_exact_top_level_keys"]:
        errors.append("attestation top-level keys do not match the frozen contract")

    checks["submission_schema_id"] = submission.get("schema") == SUBMISSION_SCHEMA
    checks["attestation_schema_id"] = attestation.get("schema") == ATTESTATION_SCHEMA
    checks["protocol_id"] = protocol.get("protocol_id") == PROTOCOL_ID
    checks["submission_protocol_id"] = submission.get("protocol", {}).get("protocol_id") == PROTOCOL_ID
    checks["attestation_protocol_id"] = attestation.get("protocol_id") == PROTOCOL_ID

    protocol_bindings = submission.get("protocol", {})
    local_bindings = {
        "protocol_json_sha256": sha256_file(protocol_path),
        "submission_schema_sha256": sha256_file(submission_schema_path),
        "author_attestation_schema_sha256": sha256_file(attestation_schema_path),
        "sim2_admission_report_sha256": sha256_file(sim2_report_path),
    }
    for field, actual in local_bindings.items():
        key = f"binding_{field}"
        checks[key] = protocol_bindings.get(field) == actual
        if not checks[key]:
            errors.append(f"protocol binding mismatch for {field}")

    checks["protocol_commit_sha"] = is_sha40(protocol_bindings.get("protocol_commit_sha"))
    checks["router_commit_sha"] = is_sha40(submission.get("router_freeze", {}).get("commit_sha"))
    checks["external_commit_sha"] = is_sha40(submission.get("external_repository", {}).get("commit_sha"))

    author_login = submission.get("external_author", {}).get("github_login")
    repo_owner = submission.get("external_repository", {}).get("owner_login")
    repo_name = submission.get("external_repository", {}).get("full_name", "")
    checks["external_author_not_hawkar"] = isinstance(author_login, str) and author_login != "Hawkar-usls"
    checks["external_owner_not_hawkar"] = isinstance(repo_owner, str) and repo_owner != "Hawkar-usls"
    checks["external_repo_not_hawkar_owned"] = isinstance(repo_name, str) and not repo_name.startswith("Hawkar-usls/")
    checks["submission_author_matches_attestation"] = author_login == attestation.get("author", {}).get("github_login")
    checks["submission_repo_matches_attestation"] = repo_name == attestation.get("external_repository", {}).get("full_name")

    allowed_permissions = {"none", "read", "triage"}
    submitted_permission = submission.get("external_author", {}).get("genesis_permission_during_development")
    attested_permission = attestation.get("genesis_relationship", {}).get("repository_permission_during_development")
    checks["allowed_genesis_permission"] = submitted_permission in allowed_permissions and attested_permission in allowed_permissions
    checks["permission_consistent"] = submitted_permission == attested_permission

    reuse = attestation.get("reuse_disclosure", {})
    external_verification = submission.get("external_verification", {})
    checks["no_genesis_import"] = reuse.get("genesis_verifier_imported") is False and external_verification.get("imports_genesis_verifier") is False
    checks["no_genesis_execution"] = reuse.get("genesis_verifier_executed") is False and external_verification.get("executes_genesis_verifier") is False
    checks["no_line_translation"] = reuse.get("line_for_line_translation") is False and external_verification.get("line_for_line_translation") is False
    checks["public_replay_authorized"] = attestation.get("public_archival_and_replay_authorized") is True

    expected_attestation_hash = attestation_payload_hash(attestation)
    checks["attestation_internal_hash"] = attestation.get("attestation_sha256") == expected_attestation_hash
    checks["submission_attestation_hash"] = submission.get("external_author", {}).get("attestation_sha256") == expected_attestation_hash
    if not checks["attestation_internal_hash"] or not checks["submission_attestation_hash"]:
        errors.append("author attestation canonical hash mismatch")

    chronology = submission.get("chronology", {})
    chronology_values: list[datetime] = []
    chronology_ok = True
    for field in CHRONOLOGY_FIELDS:
        try:
            chronology_values.append(parse_utc(chronology[field]))
        except (KeyError, ValueError) as exc:
            chronology_ok = False
            errors.append(f"invalid chronology field {field}: {exc}")
    checks["chronology_parse"] = chronology_ok
    checks["chronology_strict_order"] = chronology_ok and all(
        earlier < later for earlier, later in zip(chronology_values, chronology_values[1:])
    )
    if chronology_ok and not checks["chronology_strict_order"]:
        errors.append("ceremony timestamps are not in strict phase order")

    challenge = submission.get("challenge", {})
    challenge_rules = {
        "new_public_sources": isinstance(challenge.get("new_public_sources"), int) and challenge.get("new_public_sources") >= 5,
        "independent_repository_owners": isinstance(challenge.get("independent_repository_owners"), int) and challenge.get("independent_repository_owners") >= 3,
        "case_count": isinstance(challenge.get("case_count"), int) and challenge.get("case_count") >= 100,
        "class_count": isinstance(challenge.get("class_count"), int) and challenge.get("class_count") >= 10,
        "minimum_cases_per_class": isinstance(challenge.get("minimum_cases_per_class"), int) and challenge.get("minimum_cases_per_class") >= 5,
        "all_source_refs_are_full_commit_shas": challenge.get("all_source_refs_are_full_commit_shas") is True,
        "contains_honest_open_class": challenge.get("contains_honest_open_class") is True,
        "router_input_contains_gold_labels": challenge.get("router_input_contains_gold_labels") is False,
        "reuses_exact_sim2_source_objects": challenge.get("reuses_exact_sim2_source_objects") is False,
    }
    for field, passed in challenge_rules.items():
        checks[f"challenge_{field}"] = passed
        if not passed:
            errors.append(f"challenge rule failed: {field}")

    checks["router_not_modified_after_reveal"] = submission.get("router_freeze", {}).get("modified_after_case_reveal") is False
    checks["commitment_declared_reconstructed"] = submission.get("commitments", {}).get("commitment_reconstructed") is True
    checks["neutral_report_reproduced"] = submission.get("neutral_replay", {}).get("report_reproduced") is True
    checks["neutral_no_secrets"] = submission.get("neutral_replay", {}).get("repository_secrets_available") is False
    checks["neutral_no_network_write"] = submission.get("neutral_replay", {}).get("network_write_allowed") is False
    checks["neutral_bounded"] = all(
        submission.get("neutral_replay", {}).get(field) is True
        for field in ("bounded_timeout", "bounded_memory", "bounded_process_count")
    )

    checks["safety_boundary_exact"] = submission.get("safety_boundary") == SAFETY_BOUNDARY
    if not checks["safety_boundary_exact"]:
        errors.append("safety boundary differs from the frozen contract")

    metrics = submission.get("metrics", {})
    for metric, (operation, threshold) in METRIC_RULES.items():
        passed = metric_passes(metrics.get(metric), operation, threshold)
        checks[f"metric_{metric}"] = passed
        if not passed:
            errors.append(f"metric below contract: {metric}")

    requested_terminal = submission.get("requested_terminal")
    checks["requested_terminal_known"] = requested_terminal in {
        "JANUS_113.8_SIM_3_PROVISIONAL_EXTERNAL_REPLAY",
        "JANUS_113.8_SIM_3_ADMITTED",
    }
    if requested_terminal == "JANUS_113.8_SIM_3_ADMITTED":
        primary_language = str(submission.get("external_repository", {}).get("primary_language", "")).strip().lower()
        checks["full_admission_language_diversity_or_external_pair"] = primary_language != "python"
        if primary_language == "python":
            errors.append(
                "this single-submission validator grants full-admission eligibility only to a non-Python external implementation; "
                "two-Python-author admission requires a combined multi-submission review"
            )
    else:
        checks["full_admission_language_diversity_or_external_pair"] = True

    for section, field in (
        ("commitments", "cases_sha256"),
        ("commitments", "truth_sha256"),
        ("commitments", "challenge_salt_sha256"),
        ("commitments", "challenge_commitment_sha256"),
        ("router_outputs", "predictions_sha256"),
        ("router_outputs", "witness_ledger_sha256"),
        ("router_outputs", "run_manifest_sha256"),
        ("router_outputs", "final_ledger_hash"),
        ("external_verification", "case_verdicts_sha256"),
        ("external_verification", "verification_report_sha256"),
        ("external_verification", "replay_manifest_sha256"),
        ("neutral_replay", "proofpack_sha256"),
        ("external_repository", "release_archive_sha256"),
    ):
        key = f"sha256_{section}_{field}"
        checks[key] = is_sha256(submission.get(section, {}).get(field))

    for label, path in bound_files.items():
        if path is None:
            continue
        section, field = FILE_DIGEST_BINDINGS[label]
        expected = submission.get(section, {}).get(field)
        actual = sha256_file(path)
        passed = expected == actual
        checks[f"file_digest_{label}"] = passed
        if not passed:
            errors.append(f"file digest mismatch for {label}")

    if salt_path is not None:
        salt = salt_path.read_bytes()
        salt_hash = sha256_bytes(salt)
        cases_path = bound_files.get("cases")
        truth_path = bound_files.get("truth")
        if cases_path is None or truth_path is None:
            checks["commitment_inputs_complete"] = False
            errors.append("--salt requires --cases and --truth")
        else:
            checks["commitment_inputs_complete"] = True
            cases_hash = sha256_file(cases_path)
            truth_hash = sha256_file(truth_path)
            protocol_hash = sha256_file(protocol_path)
            external_commit = submission.get("external_repository", {}).get("commit_sha", "")
            material = (
                DOMAIN_SEPARATOR
                + salt.hex()
                + "\n"
                + cases_hash
                + "\n"
                + truth_hash
                + "\n"
                + external_commit
                + "\n"
                + protocol_hash
            ).encode("utf-8")
            commitment = sha256_bytes(material)
            checks["salt_sha256"] = submission.get("commitments", {}).get("challenge_salt_sha256") == salt_hash
            checks["commitment_reconstruction"] = submission.get("commitments", {}).get("challenge_commitment_sha256") == commitment
            if not checks["salt_sha256"]:
                errors.append("challenge salt digest mismatch")
            if not checks["commitment_reconstruction"]:
                errors.append("challenge commitment reconstruction failed")
    else:
        checks["commitment_inputs_complete"] = False
        checks["commitment_reconstruction"] = False
        errors.append("challenge salt and bound cases/truth are required for final validation")

    for name, passed in checks.items():
        if not passed and name not in {"commitment_inputs_complete", "commitment_reconstruction"}:
            if not any(name in message for message in errors):
                errors.append(f"check failed: {name}")

    valid = all(checks.values()) and not errors
    return {
        "schema": "janus.genesis.sim3.format_validation_report.v1",
        "validator_scope": "format, binding, chronology, commitment, metric, and safety validation only",
        "valid": valid,
        "requested_terminal": submission.get("requested_terminal"),
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path("protocol/janus_113_8_sim3_protocol.json"))
    parser.add_argument("--submission-schema", type=Path, default=Path("schemas/janus_113_8_sim3_submission.schema.json"))
    parser.add_argument("--attestation-schema", type=Path, default=Path("schemas/janus_113_8_sim3_author_attestation.schema.json"))
    parser.add_argument("--sim2-report", type=Path, default=Path("reports/JANUS_113_8_SIM_2_ADMISSION_REPORT.json"))
    parser.add_argument("--salt", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--router-predictions", type=Path)
    parser.add_argument("--router-ledger", type=Path)
    parser.add_argument("--router-manifest", type=Path)
    parser.add_argument("--external-case-verdicts", type=Path)
    parser.add_argument("--external-report", type=Path)
    parser.add_argument("--external-replay-manifest", type=Path)
    parser.add_argument("--neutral-proofpack", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    bound_files = {
        "cases": args.cases,
        "truth": args.truth,
        "router_predictions": args.router_predictions,
        "router_ledger": args.router_ledger,
        "router_manifest": args.router_manifest,
        "external_case_verdicts": args.external_case_verdicts,
        "external_report": args.external_report,
        "external_replay_manifest": args.external_replay_manifest,
        "neutral_proofpack": args.neutral_proofpack,
    }

    try:
        report = validate(
            submission_path=args.submission,
            attestation_path=args.attestation,
            protocol_path=args.protocol,
            submission_schema_path=args.submission_schema,
            attestation_schema_path=args.attestation_schema,
            sim2_report_path=args.sim2_report,
            salt_path=args.salt,
            bound_files=bound_files,
        )
    except (OSError, ValueError, KeyError) as exc:
        report = {
            "schema": "janus.genesis.sim3.format_validation_report.v1",
            "validator_scope": "format, binding, chronology, commitment, metric, and safety validation only",
            "valid": False,
            "checks": {},
            "errors": [str(exc)],
        }

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report.get("valid") is True else 1


if __name__ == "__main__":
    sys.exit(main())
