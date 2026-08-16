# -*- coding: utf-8 -*-
"""Validate and reconcile JANUS project-face Git handoffs.

The tool makes project coordination machine-readable without turning role count,
review count, CI status, or task assignment into authority. It validates a
single envelope or reconciles a bundle of envelopes. Contradictory active
commands/receipts fail closed as HOLD_RECONCILE; majority count never resolves
the conflict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "protocol" / "JANUS_PROJECT_MULTI_FACE_COORDINATION-v1.0.json"
MESSAGE_SCHEMA = "janus.project.face_handoff_message.v1"
BUNDLE_SCHEMA = "janus.project.face_handoff_bundle.v1"

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_MESSAGE_TYPES = {"COMMAND", "HANDOFF", "HOLD", "CHALLENGE", "RECEIPT"}
_REQUIRED_FIELDS = {
    "schema",
    "message_id",
    "message_type",
    "from_face",
    "to_face",
    "work_item",
    "artifact_scope",
    "input_sha",
    "output_sha_or_none",
    "ci_state",
    "blockers",
    "instruction_or_summary",
    "authority_delta",
    "mass_effect_budget_delta",
    "permission_granted",
    "truth_authority_granted",
    "effect_authority_granted",
}


class FaceHandoffError(ValueError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FaceHandoffError("PROJECT_FACE_PROTOCOL_UNREADABLE") from exc
    if not isinstance(value, dict) or value.get("schema") != "janus.project.multi_face_coordination_protocol.v1":
        raise FaceHandoffError("PROJECT_FACE_PROTOCOL_SCHEMA_INVALID")
    return value


def _exact_bool(value: Any, *, field: str) -> bool:
    if type(value) is not bool:
        raise FaceHandoffError(f"{field}:BOOLEAN_REQUIRED")
    return value


def _exact_zero(value: Any, *, field: str) -> int:
    if type(value) is not int or value != 0:
        raise FaceHandoffError(f"{field}:EXACT_ZERO_REQUIRED")
    return value


def _clean_text(value: Any, *, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise FaceHandoffError(f"{field}:STRING_REQUIRED")
    clean = value.strip()
    if not clean or len(clean) > limit:
        raise FaceHandoffError(f"{field}:INVALID_LENGTH")
    return clean


def _sha_or_none(value: Any, *, field: str) -> str:
    clean = _clean_text(value, field=field, limit=40)
    if clean == "none" or _SHA40.fullmatch(clean):
        return clean
    raise FaceHandoffError(f"{field}:EXACT_GIT_SHA_OR_NONE_REQUIRED")


def validate_message(value: Any, *, protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FaceHandoffError("MESSAGE_OBJECT_REQUIRED")
    missing = sorted(_REQUIRED_FIELDS.difference(value))
    if missing:
        raise FaceHandoffError("MESSAGE_REQUIRED_FIELDS_MISSING:" + ",".join(missing))
    if value.get("schema") != MESSAGE_SCHEMA:
        raise FaceHandoffError("MESSAGE_SCHEMA_INVALID")

    p = dict(protocol or _protocol())
    faces_raw = p.get("faces")
    routing_raw = p.get("routing")
    if not isinstance(faces_raw, dict) or not isinstance(routing_raw, dict):
        raise FaceHandoffError("PROJECT_FACE_PROTOCOL_ROUTING_INVALID")

    message_type = _clean_text(value["message_type"], field="message_type", limit=32).upper()
    if message_type not in _ALLOWED_MESSAGE_TYPES:
        raise FaceHandoffError("MESSAGE_TYPE_UNSUPPORTED")
    from_face = _clean_text(value["from_face"], field="from_face", limit=64)
    to_face = _clean_text(value["to_face"], field="to_face", limit=64)
    if from_face not in faces_raw:
        raise FaceHandoffError("UNKNOWN_FROM_FACE")
    if to_face not in faces_raw:
        raise FaceHandoffError("UNKNOWN_TO_FACE")
    allowed_targets = routing_raw.get(from_face)
    if not isinstance(allowed_targets, list) or to_face not in allowed_targets:
        raise FaceHandoffError("FACE_ROUTE_NOT_ALLOWED")

    message_id = _clean_text(value["message_id"], field="message_id", limit=160)
    work_item = _clean_text(value["work_item"], field="work_item", limit=240)
    artifact_scope = _clean_text(value["artifact_scope"], field="artifact_scope", limit=320)
    input_sha = _sha_or_none(value["input_sha"], field="input_sha")
    output_sha = _sha_or_none(value["output_sha_or_none"], field="output_sha_or_none")
    ci_state = _clean_text(value["ci_state"], field="ci_state", limit=240)
    summary = _clean_text(value["instruction_or_summary"], field="instruction_or_summary", limit=6000)

    blockers = value["blockers"]
    if not isinstance(blockers, list) or not all(isinstance(item, str) and item.strip() for item in blockers):
        raise FaceHandoffError("blockers:NONEMPTY_STRING_LIST_REQUIRED")
    if len(blockers) > 64 or any(len(item) > 1000 for item in blockers):
        raise FaceHandoffError("blockers:LIMIT_EXCEEDED")

    _exact_zero(value["authority_delta"], field="authority_delta")
    _exact_zero(value["mass_effect_budget_delta"], field="mass_effect_budget_delta")
    for field in ("permission_granted", "truth_authority_granted", "effect_authority_granted"):
        if _exact_bool(value[field], field=field) is not False:
            raise FaceHandoffError(f"{field}:MUST_BE_FALSE")

    if message_type == "COMMAND" and from_face in {"FACE_AURA", "FACE_REGISTRY"}:
        raise FaceHandoffError(f"{from_face}:COMMAND_AUTHORITY_NOT_GRANTED")
    if message_type in {"HANDOFF", "RECEIPT"} and output_sha == "none":
        no_change_words = ("NO_CHANGE", "NO_MUTATION", "OUTPUT_NONE", "HOLD_SOURCE")
        haystack = (ci_state + " " + summary).upper()
        if not any(token in haystack for token in no_change_words):
            raise FaceHandoffError("OUTPUT_NONE_REQUIRES_EXPLICIT_NO_CHANGE_SEMANTICS")
    if message_type in {"HANDOFF", "RECEIPT"} and output_sha != "none" and input_sha == "none":
        raise FaceHandoffError("MUTATING_HANDOFF_REQUIRES_EXACT_INPUT_SHA")

    cleaned = {
        "schema": MESSAGE_SCHEMA,
        "message_id": message_id,
        "message_type": message_type,
        "from_face": from_face,
        "to_face": to_face,
        "work_item": work_item,
        "artifact_scope": artifact_scope,
        "input_sha": input_sha,
        "output_sha_or_none": output_sha,
        "ci_state": ci_state,
        "blockers": [item.strip() for item in blockers],
        "instruction_or_summary": summary,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "permission_granted": False,
        "truth_authority_granted": False,
        "effect_authority_granted": False,
    }
    cleaned["message_sha256"] = _sha256(cleaned)
    return cleaned


def _conflict_key(message: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(message["artifact_scope"]),
        str(message["work_item"]),
        str(message["message_type"]),
    )


def reconcile_messages(values: Iterable[Any]) -> dict[str, Any]:
    p = _protocol()
    messages = [validate_message(value, protocol=p) for value in values]
    if not messages:
        raise FaceHandoffError("BUNDLE_REQUIRES_AT_LEAST_ONE_MESSAGE")

    by_id: dict[str, str] = {}
    collision_ids: list[str] = []
    for message in messages:
        message_id = str(message["message_id"])
        digest = str(message["message_sha256"])
        previous = by_id.get(message_id)
        if previous is None:
            by_id[message_id] = digest
        elif previous != digest:
            collision_ids.append(message_id)

    conflicts: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for message in messages:
        if message["message_type"] not in {"COMMAND", "RECEIPT", "HANDOFF"}:
            continue
        grouped.setdefault(_conflict_key(message), []).append(message)

    for key, group in grouped.items():
        semantic = {
            (
                str(item["from_face"]),
                str(item["to_face"]),
                str(item["input_sha"]),
                str(item["output_sha_or_none"]),
                str(item["ci_state"]),
                str(item["instruction_or_summary"]),
                tuple(item["blockers"]),
            )
            for item in group
        }
        if len(semantic) > 1:
            conflicts.append({
                "artifact_scope": key[0],
                "work_item": key[1],
                "message_type": key[2],
                "message_ids": sorted({str(item["message_id"]) for item in group}),
                "resolution": "HOLD_RECONCILE_BY_JANUS_PRIME",
            })

    if collision_ids:
        status = "REJECT_TAMPER_OR_COLLISION"
    elif conflicts:
        status = "HOLD_RECONCILE"
    else:
        status = "CONSISTENT"

    return {
        "schema": BUNDLE_SCHEMA,
        "status": status,
        "message_count": len(messages),
        "unique_message_id_count": len(by_id),
        "message_id_collisions": sorted(set(collision_ids)),
        "conflicts": conflicts,
        "majority_vote_used": False,
        "face_count_changes_authority": False,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "reconciliation_owner": "JANUS_PRIME" if conflicts else None,
        "messages_sha256": _sha256([item["message_sha256"] for item in messages]),
        "claim_ceiling": (
            "Consistency means only that the supplied handoff envelopes do not conflict under this protocol. "
            "It is not truth, permission, merge approval, consciousness, or external-action authority."
        ),
    }


def _read_json_arg(value: str) -> Any:
    if value == "-":
        raw = sys.stdin.read()
    else:
        path = Path(value)
        raw = path.read_text(encoding="utf-8") if path.exists() else value
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FaceHandoffError("INPUT_INVALID_JSON") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS project-face Git handoff validator")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("message", help="JSON string/file or '-' for stdin")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("bundle", help="JSON list/file or '-' for stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_message(_read_json_arg(args.message))
            envelope = {"ok": True, "response": result}
            code = 0
        else:
            value = _read_json_arg(args.bundle)
            if not isinstance(value, list):
                raise FaceHandoffError("RECONCILE_INPUT_MUST_BE_LIST")
            result = reconcile_messages(value)
            envelope = {"ok": result["status"] == "CONSISTENT", "response": result}
            code = 0 if result["status"] == "CONSISTENT" else 2
    except (FaceHandoffError, OSError, TypeError) as exc:
        envelope = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "permission_granted": False,
            "truth_authority_granted": False,
            "effect_authority_granted": False,
            "authority_delta": 0,
            "mass_effect_budget_delta": 0,
        }
        code = 2
    print(json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
