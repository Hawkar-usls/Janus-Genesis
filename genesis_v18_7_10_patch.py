# -*- coding: utf-8 -*-
"""Security, relationship and provenance integration patch for v18.7.10."""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_10 import SOURCE, sha256_canonical


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

    # ------------------------------------------------------------------
    # Immutable item origin, mutable ownership
    # ------------------------------------------------------------------

    @staticmethod
    def _item_origin_material(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "item_id": item["item_id"],
            "name": item["name"],
            "description": item["description"],
            "origin": item["origin"],
            "origin_event": item["origin_event"],
            "rarity": item["rarity"],
            "assessed_value": item["assessed_value"],
            "origin_owner_id": item["origin_owner_id"],
        }

    def cast_item(
        self,
        player_id: str,
        *,
        name: str,
        description: str,
        rarity: int = 1,
    ) -> dict[str, Any]:
        created = super().cast_item(
            player_id,
            name=name,
            description=description,
            rarity=rarity,
        )
        store = self._sandbox_store()
        item = store["items"][created["item_id"]]
        item["origin_owner_id"] = player_id
        item["current_owner_id"] = item["owner_id"]
        item["provenance_hash"] = sha256_canonical(self._item_origin_material(item))
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(item)

    def buy_market_listing(self, buyer_id: str, listing_id: str) -> dict[str, Any]:
        trade = super().buy_market_listing(buyer_id, listing_id)
        store = self._sandbox_store()
        item = store["items"][trade["item_id"]]
        item["current_owner_id"] = buyer_id
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(trade)

    def verify_v1810_state(self) -> tuple[bool, dict[str, Any], str | None]:
        assessor_valid, assessor_count, assessor_error = self.verify_bound_assessor_state()
        constitution = self.frozen_constitution_state()
        free_valid, players, others, free_error = self.verify_free_other_state()
        sandbox = self._sandbox_store()
        if not assessor_valid:
            return False, {}, assessor_error
        if not constitution["valid"]:
            return False, {}, "frozen constitution invalid"
        if not free_valid:
            return False, {}, free_error
        for item_id, item in sandbox["items"].items():
            expected = item.get("provenance_hash")
            if "origin_owner_id" in item:
                calculated = sha256_canonical(self._item_origin_material(item))
            else:
                legacy = copy.deepcopy(item)
                legacy.pop("provenance_hash", None)
                calculated = sha256_canonical(legacy)
            if expected != calculated:
                return False, {}, f"item provenance invalid: {item_id}"
            current_owner = item.get("current_owner_id", item.get("owner_id"))
            if current_owner != item.get("owner_id"):
                return False, {}, f"item ownership projection mismatch: {item_id}"
        return True, {
            "assessments": assessor_count,
            "players": players,
            "free_others": others,
            "sandbox_events": len(sandbox["events"]),
            "sandbox_items": len(sandbox["items"]),
        }, None
