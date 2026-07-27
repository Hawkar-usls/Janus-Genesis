# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.7."""
from __future__ import annotations

from pathlib import Path

from genesis_v18_6_playable import PlayableGenesisV186
from genesis_v18_7 import FreeOtherMixin

PLAYABLE_VERSION = "18.7.0"


class PlayableGenesisV187(FreeOtherMixin, PlayableGenesisV186):
    """v18.7 runtime with independent player paths and Free Others."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)

    def process_action(self, player_id: str, action: str):
        decision = self.preflight_free_other_action(player_id, action)
        if decision and decision["decision"] in {"refused", "alternative", "away"}:
            good_before = self.memory.load_player(player_id).good_count
            unrealized = self.unrealized_free_other_result(player_id, decision)
            threaded = self.weave_after_action(player_id, action, unrealized)
            bloomed = self.weave_possibility_after_action(
                player_id,
                action,
                threaded,
                good_before=good_before,
            )
            return self.weave_free_other_after_action(
                player_id,
                action,
                bloomed,
                contact_decision=decision,
                action_realized=False,
            )

        base = super().process_action(player_id, action)
        if base.status in self.BLOCKED_RELATIONAL_STATUSES:
            decision = None
        return self.weave_free_other_after_action(
            player_id,
            action,
            base,
            contact_decision=decision,
            action_realized=True,
        )
