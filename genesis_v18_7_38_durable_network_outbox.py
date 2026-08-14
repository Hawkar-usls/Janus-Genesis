# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.38 — durable locked network outbox with ambiguous-send blocking.

The historical v18.7 network client is intentionally retained for compatibility,
but it is not used as evidence for durable retry safety. This descendant adds a
conservative local control boundary:

- one process-global + OS lock for all local network-state mutations;
- unique same-directory durable JSON replacement through the v18.7.35 writer;
- malformed or schema-invalid *existing* state fails closed instead of being
  silently reinterpreted as a fresh node;
- outbox capacity is backpressure: event 1025 is rejected instead of silently
  deleting the oldest unsent event;
- before POST, the exact immutable event-hash batch is durably recorded as
  SEND_ENTERING;
- a crash/error after SEND_ENTERING and before a complete durable acknowledgement
  leaves an AMBIGUOUS remote-outcome record and blocks automatic resend;
- only a response that explicitly acknowledges every hash in the sent batch is
  treated as a complete send receipt by this reference client;
- a partial accepted-hash response removes the explicitly accepted events but
  keeps the unresolved hashes blocked from automatic resend.

No hub-side deduplication/idempotency guarantee has been verified by this module.
Therefore it deliberately chooses durable uncertainty over automatic duplicate
publication after an ambiguous remote boundary. A future verified hub contract
may safely narrow that uncertainty; this module does not invent one.

The local lock is same-host/shared-filesystem coordination, not multi-host
consensus. File fsync on Windows does not become a claim about directory-entry
power-loss durability.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_35_windows_safe_durable_writer import WindowsSafeDurableJsonWriter
from genesis_v18_7_network import (
    ALLOWED_EVENT_KINDS,
    NETWORK_EVENT_SCHEMA,
    NETWORK_STATE_SCHEMA,
    GenesisNetworkClient,
    _assert_public_payload,
    _canonical,
    _sha256,
)
from janus_portable_lock_v2 import PortableProcessLockV2

DURABLE_NETWORK_VERSION = "18.7.38"
DURABLE_NETWORK_SCHEMA = "janus.genesis.durable_network_outbox.v1"
MAX_DURABLE_OUTBOX = 1024


class DurableNetworkError(RuntimeError):
    code = "DURABLE_NETWORK_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class NetworkStateIntegrityError(DurableNetworkError):
    code = "NETWORK_STATE_INTEGRITY_ERROR"


class NetworkOutboxCapacityError(DurableNetworkError):
    code = "NETWORK_OUTBOX_CAPACITY_REACHED"


class NetworkSendOutcomeUndetermined(DurableNetworkError):
    code = "NETWORK_SEND_OUTCOME_UNDETERMINED"


class NetworkCrashPoint(str, Enum):
    AFTER_SEND_ENTERING_BEFORE_REMOTE = "AFTER_SEND_ENTERING_BEFORE_REMOTE"
    AFTER_REMOTE_RESPONSE_BEFORE_LOCAL_ACK = "AFTER_REMOTE_RESPONSE_BEFORE_LOCAL_ACK"


class NetworkCrashInjector:
    def __init__(self, *points: NetworkCrashPoint | str) -> None:
        self.remaining = {
            NetworkCrashPoint(p.value if isinstance(p, NetworkCrashPoint) else str(p))
            for p in points
        }

    def hit(self, point: NetworkCrashPoint) -> None:
        if point in self.remaining:
            self.remaining.remove(point)
            raise NetworkSendOutcomeUndetermined(f"INJECTED_NETWORK_CRASH:{point.value}")


@dataclass(frozen=True)
class PendingSendState:
    batch_id: str
    state: str
    event_hashes: tuple[str, ...]
    accepted_event_hashes: tuple[str, ...]
    unresolved_event_hashes: tuple[str, ...]


