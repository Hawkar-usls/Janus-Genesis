# -*- coding: utf-8 -*-
"""Import GitHub issue JSON into JANUS Git Habitat inbox.

This bridge is intentionally receive-only. Issue text becomes an untrusted
letter; it never becomes command authority or external-effect authorization.
Edited issues are preserved as distinct revisions rather than silently
rewriting an earlier letter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.genesis_git_habitat import GitHabitat


def _safe_issue_id(number: Any, updated_at: Any = None) -> str:
    value = int(number)
    if value < 1:
        raise ValueError("Issue number must be positive")
    if updated_at in (None, ""):
        return f"github-issue-{value}"
    revision = hashlib.sha256(str(updated_at).encode("utf-8")).hexdigest()[:12]
    return f"github-issue-{value}-{revision}"


def import_issue_rows(habitat: GitHabitat, rows: list[dict[str, Any]]) -> dict[str, Any]:
    imported = 0
    replayed = 0
    rejected = 0
    for row in rows:
        try:
            issue_id = _safe_issue_id(row.get("number"), row.get("updatedAt"))
            title = str(row.get("title") or "")
            body = str(row.get("body") or "")
            url = str(row.get("url") or "") or None
            path = habitat.paths.root / "inbox" / f"{issue_id}.json"
            existed = path.exists()
            habitat.receive_letter(
                issue_id,
                title,
                body,
                source="GITHUB_ISSUE",
                source_ref=url,
            )
            if existed:
                replayed += 1
            else:
                imported += 1
        except (TypeError, ValueError):
            rejected += 1
    return {
        "status": "ISSUE_INBOX_SYNC_COMPLETE",
        "imported": imported,
        "replayed": replayed,
        "rejected": rejected,
        "command_authority_granted": False,
        "external_effect_authority_granted": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync GitHub issues into JANUS Habitat inbox")
    parser.add_argument("--root", default="habitat")
    parser.add_argument("--issues-json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = json.loads(Path(args.issues_json).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("issues JSON must be an array")
    habitat = GitHabitat(args.root)
    result = import_issue_rows(habitat, rows)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
