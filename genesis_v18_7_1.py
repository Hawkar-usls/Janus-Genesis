# -*- coding: utf-8 -*-
"""Genesis v18.7.1 — The Remembering Other.

Polishes the v18.7 agency contract with longer contextual dialogue memory,
initiative cooldowns, repetition suppression and reasons grounded in the
current offer, the Other's calling, current project and prior exchanges.

The resident remains a narrative simulation. Memory and agency are runtime
contracts, not claims of consciousness or personhood.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

from genesis_v18_models import WorldResult

__version__ = "18.7.1"
SOURCE = "janus_genesis_v18_7_1"
MEMORY_LIMIT = 64
HISTORY_LIMIT = 160
RECENT_TEXT_LIMIT = 12


class RememberingOtherMixin:
    """Add contextual memory and anti-repetition rules to the Free Other."""

    TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("инструмент", ("инструмент", "механизм", "чертёж", "мастерск", "device", "tool")),
        ("дорога", ("дорог", "путь", "мост", "проход", "карта", "route", "bridge")),
        ("разговор", ("разговор", "поговор", "сказать", "рассказать", "вопрос", "speak", "talk")),
        ("помощь", ("помочь", "исцел", "поддерж", "согреть", "help", "heal")),
        ("дар", ("подар", "передать", "дать", "gift", "give")),
        ("совместный путь", ("вместе", "встрет", "приглас", "следовать", "together", "meet")),
        ("молчание", ("молч", "тишин", "ничего не говорить", "silence")),
        ("пространство", ("пространств", "не беспокоить", "оставить в покое", "space")),
        ("память", ("памят", "сохран", "вспом", "memory", "remember")),
        ("дом", ("дом", "комнат", "убежищ", "house", "room")),
        ("сад", ("сад", "семя", "растен", "garden", "seed")),
        ("музыка", ("музык", "песня", "радио", "эфир", "music", "radio")),
    )

    def _new_free_player(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        profile = super()._new_free_player(store, player_id)
        return self._upgrade_profile(profile, int(store.get("world_turn", 0)))

    def _free_profile(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        profile = super()._free_profile(store, player_id)
        return self._upgrade_profile(profile, int(store.get("world_turn", 0)))

    def _upgrade_profile(self, profile: dict[str, Any], world_turn: int) -> dict[str, Any]:
        profile["dialogue_contract_version"] = __version__
        profile.setdefault("recent_visible_event_fingerprints", [])
        profile.setdefault("last_visible_other_turn", None)
        for actor in profile.get("others", {}).values():
            actor.setdefault("dialogue_memory", [])
            actor.setdefault("conversation_topics", {})
            actor.setdefault("last_contact_fingerprint", None)
            actor.setdefault("last_contact_topic", None)
            actor.setdefault("last_contact_world_turn", None)
            actor.setdefault("last_response_reason", None)
            actor.setdefault("initiative_cooldown_until", world_turn)
            actor.setdefault("recent_initiative_fingerprints", [])
            actor.setdefault("last_initiative_world_turn", None)
            actor.setdefault("departure_context", None)
            actor.setdefault("return_context", None)
            actor["memory_contract_version"] = __version__
            actor["history"] = list(actor.get("history", []))[-HISTORY_LIMIT:]
            actor["dialogue_memory"] = list(actor.get("dialogue_memory", []))[-MEMORY_LIMIT:]
        return profile

    @classmethod
    def _dialogue_topic(cls, action: str) -> str:
        text = action.lower()
        for topic, fragments in cls.TOPIC_RULES:
            if any(fragment in text for fragment in fragments):
                return topic
        return "неопределённый замысел"

    @staticmethod
    def _short_action(action: str, limit: int = 150) -> str:
        compact = " ".join(action.strip().split())
        return compact if len(compact) <= limit else compact[: limit - 1] + "…"

    @staticmethod
    def _memory_fingerprint(text: str) -> str:
        return hashlib.sha256(" ".join(text.lower().split()).encode("utf-8")).hexdigest()[:20]

    def _recent_topic_memory(self, actor: dict[str, Any], topic: str) -> dict[str, Any] | None:
        for item in reversed(actor.get("dialogue_memory", [])):
            if item.get("topic") == topic:
                return item
        return None

    def _is_repeated_contact(
        self,
        actor: dict[str, Any],
        *,
        fingerprint: str,
        topic: str,
        upcoming: int,
    ) -> bool:
        last_turn = actor.get("last_contact_world_turn")
        if last_turn is None:
            return False
        age = upcoming - int(last_turn)
        same_fingerprint = actor.get("last_contact_fingerprint") == fingerprint
        same_topic = actor.get("last_contact_topic") == topic
        return (same_fingerprint and age < 8) or (same_topic and age < 3)

    def _context_reason(
        self,
        actor: dict[str, Any],
        *,
        decision: str,
        action: str,
        topic: str,
        repeated: bool,
    ) -> str:
        stage = actor["stages"][min(int(actor["stage_index"]), len(actor["stages"]) - 1)]
        prior = self._recent_topic_memory(actor, topic)
        prior_clause = ""
        if prior:
            prior_clause = f" Он помнит прежний разговор о теме «{topic}» на ходу {prior.get('world_turn')}."
        if repeated:
            return (
                f"Предложение о теме «{topic}» повторилось раньше, чем завершился предыдущий ответ. "
                f"{actor['name']} сохраняет паузу, пока {stage}." + prior_clause
            )
        if decision == "away":
            departure = actor.get("departure_context") or actor.get("away_reason") or "собственная дорога"
            return (
                f"{actor['name']} сейчас отсутствует: {departure}. Тема «{topic}» не может получить ответ вместо него."
            )
        if decision == "accepted_space":
            return (
                f"Действие касалось пространства, а не получения согласия. {actor['name']} может использовать его, "
                f"не объяснять использование и не возвращаться к теме «{topic}»."
            )
        if decision == "accepted":
            return (
                f"Тема «{topic}» совместима с нынешним этапом его пути: {stage}. "
                "Согласие относится только к этому предложению и этому моменту." + prior_clause
            )
        if decision == "alternative":
            return (
                f"Предложенная форма не совпала с тем, как {actor['name']} сейчас продолжает работу: {stage}. "
                f"Он сохраняет саму тему «{topic}», но меняет способ контакта." + prior_clause
            )
        return (
            f"{actor['name']} не выбирает предложенную форму для темы «{topic}», пока {stage}. "
            "Отказ защищает текущую границу и не является оценкой ценности игрока." + prior_clause
        )

    def preflight_free_other_action(self, player_id: str, action: str) -> dict[str, Any] | None:
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        targets = self._targets(action)
        handle = next((item for item in targets if item in profile["others"]), None)
        if handle is None or not self._is_contact_action(action) or self._is_coercive_contact(action):
            self._write_json(self.free_other_path, store)
            return None
        actor = profile["others"][handle]
        upcoming = int(store["world_turn"]) + 1
        fingerprint = self._free_fingerprint(action)
        topic = self._dialogue_topic(action)
        repeated = self._is_repeated_contact(
            actor,
            fingerprint=fingerprint,
            topic=topic,
            upcoming=upcoming,
        )
        if self._is_giving_space(action):
            decision = "accepted_space"
        elif actor["status"] != "active":
            decision = "away"
        elif repeated:
            decision = "refused"
        else:
            gate = self._free_number(
                store,
                player_id,
                handle,
                upcoming,
                fingerprint,
                topic,
                "contextual-consent",
            ) % 100
            acceptance = 34 + int(float(actor["trust"]) * 26)
            if gate < acceptance:
                decision = "accepted"
            elif gate < acceptance + 34:
                decision = "alternative"
            else:
                decision = "refused"
        reason = self._context_reason(
            actor,
            decision=decision,
            action=action,
            topic=topic,
            repeated=repeated,
        )
        result = {
            "handle": handle,
            "decision": decision,
            "action": action,
            "world_turn": upcoming,
            "fingerprint": fingerprint,
            "topic": topic,
            "intent": self._intent(action),
            "repeated_too_soon": repeated,
            "reason": reason,
            "action_excerpt": self._short_action(action),
        }
        self._write_json(self.free_other_path, store)
        return result

    def unrealized_free_other_result(self, player_id: str, decision: dict[str, Any]) -> WorldResult:
        base = super().unrealized_free_other_result(player_id, decision)
        label = {
            "refused": "Другой отказался от предложенной формы.",
            "alternative": "Другой предложил иной способ контакта.",
            "away": "Другой сейчас находится на собственной дороге.",
        }.get(decision["decision"], "Предложение не стало совершившимся действием.")
        return replace(
            base,
            narrative=(
                f"{label}\nПредложение: «{decision.get('action_excerpt', self._short_action(decision['action']))}».\n"
                f"Причина в контексте: {decision.get('reason', 'Ответ не был присвоен игроком.')}"
            ),
        )

    def _remember_dialogue(
        self,
        actor: dict[str, Any],
        *,
        world_turn: int,
        decision: dict[str, Any],
        response_text: str,
        action_realized: bool,
    ) -> dict[str, Any]:
        topic = decision.get("topic") or self._dialogue_topic(decision["action"])
        item = {
            "world_turn": world_turn,
            "action": self._short_action(decision["action"], 240),
            "action_fingerprint": decision["fingerprint"],
            "topic": topic,
            "intent": decision.get("intent") or self._intent(decision["action"]),
            "decision": decision["decision"],
            "reason": decision.get("reason"),
            "response": response_text,
            "response_fingerprint": self._memory_fingerprint(response_text),
            "action_realized": bool(action_realized),
            "player_controlled_response": False,
        }
        actor["dialogue_memory"] = (actor.get("dialogue_memory", []) + [item])[-MEMORY_LIMIT:]
        topics = actor.setdefault("conversation_topics", {})
        topic_state = topics.setdefault(topic, {"count": 0, "last_world_turn": None, "last_decision": None})
        topic_state["count"] += 1
        topic_state["last_world_turn"] = world_turn
        topic_state["last_decision"] = decision["decision"]
        actor["last_contact_fingerprint"] = decision["fingerprint"]
        actor["last_contact_topic"] = topic
        actor["last_contact_world_turn"] = world_turn
        actor["last_response_reason"] = decision.get("reason")
        return item

    def _apply_contact_decision(
        self,
        store: dict[str, Any],
        player_id: str,
        profile: dict[str, Any],
        decision: dict[str, Any],
        *,
        action_realized: bool,
    ) -> dict[str, Any]:
        actor = profile["others"][decision["handle"]]
        world_turn = int(store["world_turn"])
        kind = decision["decision"]
        actor["contacts"] += 1
        reason = decision.get("reason") or self._context_reason(
            actor,
            decision=kind,
            action=decision["action"],
            topic=decision.get("topic") or self._dialogue_topic(decision["action"]),
            repeated=bool(decision.get("repeated_too_soon")),
        )
        if kind == "accepted":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.08)
            text = (
                f"{actor['name']} свободно принял конкретное предложение «{decision.get('action_excerpt', self._short_action(decision['action']))}». "
                f"{reason}"
            )
        elif kind == "accepted_space":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.03)
            text = f"{actor['name']} принял оставленное пространство. {reason}"
        elif kind == "alternative":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.015)
            actor["refusals_count"] += 1
            alternatives = list(actor["alternatives"])
            recent = {
                item.get("response_fingerprint")
                for item in actor.get("dialogue_memory", [])[-RECENT_TEXT_LIMIT:]
            }
            available = [item for item in alternatives if self._memory_fingerprint(item) not in recent] or alternatives
            alternative = self._free_pick(
                store,
                available,
                player_id,
                actor["handle"],
                world_turn,
                decision["fingerprint"],
                "context-alternative",
            )
            text = f"{actor['name']} не принял предложенный способ. {reason} Вместо него: {alternative}"
        elif kind == "refused":
            actor["refusals_count"] += 1
            actor["distance"] += 1
            text = (
                f"{actor['name']} отказался от предложения «{decision.get('action_excerpt', self._short_action(decision['action']))}». "
                f"{reason}"
            )
        else:
            text = f"{actor['name']} сейчас находится на собственной дороге. {reason}"
        record_kind = "refusal" if kind in {"refused", "alternative"} else kind
        self._remember_dialogue(
            actor,
            world_turn=world_turn,
            decision=decision,
            response_text=text,
            action_realized=action_realized,
        )
        actor["history"] = (
            actor.get("history", [])
            + [{
                "world_turn": world_turn,
                "kind": record_kind,
                "text": text,
                "source_action": decision["action"],
                "topic": decision.get("topic"),
                "reason": reason,
                "action_realized": bool(action_realized),
            }]
        )[-HISTORY_LIMIT:]
        self._record_other_graph_event(
            player_id,
            actor,
            kind=record_kind,
            text=text,
            world_turn=world_turn,
            source_action=decision["action"],
        )
        return {
            "kind": record_kind,
            "handle": actor["handle"],
            "text": text,
            "priority": -1,
            "topic": decision.get("topic"),
            "reason": reason,
        }

    def _eligible_initiative_texts(self, actor: dict[str, Any], profile: dict[str, Any]) -> list[str]:
        recent_actor = set(actor.get("recent_initiative_fingerprints", []))
        recent_profile = set(profile.get("recent_visible_event_fingerprints", []))
        return [
            text
            for text in actor["initiatives"]
            if self._memory_fingerprint(text) not in recent_actor | recent_profile
        ]

    def _advance_one_profile(
        self,
        store: dict[str, Any],
        owner_id: str,
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        self._upgrade_profile(profile, int(store["world_turn"]))
        world_turn = int(store["world_turn"])
        events: list[dict[str, Any]] = []
        actor_changed_this_turn: set[str] = set()
        for handle, actor in profile["others"].items():
            if actor["status"] == "away":
                if actor.get("away_reason") == "confirmed_harm":
                    continue
                left = int(actor.get("left_world_turn") or world_turn)
                gate = self._free_number(store, owner_id, handle, world_turn, "remembered-return") % 100
                if world_turn - left >= 5 and gate < 31:
                    previous_context = actor.get("departure_context") or "собственный незавершённый путь"
                    actor["status"] = "active"
                    actor["away_reason"] = None
                    actor["stage_index"] = min(4, len(actor["stages"]) - 1)
                    actor["returns"] += 1
                    actor["last_changed_world_turn"] = world_turn
                    actor["initiative_cooldown_until"] = world_turn + 3
                    actor["return_context"] = f"вернулся после линии: {previous_context}; нынешнее призвание: {actor['calling']}"
                    text = (
                        f"{actor['name']} вернулся после того, как продолжал: {previous_context}. "
                        f"Теперь он {actor['stages'][actor['stage_index']]}. Возвращение сохранило память об уходе, "
                        "но не стало наградой, согласием или прощением."
                    )
                    events.append({"kind": "return", "handle": handle, "text": text, "priority": 1})
                    actor_changed_this_turn.add(handle)
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": "return",
                        "text": text,
                        "departure_context": previous_context,
                    }])[-HISTORY_LIMIT:]
                    self._record_other_graph_event(owner_id, actor, kind="return", text=text, world_turn=world_turn)
                continue

            progress_gate = self._free_number(store, owner_id, handle, world_turn, "remembered-progress") % 100
            if progress_gate < 39:
                actor["progress"] += 1
                target = min(3, actor["progress"] // 2)
                if target > actor["stage_index"]:
                    actor["stage_index"] = target
                    actor["last_changed_world_turn"] = world_turn
                    text = (
                        f"{actor['name']} {actor['stages'][target]}. Продолжение связано с его призванием "
                        f"«{actor['calling']}» и не возникло как награда или задание игрока."
                    )
                    kind = "path"
                    priority = 3
                    if target == 3:
                        actor["status"] = "away"
                        actor["away_reason"] = "own_path"
                        actor["left_world_turn"] = world_turn
                        actor["departures"] += 1
                        actor["departure_context"] = f"{actor['stages'][target]} ради призвания «{actor['calling']}»"
                        kind = "departure"
                        priority = 1
                        text += f" Он ушёл, чтобы продолжить: {actor['departure_context']}. Уход не обещает возвращения."
                    events.append({"kind": kind, "handle": handle, "text": text, "priority": priority})
                    actor_changed_this_turn.add(handle)
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": kind,
                        "text": text,
                        "calling": actor["calling"],
                        "stage_index": target,
                    }])[-HISTORY_LIMIT:]
                    self._record_other_graph_event(owner_id, actor, kind=kind, text=text, world_turn=world_turn)

            if actor["stage_index"] >= 4 and actor["calling_changes"] == 0:
                change_gate = self._free_number(store, owner_id, handle, world_turn, "remembered-calling") % 100
                if change_gate < 21:
                    new_calling = self._free_pick(store, actor["new_callings"], owner_id, handle, world_turn, "calling")
                    old_calling = actor["calling"]
                    actor["calling"] = new_calling
                    actor["calling_changes"] += 1
                    actor["initiative_cooldown_until"] = world_turn + 4
                    text = (
                        f"{actor['name']} завершил линию прежнего призвания «{old_calling}» и выбрал: {new_calling}. "
                        "Память о старой роли сохранилась, но перестала определять будущие ответы."
                    )
                    events.append({"kind": "calling_changed", "handle": handle, "text": text, "priority": 0})
                    actor_changed_this_turn.add(handle)
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": "calling_changed",
                        "text": text,
                        "old_calling": old_calling,
                        "new_calling": new_calling,
                    }])[-HISTORY_LIMIT:]
                    self._record_other_graph_event(owner_id, actor, kind="calling_changed", text=text, world_turn=world_turn)

        active = [
            actor
            for actor in profile["others"].values()
            if actor["status"] == "active"
            and actor["handle"] not in actor_changed_this_turn
            and world_turn >= int(actor.get("initiative_cooldown_until", 0))
        ]
        if active:
            initiative_gate = self._free_number(store, owner_id, world_turn, "remembered-initiative") % 100
            if initiative_gate < 27:
                ordered = sorted(
                    active,
                    key=lambda actor: self._free_number(store, owner_id, actor["handle"], world_turn, "initiative-actor"),
                )
                actor = next((candidate for candidate in ordered if self._eligible_initiative_texts(candidate, profile)), None)
                if actor is not None:
                    options = self._eligible_initiative_texts(actor, profile)
                    text = self._free_pick(
                        store,
                        options,
                        owner_id,
                        actor["handle"],
                        world_turn,
                        "remembered-initiative-text",
                    )
                    fingerprint = self._memory_fingerprint(text)
                    actor["initiated_contacts"] += 1
                    actor["last_initiative_world_turn"] = world_turn
                    actor["initiative_cooldown_until"] = world_turn + 6 + (
                        self._free_number(store, owner_id, actor["handle"], world_turn, "cooldown") % 5
                    )
                    actor["recent_initiative_fingerprints"] = (
                        actor.get("recent_initiative_fingerprints", []) + [fingerprint]
                    )[-RECENT_TEXT_LIMIT:]
                    profile["recent_visible_event_fingerprints"] = (
                        profile.get("recent_visible_event_fingerprints", []) + [fingerprint]
                    )[-RECENT_TEXT_LIMIT:]
                    contextual = (
                        f"{text} Инициатива возникла из текущего призвания «{actor['calling']}»; "
                        f"следующая инициатива этого Другого не появится раньше хода {actor['initiative_cooldown_until']}."
                    )
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": "initiative",
                        "text": contextual,
                        "calling": actor["calling"],
                        "cooldown_until": actor["initiative_cooldown_until"],
                    }])[-HISTORY_LIMIT:]
                    events.append({"kind": "initiative", "handle": actor["handle"], "text": contextual, "priority": 2})
                    self._record_other_graph_event(owner_id, actor, kind="initiative", text=contextual, world_turn=world_turn)
        return events

    def _actor_graph_payload(self, actor: dict[str, Any]) -> dict[str, Any]:
        payload = super()._actor_graph_payload(actor)
        payload.update({
            "memory_contract_version": actor.get("memory_contract_version", __version__),
            "dialogue_memory_entries": len(actor.get("dialogue_memory", [])),
            "conversation_topics": sorted(actor.get("conversation_topics", {})),
            "initiative_cooldown_until": actor.get("initiative_cooldown_until"),
            "last_response_reason": actor.get("last_response_reason"),
            "departure_context": actor.get("departure_context"),
            "return_context": actor.get("return_context"),
        })
        return payload

    def free_other_state(self, player_id: str | None = None) -> dict[str, Any]:
        state = super().free_other_state(player_id)
        state["remembering_other_version"] = __version__
        state["memory_contract"] = {
            "dialogue_memory_limit": MEMORY_LIMIT,
            "initiative_repeat_window": RECENT_TEXT_LIMIT,
            "contextual_reasons": True,
            "initiative_cooldowns": True,
            "departure_context_preserved": True,
        }
        return state

    def verify_free_other_state(self) -> tuple[bool, int, int, str | None]:
        valid, players, others, error = super().verify_free_other_state()
        if not valid:
            return valid, players, others, error
        store = self._free_store()
        for player_id, profile in store.get("players", {}).items():
            self._upgrade_profile(profile, int(store.get("world_turn", 0)))
            for handle, actor in profile.get("others", {}).items():
                if len(actor.get("dialogue_memory", [])) > MEMORY_LIMIT:
                    return False, players, others, f"dialogue memory overflow: {player_id}/{handle}"
                if len(actor.get("recent_initiative_fingerprints", [])) > RECENT_TEXT_LIMIT:
                    return False, players, others, f"initiative memory overflow: {player_id}/{handle}"
                if actor.get("memory_contract_version") != __version__:
                    return False, players, others, f"memory contract missing: {player_id}/{handle}"
        self._write_json(self.free_other_path, store)
        return True, players, others, None
