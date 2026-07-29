#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic wrapper that preserves fail-closed audit behavior and exposes final gate locals."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.run_century_lived_audit import run


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
        summary = run(args.output_dir, args.git_commit)
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
