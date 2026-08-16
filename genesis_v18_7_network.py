# -*- coding: utf-8 -*-
"""Genesis v18.7 shared-network client and public event protocol.

The common network is an event relay, not a remote owner of local saves. Local
Genesis remains authoritative. API keys are read from environment variables and
never enter the outbox, inbox, portable save, or event payload.

v18.7.55 hardening note: this historical direct HTTP adapter is default-deny.
Local queue/state operations remain available, but crossing the remote boundary
requires either a transient admission set by the canonical Armor wrapper after
Armor PASS or the explicit legacy compatibility opt-in
``JANUS_LEGACY_DIRECT_EGRESS=1``. The opt-in is compatibility authority, not a
replacement for Armor and not a production recommendation.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NETWORK_EVENT_SCHEMA = "janus.genesis.network.event.v1"
NETWORK_STATE_SCHEMA = "janus.genesis.network.client.v1"
LEGACY_DIRECT_EGRESS_ENV = "JANUS_LEGACY_DIRECT_EGRESS"
ALLOWED_EVENT_KINDS = {
    "presence",
    "public_creation",
    "path_signal",
    "public_message",
    "request_to_meet",
    "shared_place",
}
FORBIDDEN_PAYLOAD_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "secret",
    "credential",
    "password",
    "branch_id",
    "internal_realm",
}


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _legacy_direct_egress_opt_in() -> bool:
    """Exact compatibility opt-in; truthy strings do not become permission."""
    return os.environ.get(LEGACY_DIRECT_EGRESS_ENV) == "1"


def _assert_public_payload(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_PAYLOAD_KEYS or any(
                fragment in lowered for fragment in ("api_key", "credential", "password")
            ):
                raise ValueError(f"private network payload key rejected: {path}.{key}")
            _assert_public_payload(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_public_payload(item, path=f"{path}[{index}]")
    elif isinstance(value, str) and len(value) > 4000:
        raise ValueError(f"network string is too large: {path}")


class GenesisNetworkClient:
    """Queue public events locally; direct remote sync is legacy-default-deny."""

    def __init__(
        self,
        data_dir: str | Path,
        *,
        hub_url: str,
        api_key_env: str = "GENESIS_NETWORK_API_KEY",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.root = Path(data_dir)
        self.state_path = self.root / "network_client_v18_7.json"
        self.hub_url = hub_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
        # The canonical Armor descendant sets this only around the exact
        # already-authorized sync call and restores it in finally.
        self._armor_egress_admitted = False

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "schema": NETWORK_STATE_SCHEMA,
            "node_id": secrets.token_hex(16),
            "next_local_sequence": 1,
            "last_local_event_hash": "0" * 64,
            "hub_cursor": 0,
            "outbox": [],
            "inbox": [],
            "public_player_ids": {},
            "invariants": {
                "local_save_is_authoritative": True,
                "hub_may_rewrite_local_state": False,
                "api_key_persisted": False,
                "private_chronicle_uploaded": False,
                "events_require_explicit_public_kind": True,
                "legacy_direct_remote_egress_default_deny": True,
            },
        }

    def _load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            state = self._default_state()
            self._save(state)
            return state
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = self._default_state()
        if state.get("schema") != NETWORK_STATE_SCHEMA:
            state = self._default_state()
        for key, default in self._default_state().items():
            state.setdefault(key, default)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.state_path)

    def _key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"network API key environment variable is missing: {self.api_key_env}"
            )
        return key

    def _direct_egress_admitted(self) -> bool:
        return (
            type(getattr(self, "_armor_egress_admitted", False)) is bool
            and getattr(self, "_armor_egress_admitted", False) is True
        ) or _legacy_direct_egress_opt_in()

    def public_player_id(self, player_id: str) -> str:
        state = self._load()
        mapping = state.setdefault("public_player_ids", {})
        if player_id not in mapping:
            mapping[player_id] = _sha256(
                f"{state['node_id']}|{player_id}|GENESIS-v18.7".encode("utf-8")
            )[:24]
            self._save(state)
        return str(mapping[player_id])

    def queue_public_event(
        self,
        player_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if kind not in ALLOWED_EVENT_KINDS:
            raise ValueError(f"unsupported public event kind: {kind}")
        _assert_public_payload(payload)
        state = self._load()
        local_sequence = int(state["next_local_sequence"])
        public_player_id = state.setdefault("public_player_ids", {}).setdefault(
            player_id,
            _sha256(
                f"{state['node_id']}|{player_id}|GENESIS-v18.7".encode("utf-8")
            )[:24],
        )
        event = {
            "schema": NETWORK_EVENT_SCHEMA,
            "node_id": state["node_id"],
            "public_player_id": public_player_id,
            "local_sequence": local_sequence,
            "kind": kind,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "previous_local_hash": state["last_local_event_hash"],
            "payload": payload,
        }
        event_hash = _sha256(_canonical(event))
        event["event_hash"] = event_hash
        state["outbox"].append(event)
        state["outbox"] = state["outbox"][-1024:]
        state["next_local_sequence"] = local_sequence + 1
        state["last_local_event_hash"] = event_hash
        self._save(state)
        return event

    @staticmethod
    def verify_event(event: dict[str, Any]) -> tuple[bool, str | None]:
        if event.get("schema") != NETWORK_EVENT_SCHEMA:
            return False, "unsupported event schema"
        if event.get("kind") not in ALLOWED_EVENT_KINDS:
            return False, "unsupported event kind"
        expected = str(event.get("event_hash") or "")
        unsigned = dict(event)
        unsigned.pop("event_hash", None)
        calculated = _sha256(_canonical(unsigned))
        if expected != calculated:
            return False, "event hash mismatch"
        try:
            _assert_public_payload(event.get("payload", {}))
        except ValueError as exc:
            return False, str(exc)
        return True, None

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._direct_egress_admitted():
            raise RuntimeError(
                "LEGACY_DIRECT_NETWORK_EGRESS_DEFAULT_DENY: use the canonical "
                "Armor-gated client or explicitly set JANUS_LEGACY_DIRECT_EGRESS=1 "
                "for historical compatibility"
            )
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._key()}",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.hub_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"Genesis Network HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Genesis Network connection failed: {exc.reason}") from exc
        try:
            result = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("Genesis Network returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Genesis Network response must be an object")
        return result

    def sync(self, *, limit: int = 200) -> dict[str, Any]:
        state = self._load()
        outbox = list(state.get("outbox", []))
        accepted = 0
        if outbox:
            response = self._request(
                "POST",
                "/v1/network/events",
                payload={"events": outbox},
            )
            accepted_hashes = set(str(item) for item in response.get("accepted_event_hashes", []))
            accepted = len(accepted_hashes)
            state["outbox"] = [
                event for event in outbox if event.get("event_hash") not in accepted_hashes
            ]
        query = urllib.parse.urlencode(
            {"after": int(state.get("hub_cursor", 0)), "limit": max(1, min(1000, int(limit)))}
        )
        response = self._request("GET", f"/v1/network/events?{query}")
        received: list[dict[str, Any]] = []
        for envelope in response.get("events", []):
            if not isinstance(envelope, dict) or not isinstance(envelope.get("event"), dict):
                continue
            valid, _ = self.verify_event(envelope["event"])
            if not valid:
                continue
            received.append(envelope)
        state["inbox"] = (state.get("inbox", []) + received)[-2048:]
        state["hub_cursor"] = max(
            int(state.get("hub_cursor", 0)),
            int(response.get("next_cursor", state.get("hub_cursor", 0))),
        )
        self._save(state)
        return {
            "hub_url": self.hub_url,
            "accepted": accepted,
            "remaining_outbox": len(state["outbox"]),
            "received": len(received),
            "cursor": state["hub_cursor"],
            "local_save_authority_changed": False,
            "legacy_direct_egress_default_deny": True,
        }

    def state(self) -> dict[str, Any]:
        state = self._load()
        return {
            "hub_url": self.hub_url,
            "node_id": state["node_id"],
            "queued_public_events": len(state.get("outbox", [])),
            "received_public_events": len(state.get("inbox", [])),
            "hub_cursor": state.get("hub_cursor", 0),
            "api_key_persisted": False,
            "private_chronicle_uploaded": False,
            "legacy_direct_remote_egress_default_deny": True,
        }
