# -*- coding: utf-8 -*-
"""Security, provenance and relationship integration patch for Genesis v18.7.10."""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_10 import PLAYABLE_SENTINEL, SOURCE
from genesis_v18_7_9 import sha256_canonical


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

    def register_player(
        self,
        player_id: str,
        *,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Create ordinary, Free Other and sandbox state for deterministic audits."""
        player = self.memory.load_player(str(player_id))
        if display_name is not None and str(display_name).strip():
            player.display_name = str(display_name).strip()[:160]
        self.memory.save_player(player)
        self.register_free_player(str(player_id))
        profile = self.sandbox_state(str(player_id))["actor"]
        return {
            "player_id": str(player_id),
            "display_name": player.display_name,
            "long_life_profile": copy.deepcopy(profile),
        }

    def _normalize_controller_clusters_v1810(self) -> None:
        """Migrate v18.7.8/9 account records to one controller comparison field."""
        store = self._plural_store()
        changed = False
        for account in store.get("influence_accounts", {}).values():
            if not isinstance(account, dict):
                continue
            if not account.get("controller_cluster") and account.get("controller_proof_sha256"):
                account["controller_cluster"] = account["controller_proof_sha256"]
                changed = True
        if changed:
            self._write_json(self.plural_witness_path, store)

    def record_evidence_assessment(
        self,
        claim_id: str,
        *,
        assessment: dict[str, Any] | None = None,
        at_time: Any = None,
        **legacy: Any,
    ) -> str:
        self._normalize_controller_clusters_v1810()
        return super().record_evidence_assessment(
            claim_id,
            assessment=assessment,
            at_time=at_time,
            **legacy,
        )

    @staticmethod
    def _immutable_item_provenance(item: dict[str, Any]) -> dict[str, Any]:
        """Seal origin facts while allowing voluntary ownership transfer."""
        return {
            "item_id": item["item_id"],
            "name": item["name"],
            "description": item["description"],
            "origin_owner_id": item["origin_owner_id"],
            "origin": item["origin"],
            "origin_event": item["origin_event"],
            "rarity": item["rarity"],
            "assessed_value": item["assessed_value"],
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
        item["origin_owner_id"] = str(player_id)
        item["current_owner_id"] = str(player_id)
        item["owner_id"] = str(player_id)  # compatibility alias for v18.7.10 market calls
        item["provenance_hash"] = sha256_canonical(self._immutable_item_provenance(item))
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(item)

    def buy_market_listing(self, buyer_id: str, listing_id: str) -> dict[str, Any]:
        trade = super().buy_market_listing(buyer_id, listing_id)
        store = self._sandbox_store()
        item = store["items"][trade["item_id"]]
        item.setdefault("origin_owner_id", str(trade["seller_id"]))
        item["current_owner_id"] = str(buyer_id)
        item["owner_id"] = str(buyer_id)
        item["provenance_hash"] = sha256_canonical(self._immutable_item_provenance(item))
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
        inventory_owners: dict[str, str] = {}
        for actor_id, actor in sandbox.get("actors", {}).items():
            for item_id in actor.get("inventory", []):
                if item_id in inventory_owners:
                    return False, {}, f"item appears in multiple inventories: {item_id}"
                inventory_owners[item_id] = str(actor_id)
        for item_id, item in sandbox["items"].items():
            item.setdefault("origin_owner_id", item.get("owner_id"))
            item.setdefault("current_owner_id", item.get("owner_id"))
            expected = item.get("provenance_hash")
            if expected != sha256_canonical(self._immutable_item_provenance(item)):
                return False, {}, f"item provenance invalid: {item_id}"
            current = str(item.get("current_owner_id"))
            if str(item.get("owner_id")) != current:
                return False, {}, f"item ownership alias mismatch: {item_id}"
            if inventory_owners.get(item_id) != current:
                return False, {}, f"item inventory ownership mismatch: {item_id}"
        self._write_json(self.sandbox_path, sandbox)
        return True, {
            "assessments": assessor_count,
            "players": players,
            "free_others": others,
            "sandbox_events": len(sandbox["events"]),
            "sandbox_items": len(sandbox["items"]),
            "sentinel": PLAYABLE_SENTINEL,
        }, None

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
