# -*- coding: utf-8 -*-
"""Authenticated HTTP API for playing Genesis v18.7.

Example:
  export GENESIS_API_KEY_HASHES=$(python tools/genesis_api_server.py --hash-key 'replace-me')
  python tools/genesis_api_server.py --data-dir data_v17 --bind 127.0.0.1 --port 8787

Clients send ``Authorization: Bearer <raw key>``. Only SHA-256 key hashes are
configured on the server. Raw keys are never written by this service.

v18.7.57 hardening: authentication is identity admission, not raw world-mutation
authority. Every POST mutation requires a stable ``request_id`` and is routed
through the existing crash/replay-aware control plane:

* /v1/action -> ReconciledPortableReceiptRuntimeAdapter;
* /v1/player/name -> TypedAuxiliaryMutationAdapter;
* /v1/save/import -> RecoverySafePortableSaveManager roll-forward saga.

Read-only status/verification/export paths remain direct reads. This closes the
cooperating API server's historical raw-mutation side door; it does not prevent
arbitrary Python code from constructing PlayableGenesisV187 directly.
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

from genesis_v18_7_31_portable_receipt_runtime import (
    PortableRequestConflict,
    PortableRuntimeControlError,
    PortableRuntimeOutcomeUndetermined,
    PortableRuntimeReceiptIntegrityError,
)
from genesis_v18_7_33_inflight_duplicate_reconciliation import (
    ReconciledPortableReceiptRuntimeAdapter,
)
from genesis_v18_7_37_recovery_safe_save_import import (
    ImportRequestConflict,
    RecoverySafeImportError,
    RecoverySafePortableSaveManager,
)
from genesis_v18_7_39_typed_mutation_authority import (
    TypedAuxiliaryMutationAdapter,
    TypedMutationError,
    TypedMutationOutcomeUndetermined,
    TypedMutationReceiptIntegrityError,
    TypedMutationRequestConflict,
)
from genesis_v18_7_auth import api_key_sha256, configured_hashes, verify_bearer
from genesis_v18_7_playable import PlayableGenesisV187

MAX_BODY_BYTES = 8 * 1024 * 1024
API_CONTROL_CLIENT_ID = "genesis-api-server"


class GenesisAPIServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], data_dir: Path) -> None:
        super().__init__(address, GenesisAPIHandler)
        self.data_dir = Path(data_dir)
        self.lock = threading.RLock()
        self.saves = RecoverySafePortableSaveManager(self.data_dir)
        self._reload_world_control_plane()

    def _reload_world_control_plane(self) -> None:
        self.world = PlayableGenesisV187(self.data_dir)
        self.actions = ReconciledPortableReceiptRuntimeAdapter(self.world, self.data_dir)
        self.auxiliary = TypedAuxiliaryMutationAdapter(self.world, self.data_dir)

    def process_action(self, *, request_id: str, player_id: str, action: str):
        return self.actions.execute(
            client_id=API_CONTROL_CLIENT_ID,
            request_id=request_id,
            actor_id=player_id,
            action=action,
        )

    def set_display_name(self, *, request_id: str, player_id: str, display_name: str) -> dict[str, Any]:
        return self.auxiliary.set_display_name(
            client_id=API_CONTROL_CLIENT_ID,
            request_id=request_id,
            actor_id=player_id,
            display_name=display_name,
        )

    def import_save(
        self,
        *,
        request_id: str,
        bundle: dict[str, Any],
        conflict: str,
    ) -> dict[str, Any]:
        result = self.saves.import_bundle_recoverable(
            bundle,
            request_id=request_id,
            conflict=conflict,
        )
        # A successful import may replace world files. Rebuild readers/adapters
        # only after the recovery-safe saga has settled.
        self._reload_world_control_plane()
        return result


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

    @staticmethod
    def _request_id(payload: dict[str, Any]) -> str:
        request_id = str(payload.get("request_id") or "").strip()
        if not request_id or len(request_id) > 240:
            raise ValueError("request_id is required for mutation and must be <= 240 characters")
        return request_id

    @staticmethod
    def _query_request_id(query: dict[str, list[str]]) -> str:
        values = query.get("request_id") or []
        request_id = str(values[0] if values else "").strip()
        if not request_id:
            raise ValueError("request_id query parameter is required")
        return request_id

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "runtime": "Genesis v18.7",
                    "authenticated_actions": True,
                    "mutation_request_id_required": True,
                    "process_action_receipt_runtime": True,
                    "typed_auxiliary_mutation_authority": True,
                    "recovery_safe_save_import": True,
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
                if parsed.path == "/v1/request/action":
                    request_id = self._query_request_id(query)
                    self._send(
                        HTTPStatus.OK,
                        {
                            "request_id": request_id,
                            "request_state": self.server.actions.request_state(
                                client_id=API_CONTROL_CLIENT_ID,
                                request_id=request_id,
                            ),
                        },
                    )
                    return
                if parsed.path == "/v1/request/mutation":
                    request_id = self._query_request_id(query)
                    self._send(
                        HTTPStatus.OK,
                        {
                            "request_id": request_id,
                            "request_state": self.server.auxiliary.request_state(
                                client_id=API_CONTROL_CLIENT_ID,
                                request_id=request_id,
                            ),
                        },
                    )
                    return
                if parsed.path == "/v1/request/import":
                    request_id = self._query_request_id(query)
                    self._send(
                        HTTPStatus.OK,
                        {
                            "request_id": request_id,
                            "request_state": self.server.saves.request_state(request_id),
                        },
                    )
                    return
        except Exception as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

    def _control_failure(self, exc: BaseException, *, request_id: str | None) -> None:
        undetermined = isinstance(
            exc,
            (PortableRuntimeOutcomeUndetermined, TypedMutationOutcomeUndetermined),
        )
        conflict = isinstance(
            exc,
            (PortableRequestConflict, TypedMutationRequestConflict, ImportRequestConflict),
        )
        integrity = isinstance(
            exc,
            (PortableRuntimeReceiptIntegrityError, TypedMutationReceiptIntegrityError),
        )
        status = HTTPStatus.SERVICE_UNAVAILABLE if undetermined else (
            HTTPStatus.CONFLICT if conflict or integrity else HTTPStatus.BAD_REQUEST
        )
        self._send(
            status,
            {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_id": request_id,
                "automatic_reexecution_attempted": False,
                "outcome_undetermined": undetermined,
            },
        )

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if not self._authorized():
            return
        request_id: str | None = None
        try:
            payload = self._json_body()
            request_id = self._request_id(payload)
            query = urllib.parse.parse_qs(parsed.query)
            player_id = self._player(query, payload)
            with self.server.lock:
                if parsed.path == "/v1/action":
                    action = str(payload.get("action") or "").strip()
                    if not action:
                        raise ValueError("action is required")
                    result = self.server.process_action(
                        request_id=request_id,
                        player_id=player_id,
                        action=action,
                    )
                    self._send(
                        HTTPStatus.OK,
                        {
                            "result": result.to_dict(),
                            "public_state": self.server.world.public_state(player_id),
                            "request_id": request_id,
                            "request_state": self.server.actions.request_state(
                                client_id=API_CONTROL_CLIENT_ID,
                                request_id=request_id,
                            ),
                            "api_key_persisted": False,
                            "external_model_is_state_authority": False,
                            "raw_world_mutation_path_used": False,
                        },
                    )
                    return
                if parsed.path == "/v1/player/name":
                    name = str(payload.get("display_name") or "").strip()
                    if not name:
                        raise ValueError("display_name is required")
                    receipt = self.server.set_display_name(
                        request_id=request_id,
                        player_id=player_id,
                        display_name=name,
                    )
                    self._send(
                        HTTPStatus.OK,
                        {
                            "receipt": receipt,
                            "public_state": self.server.world.public_state(player_id),
                            "request_id": request_id,
                            "request_state": self.server.auxiliary.request_state(
                                client_id=API_CONTROL_CLIENT_ID,
                                request_id=request_id,
                            ),
                            "raw_world_mutation_path_used": False,
                        },
                    )
                    return
                if parsed.path == "/v1/save/import":
                    bundle = payload.get("bundle")
                    if not isinstance(bundle, dict):
                        raise ValueError("bundle must be an object")
                    conflict = str(payload.get("conflict") or "replace")
                    result = self.server.import_save(
                        request_id=request_id,
                        bundle=bundle,
                        conflict=conflict,
                    )
                    self._send(
                        HTTPStatus.OK,
                        {
                            "receipt": result,
                            "request_id": request_id,
                            "request_state": self.server.saves.request_state(request_id),
                            "recovery_safe_roll_forward": True,
                            "raw_portable_import_path_used": False,
                        },
                    )
                    return
        except (
            PortableRequestConflict,
            PortableRuntimeControlError,
            PortableRuntimeOutcomeUndetermined,
            PortableRuntimeReceiptIntegrityError,
            TypedMutationError,
            TypedMutationOutcomeUndetermined,
            TypedMutationReceiptIntegrityError,
            TypedMutationRequestConflict,
            RecoverySafeImportError,
            ImportRequestConflict,
            ValueError,
            FileExistsError,
        ) as exc:
            self._control_failure(exc, request_id=request_id)
            return
        except Exception as exc:
            self._control_failure(exc, request_id=request_id)
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
    print("All POST mutations require request_id and use durable control-plane adapters.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
