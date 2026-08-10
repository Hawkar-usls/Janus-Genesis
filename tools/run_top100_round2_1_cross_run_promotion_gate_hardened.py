# -*- coding: utf-8 -*-
"""Authenticated canonical entrypoint for the Round-2.1 cross-run promotion gate.

The lower-level cross-run evaluator reconstructs exact admission reports and
rederives compact evidence.  This wrapper adds two promotion-critical trust
boundaries before that evaluator may count receipts:

1. every candidate trial key must equal the frozen CriticalFrozenSet crossed
   with the exact replay range; merely having 24 distinct keys is insufficient;
2. workflow-run and artifact identities must be authenticated against live
   GitHub Actions metadata, and repeated source identities are rejected.

A later PASS therefore cannot erase a historical FAIL, and an asserted second
"run" cannot be manufactured by relabelling the same frozen report.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from tools import run_top100_round2_1_cross_run_promotion_gate as core

EXPECTED_REPOSITORY = "Hawkar-usls/Janus_Genesis"
HARDENED_SCHEMA = "janus.genesis.top100.round2_1_cross_run_promotion_hardened_receipt.v1"


def _repo_path(declared: str) -> Path:
    path = Path(declared)
    if not declared or path.is_absolute() or ".." in path.parts:
        raise ValueError("critical reference path must be repository-relative and non-traversing")
    resolved = (core.REPOSITORY_ROOT / path).resolve()
    try:
        observed = resolved.relative_to(core.REPOSITORY_ROOT).as_posix()
    except ValueError as exc:
        raise ValueError("critical reference path escapes repository root") from exc
    if observed != declared:
        raise ValueError("critical reference path identity mismatch")
    return resolved


def load_frozen_critical_profile(config: dict[str, Any]) -> dict[str, Any]:
    evidence, _ = core.load_evidence(config)
    spec = evidence.get("experimental_spec")
    if not isinstance(spec, dict):
        raise ValueError("experimental spec missing from cross-run evidence")
    critical_decl = spec.get("critical_reference")
    inference = spec.get("inference")
    if not isinstance(critical_decl, dict) or not isinstance(inference, dict):
        raise ValueError("experimental spec missing critical/inference declarations")

    declared_path = str(critical_decl.get("path") or "")
    path = _repo_path(declared_path)
    raw = path.read_bytes()
    observed_blob = core.git_blob_sha1_bytes(raw)
    if observed_blob != critical_decl.get("git_blob_sha1"):
        raise ValueError("frozen critical reference Git blob mismatch")
    critical = json.loads(raw.decode("utf-8"))
    frozen_rows = critical.get("critical_set")
    if not isinstance(frozen_rows, list):
        raise ValueError("frozen critical_set must be a list")
    if len(frozen_rows) != int(critical_decl.get("critical_set_count", -1)):
        raise ValueError("frozen critical count disagrees with experimental spec")
    observed_hash = core.canonical_sha256(frozen_rows)
    if observed_hash != critical_decl.get("critical_set_canonical_sha256"):
        raise ValueError("frozen critical canonical hash mismatch")
    if observed_hash != critical.get("critical_set_canonical_sha256"):
        raise ValueError("frozen critical object self-hash mismatch")

    replay_count = int(inference.get("critical_replays_per_model", -1))
    if replay_count <= 0:
        raise ValueError("critical replay count must be positive")
    sample_ids = [str(row["sample_id"]) for row in frozen_rows]
    if len(set(sample_ids)) != len(sample_ids):
        raise ValueError("frozen critical_set contains duplicate sample IDs")
    expected_keys = sorted((sample_id, replay) for sample_id in sample_ids for replay in range(1, replay_count + 1))
    return {
        "path": declared_path,
        "observed_git_blob_sha1": observed_blob,
        "critical_set_canonical_sha256": observed_hash,
        "critical_sample_count": len(sample_ids),
        "replays_per_sample": replay_count,
        "expected_trial_count": len(expected_keys),
        "sample_ids": sorted(sample_ids),
        "expected_keys": expected_keys,
    }


def validate_exact_critical_trial_profiles(
    evidence: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    receipts = evidence.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ValueError("cross-run evidence receipts missing")
    expected_keys = [tuple(row) for row in profile["expected_keys"]]
    expected_set = set(expected_keys)
    if len(expected_set) != int(profile["expected_trial_count"]):
        raise ValueError("expected critical trial profile contains duplicate keys")

    verified_runs: list[int] = []
    for receipt in receipts:
        source = receipt.get("source")
        records = receipt.get("candidate_records")
        if not isinstance(source, dict) or not isinstance(records, list):
            raise ValueError("receipt missing source/candidate records")
        observed_keys = [(str(row["sample_id"]), int(row["replay"])) for row in records]
        if len(observed_keys) != len(expected_keys):
            raise ValueError("candidate record count does not equal frozen critical trial profile")
        if len(set(observed_keys)) != len(observed_keys):
            raise ValueError("candidate record profile contains duplicate sample/replay keys")
        if set(observed_keys) != expected_set:
            raise ValueError("candidate record keys do not equal frozen critical sample/replay profile")
        verified_runs.append(int(source["workflow_run_id"]))

    return {
        "status": "EXACT_FROZEN_CRITICAL_TRIAL_PROFILE_VERIFIED",
        "critical_reference_path": profile["path"],
        "critical_reference_git_blob_sha1": profile["observed_git_blob_sha1"],
        "critical_set_canonical_sha256": profile["critical_set_canonical_sha256"],
        "critical_sample_count": profile["critical_sample_count"],
        "replays_per_sample": profile["replays_per_sample"],
        "expected_trial_count": profile["expected_trial_count"],
        "receipt_count_verified": len(verified_runs),
        "workflow_run_ids": verified_runs,
        "candidate_key_set_equals_frozen_profile": True,
    }


def _github_get(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "janus-genesis-cross-run-promotion-gate",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"GitHub Actions metadata lookup failed: {exc}") from exc


def fetch_live_github_source_metadata(
    config: dict[str, Any],
    *,
    repository: str,
    token: str,
) -> dict[str, Any]:
    if repository != EXPECTED_REPOSITORY:
        raise ValueError(f"unexpected GitHub repository: {repository!r}")
    if not token:
        raise ValueError("GITHUB_TOKEN is required for authoritative source authentication")
    source_configs = config.get("source_reports")
    if not isinstance(source_configs, list) or not source_configs:
        raise ValueError("source_reports missing from cross-run config")

    rows: list[dict[str, Any]] = []
    api = f"https://api.github.com/repos/{repository}"
    for source in source_configs:
        run_id = int(source["workflow_run_id"])
        artifact_id = int(source["artifact_id"])
        run = _github_get(f"{api}/actions/runs/{run_id}", token)
        artifact = _github_get(f"{api}/actions/artifacts/{artifact_id}", token)
        artifact_run = artifact.get("workflow_run") or {}
        rows.append({
            "workflow_run_id": int(run.get("id", -1)),
            "run_head_sha": run.get("head_sha"),
            "run_status": run.get("status"),
            "run_conclusion": run.get("conclusion"),
            "run_event": run.get("event"),
            "artifact_id": int(artifact.get("id", -1)),
            "artifact_name": artifact.get("name"),
            "artifact_digest": artifact.get("digest"),
            "artifact_expired": bool(artifact.get("expired", False)),
            "artifact_size_in_bytes": int(artifact.get("size_in_bytes", -1)),
            "artifact_workflow_run_id": int(artifact_run.get("id", -1)),
            "artifact_workflow_head_sha": artifact_run.get("head_sha"),
        })
    return {
        "schema": "janus.genesis.github_actions_source_authentication.v1",
        "repository": repository,
        "sources": rows,
        "fetched_live": True,
    }


def validate_authenticated_independence(
    config: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if metadata.get("repository") != EXPECTED_REPOSITORY:
        raise ValueError("GitHub metadata repository mismatch")
    sources = config.get("source_reports")
    live_rows = metadata.get("sources")
    if not isinstance(sources, list) or not isinstance(live_rows, list):
        raise ValueError("source/authentication rows missing")
    if len(sources) != len(live_rows):
        raise ValueError("GitHub authenticated source count mismatch")

    by_run: dict[int, dict[str, Any]] = {}
    for row in live_rows:
        run_id = int(row.get("workflow_run_id", -1))
        if run_id in by_run:
            raise ValueError("GitHub metadata contains duplicate workflow run identity")
        by_run[run_id] = row

    authenticated: list[dict[str, Any]] = []
    for source in sources:
        run_id = int(source["workflow_run_id"])
        row = by_run.get(run_id)
        if row is None:
            raise ValueError("configured workflow run is absent from authenticated GitHub metadata")
        if row.get("run_head_sha") != source.get("head_sha"):
            raise ValueError("workflow run head SHA is not authenticated by GitHub metadata")
        if row.get("run_status") != "completed" or row.get("run_conclusion") != "success":
            raise ValueError("source workflow run is not a completed success")
        if int(row.get("artifact_id", -1)) != int(source["artifact_id"]):
            raise ValueError("artifact ID is not authenticated by GitHub metadata")
        if row.get("artifact_name") != source.get("artifact_name"):
            raise ValueError("artifact name is not authenticated by GitHub metadata")
        if row.get("artifact_digest") != source.get("artifact_digest"):
            raise ValueError("artifact digest is not authenticated by GitHub metadata")
        if int(row.get("artifact_workflow_run_id", -1)) != run_id:
            raise ValueError("artifact is not bound to the configured workflow run")
        if row.get("artifact_workflow_head_sha") != source.get("head_sha"):
            raise ValueError("artifact workflow head SHA is not bound to the configured source head")
        authenticated.append({
            "workflow_run_id": run_id,
            "head_sha": source["head_sha"],
            "artifact_id": int(source["artifact_id"]),
            "artifact_digest": source["artifact_digest"],
            "artifact_expired_at_verification": bool(row.get("artifact_expired", False)),
            "github_run_conclusion": row["run_conclusion"],
            "github_metadata_authenticated": True,
        })

    identity_sets = {
        "workflow_run_id": [int(row["workflow_run_id"]) for row in sources],
        "artifact_id": [int(row["artifact_id"]) for row in sources],
        "artifact_digest": [str(row["artifact_digest"]) for row in sources],
        "report_json_sha256": [str(row["report_json_sha256"]) for row in sources],
        "report_raw_git_blob_sha1": [str(row["report_raw_git_blob_sha1"]) for row in sources],
        "encoded_git_blob_sha1": [str(row["encoded_git_blob_sha1"]) for row in sources],
    }
    for label, values in identity_sets.items():
        if len(set(values)) != len(values):
            raise ValueError(f"independent source receipts reuse {label}")

    return {
        "status": "GITHUB_ACTIONS_SOURCE_IDENTITIES_AUTHENTICATED",
        "repository": EXPECTED_REPOSITORY,
        "source_count": len(authenticated),
        "sources": authenticated,
        "distinct_workflow_run_ids": True,
        "distinct_artifact_ids": True,
        "distinct_artifact_digests": True,
        "distinct_raw_report_sha256": True,
        "distinct_raw_report_git_blobs": True,
        "distinct_encoded_git_blobs": True,
        "independence_counting_uses_authenticated_metadata": True,
    }


def evaluate_hardened(
    config: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    evidence, _ = core.load_evidence(config)
    profile = load_frozen_critical_profile(config)
    trial_verification = validate_exact_critical_trial_profiles(evidence, profile)
    source_auth = validate_authenticated_independence(config, metadata)
    receipt = core.evaluate(config)
    receipt["schema"] = HARDENED_SCHEMA
    receipt["canonical_entrypoint"] = "tools.run_top100_round2_1_cross_run_promotion_gate_hardened"
    receipt["critical_trial_profile_verification"] = trial_verification
    receipt["github_source_authentication"] = source_auth
    receipt["independence_authenticated_against_github_actions"] = True
    receipt["promotion_preconditions"] = {
        "exact_frozen_critical_key_set": True,
        "exact_source_report_rederivation": bool(receipt.get("compact_evidence_rederived_from_exact_source_reports")),
        "github_actions_run_artifact_authentication": True,
        "distinct_source_identities": True,
        "historical_negative_veto": True,
    }
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--github-metadata", type=Path)
    parser.add_argument("--github-repository", default=os.environ.get("GITHUB_REPOSITORY", EXPECTED_REPOSITORY))
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    config_path = args.config if args.config.is_absolute() else core.REPOSITORY_ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if args.github_metadata:
        metadata_path = args.github_metadata if args.github_metadata.is_absolute() else core.REPOSITORY_ROOT / args.github_metadata
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        metadata = fetch_live_github_source_metadata(
            config,
            repository=str(args.github_repository),
            token=os.environ.get("GITHUB_TOKEN", ""),
        )
    receipt = evaluate_hardened(config, metadata)
    print(json.dumps(
        receipt,
        ensure_ascii=False,
        sort_keys=args.pretty,
        indent=2 if args.pretty else None,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())