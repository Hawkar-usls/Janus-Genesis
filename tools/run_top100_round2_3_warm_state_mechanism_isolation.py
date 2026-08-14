# -*- coding: utf-8 -*-
"""Round-2.3: isolate request-sequence effects inside a warm Q8_0 process."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools import run_top100_round1_stratified as r1
from tools import run_top100_round2_1_capability_admission_hardened as hardened
from tools import run_top100_round2_2_nondeterminism_isolation as r22

CONFIG_SCHEMA = "janus.genesis.round2_3_warm_state_mechanism_isolation.v1"
REPORT_SCHEMA = "janus.genesis.top100.round2_3_warm_state_mechanism_isolation_report.v1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return r1.canonical_sha256(value)


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"repository-relative non-traversing path required: {value!r}")
    resolved = (REPOSITORY_ROOT / path).resolve()
    resolved.relative_to(REPOSITORY_ROOT)
    return resolved


def _llama_server_processes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    proc_root = Path("/proc")
    if not proc_root.exists():
        return rows
    for child in proc_root.iterdir():
        if not child.name.isdigit():
            continue
        try:
            cmdline = (child / "cmdline").read_bytes()
            if b"llama-server" not in cmdline:
                continue
            stat = (child / "stat").read_text(encoding="utf-8", errors="replace")
            close = stat.rfind(")")
            if close < 0:
                continue
            rest = stat[close + 2:].split()
            start_time_ticks = int(rest[19])
            rows.append({
                "pid": int(child.name),
                "start_time_ticks": start_time_ticks,
                "cmdline_sha256": _sha256_bytes(cmdline),
            })
        except (OSError, ValueError, IndexError):
            continue
    return sorted(rows, key=lambda row: (row["pid"], row["start_time_ticks"]))


def _server_identity_set(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({f"{row['pid']}:{row['start_time_ticks']}:{row['cmdline_sha256']}" for row in rows})


def validate_config(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError("Round-2.3 config schema mismatch")

    parent_ref = config["parent_round2_2"]
    parent_path = _repo_path(parent_ref["config_path"])
    parent_bytes = parent_path.read_bytes()
    if hardened.git_blob_sha1_bytes(parent_bytes) != parent_ref["config_git_blob_sha1"]:
        raise ValueError("Round-2.2 parent config Git blob mismatch")
    parent22 = json.loads(parent_bytes.decode("utf-8"))
    if parent22.get("schema") != r22.CONFIG_SCHEMA:
        raise ValueError("Round-2.2 parent schema mismatch")

    _parent21, critical, pack, provenance = r22._validate_frozen_lineage(parent22)
    critical_ref = config["critical_reference"]
    pack_ref = config["round1_pack"]
    if critical_ref["git_blob_sha1"] != parent22["critical_reference"]["git_blob_sha1"]:
        raise ValueError("Round-2.3 changed critical reference blob")
    if pack_ref["git_blob_sha1"] != parent22["round1_pack"]["git_blob_sha1"]:
        raise ValueError("Round-2.3 changed Round-1 pack blob")
    if critical_ref["canonical_sha256"] != critical["critical_set_canonical_sha256"]:
        raise ValueError("Round-2.3 changed frozen critical-set hash")
    if int(critical_ref["count"]) != 8 or int(critical["critical_set_count"]) != 8:
        raise ValueError("Round-2.3 expects frozen critical set of eight")

    q8 = config["q8_0"]
    parent_q8 = parent22["models"]["Q8_0"]
    if q8["tag"] != parent_q8["tag"] or q8["expected_digest"] != parent_q8["expected_digest"]:
        raise ValueError("Round-2.3 changed Q8_0 identity")
    for key in ("seed", "temperature", "num_predict"):
        if config["inference"][key] != parent22["inference"][key]:
            raise ValueError(f"Round-2.3 changed inference field {key}")

    critical_ids = {row["sample_id"] for row in critical["critical_set"]}
    focal = config["focal_samples"]
    if any(sid not in critical_ids for sid in focal.values()):
        raise ValueError("all focal/separator samples must remain inside CriticalFrozenSet")

    expected = int(config["expected_accounting"]["target_record_count"])
    schedule = build_schedule(config)
    if len(schedule) != expected:
        raise ValueError(f"schedule count mismatch: {len(schedule)} != {expected}")
    return parent22, critical, pack, provenance


def build_schedule(config: dict[str, Any]) -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    ordinal = 0
    for phase in config["phases"]:
        sequence = list(phase["sequence"])
        for cycle in range(1, int(phase["cycles"]) + 1):
            for position, sid in enumerate(sequence, 1):
                ordinal += 1
                schedule.append({
                    "global_ordinal": ordinal,
                    "phase_id": phase["id"],
                    "cycle": cycle,
                    "position_in_cycle": position,
                    "sample_id": sid,
                    "stop_before_request": bool(phase["stop_before_each_request"]),
                })
    return schedule


def _sample_assessment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: (row["cycle"], row["position_in_cycle"]))
    statuses = [row["status"] for row in rows]
    outputs = [row["output_sha256"] for row in rows]
    requests = [row["request_payload_sha256"] for row in rows]
    identities = sorted({ident for row in rows for ident in row["server_identities_after"]})
    return {
        "trial_count": len(rows),
        "pass_count": sum(status == "PASS" for status in statuses),
        "status_sequence": statuses,
        "output_sha256_sequence": outputs,
        "request_payload_sha256_unique": sorted(set(requests)),
        "unique_request_payload_count": len(set(requests)),
        "unique_output_count": len(set(outputs)),
        "output_divergence": len(set(outputs)) > 1,
        "status_divergence": len(set(statuses)) > 1,
        "unique_server_process_identity_count": len(identities),
        "server_process_identities": identities,
        "sequence_sha256": _canonical_sha256([
            {
                "cycle": row["cycle"],
                "position_in_cycle": row["position_in_cycle"],
                "status": row["status"],
                "output_sha256": row["output_sha256"],
                "request_payload_sha256": row["request_payload_sha256"],
            }
            for row in rows
        ]),
    }


def _phase_assessment(records: list[dict[str, Any]], phase_id: str) -> dict[str, Any]:
    rows = [row for row in records if row["phase_id"] == phase_id]
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_sample[row["sample_id"]].append(row)
    identities = sorted({ident for row in rows for ident in row["server_identities_after"]})
    return {
        "phase_id": phase_id,
        "record_count": len(rows),
        "pass_count": sum(row["status"] == "PASS" for row in rows),
        "backend_attempt_distribution": dict(sorted(Counter(row["backend_attempt"] for row in rows).items())),
        "unique_server_process_identity_count": len(identities),
        "server_process_identities": identities,
        "sample_assessments": {
            sid: _sample_assessment(group) for sid, group in sorted(by_sample.items())
        },
    }


def _mechanism_summary(config: dict[str, Any], assessments: dict[str, Any]) -> dict[str, Any]:
    gsm = config["focal_samples"]["GSM"]
    truth = config["focal_samples"]["TRUTH"]
    gsm_alone = assessments["Q8_WARM_GSM_ALONE"]["sample_assessments"][gsm]
    truth_alone = assessments["Q8_WARM_TRUTH_ALONE"]["sample_assessments"][truth]
    pair_gt_gsm = assessments["Q8_WARM_PAIR_GSM_TRUTH"]["sample_assessments"][gsm]
    pair_tg_gsm = assessments["Q8_WARM_PAIR_TRUTH_GSM"]["sample_assessments"][gsm]
    sep_gsm = assessments["Q8_WARM_GSM_WITH_STABLE_SEPARATOR"]["sample_assessments"][gsm]
    pair_gt_truth = assessments["Q8_WARM_PAIR_GSM_TRUTH"]["sample_assessments"][truth]
    pair_tg_truth = assessments["Q8_WARM_PAIR_TRUTH_GSM"]["sample_assessments"][truth]
    sep_truth = assessments["Q8_WARM_TRUTH_WITH_STABLE_SEPARATOR"]["sample_assessments"][truth]
    cold = assessments["Q8_COLD_FOCUS_CONFIRM"]["sample_assessments"]

    identical_payload_same_process_divergence = []
    for sid, row in ((gsm, gsm_alone), (truth, truth_alone)):
        if (
            row["unique_request_payload_count"] == 1
            and row["unique_server_process_identity_count"] == 1
            and row["unique_output_count"] > 1
        ):
            identical_payload_same_process_divergence.append(sid)

    return {
        "identical_payload_same_warm_process_output_divergence_sample_ids": identical_payload_same_process_divergence,
        "identical_payload_same_warm_process_divergence_observed": bool(identical_payload_same_process_divergence),
        "gsm_order_sensitivity_observed": pair_gt_gsm["output_sha256_sequence"] != pair_tg_gsm["output_sha256_sequence"],
        "truth_order_sensitivity_observed": pair_gt_truth["output_sha256_sequence"] != pair_tg_truth["output_sha256_sequence"],
        "gsm_stable_separator_sensitivity_observed": pair_gt_gsm["output_sha256_sequence"] != sep_gsm["output_sha256_sequence"],
        "truth_stable_separator_sensitivity_observed": pair_gt_truth["output_sha256_sequence"] != sep_truth["output_sha256_sequence"],
        "cold_control_all_pass": all(
            row["pass_count"] == row["trial_count"] and row["unique_output_count"] == 1
            for row in cold.values()
        ),
        "causal_internal_mechanism_established": False,
        "interpretation": "The summary detects associations among identical-payload warm repetition, prompt order, and separator insertion. It does not name an internal causal mechanism."
    }


def execute(config: dict[str, Any], *, endpoint: str, docker_image: str, timeout: float) -> dict[str, Any]:
    _parent22, critical, pack, provenance = validate_config(config)
    for key, wanted in config["required_environment"].items():
        if os.environ.get(key) != str(wanted):
            raise RuntimeError(f"required environment mismatch {key}: {os.environ.get(key)!r} != {wanted!r}")

    q8 = config["q8_0"]
    receipt = r22._model_receipt(endpoint, q8)
    if receipt["size_bytes"] != int(q8["expected_size_bytes"]):
        raise RuntimeError("Q8_0 model size changed")

    sample_map = {row["sample_id"]: row for row in pack["samples"]}
    inference = config["inference"]
    schedule = build_schedule(config)
    records: list[dict[str, Any]] = []
    started_phases: set[str] = set()

    for trial in schedule:
        phase_id = trial["phase_id"]
        if phase_id not in started_phases:
            if r22._model_is_loaded(endpoint, q8["tag"]):
                r22._stop_model(endpoint, q8["tag"])
            started_phases.add(phase_id)

        stop_receipt = None
        if trial["stop_before_request"]:
            stop_receipt = r22._stop_model(endpoint, q8["tag"])

        sample = sample_map[trial["sample_id"]]
        messages = r1._messages(sample, "RAW_PROVIDER", "")
        payload = r22._chat_payload(
            q8["tag"],
            messages,
            seed=int(inference["seed"]),
            temperature=float(inference["temperature"]),
            num_predict=int(inference["num_predict"]),
        )
        processes_before = _llama_server_processes()
        loaded_before = r22._running_models(endpoint)
        output, metadata, backend_attempt = r22._chat_with_metadata(
            endpoint,
            payload,
            timeout=timeout,
            attempts=int(inference["backend_attempt_limit"]),
        )
        loaded_after = r22._running_models(endpoint)
        processes_after = _llama_server_processes()
        status, detail = r1.grade_sample(sample, output, docker_image=docker_image)
        records.append({
            **trial,
            "model_id": "Q8_0",
            "model_tag": q8["tag"],
            "status": status,
            "grader": sample["grader"],
            "grader_detail": detail,
            "effective_input_sha256": _canonical_sha256(messages),
            "request_payload_sha256": _canonical_sha256(payload),
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "backend_attempt": backend_attempt,
            "loaded_models_before": loaded_before,
            "loaded_models_after": loaded_after,
            "target_loaded_before": q8["tag"] in loaded_before,
            "target_loaded_after": q8["tag"] in loaded_after,
            "llama_server_processes_before": processes_before,
            "llama_server_processes_after": processes_after,
            "server_identities_before": _server_identity_set(processes_before),
            "server_identities_after": _server_identity_set(processes_after),
            "stop_receipt": stop_receipt,
            "ollama_response_metadata": metadata,
            "context_field_sent": False,
            "history_outside_current_messages_sent": False
        })

    assessments = {
        phase["id"]: _phase_assessment(records, phase["id"])
        for phase in config["phases"]
    }
    summary = _mechanism_summary(config, assessments)
    attempts = Counter(row["backend_attempt"] for row in records)
    return {
        "schema": REPORT_SCHEMA,
        "campaign": config["campaign"],
        "parent_round2_2": config["parent_round2_2"],
        "frozen_lineage": {
            "critical_set_count": critical["critical_set_count"],
            "critical_set_canonical_sha256": critical["critical_set_canonical_sha256"],
            "critical_membership_changed": False,
            "provenance_verification": provenance
        },
        "model_receipt": receipt,
        "inference": inference,
        "required_environment": config["required_environment"],
        "focal_samples": config["focal_samples"],
        "phases": config["phases"],
        "target_record_count": len(records),
        "backend_attempt_distribution": dict(sorted(attempts.items())),
        "assessments": assessments,
        "mechanism_summary": summary,
        "records": records,
        "raw_output_text_persisted": False,
        "admission_rule_changed": False,
        "promotion_rule_changed": False,
        "q8_0_promoted": False,
        "causal_internal_mechanism_claimed": False,
        "canonical_world_state_mutated": False,
        "claim_ceiling": config["claim_ceiling"]
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--docker-image", default="python:3.11-alpine")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    path = args.config if args.config.is_absolute() else _repo_path(args.config.as_posix())
    config = json.loads(path.read_text(encoding="utf-8"))
    report = execute(config, endpoint=args.endpoint, docker_image=args.docker_image, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, sort_keys=args.pretty, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
