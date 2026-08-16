#!/usr/bin/env python3
"""Validate the append-only JANUS project-sync state ledger.

This is deliberately an additive layer over the canonical
`janus_project_face_handoff` protocol.  It does not define faces, routes,
authority, permissions or conflict semantics a second time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tools.janus_project_face_handoff import validate_message

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "project_sync" / "CURRENT.json"
MESSAGES = ROOT / "project_sync" / "messages"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ACTIVE_TYPES = {"COMMAND", "HOLD", "CHALLENGE"}


class ProjectSyncStateError(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectSyncStateError(f"INVALID_JSON:{path.as_posix()}") from exc
    if not isinstance(value, dict):
        raise ProjectSyncStateError(f"JSON_OBJECT_REQUIRED:{path.as_posix()}")
    return value


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _safe_state_path(raw: Any, *, root: Path) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ProjectSyncStateError("CURRENT_STATE_PATH_REQUIRED")
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise ProjectSyncStateError("CURRENT_STATE_PATH_ESCAPE")
    if len(rel.parts) < 3 or rel.parts[0] != "project_sync" or rel.parts[1] != "states" or rel.suffix != ".json":
        raise ProjectSyncStateError("CURRENT_STATE_PATH_NOT_LEDGER_STATE")
    path = root / rel
    if not path.is_file():
        raise ProjectSyncStateError("CURRENT_STATE_FILE_MISSING")
    return path


def validate_ledger(
    *,
    root: Path = ROOT,
    current_path: Path | None = None,
    messages_root: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    current_path = (current_path or (root / "project_sync" / "CURRENT.json")).resolve()
    messages_root = (messages_root or (root / "project_sync" / "messages")).resolve()

    current = _json(current_path)
    if current.get("schema") != "janus.project_sync.current_pointer.v1":
        raise ProjectSyncStateError("CURRENT_SCHEMA_INVALID")
    state_path = _safe_state_path(current.get("state_path"), root=root)
    state = _json(state_path)
    if state.get("schema") != "janus.project_sync.state.v1":
        raise ProjectSyncStateError("STATE_SCHEMA_INVALID")
    if current.get("snapshot_id") != state.get("snapshot_id"):
        raise ProjectSyncStateError("CURRENT_SNAPSHOT_ID_MISMATCH")

    expected_blob = git_blob_sha(state_path)
    if current.get("git_blob_sha") != expected_blob:
        raise ProjectSyncStateError("CURRENT_GIT_BLOB_SHA_MISMATCH")

    main_sha = current.get("state_main_sha")
    if not isinstance(main_sha, str) or not _SHA40.fullmatch(main_sha):
        raise ProjectSyncStateError("CURRENT_MAIN_SHA_INVALID")
    state_main = state.get("janus_genesis", {}).get("default_branch_sha")
    if state_main != main_sha:
        raise ProjectSyncStateError("CURRENT_MAIN_SHA_STATE_MISMATCH")

    canonical = state.get("canonical_coordination")
    if not isinstance(canonical, dict):
        raise ProjectSyncStateError("CANONICAL_COORDINATION_RECEIPT_MISSING")
    if canonical.get("protocol_path") != "protocol/JANUS_PROJECT_MULTI_FACE_COORDINATION-v1.0.json":
        raise ProjectSyncStateError("CANONICAL_PROTOCOL_POINTER_INVALID")
    if canonical.get("validator_path") != "tools/janus_project_face_handoff.py":
        raise ProjectSyncStateError("CANONICAL_VALIDATOR_POINTER_INVALID")

    message_paths = sorted(messages_root.rglob("*.json")) if messages_root.is_dir() else []
    if not message_paths:
        raise ProjectSyncStateError("PROJECT_SYNC_MESSAGES_MISSING")

    validated: list[dict[str, Any]] = []
    ids: set[str] = set()
    for path in message_paths:
        raw = _json(path)
        message = validate_message(raw)
        mid = message["message_id"]
        if mid in ids:
            raise ProjectSyncStateError(f"DUPLICATE_MESSAGE_ID:{mid}")
        ids.add(mid)

        if message["message_type"] in _ACTIVE_TYPES and message["input_sha"] != main_sha:
            raise ProjectSyncStateError(f"ACTIVE_MESSAGE_NOT_BOUND_TO_CURRENT_MAIN:{mid}")
        validated.append({
            "message_id": mid,
            "type": message["message_type"],
            "from_face": message["from_face"],
            "to_face": message["to_face"],
            "input_sha": message["input_sha"],
            "message_sha256": message["message_sha256"],
        })

    return {
        "schema": "janus.project_sync.ledger_validation.v1",
        "status": "PASS",
        "snapshot_id": state["snapshot_id"],
        "global_state": state.get("global_state"),
        "state_main_sha": main_sha,
        "state_git_blob_sha": expected_blob,
        "message_count": len(validated),
        "messages": validated,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "permission_granted": False,
        "truth_authority_granted": False,
        "effect_authority_granted": False,
        "claim_ceiling": "A valid ledger proves internal binding/format consistency only; it is not project truth, merge permission, independent evidence, consciousness, or external-effect authority."
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = validate_ledger(root=args.root)
    except (ProjectSyncStateError, ValueError) as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
            "authority_delta": 0,
            "permission_granted": False,
            "truth_authority_granted": False,
            "effect_authority_granted": False,
        }, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "response": result}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
