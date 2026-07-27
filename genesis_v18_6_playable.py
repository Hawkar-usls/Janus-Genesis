# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.6."""
from __future__ import annotations

from pathlib import Path

from genesis_v18_5_playable import PlayableGenesisV185
from genesis_v18_6 import PossibilityBloomMixin

PLAYABLE_VERSION = "18.6.0"


class PlayableGenesisV186(PossibilityBloomMixin, PlayableGenesisV185):
    """v18.6 runtime where semantic evidence blooms into real affordances."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)

    def process_action(self, player_id: str, action: str):
        good_before = self.memory.load_player(player_id).good_count
        base_result = super().process_action(player_id, action)
        return self.weave_possibility_after_action(
            player_id,
            action,
            base_result,
            good_before=good_before,
        )
