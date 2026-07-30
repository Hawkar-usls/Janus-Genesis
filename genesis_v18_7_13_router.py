# -*- coding: utf-8 -*-
"""Natural-language routing for Genesis v18.7.13 social extensions."""
from __future__ import annotations

import re

from genesis_v18_models import WorldResult


class ReturningLightNaturalLanguageMixin:
    """Route narrow, explicit phrases without inventing hidden consent."""

    @staticmethod
    def _v1813_first_handle(text: str) -> str | None:
        match = re.search(r"(?:^|\s)@([\w-]{1,80})", str(text).lower())
        return match.group(1) if match else None

    @staticmethod
    def _v1813_named_child(text: str) -> str:
        match = re.search(
            r"(?:реб[её]н(?:ка|ок)|child)\s+([A-Za-zА-Яа-яЁёІіЇїЄє0-9_-]{1,80})",
            str(text),
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else "Люмен"

    @staticmethod
    def _v1813_token(text: str, key: str) -> str | None:
        match = re.search(
            rf"(?:^|\s){re.escape(key)}:([\w-]{{1,120}})",
            str(text),
            flags=re.IGNORECASE,
        )
        return match.group(1) if match else None

    def _v1813_dict_result(
        self,
        player_id: str,
        *,
        status: str,
        narrative: str,
        payload: dict,
    ) -> WorldResult:
        trace = str(
            payload.get("aid_id")
            or payload.get("schedule_id")
            or payload.get("step_id")
            or payload.get("need_id")
            or payload.get("pair_id")
            or payload.get("habitat_id")
            or ""
        ) or None
        return self._family_result(
            str(player_id),
            status=status,
            narrative=narrative,
            choices=["Проверить запись", "Продолжить без долга", "Сохранить право отказа"],
            trace_id=trace,
            manifested=True,
        )

    def try_v1813_action(
        self,
        player_id: str,
        action: str,
    ) -> WorldResult | None:
        text = str(action)
        normalized = self._normalized_joy_text(text)
        handle = self._v1813_first_handle(text)

        if handle and "спутник" in normalized and (
            "предлож" in normalized or "стать" in normalized
        ):
            return self.propose_life_companionship(
                str(player_id),
                handle,
                shared_values=text,
                both_adults_confirmed=(
                    "оба взросл" in normalized
                    or "все взросл" in normalized
                    or "adult" in normalized
                ),
            )

        if "родител" in normalized and (
            "ребен" in normalized or "ребён" in normalized
        ):
            family_path = (
                "ADOPTION"
                if "усын" in normalized
                else "MIRACLE_OF_CARE"
                if "чуд" in normalized
                else "BIRTH"
            )
            family = self.family_state(str(player_id))
            consent = (
                "я соглас" in normalized
                or "доброволь" in normalized
                or "consent" in normalized
            )
            if isinstance(family.get("companion"), dict):
                return self.welcome_child_with_companion(
                    str(player_id),
                    child_name=self._v1813_named_child(text),
                    family_path=family_path,
                    home_plan=text,
                    player_parenthood_consent=consent,
                )
            return self.welcome_child_solo_parent(
                str(player_id),
                child_name=self._v1813_named_child(text),
                family_path=family_path,
                home_plan=text,
                player_parenthood_consent=consent,
            )

        if "дальн" in normalized and "отнош" in normalized:
            return self.transition_companionship_mode(
                str(player_id),
                mode="LONG_DISTANCE",
                reason=text,
            )
        if (
            "пауза" in normalized or "приостанов" in normalized
        ) and "отнош" in normalized:
            return self.transition_companionship_mode(
                str(player_id),
                mode="PAUSED_BY_PLAYER",
                reason=text,
            )
        if (
            "возобнов" in normalized or "вернуться" in normalized
        ) and "спут" in normalized:
            return self.transition_companionship_mode(
                str(player_id),
                mode="ACTIVE",
                reason=text,
            )

        child_id = self._v1813_token(text, "child")
        if child_id and "расписан" in normalized and "забот" in normalized:
            record = self.propose_coparent_schedule(
                str(player_id),
                child_id,
                plan=text,
            )
            return self._v1813_dict_result(
                str(player_id),
                status=f"COPARENT_SCHEDULE_{str(record['decision']).upper()}",
                narrative=(
                    "Расписание прошло через отдельный канал заботы о ребёнке и не "
                    "переоткрыло отношения взрослых."
                ),
                payload=record,
            )

        if handle and "благослов" in normalized and (
            "проводник" in normalized
            or "оракул" in normalized
            or "возвращающ" in normalized
        ):
            tier = (
                "GREAT"
                if any(
                    fragment in normalized
                    for fragment in ("велики", "богат", "правител", "магнат")
                )
                else "ABUNDANT"
                if any(
                    fragment in normalized
                    for fragment in ("обиль", "много ресурс", "влиятель")
                )
                else "COMMON"
            )
            return self.bless_free_other_as_steward(
                str(player_id),
                handle,
                capacity_tier=tier,
                capacity_evidence=text,
            )

        recipient = self._v1813_token(text, "recipient")
        need_id = self._v1813_token(text, "need")
        if handle and recipient and need_id and "помоч" in normalized:
            aid = self.offer_oracle_guided_aid(
                str(player_id),
                handle,
                recipient,
                need_id=need_id,
                request_moral_support=True,
            )
            return self._v1813_dict_result(
                str(player_id),
                status=str(aid["decision"]),
                narrative=(
                    "Оракул предложил проверяемую помощь: без долга, покупки согласия "
                    "или объявления человека навсегда добрым."
                ),
                payload=aid,
            )

        if "лев" in normalized and (
            "овц" in normalized or "ягнен" in normalized
        ) and (
            "сад" in normalized or "царств" in normalized or "мирн" in normalized
        ):
            habitat = self.create_peaceable_habitat(
                str(player_id),
                name="Мирный Сад",
                safety_plan=(
                    "никакой охоты, собственности, оружия, зрелища или принуждения к близости"
                ),
            )
            pair = self.welcome_peaceable_pair(
                str(player_id),
                habitat["habitat_id"],
                first_kind="LION",
                second_kind="LAMB",
            )
            return self._family_result(
                str(player_id),
                status="PEACEABLE_KINGDOM_PAIR_WELCOMED",
                narrative=(
                    "Лев и ягнёнок получили общий безопасный сад. Их мир не является "
                    "дрессировкой: они могут отдыхать рядом или сохранять дистанцию."
                ),
                choices=["Оставить воду", "Наблюдать без вторжения", "Дать пространство"],
                trace_id=pair["pair_id"],
                manifested=True,
            )
        return None
