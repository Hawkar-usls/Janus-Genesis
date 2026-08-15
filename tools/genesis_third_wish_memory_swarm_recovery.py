# -*- coding: utf-8 -*-
"""v18.7.42 recovery wrapper for the Third Wish memory/swarm broker.

This reference descendant closes two liveness/precision gaps without weakening
fail-closed effect handling:

1. Memory request conflicts and invalid revision ancestry are fully knowable from
   the local durable memory store. They are validated in preflight and therefore
   become PRE_EFFECT_REJECTED rather than false OUTCOME_UNDETERMINED states.
2. A process may die after queue_public_event() but before the Third-Wish request
   store records the returned event hash. Stable message_id recovery binds the
   already queued event instead of creating a duplicate.

One process/host swarm-send lock also serializes complete Third-Wish sends so two
independent intents do not accidentally share one network batch. The v18.7.38
durable outbox remains authoritative after SEND_ENTERING; pending or ambiguous
remote sends never manufacture automatic retry consent.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_40_third_wish_capability_fabric import ActionIntent
from janus_portable_lock_v2 import PortableProcessLockV2
from tools.genesis_third_wish_memory_swarm_broker import (
    MemoryRequestConflict,
    MemorySwarmBrokerError,
    THIRD_WISH_SWARM_MESSAGE_SCHEMA,
    ThirdWishMemorySwarmBroker,
    _memory_target,
    _require,
    _sha256,
)


class RecoverableThirdWishMemorySwarmBroker(ThirdWishMemorySwarmBroker):
    """Reference v18.7.42 broker with precise preflight and crash recovery."""

    @property
    def swarm_send_lock(self) -> PortableProcessLockV2:
        return PortableProcessLockV2(
            Path(self.network.root) / "third_wish_swarm_send_v18_7_42.lock"
        )

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        """Extend base validation with durable, known-no-effect memory checks.

        These checks inspect only the Third-Wish memory journal. No external
        transport, canonical world mutation, HRaiN write, or handler effect is
        entered here.
        """
        result = dict(super().preflight(intent))
        if intent.capability_id != "MEMORY.WRITE":
            return result

        domain, namespace = _memory_target(intent.target)
        if domain != "THIRD_WISH":
            # Base preflight already rejects this path. Keep the guard explicit
            # so future descendants do not accidentally treat runtime HRaiN as
            # a writable memory namespace.
            return result

        operation = intent.operation.upper()
        content = dict(_require(intent.parameters, "content"))
        kind = str(intent.parameters.get("kind", "NOTE")).strip().upper()
        supersedes_record_id: str | None = None
        if operation == "APPEND_REVISION":
            supersedes_record_id = str(
                _require(intent.parameters, "supersedes_record_id")
            ).lower()

        binding_hash = self.memory_store._binding_hash(
            actor_id=intent.actor_id,
            namespace=namespace,
            kind=kind,
            content=content,
            supersedes_record_id=supersedes_record_id,
        )

        with self.memory_store.lock.exclusive():
            state = self.memory_store._load()
            existing = state["request_bindings"].get(intent.request_id)
            if existing is not None:
                if (
                    not isinstance(existing, Mapping)
                    or existing.get("binding_hash") != binding_hash
                ):
                    raise MemoryRequestConflict(intent.request_id)
                # Exact durable replay is already bound to a historical record.
                # It does not need to re-prove the ancestor's current lookup.
                result["durable_memory_request_replay"] = True
                return result

            if operation == "APPEND_REVISION":
                parent = next(
                    (
                        row
                        for row in state["records"]
                        if row.get("record_id") == supersedes_record_id
                    ),
                    None,
                )
                if parent is None:
                    raise MemorySwarmBrokerError("SUPERSEDED_RECORD_NOT_FOUND")
                if parent.get("namespace") != namespace:
                    raise MemorySwarmBrokerError(
                        "CROSS_NAMESPACE_REVISION_BLOCKED"
                    )

        result["durable_memory_request_conflict_checked"] = True
        result["memory_revision_ancestry_checked"] = operation == "APPEND_REVISION"
        return result

    @staticmethod
    def deterministic_message_id(intent: ActionIntent, binding_hash: str) -> str:
        return _sha256({
            "request_id": intent.request_id,
            "actor_id": intent.actor_id,
            "target": intent.target,
            "binding_hash": binding_hash,
        })

    def _find_queued_event_by_message_id(self, message_id: str) -> dict[str, Any] | None:
        state = self._network_state()
        matches: list[dict[str, Any]] = []
        for row in state.get("outbox", []):
            if not isinstance(row, Mapping):
                continue
            payload = row.get("payload")
            if not isinstance(payload, Mapping):
                continue
            if payload.get("schema") != THIRD_WISH_SWARM_MESSAGE_SCHEMA:
                continue
            if str(payload.get("message_id") or "") != str(message_id):
                continue
            matches.append(dict(row))
        if len(matches) > 1:
            from tools.genesis_third_wish_memory_swarm_broker import MemoryIntegrityError
            raise MemoryIntegrityError(
                "DUPLICATE_QUEUED_EVENTS_FOR_ONE_THIRD_WISH_MESSAGE_ID"
            )
        return copy.deepcopy(matches[0]) if matches else None

    def _recover_unbound_queue_gap(
        self,
        intent: ActionIntent,
        stored: Mapping[str, Any],
        binding_hash: str,
    ) -> dict[str, Any]:
        current = copy.deepcopy(dict(stored))
        if current.get("event_hash"):
            return current
        message_id = self.deterministic_message_id(intent, binding_hash)
        queued = self._find_queued_event_by_message_id(message_id)
        if queued is None:
            return current
        event_hash = str(queued.get("event_hash") or "")
        if not event_hash:
            from tools.genesis_third_wish_memory_swarm_broker import MemoryIntegrityError
            raise MemoryIntegrityError("RECOVERED_SWARM_EVENT_HAS_NO_HASH")
        return self.swarm_requests.update(
            intent.request_id,
            state="QUEUED",
            event_hash=event_hash,
            message_id=message_id,
            recovered_after_queue_before_binding=True,
        )

    def swarm_message_send(self, intent: ActionIntent):
        # A separate lock spans request binding, queue recovery/creation, the
        # v18.7.38 send, and receipt binding. The network client still keeps its
        # own lower-level local lock for network-state integrity.
        with self.swarm_send_lock.exclusive():
            binding_hash = self._swarm_binding_hash(intent)
            stored = self.swarm_requests.bind(intent.request_id, binding_hash)
            self._recover_unbound_queue_gap(intent, stored, binding_hash)
            return super().swarm_message_send(intent)


MEMORY_SWARM_RECOVERY_CLAIMS = {
    "reference_class": "RecoverableThirdWishMemorySwarmBroker",
    "persistent_memory_request_conflict_pre_effect": True,
    "invalid_memory_revision_parent_pre_effect": True,
    "stable_message_id_before_queue": True,
    "queued_event_recovered_by_message_id": True,
    "crash_after_queue_before_request_event_hash_causes_duplicate": False,
    "third_wish_swarm_sends_serialized": True,
    "v18_7_38_ambiguous_send_can_be_auto_retried": False,
    "cross_host_consensus_claimed": False,
}
