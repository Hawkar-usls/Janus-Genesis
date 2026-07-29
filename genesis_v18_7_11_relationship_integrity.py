# -*- coding: utf-8 -*-
"""Epistemic separation of actor life and relationship life for Genesis v18.7.11."""
from __future__ import annotations

import copy
from typing import Any


class RelationshipEpistemicIntegrityMixin:
    """Expose one authoritative relationship view without owning actor life."""

    def authoritative_relationship_view(
        self,
        player_id: str,
        handle: str,
    ) -> dict[str, Any]:
        store = self._free_store()
        profile = self._free_profile(store, str(player_id))
        actor = profile.get("others", {}).get(str(handle))
        if not isinstance(actor, dict):
            raise KeyError(handle)
        relationship = actor.get("relationship_state_v1810")
        actor_life = actor.get("actor_life_v1810")
        if not isinstance(relationship, dict):
            raise RuntimeError("RELATIONSHIP_STATE_V1810_REQUIRED")
        if not isinstance(actor_life, dict):
            raise RuntimeError("ACTOR_LIFE_V1810_REQUIRED")
        view = {
            "player_id": str(player_id),
            "handle": str(handle),
            "authoritative_relationship_source": (
                "relationship_bond+relationship_score+relationship_state_v1810"
            ),
            "legacy_trust_is_compatibility_projection": True,
            "legacy_trust": float(actor.get("trust", 0.0)),
            "relationship_bond": int(actor.get("relationship_bond", 0)),
            "relationship_score": int(actor.get("relationship_score", 0)),
            "relationship_status": str(relationship.get("status", "UNKNOWN")),
            "actor_life_status": str(actor_life.get("status", "UNKNOWN")),
            "offscreen_progress": int(actor_life.get("offscreen_progress", 0)),
            "actor_life_owned_by_relationship": False,
        }
        self.assert_relationship_actor_life_separation(view)
        return copy.deepcopy(view)

    @staticmethod
    def assert_relationship_actor_life_separation(view: dict[str, Any]) -> None:
        relationship_status = str(view.get("relationship_status", "UNKNOWN"))
        actor_life_status = str(view.get("actor_life_status", "UNKNOWN"))
        progress = int(view.get("offscreen_progress", 0))
        if progress < 0:
            raise RuntimeError("OFFSCREEN_PROGRESS_CANNOT_BE_NEGATIVE")
        if relationship_status in {
            "TERMINATED_BY_OTHER",
            "TERMINATED_BY_PLAYER",
            "TERMINATED",
        } and actor_life_status in {
            "TERMINATED_BY_RELATIONSHIP",
            "DELETED_WITH_RELATIONSHIP",
            "ERASED",
        }:
            raise RuntimeError("RELATIONSHIP_TERMINATION_CANNOT_TERMINATE_ACTOR_LIFE")
        if bool(view.get("actor_life_owned_by_relationship")):
            raise RuntimeError("ACTOR_LIFE_MUST_NOT_BE_OWNED_BY_RELATIONSHIP")

    def audit_relationship_boundaries(self, player_id: str) -> dict[str, Any]:
        state = self.free_other_state(str(player_id))
        actors = state.get("profile", {}).get("others", {})
        if not isinstance(actors, dict):
            raise RuntimeError("FREE_OTHER_ACTORS_MUST_BE_AN_OBJECT")
        views = [
            self.authoritative_relationship_view(str(player_id), handle)
            for handle in sorted(actors)
        ]
        return {
            "schema": "janus.genesis.relationship_boundary_audit.v1",
            "player_id": str(player_id),
            "actor_count": len(views),
            "legacy_trust_authoritative": False,
            "actor_life_separate_from_relationship_life": True,
            "views": views,
        }
