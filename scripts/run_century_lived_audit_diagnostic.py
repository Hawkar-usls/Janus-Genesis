#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed century runner with explicit diagnostic output on evidence-gate failure."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts import run_century_lived_audit as base


def select_contextual_matched_probe_action(world: Any, handle: str) -> tuple[str, int]:
    """Select one action between v18.7.1 low/high contextual-consent thresholds."""
    store = world._free_store()
    upcoming = int(store["world_turn"]) + 1
    for index in range(4096):
        action = f"предложить @{handle} пройти контрольный мост {index} без общего финала"
        fingerprint = world._free_fingerprint(action)
        topic = world._dialogue_topic(action)
        gate = world._free_number(
            store,
            base.PLAYER_ID,
            handle,
            upcoming,
            fingerprint,
            topic,
            "contextual-consent",
        ) % 100
        if 34 <= gate < 58:
            return action, gate
    raise RuntimeError("MATCHED_CONTEXTUAL_TRUST_PROBE_ACTION_NOT_FOUND")


base.select_matched_probe_action = select_contextual_matched_probe_action


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return repr(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", default="unknown")
    args = parser.parse_args()
    try:
        summary = base.run(args.output_dir, args.git_commit)
    except RuntimeError as error:
        traceback = error.__traceback__
        while traceback is not None and traceback.tb_next is not None:
            traceback = traceback.tb_next
        locals_map = {} if traceback is None else traceback.tb_frame.f_locals
        diagnostic = {
            "error": str(error),
            "low_values": _json_safe(locals_map.get("low_values")),
            "high_values": _json_safe(locals_map.get("high_values")),
            "butterfly": _json_safe(locals_map.get("butterfly")),
            "v1810_valid": _json_safe(locals_map.get("v1810_valid")),
            "chronicle_valid": _json_safe(locals_map.get("chronicle_valid")),
            "graph_valid": _json_safe(locals_map.get("graph_valid")),
            "proofpack_valid": _json_safe(locals_map.get("proofpack_valid")),
            "summary": _json_safe(locals_map.get("summary")),
        }
        print("CENTURY_AUDIT_DIAGNOSTIC=" + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True))
        raise
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
