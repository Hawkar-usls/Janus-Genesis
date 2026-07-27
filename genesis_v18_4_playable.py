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

    def _install_fallback_guardians(self, guardian_id: str) -> None:
        store = self._childhood_store()
        covenant = store.get("guardian_covenants", {}).get(guardian_id)
        if not covenant:
            return
        household = store.get("households", {}).get(covenant.get("household_id"))
        if not household:
            return
        household["guardian_ids"] = [item for item in household.get("guardian_ids", []) if item != guardian_id]
        for fallback in ("hearth-guardian", "garden-guardian"):
            if fallback not in household["guardian_ids"]:
                household["guardian_ids"].append(fallback)
        household["protective_reassignment_active"] = True
        household["suspended_guardian_provenance"] = list(
            dict.fromkeys(household.get("suspended_guardian_provenance", []) + [guardian_id])
        )
        self._save_childhood(store)

    def enter_protected_childhood(self, player_id: str, apparent_age: int | None = None):
        # Nobody may become their own guardian. An existing covenant is suspended
        # before the same person enters the protected child role.
        store = self._childhood_store()
        own = store.get("guardian_covenants", {}).get(player_id)
        if own and own.get("status") == "active":
            own["status"] = "suspended_during_child_role"
            own["open_for_child"] = False
            self._save_childhood(store)
            self._install_fallback_guardians(player_id)

        result = super().enter_protected_childhood(player_id, apparent_age=apparent_age)
        # The core method writes child state and household state through separate
        # atomic snapshots. Reassert the household after the child snapshot so
        # neither side can overwrite the other during migration.
        household = self._safe_household(player_id)
        store = self._childhood_store()
        store.setdefault("children", {}).setdefault(player_id, {})["household_id"] = household["household_id"]
        self._save_childhood(store)
        return result

    def transform_guardian_shadow(self, player_id: str, action: str, child_id: str | None = None):
        result = super().transform_guardian_shadow(player_id, action, child_id=child_id)
        self._install_fallback_guardians(player_id)
        return result

    def commit_destructive_action(self, player_id: str, action: str):
        result = super().commit_destructive_action(player_id, action)
        self._install_fallback_guardians(player_id)
        return result

    def protected_childhood_state(self, player_id: str | None = None):
        state = super().protected_childhood_state(player_id)
        if player_id is None:
            return state
        covenant = state.get("guardian_covenant")
        if covenant:
            household_id = covenant.get("household_id")
            store = self._childhood_store()
            household = store.get("households", {}).get(household_id)
            if household and all(item.get("household_id") != household_id for item in state.get("households", [])):
                state.setdefault("households", []).append(household)
        return state

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
                households = state.get("households", [])
                household = households[0] if households else {"guardian_ids": ["hearth-guardian", "garden-guardian"]}
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
