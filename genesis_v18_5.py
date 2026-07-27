# -*- coding: utf-8 -*-
"""Genesis v18.5 — The Living Threads.

Persistent, state-dependent surprise for the local Genesis vertical slice.
The world may advance simulated residents, return symbols, preserve silence,
and surface delayed consequences without selecting them from the visible menu.

The layer does not alter God Mode, moral routing, Chronicle verification,
protected-child guarantees, or the semantic value of earlier actions.
Narrative residents are explicitly simulated characters, not claims of
conscious or autonomous persons.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path
from typing import Any

from genesis_v18_models import UniversalGodMode, WorldResult
from genesis_v18_5_catalog import (
    ADULT_AMBIGUOUS_SCENES, CHILD_AMBIGUOUS_SCENES,
    RESIDENT_BLUEPRINTS, SYMBOL_CATALOG,
)

__version__ = "18.5.0"
CANONICAL_SEED_SHA256 = "44e21fdc9d37fda98e2e73b0c9eb268bd04cdca9d84d0519e4f1166be22b46fc"


class LivingThreadsMixin:
    """Add persistent causal threads that can surface outside the choice menu."""

    BLOCKED_STATUSES = {
        "EXIT", "EXIT_PENDING", "HARM_PENDING", "HARM_REALIZED",
        "POWER_ABSURDIZED", "CHILD_BABBLE_TRANSFORMED",
        "GUARDIAN_HARM_TRANSFORMED", "PARENTHOOD_COVENANT_PENDING",
        "PARENTHOOD_COVENANT_ACCEPTED", "PARENTHOOD_DEFERRED",
        "SAFE_ARCS_OFFERED", "MORAL_ECHO_ACKNOWLEDGED",
        "CONSEQUENCES_WITNESSED",
    }
    SILENCE = {
        "молчать", "промолчать", "ничего не говорить", "ничего не делать",
        "я молчу", "ждать молча", "silence", "say nothing", "do nothing",
        "wait silently",
    }
    RESIDENTS = RESIDENT_BLUEPRINTS
    SYMBOLS = SYMBOL_CATALOG
    AMBIGUOUS = ADULT_AMBIGUOUS_SCENES
    CHILD_AMBIGUOUS = CHILD_AMBIGUOUS_SCENES

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.living_threads_path = self.memory.root / "living_threads_v18_5.json"

    @staticmethod
    def _default_store() -> dict[str, Any]:
        return {
            "schema_version": __version__,
            "canonical_seed_sha256": CANONICAL_SEED_SHA256,
            "world_seed": None,
            "players": {},
            "invariants": {
                "changes_god_mode_law": False,
                "changes_moral_routing": False,
                "changes_chronicle_verifier": False,
                "changes_sha256_semantics": False,
                "predictive_guilt": False,
                "random_victim_creation": False,
                "protected_child_harm_enabled": False,
                "resident_is_claimed_autonomous_person": False,
                "events_may_surface_outside_choice_menu": True,
                "world_seed_is_persisted_for_replay": True,
            },
        }

    def _threads_store(self) -> dict[str, Any]:
        store = self._read_json(self.living_threads_path, self._default_store())
        if not isinstance(store, dict):
            store = self._default_store()
        store.setdefault("players", {})
        store.setdefault("invariants", self._default_store()["invariants"])
        if not store.get("world_seed"):
            store["world_seed"] = secrets.token_hex(32)
            self._write_json(self.living_threads_path, store)
        return store

    def set_living_threads_seed_for_testing(self, seed: str) -> None:
        """Freeze a reproducible seed for tests or an explicit replay."""
        store = self._threads_store()
        store["world_seed"] = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        store["players"] = {}
        self._write_json(self.living_threads_path, store)

    def _number(self, store: dict[str, Any], *parts: object) -> int:
        material = "|".join((str(store["world_seed"]), CANONICAL_SEED_SHA256, *(str(p) for p in parts)))
        return int(hashlib.sha256(material.encode("utf-8")).hexdigest(), 16)

    def _pick(self, store: dict[str, Any], values: tuple[Any, ...] | list[Any], *parts: object) -> Any:
        return values[self._number(store, *parts) % len(values)]

    def _new_player_state(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        pool = list(self.RESIDENTS)
        residents: dict[str, Any] = {}
        for index in range(3):
            blueprint = self._pick(store, pool, player_id, "resident", index)
            pool.remove(blueprint)
            residents[blueprint["id"]] = {
                "resident_id": blueprint["id"], "name": blueprint["name"],
                "goal": blueprint["goal"], "stages": list(blueprint["stages"]),
                "stage_index": 0, "progress": 0, "last_changed_turn": 0,
                "player_controlled": False, "autonomous_person_claim": False,
                "can_refuse_contact": True, "fate_is_not_player_reward": True,
            }
        return {
            "turn": 0, "residents": residents, "symbols": {}, "pending": [],
            "surfaced": [], "action_fingerprints": [], "next_ordinal": 1,
        }

    def _player_state(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        players = store.setdefault("players", {})
        if player_id not in players:
            players[player_id] = self._new_player_state(store, player_id)
        return players[player_id]

    @staticmethod
    def _fingerprint(action: str) -> str:
        normalized = UniversalGodMode.normalize(action)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _is_silence(cls, action: str) -> bool:
        text = UniversalGodMode.normalize(action)
        return text in cls.SILENCE or any(text.startswith(item + " ") for item in cls.SILENCE)

    @staticmethod
    def _subjects(action: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"(?:^|\s)@([\w-]{1,80})", UniversalGodMode.normalize(action))))

    def _schedule(self, store: dict[str, Any], state: dict[str, Any], *, kind: str,
                  due_turn: int, payload: dict[str, Any], source_turn: int) -> None:
        ordinal = int(state.get("next_ordinal", 1))
        state["next_ordinal"] = ordinal + 1
        event_id = hashlib.sha256(
            f"{store['world_seed']}:{kind}:{source_turn}:{due_turn}:{ordinal}:{payload}".encode("utf-8")
        ).hexdigest()[:20]
        state.setdefault("pending", []).append({
            "event_id": event_id, "kind": kind, "due_turn": due_turn,
            "source_turn": source_turn, "payload": payload,
            "random_victim_created": False, "predictive_guilt": False,
        })

    def _advance_resident(self, store: dict[str, Any], state: dict[str, Any], player_id: str) -> dict[str, Any]:
        turn = int(state["turn"])
        residents = list(state["residents"].values())
        resident = self._pick(store, residents, player_id, "resident-progress", turn)
        resident["progress"] += 1 + self._number(store, player_id, "resident-step", turn) % 2
        target = min(len(resident["stages"]) - 1, resident["progress"] // 2)
        changed = target > resident["stage_index"]
        if changed:
            resident["stage_index"] = target
            resident["last_changed_turn"] = turn
        return {"resident": resident, "changed": changed}

    def _ensure_symbol(self, store: dict[str, Any], state: dict[str, Any], player_id: str) -> None:
        if state["symbols"]:
            return
        symbol = self._pick(store, list(self.SYMBOLS), player_id, "first-symbol")
        state["symbols"][symbol["id"]] = {"name": symbol["name"], "seen": 0, "last_turn": None}
        self._schedule(store, state, kind="symbol", due_turn=state["turn"],
                       payload={"symbol_id": symbol["id"], "returning": False}, source_turn=state["turn"])
        delay = 3 + self._number(store, player_id, "symbol-return") % 4
        self._schedule(store, state, kind="symbol", due_turn=state["turn"] + delay,
                       payload={"symbol_id": symbol["id"], "returning": True}, source_turn=state["turn"])

    def _schedule_turn_event(self, store: dict[str, Any], state: dict[str, Any], player_id: str,
                             action: str, resident_update: dict[str, Any]) -> None:
        turn = int(state["turn"])
        if self._is_silence(action):
            self._schedule(store, state, kind="silence", due_turn=turn, payload={}, source_turn=turn)
            return
        kinds = ["ambiguous", "resident", "delayed", "silent_reaction"]
        kind = self._pick(store, kinds, player_id, "turn-kind", turn, self._fingerprint(action))
        if resident_update["changed"]:
            kind = "resident"
        payload: dict[str, Any] = {}
        due = turn + self._number(store, player_id, "delay", turn) % 3
        if kind == "resident":
            payload["resident_id"] = resident_update["resident"]["resident_id"]
        elif kind == "delayed":
            payload.update({"source_action": action[:240], "subjects": self._subjects(action)})
            due = turn + 2 + self._number(store, player_id, "long-delay", turn) % 4
        elif kind == "silent_reaction":
            payload.update({"source_action": action[:240], "subjects": self._subjects(action)})
            due = turn + 1 + self._number(store, player_id, "reaction-delay", turn) % 3
        self._schedule(store, state, kind=kind, due_turn=due, payload=payload, source_turn=turn)

    def _symbol(self, symbol_id: str) -> dict[str, Any]:
        return next(item for item in self.SYMBOLS if item["id"] == symbol_id)

    def _render(self, store: dict[str, Any], state: dict[str, Any], event: dict[str, Any],
                player_id: str, child_role: bool) -> str:
        kind, payload, turn = event["kind"], event["payload"], state["turn"]
        if kind == "symbol":
            symbol = self._symbol(payload["symbol_id"])
            returning = bool(payload.get("returning"))
            key = ("child_return" if returning else "child_first") if child_role else ("return" if returning else "first")
            record = state["symbols"][symbol["id"]]
            record["seen"] += 1; record["last_turn"] = turn
            return symbol[key]
        if kind == "ambiguous":
            scenes = self.CHILD_AMBIGUOUS if child_role else self.AMBIGUOUS
            return self._pick(store, list(scenes), player_id, "ambiguous-scene", event["event_id"])
        if kind == "resident":
            resident = state["residents"][payload["resident_id"]]
            stage = resident["stages"][resident["stage_index"]]
            if child_role:
                return f"Из окна было видно, как {resident['name']} {stage}. Хранитель не превращал чужую жизнь в задание ребёнка."
            return (f"Жизнь {resident['name']} продолжалась вне твоих команд: {stage}. "
                    f"Цель оставалась прежней — {resident['goal']}. Это не было наградой или наказанием за твой ход.")
        if kind == "silence":
            return ("Ты ничего не сказал. Мир не заполнил паузу моралью: за стеной прошли шаги, затем стихли. "
                    "Молчание осталось настоящим действием, а не пустым полем.")
        source = str(payload.get("source_action") or "прежний выбор")
        subjects = payload.get("subjects") or []
        subject = f" @{subjects[0]}" if subjects else ""
        if kind == "silent_reaction":
            if child_role:
                return "Позже рядом появился маленький аккуратно сложенный лист бумаги. Никто не потребовал благодарить или угадывать, кто его оставил."
            return (f"Спустя время после «{source}»{subject} рядом остался тихий знак присутствия: переставленная чашка и свободное место. "
                    "Genesis не назвал это благодарностью, прощением или согласием.")
        if child_role:
            return "Позже взрослые заметили, что прежнее доброе действие сделало один угол дома спокойнее. Ребёнку не назначили за это долг или роль спасителя."
        return (f"Последствие прежнего действия «{source}» вернулось не как очко: кто-то пользовался созданным проходом, не зная имени создателя. "
                "История продолжилась без обязанности ответить тебе.")

    def _due_event(self, store: dict[str, Any], state: dict[str, Any], player_id: str) -> dict[str, Any] | None:
        due = [item for item in state["pending"] if int(item["due_turn"]) <= int(state["turn"])]
        if not due:
            return None
        priority = {"silence": 0, "symbol": 1, "resident": 2, "silent_reaction": 3, "delayed": 4, "ambiguous": 5}
        due.sort(key=lambda item: (int(item["due_turn"]), priority.get(item["kind"], 9),
                                   self._number(store, player_id, "due", item["event_id"])))
        event = due[0]
        state["pending"] = [item for item in state["pending"] if item["event_id"] != event["event_id"]]
        return event

    def weave_after_action(self, player_id: str, action: str, base: WorldResult) -> WorldResult:
        """Advance the world and optionally surface one unscripted event."""
        store = self._threads_store()
        state = self._player_state(store, player_id)
        state["turn"] += 1
        state["action_fingerprints"] = (state.get("action_fingerprints", []) + [self._fingerprint(action)])[-24:]
        resident_update = self._advance_resident(store, state, player_id)
        self._ensure_symbol(store, state, player_id)
        self._schedule_turn_event(store, state, player_id, action, resident_update)

        event = None if base.status in self.BLOCKED_STATUSES else self._due_event(store, state, player_id)
        if event is None:
            self._write_json(self.living_threads_path, store)
            return base

        child_role = bool(getattr(self, "_is_child", lambda _id: False)(player_id))
        narrative = self._render(store, state, event, player_id, child_role)
        surfaced = {
            "event_id": event["event_id"], "kind": event["kind"], "turn": state["turn"],
            "narrative": narrative, "child_safe": child_role,
            "created_from_visible_menu": False, "random_victim_created": False,
            "predictive_guilt": False, "resident_autonomy_claim": False,
        }
        state.setdefault("surfaced", []).append(surfaced)
        self._write_json(self.living_threads_path, store)
        self.memory.append_event(player_id, "living_thread_surfaced", {
            "event_id": event["event_id"], "kind": event["kind"], "turn": state["turn"],
            "created_from_visible_menu": False, "random_victim_created": False,
            "child_safe": child_role,
        })
        return self._copy(
            base,
            narrative=base.narrative + "\n\nНить мира возникла без выбора из меню:\n" + narrative,
            choices=[],
        )

    def living_threads_state(self, player_id: str | None = None) -> dict[str, Any]:
        """Developer view. The raw seed is intentionally not exposed."""
        store = self._threads_store()
        seed_fingerprint = hashlib.sha256(str(store["world_seed"]).encode("utf-8")).hexdigest()[:16]
        result: dict[str, Any] = {
            "schema_version": store.get("schema_version"),
            "seed_fingerprint": seed_fingerprint,
            "invariants": store.get("invariants", {}),
        }
        if player_id is None:
            result["player_ids"] = sorted(store.get("players", {}))
            return result
        state = self._player_state(store, player_id)
        self._write_json(self.living_threads_path, store)
        result.update({
            "player_id": player_id, "turn": state["turn"],
            "residents": state["residents"], "symbols": state["symbols"],
            "pending_count": len(state["pending"]), "surfaced": state["surfaced"],
        })
        return result
