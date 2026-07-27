# -*- coding: utf-8 -*-
"""Playable Genesis v18.7.1 — The Remembering Other."""
from __future__ import annotations

from pathlib import Path

from genesis_v18_7_1 import RememberingOtherMixin
from genesis_v18_7_playable import PlayableGenesisV187

PLAYABLE_VERSION = "18.7.1"


class PlayableGenesisV1871(RememberingOtherMixin, PlayableGenesisV187):
    """v18.7 with contextual dialogue memory and anti-repetition cooldowns."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
