# -*- coding: utf-8 -*-
"""Minimal hosted HTTP service for Genesis v18.7.20.

The service intentionally uses the Python standard library. Deploy it behind an
HTTPS reverse proxy; it binds to 127.0.0.1 by default and never logs bearer
tokens or request bodies.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_v18_7_19_ai_link_play import GenesisAILinkGateway
from genesis_v18_7_20_hosted_pilgrimage import (
    HostedAuthenticationError,
    HostedBridgeConfig,
    HostedBridgeError,
    HostedIdempotencyError,
    HostedPilgrimageBridge,
    HostedRateLimitError,
    HostedTokenExpired,
    HostedTokenSigner,
)
from genesis_v18_7_playable import PlayableGenesisV187

MAX_BODY_BYTES = 65536


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name}_MUST_BE_BOOLEAN")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None else int(raw)


def _bearer(header: str | None) -> str:
    value = str(header or "").strip()
    if not value.startswith("Bearer "):
        raise HostedAuthenticationError("HOSTED_BEARER_TOKEN_REQUIRED")
    token = value[7:].strip()
    if not token:
        raise HostedAuthenticationError("HOSTED_BEARER_TOKEN_REQUIRED")
    return token


def build_bridge_from_env(
    *,
    data_dir: Path,
    ephemeral_secret: bool = False,
) -> HostedPilgrimageBridge:
    secret_file = os.environ.get("GENESIS_HOSTED_SECRET_FILE", "").strip()
    secret = os.environ.get("GENESIS_HOSTED_SECRET", "")
    if secret_file:
        if secret:
            raise RuntimeError("SET_ONLY_ONE_OF_HOSTED_SECRET_OR_SECRET_FILE")
        secret = Path(secret_file).expanduser().read_text(encoding="utf-8").strip()
    if not secret and ephemeral_secret:
        secret = secrets.token_urlsafe(48)
    if not secret:
        raise RuntimeError("GENESIS_HOSTED_SECRET_REQUIRED")
    kill_switch_file = os.environ.get(
        "GENESIS_HOSTED_KILL_SWITCH_FILE",
        str(data_dir / "HOSTED_KILL_SWITCH"),
    )
    config = HostedBridgeConfig(
        public_base_url=os.environ.get("GENESIS_PUBLIC_BASE_URL", ""),
        live_mode=_env_bool("GENESIS_HOSTED_LIVE_MODE", False),
        kill_switch=_env_bool("GENESIS_HOSTED_KILL_SWITCH", True),
        kill_switch_file=kill_switch_file,
        allow_narrative_fallback=_env_bool(
            "GENESIS_HOSTED_ALLOW_NARRATIVE_FALLBACK",
            True,
        ),
        token_ttl_seconds=_env_int("GENESIS_HOSTED_TOKEN_TTL_SECONDS", 900),
        max_token_ttl_seconds=_env_int(
            "GENESIS_HOSTED_MAX_TOKEN_TTL_SECONDS",
            3600,
        ),
        global_limit_per_minute=_env_int(
            "GENESIS_HOSTED_GLOBAL_LIMIT_PER_MINUTE",
            120,
        ),
        client_limit_per_minute=_env_int(
            "GENESIS_HOSTED_CLIENT_LIMIT_PER_MINUTE",
            30,
        ),
        session_limit_per_minute=_env_int(
            "GENESIS_HOSTED_SESSION_LIMIT_PER_MINUTE",
            20,
        ),
        max_action_chars=_env_int("GENESIS_HOSTED_MAX_ACTION_CHARS", 4000),
    )
    signer = HostedTokenSigner(
        secret,
        default_ttl_seconds=config.token_ttl_seconds,
        max_ttl_seconds=config.max_token_ttl_seconds,
    )
    world = PlayableGenesisV187(data_dir)
    gateway = GenesisAILinkGateway(world, data_dir)
    return HostedPilgrimageBridge(
        gateway,
        data_dir,
        signer=signer,
        config=config,
    )


class HostedGenesisHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, bridge: HostedPilgrimageBridge):
        super().__init__(server_address, handler_class)
        self.bridge = bridge


class HostedGenesisHandler(BaseHTTPRequestHandler):
    server_version = "JanusGenesisHosted/18.7.20"

    @property
    def bridge(self) -> HostedPilgrimageBridge:
        return self.server.bridge  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        # Never log headers, bearer tokens, bodies, model labels, or action text.
        sys.stderr.write(
            "%s - - [%s] %s %s\n"
            % (
                self.address_string(),
                self.log_date_time_string(),
                self.command,
                urlparse(self.path).path,
            )
        )

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("HOSTED_CONTENT_LENGTH_REQUIRED")
        length = int(raw_length)
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("HOSTED_REQUEST_BODY_TOO_LARGE")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("HOSTED_REQUEST_INVALID_JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("HOSTED_REQUEST_MUST_BE_OBJECT")
        return payload

    def _client_id(self) -> str:
        value = str(self.headers.get("X-Genesis-Client-Id") or "").strip()
        if not value:
            raise ValueError("HOSTED_CLIENT_ID_REQUIRED")
        return value

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, HostedTokenExpired):
            status = HTTPStatus.UNAUTHORIZED
        elif isinstance(exc, HostedAuthenticationError):
            status = HTTPStatus.UNAUTHORIZED
        elif isinstance(exc, HostedRateLimitError):
            status = HTTPStatus.TOO_MANY_REQUESTS
        elif isinstance(exc, HostedIdempotencyError):
            status = HTTPStatus.CONFLICT
        elif isinstance(exc, (KeyError, FileNotFoundError)):
            status = HTTPStatus.NOT_FOUND
        elif isinstance(exc, (ValueError, TypeError, PermissionError)):
            status = HTTPStatus.BAD_REQUEST
        elif isinstance(exc, RuntimeError) and str(exc) in {
            "AI_LINK_SESSION_NOT_ACTIVE",
            "AI_LINK_SESSION_COLLISION",
            "HOSTED_IDEMPOTENT_TURN_NOT_FOUND",
        }:
            status = HTTPStatus.CONFLICT
        elif isinstance(exc, HostedBridgeError):
            status = HTTPStatus.SERVICE_UNAVAILABLE
        else:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        public_code = getattr(exc, "code", type(exc).__name__)
        public_message = (
            str(exc)
            if status != HTTPStatus.INTERNAL_SERVER_ERROR
            else "HOSTED_INTERNAL_ERROR"
        )
        self._send(
            int(status),
            {
                "ok": False,
                "error": public_code,
                "message": public_message,
                "secrets_included": False,
            },
        )

    def do_GET(self) -> None:  # noqa: N802
        try:
            path = urlparse(self.path).path
            if path in {"/", "/.well-known/janus-genesis.json"}:
                self._send(
                    HTTPStatus.OK,
                    {"ok": True, "response": self.bridge.discovery()},
                )
                return
            if path == "/v1/health":
                self._send(
                    HTTPStatus.OK,
                    {"ok": True, "response": self.bridge.health()},
                )
                return
            self._send(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "HOSTED_ROUTE_NOT_FOUND"},
            )
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urlparse(self.path).path
            payload = self._read_json()
            client_id = self._client_id()
            if path == "/v1/session/start":
                response = self.bridge.start_session(payload, client_id=client_id)
            else:
                token = _bearer(self.headers.get("Authorization"))
                if path == "/v1/session/turn":
                    response = self.bridge.process_turn(
                        token,
                        payload,
                        client_id=client_id,
                    )
                elif path == "/v1/session/state":
                    response = self.bridge.session_state(
                        token,
                        client_id=client_id,
                    )
                elif path == "/v1/session/capsule":
                    response = self.bridge.export_capsule(
                        token,
                        client_id=client_id,
                    )
                elif path == "/v1/session/close":
                    response = self.bridge.close_session(
                        token,
                        client_id=client_id,
                        reason=str(payload.get("reason") or "voluntary_exit"),
                    )
                elif path == "/v1/token/refresh":
                    response = self.bridge.refresh_token(
                        token,
                        client_id=client_id,
                    )
                else:
                    self._send(
                        HTTPStatus.NOT_FOUND,
                        {"ok": False, "error": "HOSTED_ROUTE_NOT_FOUND"},
                    )
                    return
            self._send(HTTPStatus.OK, {"ok": True, "response": response})
        except Exception as exc:
            self._handle_error(exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="genesis_hosted_gateway.py")
    parser.add_argument(
        "--host",
        default=os.environ.get("GENESIS_HOSTED_BIND", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_env_int("GENESIS_HOSTED_PORT", 8787),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("GENESIS_HOSTED_DATA_DIR", "data_v17")),
    )
    parser.add_argument(
        "--ephemeral-secret",
        action="store_true",
        help="Generate a process-only development secret. Never use for production.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate config and print discovery without starting the server.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("GENESIS_HOSTED_PORT_OUT_OF_RANGE")
    bridge = build_bridge_from_env(
        data_dir=args.data_dir,
        ephemeral_secret=args.ephemeral_secret,
    )
    if args.check:
        print(
            json.dumps(
                {
                    "ok": True,
                    "response": bridge.discovery(),
                    "health": bridge.health(),
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    if (
        args.host not in {"127.0.0.1", "::1", "localhost"}
        and bridge.config.live_mode
        and not bridge.config.public_base_url.startswith("https://")
    ):
        raise SystemExit("PUBLIC_LIVE_BIND_REQUIRES_HTTPS_PUBLIC_BASE_URL")
    server = HostedGenesisHTTPServer(
        (args.host, args.port),
        HostedGenesisHandler,
        bridge,
    )
    print(
        json.dumps(
            {
                "status": "HOSTED_PILGRIMAGE_LISTENING",
                "host": args.host,
                "port": args.port,
                "live_mode": bridge.config.live_mode,
                "kill_switch": bridge.kill_switch_active,
                "authoritative_runtime_available": bridge.authoritative_available,
                "request_bodies_logged": False,
                "bearer_tokens_logged": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
