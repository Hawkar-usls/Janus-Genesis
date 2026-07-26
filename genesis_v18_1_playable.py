# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.1."""

from __future__ import annotations

from pathlib import Path

from genesis_v18_1 import DEFAULT_SECRET, RememberedSecretRuntimeMixin
from genesis_v18_playable import PlayableGenesisV18
from genesis_v18_models import UniversalGodMode

PLAYABLE_VERSION = "18.1.0"


class PlayableGenesisV181(RememberedSecretRuntimeMixin, PlayableGenesisV18):
    """v18.1 playable runtime with direct Secret memory and inherited good."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.interpreter.CONSTRUCTIVE = set(self.interpreter.CONSTRUCTIVE) | {
            "рассказать",
            "поделиться секретом",
            "открыть секрет",
            "секрет",
        }

    def process_action(self, player_id: str, action: str):
        text = UniversalGodMode.normalize(action)
        listener_id = self.interpreter.beneficiary(text)
        speaks_secret = listener_id is not None and any(
            fragment in text for fragment in self.SECRET_WORDS
        )
        result = super().process_action(player_id, action)
        if speaks_secret and result.status == "GOOD_REALIZED":
            return self.plant_secret(
                player_id,
                listener_id,
                message=action.strip() or DEFAULT_SECRET,
                base_result=result,
            )
        return result
