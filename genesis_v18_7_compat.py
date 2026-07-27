# -*- coding: utf-8 -*-
"""Compatibility and safety overrides used only by Genesis v18.7."""
from __future__ import annotations

from typing import Any

from genesis_v18_models import WorldResult


class GenesisV187CompatibilityMixin:
    """Preserve earlier APIs while fixing boundaries discovered by lived tests."""

    def _upsert_node(
        self,
        graph: dict[str, Any],
        *,
        node_id: str,
        node_type: str,
        created_at: int,
        confidence: float,
        mutable: bool,
        payload: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        node = super()._upsert_node(
            graph,
            node_id=node_id,
            node_type=node_type,
            created_at=created_at,
            confidence=confidence,
            mutable=mutable,
            payload=payload,
        )
        if source is not None and node.get("source") != source:
            node["source"] = source
            node["integrity_hash"] = self._integrity_hash(node)
        return node

    def weave_after_action(self, player_id: str, action: str, base: WorldResult) -> WorldResult:
        """Do not schedule relational gifts from blocked or unrealized actions."""
        store = self._threads_store()
        state = self._player_state(store, player_id)
        state["turn"] += 1
        state["action_fingerprints"] = (
            state.get("action_fingerprints", []) + [self._fingerprint(action)]
        )[-24:]
        resident_update = self._advance_resident(store, state, player_id)
        self._ensure_symbol(store, state, player_id)

        blocked = base.status in (
            set(self.BLOCKED_STATUSES)
            | set(getattr(self, "UNREALIZED_CONTACT_STATUSES", set()))
        )
        if not blocked:
            self._schedule_turn_event(store, state, player_id, action, resident_update)
        event = None if blocked else self._due_event(store, state, player_id)
        if event is None:
            self._write_json(self.living_threads_path, store)
            return base

        child_role = bool(getattr(self, "_is_child", lambda _id: False)(player_id))
        narrative = self._render(store, state, event, player_id, child_role)
        surfaced = {
            "event_id": event["event_id"],
            "kind": event["kind"],
            "turn": state["turn"],
            "narrative": narrative,
            "child_safe": child_role,
            "created_from_visible_menu": False,
            "random_victim_created": False,
            "predictive_guilt": False,
            "resident_autonomy_claim": False,
        }
        state["surfaced"] = (state.setdefault("surfaced", []) + [surfaced])[-256:]
        self._write_json(self.living_threads_path, store)
        self.memory.append_event(
            player_id,
            "living_thread_surfaced",
            {
                "event_id": event["event_id"],
                "kind": event["kind"],
                "turn": state["turn"],
                "created_from_visible_menu": False,
                "random_victim_created": False,
                "child_safe": child_role,
            },
        )
        return self._copy(
            base,
            narrative=base.narrative + "\n\nНить мира возникла без выбора из меню:\n" + narrative,
            choices=[],
        )