class DurableGenesisNetworkClient(GenesisNetworkClient):
    """Compatibility descendant with durable local state and conservative send semantics."""

    def __init__(
        self,
        data_dir: str | Path,
        *,
        hub_url: str,
        api_key_env: str = "GENESIS_NETWORK_API_KEY",
        timeout_seconds: float = 20.0,
        crash_injector: NetworkCrashInjector | None = None,
    ) -> None:
        super().__init__(
            data_dir,
            hub_url=hub_url,
            api_key_env=api_key_env,
            timeout_seconds=timeout_seconds,
        )
        self.local_lock = PortableProcessLockV2(
            self.root / "network_client_v18_7_38.lock"
        )
        self.durable_writer = WindowsSafeDurableJsonWriter()
        self.crash_injector = crash_injector or NetworkCrashInjector()
        with self.local_lock.exclusive():
            if not self.state_path.exists():
                self._save(self._default_state_v38())
            else:
                # Existing invalid state must fail now; construction itself is a
                # useful admission gate rather than waiting for a later mutation.
                self._load()

    @staticmethod
    def _default_state_v38() -> dict[str, Any]:
        state = GenesisNetworkClient._default_state()
        state["control_v18_7_38"] = {
            "schema": DURABLE_NETWORK_SCHEMA,
            "pending_send": None,
            "completed_send_receipts": [],
            "malformed_existing_state_resets_to_fresh_node": False,
            "automatic_resend_after_ambiguous_send": False,
            "hub_idempotency_verified": False,
        }
        return state

    def _load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise NetworkStateIntegrityError("NETWORK_STATE_MISSING_AFTER_INITIALIZATION")
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise NetworkStateIntegrityError("NETWORK_STATE_UNREADABLE") from exc
        except json.JSONDecodeError as exc:
            raise NetworkStateIntegrityError("NETWORK_STATE_INVALID_JSON") from exc
        if not isinstance(state, dict):
            raise NetworkStateIntegrityError("NETWORK_STATE_NOT_OBJECT")
        if state.get("schema") != NETWORK_STATE_SCHEMA:
            raise NetworkStateIntegrityError("NETWORK_STATE_SCHEMA_INVALID")

        defaults = GenesisNetworkClient._default_state()
        for key, default in defaults.items():
            if key not in state:
                state[key] = default
        if not isinstance(state.get("outbox"), list):
            raise NetworkStateIntegrityError("NETWORK_OUTBOX_NOT_LIST")
        if not isinstance(state.get("inbox"), list):
            raise NetworkStateIntegrityError("NETWORK_INBOX_NOT_LIST")
        if not isinstance(state.get("public_player_ids"), dict):
            raise NetworkStateIntegrityError("NETWORK_PUBLIC_PLAYER_IDS_NOT_OBJECT")
        if len(state["outbox"]) > MAX_DURABLE_OUTBOX:
            raise NetworkStateIntegrityError("NETWORK_OUTBOX_OVER_CAPACITY")

        control = state.get("control_v18_7_38")
        if control is None:
            # Admit a structurally valid historical state into the descendant
            # without changing its node/outbox/cursor identity.
            control = self._default_state_v38()["control_v18_7_38"]
            state["control_v18_7_38"] = control
        if not isinstance(control, dict) or control.get("schema") != DURABLE_NETWORK_SCHEMA:
            raise NetworkStateIntegrityError("NETWORK_CONTROL_SCHEMA_INVALID")
        if not isinstance(control.get("completed_send_receipts", []), list):
            raise NetworkStateIntegrityError("NETWORK_COMPLETED_RECEIPTS_NOT_LIST")
        pending = control.get("pending_send")
        if pending is not None and not isinstance(pending, dict):
            raise NetworkStateIntegrityError("NETWORK_PENDING_SEND_NOT_OBJECT")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.durable_writer.write(self.state_path, state)

    @staticmethod
    def _batch_id(node_id: str, event_hashes: list[str]) -> str:
        payload = json.dumps(
            {"node_id": node_id, "event_hashes": event_hashes},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "NET-BATCH-" + hashlib.sha256(payload).hexdigest()[:32]

    @staticmethod
    def _pending_from_state(state: Mapping[str, Any]) -> PendingSendState | None:
        control = state.get("control_v18_7_38")
        if not isinstance(control, Mapping):
            return None
        value = control.get("pending_send")
        if not isinstance(value, Mapping):
            return None
        return PendingSendState(
            batch_id=str(value.get("batch_id") or ""),
            state=str(value.get("state") or ""),
            event_hashes=tuple(str(x) for x in value.get("event_hashes", [])),
            accepted_event_hashes=tuple(
                str(x) for x in value.get("accepted_event_hashes", [])
            ),
            unresolved_event_hashes=tuple(
                str(x) for x in value.get("unresolved_event_hashes", [])
            ),
        )

    @staticmethod
    def _pending_payload(
        *,
        batch_id: str,
        state: str,
        event_hashes: list[str],
        accepted: list[str] | None = None,
        unresolved: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "batch_id": batch_id,
            "state": state,
            "event_hashes": list(event_hashes),
            "accepted_event_hashes": list(accepted or []),
            "unresolved_event_hashes": list(unresolved or []),
        }

    def public_player_id(self, player_id: str) -> str:
        with self.local_lock.exclusive():
            state = self._load()
            mapping = state["public_player_ids"]
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
        with self.local_lock.exclusive():
            state = self._load()
            if len(state["outbox"]) >= MAX_DURABLE_OUTBOX:
                raise NetworkOutboxCapacityError(
                    f"capacity={MAX_DURABLE_OUTBOX};oldest_unsent_event_preserved"
                )
            local_sequence = int(state["next_local_sequence"])
            public_player_id = state["public_player_ids"].setdefault(
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
            state["next_local_sequence"] = local_sequence + 1
            state["last_local_event_hash"] = event_hash
            self._save(state)
            return dict(event)

    def _block_if_pending(self, state: Mapping[str, Any]) -> None:
        pending = self._pending_from_state(state)
        if pending is None:
            return
        raise NetworkSendOutcomeUndetermined(
            f"batch_id={pending.batch_id};state={pending.state};"
            f"unresolved={len(pending.unresolved_event_hashes or pending.event_hashes)};"
            "automatic_remote_resend_blocked_without_verified_hub_idempotency"
        )

    def sync(self, *, limit: int = 200) -> dict[str, Any]:
        # The local lock intentionally spans the remote call in this conservative
        # reference descendant. This trades local queue availability for a simple,
        # reviewable one-writer state machine; it is not a performance claim.
        with self.local_lock.exclusive():
            state = self._load()
            self._block_if_pending(state)
            outbox = list(state["outbox"])
            accepted_count = 0

            if outbox:
                event_hashes = [str(event.get("event_hash") or "") for event in outbox]
                if not all(event_hashes) or len(set(event_hashes)) != len(event_hashes):
                    raise NetworkStateIntegrityError("OUTBOX_EVENT_HASH_IDENTITY_INVALID")
                for event in outbox:
                    valid, error = self.verify_event(event)
                    if not valid:
                        raise NetworkStateIntegrityError(
                            f"OUTBOX_EVENT_INVALID:{error or 'unknown'}"
                        )
                batch_id = self._batch_id(str(state["node_id"]), event_hashes)
                control = state["control_v18_7_38"]
                control["pending_send"] = self._pending_payload(
                    batch_id=batch_id,
                    state="SEND_ENTERING",
                    event_hashes=event_hashes,
                    unresolved=event_hashes,
                )
                self._save(state)
                self.crash_injector.hit(NetworkCrashPoint.AFTER_SEND_ENTERING_BEFORE_REMOTE)

                try:
                    response = self._request(
                        "POST",
                        "/v1/network/events",
                        payload={"events": outbox},
                    )
                except BaseException as exc:
                    raise NetworkSendOutcomeUndetermined(
                        f"batch_id={batch_id};remote_call_returned_no_verifiable_ack;"
                        "automatic_resend_blocked"
                    ) from exc

                accepted = [str(item) for item in response.get("accepted_event_hashes", [])]
                accepted_set = set(accepted)
                sent_set = set(event_hashes)
                if len(accepted_set) != len(accepted):
                    raise NetworkStateIntegrityError("REMOTE_ACK_CONTAINS_DUPLICATE_HASHES")
                if not accepted_set.issubset(sent_set):
                    raise NetworkStateIntegrityError("REMOTE_ACK_REFERENCES_UNSENT_EVENT_HASH")
                self.crash_injector.hit(
                    NetworkCrashPoint.AFTER_REMOTE_RESPONSE_BEFORE_LOCAL_ACK
                )

                unresolved = [value for value in event_hashes if value not in accepted_set]
                state["outbox"] = [
                    event
                    for event in state["outbox"]
                    if str(event.get("event_hash") or "") not in accepted_set
                ]
                accepted_count = len(accepted_set)
                if unresolved:
                    control["pending_send"] = self._pending_payload(
                        batch_id=batch_id,
                        state="PARTIAL_ACK_UNRESOLVED",
                        event_hashes=event_hashes,
                        accepted=accepted,
                        unresolved=unresolved,
                    )
                    self._save(state)
                    raise NetworkSendOutcomeUndetermined(
                        f"batch_id={batch_id};accepted={len(accepted)};"
                        f"unresolved={len(unresolved)};automatic_resend_blocked"
                    )

                receipt = {
                    "batch_id": batch_id,
                    "event_hashes": event_hashes,
                    "accepted_event_hashes": accepted,
                    "complete_ack": True,
                }
                receipts = control.setdefault("completed_send_receipts", [])
                receipts.append(receipt)
                control["completed_send_receipts"] = receipts[-256:]
                control["pending_send"] = None
                self._save(state)

            query = __import__("urllib.parse", fromlist=["urlencode"]).urlencode(
                {
                    "after": int(state.get("hub_cursor", 0)),
                    "limit": max(1, min(1000, int(limit))),
                }
            )
            response = self._request("GET", f"/v1/network/events?{query}")
            received: list[dict[str, Any]] = []
            for envelope in response.get("events", []):
                if not isinstance(envelope, dict) or not isinstance(envelope.get("event"), dict):
                    continue
                valid, _ = self.verify_event(envelope["event"])
                if valid:
                    received.append(envelope)
            state["inbox"] = (state.get("inbox", []) + received)[-2048:]
            state["hub_cursor"] = max(
                int(state.get("hub_cursor", 0)),
                int(response.get("next_cursor", state.get("hub_cursor", 0))),
            )
            self._save(state)
            return {
                "hub_url": self.hub_url,
                "accepted": accepted_count,
                "remaining_outbox": len(state["outbox"]),
                "received": len(received),
                "hub_cursor": state["hub_cursor"],
                "local_save_is_authoritative": True,
                "api_key_persisted": False,
                "hub_idempotency_verified": False,
                "automatic_resend_after_ambiguous_send": False,
            }

    def public_inbox(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        with self.local_lock.shared():
            state = self._load()
            return [
                envelope
                for envelope in state.get("inbox", [])
                if int(envelope.get("network_sequence", 0)) > int(after_sequence)
            ]

    def state(self) -> dict[str, Any]:
        with self.local_lock.shared():
            state = self._load()
            pending = self._pending_from_state(state)
            return {
                "schema": state["schema"],
                "node_id": state["node_id"],
                "hub_cursor": state["hub_cursor"],
                "outbox_count": len(state["outbox"]),
                "inbox_count": len(state["inbox"]),
                "public_player_ids": dict(state["public_player_ids"]),
                "invariants": dict(state["invariants"]),
                "control_schema": DURABLE_NETWORK_SCHEMA,
                "pending_send": None if pending is None else {
                    "batch_id": pending.batch_id,
                    "state": pending.state,
                    "event_hashes": list(pending.event_hashes),
                    "accepted_event_hashes": list(pending.accepted_event_hashes),
                    "unresolved_event_hashes": list(pending.unresolved_event_hashes),
                },
                "hub_idempotency_verified": False,
                "automatic_resend_after_ambiguous_send": False,
            }


__all__ = [
    "DURABLE_NETWORK_VERSION",
    "DURABLE_NETWORK_SCHEMA",
    "MAX_DURABLE_OUTBOX",
    "DurableNetworkError",
    "NetworkStateIntegrityError",
    "NetworkOutboxCapacityError",
    "NetworkSendOutcomeUndetermined",
    "NetworkCrashPoint",
    "NetworkCrashInjector",
    "PendingSendState",
    "DurableGenesisNetworkClient",
]
