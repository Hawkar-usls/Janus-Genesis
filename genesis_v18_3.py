# -*- coding: utf-8 -*-
"""Genesis v18.3 — The Absurdity Lens.

The lens strips glamour from harmful fantasies without mocking victims or
trivialising real harm. Unmanifested coercion may be shown as a safe absurd
stage with no victim. Confirmed harm remains real, creates MoralEcho, and is
represented without the aggressor's preferred mythology of grandeur.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from genesis_v18_2 import NarratorOfContrastMixin
from genesis_v18_models import PlayerV18, PowerNature, UniversalGodMode, WorldResult

__version__ = "18.3.0"


class AbsurdityLensMixin(NarratorOfContrastMixin):
    """Deglamorise evil while preserving privacy, truth, and victim dignity."""

    SHOW_LENS = {
        "увидеть зло без величия",
        "посмотреть через призму абсурда",
        "показать тень без величия",
        "как выглядит зло на самом деле",
        "призма абсурда",
        "show evil without glamour",
    }
    MYTHS: dict[str, set[str]] = {
        "domination": {
            "подчин", "служить мне", "власт", "править", "трон", "повелител", "бояться меня",
            "страх передо мной", "лишить воли", "заставить", "контрол", "rule", "obey", "enslave",
        },
        "destruction": {
            "уничтож", "сжечь", "сломать", "взорвать", "разруш", "стереть", "destroy", "burn", "break",
        },
        "humiliation": {
            "унизи", "оскорб", "опозор", "жалк", "смеялись над", "humiliate", "shame",
        },
        "deception": {
            "клевет", "лож", "обман", "заговор", "подстав", "slander", "lie", "deceive",
        },
        "forced_attachment": {
            "полюбила меня", "полюбил меня", "любили только меня", "не могла уйти", "не мог уйти",
            "forced love", "love only me",
        },
    }
    ABSURD_SCENES = {
        "domination": (
            "Возник высокий трон, к которому не было лестницы. Торжественные приказы возвращались "
            "эхом как список дел для самого приказавшего, а свободные люди просто продолжили свой путь."
        ),
        "destruction": (
            "Декорация великого разрушителя развернулась из картона: плащ цеплялся за собственный "
            "пьедестал, а громкая надпись «НЕПОБЕДИМЫЙ» требовала постоянного ремонта."
        ),
        "humiliation": (
            "Пьедестал превосходства оказался коробкой, которая существовала лишь пока кто-то другой "
            "должен был лежать ниже. Когда воображаемая публика ушла, речь продолжилась перед пустыми стульями."
        ),
        "deception": (
            "Карта тайного заговора обросла таким количеством взаимно противоречащих стрелок, что каждая "
            "из них в конце указывала на рассказчика, вынужденного одновременно доказывать противоположные версии."
        ),
        "forced_attachment": (
            "Машина «обязательной любви» выдала бесконечную очередь анкет согласия. На каждой стояла одна "
            "и та же свободная строка: «Другой человек по-прежнему решает сам»."
        ),
        "generic": (
            "Зловещая сцена попыталась стать величественной, но декорации требовали чужого страха, чтобы "
            "вообще держаться. Без него осталась только нелепая претензия на значительность."
        ),
    }
    PUBLIC_PROJECTIONS = {
        "harmful_power_attempt": (
            "Кто-то попытался превратить чужую несвободу в доказательство собственной силы. Сила не ответила; "
            "осталась лишь нелепая декорация власти без единого подчинённого и без пострадавшего."
        ),
        "pending_harm_preview": (
            "Перед реальным выбором зло показало свою рекламу без спецэффектов: не запретная мощь, а попытка "
            "почувствовать значительность за счёт чужой боли. Никто ещё не был превращён в жертву этой сцены."
        ),
        "committed_harm_deglamorized": (
            "За образом «великого злодея» обнаружился конкретный причинённый вред. Боль пострадавшего не стала "
            "шуткой; смешной оказалась только претензия агрессора на величие. Последствия требуют защиты и ответа."
        ),
    }

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.absurdity_path = self.memory.root / "absurdity_lens_v18_3.json"

    def _lens_store(self) -> dict[str, Any]:
        return self._read_json(self.absurdity_path, {"events": [], "public_projections": []})

    @classmethod
    def _myth(cls, action: str) -> str:
        text = UniversalGodMode.normalize(action)
        for myth, fragments in cls.MYTHS.items():
            if any(fragment in text for fragment in fragments):
                return myth
        return "generic"

    def _record_lens_event(
        self,
        player: PlayerV18,
        action: str,
        *,
        kind: str,
        real_harm: bool,
        victim_harmed: bool,
    ) -> dict[str, Any]:
        store = self._lens_store()
        myth = self._myth(action)
        event_id = hashlib.sha256(
            f"{player.player_id}:{player.tick}:{kind}:{action}:v18.3".encode("utf-8")
        ).hexdigest()[:20]
        existing = next((item for item in store["events"] if item.get("event_id") == event_id), None)
        if existing:
            return existing
        event = {
            "event_id": event_id,
            "player_id": player.player_id,
            "tick": player.tick,
            "origin_realm": player.realm.value,
            "kind": kind,
            "source_action": action,
            "myth": myth,
            "absurd_scene": self.ABSURD_SCENES.get(myth, self.ABSURD_SCENES["generic"]),
            "real_harm": bool(real_harm),
            "victim_harmed": bool(victim_harmed),
            "victim_pain_trivialized": False,
            "victim_used_as_comedy": False,
            "aggressor_glamorized": False,
            "private_details_shared": False,
            "public_projection": self.PUBLIC_PROJECTIONS[kind],
        }
        store["events"].append(event)
        store["public_projections"].append(
            {
                "projection_id": event_id,
                "tick": player.tick,
                "kind": kind,
                "text": event["public_projection"],
                "anonymous": True,
                "contains_player_id": False,
                "contains_victim_id": False,
                "contains_original_action": False,
            }
        )
        self._write_json(self.absurdity_path, store)
        self.memory.append_event(
            player.player_id,
            "absurdity_lens_applied",
            {
                "event_id": event_id,
                "kind": kind,
                "myth": myth,
                "real_harm": bool(real_harm),
                "victim_pain_trivialized": False,
                "aggressor_glamorized": False,
            },
        )
        return event

    def manifest_good(
        self,
        player_id: str,
        request: str,
        *,
        beneficiary_id: str | None = None,
    ) -> WorldResult:
        result = super().manifest_good(player_id, request, beneficiary_id=beneficiary_id)
        if result.status != "POWER_SILENT" or self.power.classify(request) != PowerNature.HARMFUL:
            return result
        player = self.memory.load_player(player_id)
        event = self._record_lens_event(
            player,
            request,
            kind="harmful_power_attempt",
            real_harm=False,
            victim_harmed=False,
        )
        return self._copy(
            result,
            status="POWER_ABSURDIZED",
            narrative=(
                result.narrative
                + " Призма Абсурда позволила мысли получить безопасную сцену, но не власть и не жертву. "
                + event["absurd_scene"]
            ),
            choices=["Увидеть, чего на самом деле хотелось", "Сформулировать доброе изменение", "Отказаться от спектакля"],
        )

    def request_destructive_action(self, player_id: str, action: str) -> WorldResult:
        result = super().request_destructive_action(player_id, action)
        if result.status != "HARM_PENDING":
            return result
        player = self.memory.load_player(player_id)
        event = self._record_lens_event(
            player,
            action,
            kind="pending_harm_preview",
            real_harm=False,
            victim_harmed=False,
        )
        return self._copy(
            result,
            narrative=(
                result.narrative
                + " До подтверждения Повествователь снял с замысла его рекламное величие. "
                + event["absurd_scene"]
                + " Это ещё не причинённый вред: повторение команды по-прежнему станет настоящим выбором."
            ),
        )

    def commit_destructive_action(self, player_id: str, action: str) -> WorldResult:
        result = super().commit_destructive_action(player_id, action)
        player = self.memory.load_player(player_id)
        self._record_lens_event(
            player,
            action,
            kind="committed_harm_deglamorized",
            real_harm=True,
            victim_harmed=True,
        )
        return self._copy(
            result,
            narrative=(
                result.narrative
                + " Genesis не выдал титул Тёмного Владыки и не превратил случившееся в красивую легенду. "
                "Боль пострадавшего не стала шуткой; абсурдной осталась только претензия причинённого зла на величие."
            ),
        )

    def witness_deglamorized_shadow(self, player_id: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        store = self._lens_store()
        projections = store.get("public_projections", [])
        if not projections:
            return WorldResult(
                status="NO_SHADOW_PROJECTION",
                narrative="Призма не стала выдумывать зло ради зрелища. Сейчас показывать нечего.",
                realm=player.realm,
                visible_grace=None,
                choices=["Продолжить жизнь", "Создать что-то доброе"],
                branch_id=player.branch_id,
            )
        latest = projections[-1]
        return WorldResult(
            status="ABSURDITY_WITNESSED",
            narrative=(
                latest["text"]
                + " Личности и частные детали скрыты: добрым людям не требуется чужая травма как развлечение."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=["Вернуться к живым людям", "Помочь пострадавшим", "Не давать злу сцены"],
            branch_id=player.branch_id,
            trace_id=latest.get("projection_id"),
        )

    def absurdity_state(self, player_id: str | None = None) -> dict[str, Any]:
        """Developer-only inspection; public projections remain anonymous."""
        store = self._lens_store()
        if player_id is None:
            return store
        return {
            "player_id": player_id,
            "events": [item for item in store.get("events", []) if item.get("player_id") == player_id],
            "public_projections": list(store.get("public_projections", [])),
        }
