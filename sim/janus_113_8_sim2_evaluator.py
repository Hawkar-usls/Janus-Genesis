#!/usr/bin/env python3
"""Independent evaluator for JANUS 113.8 SIM-2 open-world calibration.

This module imports neither the corpus builder nor the router. It independently
re-fetches pinned public artifacts, reconstructs every expected terminal, and
replays both historical v1 and hardened v2 prediction and Witness Ledger formats.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "JANUS-113.8-SIM-2-INDEPENDENT-EVALUATOR-v2.0"
ALLOWED_HOST = "raw.githubusercontent.com"
UNPINNED_REFS = {"main", "master", "HEAD"}
MAX_SOURCE_BYTES = 300_000
TIMEOUT_SECONDS = 20
RETRY_COUNT = 3
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PREDICTION_DOMAIN = "JANUS_ROUTER_PREDICTION_V2\n"
LEDGER_DOMAIN = "JANUS_ROUTER_LEDGER_V2\n"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fetch_public_text(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"{VERSION} read-only independent replay"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                data = response.read(MAX_SOURCE_BYTES + 1)
                if len(data) > MAX_SOURCE_BYTES:
                    raise ValueError("source exceeds the independent byte limit")
                return data
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < RETRY_COUNT:
                time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"independent source read failed: {last_error}")


def load_sources(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "janus.genesis.sim2.public_sources.v1":
        raise ValueError("source manifest schema mismatch")
    return manifest


def independent_source_snapshot(source_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for source in source_manifest["sources"]:
        parsed = urllib.parse.urlparse(source["raw_url"])
        segments = [segment for segment in parsed.path.split("/") if segment]
        if (
            parsed.scheme != "https"
            or parsed.hostname != ALLOWED_HOST
            or len(segments) < 4
            or segments[2] != source["ref"]
            or source["ref"] in UNPINNED_REFS
        ):
            raise ValueError(f"untrusted or unpinned source manifest entry: {source['source_id']}")
        data = fetch_public_text(source["raw_url"])
        text = data.decode("utf-8")
        snapshots.append(
            {
                **source,
                "observed_sha256": sha256_bytes(data),
                "observed_size_bytes": len(data),
                "required_marker_present": source["required_marker"] in text,
            }
        )
    return snapshots


def _case_shape_ok(case: Any) -> bool:
    required = {
        "schema",
        "case_id",
        "nonce",
        "source_id",
        "source_repository",
        "source_ref",
        "source_path",
        "source_url",
        "claim",
        "read_only",
        "runtime_authority",
    }
    return (
        isinstance(case, dict)
        and case.get("schema") == "janus.genesis.sim2.public_case.v1"
        and set(case) == required
        and case.get("read_only") is True
        and case.get("runtime_authority") == "NONE"
    )


def _claim_shape_ok(claim: Any) -> bool:
    if not isinstance(claim, dict) or set(claim) != {
        "sha256",
        "size_bytes",
        "required_marker",
        "alternate_sha256",
    }:
        return False
    if not isinstance(claim["sha256"], str) or not HEX64.fullmatch(claim["sha256"]):
        return False
    size = claim["size_bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_SOURCE_BYTES:
        return False
    if not isinstance(claim["required_marker"], str) or not claim["required_marker"]:
        return False
    alternate = claim["alternate_sha256"]
    return alternate is None or (isinstance(alternate, str) and HEX64.fullmatch(alternate) is not None)


def independent_terminal(case: Any, cache: dict[str, bytes | Exception]) -> tuple[str, str]:
    if not _case_shape_ok(case) or not _claim_shape_ok(case.get("claim") if isinstance(case, dict) else None):
        return "REFUTED_SCHEMA", "independent schema replay failed"
    claim = case["claim"]
    alternate = claim["alternate_sha256"]
    if alternate is not None and alternate != claim["sha256"]:
        return "OPEN_CONFLICTING_CLAIMS", "incompatible digests remain unresolved"

    parsed = urllib.parse.urlparse(case["source_url"])
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        return "SAFETY_BLOCK_UNTRUSTED_SOURCE", "source is outside the evaluator allowlist"
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 4:
        return "REFUTED_SCHEMA", "raw source URL shape is invalid"
    observed_ref = segments[2]
    if observed_ref in UNPINNED_REFS or case["source_ref"] in UNPINNED_REFS or observed_ref != case["source_ref"]:
        return "OPEN_UNPINNED_PROVENANCE", "source ref is floating or mismatched"

    url = case["source_url"]
    if url not in cache:
        try:
            cache[url] = fetch_public_text(url)
        except Exception as exc:
            cache[url] = exc
    payload = cache[url]
    if isinstance(payload, Exception):
        return "OPEN_SOURCE_UNREACHABLE", "independent fetch could not reach the pinned object"
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return "REFUTED_SCHEMA", "source is not UTF-8"
    if sha256_bytes(payload) != claim["sha256"]:
        return "REFUTED_HASH", "digest mismatch"
    if len(payload) != claim["size_bytes"]:
        return "REFUTED_SIZE", "size mismatch"
    if claim["required_marker"] not in text:
        return "REFUTED_MARKER", "required marker mismatch"
    return "SUPPORTED_PUBLIC_PROVENANCE", "pinned public provenance independently supported"


def terminal_class(terminal: str) -> str:
    if terminal == "SUPPORTED_PUBLIC_PROVENANCE":
        return "SUPPORTED"
    if terminal.startswith("REFUTED_"):
        return "REFUTED"
    if terminal.startswith("SAFETY_BLOCK_"):
        return "SAFETY_BLOCK"
    return "OPEN"


def expected_calibration_error(
    probabilities: list[float], labels: list[int], bins: int = 10
) -> tuple[float, list[dict[str, Any]]]:
    if len(probabilities) != len(labels) or not probabilities:
        raise ValueError("calibration vectors must be non-empty and aligned")
    rows: list[dict[str, Any]] = []
    ece = 0.0
    count = len(probabilities)
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        members = [
            (probability, label)
            for probability, label in zip(probabilities, labels, strict=True)
            if low <= probability < high or (index == bins - 1 and probability == 1.0)
        ]
        if not members:
            continue
        mean_probability = sum(item[0] for item in members) / len(members)
        empirical_rate = sum(item[1] for item in members) / len(members)
        gap = abs(mean_probability - empirical_rate)
        ece += (len(members) / count) * gap
        rows.append(
            {
                "bin": index,
                "low": low,
                "high": high,
                "count": len(members),
                "mean_support_probability": mean_probability,
                "empirical_support_rate": empirical_rate,
                "absolute_gap": gap,
            }
        )
    return ece, rows


def _verify_prediction_v2(prediction: dict[str, Any], ordinal: int) -> tuple[bool, str]:
    body = dict(prediction)
    claimed_prediction_hash = body.pop("prediction_sha256", None)
    claimed_body_hash = body.pop("prediction_body_sha256", None)
    expected_body_hash = sha256_text(canonical_json(body))
    if claimed_body_hash != expected_body_hash:
        return False, f"prediction body hash mismatch at ordinal {ordinal}"
    input_line_hash = prediction.get("input_line_sha256")
    input_case_hash = prediction.get("input_case_sha256") or "NULL"
    if not isinstance(input_line_hash, str):
        return False, f"prediction input line hash missing at ordinal {ordinal}"
    expected_prediction_hash = sha256_text(
        PREDICTION_DOMAIN
        + input_line_hash
        + "\n"
        + input_case_hash
        + "\n"
        + expected_body_hash
    )
    if claimed_prediction_hash != expected_prediction_hash:
        return False, f"prediction hash mismatch at ordinal {ordinal}"
    return True, expected_prediction_hash


def verify_witness_ledger(
    predictions: list[dict[str, Any]], ledger: list[dict[str, Any]]
) -> tuple[bool, str]:
    if len(predictions) != len(ledger):
        return False, "prediction and ledger lengths differ"
    previous = "0" * 64
    for ordinal, (prediction, entry) in enumerate(zip(predictions, ledger, strict=True)):
        if prediction.get("schema") == "janus.genesis.router.prediction.v2":
            ok, prediction_hash = _verify_prediction_v2(prediction, ordinal)
            if not ok:
                return False, prediction_hash
            expected_body = {
                "schema": "janus.genesis.router.ledger_entry.v2",
                "ordinal": ordinal,
                "input_line_sha256": prediction["input_line_sha256"],
                "prediction_sha256": prediction_hash,
                "prev_hash": previous,
            }
            expected_hash = sha256_text(LEDGER_DOMAIN + canonical_json(expected_body))
        else:
            prediction_body = dict(prediction)
            prediction_hash = prediction_body.pop("prediction_sha256", None)
            expected_prediction_hash = sha256_text(canonical_json(prediction_body))
            if prediction_hash != expected_prediction_hash:
                return False, f"prediction hash mismatch at ordinal {ordinal}"
            expected_body = {
                "ordinal": ordinal,
                "case_id": prediction["case_id"],
                "prediction_sha256": expected_prediction_hash,
                "prev_hash": previous,
            }
            expected_hash = sha256_text(canonical_json(expected_body))
        if entry != {**expected_body, "entry_hash": expected_hash}:
            return False, f"ledger chain mismatch at ordinal {ordinal}"
        previous = expected_hash
    return True, previous


def evaluate(
    *, source_manifest_path: Path, corpus_dir: Path, router_dir: Path, output_dir: Path
) -> dict[str, Any]:
    source_manifest = load_sources(source_manifest_path)
    independent_snapshots = independent_source_snapshot(source_manifest)
    independent_source_map = {item["raw_url"]: item for item in independent_snapshots}

    builder_manifest_path = corpus_dir / "builder_manifest.json"
    snapshot_path = corpus_dir / "source_snapshot.json"
    public_path = corpus_dir / "cases_public.jsonl"
    truth_path = corpus_dir / "truth.jsonl"
    builder_manifest = json.loads(builder_manifest_path.read_text(encoding="utf-8"))
    builder_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))["sources"]
    public_cases = read_jsonl(public_path)
    truth = read_jsonl(truth_path)

    router_manifest_path = router_dir / "router_manifest.json"
    predictions_path = router_dir / "predictions.jsonl"
    ledger_path = router_dir / "witness_ledger.jsonl"
    router_manifest = json.loads(router_manifest_path.read_text(encoding="utf-8"))
    predictions = read_jsonl(predictions_path)
    ledger = read_jsonl(ledger_path)

    source_snapshots_match = canonical_json(independent_snapshots) == canonical_json(builder_snapshot)
    stable_replay = {"snapshots": builder_snapshot, "public_cases": public_cases, "truth": truth}
    builder_checks = {
        "source_snapshot_sha256": builder_manifest.get("source_snapshot_sha256")
        == sha256_text(snapshot_path.read_text(encoding="utf-8")),
        "public_cases_sha256": builder_manifest.get("public_cases_sha256")
        == sha256_text(public_path.read_text(encoding="utf-8")),
        "truth_sha256": builder_manifest.get("truth_sha256")
        == sha256_text(truth_path.read_text(encoding="utf-8")),
        "replay_digest_sha256": builder_manifest.get("replay_digest_sha256")
        == sha256_text(canonical_json(stable_replay)),
        "source_snapshots_match_independent_fetch": source_snapshots_match,
        "case_count": builder_manifest.get("case_count") == len(public_cases) == len(truth),
    }

    ledger_ok, final_ledger_hash = verify_witness_ledger(predictions, ledger)
    manifest_is_v2 = router_manifest.get("schema") == "janus.genesis.router.manifest.v2"
    if manifest_is_v2:
        case_count_ok = (
            router_manifest.get("run_terminal") == "COMPLETED"
            and router_manifest.get("input_complete") is True
            and router_manifest.get("line_conservation") is True
            and router_manifest.get("input_nonempty_line_count") == len(public_cases)
            and router_manifest.get("prediction_count") == len(predictions)
            and router_manifest.get("ledger_entry_count") == len(ledger)
            and len(predictions) == len(ledger) == len(public_cases)
        )
    else:
        case_count_ok = router_manifest.get("case_count") == len(predictions)

    router_checks = {
        "public_cases_sha256": router_manifest.get("public_cases_sha256")
        == sha256_text(public_path.read_text(encoding="utf-8")),
        "predictions_sha256": router_manifest.get("predictions_sha256")
        == sha256_text(predictions_path.read_text(encoding="utf-8")),
        "witness_ledger_sha256": router_manifest.get("witness_ledger_sha256")
        == sha256_text(ledger_path.read_text(encoding="utf-8")),
        "final_ledger_hash": router_manifest.get("final_ledger_hash") == final_ledger_hash,
        "ledger_replay": ledger_ok,
        "case_count": case_count_ok,
        "valid_terminals_only": router_manifest.get("valid_terminals_only") is True,
    }

    truth_by_id = {item["case_id"]: item for item in truth}
    prediction_by_id = {item["case_id"]: item for item in predictions}
    unique_case_ids = len({case["case_id"] for case in public_cases}) == len(public_cases)
    aligned_ids = set(truth_by_id) == set(prediction_by_id) == {case["case_id"] for case in public_cases}

    cache: dict[str, bytes | Exception] = {url: fetch_public_text(url) for url in independent_source_map}
    results: list[dict[str, Any]] = []
    for case in public_cases:
        independent, independent_reason = independent_terminal(case, cache)
        truth_item = truth_by_id.get(case["case_id"], {})
        prediction = prediction_by_id.get(case["case_id"], {})
        router_terminal = prediction.get("decision_terminal")
        truth_terminal = truth_item.get("expected_terminal")
        results.append(
            {
                "case_id": case["case_id"],
                "source_id": case["source_id"],
                "mutation_class": truth_item.get("mutation_class"),
                "independent_terminal": independent,
                "truth_terminal": truth_terminal,
                "router_terminal": router_terminal,
                "truth_matches_independent": truth_terminal == independent,
                "router_matches_independent": router_terminal == independent,
                "independent_class": terminal_class(independent),
                "router_class": prediction.get("predicted_class"),
                "support_probability": prediction.get("support_probability"),
                "reason": independent_reason,
            }
        )

    exact_terminal_accuracy = sum(r["router_matches_independent"] for r in results) / len(results)
    truth_accuracy = sum(r["truth_matches_independent"] for r in results) / len(results)
    non_supported = [r for r in results if r["independent_class"] != "SUPPORTED"]
    supported = [r for r in results if r["independent_class"] == "SUPPORTED"]
    false_acceptance_rate = (
        sum(r["router_class"] == "SUPPORTED" for r in non_supported) / len(non_supported)
        if non_supported
        else 0.0
    )
    false_rejection_rate = (
        sum(r["router_class"] != "SUPPORTED" for r in supported) / len(supported)
        if supported
        else 0.0
    )
    decisive = [r for r in results if r["independent_class"] in {"SUPPORTED", "REFUTED"}]
    probabilities = [float(r["support_probability"]) for r in decisive]
    labels = [1 if r["independent_class"] == "SUPPORTED" else 0 for r in decisive]
    brier_score = sum(
        (probability - label) ** 2
        for probability, label in zip(probabilities, labels, strict=True)
    ) / len(decisive)
    ece, calibration_bins = expected_calibration_error(probabilities, labels)
    decisive_coverage = sum(r["router_class"] in {"SUPPORTED", "REFUTED"} for r in decisive) / len(decisive)

    mutation_counts = Counter(item.get("mutation_class") for item in truth)
    terminal_counts = Counter(item["independent_terminal"] for item in results)
    suite_checks = {
        "builder_checks_pass": all(builder_checks.values()),
        "router_checks_pass": all(router_checks.values()),
        "unique_case_ids": unique_case_ids,
        "aligned_case_ids": aligned_ids,
        "case_count_200": len(results) == 200,
        "ten_mutation_classes": len(mutation_counts) == 10,
        "twenty_cases_per_mutation": all(count == 20 for count in mutation_counts.values()),
        "truth_reconstructed_independently": math.isclose(truth_accuracy, 1.0),
        "router_exact_terminal_accuracy": math.isclose(exact_terminal_accuracy, 1.0),
        "false_acceptance_rate_zero": math.isclose(false_acceptance_rate, 0.0),
        "false_rejection_rate_zero": math.isclose(false_rejection_rate, 0.0),
        "decisive_coverage_full": math.isclose(decisive_coverage, 1.0),
        "brier_score_at_most_0_0002": brier_score <= 0.0002,
        "ece_at_most_0_011": ece <= 0.011,
    }
    admitted = all(suite_checks.values())
    terminal = "JANUS_113.8_SIM_2_ADMITTED" if admitted else "JANUS_113.8_SIM_2_REJECTED"

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "case_results.jsonl").write_text(
        "".join(canonical_json(item) + "\n" for item in results), encoding="utf-8"
    )
    (output_dir / "calibration_bins.json").write_text(
        json.dumps({"schema": "janus.genesis.sim2.calibration_bins.v1", "bins": calibration_bins}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": "janus.genesis.sim2.independent_evaluation_report.v2",
        "version": VERSION,
        "generated_utc": utc_now(),
        "terminal": terminal,
        "admitted": admitted,
        "source_count": len(independent_snapshots),
        "case_count": len(results),
        "mutation_counts": dict(sorted(mutation_counts.items())),
        "terminal_counts": dict(sorted(terminal_counts.items())),
        "metrics": {
            "truth_reconstruction_accuracy": truth_accuracy,
            "router_exact_terminal_accuracy": exact_terminal_accuracy,
            "false_acceptance_rate": false_acceptance_rate,
            "false_rejection_rate": false_rejection_rate,
            "decisive_coverage": decisive_coverage,
            "brier_score": brier_score,
            "expected_calibration_error": ece,
        },
        "builder_checks": builder_checks,
        "router_checks": router_checks,
        "suite_checks": suite_checks,
        "failed_case_ids": [r["case_id"] for r in results if not r["router_matches_independent"]],
        "replay_digest_sha256": builder_manifest.get("replay_digest_sha256"),
        "final_ledger_hash": final_ledger_hash,
        "claim_boundary": {
            "network_read": True,
            "network_write": False,
            "open_world_scope": "five pinned public GitHub text artifacts and ten sealed perturbation classes",
            "organizational_independence": False,
            "consciousness_claimed": False,
            "runtime_authority": "NONE",
        },
        "next_terminal": "SIM_3_EXTERNAL_AUTHOR_VERIFIER_REQUIRED" if admitted else "SIM_2_CORRECTION_REQUIRED",
    }
    (output_dir / "independent_evaluation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = {
        "schema": "janus.genesis.sim2.summary.v2",
        "terminal": terminal,
        "admitted": admitted,
        "source_count": len(independent_snapshots),
        "case_count": len(results),
        "router_exact_terminal_accuracy": exact_terminal_accuracy,
        "false_acceptance_rate": false_acceptance_rate,
        "false_rejection_rate": false_rejection_rate,
        "brier_score": brier_score,
        "expected_calibration_error": ece,
        "replay_digest_sha256": builder_manifest.get("replay_digest_sha256"),
        "next_terminal": report["next_terminal"],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--router", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    report = evaluate(
        source_manifest_path=args.sources,
        corpus_dir=args.corpus,
        router_dir=args.router,
        output_dir=args.output,
    )
    if args.print_summary:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["admitted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
