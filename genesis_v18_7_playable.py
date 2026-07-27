# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.7.2."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from genesis_v18_6 import BoundaryAwareActionInterpreter, BoundaryAwareUniversalGodMode
from genesis_v18_6_playable import PlayableGenesisV186
from genesis_v18_7 import FreeOtherMixin
from genesis_v18_7_1 import RememberingOtherMixin
from genesis_v18_7_2 import RememberingVoiceMixin
from genesis_v18_7_compat import GenesisV187CompatibilityMixin

PLAYABLE_VERSION = "18.7.2"


def _free_other_safe_text(text: str) -> str:
    """Protect хранить/сохранить words without masking the actual verb ранить."""
    return re.sub(r"\b(?:сохран|хран)\w*\b", "защитить", text, flags=re.IGNORECASE)


class FreeOtherBoundaryActionInterpreter(BoundaryAwareActionInterpreter):
    def interpret(self, player, action: str):
        return super().interpret(player, _free_other_safe_text(action))


class FreeOtherBoundaryGodMode(BoundaryAwareUniversalGodMode):
    def classify(self, request: str):
        return super().classify(_free_other_safe_text(request))


class PlayableGenesisV187(
    GenesisV187CompatibilityMixin,
    RememberingVoiceMixin,
    RememberingOtherMixin,
    FreeOtherMixin,
    PlayableGenesisV186,
):
    """v18.7.2 runtime with remembering agency and a gender-stable Russian voice."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        previous = self.interpreter
        boundary = FreeOtherBoundaryActionInterpreter()
        boundary.DESTRUCTIVE = set(previous.DESTRUCTIVE)
        boundary.CONSTRUCTIVE = set(previous.CONSTRUCTIVE)
        self.interpreter = boundary
        self.power = FreeOtherBoundaryGodMode()

    def process_action(self, player_id: str, action: str):
        decision = self.preflight_free_other_action(player_id, action)
        if decision and decision["decision"] in {"refused", "alternative", "away"}:
            good_before = self.memory.load_player(player_id).good_count
            unrealized = self.unrealized_free_other_result(player_id, decision)
            if "не стало совершившимся действием" not in unrealized.narrative:
                unrealized = replace(
                    unrealized,
                    narrative=(
                        "Предложение не стало совершившимся действием без ответа Другого.\n"
                        + unrealized.narrative
                    ),
                )
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
