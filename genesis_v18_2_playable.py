# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.2."""
from __future__ import annotations

from pathlib import Path

from genesis_v18_1_playable import PlayableGenesisV181
from genesis_v18_2 import NarratorOfContrastMixin
from genesis_v18_models import UniversalGodMode

PLAYABLE_VERSION = "18.2.0"


class PlayableGenesisV182(NarratorOfContrastMixin, PlayableGenesisV181):
    """v18.2 runtime with MoralEcho, CareBond and safe narrative arcs."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.interpreter.DESTRUCTIVE = set(self.interpreter.DESTRUCTIVE) | {
            "обидеть", "мучить", "издеваться", "бросить без помощи", "терзать",
            "abuse", "torment", "abandon",
        }
        self.interpreter.CONSTRUCTIVE = set(self.interpreter.CONSTRUCTIVE) | {
            "заботиться", "кормить", "ухаживать", "слушать", "бережно", "погладить",
            "поддерживать", "выращивать", "просить прощения", "извиниться", "исправить",
            "восстановить", "возместить", "care", "feed", "listen", "support",
        }

    def process_action(self, player_id: str, action: str):
        text = UniversalGodMode.normalize(action)
        if any(fragment in text for fragment in self.NARRATOR):
            return self.offer_safe_arc(player_id)
        if any(fragment in text for fragment in self.SHOW):
            return self.show_consequences(player_id)
        if any(fragment in text for fragment in self.REFLECT):
            return self.acknowledge_echo(player_id, action)
        return super().process_action(player_id, action)
