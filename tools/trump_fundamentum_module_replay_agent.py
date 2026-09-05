#!/usr/bin/env python3
"""Deterministic, read-only replay of a whitelisted Janus-Fundamentum experiment module.

This is a generic executor for proof-carrying TRUMP research gates. It imports
one experiment module from the checked-out read-only source branch and invokes
its zero-argument ``run()`` function. No shell, network or source write is
performed here. The result is wrapped in the same fail-closed Habitat receipt
contract used by the TRUMP research bridge.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LANE_ID = "JANUS_TRUMP_FUNDAMENTUM_MODULE_REPLAY"
MODULE_RE = re.compile(r"^janus_trump_r[0-9]+[a-z0-9_]*$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--habitat-root", required=True)
    args = ap.parse_args()

    request_path = Path(args.request)
    workspace = Path(args.workspace)
    habitat = Path(args.habitat_root)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(request.get("request_id") or request_path.stem))[:120]

    if request.get("status") != "QUEUED":
        raise ValueError("TRUMP_MODULE_REPLAY_REQUEST_NOT_QUEUED")
    if request.get("purpose") != "PARALLEL_TRUMP_MODULE_REPLAY":
        raise ValueError("TRUMP_MODULE_REPLAY_WRONG_PURPOSE")
    if request.get("source_repo") != "Hawkar-usls/Janus-Fundamentum":
        raise ValueError("TRUMP_MODULE_REPLAY_WRONG_REPOSITORY")

    module_name = str(request.get("target_module") or "").strip()
    if not MODULE_RE.fullmatch(module_name):
        raise ValueError(f"TRUMP_MODULE_REPLAY_MODULE_NOT_WHITELISTED:{module_name}")

    experiments = workspace / "experiments"
    if not experiments.is_dir():
        raise RuntimeError(f"TRUMP_MODULE_REPLAY_EXPERIMENTS_MISSING:{experiments}")
    for path in (str(workspace), str(experiments)):
        if path not in sys.path:
            sys.path.insert(0, path)

    module = importlib.import_module(module_name)
    run = getattr(module, "run", None)
    if not callable(run):
        raise ValueError(f"TRUMP_MODULE_REPLAY_RUN_MISSING:{module_name}")

    report = run()
    if not isinstance(report, dict):
        raise TypeError("TRUMP_MODULE_REPLAY_REPORT_NOT_OBJECT")
    report = dict(report)
    report["proof_claim"] = False
    report["p_vs_np"] = "OPEN"
    report["sat_in_p"] = "NOT_PROVED"
    report["module_replay_status"] = "EXECUTED"

    receipt = {
        "schema": "janus.genesis.trump_module_replay_receipt.v1",
        "lane_id": LANE_ID,
        "request_id": request_id,
        "processed_at_utc": utc_now(),
        "source_repo": request.get("source_repo"),
        "source_branch": request.get("source_branch"),
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "target_module": module_name,
        "engine": "DETERMINISTIC_FUNDAMENTUM_MODULE_REPLAY",
        "authority": "RESEARCH_HYPOTHESIS_ONLY",
        "truth_boundary": {
            "model_output_is_proof": False,
            "model_output_is_independent_confirmation": False,
            "deterministic_finite_search_is_universal_proof": False,
            "p_vs_np": "OPEN",
            "sat_in_p": "NOT_PROVED"
        },
        "report": report,
    }

    outbox = habitat / "outbox" / "trump" / f"{request_id}.json"
    memory = habitat / "memory" / "trump" / f"{utc_now().replace(':', '-')}_{request_id}.json"
    write_json(outbox, receipt)
    write_json(memory, receipt)
    print(f"TRUMP_MODULE_REPLAY_RECEIPT={outbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
