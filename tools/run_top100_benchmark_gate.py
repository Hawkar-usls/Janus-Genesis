# -*- coding: utf-8 -*-
"""Attribution-safe runner for the Janus Genesis public benchmark campaign.

This runner is intentionally read/evaluate-only. It never imports or invokes
PlayableGenesisV187 and therefore cannot mutate canonical world state.

It validates the frozen 100-benchmark manifest and can optionally run a
user-supplied sample pack through an Ollama/OpenAI-compatible provider.
Official benchmark scores require each benchmark's own frozen dataset and grader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from genesis_v18_7_ai import AIProviderConfig, build_provider

MANIFEST_SCHEMA = "janus.genesis.top100_benchmark_manifest.v1"
REPORT_SCHEMA = "janus.genesis.top100_benchmark_gate_report.v1"
SAMPLE_SCHEMA = "janus.genesis.benchmark_sample_pack.v1"
ALLOWED_TARGETS = {"provider", "system_plus_provider", "external_environment"}
EXPECTED_COUNTS = {"provider": 68, "system_plus_provider": 16, "external_environment": 16}


class ProviderLike(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str: ...


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != MANIFEST_SCHEMA:
        errors.append("manifest schema mismatch")
    rows = payload.get("benchmarks")
    if not isinstance(rows, list):
        return {"valid": False, "errors": errors + ["benchmarks must be a list"]}
    if len(rows) != 100:
        errors.append(f"expected 100 benchmarks, got {len(rows)}")

    ids: list[int] = []
    names: list[str] = []
    targets: list[str] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"row {index} must be an object")
            continue
        row_id = row.get("id")
        name = row.get("name")
        target = row.get("target")
        if not isinstance(row_id, int):
            errors.append(f"row {index} id must be int")
        else:
            ids.append(row_id)
        if not isinstance(name, str) or not name.strip():
            errors.append(f"row {index} name missing")
        else:
            names.append(name.strip())
        if target not in ALLOWED_TARGETS:
            errors.append(f"row {index} invalid target {target!r}")
        else:
            targets.append(target)

    if ids and ids != list(range(1, 101)):
        errors.append("benchmark ids must be exactly 1..100 in order")
    if len(names) != len(set(names)):
        errors.append("benchmark names must be unique")

    counts = dict(Counter(targets))
    for target, expected in EXPECTED_COUNTS.items():
        if counts.get(target, 0) != expected:
            errors.append(
                f"target count mismatch for {target}: {counts.get(target, 0)} != {expected}"
            )
    return {
        "valid": not errors,
        "errors": errors,
        "benchmark_count": len(rows),
        "target_counts": {k: counts.get(k, 0) for k in sorted(ALLOWED_TARGETS)},
        "manifest_sha256": canonical_sha256(payload),
    }


def readiness_report(
    manifest: dict[str, Any],
    *,
    provider_available: bool,
    external_environment_available: bool,
    universal_chat_executor_available: bool,
) -> dict[str, Any]:
    validation = validate_manifest(manifest)
    if not validation["valid"]:
        raise ValueError("invalid manifest: " + "; ".join(validation["errors"]))

    statuses: list[dict[str, Any]] = []
    for row in manifest["benchmarks"]:
        target = row["target"]
        if target == "provider":
            status = "READY_FOR_DATASET_EXECUTION" if provider_available else "BLOCKED_NO_PROVIDER"
        elif target == "system_plus_provider":
            status = (
                "READY_FOR_COMPOSITE_EXECUTION"
                if provider_available and universal_chat_executor_available
                else "BLOCKED_NO_COMPOSITE_EXECUTOR"
            )
        else:
            status = (
                "READY_FOR_EXTERNAL_ENV_EXECUTION"
                if external_environment_available
                else "BLOCKED_NO_EXTERNAL_ENV"
            )
        statuses.append({
            "id": row["id"], "benchmark": row["name"],
            "target": target, "status": status,
        })

    counts = Counter(item["status"] for item in statuses)
    return {
        "schema": REPORT_SCHEMA,
        "mode": "EXECUTION_READINESS",
        "manifest": validation,
        "availability": {
            "provider": provider_available,
            "universal_chat_executor": universal_chat_executor_available,
            "external_environment": external_environment_available,
        },
        "status_counts": dict(sorted(counts.items())),
        "benchmarks": statuses,
        "official_dataset_accuracy_claimed": False,
        "canonical_world_state_mutated": False,
        "claim_ceiling": (
            "Readiness classification only. Blocked means required execution capacity "
            "is absent; it is not a benchmark failure."
        ),
    }


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def grade_answer(answer: str, expected: Any, grader: str) -> tuple[bool, str]:
    if grader == "exact":
        wanted = _normalize_text(str(expected))
        got = _normalize_text(answer)
        return got == wanted, f"exact:{got!r}=={wanted!r}"
    if grader == "contains":
        wanted = _normalize_text(str(expected))
        got = _normalize_text(answer)
        return wanted in got, f"contains:{wanted!r} in answer"
    if grader == "regex":
        pattern = str(expected)
        return re.search(pattern, answer, re.MULTILINE) is not None, f"regex:{pattern!r}"
    raise ValueError(f"unsupported grader: {grader}")


def validate_sample_pack(pack: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if pack.get("schema") != SAMPLE_SCHEMA:
        errors.append("sample pack schema mismatch")
    samples = pack.get("samples")
    if not isinstance(samples, list) or not samples:
        return errors + ["samples must be a non-empty list"]

    known = {row["name"]: row for row in manifest["benchmarks"]}
    seen: set[str] = set()
    for i, sample in enumerate(samples, 1):
        if not isinstance(sample, dict):
            errors.append(f"sample {i} must be object")
            continue
        sid = str(sample.get("sample_id") or "").strip()
        benchmark = str(sample.get("benchmark") or "").strip()
        prompt = sample.get("prompt")
        grader = sample.get("grader")
        if not sid:
            errors.append(f"sample {i} missing sample_id")
        elif sid in seen:
            errors.append(f"duplicate sample_id {sid}")
        else:
            seen.add(sid)
        if benchmark not in known:
            errors.append(f"sample {i} unknown benchmark {benchmark!r}")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"sample {i} prompt missing")
        if "expected" not in sample:
            errors.append(f"sample {i} expected missing")
        if grader not in {"exact", "contains", "regex"}:
            errors.append(f"sample {i} unsupported grader {grader!r}")
    return errors


def run_sample_pack(
    pack: dict[str, Any], manifest: dict[str, Any], provider: ProviderLike,
    *, system_prompt: str | None = None,
) -> dict[str, Any]:
    errors = validate_sample_pack(pack, manifest)
    if errors:
        raise ValueError("invalid sample pack: " + "; ".join(errors))

    by_name = {row["name"]: row for row in manifest["benchmarks"]}
    receipts: list[dict[str, Any]] = []
    scored = 0
    passed = 0
    for sample in pack["samples"]:
        row = by_name[sample["benchmark"]]
        if row["target"] == "external_environment":
            receipts.append({
                "sample_id": sample["sample_id"],
                "benchmark": row["name"],
                "status": "NOT_EXECUTED_EXTERNAL_ENV_REQUIRED",
                "input_sha256": canonical_sha256(sample),
            })
            continue

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": sample["prompt"]})
        answer = provider.chat(messages)
        ok, detail = grade_answer(answer, sample["expected"], sample["grader"])
        scored += 1
        passed += int(ok)
        receipts.append({
            "sample_id": sample["sample_id"],
            "benchmark": row["name"],
            "target": row["target"],
            "status": "PASS" if ok else "FAIL",
            "grader": sample["grader"],
            "grader_detail": detail,
            "input_sha256": canonical_sha256(sample),
            "output_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        })

    return {
        "schema": REPORT_SCHEMA,
        "mode": "SAMPLE_PACK_EXECUTION",
        "sample_pack_id": pack.get("pack_id"),
        "sample_pack_sha256": canonical_sha256(pack),
        "scored": scored,
        "passed": passed,
        "failed": scored - passed,
        "accuracy": (passed / scored) if scored else None,
        "receipts": receipts,
        "official_dataset_accuracy_claimed": False,
        "score_label": "SAMPLE_PACK_ONLY",
        "canonical_world_state_mutated": False,
        "claim_ceiling": (
            "Score applies only to the supplied frozen sample pack. It is not an "
            "official benchmark-family score unless the pack itself is proven to be "
            "the official frozen evaluation set and grader."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path,
                   default=Path("benchmarks/top100_public_ai_benchmarks_v0.1.json"))
    p.add_argument("--samples", type=Path)
    p.add_argument("--provider", choices=("ollama", "openai-compatible"))
    p.add_argument("--model")
    p.add_argument("--endpoint")
    p.add_argument("--api-key-env")
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--system-prompt-file", type=Path)
    p.add_argument("--external-environment-available", action="store_true")
    p.add_argument("--universal-chat-executor-available", action="store_true")
    p.add_argument("--pretty", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_json(args.manifest)
    validation = validate_manifest(manifest)
    if not validation["valid"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 2

    provider = None
    if args.provider:
        if not args.model or not args.endpoint:
            raise SystemExit("--provider requires --model and --endpoint")
        provider = build_provider(AIProviderConfig(
            provider=args.provider, model=args.model, endpoint=args.endpoint,
            api_key_env=args.api_key_env, timeout_seconds=args.timeout,
        ))

    if args.samples:
        if provider is None:
            raise SystemExit("--samples requires a configured --provider")
        pack = load_json(args.samples)
        system_prompt = (
            args.system_prompt_file.read_text(encoding="utf-8")
            if args.system_prompt_file else None
        )
        report = run_sample_pack(pack, manifest, provider, system_prompt=system_prompt)
    else:
        report = readiness_report(
            manifest,
            provider_available=provider is not None,
            external_environment_available=args.external_environment_available,
            universal_chat_executor_available=args.universal_chat_executor_available,
        )

    print(json.dumps(report, ensure_ascii=False,
                     indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
