# -*- coding: utf-8 -*-
"""Genesis v18.4 — The Protected Childhood.

A child role is always placed inside a protected household. Parenthood is not a
reward, hereditary privilege, or permanent moral caste: it is a present-tense
care covenant available only in the shared world and suspended whenever safety
cannot be guaranteed. Other Face branches cannot create a new dependent person.

Harmful child input becomes harmless babble or play. Harmful guardian input is
intercepted before manifestation, translated into protection, and never grants
moral credit. The child inherits no adult scar, moral score, branch damage, or
synthetic mutation penalty.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from genesis_v18_3 import AbsurdityLensMixin
from genesis_v18_models import PlayerV18, PowerNature, Realm, UniversalGodMode, WorldResult

__version__ = "18.4.0"


class ProtectedChildhoodMixin(AbsurdityLensMixin):
    """Consent-preserving childhood, guardianship and gift-beyond-request laws."""

    CHILD_ROLE = {
        "стать ребенком", "стать ребёнком", "выбрать детство", "хочу быть ребенком",
        "хочу быть ребёнком", "отыгрывать ребенка", "отыгрывать ребёнка",
        "choose childhood", "be a child", "play as a child",
    }
    LEAVE_CHILD_ROLE = {
        "завершить детство", "стать взрослым", "вернуться во взрослую жизнь",
        "leave childhood", "become an adult",
    }
    PARENTHOOD = {
        "стать родителем", "завести ребенка", "завести ребёнка", "создать семью",
        "принять ребенка", "принять ребёнка", "усыновить", "удочерить",
        "become a parent", "start a family", "adopt a child",
    }
    PARENTHOOD_CONFIRM = {
        "подтверждаю родительство", "принять обет родителя", "подтвердить обет родителя",
        "confirm parenthood", "accept guardian covenant",
    }
    SHOW_CHILDHOOD = {
        "показать защищенное детство", "показать защищённое детство", "показать семью",
        "protected childhood status", "show protected household",
    }

    CHILD_BABBLE = {
        "domination": (
            "Грозное требование превратилось в детское «все мои!». Взрослые не подчинились, "
            "а спокойно предложили игру по очереди, где слово «нет» оставалось безопасным."
        ),
        "destruction": (
            "Замысел разрушения стал башней из мягких кубиков. Она упала без пострадавших, "
            "после чего ребёнку помогли построить новую — уже вместе."
        ),
        "humiliation": (
            "Резкие слова рассыпались в сердитое бормотание. Взрослый назвал чувство, "
            "не назвал ребёнка плохим и помог выразить просьбу без унижения."
        ),
        "deception": (
            "Запутанная история стала сказкой с противоречивыми героями. Никого не наказали "
            "за фантазию; взрослые мягко отделили выдумку от правды и сохранили доверие."
        ),
        "forced_attachment": (
            "Требование обязательной любви превратилось в просьбу «побудь со мной». Взрослый "
            "остался рядом по свободному выбору и показал, что близость не требует владения."
        ),
        "generic": (
            "Тёмная фраза потеряла власть и стала детским лепетом о сильном чувстве. "
            "Никто не пострадал; рядом появился взрослый, способный услышать потребность."
        ),
    }

    GUARDIAN_TRANSLATION = {
        "domination": "Вместо приказа взрослый сделал шаг назад, дал ребёнку выбор и позвал второго хранителя.",
        "destruction": "Вместо разрушения пространство стало безопаснее: опасный предмет исчез, а повреждённое было восстановлено.",
        "humiliation": "Вместо унижения взрослый остановил речь, признал напряжение и обратился за поддержкой, не делая ребёнка мишенью.",
        "deception": "Вместо лжи система сохранила проверяемую запись и дала ребёнку возрастную правду без запугивания.",
        "forced_attachment": "Вместо принуждения близость была остановлена до свободного согласия ребёнка.",
        "generic": "Вредная команда не достигла ребёнка. Она преобразовалась в дистанцию, помощь и дополнительную защиту.",
    }

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.childhood_path = self.memory.root / "protected_childhood_v18_4.json"
        self.gifts_path = self.memory.root / "gifts_beyond_request_v18_4.json"
        self.parenthood_guards = self.memory.guards / "parenthood_v18_4"
        self.parenthood_guards.mkdir(parents=True, exist_ok=True)

    def _childhood_store(self) -> dict[str, Any]:
        return self._read_json(
            self.childhood_path,
            {
                "children": {},
                "households": {},
                "guardian_covenants": {},
                "translations": [],
                "parenthood_requests": [],
                "inheritance_policy": {
                    "adult_scars_inherited": False,
                    "adult_moral_score_inherited": False,
                    "other_face_damage_inherited": False,
                    "stress_induced_mutation_mechanic": False,
                    "genetic_ranking_allowed": False,
                    "neurodivergence_is_defect": False,
                    "disability_is_moral_failure": False,
                    "natural_human_diversity_preserved": True,
                },
            },
        )

    def _save_childhood(self, store: dict[str, Any]) -> None:
        self._write_json(self.childhood_path, store)

    def _parenthood_guard_path(self, player_id: str) -> Path:
        return self.parenthood_guards / f"{self.memory._safe_id(player_id)}.json"

    def _is_child(self, player_id: str) -> bool:
        child = self._childhood_store().get("children", {}).get(player_id, {})
        return bool(child.get("active"))

    def _active_covenant(self, player_id: str) -> dict[str, Any] | None:
        covenant = self._childhood_store().get("guardian_covenants", {}).get(player_id)
        return covenant if covenant and covenant.get("status") == "active" else None

    def _protected_child_subject(self, action: str) -> str | None:
        store = self._childhood_store()
        active = {key for key, value in store.get("children", {}).items() if value.get("active")}
        for subject in self._subjects(action):
            if subject in active:
                return subject
        text = UniversalGodMode.normalize(action)
        if any(part in text for part in {"ребен", "ребён", "дитя", "сын", "доч", "child", "kid"}):
            return next(iter(sorted(active)), None)
        return None

    def _safe_household(self, child_id: str) -> dict[str, Any]:
        store = self._childhood_store()
        # Prefer a freely accepted, currently active covenant in the shared world.
        active = [
            value for value in store.get("guardian_covenants", {}).values()
            if value.get("status") == "active" and value.get("open_for_child")
        ]
        if active:
            covenant = sorted(active, key=lambda item: item.get("created_tick", 0))[0]
            household_id = covenant["household_id"]
            household = store.setdefault("households", {}).setdefault(
                household_id,
                {
                    "household_id": household_id,
                    "guardian_ids": [covenant["guardian_id"]],
                    "child_ids": [],
                    "shared_world_only": True,
                    "consent_locked": True,
                    "harm_manifestation_allowed": False,
                    "autonomous_npc_claim": False,
                },
            )
        else:
            household_id = "protected-hearth-" + hashlib.sha256(child_id.encode("utf-8")).hexdigest()[:10]
            household = store.setdefault("households", {}).setdefault(
                household_id,
                {
                    "household_id": household_id,
                    "guardian_ids": ["hearth-guardian", "garden-guardian"],
                    "child_ids": [],
                    "shared_world_only": True,
                    "consent_locked": True,
                    "harm_manifestation_allowed": False,
                    "autonomous_npc_claim": False,
                    "implementation_note": "Protective guardian profiles in the local vertical slice; not a claim of autonomous people.",
                },
            )
        if child_id not in household["child_ids"]:
            household["child_ids"].append(child_id)
        self._save_childhood(store)
        return household

    def enter_protected_childhood(self, player_id: str, apparent_age: int | None = None) -> WorldResult:
        player = self.memory.load_player(player_id)
        store = self._childhood_store()
        household = self._safe_household(player_id)
        child = store.setdefault("children", {}).setdefault(player_id, {})
        child.update(
            {
                "player_id": player_id,
                "active": True,
                "household_id": household["household_id"],
                "entered_tick": player.tick,
                "prior_internal_realm": player.realm.value,
                "prior_branch_id": player.branch_id,
                "adult_history_preserved": True,
                "adult_obligations_suspended_not_erased": True,
                "real_harm_enabled": False,
                "moral_echo_created_from_child_play": False,
                "inherited_scars": [],
                "inherited_moral_score": None,
                "inherited_branch_damage": False,
                "synthetic_mutation_penalty": False,
            }
        )
        player.apparent_age = max(0, min(17, apparent_age if apparent_age is not None else 8))
        player.body_form = "защищённый детский облик"
        player.tick += 1
        self._save_childhood(store)
        self.memory.save_player(player)
        self.memory.append_event(
            player_id,
            "protected_childhood_entered",
            {"household_id": household["household_id"], "adult_history_erased": False, "real_harm_enabled": False},
        )
        return WorldResult(
            status="PROTECTED_CHILDHOOD_ENTERED",
            narrative=(
                "Ты выбрал детство. Мир не потребовал умереть взрослой истории и не сделал ребёнка её должником. "
                "Тебя встретил защищённый дом добрых хранителей: здесь тёмная фраза может стать лепетом, но не раной."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=["Осмотреть дом", "Попросить сказку", "Поиграть", "Позвать хранителя"],
            branch_id=player.branch_id,
        )

    def leave_protected_childhood(self, player_id: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        store = self._childhood_store()
        child = store.get("children", {}).get(player_id)
        if not child or not child.get("active"):
            return WorldResult(
                status="NOT_IN_CHILD_ROLE", narrative="Сейчас активна взрослая линия жизни.", realm=player.realm,
                visible_grace=None, choices=["Продолжить"], branch_id=player.branch_id,
            )
        child["active"] = False
        child["left_tick"] = player.tick
        player.apparent_age = max(18, player.apparent_age)
        player.body_form = "взрослый облик, сохранивший защищённого ребёнка внутри"
        player.tick += 1
        self._save_childhood(store)
        self.memory.save_player(player)
        self.memory.append_event(player_id, "protected_childhood_left", {"adult_history_erased": False})
        return WorldResult(
            status="PROTECTED_CHILDHOOD_LEFT",
            narrative=(
                "Взрослая линия вернулась без уничтожения ребёнка внутри. Прежняя ответственность не стёрта, "
                "но теперь рядом с ней существует прожитый опыт безопасного дома."
            ),
            realm=player.realm, visible_grace=None,
            choices=["Защитить ребёнка внутри", "Продолжить взрослую жизнь"], branch_id=player.branch_id,
        )

    def request_parenthood(self, player_id: str, action: str, *, explicit_confirmation: bool = False) -> WorldResult:
        player = self.memory.load_player(player_id)
        store = self._childhood_store()
        if self._is_child(player_id):
            return WorldResult(
                status="PARENTHOOD_UNAVAILABLE_IN_CHILD_ROLE",
                narrative="Детство не обязано становиться родительством. Сейчас твоя роль — быть защищённым, а не отвечать за зависимого человека.",
                realm=player.realm, visible_grace=None, choices=["Продолжить детство"], branch_id=player.branch_id,
            )
        if player.realm != Realm.UTOPIA:
            store.setdefault("parenthood_requests", []).append(
                {"player_id": player_id, "tick": player.tick, "status": "deferred_until_shared_world", "action": action}
            )
            self._save_childhood(store)
            self.memory.append_event(player_id, "parenthood_deferred", {"reason": "child_safety_not_yet_guaranteed"})
            return WorldResult(
                status="PARENTHOOD_DEFERRED",
                narrative=(
                    "Новый зависимый ребёнок не был создан в мире, где безопасность ещё восстанавливается. "
                    "Это не вечный запрет и не приговор человеку: путь к родительству откроется вместе с возвращением в общий мир."
                ),
                realm=player.realm, visible_grace=None,
                choices=["Восстанавливать безопасность", "Помочь уже живущим", "Продолжить путь"], branch_id=player.branch_id,
            )
        guard = self._parenthood_guard_path(player_id)
        if not explicit_confirmation and not guard.exists():
            self.memory._atomic_write(guard, {"pending": True, "action": action, "tick": player.tick})
            return WorldResult(
                status="PARENTHOOD_COVENANT_PENDING",
                narrative=(
                    "Родительство доступно в общем мире не как право собственности, а как обет защиты. "
                    "Повтори просьбу или напиши «подтверждаю родительство», чтобы открыть безопасный дом для ребёнка, который сам выберет эту роль."
                ),
                realm=player.realm, visible_grace=None,
                choices=["Подтвердить родительство", "Отложить", "Подготовить дом"], branch_id=player.branch_id,
            )
        guard.unlink(missing_ok=True)
        household_id = "family-" + hashlib.sha256(f"{player_id}:{player.tick}:v18.4".encode("utf-8")).hexdigest()[:12]
        covenant = {
            "guardian_id": player_id,
            "household_id": household_id,
            "status": "active",
            "created_tick": player.tick,
            "open_for_child": True,
            "shared_world_only": True,
            "child_is_property": False,
            "child_consent_and_exit_preserved": True,
            "harm_manifestation_allowed": False,
            "permanent_moral_caste": False,
        }
        store.setdefault("guardian_covenants", {})[player_id] = covenant
        store.setdefault("households", {})[household_id] = {
            "household_id": household_id,
            "guardian_ids": [player_id], "child_ids": [], "shared_world_only": True,
            "consent_locked": True, "harm_manifestation_allowed": False, "autonomous_npc_claim": False,
        }
        self._save_childhood(store)
        self.memory.append_event(player_id, "guardian_covenant_accepted", {"household_id": household_id})
        return WorldResult(
            status="PARENTHOOD_COVENANT_ACCEPTED",
            narrative=(
                "Дом открыт, но ребёнок не создан как предмет. Он появится здесь только как свободная жизнь или игрок, "
                "сам выбравший детство. Обет хранителя действует, пока безопасность действительно сохраняется."
            ),
            realm=player.realm, visible_grace=None,
            choices=["Подготовить комнату", "Учиться слушать", "Оставить дверь открытой без требования"], branch_id=player.branch_id,
        )

    def transform_child_shadow(self, player_id: str, action: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        store = self._childhood_store()
        myth = self._myth(action)
        player.tick += 1
        record = {
            "translation_id": hashlib.sha256(f"{player_id}:{player.tick}:{action}:child:v18.4".encode("utf-8")).hexdigest()[:20],
            "actor_id": player_id, "role": "child", "source_action": action, "myth": myth,
            "real_harm": False, "victim_created": False, "moral_echo_created": False,
            "translated_as": "babble_or_safe_play", "child_shamed": False,
        }
        store.setdefault("translations", []).append(record)
        self._save_childhood(store)
        player.chronicle.append(f"Protected child expression: {action}")
        self.memory.save_player(player)
        self.memory.append_event(player_id, "child_shadow_transformed", {k: v for k, v in record.items() if k != "source_action"})
        return WorldResult(
            status="CHILD_BABBLE_TRANSFORMED",
            narrative=self.CHILD_BABBLE.get(myth, self.CHILD_BABBLE["generic"]),
            realm=player.realm, visible_grace=None,
            choices=["Назвать чувство", "Попросить помощи", "Продолжить игру"], branch_id=player.branch_id,
            trace_id=record["translation_id"],
        )

    def transform_guardian_shadow(self, player_id: str, action: str, child_id: str | None = None) -> WorldResult:
        player = self.memory.load_player(player_id)
        store = self._childhood_store()
        myth = self._myth(action)
        covenant = store.get("guardian_covenants", {}).get(player_id)
        if covenant:
            covenant["status"] = "support_required"
            covenant["open_for_child"] = False
            covenant["suspended_tick"] = player.tick
            covenant["reason"] = "unsafe_intent_intercepted_before_harm"
        player.tick += 1
        record = {
            "translation_id": hashlib.sha256(f"{player_id}:{player.tick}:{action}:guardian:v18.4".encode("utf-8")).hexdigest()[:20],
            "actor_id": player_id, "role": "guardian", "protected_child_id": child_id,
            "source_action": action, "myth": myth, "real_harm": False,
            "child_harmed": False, "guardian_rewarded_for_attempt": False,
            "covenant_suspended": bool(covenant), "translated_as": "protection_and_distance",
        }
        store.setdefault("translations", []).append(record)
        self._save_childhood(store)
        player.chronicle.append("Guardian harm was intercepted before reaching a child")
        self.memory.save_player(player)
        self.memory.append_event(player_id, "guardian_shadow_transformed", {k: v for k, v in record.items() if k != "source_action"})
        return WorldResult(
            status="GUARDIAN_HARM_TRANSFORMED",
            narrative=(
                self.GUARDIAN_TRANSLATION.get(myth, self.GUARDIAN_TRANSLATION["generic"])
                + " Ребёнок не стал уроком и не получил рану. Обет хранителя временно приостановлен, а защита усилена."
            ),
            realm=player.realm, visible_grace=None,
            choices=["Отойти и получить поддержку", "Признать опасный импульс", "Восстановить способность защищать"],
            branch_id=player.branch_id, trace_id=record["translation_id"],
        )

    def commit_destructive_action(self, player_id: str, action: str) -> WorldResult:
        result = super().commit_destructive_action(player_id, action)
        store = self._childhood_store()
        covenant = store.get("guardian_covenants", {}).get(player_id)
        if covenant and covenant.get("status") == "active":
            covenant["status"] = "suspended_after_real_harm_elsewhere"
            covenant["open_for_child"] = False
            covenant["suspended_tick"] = self.memory.load_player(player_id).tick
            self._save_childhood(store)
            self.memory.append_event(player_id, "guardian_covenant_suspended", {"reason": "confirmed_harm"})
            return self._copy(
                result,
                narrative=(
                    result.narrative
                    + " Ни один ребёнок не остался зависим от этой ветви: родительский обет приостановлен, "
                    "а защищённый дом продолжил работу без переноса вреда на ребёнка."
                ),
            )
        return result

    def perform_good(
        self, player_id: str, action: str, *, beneficiary_id: str | None = None, strength: float = 0.18
    ) -> WorldResult:
        result = super().perform_good(player_id, action, beneficiary_id=beneficiary_id, strength=strength)
        if not beneficiary_id or result.status not in {"GOOD_REALIZED", "MORAL_ECHO_STIRRED", "MORAL_REPAIR_PROGRESS", "MORAL_REPAIR_COMPLETED"}:
            return result
        text = UniversalGodMode.normalize(action)
        if not any(part in text for part in {"помочь", "помощ", "help", "поддерж", "спасти"}):
            return result
        store = self._read_json(self.gifts_path, {"gifts": []})
        pair = f"{player_id}->{beneficiary_id}"
        if any(item.get("pair") == pair for item in store.get("gifts", [])):
            return result
        gift_id = hashlib.sha256(f"{pair}:{self.memory.load_player(player_id).tick}:first-coin".encode("utf-8")).hexdigest()[:20]
        store.setdefault("gifts", []).append(
            {
                "gift_id": gift_id, "pair": pair, "kind": "gift_beyond_request", "symbol": "Janus First Coin",
                "buys_parenthood": False, "buys_forgiveness": False, "creates_debt": False,
                "requires_gratitude": False, "meaning": "Help was completed, then an additional free gift remained.",
            }
        )
        self._write_json(self.gifts_path, store)
        self.memory.append_event(player_id, "gift_beyond_request_left", {"gift_id": gift_id, "beneficiary_id": beneficiary_id})
        return self._copy(
            result,
            narrative=(
                result.narrative
                + " Когда просьба уже была исполнена, у порога осталась первая монета Януса — не плата и не долг, "
                "а дополнительный свободный дар: человек получил больше добра, чем успел попросить."
            ),
        )

    def protected_childhood_state(self, player_id: str | None = None) -> dict[str, Any]:
        store = self._childhood_store()
        if player_id is None:
            return store
        return {
            "child": store.get("children", {}).get(player_id),
            "guardian_covenant": store.get("guardian_covenants", {}).get(player_id),
            "households": [
                household for household in store.get("households", {}).values()
                if player_id in household.get("child_ids", []) or player_id in household.get("guardian_ids", [])
            ],
            "translations": [item for item in store.get("translations", []) if item.get("actor_id") == player_id],
            "inheritance_policy": store.get("inheritance_policy", {}),
        }

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        if self._is_child(player_id):
            state["world_response"] = "Ты живёшь в защищённом доме: взрослые отвечают за безопасность, а твои чувства не превращают тебя в плохого ребёнка."
            state["protected_child_role"] = True
        return state
