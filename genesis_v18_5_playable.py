# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.5."""
from __future__ import annotations

from pathlib import Path

from genesis_v18_4_playable import PlayableGenesisV184
from genesis_v18_5 import LivingThreadsMixin

PLAYABLE_VERSION = "18.5.0"


class PlayableGenesisV185(LivingThreadsMixin, PlayableGenesisV184):
    """v18.5 runtime with persistent unscripted causal threads."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)

    def process_action(self, player_id: str, action: str):
        base_result = super().process_action(player_id, action)
        return self.weave_after_action(player_id, action, base_result)
