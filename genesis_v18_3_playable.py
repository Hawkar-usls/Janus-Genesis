# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.3."""
from __future__ import annotations

from pathlib import Path

from genesis_v18_2_playable import PlayableGenesisV182
from genesis_v18_3 import AbsurdityLensMixin
from genesis_v18_models import UniversalGodMode

PLAYABLE_VERSION = "18.3.0"


class PlayableGenesisV183(AbsurdityLensMixin, PlayableGenesisV182):
    """v18.3 runtime with the non-victimising Absurdity Lens."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)

    def process_action(self, player_id: str, action: str):
        text = UniversalGodMode.normalize(action)
        if any(fragment in text for fragment in self.SHOW_LENS):
            return self.witness_deglamorized_shadow(player_id)
        return super().process_action(player_id, action)
