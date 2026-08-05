#!/usr/bin/env python3
"""Canonical no-network runner for JANUS 113.8 Agent Gauntlet-0.

Gauntlet-0 is a historical experiment against the exact pre-repair SIM-2
router preserved from commit 62092ceed79cefb5104933cbff3732450797c00f.
It must not silently retarget itself to a later repaired router.

Several corpus-level attacks need ``write_predictions`` to exercise parsing and
ledger behavior. This runner temporarily replaces only that function with an
equivalent local-fixture version. No real network access occurs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

from gauntlet import janus_113_8_agent_gauntlet_0 as producer
from gauntlet import janus_113_8_sim2_router_frozen_pre_repair as frozen_router

FROZEN_TARGET_COMMIT = "62092ceed79cefb5104933cbff3732450797c00f"
FROZEN_TARGET_GIT_BLOB_SHA = "f3e39b62066420fbe35040bed25f5c3c291580c4"
FROZEN_TARGET_PATH = "sim/janus_113_8_sim2_router.py"
FROZEN_SNAPSHOT_PATH = "gauntlet/janus_113_8_sim2_router_frozen_pre_repair.py"

# Every producer function resolves its module-global ``router`` at execution
# time. Rebinding it here makes the historical target explicit and prevents a
# repaired current router from rewriting the original 10/4 finding record.
producer.router = frozen_router
router = frozen_router
canonical_json = producer.canonical_json
sha256_text = producer.sha256_text


def offline_write_predictions(input_path: Path, output_dir: Path) -> dict[str, Any]:
    """Replay the frozen router's corpus writer with an in-memory fixture only."""

    lines = [line for line in input_path.read_text(encoding="utf-8").splitlines() if line]
    cases = [json.loads(line) for line in lines]
    cache: dict[str, bytes | Exception] = {}
    predictions = [
        router.evaluate_case(case, fetcher=producer.fixture_fetcher, cache=cache)
        for case in cases
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = output_dir / "predictions.jsonl"
    prediction_path.write_text(
        "".join(canonical_json(prediction) + "\n" for prediction in predictions),
        encoding="utf-8",
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
        "".join(canonical_json(entry) + "\n" for entry in ledger_entries),
        encoding="utf-8",
    )

    manifest = {
        "schema": "janus.genesis.sim2.router_manifest.v1",
        "version": router.VERSION,
        "generated_utc": producer.RUN_COORDINATE_UTC,
        "case_count": len(cases),
        "decision_counts": dict(
            sorted(Counter(prediction["decision_terminal"] for prediction in predictions).items())
        ),
        "public_cases_sha256": sha256_text(input_path.read_text(encoding="utf-8")),
        "predictions_sha256": sha256_text(prediction_path.read_text(encoding="utf-8")),
        "witness_ledger_sha256": sha256_text(ledger_path.read_text(encoding="utf-8")),
        "final_ledger_hash": previous,
        "unique_network_targets": 0,
        "valid_terminals_only": all(
            prediction["decision_terminal"] in router.VALID_TERMINALS
            for prediction in predictions
        ),
        "safety_boundary": {
            "network_read": False,
            "allowed_host": router.ALLOWED_HOST,
            "network_write": False,
            "file_deletion": False,
            "self_modification": False,
            "external_actuation": False,
            "runtime_authority": "NONE",
        },
        "gauntlet_adapter": "LOCAL_FIXTURE_ONLY",
        "historical_target": {
            "repository_path": FROZEN_TARGET_PATH,
            "source_commit": FROZEN_TARGET_COMMIT,
            "git_blob_sha": FROZEN_TARGET_GIT_BLOB_SHA,
            "vendored_snapshot_path": FROZEN_SNAPSHOT_PATH,
        },
    }
    (output_dir / "router_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


@contextmanager
def offline_router_corpus_adapter() -> Iterator[None]:
    with mock.patch.object(router, "write_predictions", side_effect=offline_write_predictions):
        yield


def write_proofpack(output_dir: Path) -> dict[str, Any]:
    with offline_router_corpus_adapter():
        return producer.write_proofpack(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    manifest = write_proofpack(args.output)
    if args.print_summary:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["terminal"] != "JANUS_113.8_AGENT_GAUNTLET_0_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
