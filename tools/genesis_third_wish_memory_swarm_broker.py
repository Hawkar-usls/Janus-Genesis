# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.42 — Third Wish memory + swarm broker.

This descendant makes four already-declared capabilities physically useful:

- MEMORY.READ
- MEMORY.WRITE
- SWARM.TELEMETRY.READ
- SWARM.MESSAGE.SEND

The important boundaries are negative as well as positive:

* MEMORY.WRITE is not canonical world-state authority. It can append/revise a
  separate provenance-rich Third-Wish memory journal but cannot call
  save_player(), save_world(), or rewrite the runtime-owned HRaiN graph.
* HRaiN is exposed through a verified read projection of
  HRAIN-GENESIS-GRAPH-v1.
* SWARM.MESSAGE.SEND is a typed public message carried by the existing durable
  v18.7.38 outbox. The reference hub relays it but does not execute it.
* Stable Third-Wish message request IDs are durably bound across process
  restarts, and the v18.7.38 ambiguous-send state remains authoritative: an
  uncertain remote effect is not silently resent.
* A network node_id is an observed relay identifier, not proof of a real-world
  person, device identity, consciousness, or command authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_35_windows_safe_durable_writer import WindowsSafeDurableJsonWriter
from genesis_v18_7_38_durable_network_outbox import (
    DURABLE_NETWORK_SCHEMA,
    DurableGenesisNetworkClient,
    NetworkSendOutcomeUndetermined,
)
from genesis_v18_7_network import GenesisNetworkClient
from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    CapabilityRequestConflict,
    ThirdWishCapabilityFabric,
)
from janus_portable_lock_v2 import PortableProcessLockV2

MEMORY_SWARM_VERSION = "18.7.42"
THIRD_WISH_MEMORY_SCHEMA = "janus.genesis.third_wish.memory.v1"
THIRD_WISH_MEMORY_RECORD_SCHEMA = "janus.genesis.third_wish.memory.record.v1"
THIRD_WISH_SWARM_SCHEMA = "janus.genesis.third_wish.swarm.v1"
THIRD_WISH_SWARM_MESSAGE_SCHEMA = "janus.genesis.third_wish.swarm.message.v1"
HRAIN_GRAPH_SCHEMA = "HRAIN-GENESIS-GRAPH-v1"
ZERO_HASH = "0" * 64
MAX_MEMORY_RECORD_BYTES = 64 * 1024
MAX_MEMORY_RECORDS = 4096
MAX_MEMORY_READ_ROWS = 200
MAX_SWARM_MESSAGE_BYTES = 4000
MAX_SWARM_METADATA_BYTES = 4096
MAX_SWARM_READ_EVENTS = 200


class MemorySwarmBrokerError(RuntimeError):
    pass


class MemoryIntegrityError(MemorySwarmBrokerError):
    pass


class MemoryRequestConflict(MemorySwarmBrokerError):
    pass


class SwarmRequestConflict(MemorySwarmBrokerError):
    pass


