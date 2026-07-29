# -*- coding: utf-8 -*-
"""Authoritative relationship interventions for isolated Genesis mirrors."""
from __future__ import annotations

import copy
import math
from typing import Any


class CounterfactualRelationshipProbeMixin:
    """Intervene on relationship state without altering a Free Other's own life."""

    def set_counterfactual_actor_trust_for_probe(
        self,
        player_id: str,
        handle: str,
        *,
        trust_percent: float,
        reason_code: str,
    ) -> dict[str, Any]:
        manifest = self._counterfactual_manifest()
        value = float(trust_percent)
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError("TRUST_PERCENT_OUT_OF_RANGE")

        store = self._free_store()
        profile = self._free_profile(store, str(player_id))
        actor = profile.get("others", {}).get(str(handle))
        if not isinstance(actor, dict):
            raise KeyError(handle)

        before = {
            "legacy_trust": float(actor.get("trust", 0.0)),
            "relationship_bond": int(actor.get("relationship_bond", 0)),
            "relationship_score": int(actor.get("relationship_score", 0)),
        }
        after_trust = value / 100.0
        after_bond = max(-100, min(100, int(round(after_trust * 35.0))))

        # BenevolentSovereignMixin treats relationship_bond/relationship_score as
        # authoritative. legacy trust is kept in sync only as a compatibility view.
        actor["trust"] = after_trust
        actor["relationship_bond"] = after_bond
        self._refresh_actor_relationship(str(player_id), actor)
        after = {
            "legacy_trust": float(actor["trust"]),
            "relationship_bond": int(actor["relationship_bond"]),
            "relationship_score": int(actor["relationship_score"]),
        }

        intervention = {
            "mirror_id": manifest["mirror_id"],
            "variable": "free_other.relationship_trust_prior",
            "handle": str(handle),
            "before": before,
            "after": after,
            "trust_percent": value,
            "reason_code": str(reason_code)[:120],
            "controlled_intervention": True,
            "canonical_mutation": False,
            "actor_life_mutation": False,
            "relationship_life_only": True,
        }
        actor.setdefault("history", []).append(
            {
                "world_turn": int(store.get("world_turn", 0)),
                "event": "counterfactual_relationship_trust_intervention",
                "before": before,
                "after": after,
                "reason_code": intervention["reason_code"],
                "actor_life_mutation": False,
            }
        )
        self._write_json(self.free_other_path, store)
        self.memory.append_event(
            str(player_id),
            "counterfactual_probe_variable_set",
            intervention,
        )
        return copy.deepcopy(intervention)
