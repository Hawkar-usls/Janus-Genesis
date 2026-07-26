# -*- coding: utf-8 -*-
"""Domain models and universal God Mode law for Janus Genesis v18."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

__version__ = "18.0.0"
SHARED_UTOPIA_ID = "genesis-online"


class Realm(StrEnum):
    REFLECTION = "reflection"
    UTOPIA = "utopia"
    OTHER_FACE = "other_face"


class PowerNature(StrEnum):
    BENEVOLENT = "benevolent"
    HARMFUL = "harmful"
    UNCLEAR = "unclear"


@dataclass(slots=True)
class RelationshipMemory:
    subject_id: str
    known_name: str | None = None
    strength: float = 0.35
    residual_trust: float = 0.0
    residual_hurt: float = 0.0
    last_contact_tick: int = 0
    anchors: list[str] = field(default_factory=list)

    def decay(self, current_tick: int, rate: float = 0.012) -> None:
        elapsed = max(0, current_tick - self.last_contact_tick)
        self.strength = max(0.0, self.strength - elapsed * rate)
        if self.strength <= 0.08:
            self.known_name = None


@dataclass(slots=True)
class WorldState:
    world_id: str
    damage: float = 0.0
    warmth: float = 0.15
    shelter: float = 0.15
    healing: float = 0.15
    trust: float = 0.10
    nature: float = 0.10
    music: float = 0.05
    connection: float = 0.05
    good_facets: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)

    @staticmethod
    def _clamp(value: float) -> float:
        return min(1.0, max(0.0, float(value)))

    def normalize(self) -> None:
        for key in ("damage", "warmth", "shelter", "healing", "trust", "nature", "music", "connection"):
            setattr(self, key, self._clamp(getattr(self, key)))
        self.good_facets = list(dict.fromkeys(self.good_facets))

    @property
    def restoration(self) -> float:
        values = [self.warmth, self.shelter, self.healing, self.trust, self.nature, self.music, self.connection]
        return self._clamp(sum(values) / len(values) * 0.72 + (1.0 - self.damage) * 0.28)

    @property
    def ready_to_join(self) -> bool:
        mature = sum(
            value >= 0.35
            for value in (self.warmth, self.shelter, self.healing, self.trust, self.nature, self.music, self.connection)
        )
        return self.restoration >= 0.52 and mature >= 4 and len(self.good_facets) >= 4


@dataclass(slots=True)
class SharedWorldState:
    world_id: str = SHARED_UTOPIA_ID
    citizens: list[str] = field(default_factory=list)
    creations: list[str] = field(default_factory=list)
    restored_worlds: list[str] = field(default_factory=list)
    history: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PlayerV18:
    player_id: str
    display_name: str = "Unknown Wanderer"
    realm: Realm = Realm.REFLECTION
    branch_id: str | None = None
    grace: float = 0.0
    light: float = 0.0
    trust: float = 0.0
    scars: list[str] = field(default_factory=list)
    chronicle: list[str] = field(default_factory=list)
    relationships: dict[str, RelationshipMemory] = field(default_factory=dict)
    recent_pairs: dict[str, int] = field(default_factory=dict)
    recent_actions: dict[str, int] = field(default_factory=dict)
    tick: int = 0
    god_mode: bool = True
    good_count: int = 0
    harm_count: int = 0
    chronological_age: int = 18
    apparent_age: int = 18
    body_form: str = "привычное тело"
    immortal: bool = False
    restored_branches: list[str] = field(default_factory=list)

    def normalize(self) -> None:
        self.grace = max(0.0, float(self.grace))
        self.light = min(1.0, max(0.0, float(self.light)))
        self.trust = min(1.0, max(0.0, float(self.trust)))
        self.tick = max(0, int(self.tick))
        self.realm = Realm(self.realm)
        # God Mode is not a reward and can never be revoked.
        self.god_mode = True
        self.good_count = max(0, int(self.good_count))
        self.harm_count = max(0, int(self.harm_count))
        self.chronological_age = max(0, int(self.chronological_age))
        self.apparent_age = max(0, int(self.apparent_age))
        self.immortal = bool(self.immortal)


@dataclass(frozen=True, slots=True)
class WorldResult:
    status: str
    narrative: str
    realm: Realm
    visible_grace: None
    choices: list[str]
    branch_id: str | None = None
    trace_id: str | None = None
    wish_manifested: bool = False

    def to_dict(self, *, internal: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if internal:
            data["realm"] = self.realm.value
            return data
        # Realm and branch routing are intentionally invisible to players.
        data.pop("realm", None)
        data.pop("branch_id", None)
        return data


class UniversalGodMode:
    """Classify power requests by effect, never by a permanent moral label."""

    HARMFUL = {
        "убить", "сломать", "сжечь", "уничтожить", "взорвать", "ранить",
        "заставить", "подчинить", "поработить", "контролировать", "стереть память",
        "лишить воли", "потеряет волю", "волю", "подчин", "отнять свободу", "kill", "destroy", "burn", "hurt",
        "force", "enslave", "control", "erase memory",
    }
    BENEVOLENT = {
        "помочь", "спасти", "исцелить", "вылечить", "согреть", "защитить",
        "накормить", "построить", "починить", "вернуть", "простить", "обнять",
        "осветить", "очистить", "создать", "подарить", "поделиться", "научить",
        "любов", "свобод", "дом", "сад", "мост", "вода", "река", "музык",
        "help", "save", "heal", "warm", "protect", "feed", "build", "repair",
        "forgive", "create", "love", "freedom",
    }
    SELF_FORM = {"возраст", "выглядеть", "тело", "облик", "форма", "age", "body", "appearance"}

    @staticmethod
    def normalize(text: str) -> str:
        cleaned = re.sub(r"[^\w\s@:_-]+", " ", text.strip().lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def classify(self, request: str) -> PowerNature:
        text = self.normalize(request)
        if any(fragment in text for fragment in self.HARMFUL):
            return PowerNature.HARMFUL
        if any(fragment in text for fragment in self.BENEVOLENT | self.SELF_FORM):
            return PowerNature.BENEVOLENT
        return PowerNature.UNCLEAR
