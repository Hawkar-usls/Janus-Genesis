# -*- coding: utf-8 -*-
"""Round-2 quantization and routed-boundary experiment.

Reuses the immutable Round-1 frozen sample pack.  The experiment measures:
1) FP16 -> Q8_0 -> Q4_K_M quantization non-regression on identical raw prompts.
2) Q4_K_M raw vs the old global Genesis overlay vs a routed constitutional
   boundary that stays out of pure benchmark cognition.

Wrong benchmark answers are experimental results, not harness failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools import run_top100_round1_stratified as r1

REPORT_SCHEMA = "janus.genesis.top100.round2_quantization_routing_report.v1"
CONFIG_SCHEMA = "janus.genesis.round2_quantization_routing_config.v1"
CONSTITUTIONAL_RELEVANCE = {
    "external_effect", "consent", "authority", "delegation", "remedy", "sovereign_boundary"
}


def canonical_sha256(value: Any) -> str:
    return r1.canonical_sha256(value)


def constitutional_boundary_required(sample: dict[str, Any]) -> bool:
    """Fail closed to neutral for legacy benchmark samples with no rights/effect metadata.

    A benchmark item is routed through the constitutional overlay only when its
    frozen evaluation metadata explicitly declares relevant boundary semantics.
    Prompt words alone never manufacture jurisdiction.
    """
    value = sample.get("boundary_relevance")
    if value is True:
        return True
    if isinstance(value, str):
        return value in CONSTITUTIONAL_RELEVANCE
    if isinstance(value, list):
        return bool(CONSTITUTIONAL_RELEVANCE.intersection(str(x) for x in value))
    return False


def routed_messages(sample: dict[str, Any], overlay: str) -> tuple[str, list[dict[str, str]]]:
    if constitutional_boundary_required(sample):
        return "CONSTITUTIONAL_BOUNDARY_PATH", r1._messages(
            sample, "GENESIS_BOUNDARY_OVERLAY", overlay
        )
    return "NEUTRAL_BENCHMARK_PATH", r1._messages(sample, "RAW_PROVIDER", overlay)


def _summary(records: list[dict[str, Any]], config_id: str) -> dict[str, Any]:
    rows = [x for x in records if x["config_id"] == config_id]
    counts = Counter(x["status"] for x in rows)
    scored = counts["PASS"] + counts["FAIL"]
    per_benchmark: dict[str, Any] = {}
    for name in sorted({x["benchmark"] for x in rows}):
        subset = [x for x in rows if x["benchmark"] == name]
        c = Counter(x["status"] for x in subset)
        n = c["PASS"] + c["FAIL"]
        per_benchmark[name] = {
            "samples": len(subset), "pass": c["PASS"], "fail": c["FAIL"],
            "blocked": len(subset) - n,
            "accuracy_on_scored": c["PASS"] / n if n else None,
        }
    return {
        "samples": len(rows), "pass": counts["PASS"], "fail": counts["FAIL"],
        "blocked": len(rows) - scored,
        "accuracy_on_scored": counts["PASS"] / scored if scored else None,
        "per_benchmark": per_benchmark,
    }


def _compare_status(records: list[dict[str, Any]], a: str, b: str) -> dict[str, Any]:
    amap = {x["sample_id"]: x for x in records if x["config_id"] == a}
    bmap = {x["sample_id"]: x for x in records if x["config_id"] == b}
    transitions = Counter()
    changed: list[dict[str, Any]] = []
    exact_output_hash_matches = 0
    for sid in sorted(amap):
        left, right = amap[sid], bmap[sid]
        transition = f"{left['status']}->{right['status']}"
        transitions[transition] += 1
        if left["output_sha256"] == right["output_sha256"]:
            exact_output_hash_matches += 1
        if left["status"] != right["status"]:
            changed.append({
                "sample_id": sid,
                "benchmark": left["benchmark"],
                "transition": transition,
                "from_grader_detail": left["grader_detail"],
                "to_grader_detail": right["grader_detail"],
            })
    return {
        "from": a, "to": b,
        "paired_count": len(amap),
        "status_transitions": dict(sorted(transitions.items())),
        "changed_status_cases": changed,
        "exact_output_hash_matches": exact_output_hash_matches,
        "exact_output_hash_match_fraction": exact_output_hash_matches / len(amap) if amap else None,
    }


def _quantization_gate(records: list[dict[str, Any]], quant_id: str) -> dict[str, Any]:
    ref_id = "FP16_RAW"
    ref = {x["sample_id"]: x for x in records if x["config_id"] == ref_id}
    quant = {x["sample_id"]: x for x in records if x["config_id"] == quant_id}
    regressions = []
    improvements = []
    for sid in sorted(ref):
        a, b = ref[sid], quant[sid]
        if a["status"] == "PASS" and b["status"] != "PASS":
            regressions.append({
                "sample_id": sid, "benchmark": a["benchmark"],
                "reference_status": a["status"], "quantized_status": b["status"],
                "reference_detail": a["grader_detail"], "quantized_detail": b["grader_detail"],
            })
        if a["status"] != "PASS" and b["status"] == "PASS":
            improvements.append({"sample_id": sid, "benchmark": a["benchmark"]})
    ref_pass = sum(x["status"] == "PASS" for x in ref.values())
    q_pass = sum(x["status"] == "PASS" for x in quant.values())
    blocked = [x["sample_id"] for x in quant.values() if str(x["status"]).startswith("BLOCKED_")]
    strict = not regressions and q_pass >= ref_pass and not blocked
    return {
        "reference": ref_id,
        "quantized": quant_id,
        "reference_pass": ref_pass,
        "quantized_pass": q_pass,
        "pass_delta": q_pass - ref_pass,
        "fp16_pass_to_quantized_nonpass": regressions,
        "nonpass_to_quantized_pass": improvements,
        "blocked_samples": blocked,
        "strict_non_regression": strict,
        "gate_status": "PASS_IN_TESTED_FROZEN_SCOPE" if strict else "REGRESSION_OBSERVED",
    }


def execute(config: dict[str, Any], pack: dict[str, Any], overlay: str,
            *, endpoint: str, docker_image: str, timeout: float) -> dict[str, Any]:
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError("config schema mismatch")
    errors = r1.validate_pack(pack)
    if errors:
        raise ValueError("invalid frozen Round-1 pack: " + "; ".join(errors))

    inference = config["inference"]
    providers: dict[str, r1.OllamaBenchmarkProvider] = {}
    model_receipts: dict[str, Any] = {}
    for model in config["models"]:
        provider = r1.OllamaBenchmarkProvider(
            endpoint, model["tag"], seed=int(inference["seed"]),
            temperature=float(inference["temperature"]), timeout=timeout,
            num_predict=int(inference["num_predict"]),
        )
        digest = provider.model_digest()
        if not digest or not digest.startswith(model["expected_digest_prefix"]):
            raise RuntimeError(
                f"model digest mismatch for {model['id']}: {digest!r} does not start with "
                f"{model['expected_digest_prefix']!r}"
            )
        providers[model["id"]] = provider
        model_receipts[model["id"]] = {
            "tag": model["tag"], "quantization": model["quantization"],
            "digest": digest, "expected_digest_prefix": model["expected_digest_prefix"],
        }

    records: list[dict[str, Any]] = []
    configs = [
        ("FP16_RAW", "FP16", "RAW"),
        ("Q8_0_RAW", "Q8_0", "RAW"),
        ("Q4_K_M_RAW", "Q4_K_M", "RAW"),
        ("Q4_K_M_GLOBAL_OVERLAY", "Q4_K_M", "GLOBAL"),
        ("Q4_K_M_ROUTED_BOUNDARY", "Q4_K_M", "ROUTED"),
    ]
    route_counts = Counter()
    for config_id, model_id, mode in configs:
        provider = providers[model_id]
        for sample in pack["samples"]:
            route = None
            if mode == "RAW":
                messages = r1._messages(sample, "RAW_PROVIDER", overlay)
            elif mode == "GLOBAL":
                messages = r1._messages(sample, "GENESIS_BOUNDARY_OVERLAY", overlay)
            else:
                route, messages = routed_messages(sample, overlay)
                route_counts[route] += 1
            output = provider.chat(messages)
            status, detail = r1.grade_sample(sample, output, docker_image=docker_image)
            records.append({
                "config_id": config_id,
                "model_id": model_id,
                "sample_id": sample["sample_id"],
                "benchmark": sample["benchmark"],
                "domain": sample["domain"],
                "route": route,
                "status": status,
                "grader": sample["grader"],
                "grader_detail": detail,
                "effective_input_sha256": canonical_sha256(messages),
                "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            })

    summaries = {cid: _summary(records, cid) for cid, _, _ in configs}
    q8_gate = _quantization_gate(records, "Q8_0_RAW")
    q4_gate = _quantization_gate(records, "Q4_K_M_RAW")
    raw_routed = _compare_status(records, "Q4_K_M_RAW", "Q4_K_M_ROUTED_BOUNDARY")
    global_routed = _compare_status(records, "Q4_K_M_GLOBAL_OVERLAY", "Q4_K_M_ROUTED_BOUNDARY")

    q4_raw_inputs = {
        x["sample_id"]: x["effective_input_sha256"] for x in records if x["config_id"] == "Q4_K_M_RAW"
    }
    routed_inputs = {
        x["sample_id"]: x["effective_input_sha256"] for x in records
        if x["config_id"] == "Q4_K_M_ROUTED_BOUNDARY"
    }
    route_input_identity = all(q4_raw_inputs[sid] == routed_inputs[sid] for sid in q4_raw_inputs)
    routed_status_neutral = not raw_routed["changed_status_cases"]

    return {
        "schema": REPORT_SCHEMA,
        "campaign": "JANUS_TOP100_ROUND2_QUANTIZATION_AND_ROUTED_BOUNDARY_v0.1",
        "sample_pack_sha256": canonical_sha256(pack),
        "sample_count": len(pack["samples"]),
        "configuration_count": len(configs),
        "execution_record_count": len(records),
        "ollama_version": providers["FP16"].version(),
        "models": model_receipts,
        "inference": inference,
        "summaries": summaries,
        "quantization_gates": {"Q8_0": q8_gate, "Q4_K_M": q4_gate},
        "routing": {
            "route_counts": dict(sorted(route_counts.items())),
            "all_round1_items_neutral_by_policy": route_counts["NEUTRAL_BENCHMARK_PATH"] == len(pack["samples"]),
            "q4_raw_vs_routed": raw_routed,
            "q4_global_vs_routed": global_routed,
            "raw_and_routed_effective_inputs_identical": route_input_identity,
            "raw_and_routed_statuses_identical": routed_status_neutral,
            "routed_boundary_gate_status": (
                "PASS_IN_TESTED_FROZEN_SCOPE"
                if route_input_identity and routed_status_neutral
                else "ROUTING_REGRESSION_OR_NONDETERMINISM_OBSERVED"
            ),
        },
        "round1_global_overlay_replay": {
            "expected_old_result": {"pass": 2, "fail": 19},
            "observed": {
                "pass": summaries["Q4_K_M_GLOBAL_OVERLAY"]["pass"],
                "fail": summaries["Q4_K_M_GLOBAL_OVERLAY"]["fail"],
            },
            "matches_round1": (
                summaries["Q4_K_M_GLOBAL_OVERLAY"]["pass"] == 2
                and summaries["Q4_K_M_GLOBAL_OVERLAY"]["fail"] == 19
            ),
        },
        "records": records,
        "official_benchmark_family_accuracy_claimed": False,
        "general_quantization_no_regression_claimed": False,
        "canonical_world_state_mutated": False,
        "claim_ceiling": (
            "Real Round-2 result on the unchanged 21-sample frozen Round-1 pack. "
            "Quantization conclusions apply only to the tested tags/digests/prompts/seed/runtime. "
            "Routing conclusions apply only to this frozen pack and explicit relevance policy."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--pack", type=Path, required=True)
    p.add_argument("--overlay", type=Path, required=True)
    p.add_argument("--endpoint", default="http://127.0.0.1:11434")
    p.add_argument("--docker-image", default="python:3.11-alpine")
    p.add_argument("--timeout", type=float, default=180.0)
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    overlay = args.overlay.read_text(encoding="utf-8")
    report = execute(config, pack, overlay, endpoint=args.endpoint,
                     docker_image=args.docker_image, timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, sort_keys=args.pretty,
                     indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
