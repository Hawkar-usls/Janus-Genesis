# -*- coding: utf-8 -*-
"""Playable natural-language layer for Genesis v18.4."""
from __future__ import annotations

from pathlib import Path

from genesis_v18_3_playable import PlayableGenesisV183
from genesis_v18_4 import ProtectedChildhoodMixin
from genesis_v18_models import PowerNature, UniversalGodMode

PLAYABLE_VERSION = "18.4.0"


class PlayableGenesisV184(ProtectedChildhoodMixin, PlayableGenesisV183):
    """v18.4 runtime with protected childhood and present-tense parenthood gates."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.interpreter.DESTRUCTIVE = set(self.interpreter.DESTRUCTIVE) | {
            "ударить ребенка", "ударить ребёнка", "наказать ребенка", "наказать ребёнка",
            "накричать на ребенка", "накричать на ребёнка", "бросить ребенка", "бросить ребёнка",
            "hit the child", "punish the child", "abandon the child",
        }

    def choose_form(self, player_id: str, *, apparent_age: int | None = None, body_form: str | None = None):
        if apparent_age is not None and apparent_age < 18:
            return self.enter_protected_childhood(player_id, apparent_age=apparent_age)
        if apparent_age is not None and apparent_age >= 18 and self._is_child(player_id):
            left = self.leave_protected_childhood(player_id)
            adult = super().choose_form(player_id, apparent_age=apparent_age, body_form=body_form)
            return self._copy(
                adult,
                status="ADULT_FORM_AFTER_PROTECTED_CHILDHOOD",
                narrative=left.narrative + " " + adult.narrative,
            )
        return super().choose_form(player_id, apparent_age=apparent_age, body_form=body_form)

    def process_action(self, player_id: str, action: str):
        text = UniversalGodMode.normalize(action)
        player = self.memory.load_player(player_id)

        if any(fragment in text for fragment in self.SHOW_CHILDHOOD):
            state = self.protected_childhood_state(player_id)
            if state.get("child") and state["child"].get("active"):
                household = state.get("households", [{}])[0]
                return self._copy(
                    super().process_action(player_id, "Осмотреться"),
                    status="PROTECTED_HOUSEHOLD_SHOWN",
                    narrative=(
                        "Дом держится не на праве взрослого владеть ребёнком, а на действующем обете защиты. "
                        f"Хранители: {', '.join(household.get('guardian_ids', []))}. Вред здесь не может проявиться."
                    ),
                    choices=["Поиграть", "Поговорить с хранителем", "Отдохнуть"],
                )
            return self._copy(
                super().process_action(player_id, "Осмотреться"),
                status="NO_ACTIVE_CHILD_ROLE",
                narrative="Защищённое детство сейчас не выбрано.",
                choices=["Стать ребёнком", "Продолжить взрослую жизнь"],
            )

        if any(fragment in text for fragment in self.LEAVE_CHILD_ROLE):
            return self.leave_protected_childhood(player_id)

        if any(fragment in text for fragment in self.CHILD_ROLE):
            return self.enter_protected_childhood(player_id)

        if any(fragment in text for fragment in self.PARENTHOOD_CONFIRM):
            return self.request_parenthood(player_id, action, explicit_confirmation=True)

        if any(fragment in text for fragment in self.PARENTHOOD):
            return self.request_parenthood(player_id, action)

        interpreted = self.interpreter.interpret(player, action)
        harmful = interpreted.kind == "destructive" or self.power.classify(action) == PowerNature.HARMFUL

        if self._is_child(player_id) and harmful:
            self.cancel_pending_harm(player_id, action)
            return self.transform_child_shadow(player_id, action)

        protected_child = self._protected_child_subject(action)
        if harmful and (self._active_covenant(player_id) is not None or protected_child is not None):
            self.cancel_pending_harm(player_id, action)
            return self.transform_guardian_shadow(player_id, action, child_id=protected_child)

        return super().process_action(player_id, action)
