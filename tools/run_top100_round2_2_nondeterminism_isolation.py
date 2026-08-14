# -*- coding: utf-8 -*-
"""Round-2.2 nondeterminism isolation for the frozen eight-sample critical set.

This is a diagnostic experiment, not a new admission rule. It preserves the
Round-2.1 CriticalFrozenSet exactly and compares the same Q8_0 / FP16 model
identities under controlled within-run loading regimes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools import run_top100_round1_stratified as r1
from tools import run_top100_round2_1_capability_admission as admission
from tools import run_top100_round2_1_capability_admission_hardened as hardened

CONFIG_SCHEMA = "janus.genesis.round2_2_nondeterminism_isolation.v1"
REPORT_SCHEMA = "janus.genesis.top100.round2_2_nondeterminism_isolation_report.v1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_RETRY_MARKERS = admission._RETRY_MARKERS


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _canonical_sha256(value: Any) -> str:
    return r1.canonical_sha256(value)


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"repository-relative non-traversing path required: {value!r}")
    resolved = (REPOSITORY_ROOT / path).resolve()
    resolved.relative_to(REPOSITORY_ROOT)
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _model_names_from_ps(value: dict[str, Any]) -> list[str]:
    rows = value.get("models")
    if not isinstance(rows, list):
        return []
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("model")
        if isinstance(name, str) and name:
            names.append(name)
    return sorted(set(names))


def _running_models(endpoint: str) -> list[str]:
    return _model_names_from_ps(r1._http_json(endpoint.rstrip("/") + "/api/ps", timeout=20.0))


def _model_is_loaded(endpoint: str, tag: str) -> bool:
    return tag in _running_models(endpoint)


def _stop_model(endpoint: str, tag: str, *, timeout: float = 20.0) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        ["ollama", "stop", tag],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ollama stop failed for {tag}: rc={proc.returncode} stderr={proc.stderr[:500]}"
        )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _model_is_loaded(endpoint, tag):
            return {
                "tag": tag,
                "stopped": True,
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
                "stdout_sha256": _sha256_text(proc.stdout),
                "stderr_sha256": _sha256_text(proc.stderr),
            }
        time.sleep(0.1)
    raise RuntimeError(f"model remained loaded after ollama stop: {tag}")


def _chat_payload(
    tag: str,
    messages: list[dict[str, str]],
    *,
    seed: int,
    temperature: float,
    num_predict: int,
) -> dict[str, Any]:
    return {
        "model": tag,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "seed": seed,
            "num_predict": num_predict,
        },
    }


def _chat_with_metadata(
    endpoint: str,
    payload: dict[str, Any],
    *,
    timeout: float,
    attempts: int,
) -> tuple[str, dict[str, Any], int]:
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            response = r1._http_json(
                endpoint.rstrip("/") + "/api/chat",
                payload=payload,
                timeout=timeout,
            )
            message = response.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise RuntimeError("Ollama response lacks message.content")
            metadata = {
                key: response.get(key)
                for key in (
                    "created_at",
                    "done",
                    "done_reason",
                    "total_duration",
                    "load_duration",
                    "prompt_eval_count",
                    "prompt_eval_duration",
                    "eval_count",
                    "eval_duration",
                )
                if key in response
            }
            return message["content"], metadata, attempt
        except RuntimeError as exc:
            text = str(exc)
            if not any(marker.lower() in text.lower() for marker in _RETRY_MARKERS):
                raise
            failures.append(text)
            print(
                f"ROUND2_2_BACKEND_RETRY attempt={attempt}/{attempts} error={text[:300]}",
                file=sys.stderr,
                flush=True,
            )
            if attempt < attempts:
                time.sleep(float(attempt))
    raise RuntimeError("backend failed after bounded retries: " + " | ".join(failures[-2:]))


def _model_receipt(endpoint: str, spec: dict[str, Any]) -> dict[str, Any]:
    provider = r1.OllamaBenchmarkProvider(endpoint, spec["tag"])
    digest = provider.model_digest()
    if digest != spec["expected_digest"]:
        raise RuntimeError(
            f"model digest mismatch for {spec['id']}: {digest!r} != {spec['expected_digest']!r}"
        )
    rows = admission._tags_by_name(endpoint)
    row = rows.get(spec["tag"])
    if not row:
        raise RuntimeError(f"model tag missing from /api/tags: {spec['tag']}")
    size = row.get("size")
    if not isinstance(size, int) or size <= 0:
        raise RuntimeError(f"invalid model size for {spec['tag']}: {size!r}")
    return {
        "id": spec["id"],
        "tag": spec["tag"],
        "digest": digest,
        "size_bytes": size,
    }


def _environment_fingerprint(endpoint: str) -> dict[str, Any]:
    try:
        lscpu = subprocess.check_output(["lscpu", "-J"], text=True, stderr=subprocess.STDOUT)
    except Exception as exc:
        lscpu = f"UNAVAILABLE:{type(exc).__name__}:{exc}"
    try:
        cpuinfo = Path("/proc/cpuinfo").read_bytes()
    except OSError:
        cpuinfo = b""
    try:
        os_release = Path("/etc/os-release").read_bytes()
    except OSError:
        os_release = b""
    material = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "kernel": platform.release(),
        "lscpu_sha256": _sha256_text(lscpu),
        "proc_cpuinfo_sha256": _sha256_bytes(cpuinfo),
        "os_release_sha256": _sha256_bytes(os_release),
        "ollama_version": r1.OllamaBenchmarkProvider(endpoint, "_unused_").version(),
        "OLLAMA_NUM_PARALLEL": os.environ.get("OLLAMA_NUM_PARALLEL"),
        "OLLAMA_MAX_LOADED_MODELS": os.environ.get("OLLAMA_MAX_LOADED_MODELS"),
        "RUNNER_OS": os.environ.get("RUNNER_OS"),
        "RUNNER_ARCH": os.environ.get("RUNNER_ARCH"),
        "ImageOS": os.environ.get("ImageOS"),
    }
    return {**material, "environment_fingerprint_sha256": _canonical_sha256(material)}


def _validate_frozen_lineage(
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError("isolation config schema mismatch")

    parent_path = _repo_path(config["parent_admission_config"]["path"])
    critical_path = _repo_path(config["critical_reference"]["path"])
    pack_path = _repo_path(config["round1_pack"]["path"])

    parent_bytes = parent_path.read_bytes()
    critical_bytes = critical_path.read_bytes()
    pack_bytes = pack_path.read_bytes()

    if hardened.git_blob_sha1_bytes(parent_bytes) != config["parent_admission_config"]["git_blob_sha1"]:
        raise ValueError("parent admission config Git blob mismatch")
    if hardened.git_blob_sha1_bytes(critical_bytes) != config["critical_reference"]["git_blob_sha1"]:
        raise ValueError("critical reference Git blob mismatch")
    if hardened.git_blob_sha1_bytes(pack_bytes) != config["round1_pack"]["git_blob_sha1"]:
        raise ValueError("Round-1 pack Git blob mismatch")

    parent = json.loads(parent_bytes.decode("utf-8"))
    critical = json.loads(critical_bytes.decode("utf-8"))
    pack = json.loads(pack_bytes.decode("utf-8"))

    if parent.get("schema") != admission.CONFIG_SCHEMA:
        raise ValueError("parent admission config schema mismatch")
    if parent.get("critical_set_canonical_sha256") != config["critical_set_canonical_sha256"]:
        raise ValueError("isolation config changed the parent critical-set hash")
    if critical.get("critical_set_canonical_sha256") != config["critical_set_canonical_sha256"]:
        raise ValueError("critical reference hash mismatch")
    if int(critical.get("critical_set_count", -1)) != 8:
        raise ValueError("exactly eight frozen critical samples are required")

    errors = r1.validate_pack(pack)
    if errors:
        raise ValueError("invalid frozen Round-1 pack: " + "; ".join(errors))

    source_path = hardened._source_path_from_config(parent)
    source_encoded_bytes = source_path.read_bytes()
    provenance = hardened.validate_provenance(
        parent,
        critical,
        config_path=parent_path,
        critical_path=critical_path,
        pack_path=pack_path,
        source_path=source_path,
        config_bytes=parent_bytes,
        critical_bytes=critical_bytes,
        pack_bytes=pack_bytes,
        source_encoded_bytes=source_encoded_bytes,
    )
    round2_report, source_identity = hardened._decode_round2_source_report(
        parent, critical, source_encoded_bytes
    )
    derivation = hardened.validate_critical_derivation(parent, critical, round2_report)

    actual_ids = [row["sample_id"] for row in critical["critical_set"]]
    if actual_ids != config["critical_sample_ids"]:
        raise ValueError("critical sample order/membership differs from frozen isolation config")
    focus = config["focused_diagnostic_sample_ids"]
    if not focus or any(sid not in actual_ids for sid in focus):
        raise ValueError("focused diagnostic samples must be a non-empty subset of CriticalFrozenSet")

    provenance["round2_source_identity"] = source_identity
    provenance["critical_set_derivation"] = derivation
    return parent, critical, pack, provenance


def build_schedule(config: dict[str, Any], critical: dict[str, Any]) -> list[dict[str, Any]]:
    critical_ids = [row["sample_id"] for row in critical["critical_set"]]
    focus_ids = list(config["focused_diagnostic_sample_ids"])
    schedule: list[dict[str, Any]] = []
    for phase in config["phases"]:
        sample_ids = critical_ids if phase["sample_scope"] == "FULL_CRITICAL_SET" else focus_ids
        for replay in range(1, int(phase["replays"]) + 1):
            for sid in sample_ids:
                schedule.append({
                    "phase_id": phase["id"],
                    "target_model_id": phase["target_model_id"],
                    "pre_trial_action": phase["pre_trial_action"],
                    "sample_id": sid,
                    "replay": replay,
                    "primer_model_id": phase.get("primer_model_id"),
                })
    keys = [(r["phase_id"], r["target_model_id"], r["sample_id"], r["replay"]) for r in schedule]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate diagnostic trial key")
    return schedule


def _phase_assessment(records: list[dict[str, Any]], phase_id: str) -> dict[str, Any]:
    rows = [row for row in records if row["phase_id"] == phase_id and row["record_role"] == "TARGET"]
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_sample[row["sample_id"]].append(row)
    status_instability: dict[str, list[str]] = {}
    output_divergence: dict[str, dict[str, Any]] = {}
    for sid, group in sorted(by_sample.items()):
        statuses = [row["status"] for row in group]
        outputs = [row["output_sha256"] for row in group]
        if len(set(statuses)) > 1:
            status_instability[sid] = statuses
        if len(set(outputs)) > 1:
            output_divergence[sid] = {
                "unique_output_count": len(set(outputs)),
                "trial_count": len(outputs),
                "output_sha256_sequence": outputs,
            }
    counts = Counter(row["status"] for row in rows)
    return {
        "phase_id": phase_id,
        "target_record_count": len(rows),
        "pass_count": counts.get("PASS", 0),
        "nonpass_count": len(rows) - counts.get("PASS", 0),
        "status_counts": dict(sorted(counts.items())),
        "failed_sample_ids": sorted({row["sample_id"] for row in rows if row["status"] != "PASS"}),
        "within_phase_status_instability": status_instability,
        "within_phase_output_divergence": output_divergence,
        "backend_attempt_distribution": dict(sorted(Counter(row["backend_attempt"] for row in rows).items())),
    }


def _localization(assessments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def unstable(phase: str) -> set[str]:
        return set(assessments[phase]["within_phase_status_instability"])
    warm_full = unstable("Q8_WARM_FULL")
    cold_full = unstable("Q8_COLD_FULL")
    switch_full = unstable("Q8_SWITCH_FROM_FP16_FULL")
    warm_focus = unstable("Q8_WARM_FOCUS")
    cold_focus = unstable("Q8_COLD_FOCUS")
    fp16_warm = unstable("FP16_WARM_FULL")

    q8_warm_any = warm_full | warm_focus
    q8_cold_any = cold_full | cold_focus
    if q8_warm_any:
        classification = "STATUS_INSTABILITY_PERSISTS_WITHOUT_FORCED_MODEL_RELOAD"
    elif q8_cold_any and not q8_warm_any:
        classification = "STATUS_INSTABILITY_ASSOCIATED_WITH_FORCED_RELOAD_PATH_IN_THIS_RUN"
    elif switch_full and not q8_warm_any and not q8_cold_any:
        classification = "STATUS_INSTABILITY_ASSOCIATED_WITH_FP16_TO_Q8_MODEL_SWITCH_PATH_IN_THIS_RUN"
    elif fp16_warm:
        classification = "REFERENCE_AND_OR_BACKEND_STATUS_INSTABILITY_PRESENT_IN_THIS_RUN"
    else:
        classification = "NO_WITHIN_RUN_STATUS_INSTABILITY_OBSERVED_UNDER_TESTED_PHASES"

    return {
        "classification": classification,
        "causal_claimed": False,
        "q8_warm_unstable_sample_ids": sorted(q8_warm_any),
        "q8_cold_unstable_sample_ids": sorted(q8_cold_any),
        "q8_switch_unstable_sample_ids": sorted(switch_full),
        "fp16_warm_unstable_sample_ids": sorted(fp16_warm),
        "interpretation": (
            "Phase association localizes where graded status divergence is observed within one "
            "runner/Ollama process. It does not by itself prove a causal backend mechanism."
        ),
    }


def execute(
    config: dict[str, Any],
    *,
    endpoint: str,
    docker_image: str,
    timeout: float,
) -> dict[str, Any]:
    parent, critical, pack, provenance = _validate_frozen_lineage(config)

    for key, wanted in config["required_environment"].items():
        observed = os.environ.get(key)
        if observed != str(wanted):
            raise RuntimeError(f"required environment mismatch {key}: {observed!r} != {wanted!r}")

    inference = config["inference"]
    seed = int(inference["seed"])
    temperature = float(inference["temperature"])
    num_predict = int(inference["num_predict"])
    attempts = int(inference["backend_attempt_limit"])

    if (
        seed != int(parent["inference"]["seed"])
        or temperature != float(parent["inference"]["temperature"])
        or num_predict != int(parent["inference"]["num_predict"])
    ):
        raise ValueError("isolation inference settings differ from parent Round-2.1 exact spec")

    candidate_spec = config["models"]["Q8_0"]
    reference_spec = config["models"]["FP16"]
    candidate_receipt = _model_receipt(endpoint, candidate_spec)
    reference_receipt = _model_receipt(endpoint, reference_spec)

    sample_map = {row["sample_id"]: row for row in pack["samples"]}
    schedule = build_schedule(config, critical)

    records: list[dict[str, Any]] = []
    primer_records: list[dict[str, Any]] = []
    started_phases: set[str] = set()

    def one_call(
        *,
        phase_id: str,
        role: str,
        model_spec: dict[str, Any],
        sid: str,
        replay: int,
        pre_action: str,
    ) -> dict[str, Any]:
        sample = sample_map[sid]
        messages = r1._messages(sample, "RAW_PROVIDER", "")
        payload = _chat_payload(
            model_spec["tag"],
            messages,
            seed=seed,
            temperature=temperature,
            num_predict=num_predict,
        )
        stop_receipt = None
        if pre_action == "STOP_TARGET_BEFORE_EACH_TRIAL":
            stop_receipt = _stop_model(endpoint, model_spec["tag"])
        loaded_before = _running_models(endpoint)
        output, metadata, backend_attempt = _chat_with_metadata(
            endpoint, payload, timeout=timeout, attempts=attempts
        )
        loaded_after = _running_models(endpoint)
        status, detail = r1.grade_sample(sample, output, docker_image=docker_image)
        return {
            "phase_id": phase_id,
            "record_role": role,
            "model_id": model_spec["id"],
            "model_tag": model_spec["tag"],
            "sample_id": sid,
            "replay": replay,
            "status": status,
            "grader": sample["grader"],
            "grader_detail": detail,
            "effective_input_sha256": _canonical_sha256(messages),
            "request_payload_sha256": _canonical_sha256(payload),
            "output_sha256": _sha256_text(output),
            "backend_attempt": backend_attempt,
            "loaded_models_before": loaded_before,
            "loaded_models_after": loaded_after,
            "target_loaded_before": model_spec["tag"] in loaded_before,
            "target_loaded_after": model_spec["tag"] in loaded_after,
            "stop_receipt": stop_receipt,
            "ollama_response_metadata": metadata,
            "context_field_sent": False,
            "history_outside_current_messages_sent": False,
        }

    for trial in schedule:
        phase_id = trial["phase_id"]
        if phase_id not in started_phases:
            for spec in (candidate_spec, reference_spec):
                if _model_is_loaded(endpoint, spec["tag"]):
                    _stop_model(endpoint, spec["tag"])
            started_phases.add(phase_id)

        primer_id = trial.get("primer_model_id")
        if primer_id:
            primer_spec = config["models"][primer_id]
            primer = one_call(
                phase_id=phase_id,
                role="PRIMER",
                model_spec=primer_spec,
                sid=trial["sample_id"],
                replay=trial["replay"],
                pre_action="NONE",
            )
            primer_records.append(primer)
            if candidate_spec["tag"] in primer["loaded_models_after"]:
                raise RuntimeError("Q8_0 remained loaded after FP16 primer under max-loaded-models=1")

        record = one_call(
            phase_id=phase_id,
            role="TARGET",
            model_spec=config["models"][trial["target_model_id"]],
            sid=trial["sample_id"],
            replay=trial["replay"],
            pre_action=trial["pre_trial_action"],
        )
        records.append(record)

    assessments = {
        phase["id"]: _phase_assessment(records, phase["id"])
        for phase in config["phases"]
    }
    localization = _localization(assessments)
    target_attempts = Counter(row["backend_attempt"] for row in records)
    primer_attempts = Counter(row["backend_attempt"] for row in primer_records)

    return {
        "schema": REPORT_SCHEMA,
        "campaign": config["campaign"],
        "parent_round2_1": {
            "config_path": config["parent_admission_config"]["path"],
            "config_git_blob_sha1": config["parent_admission_config"]["git_blob_sha1"],
            "experimental_spec_fingerprint_sha256": config["parent_experimental_spec_fingerprint_sha256"],
            "historical_cross_run_receipts_preserved": True,
            "historical_results_mutated": False,
        },
        "frozen_lineage": {
            "critical_set_count": len(critical["critical_set"]),
            "critical_set_canonical_sha256": critical["critical_set_canonical_sha256"],
            "critical_sample_ids": [row["sample_id"] for row in critical["critical_set"]],
            "focused_diagnostic_sample_ids": config["focused_diagnostic_sample_ids"],
            "focused_subset_changes_admission_membership": False,
            "provenance_verification": provenance,
        },
        "models": {"Q8_0": candidate_receipt, "FP16": reference_receipt},
        "inference": inference,
        "required_environment": config["required_environment"],
        "environment": _environment_fingerprint(endpoint),
        "phase_count": len(config["phases"]),
        "phases": config["phases"],
        "target_record_count": len(records),
        "primer_record_count": len(primer_records),
        "actual_inference_call_count": len(records) + len(primer_records),
        "target_backend_attempt_distribution": dict(sorted(target_attempts.items())),
        "primer_backend_attempt_distribution": dict(sorted(primer_attempts.items())),
        "assessments": assessments,
        "localization": localization,
        "records": records,
        "primer_records": primer_records,
        "admission_decision_changed_by_this_diagnostic": False,
        "authoritative_runtime_changed_by_this_diagnostic": False,
        "official_benchmark_accuracy_claimed": False,
        "bitwise_determinism_claimed": False,
        "causal_source_of_nondeterminism_claimed": False,
        "canonical_world_state_mutated": False,
        "claim_ceiling": config["claim_ceiling"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--docker-image", default="python:3.11-alpine")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    config_path = args.config if args.config.is_absolute() else _repo_path(args.config.as_posix())
    config = _read_json(config_path)
    report = execute(config, endpoint=args.endpoint, docker_image=args.docker_image, timeout=args.timeout)
    print(json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=args.pretty,
        indent=2 if args.pretty else None,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
