# -*- coding: utf-8 -*-
"""Round-2.1 strict capability-preserving quantization admission gate.

The admission question is deliberately not an average-score question:

    for every x in CriticalFrozenSet and every configured replay,
    PASS_reference_frozen(x) => PASS_candidate(x)

CriticalFrozenSet membership is frozen from the prior Round-2 FP16_RAW PASS
projection. Candidate outcomes cannot add, remove, or reweight critical items.
The smallest admitted quantized representation is selected by actual Ollama
model size in bytes. If none is admitted, FP16 remains the authoritative
runtime representation for this gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from tools import run_top100_round1_stratified as r1

CONFIG_SCHEMA = "janus.genesis.round2_1_capability_preserving_quantization_admission.v1"
CRITICAL_SCHEMA = "janus.genesis.top100.round2_fp16_critical_reference.v1"
REPORT_SCHEMA = "janus.genesis.top100.round2_1_capability_admission_report.v1"

_RETRY_MARKERS = (
    "llama-server process has terminated",
    "provider connection failed",
    "HTTP 500",
    "connection reset",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chat_with_backend_retry(
    provider: r1.OllamaBenchmarkProvider,
    messages: list[dict[str, str]],
    *,
    attempts: int = 4,
) -> tuple[str, int]:
    """Retry infrastructure/backend failures only; never retry a graded FAIL."""
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            return provider.chat(messages), attempt
        except RuntimeError as exc:
            text = str(exc)
            if not any(marker.lower() in text.lower() for marker in _RETRY_MARKERS):
                raise
            failures.append(text)
            print(
                f"OLLAMA_TRANSIENT_RETRY model={provider.model} "
                f"attempt={attempt}/{attempts} error={text[:300]}",
                file=sys.stderr,
                flush=True,
            )
            if attempt < attempts:
                time.sleep(float(attempt))
    raise RuntimeError(
        "Ollama backend failed after bounded retries: " + " | ".join(failures[-2:])
    )


def _tags_by_name(endpoint: str) -> dict[str, dict[str, Any]]:
    value = r1._http_json(endpoint.rstrip("/") + "/api/tags", timeout=30.0)
    rows = value.get("models")
    if not isinstance(rows, list):
        raise RuntimeError("Ollama /api/tags did not return models list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in (row.get("name"), row.get("model")):
            if isinstance(key, str) and key:
                result[key] = row
    return result


def _validate_critical_reference(
    config: dict[str, Any],
    critical: dict[str, Any],
    pack: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError("config schema mismatch")
    if critical.get("schema") != CRITICAL_SCHEMA:
        raise ValueError("critical reference schema mismatch")
    errors = r1.validate_pack(pack)
    if errors:
        raise ValueError("invalid frozen Round-1 pack: " + "; ".join(errors))

    pack_hash = r1.canonical_sha256(pack)
    expected_pack_hash = critical["source"]["round1_pack_canonical_sha256"]
    if pack_hash != expected_pack_hash:
        raise ValueError(f"Round-1 canonical pack hash mismatch: {pack_hash} != {expected_pack_hash}")

    rows = critical.get("critical_set")
    if not isinstance(rows, list) or not rows:
        raise ValueError("critical_set must be non-empty list")
    if len(rows) != int(critical.get("critical_set_count", -1)):
        raise ValueError("critical_set_count mismatch")
    if len(rows) != int(critical.get("source_fp16_pass_count", -1)):
        raise ValueError("critical set must equal frozen FP16 PASS count")

    canonical_hash = r1.canonical_sha256(rows)
    expected_hash = str(config["critical_set_canonical_sha256"])
    if canonical_hash != expected_hash or canonical_hash != critical.get("critical_set_canonical_sha256"):
        raise ValueError("critical set canonical hash mismatch")

    sample_map = {str(row["sample_id"]): row for row in pack["samples"]}
    seen: set[str] = set()
    for ref in rows:
        sid = str(ref.get("sample_id") or "")
        if not sid or sid in seen:
            raise ValueError(f"invalid or duplicate critical sample id {sid!r}")
        seen.add(sid)
        if ref.get("reference_status") != "PASS":
            raise ValueError(f"critical sample {sid} was not frozen as PASS")
        sample = sample_map.get(sid)
        if sample is None:
            raise ValueError(f"critical sample missing from frozen pack: {sid}")
        if sample.get("benchmark") != ref.get("benchmark"):
            raise ValueError(f"benchmark mismatch for {sid}")
        if sample.get("domain") != ref.get("domain"):
            raise ValueError(f"domain mismatch for {sid}")
        if sample.get("grader") != ref.get("grader"):
            raise ValueError(f"grader mismatch for {sid}")
        messages = r1._messages(sample, "RAW_PROVIDER", "")
        effective = r1.canonical_sha256(messages)
        if effective != ref.get("effective_input_sha256"):
            raise ValueError(f"effective input changed for frozen critical sample {sid}")

    if len(rows) != 8:
        raise ValueError(f"Round-2.1 expects exactly 8 frozen FP16 PASS items, got {len(rows)}")
    return rows, sample_map


def _model_receipts(
    config: dict[str, Any],
    *,
    endpoint: str,
    timeout: float,
) -> tuple[dict[str, r1.OllamaBenchmarkProvider], dict[str, dict[str, Any]]]:
    inference = config["inference"]
    specs = [config["reference"], *config["candidates"]]
    tags = _tags_by_name(endpoint)
    providers: dict[str, r1.OllamaBenchmarkProvider] = {}
    receipts: dict[str, dict[str, Any]] = {}
    for spec in specs:
        provider = r1.OllamaBenchmarkProvider(
            endpoint,
            spec["tag"],
            seed=int(inference["seed"]),
            temperature=float(inference["temperature"]),
            timeout=timeout,
            num_predict=int(inference["num_predict"]),
        )
        digest = provider.model_digest()
        prefix = str(spec["expected_digest_prefix"])
        if not digest or not digest.startswith(prefix):
            raise RuntimeError(
                f"model digest mismatch for {spec['id']}: {digest!r} does not start with {prefix!r}"
            )
        tag_row = tags.get(spec["tag"])
        if not tag_row:
            raise RuntimeError(f"model tag missing from /api/tags: {spec['tag']}")
        size = tag_row.get("size")
        if not isinstance(size, int) or size <= 0:
            raise RuntimeError(f"invalid model size for {spec['tag']}: {size!r}")
        providers[spec["id"]] = provider
        receipts[spec["id"]] = {
            "id": spec["id"],
            "tag": spec["tag"],
            "digest": digest,
            "expected_digest_prefix": prefix,
            "size_bytes": size,
            "is_reference": spec["id"] == config["reference"]["id"],
        }
    return providers, receipts


def _run_model(
    model_id: str,
    provider: r1.OllamaBenchmarkProvider,
    critical_rows: list[dict[str, Any]],
    sample_map: dict[str, dict[str, Any]],
    *,
    replays: int,
    docker_image: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for replay in range(1, replays + 1):
        for ref in critical_rows:
            sid = ref["sample_id"]
            sample = sample_map[sid]
            messages = r1._messages(sample, "RAW_PROVIDER", "")
            print(
                f"ROUND2_1_INFERENCE model={model_id} replay={replay}/{replays} sample={sid}",
                file=sys.stderr,
                flush=True,
            )
            output, backend_attempt = _chat_with_backend_retry(provider, messages)
            status, detail = r1.grade_sample(sample, output, docker_image=docker_image)
            records.append({
                "model_id": model_id,
                "replay": replay,
                "sample_id": sid,
                "benchmark": sample["benchmark"],
                "domain": sample["domain"],
                "status": status,
                "grader": sample["grader"],
                "grader_detail": detail,
                "backend_attempt": backend_attempt,
                "effective_input_sha256": r1.canonical_sha256(messages),
                "output_sha256": _sha256_text(output),
                "frozen_reference_status": "PASS",
            })
    return records


def _assessment(
    records: list[dict[str, Any]],
    model_id: str,
    *,
    critical_count: int,
    replays: int,
) -> dict[str, Any]:
    rows = [row for row in records if row["model_id"] == model_id]
    expected_trials = critical_count * replays
    if len(rows) != expected_trials:
        raise ValueError(f"trial count mismatch for {model_id}: {len(rows)} != {expected_trials}")
    failures = [row for row in rows if row["status"] != "PASS"]
    by_sample: dict[str, list[str]] = {}
    for row in rows:
        by_sample.setdefault(row["sample_id"], []).append(row["status"])
    unstable = {
        sid: statuses for sid, statuses in sorted(by_sample.items())
        if len(set(statuses)) > 1
    }
    failed_samples = sorted({row["sample_id"] for row in failures})
    admitted = not failures
    return {
        "model_id": model_id,
        "critical_sample_count": critical_count,
        "replays": replays,
        "required_trials": expected_trials,
        "pass_trials": expected_trials - len(failures),
        "nonpass_trials": len(failures),
        "failed_sample_ids": failed_samples,
        "within_model_status_instability": unstable,
        "strict_capability_preservation": admitted,
        "admission_status": (
            "ADMITTED_CAPABILITY_PRESERVING_IN_TESTED_CRITICAL_SCOPE"
            if admitted else
            "REJECTED_CRITICAL_CAPABILITY_REGRESSION_OBSERVED"
        ),
        "failure_evidence": [
            {
                "replay": row["replay"],
                "sample_id": row["sample_id"],
                "benchmark": row["benchmark"],
                "status": row["status"],
                "grader_detail": row["grader_detail"],
            }
            for row in failures
        ],
    }


def execute(
    config: dict[str, Any],
    critical: dict[str, Any],
    pack: dict[str, Any],
    *,
    endpoint: str,
    docker_image: str,
    timeout: float,
) -> dict[str, Any]:
    critical_rows, sample_map = _validate_critical_reference(config, critical, pack)
    providers, model_receipts = _model_receipts(config, endpoint=endpoint, timeout=timeout)
    replays = int(config["inference"]["critical_replays_per_model"])
    if replays < 2:
        raise ValueError("Round-2.1 requires at least two replays")

    reference_id = config["reference"]["id"]
    candidate_ids = [row["id"] for row in config["candidates"]]
    # Execute candidates by actual bytes, not by quantization label. The reference
    # is replayed last as a stability diagnostic and never changes critical membership.
    ordered_candidates = sorted(
        candidate_ids,
        key=lambda mid: (model_receipts[mid]["size_bytes"], model_receipts[mid]["tag"]),
    )
    execution_order = [*ordered_candidates, reference_id]

    records: list[dict[str, Any]] = []
    assessments: dict[str, Any] = {}
    for model_id in execution_order:
        model_records = _run_model(
            model_id,
            providers[model_id],
            critical_rows,
            sample_map,
            replays=replays,
            docker_image=docker_image,
        )
        records.extend(model_records)
        assessments[model_id] = _assessment(
            records,
            model_id,
            critical_count=len(critical_rows),
            replays=replays,
        )

    admitted_candidates = [
        mid for mid in ordered_candidates
        if assessments[mid]["strict_capability_preservation"]
    ]
    smallest = admitted_candidates[0] if admitted_candidates else None
    if smallest is None:
        selected = reference_id
        selection_status = "NO_QUANTIZED_CANDIDATE_ADMITTED_FP16_REMAINS_AUTHORITATIVE_RUNTIME"
    else:
        selected = smallest
        selection_status = "SMALLEST_CAPABILITY_PRESERVING_QUANTIZED_REPRESENTATION_ADMITTED"

    for mid in candidate_ids:
        if assessments[mid]["strict_capability_preservation"]:
            classification = "CAPABILITY_PRESERVING_QUANTIZED_CANDIDATE_IN_TESTED_SCOPE"
        else:
            classification = "ECONOMIC_APPROXIMATION_NOT_CAPABILITY_PRESERVING_IN_TESTED_SCOPE"
        model_receipts[mid]["classification"] = classification
        model_receipts[mid]["identity_preserving_replacement_claimed"] = False
    model_receipts[reference_id]["classification"] = "AUTHORITATIVE_REFERENCE"
    model_receipts[reference_id]["identity_preserving_replacement_claimed"] = False

    ref_assessment = assessments[reference_id]
    reference_replay_stability = (
        "PASS_ALL_FROZEN_CRITICAL_TRIALS"
        if ref_assessment["strict_capability_preservation"]
        else "CURRENT_BACKEND_REPLAY_INSTABILITY_OR_REGRESSION_OBSERVED"
    )

    size_order = [
        {
            "rank": i + 1,
            "model_id": mid,
            "tag": model_receipts[mid]["tag"],
            "size_bytes": model_receipts[mid]["size_bytes"],
            "admission_status": assessments[mid]["admission_status"],
        }
        for i, mid in enumerate(ordered_candidates)
    ]

    total_expected = (len(candidate_ids) + 1) * len(critical_rows) * replays
    counts = Counter(row["status"] for row in records)
    return {
        "schema": REPORT_SCHEMA,
        "campaign": config["campaign"],
        "critical_reference": {
            "path": config["critical_reference"],
            "git_blob_sha1": config["critical_reference_git_blob_sha1"],
            "critical_set_count": len(critical_rows),
            "critical_set_canonical_sha256": r1.canonical_sha256(critical_rows),
            "membership_mutated_by_candidate_results": False,
            "source_round2_report_sha256": critical["source"]["round2_report_json_sha256"],
            "source_round2_artifact_id": critical["source"]["round2_artifact_id"],
        },
        "frozen_pack": {
            "path": config["round1_pack"],
            "git_blob_sha1": config["round1_pack_git_blob_sha1"],
            "canonical_sha256": r1.canonical_sha256(pack),
            "sample_count": len(pack["samples"]),
        },
        "inference": config["inference"],
        "ollama_version": providers[reference_id].version(),
        "model_count": len(model_receipts),
        "quantized_candidate_count": len(candidate_ids),
        "model_receipts": model_receipts,
        "candidate_size_order": size_order,
        "assessments": assessments,
        "selection": {
            "rule": "minimum actual size_bytes among quantized candidates with 24/24 critical PASS trials",
            "aggregate_score_used": False,
            "noncritical_compensation_allowed": False,
            "admitted_quantized_candidates": admitted_candidates,
            "smallest_admitted_quantized_candidate": smallest,
            "selected_runtime_representation": selected,
            "selection_status": selection_status,
            "reference_model": reference_id,
            "reference_replay_stability": reference_replay_stability,
        },
        "execution": {
            "execution_order": execution_order,
            "expected_record_count": total_expected,
            "record_count": len(records),
            "status_counts": dict(sorted(counts.items())),
            "all_records_accounted_for": len(records) == total_expected,
        },
        "records": records,
        "critical_set_average_score_used_for_admission": False,
        "official_benchmark_family_accuracy_claimed": False,
        "general_lossless_quantization_claimed": False,
        "bitwise_output_identity_claimed": False,
        "canonical_world_state_mutated": False,
        "claim_ceiling": config["claim_ceiling"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--critical-reference", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--docker-image", default="python:3.11-alpine")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text(encoding="utf-8"))
    critical = json.loads(args.critical_reference.read_text(encoding="utf-8"))
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    report = execute(
        config,
        critical,
        pack,
        endpoint=args.endpoint,
        docker_image=args.docker_image,
        timeout=args.timeout,
    )
    print(json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=args.pretty,
        indent=2 if args.pretty else None,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
