# -*- coding: utf-8 -*-
"""Authenticated HTTP API for playing Genesis v18.7 from agents or devices.

Example:
  export GENESIS_API_KEY_HASHES=$(python tools/genesis_api_server.py --hash-key 'replace-me')
  python tools/genesis_api_server.py --data-dir data_v17 --bind 127.0.0.1 --port 8787

Clients send `Authorization: Bearer <raw key>`. Only SHA-256 key hashes are
configured on the server. Raw keys are never written by this service.
"""
from __future__ import annotations

import argparse
import json
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from genesis_v18_7_auth import api_key_sha256, configured_hashes, verify_bearer
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

MAX_BODY_BYTES = 8 * 1024 * 1024


class GenesisAPIServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], data_dir: Path) -> None:
        super().__init__(address, GenesisAPIHandler)
        self.world = PlayableGenesisV187(data_dir)
        self.saves = PortableSaveManager(data_dir)
        self.lock = threading.RLock()


class GenesisAPIHandler(BaseHTTPRequestHandler):
    server: GenesisAPIServer

    def log_message(self, format: str, *args: Any) -> None:
        super().log_message(format, *args)

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self) -> bool:
        if verify_bearer(self.headers, hashes_env="GENESIS_API_KEY_HASHES"):
            return True
        self._send(
            HTTPStatus.UNAUTHORIZED,
            {"error": "missing or invalid bearer key", "api_key_persisted": False},
        )
        return False

    def _json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request JSON must be an object")
        return payload

    @staticmethod
    def _player(query: dict[str, list[str]], payload: dict[str, Any] | None = None) -> str:
        value = None
        if payload is not None:
            value = payload.get("player_id")
        if value is None:
            values = query.get("player_id") or query.get("player") or []
            value = values[0] if values else "traveler"
        return str(value)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "runtime": "Genesis v18.7",
                    "authenticated_actions": True,
                    "api_key_persisted": False,
                },
            )
            return
        if not self._authorized():
            return
        query = urllib.parse.parse_qs(parsed.query)
        player_id = self._player(query)
        try:
            with self.server.lock:
                if parsed.path == "/v1/status":
                    self._send(HTTPStatus.OK, self.server.world.public_state(player_id))
                    return
                if parsed.path == "/v1/others":
                    self._send(HTTPStatus.OK, self.server.world.free_other_state(player_id))
                    return
                if parsed.path == "/v1/save/export":
                    label = (query.get("label") or ["Genesis API device save"])[0]
                    self._send(HTTPStatus.OK, self.server.saves.build_bundle(label=label))
                    return
                if parsed.path == "/v1/verify":
                    chronicle = self.server.world.verify_chronicle_records()
                    graph = self.server.world.verify_possibility_graph()
                    others = self.server.world.verify_free_other_state()
                    self._send(
                        HTTPStatus.OK,
                        {
                            "chronicle": {"valid": chronicle[0], "events": chronicle[1], "error": chronicle[2]},
                            "hrain": {"valid": graph[0], "nodes": graph[1], "edges": graph[2], "error": graph[3]},
                            "free_others": {"valid": others[0], "players": others[1], "others": others[2], "error": others[3]},
                        },
                    )
                    return
        except Exception as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if not self._authorized():
            return
        try:
            payload = self._json_body()
            query = urllib.parse.parse_qs(parsed.query)
            player_id = self._player(query, payload)
            with self.server.lock:
                if parsed.path == "/v1/action":
                    action = str(payload.get("action") or "").strip()
                    if not action:
                        raise ValueError("action is required")
                    result = self.server.world.process_action(player_id, action)
                    self._send(
                        HTTPStatus.OK,
                        {
                            "result": result.to_dict(),
                            "public_state": self.server.world.public_state(player_id),
                            "api_key_persisted": False,
                            "external_model_is_state_authority": False,
                        },
                    )
                    return
                if parsed.path == "/v1/player/name":
                    name = str(payload.get("display_name") or "").strip()
                    if not name:
                        raise ValueError("display_name is required")
                    self.server.world.set_display_name(player_id, name)
                    self._send(HTTPStatus.OK, self.server.world.public_state(player_id))
                    return
                if parsed.path == "/v1/save/import":
                    bundle = payload.get("bundle")
                    if not isinstance(bundle, dict):
                        raise ValueError("bundle must be an object")
                    conflict = str(payload.get("conflict") or "replace")
                    result = self.server.saves.import_bundle(bundle, conflict=conflict)
                    self.server.world = PlayableGenesisV187(self.server.saves.root)
                    self._send(HTTPStatus.OK, result)
                    return
        except Exception as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="genesis_api_server.py")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data-dir", type=Path, default=Path("data_v17"))
    parser.add_argument("--hash-key", help="Print SHA-256 for one raw API key and exit.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.hash_key is not None:
        print(api_key_sha256(args.hash_key))
        return 0
    if not configured_hashes("GENESIS_API_KEY_HASHES"):
        raise SystemExit(
            "GENESIS_API_KEY_HASHES is empty. Configure comma-separated SHA-256 key hashes first."
        )
    server = GenesisAPIServer((args.bind, args.port), args.data_dir)
    print(f"Genesis v18.7 API listening on http://{args.bind}:{args.port}")
    print("Bearer keys are verified by SHA-256; raw keys are not persisted.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
