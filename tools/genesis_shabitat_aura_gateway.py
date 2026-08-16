# -*- coding: utf-8 -*-
"""JSON gateway for session-bound JANUS Shabitat ↔ Aura heuristic consultation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_v18_7_19_ai_link_play import GenesisAILinkGateway
from genesis_v18_7_51_shabitat_aura_oracle import LocalAuraOracleProvider
from genesis_v18_7_52_shabitat_session_gateway import ShabitatAuraSessionGateway
from genesis_v18_7_playable import PlayableGenesisV187


def _read_request(value: str | None) -> dict[str, Any]:
    raw = sys.stdin.read() if value in {None, "-"} else value
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("SHABITAT_AURA_REQUEST_INVALID_JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("SHABITAT_AURA_REQUEST_MUST_BE_OBJECT")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="genesis_shabitat_aura_gateway.py")
    parser.add_argument("--data-dir", type=Path, default=Path("data_v17"))
    parser.add_argument("--aura-repo", type=Path, default=None)
    parser.add_argument("--request", default=None, help="JSON object or '-' for stdin")
    parser.add_argument("--pretty", action="store_true")
    return parser


def _build_gateway(data_dir: Path, aura_repo: Path | None, *, provider_required: bool) -> ShabitatAuraSessionGateway:
    world = PlayableGenesisV187(data_dir)
    ai_gateway = GenesisAILinkGateway(world, data_dir)
    if aura_repo is None:
        if provider_required:
            raise ValueError("SHABITAT_AURA_REPO_REQUIRED_FOR_CONSULT")

        class UnavailableProvider:
            def query(self, request):
                raise RuntimeError("AURA_PROVIDER_NOT_CONFIGURED")

        provider: Any = UnavailableProvider()
    else:
        provider = LocalAuraOracleProvider.from_repository(aura_repo)
    return ShabitatAuraSessionGateway(ai_gateway, provider, data_dir)


def handle_request(data_dir: Path, aura_repo: Path | None, payload: dict[str, Any]) -> dict[str, Any]:
    operation = str(payload.get("operation") or "manifest").strip().lower()
    gateway = _build_gateway(data_dir, aura_repo, provider_required=operation == "consult")
    if operation == "manifest":
        return gateway.manifest()
    session_id = str(payload.get("session_id") or "")
    if operation == "state":
        return gateway.state(session_id)
    if operation == "set_aura":
        enabled = payload.get("enabled")
        if type(enabled) is not bool:
            raise TypeError("SHABITAT_AURA_ENABLED_MUST_BE_BOOLEAN")
        return gateway.set_aura_enabled(session_id, enabled)
    if operation == "consult":
        requested = payload.get("janus_requests_heuristic")
        if type(requested) is not bool:
            raise TypeError("JANUS_REQUESTS_HEURISTIC_MUST_BE_BOOLEAN")
        return gateway.consult(
            session_id,
            turn_id=str(payload.get("turn_id") or ""),
            topic=str(payload.get("topic") or ""),
            question=str(payload.get("question") or ""),
            context=str(payload.get("context") or ""),
            janus_requests_heuristic=requested,
        )
    raise ValueError(f"SHABITAT_AURA_UNKNOWN_OPERATION:{operation}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = _read_request(args.request)
        response = handle_request(args.data_dir, args.aura_repo, payload)
        envelope = {
            "ok": True,
            "response": response,
            "secrets_included": False,
            "conversation_text_persisted_by_gateway": False,
            "aura_heuristic_text_persisted_by_gateway": False,
        }
        code = 0
    except Exception as exc:
        envelope = {
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
            "secrets_included": False,
            "conversation_text_persisted_by_gateway": False,
            "aura_heuristic_text_persisted_by_gateway": False,
        }
        code = 1
    print(json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2 if args.pretty else None))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
