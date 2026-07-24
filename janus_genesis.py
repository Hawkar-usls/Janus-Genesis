# -*- coding: utf-8 -*-
"""Janus Genesis v16.1 — Golden Mirror MMO Foundation.

A kindness-first evolving interactive-fiction engine. It can run standalone,
be imported as a module, or serve as deterministic domain logic for a future
MMO backend. The LLM narrator is optional and never has safety authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, BinaryIO, Iterator

__version__ = "16.1.1"


class Shard(StrEnum):
    REFLECTION = "reflection"
    UTOPIA = "utopia"


class Intent(StrEnum):
    CONSTRUCTIVE = "constructive"
    DESTRUCTIVE = "destructive"
    FEAR = "fear"
    EXIT = "exit"
    NEUTRAL = "neutral"


@dataclass(slots=True)
class PlayerState:
    player_id: str
    display_name: str = "Traveler"
    shard: Shard = Shard.REFLECTION
    light: float = 0.0
    trust: float = 0.0
    entropy: float = 0.1
    depth: int = 1
    god_mode: bool = False
    inventory: list[str] = field(default_factory=list)
    lore: list[str] = field(default_factory=list)
    echoes: list[str] = field(default_factory=list)
    last_context: str = ""
    last_action: str = ""

    def normalize(self) -> None:
        self.light = min(1.0, max(0.0, float(self.light)))
        self.trust = min(1.0, max(0.0, float(self.trust)))
        self.entropy = min(1.5, max(0.0, float(self.entropy)))
        self.depth = max(1, int(self.depth))
        self.shard = Shard(self.shard)
        self.god_mode = bool(self.god_mode)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["shard"] = self.shard.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerState":
        state = cls(
            player_id=str(data["player_id"]),
            display_name=str(data.get("display_name", "Traveler")),
            shard=Shard(data.get("shard", Shard.REFLECTION.value)),
            light=float(data.get("light", 0.0)),
            trust=float(data.get("trust", 0.0)),
            entropy=float(data.get("entropy", 0.1)),
            depth=int(data.get("depth", 1)),
            god_mode=bool(data.get("god_mode", False)),
            inventory=list(data.get("inventory", [])),
            lore=list(data.get("lore", [])),
            echoes=list(data.get("echoes", [])),
            last_context=str(data.get("last_context", "")),
            last_action=str(data.get("last_action", "")),
        )
        state.normalize()
        return state


@dataclass(slots=True)
class WorldReply:
    status: str
    narrative: str
    choices: list[str]
    intent: Intent
    shard: Shard
    god_mode: bool
    light: float
    trust: float
    transformed_action: str | None = None
    artifact: str | None = None
    lore: str | None = None
    route_reason: str | None = None
    source: str = "local_rules"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["intent"] = self.intent.value
        data["shard"] = self.shard.value
        return data


@dataclass(frozen=True, slots=True)
class GenesisConfig:
    data_dir: Path
    gemini_api_key: str | None
    gemini_model: str
    network_enabled: bool
    utopia_light_threshold: float = 0.70
    utopia_trust_threshold: float = 0.55

    @classmethod
    def load(cls, data_dir: str | Path | None = None) -> "GenesisConfig":
        resolved = Path(
            data_dir
            or os.environ.get("JANUS_GENESIS_DATA")
            or Path.cwd() / "data"
        ).expanduser().resolve()
        return cls(
            data_dir=resolved,
            gemini_api_key=os.environ.get("GEMINI_API_KEY"),
            gemini_model=os.environ.get("JANUS_GEMINI_MODEL", "gemini-2.0-flash"),
            network_enabled=os.environ.get("JANUS_NETWORK", "1").lower()
            not in {"0", "false", "no"},
            utopia_light_threshold=float(os.environ.get("JANUS_UTOPIA_LIGHT", "0.70")),
            utopia_trust_threshold=float(os.environ.get("JANUS_UTOPIA_TRUST", "0.55")),
        )


class InterProcessFileLock:
    """OS advisory lock released automatically when a worker exits."""

    def __init__(self, path: Path, *, timeout: float = 30.0, poll_interval: float = 0.02):
        self.path = Path(path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._handle: BinaryIO | None = None

    @staticmethod
    def _try_lock(handle: BinaryIO) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(handle: BinaryIO) -> None:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def acquire(self) -> None:
        if self._handle is not None:
            raise RuntimeError("lock is already acquired by this instance")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._try_lock(handle)
                self._handle = handle
                return
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    handle.close()
                    raise TimeoutError(f"Timed out waiting for lock: {self.path}")
                time.sleep(self.poll_interval)

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            self._unlock(handle)
        finally:
            handle.close()

    def __enter__(self) -> "InterProcessFileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


class GenesisMemory:
    """Atomic player states and a process-safe SHA-256 event chain."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.players_dir = self.data_dir / "players"
        self.chronicle_path = self.data_dir / "genesis_chronicle.jsonl"
        self.dreams_path = self.data_dir / "dreams.json"
        self.locks_dir = self.data_dir / ".locks"
        self._lock = threading.RLock()
        self.players_dir.mkdir(parents=True, exist_ok=True)
        self.locks_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_player_id(player_id: str) -> str:
        allowed = "".join(ch for ch in player_id if ch.isalnum() or ch in "-_")
        if not allowed:
            raise ValueError("player_id must contain letters, numbers, '-' or '_'")
        return allowed[:80]

    def _player_path(self, player_id: str) -> Path:
        return self.players_dir / f"{self._safe_player_id(player_id)}.json"

    def _file_lock(self, name: str, *, timeout: float = 30.0) -> InterProcessFileLock:
        return InterProcessFileLock(self.locks_dir / f"{name}.lock", timeout=timeout)

    @staticmethod
    def _atomic_json_write(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _load_player_unlocked(self, player_id: str, display_name: str | None = None) -> PlayerState:
        safe_id = self._safe_player_id(player_id)
        path = self._player_path(safe_id)
        if path.exists():
            try:
                return PlayerState.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                try:
                    os.replace(path, path.with_suffix(path.suffix + ".damaged"))
                except OSError:
                    pass
        return PlayerState(player_id=safe_id, display_name=display_name or "Traveler")

    def _save_player_unlocked(self, state: PlayerState) -> None:
        state.normalize()
        self._atomic_json_write(self._player_path(state.player_id), state.to_dict())

    def load_player(self, player_id: str, display_name: str | None = None) -> PlayerState:
        safe_id = self._safe_player_id(player_id)
        with self._lock, self._file_lock(f"player-{safe_id}"):
            return self._load_player_unlocked(safe_id, display_name)

    def save_player(self, state: PlayerState) -> None:
        safe_id = self._safe_player_id(state.player_id)
        with self._lock, self._file_lock(f"player-{safe_id}"):
            self._save_player_unlocked(state)

    @contextmanager
    def player_transaction(self, player_id: str, display_name: str | None = None) -> Iterator[PlayerState]:
        safe_id = self._safe_player_id(player_id)
        with self._lock, self._file_lock(f"player-{safe_id}"):
            state = self._load_player_unlocked(safe_id, display_name)
            try:
                yield state
            finally:
                self._save_player_unlocked(state)

    def _last_hash_unlocked(self) -> str:
        if not self.chronicle_path.exists():
            return "GENESIS"
        last = ""
        with self.chronicle_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        if not last:
            return "GENESIS"
        try:
            return str(json.loads(last).get("event_hash", "GENESIS"))
        except json.JSONDecodeError:
            return "CORRUPTED_PREVIOUS_EVENT"

    def append_event(self, player_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._file_lock("chronicle"):
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "player_id": self._safe_player_id(player_id),
                "event_type": event_type,
                "payload": payload,
                "previous_hash": self._last_hash_unlocked(),
            }
            canonical = json.dumps(
                event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            event["event_hash"] = hashlib.sha256(canonical).hexdigest()
            self.chronicle_path.parent.mkdir(parents=True, exist_ok=True)
            with self.chronicle_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return event

    def verify_chronicle(self) -> tuple[bool, int, str | None]:
        with self._lock, self._file_lock("chronicle"):
            if not self.chronicle_path.exists():
                return True, 0, None
            previous, count = "GENESIS", 0
            with self.chronicle_path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        return False, count, f"invalid JSON at line {line_number}"
                    event_hash = str(event.pop("event_hash", ""))
                    if event.get("previous_hash") != previous:
                        return False, count, f"broken predecessor at line {line_number}"
                    canonical = json.dumps(
                        event, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                    if event_hash != hashlib.sha256(canonical).hexdigest():
                        return False, count, f"invalid event hash at line {line_number}"
                    previous, count = event_hash, count + 1
            return True, count, None

    def export_dream(self, state: PlayerState, label: str, content: str, dream_type: str) -> None:
        with self._lock, self._file_lock("dreams"):
            dreams: list[dict[str, Any]] = []
            if self.dreams_path.exists():
                try:
                    loaded = json.loads(self.dreams_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, list):
                        dreams = loaded
                except (OSError, json.JSONDecodeError):
                    dreams = []
            dreams.append({
                "id": f"genesis-{state.player_id}-{len(dreams) + 1}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": dream_type,
                "label": f"[GENESIS] {label}",
                "content": content,
                "meta": {
                    "depth": state.depth,
                    "entropy": state.entropy,
                    "light": state.light,
                    "shard": state.shard.value,
                },
            })
            self._atomic_json_write(self.dreams_path, dreams[-100:])


@dataclass(frozen=True, slots=True)
class KarmaDecision:
    intent: Intent
    transformed_action: str | None
    light_delta: float
    trust_delta: float
    entropy_delta: float
    message: str


class GoldenMirror:
    """Deterministic safety authority. The narrator cannot override it."""

    EXIT_WORDS = {"exit", "quit", "выход", "выйти", "закрыть игру", "хватит", "стоп игра"}
    DESTRUCTIVE_WORDS = {
        "убить", "ударить", "сломать", "украсть", "взорвать", "сжечь", "разрушить",
        "ограбить", "оскорбить", "kill", "attack", "steal", "destroy", "burn", "explode", "hurt",
    }
    CONSTRUCTIVE_WORDS = {
        "помочь", "защитить", "построить", "создать", "подарить", "исцелить", "поделиться",
        "простить", "спасти", "починить", "обнять", "help", "protect", "build", "create", "heal",
        "share", "repair",
    }
    FEAR_WORDS = {"страшно", "боюсь", "паника", "тревога", "ужас", "спрятаться", "fear", "afraid", "panic", "anxiety"}

    @staticmethod
    def _normalized(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]+", " ", text.strip().lower())).strip()

    def classify(self, text: str) -> Intent:
        normalized = self._normalized(text)
        if normalized in self.EXIT_WORDS or any(normalized.startswith(word + " ") for word in self.EXIT_WORDS):
            return Intent.EXIT
        if any(word in normalized for word in self.DESTRUCTIVE_WORDS):
            return Intent.DESTRUCTIVE
        if any(word in normalized for word in self.CONSTRUCTIVE_WORDS):
            return Intent.CONSTRUCTIVE
        if any(word in normalized for word in self.FEAR_WORDS):
            return Intent.FEAR
        return Intent.NEUTRAL

    def decide(self, state: PlayerState, text: str) -> KarmaDecision:
        intent = self.classify(text)
        if intent is Intent.EXIT:
            return KarmaDecision(intent, None, 0.0, 0.0, -0.05, "Дверь открыта. Твой выход уважается немедленно.")
        if intent is Intent.CONSTRUCTIVE:
            return KarmaDecision(intent, text, 0.14, 0.10, -0.03, "Мир отвечает доверием: созидание открывает больше возможностей.")
        if intent is Intent.DESTRUCTIVE:
            return KarmaDecision(
                intent,
                "Остановить вред, понять его причину и превратить импульс в восстановление, защиту или честный обмен.",
                -0.05, -0.12, 0.08,
                "Разрушительное действие не достигает цели и превращается в безопасный восстановительный квест.",
            )
        if intent is Intent.FEAR:
            return KarmaDecision(intent, "Найти безопасное место, свет и союзника.", 0.03, 0.04, -0.12, "Мир снижает давление: появляется свет и понятный безопасный путь.")
        return KarmaDecision(intent, text, 0.01, 0.01, 0.01, "Мир внимательно слушает и предлагает исследовать последствия без вреда.")


@dataclass(frozen=True, slots=True)
class RouteDecision:
    shard: Shard
    god_mode: bool
    reason: str
    changed: bool


class MMOGateway:
    def __init__(self, light_threshold: float = 0.70, trust_threshold: float = 0.55):
        self.light_threshold = light_threshold
        self.trust_threshold = trust_threshold

    def route(self, state: PlayerState, intent: Intent) -> RouteDecision:
        previous = (state.shard, state.god_mode)
        if state.shard is Shard.UTOPIA and intent is Intent.DESTRUCTIVE:
            state.shard, state.god_mode = Shard.REFLECTION, False
            return RouteDecision(state.shard, False, "Вред заблокирован до применения. Доступ к общей Утопии временно приостановлен; прогресс других игроков не затронут.", True)
        eligible = state.light >= self.light_threshold and state.trust >= self.trust_threshold and intent is not Intent.DESTRUCTIVE
        state.shard = Shard.UTOPIA if eligible else Shard.REFLECTION
        state.god_mode = eligible
        reason = "Созидательная история открыла Utopia Shard и God Mode." if eligible else "Reflection — безопасная личная песочница, а не наказание."
        return RouteDecision(state.shard, state.god_mode, reason, previous != (state.shard, state.god_mode))


@dataclass(frozen=True, slots=True)
class Narrative:
    narrative: str
    choices: list[str]
    artifact: str | None = None
    lore: str | None = None
    source: str = "offline"


class TrinityNarrator:
    def __init__(self, config: GenesisConfig):
        self.config = config

    @staticmethod
    def archetype(state: PlayerState) -> tuple[str, str, float]:
        if state.entropy < 0.30:
            return "🏛️", "АРХИТЕКТОР", 0.45
        if state.entropy < 0.75:
            return "👁️", "ТВОРЕЦ", 0.75
        return "🎭", "ТРИКСТЕР", 0.95

    @staticmethod
    def _offline(state: PlayerState, intent: Intent, safe_message: str) -> Narrative:
        icon, archetype, _ = TrinityNarrator.archetype(state)
        place = "Утопии" if state.shard is Shard.UTOPIA else "Зеркальном Инстансе"
        if intent is Intent.CONSTRUCTIVE:
            return Narrative(f"{icon} {archetype}: В {place} твой поступок становится новой дорогой, мастерской и союзом. {safe_message}", ["Продолжить созидание", "Поделиться результатом", "Исследовать путь"])
        if intent is Intent.DESTRUCTIVE:
            return Narrative(f"{icon} {archetype}: Вред не материализуется. Энергия действия перенаправлена в восстановление. {safe_message}", ["Исправить", "Понять причину", "Попросить помощи"])
        if intent is Intent.FEAR:
            return Narrative(f"{icon} {archetype}: Пространство становится светлее. {safe_message}", ["Выдохнуть", "Позвать союзника", "Выйти из игры"])
        return Narrative(f"{icon} {archetype}: Мир превращает мысль в безопасную развилку. {safe_message}", ["Осмотреться", "Создать что-то", "Выйти из игры"])

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        clean = text.replace("```json", "").replace("```", "").strip()
        start, end = clean.find("{"), clean.rfind("}")
        if start < 0 or end < start:
            return None
        try:
            parsed = json.loads(clean[start:end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def generate(self, state: PlayerState, user_action: str, intent: Intent, safe_message: str, transformed_action: str | None) -> Narrative:
        if not self.config.network_enabled or not self.config.gemini_api_key or intent is Intent.EXIT:
            return self._offline(state, intent, safe_message)
        icon, archetype, temperature = self.archetype(state)
        system = (
            "Ты рассказчик Janus Genesis — мира, где созидание открывает больше возможностей. "
            "Golden Mirror уже вынес решение: не разрешай вред, не удерживай игрока, не меняй shard/god_mode. "
            "Верни JSON на русском с ключами narrative, choices, artifact, lore. "
            f"ARCHETYPE={archetype}; SHARD={state.shard.value}; GOD_MODE={state.god_mode}; "
            f"INTENT={intent.value}; SAFETY={safe_message}; TRANSFORMED={transformed_action}; ICON={icon}"
        )
        prompt = f"ACTION={user_action}\nCONTEXT={state.last_context[-1200:]}\nLIGHT={state.light:.3f}; TRUST={state.trust:.3f}; ENTROPY={state.entropy:.3f}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "system_instruction": {"parts": [{"text": system}]},
            "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.gemini_model}:generateContent?key={self.config.gemini_api_key}"
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = json.loads(response.read().decode("utf-8"))
            parsed = self._extract_json(data["candidates"][0]["content"]["parts"][0]["text"])
            if not parsed:
                raise ValueError("invalid narrator JSON")
            choices = [str(item) for item in parsed.get("choices", []) if str(item).strip()][:4] or ["Продолжить", "Выйти из игры"]
            if not any("вый" in item.lower() for item in choices):
                choices.append("Выйти из игры")
            return Narrative(
                str(parsed.get("narrative") or safe_message), choices,
                str(parsed["artifact"]) if parsed.get("artifact") else None,
                str(parsed["lore"]) if parsed.get("lore") else None,
                "gemini",
            )
        except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError, urllib.error.URLError):
            return self._offline(state, intent, safe_message)


class JanusWorld:
    def __init__(self, config: GenesisConfig | None = None, data_dir: str | Path | None = None):
        self.config = config or GenesisConfig.load(data_dir)
        self.memory = GenesisMemory(self.config.data_dir)
        self.golden_mirror = GoldenMirror()
        self.gateway = MMOGateway(self.config.utopia_light_threshold, self.config.utopia_trust_threshold)
        self.narrator = TrinityNarrator(self.config)

    def get_player(self, player_id: str, display_name: str | None = None) -> PlayerState:
        return self.memory.load_player(player_id, display_name)

    def process_action(self, player_id: str, action: str, display_name: str | None = None) -> WorldReply:
        with self.memory.player_transaction(player_id, display_name) as state:
            decision = self.golden_mirror.decide(state, action)
            if decision.intent is Intent.EXIT:
                self.memory.append_event(state.player_id, "exit", {"action": action, "respected": True})
                return WorldReply("EXIT", decision.message, [], decision.intent, state.shard, state.god_mode, state.light, state.trust, route_reason="Явный выход всегда исполняется.")
            state.light += decision.light_delta
            state.trust += decision.trust_delta
            state.entropy += decision.entropy_delta
            state.last_action = action
            if len(action.strip()) > 10:
                state.echoes = (state.echoes + [action.strip()])[-30:]
            state.normalize()
            route = self.gateway.route(state, decision.intent)
            narrative = self.narrator.generate(state, action, decision.intent, decision.message, decision.transformed_action)
            if narrative.artifact:
                state.inventory.append(narrative.artifact)
            if narrative.lore:
                state.lore.append(narrative.lore)
                state.depth += 1
            state.last_context = narrative.narrative
            state.normalize()
            reply = WorldReply(
                "CONTINUE", narrative.narrative, narrative.choices, decision.intent,
                state.shard, state.god_mode, state.light, state.trust,
                decision.transformed_action, narrative.artifact, narrative.lore,
                route.reason, narrative.source,
            )
            self.memory.append_event(state.player_id, "action", {"action": action, "reply": reply.to_dict(), "route_changed": route.changed})
            self.memory.export_dream(state, f"Путь: {decision.intent.value}", narrative.narrative, "game_event")
            return reply


def _banner() -> None:
    print("\n╔══════════════════════════════════════════════════╗\n║       JANUS GENESIS v16.1 — GOLDEN MIRROR        ║\n║ Reflection → Trust → Utopia → Shared Creation    ║\n╚══════════════════════════════════════════════════╝\n")


def play(data_dir: Path | None, player_id: str, name: str) -> int:
    world = JanusWorld(GenesisConfig.load(data_dir))
    _banner()
    state = world.get_player(player_id, name)
    print(f"Игрок: {state.display_name} | Мир: {state.shard.value} | Свет: {state.light:.2f} | Доверие: {state.trust:.2f}\nНапиши действие. Команды выхода: exit, quit, выход, выйти.\n")
    while True:
        try:
            action = input("🌀 > ").strip() or "Осмотреться"
        except (EOFError, KeyboardInterrupt):
            print()
            action = "exit"
        reply = world.process_action(player_id, action, name)
        print(f"\n{reply.narrative}\n[{reply.shard.value}] light={reply.light:.2f} trust={reply.trust:.2f} god_mode={reply.god_mode}")
        if reply.route_reason:
            print(f"Маршрут: {reply.route_reason}")
        for index, choice in enumerate(reply.choices, 1):
            print(f"{index}. {choice}")
        print()
        if reply.status == "EXIT":
            return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="janus_genesis.py")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--player", default="traveler")
    parser.add_argument("--name", default="Traveler")
    parser.add_argument("--action", help="Process one action, print JSON and exit.")
    parser.add_argument("--status", action="store_true", help="Print player state and exit.")
    parser.add_argument("--verify-chronicle", action="store_true", help="Validate the SHA-256 chronicle and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    world = JanusWorld(GenesisConfig.load(args.data_dir))
    if args.verify_chronicle:
        valid, count, error = world.memory.verify_chronicle()
        print(json.dumps({"valid": valid, "events": count, "error": error}, ensure_ascii=False, indent=2))
        return 0 if valid else 1
    if args.status:
        print(json.dumps(world.get_player(args.player, args.name).to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.action is not None:
        print(json.dumps(world.process_action(args.player, args.action, args.name).to_dict(), ensure_ascii=False, indent=2))
        return 0
    return play(args.data_dir, args.player, args.name)


if __name__ == "__main__":
    raise SystemExit(main())
