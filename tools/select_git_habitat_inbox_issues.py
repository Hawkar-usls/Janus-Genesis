# -*- coding: utf-8 -*-
"""Select GitHub issues that may enter the JANUS Git Habitat inbox.

Selection is routing only. Matching issue text remains an untrusted letter and
never acquires command or external-effect authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FACE_PREFIXES = ("[JANUS FACE:", "[JANUS FACE COUNCIL]")
INBOX_LABEL = "janus-inbox"


def _label_names(row: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    labels = row.get("labels", [])
    if not isinstance(labels, list):
        return names
    for label in labels:
        if isinstance(label, str):
            names.add(label)
        elif isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
    return names


def is_habitat_inbox_issue(row: dict[str, Any]) -> bool:
    title = str(row.get("title") or "")
    if INBOX_LABEL in _label_names(row):
        return True
    return any(title.startswith(prefix) for prefix in FACE_PREFIXES)


def select_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not is_habitat_inbox_issue(row):
            continue
        selected.append(
            {
                "number": row.get("number"),
                "title": row.get("title"),
                "body": row.get("body"),
                "url": row.get("url"),
                "updatedAt": row.get("updatedAt"),
            }
        )
    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select non-authoritative Git Habitat inbox issues")
    parser.add_argument("--issues-json", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = json.loads(Path(args.issues_json).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("issues JSON must be an array")
    selected = select_rows(rows)
    Path(args.output).write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "HABITAT_INBOX_SELECTION_COMPLETE",
        "candidate_count": len(rows),
        "selected_count": len(selected),
        "selection_creates_command_authority": False,
        "selection_creates_external_effect_authority": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