class SwarmBusy(MemorySwarmBrokerError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _integrity_hash(row: Mapping[str, Any]) -> str:
    clean = dict(row)
    clean.pop("integrity_hash", None)
    return _sha256(clean)


def _json_size(value: Any) -> int:
    return len(_canonical(value).encode("utf-8"))


def _require(parameters: Mapping[str, Any], key: str) -> Any:
    if key not in parameters:
        raise MemorySwarmBrokerError(f"MISSING_PARAMETER:{key}")
    return parameters[key]


_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RECORD_ID_RE = re.compile(r"^[a-f0-9]{64}$")


def _namespace(value: str) -> str:
    text = str(value).strip()
    if not _NAMESPACE_RE.fullmatch(text):
        raise MemorySwarmBrokerError("INVALID_MEMORY_NAMESPACE")
    return text


def _node_id(value: str, *, wildcard: bool = False) -> str:
    text = str(value).strip()
    if wildcard and text == "*":
        return text
    if not _NODE_ID_RE.fullmatch(text):
        raise MemorySwarmBrokerError("INVALID_SWARM_NODE_ID")
    return text


def _memory_target(target: str) -> tuple[str, str]:
    prefix = "genesis-memory:"
    text = str(target).strip()
    if not text.startswith(prefix):
        raise MemorySwarmBrokerError("MEMORY_TARGET_PREFIX_REQUIRED")
    suffix = text[len(prefix):]
    if suffix == "hrain/possibility-graph":
        return "HRAIN", "possibility-graph"
    if suffix.startswith("third-wish/"):
        return "THIRD_WISH", _namespace(suffix.split("/", 1)[1])
    raise MemorySwarmBrokerError("MEMORY_TARGET_NOT_GRANTED_BY_REFERENCE_BROKER")


def _swarm_target(target: str) -> str:
    prefix = "janus-swarm:"
    text = str(target).strip()
    if not text.startswith(prefix):
        raise MemorySwarmBrokerError("SWARM_TARGET_PREFIX_REQUIRED")
    return _node_id(text[len(prefix):], wildcard=True)


class ThirdWishMemoryStore:
    """Durable append/revision journal separate from canonical Genesis state."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "third_wish_memory_v18_7_42.json"
        self.lock = PortableProcessLockV2(self.root / "third_wish_memory_v18_7_42.lock")
        self.writer = WindowsSafeDurableJsonWriter()
        with self.lock.exclusive():
            if not self.path.exists():
                self._save(self._default_state())
            else:
                self._load()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "schema": THIRD_WISH_MEMORY_SCHEMA,
            "next_sequence": 1,
            "last_record_hash": ZERO_HASH,
            "records": [],
            "request_bindings": {},
            "invariants": {
                "canonical_world_state_mutated": False,
                "canonical_player_state_mutated": False,
                "runtime_hrain_graph_mutated": False,
                "append_revision_only": True,
                "deletion_supported": False,
                "memory_is_world_authority": False,
            },
        }

    def _load(self) -> dict[str, Any]:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryIntegrityError("THIRD_WISH_MEMORY_UNREADABLE") from exc
        if not isinstance(state, dict) or state.get("schema") != THIRD_WISH_MEMORY_SCHEMA:
            raise MemoryIntegrityError("THIRD_WISH_MEMORY_SCHEMA_INVALID")
        records = state.get("records")
        bindings = state.get("request_bindings")
        if not isinstance(records, list) or not isinstance(bindings, dict):
            raise MemoryIntegrityError("THIRD_WISH_MEMORY_SHAPE_INVALID")
        if len(records) > MAX_MEMORY_RECORDS:
            raise MemoryIntegrityError("THIRD_WISH_MEMORY_OVER_CAPACITY")
        previous = ZERO_HASH
        for index, record in enumerate(records, 1):
            if not isinstance(record, dict):
                raise MemoryIntegrityError("MEMORY_RECORD_NOT_OBJECT")
            if record.get("schema") != THIRD_WISH_MEMORY_RECORD_SCHEMA:
                raise MemoryIntegrityError("MEMORY_RECORD_SCHEMA_INVALID")
            if int(record.get("sequence", 0)) != index:
                raise MemoryIntegrityError("MEMORY_RECORD_SEQUENCE_INVALID")
            if record.get("previous_record_hash") != previous:
                raise MemoryIntegrityError("MEMORY_RECORD_CHAIN_BROKEN")
            observed = str(record.get("record_hash") or "")
            unsigned = dict(record)
            unsigned.pop("record_hash", None)
            if _sha256(unsigned) != observed:
                raise MemoryIntegrityError("MEMORY_RECORD_HASH_INVALID")
            previous = observed
        if str(state.get("last_record_hash") or ZERO_HASH) != previous:
            raise MemoryIntegrityError("MEMORY_LAST_HASH_INVALID")
        if int(state.get("next_sequence", 0)) != len(records) + 1:
            raise MemoryIntegrityError("MEMORY_NEXT_SEQUENCE_INVALID")
        return state

    def _save(self, state: Mapping[str, Any]) -> None:
        self.writer.write(self.path, dict(state))

    @staticmethod
    def _binding_hash(
        *,
        actor_id: str,
        namespace: str,
        kind: str,
        content: Mapping[str, Any],
        supersedes_record_id: str | None,
    ) -> str:
        return _sha256({
            "actor_id": actor_id,
            "namespace": namespace,
            "kind": kind,
            "content": dict(content),
            "supersedes_record_id": supersedes_record_id,
        })

    def append(
        self,
        *,
        actor_id: str,
        namespace: str,
        request_id: str,
        kind: str,
        content: Mapping[str, Any],
        supersedes_record_id: str | None = None,
    ) -> dict[str, Any]:
        namespace = _namespace(namespace)
        request_id = str(request_id).strip()
        kind = str(kind).strip().upper()
        if not request_id:
            raise MemorySwarmBrokerError("MEMORY_REQUEST_ID_REQUIRED")
        if not kind or len(kind) > 64:
            raise MemorySwarmBrokerError("MEMORY_KIND_INVALID")
        content_dict = copy.deepcopy(dict(content))
        if _json_size(content_dict) > MAX_MEMORY_RECORD_BYTES:
            raise MemorySwarmBrokerError("MEMORY_RECORD_TOO_LARGE")
        if supersedes_record_id is not None:
            supersedes_record_id = str(supersedes_record_id).lower()
            if not _RECORD_ID_RE.fullmatch(supersedes_record_id):
                raise MemorySwarmBrokerError("SUPERSEDES_RECORD_ID_INVALID")

        binding_hash = self._binding_hash(
            actor_id=str(actor_id),
            namespace=namespace,
            kind=kind,
            content=content_dict,
            supersedes_record_id=supersedes_record_id,
        )
        with self.lock.exclusive():
            state = self._load()
            existing = state["request_bindings"].get(request_id)
            if existing is not None:
                if not isinstance(existing, dict) or existing.get("binding_hash") != binding_hash:
                    raise MemoryRequestConflict(request_id)
                record_id = str(existing.get("record_id") or "")
                match = next((row for row in state["records"] if row.get("record_id") == record_id), None)
                if match is None:
                    raise MemoryIntegrityError("MEMORY_REQUEST_BINDING_DANGLING")
                return copy.deepcopy(match)

            if len(state["records"]) >= MAX_MEMORY_RECORDS:
                raise MemorySwarmBrokerError("THIRD_WISH_MEMORY_CAPACITY_REACHED")
            if supersedes_record_id is not None:
                parent = next(
                    (row for row in state["records"] if row.get("record_id") == supersedes_record_id),
                    None,
                )
                if parent is None:
                    raise MemorySwarmBrokerError("SUPERSEDED_RECORD_NOT_FOUND")
                if parent.get("namespace") != namespace:
                    raise MemorySwarmBrokerError("CROSS_NAMESPACE_REVISION_BLOCKED")

            sequence = int(state["next_sequence"])
            record_id = _sha256({
                "schema": THIRD_WISH_MEMORY_RECORD_SCHEMA,
                "request_id": request_id,
                "binding_hash": binding_hash,
                "sequence": sequence,
            })
            record = {
                "schema": THIRD_WISH_MEMORY_RECORD_SCHEMA,
                "sequence": sequence,
                "record_id": record_id,
                "request_id": request_id,
                "actor_id": str(actor_id),
                "namespace": namespace,
                "kind": kind,
                "content": content_dict,
                "content_sha256": _sha256(content_dict),
                "supersedes_record_id": supersedes_record_id,
                "previous_record_hash": state["last_record_hash"],
                "canonical_world_effect": False,
                "canonical_hrain_graph_effect": False,
            }
            unsigned = dict(record)
            record["record_hash"] = _sha256(unsigned)
            state["records"].append(record)
            state["last_record_hash"] = record["record_hash"]
            state["next_sequence"] = sequence + 1
            state["request_bindings"][request_id] = {
                "binding_hash": binding_hash,
                "record_id": record_id,
            }
            self._save(state)
            return copy.deepcopy(record)

    def list_records(self, namespace: str, *, limit: int = 100) -> list[dict[str, Any]]:
        namespace = _namespace(namespace)
        limit = max(1, min(MAX_MEMORY_READ_ROWS, int(limit)))
        with self.lock.exclusive():
            state = self._load()
            rows = [row for row in state["records"] if row.get("namespace") == namespace]
        return copy.deepcopy(rows[-limit:])

    def get_record(self, namespace: str, record_id: str) -> dict[str, Any] | None:
        namespace = _namespace(namespace)
        record_id = str(record_id).lower()
        if not _RECORD_ID_RE.fullmatch(record_id):
            raise MemorySwarmBrokerError("MEMORY_RECORD_ID_INVALID")
        with self.lock.exclusive():
            state = self._load()
            row = next(
                (
                    item
                    for item in state["records"]
                    if item.get("namespace") == namespace and item.get("record_id") == record_id
                ),
                None,
            )
        return copy.deepcopy(row) if row is not None else None

    def state_summary(self) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
        namespaces = sorted({str(row.get("namespace")) for row in state["records"]})
        return {
            "schema": state["schema"],
            "record_count": len(state["records"]),
            "namespaces": namespaces,
            "last_record_hash": state["last_record_hash"],
            "invariants": dict(state["invariants"]),
        }


class HRaiNReadProjection:
    """Verified read-only projection of the runtime-owned v18.6 HRaiN graph."""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "hrain_genesis_graph_v18_6.json"

    def read(
        self,
        *,
        node_type: str | None = None,
        limit: int = 100,
        include_payload: bool = True,
    ) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": HRAIN_GRAPH_SCHEMA,
                "exists": False,
                "integrity_valid": True,
                "nodes": [],
                "edges": [],
                "runtime_graph_mutated": False,
            }
        try:
            graph = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryIntegrityError("HRAIN_GRAPH_UNREADABLE") from exc
        if not isinstance(graph, dict) or graph.get("schema_version") != HRAIN_GRAPH_SCHEMA:
            raise MemoryIntegrityError("HRAIN_GRAPH_SCHEMA_INVALID")
        nodes = graph.get("nodes")
        edges = graph.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise MemoryIntegrityError("HRAIN_GRAPH_SHAPE_INVALID")
        for row in [*nodes, *edges]:
            if not isinstance(row, dict) or str(row.get("integrity_hash") or "") != _integrity_hash(row):
                raise MemoryIntegrityError("HRAIN_GRAPH_INTEGRITY_INVALID")
        limit = max(1, min(MAX_MEMORY_READ_ROWS, int(limit)))
        selected = [row for row in nodes if node_type is None or row.get("type") == node_type][:limit]
        projected_nodes: list[dict[str, Any]] = []
        for row in selected:
            projected = {
                "id": row.get("id"),
                "type": row.get("type"),
                "source": row.get("source"),
                "created_at": row.get("created_at"),
                "confidence": row.get("confidence"),
                "mutable": row.get("mutable"),
                "integrity_hash": row.get("integrity_hash"),
            }
            if include_payload:
                projected["payload"] = copy.deepcopy(row.get("payload", {}))
            projected_nodes.append(projected)
        selected_ids = {str(row.get("id")) for row in selected}
        projected_edges = [
            copy.deepcopy(row)
            for row in edges
            if str(row.get("from")) in selected_ids or str(row.get("to")) in selected_ids
        ][:limit]
        return {
            "schema_version": graph["schema_version"],
            "exists": True,
            "integrity_valid": True,
            "canonical_seed_sha256": graph.get("canonical_seed_sha256"),
            "node_count_total": len(nodes),
            "edge_count_total": len(edges),
            "nodes": projected_nodes,
            "edges": projected_edges,
            "runtime_graph_mutated": False,
            "projection_only": True,
        }


_ALLOWED_MESSAGE_TYPES = frozenset(
    {"HELLO", "NOTE", "QUERY", "RESPONSE", "STATUS_REQUEST", "STATUS_REPORT"}
)
_EXECUTION_KEY_FRAGMENTS = ("command", "exec", "shell", "subprocess", "action_to_execute", "remote_action")


def _assert_nonexecuting_metadata(value: Any, *, path: str = "metadata") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if any(fragment in normalized for fragment in _EXECUTION_KEY_FRAGMENTS):
                raise MemorySwarmBrokerError(f"EXECUTABLE_MESSAGE_FIELD_BLOCKED:{path}.{key}")
            _assert_nonexecuting_metadata(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_nonexecuting_metadata(item, path=f"{path}[{index}]")


class SwarmRequestStore:
    """Persistent request binding around one dedicated durable network client."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "third_wish_swarm_requests_v18_7_42.json"
        self.lock = PortableProcessLockV2(self.root / "third_wish_swarm_requests_v18_7_42.lock")
        self.writer = WindowsSafeDurableJsonWriter()
        with self.lock.exclusive():
            if not self.path.exists():
                self._save({
                    "schema": THIRD_WISH_SWARM_SCHEMA,
                    "requests": {},
                    "invariants": {
                        "request_id_rebind_allowed": False,
                        "message_is_remote_command": False,
                        "peer_node_id_is_real_world_identity_proof": False,
                    },
                })
            else:
                self._load()

    def _load(self) -> dict[str, Any]:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MemoryIntegrityError("SWARM_REQUEST_STORE_UNREADABLE") from exc
        if not isinstance(state, dict) or state.get("schema") != THIRD_WISH_SWARM_SCHEMA:
            raise MemoryIntegrityError("SWARM_REQUEST_STORE_SCHEMA_INVALID")
        if not isinstance(state.get("requests"), dict):
            raise MemoryIntegrityError("SWARM_REQUEST_STORE_SHAPE_INVALID")
        return state

    def _save(self, state: Mapping[str, Any]) -> None:
        self.writer.write(self.path, dict(state))

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self.lock.exclusive():
            value = self._load()["requests"].get(str(request_id))
        return copy.deepcopy(value) if isinstance(value, dict) else None

    def bind(self, request_id: str, binding_hash: str) -> dict[str, Any]:
        request_id = str(request_id).strip()
        with self.lock.exclusive():
            state = self._load()
            existing = state["requests"].get(request_id)
            if existing is not None:
                if not isinstance(existing, dict) or existing.get("binding_hash") != binding_hash:
                    raise SwarmRequestConflict(request_id)
                return copy.deepcopy(existing)
            value = {
                "binding_hash": binding_hash,
                "state": "BOUND",
                "event_hash": None,
                "receipt": None,
            }
            state["requests"][request_id] = value
            self._save(state)
            return copy.deepcopy(value)

    def update(self, request_id: str, **fields: Any) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
            value = state["requests"].get(str(request_id))
            if not isinstance(value, dict):
                raise MemoryIntegrityError("SWARM_REQUEST_BINDING_MISSING")
            value.update(copy.deepcopy(fields))
            state["requests"][str(request_id)] = value
            self._save(state)
            return copy.deepcopy(value)


@dataclass
class ThirdWishMemorySwarmBroker:
    data_dir: Path
    memory_store: ThirdWishMemoryStore
    hrain: HRaiNReadProjection
    network: DurableGenesisNetworkClient
    swarm_requests: SwarmRequestStore

    REGISTERED_CAPABILITIES = (
        "MEMORY.READ",
        "MEMORY.WRITE",
        "SWARM.TELEMETRY.READ",
        "SWARM.MESSAGE.SEND",
    )

    @classmethod
    def system(
        cls,
        data_dir: str | Path,
        *,
        hub_url: str,
        network_key_env: str = "GENESIS_NETWORK_API_KEY",
        timeout_seconds: float = 20.0,
    ) -> "ThirdWishMemorySwarmBroker":
        root = Path(data_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        swarm_root = root / "third_wish_swarm_v18_7_42"
        swarm_root.mkdir(parents=True, exist_ok=True)
        return cls(
            data_dir=root,
            memory_store=ThirdWishMemoryStore(root),
            hrain=HRaiNReadProjection(root),
            network=DurableGenesisNetworkClient(
                swarm_root,
                hub_url=hub_url,
                api_key_env=network_key_env,
                timeout_seconds=timeout_seconds,
            ),
            swarm_requests=SwarmRequestStore(swarm_root),
        )

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        handlers = {
            "MEMORY.READ": self.memory_read,
            "MEMORY.WRITE": self.memory_write,
            "SWARM.TELEMETRY.READ": self.swarm_telemetry_read,
            "SWARM.MESSAGE.SEND": self.swarm_message_send,
        }
        for capability_id, handler in handlers.items():
            fabric.register_handler(capability_id, handler, preflight=self.preflight)

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        cap = intent.capability_id
        operation = intent.operation.upper()
        p = intent.parameters
        if cap == "MEMORY.READ":
            domain, _ = _memory_target(intent.target)
            allowed = {"LIST_RECORDS", "GET_RECORD"} if domain == "THIRD_WISH" else {"READ_GRAPH"}
            if operation not in allowed:
                raise MemorySwarmBrokerError("UNSUPPORTED_MEMORY_READ_OPERATION")
            if operation == "GET_RECORD":
                record_id = str(_require(p, "record_id")).lower()
                if not _RECORD_ID_RE.fullmatch(record_id):
                    raise MemorySwarmBrokerError("MEMORY_RECORD_ID_INVALID")
            if "limit" in p:
                limit = int(p["limit"])
                if not 1 <= limit <= MAX_MEMORY_READ_ROWS:
                    raise MemorySwarmBrokerError("MEMORY_READ_LIMIT_OUT_OF_RANGE")
        elif cap == "MEMORY.WRITE":
            domain, _ = _memory_target(intent.target)
            if domain != "THIRD_WISH":
                raise CapabilityDenied("RUNTIME_HRAIN_GRAPH_IS_READ_ONLY_TO_THIRD_WISH")
            if operation not in {"APPEND_RECORD", "APPEND_REVISION"}:
                raise MemorySwarmBrokerError("UNSUPPORTED_MEMORY_WRITE_OPERATION")
            content = _require(p, "content")
            if not isinstance(content, Mapping):
                raise MemorySwarmBrokerError("MEMORY_CONTENT_MUST_BE_OBJECT")
            if _json_size(content) > MAX_MEMORY_RECORD_BYTES:
                raise MemorySwarmBrokerError("MEMORY_RECORD_TOO_LARGE")
            if operation == "APPEND_REVISION":
                record_id = str(_require(p, "supersedes_record_id")).lower()
                if not _RECORD_ID_RE.fullmatch(record_id):
                    raise MemorySwarmBrokerError("SUPERSEDES_RECORD_ID_INVALID")
        elif cap == "SWARM.TELEMETRY.READ":
            _swarm_target(intent.target)
            if operation != "READ_PUBLIC_EVENTS":
                raise MemorySwarmBrokerError("UNSUPPORTED_SWARM_TELEMETRY_OPERATION")
            limit = int(p.get("limit", 100))
            if not 1 <= limit <= MAX_SWARM_READ_EVENTS:
                raise MemorySwarmBrokerError("SWARM_READ_LIMIT_OUT_OF_RANGE")
            if int(p.get("after", 0)) < 0:
                raise MemorySwarmBrokerError("SWARM_CURSOR_MUST_BE_NONNEGATIVE")
        elif cap == "SWARM.MESSAGE.SEND":
            _swarm_target(intent.target)
            if operation != "SEND_MESSAGE":
                raise MemorySwarmBrokerError("UNSUPPORTED_SWARM_SEND_OPERATION")
            message_type = str(_require(p, "message_type")).upper()
            if message_type not in _ALLOWED_MESSAGE_TYPES:
                raise MemorySwarmBrokerError("SWARM_MESSAGE_TYPE_NOT_NONEXECUTING")
            body = str(_require(p, "body"))
            if len(body.encode("utf-8")) > MAX_SWARM_MESSAGE_BYTES:
                raise MemorySwarmBrokerError("SWARM_MESSAGE_TOO_LARGE")
            metadata = p.get("metadata", {})
            if not isinstance(metadata, Mapping) or _json_size(metadata) > MAX_SWARM_METADATA_BYTES:
                raise MemorySwarmBrokerError("SWARM_METADATA_INVALID")
            _assert_nonexecuting_metadata(metadata)
            existing = self.swarm_requests.get(intent.request_id)
            binding_hash = self._swarm_binding_hash(intent)
            if existing is not None and existing.get("binding_hash") != binding_hash:
                raise SwarmRequestConflict(intent.request_id)
            if existing is None:
                self._assert_dedicated_swarm_idle()
        else:
            raise MemorySwarmBrokerError("CAPABILITY_NOT_INSTALLED_BY_MEMORY_SWARM_BROKER")
        return {
            "validated": True,
            "capability_id": cap,
            "operation": operation,
            "canonical_world_state_mutation": False,
            "remote_command_authority": False,
            "external_call_entered": False,
        }

    def memory_read(self, intent: ActionIntent) -> Mapping[str, Any]:
        domain, name = _memory_target(intent.target)
        operation = intent.operation.upper()
        if domain == "HRAIN":
            return self.hrain.read(
                node_type=str(intent.parameters["node_type"]) if intent.parameters.get("node_type") else None,
                limit=int(intent.parameters.get("limit", 100)),
                include_payload=bool(intent.parameters.get("include_payload", True)),
            )
        if operation == "LIST_RECORDS":
            rows = self.memory_store.list_records(name, limit=int(intent.parameters.get("limit", 100)))
            return {
                "namespace": name,
                "records": rows,
                "record_count": len(rows),
                "canonical_world_state_mutated": False,
            }
        if operation == "GET_RECORD":
            row = self.memory_store.get_record(name, str(_require(intent.parameters, "record_id")))
            return {
                "namespace": name,
                "found": row is not None,
                "record": row,
                "canonical_world_state_mutated": False,
            }
        raise MemorySwarmBrokerError("UNSUPPORTED_MEMORY_READ_OPERATION")

    def memory_write(self, intent: ActionIntent) -> Mapping[str, Any]:
        domain, namespace = _memory_target(intent.target)
        if domain != "THIRD_WISH":
            raise CapabilityDenied("RUNTIME_HRAIN_GRAPH_IS_READ_ONLY_TO_THIRD_WISH")
        operation = intent.operation.upper()
        supersedes = None
        if operation == "APPEND_REVISION":
            supersedes = str(_require(intent.parameters, "supersedes_record_id"))
        elif operation != "APPEND_RECORD":
            raise MemorySwarmBrokerError("UNSUPPORTED_MEMORY_WRITE_OPERATION")
        record = self.memory_store.append(
            actor_id=intent.actor_id,
            namespace=namespace,
            request_id=intent.request_id,
            kind=str(intent.parameters.get("kind", "NOTE")),
            content=dict(_require(intent.parameters, "content")),
            supersedes_record_id=supersedes,
        )
        return {
            "namespace": namespace,
            "record": record,
            "append_only": True,
            "revision_is_lineage_not_overwrite": supersedes is not None,
            "canonical_world_state_mutated": False,
            "runtime_hrain_graph_mutated": False,
        }

    def _network_state(self) -> dict[str, Any]:
        with self.network.local_lock.exclusive():
            return copy.deepcopy(self.network._load())

    def _assert_dedicated_swarm_idle(self) -> None:
        state = self._network_state()
        control = state.get("control_v18_7_38")
        if not isinstance(control, Mapping) or control.get("schema") != DURABLE_NETWORK_SCHEMA:
            raise MemoryIntegrityError("DURABLE_SWARM_CONTROL_STATE_INVALID")
        if control.get("pending_send") is not None:
            raise SwarmBusy("SWARM_PENDING_SEND_MUST_BE_RECONCILED")
        if state.get("outbox"):
            raise SwarmBusy("DEDICATED_THIRD_WISH_SWARM_OUTBOX_NOT_EMPTY")

    @staticmethod
    def _swarm_binding_hash(intent: ActionIntent) -> str:
        p = intent.parameters
        return _sha256({
            "actor_id": intent.actor_id,
            "target": intent.target,
            "message_type": str(p.get("message_type", "")).upper(),
            "body": str(p.get("body", "")),
            "metadata": dict(p.get("metadata", {})),
        })

    def _recover_swarm_request(self, intent: ActionIntent, stored: Mapping[str, Any]) -> Mapping[str, Any] | None:
        if stored.get("state") == "SETTLED" and isinstance(stored.get("receipt"), Mapping):
            return copy.deepcopy(dict(stored["receipt"]))
        event_hash = str(stored.get("event_hash") or "")
        if not event_hash:
            return None
        state = self._network_state()
        control = state.get("control_v18_7_38", {})
        pending = control.get("pending_send") if isinstance(control, Mapping) else None
        if isinstance(pending, Mapping) and event_hash in set(str(x) for x in pending.get("event_hashes", [])):
            raise NetworkSendOutcomeUndetermined(
                f"request_id={intent.request_id};event_hash={event_hash};durable_pending_send_blocks_resend"
            )
        completed = control.get("completed_send_receipts", []) if isinstance(control, Mapping) else []
        for receipt in completed if isinstance(completed, list) else []:
            if isinstance(receipt, Mapping) and event_hash in set(str(x) for x in receipt.get("accepted_event_hashes", [])):
                response = {
                    "message_id": str(stored.get("message_id") or ""),
                    "event_hash": event_hash,
                    "recipient_node_id": _swarm_target(intent.target),
                    "settled": True,
                    "recovered_from_durable_network_receipt": True,
                    "message_is_remote_command": False,
                    "remote_execution_authority": False,
                }
                self.swarm_requests.update(intent.request_id, state="SETTLED", receipt=response)
                return response
        outbox_hashes = {
            str(row.get("event_hash") or "")
            for row in state.get("outbox", [])
            if isinstance(row, Mapping)
        }
        if event_hash not in outbox_hashes:
            raise MemoryIntegrityError("SWARM_BOUND_EVENT_MISSING_WITHOUT_RECEIPT")
        return None

    def swarm_message_send(self, intent: ActionIntent) -> Mapping[str, Any]:
        binding_hash = self._swarm_binding_hash(intent)
        stored = self.swarm_requests.bind(intent.request_id, binding_hash)
        recovered = self._recover_swarm_request(intent, stored)
        if recovered is not None:
            return recovered

        event_hash = str(stored.get("event_hash") or "")
        recipient = _swarm_target(intent.target)
        message_type = str(_require(intent.parameters, "message_type")).upper()
        metadata = copy.deepcopy(dict(intent.parameters.get("metadata", {})))
        _assert_nonexecuting_metadata(metadata)
        message_id = _sha256({
            "request_id": intent.request_id,
            "actor_id": intent.actor_id,
            "target": intent.target,
            "binding_hash": binding_hash,
        })

        if not event_hash:
            self._assert_dedicated_swarm_idle()
            event = self.network.queue_public_event(
                intent.actor_id,
                "public_message",
                {
                    "schema": THIRD_WISH_SWARM_MESSAGE_SCHEMA,
                    "message_id": message_id,
                    "recipient_node_id": recipient,
                    "message_type": message_type,
                    "body": str(_require(intent.parameters, "body")),
                    "metadata": metadata,
                    "executable": False,
                    "remote_action_authority": False,
                },
            )
            event_hash = str(event["event_hash"])
            self.swarm_requests.update(
                intent.request_id,
                state="QUEUED",
                event_hash=event_hash,
                message_id=message_id,
            )

        result = self.network.sync(limit=MAX_SWARM_READ_EVENTS)
        if int(result.get("remaining_outbox", -1)) != 0:
            raise NetworkSendOutcomeUndetermined(
                f"request_id={intent.request_id};event_hash={event_hash};outbox_not_empty_after_send"
            )
        state = self._network_state()
        control = state.get("control_v18_7_38", {})
        completed = control.get("completed_send_receipts", []) if isinstance(control, Mapping) else []
        if not any(
            isinstance(row, Mapping)
            and event_hash in set(str(x) for x in row.get("accepted_event_hashes", []))
            for row in completed if isinstance(completed, list)
        ):
            raise NetworkSendOutcomeUndetermined(
                f"request_id={intent.request_id};event_hash={event_hash};complete_ack_not_durable"
            )
        response = {
            "message_id": message_id,
            "event_hash": event_hash,
            "recipient_node_id": recipient,
            "message_type": message_type,
            "settled": True,
            "accepted": int(result.get("accepted", 0)),
            "message_is_remote_command": False,
            "remote_execution_authority": False,
            "peer_identity_cryptographically_attested": False,
        }
        self.swarm_requests.update(intent.request_id, state="SETTLED", receipt=response)
        return response

    def swarm_telemetry_read(self, intent: ActionIntent) -> Mapping[str, Any]:
        target_node = _swarm_target(intent.target)
        after = max(0, int(intent.parameters.get("after", 0)))
        limit = max(1, min(MAX_SWARM_READ_EVENTS, int(intent.parameters.get("limit", 100))))
        query = __import__("urllib.parse", fromlist=["urlencode"]).urlencode({"after": after, "limit": limit})
        response = self.network._request("GET", f"/v1/network/events?{query}")
        rows: list[dict[str, Any]] = []
        invalid = 0
        for envelope in response.get("events", []):
            if not isinstance(envelope, Mapping) or not isinstance(envelope.get("event"), Mapping):
                invalid += 1
                continue
            event = dict(envelope["event"])
            valid, _ = GenesisNetworkClient.verify_event(event)
            if not valid:
                invalid += 1
                continue
            node_id = str(event.get("node_id") or "")
            if target_node != "*" and node_id != target_node:
                continue
            payload = copy.deepcopy(event.get("payload", {}))
            rows.append({
                "network_sequence": int(envelope.get("network_sequence", 0)),
                "event_hash": event.get("event_hash"),
                "node_id": node_id,
                "public_player_id": event.get("public_player_id"),
                "kind": event.get("kind"),
                "occurred_at": event.get("occurred_at"),
                "payload": payload,
                "event_integrity_valid": True,
                "event_is_remote_command": False,
            })
        return {
            "target_node_id": target_node,
            "events": rows,
            "event_count": len(rows),
            "invalid_envelopes_omitted": invalid,
            "next_cursor": int(response.get("next_cursor", after)),
            "hub_may_rewrite_local_state": False,
            "peer_node_id_is_real_world_identity_proof": False,
            "telemetry_read_grants_remote_execution_authority": False,
        }


MEMORY_SWARM_CLAIM_BOUNDARY = {
    "registered_capability_count": len(ThirdWishMemorySwarmBroker.REGISTERED_CAPABILITIES),
    "memory_write_can_save_player": False,
    "memory_write_can_save_world": False,
    "memory_write_can_mutate_runtime_hrain_graph": False,
    "memory_revision_overwrites_history": False,
    "hrain_projection_verifies_integrity": True,
    "swarm_message_is_remote_command": False,
    "swarm_message_remote_execution_authority": False,
    "swarm_send_uses_durable_v18_7_38_outbox": True,
    "ambiguous_swarm_send_auto_retried": False,
    "stable_swarm_request_bound_across_restart": True,
    "peer_node_id_is_real_world_identity_proof": False,
    "swarm_hub_can_rewrite_local_genesis_state": False,
    "raw_network_key_visible_to_actor": False,
    "capability_is_command": False,
}
