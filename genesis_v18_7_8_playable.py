# -*- coding: utf-8 -*-
"""Historical playable runtime for Genesis v18.7.8 — The Unbought Voice."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from genesis_v18_6 import BoundaryAwareActionInterpreter, BoundaryAwareUniversalGodMode
from genesis_v18_6_playable import PlayableGenesisV186
from genesis_v18_7 import FreeOtherMixin
from genesis_v18_7_1 import RememberingOtherMixin
from genesis_v18_7_2 import RememberingVoiceMixin
from genesis_v18_7_3 import (
    NON_EXECUTING_MODES,
    HonestIntentionActionInterpreter,
    HonestIntentionGodMode,
    HonestIntentionMixin,
)
from genesis_v18_7_4 import PluralWitnessIntentionAnalyzer
from genesis_v18_7_5 import GroundedWitnessMixin
from genesis_v18_7_5_repair import DerivedRepairMixin
from genesis_v18_7_7 import BenevolentSovereignMixin
from genesis_v18_7_7_voice_integrity import SovereignVoiceIntegrityMixin
from genesis_v18_7_8 import UnboughtVoiceMixin
from genesis_v18_7_compat import GenesisV187CompatibilityMixin

PLAYABLE_VERSION = "18.7.8"


def _free_other_safe_text(text: str) -> str:
    return re.sub(r"\b(?:сохран|хран)\w*\b", "защитить", text, flags=re.IGNORECASE)


class FreeOtherBoundaryActionInterpreterV178(BoundaryAwareActionInterpreter):
    def interpret(self, player, action: str):
        return super().interpret(player, _free_other_safe_text(action))


class FreeOtherBoundaryGodModeV178(BoundaryAwareUniversalGodMode):
    def classify(self, request: str):
        return super().classify(_free_other_safe_text(request))


class PlayableGenesisV1878(
    GenesisV187CompatibilityMixin,
    UnboughtVoiceMixin,
    SovereignVoiceIntegrityMixin,
    BenevolentSovereignMixin,
    DerivedRepairMixin,
    GroundedWitnessMixin,
    HonestIntentionMixin,
    RememberingVoiceMixin,
    RememberingOtherMixin,
    FreeOtherMixin,
    PlayableGenesisV186,
):
    """Frozen v18.7.8 behavior for historical regression tests and old saves."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.intention_analyzer = PluralWitnessIntentionAnalyzer(
            self.intention_analyzer.harmful_fragments
        )
        previous = self.interpreter
        boundary = FreeOtherBoundaryActionInterpreterV178()
        boundary.DESTRUCTIVE = set(previous.DESTRUCTIVE)
        boundary.CONSTRUCTIVE = set(previous.CONSTRUCTIVE)
        interpreter = HonestIntentionActionInterpreter(boundary, self.intention_analyzer)
        interpreter.DESTRUCTIVE = boundary.DESTRUCTIVE
        interpreter.CONSTRUCTIVE = boundary.CONSTRUCTIVE
        interpreter.beneficiary = boundary.beneficiary
        interpreter.normalize = boundary.normalize
        self.interpreter = interpreter
        self.power = HonestIntentionGodMode(
            FreeOtherBoundaryGodModeV178(), self.intention_analyzer
        )
        self.BLOCKED_STATUSES = set(self.BLOCKED_STATUSES) | {"INTENTION_WITNESSED"}
        self.BLOCKED_RELATIONAL_STATUSES = set(self.BLOCKED_RELATIONAL_STATUSES) | {
            "INTENTION_WITNESSED"
        }

    def process_action(self, player_id: str, action: str):
        frame = self.analyze_intention(action)
        if frame.mode in NON_EXECUTING_MODES:
            good_before = self.memory.load_player(player_id).good_count
            if self.exit_pending(player_id):
                self._exit_guard_path(player_id).unlink(missing_ok=True)
                self.memory.append_event(player_id, "exit_cancelled", {"continued_with": action})
            self.cancel_pending_harm(player_id, action)
            witnessed = self.witness_nonexecuting_intention(player_id, action, frame)
            threaded = self.weave_after_action(player_id, action, witnessed)
            bloomed = self.weave_possibility_after_action(
                player_id, action, threaded, good_before=good_before
            )
            return self.weave_free_other_after_action(
                player_id,
                action,
                bloomed,
                contact_decision=None,
                action_realized=False,
            )
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
                player_id, action, threaded, good_before=good_before
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
