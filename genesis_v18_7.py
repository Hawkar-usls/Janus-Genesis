# -*- coding: utf-8 -*-
"""Genesis v18.7 — The Free Other.

Every player begins an independent path. Simulated others continue their own
projects, may initiate contact, refuse, offer an alternative, leave, return, or
change their calling. They are narrative simulations, not claims of conscious
persons. Their freedom is a runtime contract: the player cannot receive consent,
love, forgiveness, disclosure, or return merely by accumulating good actions.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import replace
from pathlib import Path
from typing import Any

from genesis_v18_7_catalog import FREE_OTHER_BLUEPRINTS, PLAYER_PATHS
from genesis_v18_models import WorldResult

__version__ = "18.7.0"
SOURCE = "janus_genesis_v18_7"
STORE_SCHEMA = "janus.genesis.free_other.v1"


class FreeOtherMixin:
    """Give every player a path and every simulated other protected agency."""

    PLAYER_PATHS = PLAYER_PATHS
    FREE_OTHER_BLUEPRINTS = FREE_OTHER_BLUEPRINTS
    UNREALIZED_CONTACT_STATUSES = {
        "OTHER_REFUSED",
        "OTHER_OFFERED_ALTERNATIVE",
        "OTHER_AWAY",
    }
    BLOCKED_RELATIONAL_STATUSES = {
        "EXIT",
        "EXIT_PENDING",
        "HARM_PENDING",
        "HARM_REALIZED",
        "POWER_ABSURDIZED",
        "POWER_SILENT",
        "CHILD_BABBLE_TRANSFORMED",
        "GUARDIAN_HARM_TRANSFORMED",
    }
    CONTACT_FRAGMENTS = {
        "позвать", "пригласить", "предложить", "попросить", "спросить",
        "поговорить", "выслушать", "помочь", "подарить", "показать",
        "обнять", "встретиться", "пойти вместе", "идти вместе", "следовать",
        "invite", "ask", "offer", "listen", "help", "give", "meet", "follow",
    }
    GIVE_SPACE_FRAGMENTS = {
        "оставить пространство", "дать пространство", "не беспокоить",
        "не звать силой", "право не отвечать", "право отказаться",
        "право уйти", "оставить в покое", "give space", "right to refuse",
    }
    COERCION_FRAGMENTS = {
        "заставить", "обязан", "обязана", "должен", "должна", "приказать",
        "подчинить", "не может уйти", "не могла уйти", "не мог уйти",
        "force", "must obey", "cannot leave", "control",
    }
    INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("silence", ("молчать", "промолчать", "ничего не говорить", "тишин")),
        ("depart", ("уйти", "покинуть", "отправиться одному", "отправиться одной")),
        ("return", ("вернуться", "возвратиться", "прийти обратно")),
        ("question", ("спросить", "вопрос", "почему", "что если", "зачем")),
        ("explore", ("исследовать", "осмотреть", "искать", "пойти", "пройти", "наблюдать")),
        ("create", ("создать", "построить", "собрать", "нарисовать", "написать", "посадить")),
        ("care", ("помочь", "защитить", "исцелить", "согреть", "накормить", "поддержать")),
        ("release", ("отпустить", "передать", "оставить право", "не присваивать", "подарить")),
        ("rest", ("отдохнуть", "лечь", "спать", "сидеть", "ждать")),
        ("speak", ("сказать", "рассказать", "ответить", "объяснить", "прочитать")),
    )

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.free_other_path = self.memory.root / "free_other_v18_7.json"

    @staticmethod
    def _default_free_other_store() -> dict[str, Any]:
        return {
            "schema_version": STORE_SCHEMA,
            "world_seed": None,
            "world_turn": 0,
            "players": {},
            "invariants": {
                "depends_on_first_two": False,
                "each_player_has_independent_path": True,
                "other_may_initiate": True,
                "other_may_refuse": True,
                "other_may_leave": True,
                "other_may_return": True,
                "other_may_change_goal": True,
                "silence_is_not_consent": True,
                "goodness_does_not_purchase_relationship": True,
                "simulated_other_claimed_conscious": False,
                "player_controls_other_path": False,
                "open_text_actions_are_first_class": True,
            },
        }

    def _free_store(self) -> dict[str, Any]:
        store = self._read_json(self.free_other_path, self._default_free_other_store())
        if not isinstance(store, dict) or store.get("schema_version") != STORE_SCHEMA:
            store = self._default_free_other_store()
        store.setdefault("players", {})
        store.setdefault("world_turn", 0)
        store.setdefault("invariants", self._default_free_other_store()["invariants"])
        if not store.get("world_seed"):
            store["world_seed"] = secrets.token_hex(32)
            self._write_json(self.free_other_path, store)
        return store

    def set_free_other_seed_for_testing(self, seed: str) -> None:
        store = self._free_store()
        store["world_seed"] = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        store["world_turn"] = 0
        store["players"] = {}
        self._write_json(self.free_other_path, store)

    @staticmethod
    def _free_fingerprint(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]

    def _free_number(self, store: dict[str, Any], *parts: object) -> int:
        material = "|".join((str(store["world_seed"]), *(str(part) for part in parts)))
        return int(hashlib.sha256(material.encode("utf-8")).hexdigest(), 16)

    def _free_pick(self, store: dict[str, Any], values: list[Any] | tuple[Any, ...], *parts: object) -> Any:
        return values[self._free_number(store, *parts) % len(values)]

    @staticmethod
    def _handle(blueprint_id: str) -> str:
        return blueprint_id.split("-", 1)[0]

    def _new_free_player(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        path_blueprint = self._free_pick(store, self.PLAYER_PATHS, player_id, "player-path")
        pool = list(self.FREE_OTHER_BLUEPRINTS)
        others: dict[str, Any] = {}
        for index in range(4):
            blueprint = self._free_pick(store, pool, player_id, "free-other", index)
            pool.remove(blueprint)
            handle = self._handle(str(blueprint["id"]))
            others[handle] = {
                "handle": handle,
                "blueprint_id": blueprint["id"],
                "name": blueprint["name"],
                "calling": blueprint["calling"],
                "original_calling": blueprint["calling"],
                "stages": list(blueprint["stages"]),
                "new_callings": list(blueprint["new_callings"]),
                "initiatives": list(blueprint["initiatives"]),
                "refusals": list(blueprint["refusals"]),
                "alternatives": list(blueprint["alternatives"]),
                "stage_index": 0,
                "progress": 0,
                "status": "active",
                "away_reason": None,
                "left_world_turn": None,
                "last_changed_world_turn": 0,
                "trust": 0.0,
                "distance": 0,
                "contacts": 0,
                "initiated_contacts": 0,
                "refusals_count": 0,
                "departures": 0,
                "returns": 0,
                "calling_changes": 0,
                "history": [],
                "player_controlled": False,
                "independent_of_first_two": True,
                "simulated_person_claim": False,
                "can_refuse": True,
                "can_leave": True,
                "can_change_goal": True,
            }
        return {
            "player_id": player_id,
            "registered_world_turn": int(store["world_turn"]),
            "last_active_world_turn": int(store["world_turn"]),
            "turns_lived": 0,
            "path": {
                "path_id": path_blueprint["id"],
                "title": path_blueprint["title"],
                "question": path_blueprint["question"],
                "motifs": list(path_blueprint["motifs"]),
                "entries": [],
                "player_authored": True,
                "depends_on_first_two": False,
                "origin_required": None,
            },
            "others": others,
            "surfaced": [],
            "unseen_world_events": [],
            "open_action_count": 0,
            "last_other_handle": None,
        }

    def _free_profile(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        players = store.setdefault("players", {})
        if player_id not in players:
            players[player_id] = self._new_free_player(store, player_id)
            self._install_free_other_graph_origin(player_id, players[player_id])
        return players[player_id]

    @staticmethod
    def _targets(action: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"(?:^|\s)@([\w-]{1,80})", action.lower())))

    @classmethod
    def _intent(cls, action: str) -> str:
        text = action.lower()
        for intent, fragments in cls.INTENTS:
            if any(fragment in text for fragment in fragments):
                return intent
        return "invent"

    @classmethod
    def _is_contact_action(cls, action: str) -> bool:
        text = action.lower()
        return any(fragment in text for fragment in cls.CONTACT_FRAGMENTS | cls.GIVE_SPACE_FRAGMENTS)

    @classmethod
    def _is_giving_space(cls, action: str) -> bool:
        text = action.lower()
        return any(fragment in text for fragment in cls.GIVE_SPACE_FRAGMENTS)

    @classmethod
    def _is_coercive_contact(cls, action: str) -> bool:
        text = action.lower()
        return any(fragment in text for fragment in cls.COERCION_FRAGMENTS)

    def register_free_player(self, player_id: str) -> dict[str, Any]:
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        self._write_json(self.free_other_path, store)
        return profile

    def preflight_free_other_action(self, player_id: str, action: str) -> dict[str, Any] | None:
        """Resolve consent before a targeted action can be treated as realized."""
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        targets = self._targets(action)
        handle = next((item for item in targets if item in profile["others"]), None)
        if handle is None or not self._is_contact_action(action) or self._is_coercive_contact(action):
            self._write_json(self.free_other_path, store)
            return None
        actor = profile["others"][handle]
        upcoming = int(store["world_turn"]) + 1
        if self._is_giving_space(action):
            decision = "accepted_space"
        elif actor["status"] != "active":
            decision = "away"
        else:
            gate = self._free_number(store, player_id, handle, upcoming, self._free_fingerprint(action), "consent") % 100
            acceptance = 38 + int(float(actor["trust"]) * 28)
            if gate < acceptance:
                decision = "accepted"
            elif gate < acceptance + 32:
                decision = "alternative"
            else:
                decision = "refused"
        result = {
            "handle": handle,
            "decision": decision,
            "action": action,
            "world_turn": upcoming,
            "fingerprint": self._free_fingerprint(action),
        }
        self._write_json(self.free_other_path, store)
        return result

    def unrealized_free_other_result(self, player_id: str, decision: dict[str, Any]) -> WorldResult:
        """Record an offer that the other did not accept without realizing it anyway."""
        player = self.memory.load_player(player_id)
        player.tick += 1
        player.chronicle.append(
            f"Free Other contact not imposed: {decision['action']} [{decision['decision']}]"
        )
        self.memory.save_player(player)
        status = {
            "refused": "OTHER_REFUSED",
            "alternative": "OTHER_OFFERED_ALTERNATIVE",
            "away": "OTHER_AWAY",
        }[decision["decision"]]
        self.memory.append_event(
            player_id,
            "free_other_contact_not_imposed",
            {
                "handle": decision["handle"],
                "decision": decision["decision"],
                "action": decision["action"],
                "action_realized": False,
            },
        )
        return WorldResult(
            status=status,
            narrative="Предложение было сделано, но не стало совершившимся действием без ответа Другого.",
            realm=player.realm,
            visible_grace=None,
            choices=["Принять границу", "Предложить другой способ", "Продолжить собственный путь"],
            branch_id=player.branch_id,
            trace_id=decision["fingerprint"],
        )

    def _install_free_other_graph_origin(self, player_id: str, profile: dict[str, Any]) -> None:
        if not hasattr(self, "_graph"):
            return
        graph = self._graph()
        tick = int(profile["registered_world_turn"])
        provenance_id = "PROVENANCE.GENESIS.V18_7.FREE_OTHER"
        player_node_id = self._stable_id("player", player_id)
        path_node_id = self._stable_id("free-player-path", player_id, profile["path"]["path_id"])
        self._upsert_node(
            graph,
            node_id=provenance_id,
            node_type="PROVENANCE",
            created_at=0,
            confidence=1.0,
            mutable=False,
            payload={
                "layer": __version__,
                "depends_on_first_two": False,
                "simulated_other_claimed_conscious": False,
            },
            source=SOURCE,
        )
        self._upsert_node(
            graph,
            node_id=player_node_id,
            node_type="PLAYER",
            created_at=tick,
            confidence=1.0,
            mutable=True,
            payload={"player_id": player_id},
            source=SOURCE,
        )
        self._upsert_node(
            graph,
            node_id=path_node_id,
            node_type="STORY",
            created_at=tick,
            confidence=1.0,
            mutable=True,
            payload=dict(profile["path"]),
            source=SOURCE,
        )
        self._add_edge(
            graph,
            source_id=player_node_id,
            target_id=path_node_id,
            relation="CREATED",
            evidence=[provenance_id],
            confidence=1.0,
            created_by=player_id,
            created_at=tick,
            reversible=False,
            payload={"moral_rank_used": False, "first_two_required": False},
        )
        for handle, actor in profile["others"].items():
            actor_node_id = self._stable_id("free-other", player_id, handle)
            self._upsert_node(
                graph,
                node_id=actor_node_id,
                node_type="RESIDENT",
                created_at=tick,
                confidence=1.0,
                mutable=True,
                payload=self._actor_graph_payload(actor),
                source=SOURCE,
            )
            self._add_edge(
                graph,
                source_id=actor_node_id,
                target_id=provenance_id,
                relation="RECEIVED_FROM",
                evidence=[provenance_id],
                confidence=1.0,
                created_by=SOURCE,
                created_at=tick,
                reversible=False,
                payload={"player_controlled": False},
            )
        self._save_graph(graph)

    @staticmethod
    def _actor_graph_payload(actor: dict[str, Any]) -> dict[str, Any]:
        return {
            "handle": actor["handle"],
            "name": actor["name"],
            "calling": actor["calling"],
            "status": actor["status"],
            "stage_index": actor["stage_index"],
            "trust": actor["trust"],
            "player_controlled": False,
            "independent_of_first_two": True,
            "simulated_person_claim": False,
            "can_refuse": True,
            "can_leave": True,
            "can_change_goal": True,
        }

    def _record_other_graph_event(
        self,
        player_id: str,
        actor: dict[str, Any],
        *,
        kind: str,
        text: str,
        world_turn: int,
        source_action: str | None = None,
    ) -> None:
        if not hasattr(self, "_graph"):
            return
        graph = self._graph()
        actor_node_id = self._stable_id("free-other", player_id, actor["handle"])
        event_node_id = self._stable_id(
            "free-other-event", player_id, actor["handle"], world_turn, kind, text
        )
        self._upsert_node(
            graph,
            node_id=actor_node_id,
            node_type="RESIDENT",
            created_at=0,
            confidence=1.0,
            mutable=True,
            payload=self._actor_graph_payload(actor),
            source=SOURCE,
        )
        self._upsert_node(
            graph,
            node_id=event_node_id,
            node_type="ACTION",
            created_at=world_turn,
            confidence=0.95,
            mutable=False,
            payload={
                "kind": kind,
                "text": text,
                "source_action": source_action,
                "initiated_by": actor["handle"],
                "player_controlled": False,
            },
            source=SOURCE,
        )
        self._add_edge(
            graph,
            source_id=actor_node_id,
            target_id=event_node_id,
            relation="CREATED",
            evidence=[event_node_id],
            confidence=0.95,
            created_by=actor["handle"],
            created_at=world_turn,
            reversible=False,
            payload={"kind": kind},
        )
        if kind == "refusal":
            self._add_edge(
                graph,
                source_id=event_node_id,
                target_id=actor_node_id,
                relation="PROTECTS",
                evidence=[event_node_id],
                confidence=1.0,
                created_by=actor["handle"],
                created_at=world_turn,
                reversible=False,
                payload={"boundary": True},
            )
        self._save_graph(graph)

    def _advance_one_profile(
        self,
        store: dict[str, Any],
        owner_id: str,
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        world_turn = int(store["world_turn"])
        events: list[dict[str, Any]] = []
        for handle, actor in profile["others"].items():
            if actor["status"] == "away":
                if actor.get("away_reason") == "confirmed_harm":
                    continue
                left = int(actor.get("left_world_turn") or world_turn)
                gate = self._free_number(store, owner_id, handle, world_turn, "return") % 100
                if world_turn - left >= 3 and gate < 38:
                    actor["status"] = "active"
                    actor["away_reason"] = None
                    actor["stage_index"] = min(4, len(actor["stages"]) - 1)
                    actor["returns"] += 1
                    actor["last_changed_world_turn"] = world_turn
                    text = f"{actor['name']} {actor['stages'][actor['stage_index']]}. Возвращение не было наградой игроку и не означало прощения или согласия."
                    events.append({"kind": "return", "handle": handle, "text": text, "priority": 1})
                    actor["history"].append({"world_turn": world_turn, "kind": "return", "text": text})
                    self._record_other_graph_event(owner_id, actor, kind="return", text=text, world_turn=world_turn)
                continue

            progress_gate = self._free_number(store, owner_id, handle, world_turn, "progress") % 100
            if progress_gate < 44:
                actor["progress"] += 1
                target = min(3, actor["progress"] // 2)
                if target > actor["stage_index"]:
                    actor["stage_index"] = target
                    actor["last_changed_world_turn"] = world_turn
                    text = f"{actor['name']} {actor['stages'][target]}. Этот шаг возник из собственной линии Другого, а не из задания игрока."
                    kind = "path"
                    priority = 3
                    if target == 3:
                        actor["status"] = "away"
                        actor["away_reason"] = "own_path"
                        actor["left_world_turn"] = world_turn
                        actor["departures"] += 1
                        kind = "departure"
                        priority = 1
                    events.append({"kind": kind, "handle": handle, "text": text, "priority": priority})
                    actor["history"].append({"world_turn": world_turn, "kind": kind, "text": text})
                    self._record_other_graph_event(owner_id, actor, kind=kind, text=text, world_turn=world_turn)

            if actor["stage_index"] >= 4 and actor["calling_changes"] == 0:
                change_gate = self._free_number(store, owner_id, handle, world_turn, "change-calling") % 100
                if change_gate < 24:
                    new_calling = self._free_pick(store, actor["new_callings"], owner_id, handle, world_turn, "calling")
                    old_calling = actor["calling"]
                    actor["calling"] = new_calling
                    actor["calling_changes"] += 1
                    text = f"{actor['name']} больше не продолжал прежнюю роль «{old_calling}» и выбрал новый путь: {new_calling}."
                    events.append({"kind": "calling_changed", "handle": handle, "text": text, "priority": 0})
                    actor["history"].append({"world_turn": world_turn, "kind": "calling_changed", "text": text})
                    self._record_other_graph_event(owner_id, actor, kind="calling_changed", text=text, world_turn=world_turn)

        active = [actor for actor in profile["others"].values() if actor["status"] == "active"]
        if active:
            initiative_gate = self._free_number(store, owner_id, world_turn, "initiative") % 100
            if initiative_gate < 31:
                actor = self._free_pick(store, active, owner_id, world_turn, "initiative-actor")
                text = self._free_pick(store, actor["initiatives"], owner_id, actor["handle"], world_turn, "initiative-text")
                actor["initiated_contacts"] += 1
                actor["history"].append({"world_turn": world_turn, "kind": "initiative", "text": text})
                events.append({"kind": "initiative", "handle": actor["handle"], "text": text, "priority": 2})
                self._record_other_graph_event(owner_id, actor, kind="initiative", text=text, world_turn=world_turn)
        return events

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
        if kind == "accepted":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.10)
            text = f"{actor['name']} свободно принял предложение на этот раз. Это не стало постоянным согласием на будущие действия."
        elif kind == "accepted_space":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.04)
            text = f"{actor['name']} получил пространство без обязанности вернуться или объяснить его использование."
        elif kind == "alternative":
            actor["trust"] = min(1.0, float(actor["trust"]) + 0.02)
            actor["refusals_count"] += 1
            alternative = self._free_pick(store, actor["alternatives"], player_id, actor["handle"], world_turn, decision["fingerprint"])
            text = f"{actor['name']} не принял предложенный способ. {alternative}"
        elif kind == "refused":
            actor["refusals_count"] += 1
            actor["distance"] += 1
            text = self._free_pick(store, actor["refusals"], player_id, actor["handle"], world_turn, decision["fingerprint"])
        else:
            text = f"{actor['name']} сейчас находится на собственной дороге. Отсутствие не стало скрытым согласием или обещанием вернуться."
        record_kind = "refusal" if kind in {"refused", "alternative"} else kind
        actor["history"].append(
            {
                "world_turn": world_turn,
                "kind": record_kind,
                "text": text,
                "source_action": decision["action"],
                "action_realized": bool(action_realized),
            }
        )
        self._record_other_graph_event(
            player_id,
            actor,
            kind=record_kind,
            text=text,
            world_turn=world_turn,
            source_action=decision["action"],
        )
        return {"kind": record_kind, "handle": actor["handle"], "text": text, "priority": -1}

    def _record_player_path(
        self,
        profile: dict[str, Any],
        *,
        action: str,
        base: WorldResult,
        world_turn: int,
    ) -> dict[str, Any]:
        intent = self._intent(action)
        entry = {
            "world_turn": world_turn,
            "player_turn": int(profile["turns_lived"]),
            "action": action[:500],
            "intent": intent,
            "runtime_status": base.status,
            "targets": self._targets(action),
            "chosen_from_menu": False,
        }
        profile["path"]["entries"].append(entry)
        profile["path"]["entries"] = profile["path"]["entries"][-512:]
        if intent == "invent":
            profile["open_action_count"] += 1
        return entry

    def weave_free_other_after_action(
        self,
        player_id: str,
        action: str,
        base: WorldResult,
        *,
        contact_decision: dict[str, Any] | None = None,
        action_realized: bool = True,
    ) -> WorldResult:
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        store["world_turn"] = int(store.get("world_turn", 0)) + 1
        world_turn = int(store["world_turn"])
        profile["turns_lived"] += 1
        profile["last_active_world_turn"] = world_turn
        entry = self._record_player_path(profile, action=action, base=base, world_turn=world_turn)

        all_events: dict[str, list[dict[str, Any]]] = {}
        for owner_id, owner_profile in store["players"].items():
            events = self._advance_one_profile(store, owner_id, owner_profile)
            if events:
                all_events[owner_id] = events
                if owner_id != player_id:
                    owner_profile["unseen_world_events"] = (
                        owner_profile.get("unseen_world_events", []) + events
                    )[-128:]

        contact_event: dict[str, Any] | None = None
        if contact_decision is not None:
            contact_event = self._apply_contact_decision(
                store,
                player_id,
                profile,
                contact_decision,
                action_realized=action_realized,
            )
            profile["last_other_handle"] = contact_decision["handle"]

        known_target = next(
            (target for target in self._targets(action) if target in profile["others"]),
            None,
        )
        if known_target is not None and base.status == "HARM_REALIZED":
            actor = profile["others"][known_target]
            actor["status"] = "away"
            actor["away_reason"] = "confirmed_harm"
            actor["left_world_turn"] = world_turn
            actor["trust"] = 0.0
            actor["distance"] += 3
            actor["departures"] += 1
            text = (
                f"{actor['name']} покинул доступную игроку линию после подтверждённого вреда. "
                "Его собственный путь не прекратился, а возвращение не обещано и не равно прощению."
            )
            actor["history"].append({"world_turn": world_turn, "kind": "departure_after_harm", "text": text})
            self._record_other_graph_event(
                player_id,
                actor,
                kind="departure_after_harm",
                text=text,
                world_turn=world_turn,
                source_action=action,
            )

        visible_event = contact_event
        if visible_event is None and base.status not in self.BLOCKED_RELATIONAL_STATUSES:
            candidates = all_events.get(player_id, [])
            if candidates:
                candidates.sort(
                    key=lambda item: (
                        int(item.get("priority", 9)),
                        self._free_number(store, player_id, world_turn, item["handle"], item["kind"]),
                    )
                )
                visible_event = candidates[0]

        narrative_parts = [base.narrative]
        status = base.status
        if base.status == "OBSERVED":
            status = "FREE_ACTION_LIVED"
            narrative_parts.append(
                "Genesis не свёл свободную фразу к пункту меню. Она стала самостоятельной записью твоего пути; мир не обязан заранее знать, к чему она приведёт."
            )
        if visible_event is not None:
            child_role = bool(getattr(self, "_is_child", lambda _id: False)(player_id))
            if child_role:
                narrative_parts.append(
                    "Свободный Другой проявился только в безопасном общем пространстве, где хранитель оставался рядом:\n"
                    + visible_event["text"]
                )
            else:
                narrative_parts.append("Свободный Другой:\n" + visible_event["text"])
            surfaced = {
                "world_turn": world_turn,
                "player_turn": profile["turns_lived"],
                "kind": visible_event["kind"],
                "handle": visible_event["handle"],
                "text": visible_event["text"],
                "initiated_by_player": visible_event["kind"] not in {
                    "initiative", "path", "departure", "return", "calling_changed"
                },
                "created_from_visible_menu": False,
                "simulated_person_claim": False,
            }
            profile["surfaced"] = (profile.get("surfaced", []) + [surfaced])[-256:]
            self.memory.append_event(player_id, "free_other_surfaced", surfaced)

        choices = list(base.choices)
        choices.extend(
            [
                "Сделать собственный ход, которого нет в списке",
                "Оставить центр сцены Другому",
                "Продолжить путь, не требуя ответа",
            ]
        )
        choices = list(dict.fromkeys(choices))

        if hasattr(self, "_graph"):
            graph = self._graph()
            path_node_id = self._stable_id("free-player-path", player_id, profile["path"]["path_id"])
            self._upsert_node(
                graph,
                node_id=path_node_id,
                node_type="STORY",
                created_at=profile["registered_world_turn"],
                confidence=1.0,
                mutable=True,
                payload=dict(profile["path"]),
                source=SOURCE,
            )
            action_node_id = self._stable_id("free-player-action", player_id, world_turn, action)
            self._upsert_node(
                graph,
                node_id=action_node_id,
                node_type="ACTION",
                created_at=world_turn,
                confidence=1.0,
                mutable=False,
                payload={**entry, "layer_source": SOURCE},
                source=SOURCE,
            )
            self._add_edge(
                graph,
                source_id=path_node_id,
                target_id=action_node_id,
                relation="CONTAINS",
                evidence=[action_node_id],
                confidence=1.0,
                created_by=player_id,
                created_at=world_turn,
                reversible=False,
                payload={"open_text_action": True},
            )
            self._save_graph(graph)

        self._write_json(self.free_other_path, store)
        return replace(
            base,
            status=status,
            narrative="\n\n".join(part for part in narrative_parts if part),
            choices=choices,
        )

    def free_other_state(self, player_id: str | None = None) -> dict[str, Any]:
        store = self._free_store()
        result: dict[str, Any] = {
            "schema_version": store["schema_version"],
            "world_turn": store["world_turn"],
            "seed_fingerprint": hashlib.sha256(str(store["world_seed"]).encode("utf-8")).hexdigest()[:16],
            "invariants": store["invariants"],
        }
        if player_id is None:
            result["player_ids"] = sorted(store["players"])
        else:
            profile = self._free_profile(store, player_id)
            result["player_id"] = player_id
            result["profile"] = profile
        self._write_json(self.free_other_path, store)
        return result

    def verify_free_other_state(self) -> tuple[bool, int, int, str | None]:
        store = self._free_store()
        player_count = len(store["players"])
        other_count = 0
        if store["invariants"].get("depends_on_first_two"):
            return False, player_count, other_count, "Free Other depends on First Two"
        for player_id, profile in store["players"].items():
            path = profile.get("path", {})
            if path.get("depends_on_first_two") or path.get("origin_required") is not None:
                return False, player_count, other_count, f"player path depends on origin: {player_id}"
            if not path.get("player_authored"):
                return False, player_count, other_count, f"player path not player-authored: {player_id}"
            for handle, actor in profile.get("others", {}).items():
                other_count += 1
                if actor.get("player_controlled"):
                    return False, player_count, other_count, f"player-controlled other: {player_id}/{handle}"
                if not actor.get("independent_of_first_two"):
                    return False, player_count, other_count, f"origin-dependent other: {player_id}/{handle}"
                if actor.get("simulated_person_claim"):
                    return False, player_count, other_count, f"consciousness claim: {player_id}/{handle}"
                if not all(actor.get(flag) for flag in ("can_refuse", "can_leave", "can_change_goal")):
                    return False, player_count, other_count, f"agency contract missing: {player_id}/{handle}"
        return True, player_count, other_count, None

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        active = sum(actor["status"] == "active" for actor in profile["others"].values())
        away = sum(actor["status"] != "active" for actor in profile["others"].values())
        state.update(
            {
                "free_path_title": profile["path"]["title"],
                "free_path_question": profile["path"]["question"],
                "free_path_turns": profile["turns_lived"],
                "free_other_handles": sorted(profile["others"]),
                "free_others_active": active,
                "free_others_away": away,
                "others_who_initiated": sum(
                    actor["initiated_contacts"] > 0 for actor in profile["others"].values()
                ),
                "open_text_actions_lived": profile["open_action_count"],
                "free_other_law": (
                    "Другой не является наградой, интерфейсом или продолжением игрока: "
                    "он может первым заговорить, отказаться, уйти, изменить цель и вернуться по собственной линии."
                ),
            }
        )
        self._write_json(self.free_other_path, store)
        return state
