#!/usr/bin/env python3
"""Fail-closed validator for JANUS project-sync / Many Faces command packets.

Each command is replayed against the exact project-state snapshot it names. A
separate CURRENT pointer identifies which append-only snapshot governs new work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PROTOCOL_PATH = Path("protocol/JANUS_MANY_FACES_GIT_COORDINATION-v1.0.json")
CURRENT_PATH = Path("project_sync/CURRENT.json")
COMMAND_ROOT = Path("project_sync/commands")

FORBIDDEN_DURING_GLOBAL_HOLD = (
    "merge",
    "force push",
    "force-push",
    "force_push",
    "delete repository",
    "repository admin",
    "admin permission",
    "bypass protected",
    "bypass branch protection",
    "destructive operation",
)


class ProjectSyncError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProjectSyncError(f"INVALID_JSON:{path}:{type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise ProjectSyncError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # Git object identity, not truth proof.


def _safe_repo_path(root: Path, raw: str) -> Path:
    rel = Path(str(raw))
    if rel.is_absolute() or ".." in rel.parts:
        raise ProjectSyncError(f"STATE_BINDING_PATH_ESCAPE:{raw}")
    if not rel.as_posix().startswith("project_sync/PROJECT_SYNC_STATE") or rel.suffix != ".json":
        raise ProjectSyncError(f"STATE_BINDING_PATH_NOT_PROJECT_SNAPSHOT:{raw}")
    path = root / rel
    if not path.is_file():
        raise ProjectSyncError(f"BOUND_STATE_MISSING:{raw}")
    return path


def _check_binding(root: Path, binding: dict[str, Any], accepted_algorithms: set[str], binding_required: set[str]) -> tuple[Path, dict[str, Any]]:
    missing = binding_required - set(binding)
    if missing:
        raise ProjectSyncError(f"BINDING_FIELDS_MISSING:{','.join(sorted(missing))}")
    algorithm = str(binding.get("algorithm") or "")
    value = str(binding.get("value") or "")
    raw_path = str(binding.get("path") or "")
    if algorithm not in accepted_algorithms:
        raise ProjectSyncError(f"BINDING_ALGORITHM_NOT_ALLOWED:{algorithm}")
    state_path = _safe_repo_path(root, raw_path)
    if algorithm == "git_blob_sha":
        expected = git_blob_sha(state_path)
        if value != expected:
            raise ProjectSyncError(f"BINDING_GIT_BLOB_MISMATCH:{raw_path}:{value}:{expected}")
    elif algorithm == "sha256":
        expected = hashlib.sha256(state_path.read_bytes()).hexdigest()
        if value != expected:
            raise ProjectSyncError(f"BINDING_SHA256_MISMATCH:{raw_path}:{value}:{expected}")
    return state_path, load_json(state_path)


def validate(
    protocol_path: Path = PROTOCOL_PATH,
    current_path: Path = CURRENT_PATH,
    command_root: Path = COMMAND_ROOT,
    project_root: Path = Path("."),
) -> dict[str, Any]:
    root = project_root.resolve()
    protocol = load_json(protocol_path)
    current = load_json(current_path)

    faces = {
        row["face_id"]: row
        for row in protocol.get("faces", [])
        if isinstance(row, dict) and row.get("face_id")
    }
    if not faces:
        raise ProjectSyncError("NO_FACES_DEFINED")

    packet = protocol.get("command_packet")
    if not isinstance(packet, dict):
        raise ProjectSyncError("COMMAND_PACKET_CONTRACT_MISSING")
    required = set(packet.get("required_fields") or [])
    authority_classes = set(packet.get("authority_classes") or [])
    settlement_states = set(packet.get("settlement_states") or [])
    binding_contract = packet.get("project_sync_state_binding") or {}
    accepted_algorithms = set(binding_contract.get("accepted_algorithms") or [])
    binding_required = set(binding_contract.get("required_fields") or [])

    current_raw_path = str(current.get("state_path") or "")
    current_state_path = _safe_repo_path(root, current_raw_path)
    current_blob = git_blob_sha(current_state_path)
    if str(current.get("git_blob_sha") or "") != current_blob:
        raise ProjectSyncError(
            f"CURRENT_POINTER_BLOB_MISMATCH:{current.get('git_blob_sha')}:{current_blob}"
        )
    current_state = load_json(current_state_path)
    if current.get("snapshot_id") != current_state.get("snapshot_id"):
        raise ProjectSyncError("CURRENT_POINTER_SNAPSHOT_ID_MISMATCH")

    seen_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    paths = sorted(command_root.rglob("*.json"))
    if not paths:
        raise ProjectSyncError("NO_COMMAND_PACKETS")

    for path in paths:
        cmd = load_json(path)
        missing = sorted(required - set(cmd))
        if missing:
            raise ProjectSyncError(f"COMMAND_REQUIRED_FIELDS_MISSING:{path}:{','.join(missing)}")

        command_id = str(cmd.get("command_id") or "")
        if not command_id or command_id in seen_ids:
            raise ProjectSyncError(f"COMMAND_ID_INVALID_OR_DUPLICATE:{path}:{command_id}")
        seen_ids.add(command_id)

        source = str(cmd.get("from_face") or "")
        target = str(cmd.get("to_face") or "")
        if source not in faces:
            raise ProjectSyncError(f"UNKNOWN_SOURCE_FACE:{path}:{source}")
        if target not in faces:
            raise ProjectSyncError(f"UNKNOWN_TARGET_FACE:{path}:{target}")

        command_type = str(cmd.get("command_type") or "")
        if command_type not in set(faces[source].get("may_issue") or []):
            raise ProjectSyncError(f"SOURCE_FACE_CANNOT_ISSUE_TYPE:{path}:{source}:{command_type}")

        authority = str(cmd.get("authority_class") or "")
        if authority not in authority_classes:
            raise ProjectSyncError(f"UNKNOWN_AUTHORITY_CLASS:{path}:{authority}")

        settlement = str(cmd.get("settlement_state") or "")
        if settlement not in settlement_states:
            raise ProjectSyncError(f"UNKNOWN_SETTLEMENT_STATE:{path}:{settlement}")

        if cmd.get("effect_executed") is not False:
            raise ProjectSyncError(f"COMMAND_PACKET_MAY_NOT_SELF_ASSERT_EFFECT:{path}")

        binding = cmd.get("project_sync_state_binding")
        if not isinstance(binding, dict):
            raise ProjectSyncError(f"BINDING_NOT_OBJECT:{path}")
        try:
            bound_state_path, bound_state = _check_binding(
                root, binding, accepted_algorithms, binding_required
            )
        except ProjectSyncError as exc:
            raise ProjectSyncError(f"{exc}:{path}") from exc

        global_hold = str(bound_state.get("global_state", "")).startswith("HOLD")
        combined = json.dumps(
            {
                "type": command_type,
                "requested_action": cmd.get("requested_action"),
                "scope": cmd.get("scope"),
            },
            ensure_ascii=False,
        ).lower()
        if global_hold and any(term in combined for term in FORBIDDEN_DURING_GLOBAL_HOLD):
            action = str(cmd.get("requested_action") or "").lower()
            protective = any(
                marker in action
                for marker in ("do not", "without", "forbid", "must not", "not merge", "no merge")
            )
            if not protective:
                raise ProjectSyncError(f"GLOBAL_HOLD_FORBIDS_REQUESTED_EFFECT:{path}")

        validated.append(
            {
                "command_id": command_id,
                "from_face": source,
                "to_face": target,
                "command_type": command_type,
                "authority_class": authority,
                "settlement_state": settlement,
                "bound_snapshot_id": bound_state.get("snapshot_id"),
                "bound_state_path": bound_state_path.relative_to(root).as_posix(),
                "is_current_state_binding": bound_state_path.resolve() == current_state_path.resolve(),
            }
        )

    return {
        "status": "PASS",
        "current_snapshot_id": current_state.get("snapshot_id"),
        "current_global_state": current_state.get("global_state"),
        "current_project_state_git_blob_sha": current_blob,
        "faces": len(faces),
        "commands": len(validated),
        "validated_commands": validated,
        "authority_growth": 0,
        "independent_evidence_created_by_face_count": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--current", type=Path, default=CURRENT_PATH)
    parser.add_argument("--commands", type=Path, default=COMMAND_ROOT)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        result = validate(args.protocol, args.current, args.commands, args.root)
    except ProjectSyncError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
