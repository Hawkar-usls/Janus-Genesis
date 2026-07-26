# -*- coding: utf-8 -*-
"""Offline-first persistence and linked Chronicle for Janus Genesis v18."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from genesis_v18_models import PlayerV18, RelationshipMemory, SharedWorldState, WorldState


class GenesisV18Memory:
    def __init__(self, data_dir: str | Path = "data_v17"):
        self.root = Path(data_dir)
        self.players = self.root / "players"
        self.worlds = self.root / "worlds_v18"
        self.guards = self.root / "guards_v18"
        self.chronicle = self.root / "chronicle_v18.jsonl"
        self.shared_world_path = self.root / "shared_utopia_v18.json"
        self.purgatory_path = self.root / "purgatory_presence_v18.json"
        for path in (self.players, self.worlds, self.guards):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_id(value: str) -> str:
        cleaned = "".join(ch for ch in value if ch.isalnum() or ch in "-_")[:80]
        if not cleaned:
            raise ValueError("identifier is empty or unsafe")
        return cleaned

    @staticmethod
    def _atomic_write(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    @staticmethod
    def _dataclass_payload(cls: type[Any], raw: dict[str, Any]) -> dict[str, Any]:
        allowed = {item.name for item in fields(cls)}
        return {key: value for key, value in raw.items() if key in allowed}

    def load_player(self, player_id: str) -> PlayerV18:
        player_id = self._safe_id(player_id)
        path = self.players / f"{player_id}.json"
        if not path.exists():
            return PlayerV18(player_id=player_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        relationships = {
            key: RelationshipMemory(**self._dataclass_payload(RelationshipMemory, value))
            for key, value in raw.pop("relationships", {}).items()
        }
        payload = self._dataclass_payload(PlayerV18, raw)
        payload["player_id"] = player_id
        payload["relationships"] = relationships
        player = PlayerV18(**payload)
        player.normalize()
        return player

    def save_player(self, player: PlayerV18) -> None:
        player.normalize()
        self._atomic_write(self.players / f"{self._safe_id(player.player_id)}.json", asdict(player))

    def _world_path(self, world_id: str) -> Path:
        return self.worlds / f"{self._safe_id(world_id)}.json"

    def load_world(self, world_id: str) -> WorldState:
        path = self._world_path(world_id)
        if not path.exists():
            return WorldState(world_id=world_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        world = WorldState(**self._dataclass_payload(WorldState, raw))
        world.normalize()
        return world

    def save_world(self, world: WorldState) -> None:
        world.normalize()
        self._atomic_write(self._world_path(world.world_id), asdict(world))

    def load_shared_world(self) -> SharedWorldState:
        if not self.shared_world_path.exists():
            return SharedWorldState()
        raw = json.loads(self.shared_world_path.read_text(encoding="utf-8"))
        return SharedWorldState(**self._dataclass_payload(SharedWorldState, raw))

    def save_shared_world(self, shared: SharedWorldState) -> None:
        shared.citizens = list(dict.fromkeys(shared.citizens))
        shared.restored_worlds = list(dict.fromkeys(shared.restored_worlds))
        self._atomic_write(self.shared_world_path, asdict(shared))

    def set_purgatory_presence(self, player_id: str, present: bool) -> None:
        current: list[str] = []
        if self.purgatory_path.exists():
            try:
                current = list(json.loads(self.purgatory_path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                current = []
        safe = self._safe_id(player_id)
        if present and safe not in current:
            current.append(safe)
        if not present:
            current = [item for item in current if item != safe]
        self._atomic_write(self.purgatory_path, sorted(set(current)))

    def _last_event_hash(self) -> str:
        if not self.chronicle.exists():
            return "0" * 64
        last = ""
        with self.chronicle.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
        if not last:
            return "0" * 64
        try:
            return str(json.loads(last).get("event_hash", "0" * 64))
        except json.JSONDecodeError:
            return "0" * 64

    def append_event(self, player_id: str, event_type: str, payload: dict[str, Any]) -> str:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "player_id": self._safe_id(player_id),
            "event_type": event_type,
            "previous_hash": self._last_event_hash(),
            "payload": payload,
        }
        canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        event["event_hash"] = event_hash
        with self.chronicle.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event_hash

    def verify_chronicle(self) -> tuple[bool, int, str | None]:
        if not self.chronicle.exists():
            return True, 0, None
        expected_previous = "0" * 64
        count = 0
        with self.chronicle.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    return False, count, f"invalid JSON at line {line_number}"
                event_hash = str(event.pop("event_hash", ""))
                if event.get("previous_hash") != expected_previous:
                    return False, count, f"broken chain at line {line_number}"
                canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                calculated = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if event_hash != calculated:
                    return False, count, f"invalid event hash at line {line_number}"
                expected_previous = event_hash
                count += 1
        return True, count, None
