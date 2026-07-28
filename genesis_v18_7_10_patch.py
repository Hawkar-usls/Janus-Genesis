# -*- coding: utf-8 -*-
"""Security and relationship integration patch for Genesis v18.7.10."""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_10 import SOURCE


class BoundAssessorI0IntegrationPatchMixin:
    """Close inherited bootstrap paths and preserve terminal social boundaries."""

    def register_trusted_provider_key(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise PermissionError(
            "ROOT_GOVERNANCE_MANIFEST_REQUIRED: ordinary runtime cannot trust provider roots"
        )

    def register_sovereign_key(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise PermissionError(
            "ROOT_GOVERNANCE_MANIFEST_REQUIRED: ordinary runtime cannot trust sovereign roots"
        )

    def _apply_root_operation(self, store: dict[str, Any], operation: dict[str, Any]) -> None:
        if not isinstance(operation, dict):
            raise ValueError("root operation must be an object")
        kind = str(operation.get("operation"))
        if kind == "TRUST_PROVIDER_KEY":
            provider_id = str(operation["provider_id"])
            key_id = str(operation["key_id"])
            record = self._key_record(
                owner_id=provider_id,
                key_id=key_id,
                public_key_b64=str(operation["public_key_b64"]),
                valid_from=operation["valid_from"],
                valid_until=operation["valid_until"],
            )
            store["trusted_provider_keys"][f"{provider_id}:{key_id}"] = record
            return
        if kind == "TRUST_SOVEREIGN_KEY":
            key_id = str(operation["key_id"])
            record = self._key_record(
                owner_id="JANUS.SOVEREIGN",
                key_id=key_id,
                public_key_b64=str(operation["public_key_b64"]),
                valid_from=operation["valid_from"],
                valid_until=operation["valid_until"],
            )
            store["trusted_sovereign_keys"][key_id] = record
            return
        return super()._apply_root_operation(store, operation)

    def _apply_contact_decision(
        self,
        store: dict[str, Any],
        player_id: str,
        profile: dict[str, Any],
        decision: dict[str, Any],
        *,
        action_realized: bool,
    ) -> dict[str, Any]:
        if decision.get("decision") != "terminated":
            return super()._apply_contact_decision(
                store,
                player_id,
                profile,
                decision,
                action_realized=action_realized,
            )
        actor = profile["others"][decision["handle"]]
        relationship = actor.get("relationship_state_v1810", {})
        text = (
            f"{actor['name']} не был возвращён в завершённую связь. "
            "Окончательная граница сохранилась; собственный путь Другого продолжается вне отношений с игроком."
        )
        actor.setdefault("history", []).append(
            {
                "world_turn": int(store.get("world_turn", 0)),
                "kind": "terminated_relationship_boundary_preserved",
                "text": text,
                "source_action": decision.get("action"),
                "action_realized": False,
                "termination_event_id": relationship.get("termination_event_id"),
            }
        )
        self._record_other_graph_event(
            player_id,
            actor,
            kind="terminated_relationship_boundary_preserved",
            text=text,
            world_turn=int(store.get("world_turn", 0)),
            source_action=decision.get("action"),
        )
        return {
            "kind": "relationship_terminated_boundary",
            "handle": actor["handle"],
            "text": text,
            "priority": -1,
            "relationship_status": "TERMINATED_BY_OTHER",
            "relationship_mutated": False,
            "source": SOURCE,
        }
