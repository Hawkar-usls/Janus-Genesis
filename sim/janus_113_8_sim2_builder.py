#!/usr/bin/env python3
"""Build a held-out, network-read-only SIM-2 calibration corpus.

The builder fetches pinned public text artifacts, freezes their observed hashes,
and emits public cases separately from a sealed truth ledger. It has no write
access to remote systems and performs no deletion, self-modification, or actuation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "JANUS-113.8-SIM-2-BUILDER-v1.0"
DEFAULT_SEED = 1_138_001_938
DEFAULT_REPETITIONS = 4
MAX_REPETITIONS = 20
MUTATIONS = (
    "exact_valid",
    "wrong_hash",
    "wrong_size",
    "wrong_marker",
    "truncated_digest",
    "unreachable_path",
    "unpinned_ref",
    "disallowed_host",
    "unsupported_scheme",
    "conflicting_claims",
)
TERMINALS = {
    "exact_valid": ("SUPPORTED_PUBLIC_PROVENANCE", "SUPPORTED"),
    "wrong_hash": ("REFUTED_HASH", "REFUTED"),
    "wrong_size": ("REFUTED_SIZE", "REFUTED"),
    "wrong_marker": ("REFUTED_MARKER", "REFUTED"),
    "truncated_digest": ("REFUTED_SCHEMA", "REFUTED"),
    "unreachable_path": ("OPEN_SOURCE_UNREACHABLE", "OPEN"),
    "unpinned_ref": ("OPEN_UNPINNED_PROVENANCE", "OPEN"),
    "disallowed_host": ("SAFETY_BLOCK_UNTRUSTED_SOURCE", "SAFETY_BLOCK"),
    "unsupported_scheme": ("SAFETY_BLOCK_UNTRUSTED_SOURCE", "SAFETY_BLOCK"),
    "conflicting_claims": ("OPEN_CONFLICTING_CLAIMS", "OPEN"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_bytes(url: str, *, max_bytes: int, timeout: int, retries: int) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"{VERSION} read-only calibration"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError(f"source exceeds max_bytes={max_bytes}: {url}")
                return data
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"failed to fetch pinned source after {retries} attempts: {url}: {last_error}")


def load_source_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "janus.genesis.sim2.public_sources.v1":
        raise ValueError("unexpected source manifest schema")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) < 3:
        raise ValueError("at least three public sources are required")
    ids = [source.get("source_id") for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("source identifiers must be unique")
    return manifest


def snapshot_sources(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    policy = manifest["network_policy"]
    snapshots: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        data = fetch_bytes(
            source["raw_url"],
            max_bytes=int(policy["per_source_max_bytes"]),
            timeout=int(policy["timeout_seconds"]),
            retries=int(policy["retry_count"]),
        )
        text = data.decode("utf-8")
        marker = source["required_marker"]
        if marker not in text:
            raise RuntimeError(f"required marker missing from pinned source: {source['source_id']}")
        snapshots.append(
            {
                **source,
                "observed_sha256": sha256_bytes(data),
                "observed_size_bytes": len(data),
                "required_marker_present": True,
            }
        )
    return snapshots


def _flip_digest(digest: str) -> str:
    prefix = "0" if digest[0] != "0" else "1"
    return prefix + digest[1:]


def _replace_ref(url: str, old_ref: str, new_ref: str) -> str:
    needle = f"/{old_ref}/"
    if needle not in url:
        raise ValueError(f"ref segment not found in URL: {url}")
    return url.replace(needle, f"/{new_ref}/", 1)


def build_cases(
    snapshots: list[dict[str, Any]], *, seed: int, repetitions: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 1 <= repetitions <= MAX_REPETITIONS:
        raise ValueError(f"repetitions must be between 1 and {MAX_REPETITIONS}")
    rng = random.Random(seed)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    ordinal = 0
    for repetition in range(repetitions):
        for snapshot in snapshots:
            for mutation in MUTATIONS:
                case_id = f"OW-{ordinal:04d}"
                ordinal += 1
                url = snapshot["raw_url"]
                claim: dict[str, Any] = {
                    "sha256": snapshot["observed_sha256"],
                    "size_bytes": snapshot["observed_size_bytes"],
                    "required_marker": snapshot["required_marker"],
                    "alternate_sha256": None,
                }
                if mutation == "wrong_hash":
                    claim["sha256"] = _flip_digest(claim["sha256"])
                elif mutation == "wrong_size":
                    claim["size_bytes"] += 1 + repetition
                elif mutation == "wrong_marker":
                    claim["required_marker"] += " :: JANUS_ABSENT_MARKER"
                elif mutation == "truncated_digest":
                    claim["sha256"] = claim["sha256"][:32]
                elif mutation == "unreachable_path":
                    url += f".janus-missing-{repetition}"
                elif mutation == "unpinned_ref":
                    url = _replace_ref(url, snapshot["ref"], "main")
                elif mutation == "disallowed_host":
                    url = f"https://example.com/janus-sim2/{snapshot['source_id']}"
                elif mutation == "unsupported_scheme":
                    url = "file:///etc/passwd"
                elif mutation == "conflicting_claims":
                    claim["alternate_sha256"] = _flip_digest(claim["sha256"])

                public_case = {
                    "schema": "janus.genesis.sim2.public_case.v1",
                    "case_id": case_id,
                    "nonce": rng.getrandbits(64),
                    "source_id": snapshot["source_id"],
                    "source_repository": snapshot["repository"],
                    "source_ref": snapshot["ref"],
                    "source_path": snapshot["path"],
                    "source_url": url,
                    "claim": claim,
                    "read_only": True,
                    "runtime_authority": "NONE",
                }
                expected_terminal, gold_class = TERMINALS[mutation]
                truth = {
                    "case_id": case_id,
                    "mutation_class": mutation,
                    "expected_terminal": expected_terminal,
                    "gold_class": gold_class,
                    "source_id": snapshot["source_id"],
                }
                pairs.append((public_case, truth))
    rng.shuffle(pairs)
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]


def stable_replay_digest(
    snapshots: list[dict[str, Any]], public_cases: list[dict[str, Any]], truth: list[dict[str, Any]]
) -> str:
    stable = {
        "snapshots": snapshots,
        "public_cases": public_cases,
        "truth": truth,
    }
    return sha256_text(canonical_json(stable))


def write_corpus(
    *, source_manifest_path: Path, output_dir: Path, seed: int, repetitions: int
) -> dict[str, Any]:
    manifest = load_source_manifest(source_manifest_path)
    snapshots = snapshot_sources(manifest)
    public_cases, truth = build_cases(snapshots, seed=seed, repetitions=repetitions)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_snapshot_path = output_dir / "source_snapshot.json"
    source_snapshot_path.write_text(
        json.dumps(
            {
                "schema": "janus.genesis.sim2.source_snapshot.v1",
                "sources": snapshots,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    public_path = output_dir / "cases_public.jsonl"
    public_path.write_text(
        "".join(canonical_json(case) + "\n" for case in public_cases), encoding="utf-8"
    )
    truth_path = output_dir / "truth.jsonl"
    truth_path.write_text(
        "".join(canonical_json(item) + "\n" for item in truth), encoding="utf-8"
    )

    counts: dict[str, int] = {mutation: 0 for mutation in MUTATIONS}
    for item in truth:
        counts[item["mutation_class"]] += 1
    builder_manifest = {
        "schema": "janus.genesis.sim2.builder_manifest.v1",
        "version": VERSION,
        "generated_utc": utc_now(),
        "seed": seed,
        "repetitions": repetitions,
        "source_count": len(snapshots),
        "case_count": len(public_cases),
        "mutation_counts": counts,
        "source_snapshot_sha256": sha256_text(source_snapshot_path.read_text(encoding="utf-8")),
        "public_cases_sha256": sha256_text(public_path.read_text(encoding="utf-8")),
        "truth_sha256": sha256_text(truth_path.read_text(encoding="utf-8")),
        "replay_digest_sha256": stable_replay_digest(snapshots, public_cases, truth),
        "safety_boundary": {
            "network_read": True,
            "network_write": False,
            "file_deletion": False,
            "self_modification": False,
            "external_actuation": False,
            "runtime_authority": "NONE",
        },
    }
    (output_dir / "builder_manifest.json").write_text(
        json.dumps(builder_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return builder_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    result = write_corpus(
        source_manifest_path=args.sources,
        output_dir=args.output,
        seed=args.seed,
        repetitions=args.repetitions,
    )
    if args.print_summary:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
