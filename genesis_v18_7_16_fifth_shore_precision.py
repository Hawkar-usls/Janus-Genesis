# -*- coding: utf-8 -*-
"""Semantic precision patch for distinct Fifth Shore rest-and-humor outcomes."""
from __future__ import annotations

import copy
from typing import Any


class FifthShoreRestHumorPrecisionMixin:
    """Give restorative play its own status instead of calling every episode repair."""

    def play_fifth_shore_episode(
        self,
        player_id: str,
        community_id: str,
        *,
        participates: bool,
        rehearsal_kind: str,
        commits_to_external_action: bool,
        chooses_rest_or_humor: bool = False,
    ) -> dict[str, Any]:
        result = super().play_fifth_shore_episode(
            player_id,
            community_id,
            participates=participates,
            rehearsal_kind=rehearsal_kind,
            commits_to_external_action=commits_to_external_action,
            chooses_rest_or_humor=chooses_rest_or_humor,
        )
        if not (
            participates
            and chooses_rest_or_humor
            and result.get("status") == "FIFTH_SHORE_REPAIR_REHEARSED"
        ):
            return result

        refined = copy.deepcopy(result)
        refined["status"] = "FIFTH_SHORE_REST_HUMOR_RESTORED"
        refined["repair_claimed"] = False
        refined["rest_humor_is_valid_good"] = True

        store = self._inner_genesis_store()
        episode_id = refined.get("episode_id")
        for episode in reversed(store.get("episodes", [])):
            if episode.get("episode_id") == episode_id:
                episode.update(copy.deepcopy(refined))
                break
        for event in reversed(store.get("events", [])):
            if (
                event.get("kind") == "FIFTH_SHORE_EPISODE_DECIDED"
                and event.get("episode_id") == episode_id
            ):
                event["status"] = refined["status"]
                break
        store.setdefault("events", []).append(
            {
                "kind": "FIFTH_SHORE_REST_HUMOR_OUTCOME_REFINED",
                "episode_id": episode_id,
                "status": refined["status"],
                "repair_claimed": False,
            }
        )
        self._write_inner_genesis_store(store)
        self.memory.append_event(
            str(player_id),
            "fifth_shore_rest_humor_restored",
            refined,
        )
        return copy.deepcopy(refined)
