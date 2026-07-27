# -*- coding: utf-8 -*-
"""Reference shared-event hub for Genesis v18.7.

The hub is intentionally narrow: it authenticates nodes, verifies public event
hashes, assigns a global sequence and relays events. It cannot execute player
actions, import local saves, inspect private Chronicle state, or rewrite a node.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from genesis_v18_7_auth import api_key_sha256, configured_hashes, verify_bearer
from genesis_v18_7_network import GenesisNetworkClient

MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_BATCH_EVENTS = 500


class HubStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events_path = root / "events.jsonl"
        self.meta_path = root / "meta.json"
        self.lock = threading.RLock()
        root.mkdir(parents=True, exist_ok=True)
        self._ensure_meta()

    def _ensure_meta(self) -> None:
        if not self.meta_path.exists():
            self._write_meta(
                {
                    "schema": "janus.genesis.network.hub.v1",
                    "next_network_sequence": 1,
                    "event_count": 0,
                    "hub_may_rewrite_local_state": False,
                    "raw_api_keys_persisted": False,
                }
            )

    def _meta(self) -> dict[str, Any]:
        try:
            value = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        value.setdefault("schema", "janus.genesis.network.hub.v1")
        value.setdefault("next_network_sequence", 1)
        value.setdefault("event_count", 0)
        value.setdefault("hub_may_rewrite_local_state", False)
        value.setdefault("raw_api_keys_persisted", False)
        return value

    def _write_meta(self, payload: dict[str, Any]) -> None:
        temporary = self.meta_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.meta_path)

    def _known_hashes(self) -> set[str]:
        hashes: set[str] = set()
        if not self.events_path.exists():
            return hashes
        with self.events_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    envelope = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = envelope.get("event") if isinstance(envelope, dict) else None
                if isinstance(event, dict) and event.get("event_hash"):
                    hashes.add(str(event["event_hash"]))
        return hashes

    def append_events(self, events: list[dict[str, Any]]) -> list[str]:
        if len(events) > MAX_BATCH_EVENTS:
            raise ValueError(f"batch exceeds {MAX_BATCH_EVENTS} events")
        accepted: list[str] = []
        with self.lock:
            meta = self._meta()
            known = self._known_hashes()
            lines: list[str] = []
            for event in events:
                if not isinstance(event, dict):
                    raise ValueError("every event must be an object")
                valid, error = GenesisNetworkClient.verify_event(event)
                if not valid:
                    raise ValueError(error or "invalid network event")
                event_hash = str(event["event_hash"])
                if event_hash in known:
                    accepted.append(event_hash)
                    continue
                sequence = int(meta["next_network_sequence"])
                envelope = {
                    "network_sequence": sequence,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "event": event,
                }
                lines.append(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
                known.add(event_hash)
                accepted.append(event_hash)
                meta["next_network_sequence"] = sequence + 1
                meta["event_count"] = int(meta.get("event_count", 0)) + 1
            if lines:
                with self.events_path.open("a", encoding="utf-8") as handle:
                    for line in lines:
                        handle.write(line + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
            self._write_meta(meta)
        return accepted

    def read_events(self, *, after: int, limit: int) -> tuple[list[dict[str, Any]], int]:
        results: list[dict[str, Any]] = []
        next_cursor = max(0, int(after))
        with self.lock:
            if self.events_path.exists():
                with self.events_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if not line.strip():
                            continue
                        try:
                            envelope = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        sequence = int(envelope.get("network_sequence", 0))
                        if sequence <= after:
                            continue
                        results.append(envelope)
                        next_cursor = max(next_cursor, sequence)
                        if len(results) >= limit:
                            break
        return results, next_cursor

    def public_meta(self) -> dict[str, Any]:
        with self.lock:
            meta = self._meta()
        return {
            "schema": meta["schema"],
            "event_count": meta["event_count"],
            "latest_network_sequence": int(meta["next_network_sequence"]) - 1,
            "hub_may_rewrite_local_state": False,
            "raw_api_keys_persisted": False,
        }


class GenesisNetworkHub(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], root: Path) -> None:
        super().__init__(address, GenesisNetworkHubHandler)
        self.store = HubStore(root)


class GenesisNetworkHubHandler(BaseHTTPRequestHandler):
    server: GenesisNetworkHub

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self) -> bool:
        if verify_bearer(self.headers, hashes_env="GENESIS_NETWORK_KEY_HASHES"):
            return True
        self._send(HTTPStatus.UNAUTHORIZED, {"error": "invalid network bearer key"})
        return False

    def _json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body is too large")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request JSON must be an object")
        return payload

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self._send(HTTPStatus.OK, {"status": "ok", **self.server.store.public_meta()})
            return
        if not self._authorized():
            return
        if parsed.path == "/v1/network/meta":
            self._send(HTTPStatus.OK, self.server.store.public_meta())
            return
        if parsed.path == "/v1/network/events":
            query = urllib.parse.parse_qs(parsed.query)
            try:
                after = max(0, int((query.get("after") or [0])[0]))
                limit = max(1, min(1000, int((query.get("limit") or [200])[0])))
                events, next_cursor = self.server.store.read_events(after=after, limit=limit)
                self._send(
                    HTTPStatus.OK,
                    {
                        "events": events,
                        "next_cursor": next_cursor,
                        "hub_may_rewrite_local_state": False,
                    },
                )
            except Exception as exc:
                self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if not self._authorized():
            return
        if parsed.path != "/v1/network/events":
            self._send(HTTPStatus.NOT_FOUND, {"error": "unknown endpoint"})
            return
        try:
            payload = self._json_body()
            events = payload.get("events")
            if not isinstance(events, list):
                raise ValueError("events must be a list")
            accepted = self.server.store.append_events(events)
            self._send(
                HTTPStatus.OK,
                {
                    "accepted_event_hashes": accepted,
                    "accepted": len(accepted),
                    "hub_may_rewrite_local_state": False,
                },
            )
        except Exception as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="genesis_network_hub.py")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--data-dir", type=Path, default=Path("genesis_network_hub_data"))
    parser.add_argument("--hash-key", help="Print SHA-256 for one raw network key and exit.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.hash_key is not None:
        print(api_key_sha256(args.hash_key))
        return 0
    if not configured_hashes("GENESIS_NETWORK_KEY_HASHES"):
        raise SystemExit(
            "GENESIS_NETWORK_KEY_HASHES is empty. Configure comma-separated SHA-256 key hashes first."
        )
    server = GenesisNetworkHub((args.bind, args.port), args.data_dir)
    print(f"Genesis Network hub listening on http://{args.bind}:{args.port}")
    print("The hub relays public events only and cannot rewrite local Genesis saves.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
