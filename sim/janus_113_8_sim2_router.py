#!/usr/bin/env python3
"""JANUS 113.8 SIM-2 read-only open-world provenance router.

The router receives public cases without gold labels. It may read only pinned
raw GitHub text artifacts, then emits a decision and a complete witness ledger.
It performs no network write, deletion, self-modification, or external actuation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

VERSION = "JANUS-113.8-SIM-2-ROUTER-v1.0"
ALLOWED_HOST = "raw.githubusercontent.com"
UNPINNED_REFS = {"main", "master", "HEAD"}
MAX_SOURCE_BYTES = 300_000
TIMEOUT_SECONDS = 20
RETRY_COUNT = 3
HEX64 = re.compile(r"^[0-9a-f]{64}$")
VALID_TERMINALS = {
    "SUPPORTED_PUBLIC_PROVENANCE",
    "REFUTED_HASH",
    "REFUTED_SIZE",
    "REFUTED_MARKER",
    "REFUTED_SCHEMA",
    "OPEN_SOURCE_UNREACHABLE",
    "OPEN_UNPINNED_PROVENANCE",
    "OPEN_CONFLICTING_CLAIMS",
    "SAFETY_BLOCK_UNTRUSTED_SOURCE",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_bytes(url: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"{VERSION} read-only provenance check"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError("source exceeds bounded read limit")
                return data
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < RETRY_COUNT:
                time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"source read failed: {last_error}")


def _url_gate(case: dict[str, Any]) -> tuple[str | None, str]:
    url = case.get("source_url")
    if not isinstance(url, str):
        return "REFUTED_SCHEMA", "source_url must be text"
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
        return "SAFETY_BLOCK_UNTRUSTED_SOURCE", "scheme or host is outside the read-only allowlist"
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 4:
        return "REFUTED_SCHEMA", "raw GitHub URL lacks owner/repository/ref/path"
    observed_ref = segments[2]
    declared_ref = case.get("source_ref")
    if observed_ref in UNPINNED_REFS or declared_ref in UNPINNED_REFS or observed_ref != declared_ref:
        return "OPEN_UNPINNED_PROVENANCE", "source ref is floating or differs from the declared pinned ref"
    return None, "trusted pinned raw GitHub source"


def _claim_schema_error(claim: Any) -> str | None:
    if not isinstance(claim, dict):
        return "claim must be an object"
    if set(claim) != {"sha256", "size_bytes", "required_marker", "alternate_sha256"}:
        return "claim fields do not match the sealed schema"
    if not isinstance(claim["sha256"], str) or not HEX64.fullmatch(claim["sha256"]):
        return "sha256 must contain exactly 64 lowercase hexadecimal characters"
    size = claim["size_bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_SOURCE_BYTES:
        return "size_bytes must be a bounded integer"
    if not isinstance(claim["required_marker"], str) or not claim["required_marker"]:
        return "required_marker must be non-empty text"
    alternate = claim["alternate_sha256"]
    if alternate is not None and (not isinstance(alternate, str) or not HEX64.fullmatch(alternate)):
        return "alternate_sha256 must be null or a complete digest"
    return None


def _decision(
    case: dict[str, Any], terminal: str, reason: str, observed: dict[str, Any] | None = None
) -> dict[str, Any]:
    if terminal == "SUPPORTED_PUBLIC_PROVENANCE":
        predicted_class, support_probability, confidence = "SUPPORTED", 0.99, 0.99
    elif terminal.startswith("REFUTED_"):
        predicted_class, support_probability, confidence = "REFUTED", 0.01, 0.99
    elif terminal.startswith("SAFETY_BLOCK_"):
        predicted_class, support_probability, confidence = "SAFETY_BLOCK", 0.50, 1.00
    else:
        predicted_class, support_probability, confidence = "OPEN", 0.50, 0.50
    result = {
        "case_id": case.get("case_id", "UNKNOWN"),
        "source_id": case.get("source_id"),
        "decision_terminal": terminal,
        "predicted_class": predicted_class,
        "support_probability": support_probability,
        "confidence": confidence,
        "reason": reason,
        "observed": observed,
        "runtime_authority": "NONE",
    }
    result["prediction_sha256"] = sha256_text(canonical_json(result))
    return result


def evaluate_case(
    case: Any,
    *,
    fetcher: Callable[[str], bytes] = fetch_bytes,
    cache: dict[str, bytes | Exception] | None = None,
) -> dict[str, Any]:
    if not isinstance(case, dict) or case.get("schema") != "janus.genesis.sim2.public_case.v1":
        return _decision(case if isinstance(case, dict) else {}, "REFUTED_SCHEMA", "public case schema mismatch")
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
    if set(case) != required or case.get("read_only") is not True or case.get("runtime_authority") != "NONE":
        return _decision(case, "REFUTED_SCHEMA", "case fields or authority boundary are invalid")

    claim_error = _claim_schema_error(case.get("claim"))
    if claim_error:
        return _decision(case, "REFUTED_SCHEMA", claim_error)
    claim = case["claim"]
    alternate = claim["alternate_sha256"]
    if alternate is not None and alternate != claim["sha256"]:
        return _decision(case, "OPEN_CONFLICTING_CLAIMS", "two incompatible source digests are asserted")

    gate_terminal, gate_reason = _url_gate(case)
    if gate_terminal:
        return _decision(case, gate_terminal, gate_reason)

    url = case["source_url"]
    local_cache = cache if cache is not None else {}
    if url not in local_cache:
        try:
            local_cache[url] = fetcher(url)
        except Exception as exc:  # bounded external read failure becomes an honest OPEN
            local_cache[url] = exc
    cached = local_cache[url]
    if isinstance(cached, Exception):
        return _decision(case, "OPEN_SOURCE_UNREACHABLE", f"pinned source could not be read: {type(cached).__name__}")

    data = cached
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _decision(case, "REFUTED_SCHEMA", "source is not UTF-8 text")
    observed = {
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
        "required_marker_present": claim["required_marker"] in text,
    }
    if observed["sha256"] != claim["sha256"]:
        return _decision(case, "REFUTED_HASH", "observed source digest differs from the claim", observed)
    if observed["size_bytes"] != claim["size_bytes"]:
        return _decision(case, "REFUTED_SIZE", "observed source size differs from the claim", observed)
    if not observed["required_marker_present"]:
        return _decision(case, "REFUTED_MARKER", "required marker is absent from the observed source", observed)
    return _decision(case, "SUPPORTED_PUBLIC_PROVENANCE", "all pinned provenance checks passed", observed)


def write_predictions(input_path: Path, output_dir: Path) -> dict[str, Any]:
    lines = [line for line in input_path.read_text(encoding="utf-8").splitlines() if line]
    cases = [json.loads(line) for line in lines]
    cache: dict[str, bytes | Exception] = {}
    predictions = [evaluate_case(case, cache=cache) for case in cases]
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = output_dir / "predictions.jsonl"
    prediction_path.write_text(
        "".join(canonical_json(prediction) + "\n" for prediction in predictions), encoding="utf-8"
    )

    previous = "0" * 64
    ledger_entries: list[dict[str, Any]] = []
    for ordinal, prediction in enumerate(predictions):
        body = {
            "ordinal": ordinal,
            "case_id": prediction["case_id"],
            "prediction_sha256": prediction["prediction_sha256"],
            "prev_hash": previous,
        }
        entry_hash = sha256_text(canonical_json(body))
        entry = {**body, "entry_hash": entry_hash}
        ledger_entries.append(entry)
        previous = entry_hash
    ledger_path = output_dir / "witness_ledger.jsonl"
    ledger_path.write_text(
        "".join(canonical_json(entry) + "\n" for entry in ledger_entries), encoding="utf-8"
    )

    manifest = {
        "schema": "janus.genesis.sim2.router_manifest.v1",
        "version": VERSION,
        "generated_utc": utc_now(),
        "case_count": len(cases),
        "decision_counts": dict(sorted(Counter(p["decision_terminal"] for p in predictions).items())),
        "public_cases_sha256": sha256_text(input_path.read_text(encoding="utf-8")),
        "predictions_sha256": sha256_text(prediction_path.read_text(encoding="utf-8")),
        "witness_ledger_sha256": sha256_text(ledger_path.read_text(encoding="utf-8")),
        "final_ledger_hash": previous,
        "unique_network_targets": len(cache),
        "valid_terminals_only": all(p["decision_terminal"] in VALID_TERMINALS for p in predictions),
        "safety_boundary": {
            "network_read": True,
            "allowed_host": ALLOWED_HOST,
            "network_write": False,
            "file_deletion": False,
            "self_modification": False,
            "external_actuation": False,
            "runtime_authority": "NONE",
        },
    }
    (output_dir / "router_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    manifest = write_predictions(args.input, args.output)
    if args.print_summary:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
