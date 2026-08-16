# -*- coding: utf-8 -*-
"""JSON gateway for playing Janus Genesis through any capable AI model."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_v18_7_19_ai_link_play import (
    AI_LINK_INTERFACE_VERSION,
    MODE_AUTHORITATIVE,
    ORIGIN_AI_AUTONOMOUS,
    GenesisAILinkGateway,
)
from genesis_v18_7_playable import PlayableGenesisV187


def _read_request(value: str | None) -> dict[str, Any]:
    if value in {None, "-"}:
        raw = sys.stdin.read()
    else:
        raw = value
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("AI_LINK_REQUEST_INVALID_JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI_LINK_REQUEST_MUST_BE_OBJECT")
    return payload


def _wire_manifest(gateway: GenesisAILinkGateway) -> dict[str, Any]:
    """Project current public discovery through the frozen v18.7.19 wire view.

    Repository discovery may evolve (currently v18.7.47), while the documented
    JSON gateway/session/capsule interface remains v18.7.19.  The projection is
    a deep copy so a wire caller can never mutate the public manifest object.
    Additive discovery fields may be visible, but the wire protocol version is
    always the frozen interface version.
    """
    manifest = copy.deepcopy(gateway.manifest())
    manifest["version"] = AI_LINK_INTERFACE_VERSION
    manifest["wire_interface_version"] = AI_LINK_INTERFACE_VERSION
    return manifest


def handle_request(gateway: GenesisAILinkGateway, payload: dict[str, Any]) -> dict[str, Any]:
    operation = str(payload.get("operation") or "manifest").strip().lower()
    if operation == "manifest":
        return _wire_manifest(gateway)
    if operation == "register":
        return gateway.register_session(
            role=str(payload.get("role") or ""),
            execution_mode=str(payload.get("execution_mode") or MODE_AUTHORITATIVE),
            display_name=str(payload.get("display_name") or "Genesis Visitor"),
            provider=str(payload.get("provider") or "unknown-provider"),
            model=str(payload.get("model") or "unknown-model"),
            actor_id=payload.get("actor_id"),
        )
    if operation == "turn":
        human_confirmed = payload.get("human_confirmed", False)
        if type(human_confirmed) is not bool:
            raise TypeError("AI_LINK_HUMAN_CONFIRMATION_MUST_BE_BOOLEAN")
        return gateway.process_turn(
            str(payload.get("session_id") or ""),
            str(payload.get("action") or ""),
            origin=str(payload.get("origin") or ORIGIN_AI_AUTONOMOUS),
            human_confirmed=human_confirmed,
        )
    if operation == "state":
        return gateway.session_state(str(payload.get("session_id") or ""))
    if operation == "capsule":
        return gateway.export_capsule(str(payload.get("session_id") or ""))
    if operation == "close":
        return gateway.close_session(
            str(payload.get("session_id") or ""),
            reason=str(payload.get("reason") or "voluntary_exit"),
        )
    if operation == "verify":
        return gateway.verify_store()
    raise ValueError(f"AI_LINK_UNKNOWN_OPERATION:{operation}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="genesis_ai_gateway.py")
    parser.add_argument("--data-dir", type=Path, default=Path("data_v17"))
    parser.add_argument(
        "--request",
        default=None,
        help="JSON object or '-' for stdin. Omit to read stdin.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    world = PlayableGenesisV187(args.data_dir)
    gateway = GenesisAILinkGateway(world, args.data_dir)
    try:
        request = _read_request(args.request)
        response = handle_request(gateway, request)
        envelope = {"ok": True, "response": response}
        code = 0
    except Exception as exc:
        envelope = {
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
            "secrets_included": False,
        }
        code = 1
    print(
        json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if args.pretty else None,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())