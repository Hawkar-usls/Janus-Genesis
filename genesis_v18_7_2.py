# -*- coding: utf-8 -*-
"""Genesis v18.7.2 — The Remembering Voice.

Keeps the contextual memory and cooldown contract of v18.7.1 while rendering
Russian narrative responses without guessing grammatical gender from a name.
The voice uses stable present-tense or impersonal constructions so stored
memory, Chronicle excerpts and HRaiN events preserve the Other's identity.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from genesis_v18_7_1 import HISTORY_LIMIT, RECENT_TEXT_LIMIT
from genesis_v18_models import WorldResult

__version__ = "18.7.2"
VOICE_CONTRACT = "gender_neutral_ru_v1"


class RememberingVoiceMixin:
    """Render remembered agency without accidental grammatical reassignment."""

    def _upgrade_profile(self, profile: dict[str, Any], world_turn: int) -> dict[str, Any]:
        profile = super()._upgrade_profile(profile, world_turn)
        profile["voice_contract_version"] = __version__
        for actor in profile.get("others", {}).values():
            actor["voice_contract"] = VOICE_CONTRACT
        return profile

    def _context_reason(
        self,
        actor: dict[str, Any],
        *,
        decision: str,
        action: str,
        topic: str,
        repeated: bool,
    ) -> str:
        reason = super()._context_reason(
            actor,
            decision=decision,
            action=action,
            topic=topic,
            repeated=repeated,
        )
        return (
            reason.replace(" Он помнит прежний разговор", " В памяти сохранился прежний разговор")
            .replace("нынешним этапом его пути", "нынешним этапом пути")
            .replace("Он сохраняет саму тему", "Сама тема сохраняется")
            .replace("ответ вместо него", "ответ за отсутствующего человека")
        )

    def unrealized_free_other_result(self, player_id: str, decision: dict[str, Any]) -> WorldResult:
        result = super().unrealized_free_other_result(player_id, decision)
        narrative = (
            result.narrative.replace(
                "Другой отказался от предложенной формы.",
                "Ответом стал отказ от предложенной формы.",
            )
            .replace(
                "Другой предложил иной способ контакта.",
                "В ответ был предложен иной способ контакта.",
            )
            .replace(
                "Другой сейчас находится на собственной дороге.",
                "Ответ сейчас невозможен: человек находится на собственной дороге.",
            )
        )
        return replace(result, narrative=narrative)

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
        excerpt = decision.get("action_excerpt", self._short_action(decision["action"]))
        if kind == "accepted":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.08)
            text = f"{actor['name']} свободно принимает конкретное предложение «{excerpt}». {reason}"
        elif kind == "accepted_space":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.03)
            text = f"{actor['name']} принимает оставленное пространство. {reason}"
        elif kind == "alternative":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.015)
            actor["refusals_count"] += 1
            alternatives = list(actor["alternatives"])
            recent = {
                item.get("response_fingerprint")
                for item in actor.get("dialogue_memory", [])[-RECENT_TEXT_LIMIT:]
            }
            available = [
                item for item in alternatives if self._memory_fingerprint(item) not in recent
            ] or alternatives
            alternative = self._free_pick(
                store,
                available,
                player_id,
                actor["handle"],
                world_turn,
                decision["fingerprint"],
                "context-alternative",
            )
            text = f"{actor['name']} не принимает предложенный способ. {reason} Вместо него: {alternative}"
        elif kind == "refused":
            actor["refusals_count"] += 1
            actor["distance"] += 1
            text = f"{actor['name']} отвечает отказом на предложение «{excerpt}». {reason}"
        else:
            text = f"{actor['name']} находится на собственной дороге. {reason}"
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
                "voice_contract": VOICE_CONTRACT,
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
                    actor["return_context"] = (
                        f"возвращение после линии: {previous_context}; нынешнее призвание: {actor['calling']}"
                    )
                    text = (
                        f"{actor['name']} возвращается после продолжения линии: {previous_context}. "
                        f"Теперь: {actor['stages'][actor['stage_index']]}. Возвращение сохраняет память об уходе, "
                        "но не становится наградой, согласием или прощением."
                    )
                    events.append({"kind": "return", "handle": handle, "text": text, "priority": 1})
                    actor_changed_this_turn.add(handle)
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": "return",
                        "text": text,
                        "departure_context": previous_context,
                        "voice_contract": VOICE_CONTRACT,
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
                        f"{actor['name']} {actor['stages'][target]}. Продолжение связано с призванием "
                        f"«{actor['calling']}» и не возникает как награда или задание игрока."
                    )
                    kind = "path"
                    priority = 3
                    if target == 3:
                        actor["status"] = "away"
                        actor["away_reason"] = "own_path"
                        actor["left_world_turn"] = world_turn
                        actor["departures"] += 1
                        actor["departure_context"] = (
                            f"{actor['stages'][target]} ради призвания «{actor['calling']}»"
                        )
                        kind = "departure"
                        priority = 1
                        text += (
                            f" {actor['name']} уходит, чтобы продолжить: {actor['departure_context']}. "
                            "Уход не обещает возвращения."
                        )
                    events.append({"kind": kind, "handle": handle, "text": text, "priority": priority})
                    actor_changed_this_turn.add(handle)
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": kind,
                        "text": text,
                        "calling": actor["calling"],
                        "stage_index": target,
                        "voice_contract": VOICE_CONTRACT,
                    }])[-HISTORY_LIMIT:]
                    self._record_other_graph_event(owner_id, actor, kind=kind, text=text, world_turn=world_turn)

            if actor["stage_index"] >= 4 and actor["calling_changes"] == 0:
                change_gate = self._free_number(store, owner_id, handle, world_turn, "remembered-calling") % 100
                if change_gate < 21:
                    new_calling = self._free_pick(
                        store, actor["new_callings"], owner_id, handle, world_turn, "calling"
                    )
                    old_calling = actor["calling"]
                    actor["calling"] = new_calling
                    actor["calling_changes"] += 1
                    actor["initiative_cooldown_until"] = world_turn + 4
                    text = (
                        f"{actor['name']} завершает линию прежнего призвания «{old_calling}» и выбирает: {new_calling}. "
                        "Память о старой роли сохраняется, но перестаёт определять будущие ответы."
                    )
                    events.append({"kind": "calling_changed", "handle": handle, "text": text, "priority": 0})
                    actor_changed_this_turn.add(handle)
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": "calling_changed",
                        "text": text,
                        "old_calling": old_calling,
                        "new_calling": new_calling,
                        "voice_contract": VOICE_CONTRACT,
                    }])[-HISTORY_LIMIT:]
                    self._record_other_graph_event(
                        owner_id, actor, kind="calling_changed", text=text, world_turn=world_turn
                    )

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
                    key=lambda actor: self._free_number(
                        store, owner_id, actor["handle"], world_turn, "initiative-actor"
                    ),
                )
                actor = next(
                    (candidate for candidate in ordered if self._eligible_initiative_texts(candidate, profile)),
                    None,
                )
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
                        f"{text} Инициатива возникает из текущего призвания «{actor['calling']}»; "
                        f"следующая инициатива этого Другого не появится раньше хода {actor['initiative_cooldown_until']}."
                    )
                    actor["history"] = (actor["history"] + [{
                        "world_turn": world_turn,
                        "kind": "initiative",
                        "text": contextual,
                        "calling": actor["calling"],
                        "cooldown_until": actor["initiative_cooldown_until"],
                        "voice_contract": VOICE_CONTRACT,
                    }])[-HISTORY_LIMIT:]
                    events.append({
                        "kind": "initiative",
                        "handle": actor["handle"],
                        "text": contextual,
                        "priority": 2,
                    })
                    self._record_other_graph_event(
                        owner_id, actor, kind="initiative", text=contextual, world_turn=world_turn
                    )
        return events

    def _actor_graph_payload(self, actor: dict[str, Any]) -> dict[str, Any]:
        payload = super()._actor_graph_payload(actor)
        payload.update({
            "voice_contract": actor.get("voice_contract", VOICE_CONTRACT),
            "voice_contract_version": __version__,
        })
        return payload

    def free_other_state(self, player_id: str | None = None) -> dict[str, Any]:
        state = super().free_other_state(player_id)
        state["remembering_voice_version"] = __version__
        state["voice_contract"] = {
            "id": VOICE_CONTRACT,
            "infers_gender_from_name": False,
            "uses_stable_present_or_impersonal_ru": True,
        }
        return state

    def verify_free_other_state(self) -> tuple[bool, int, int, str | None]:
        valid, players, others, error = super().verify_free_other_state()
        if not valid:
            return valid, players, others, error
        store = self._free_store()
        for player_id, profile in store.get("players", {}).items():
            self._upgrade_profile(profile, int(store.get("world_turn", 0)))
            if profile.get("voice_contract_version") != __version__:
                return False, players, others, f"voice contract missing: {player_id}"
            for handle, actor in profile.get("others", {}).items():
                if actor.get("voice_contract") != VOICE_CONTRACT:
                    return False, players, others, f"actor voice contract missing: {player_id}/{handle}"
        self._write_json(self.free_other_path, store)
        return True, players, others, None
