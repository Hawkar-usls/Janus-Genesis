# -*- coding: utf-8 -*-
"""Janus Genesis v17 — The Other Face and Living Grace.

This module is a deterministic, offline-first runtime for the v17 mechanics:
severance into isolated world branches, living relationship memory, hidden
Grace, contextual anti-abuse valuation, delayed consequences, and wish casting.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

__version__ = "17.0.0"


class Realm(StrEnum):
    REFLECTION = "reflection"
    UTOPIA = "utopia"
    OTHER_FACE = "other_face"


class Intent(StrEnum):
    CONSTRUCTIVE = "constructive"
    DESTRUCTIVE = "destructive"
    WISH = "wish"
    NEUTRAL = "neutral"


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
class GraceTrace:
    trace_id: str
    actor_id: str
    beneficiary_id: str | None
    action: str
    base_utility: float
    need: float
    durability: float
    sacrifice: float
    novelty: float
    reciprocity_risk: float
    chain_depth: int
    created_tick: int
    settled: bool = False
    realized_impact: float = 0.0


@dataclass(slots=True)
class PlayerV17:
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
    tick: int = 0
    god_mode: bool = False

    def normalize(self) -> None:
        self.grace = max(0.0, float(self.grace))
        self.light = min(1.0, max(0.0, float(self.light)))
        self.trust = min(1.0, max(0.0, float(self.trust)))
        self.tick = max(0, int(self.tick))
        self.realm = Realm(self.realm)
        self.god_mode = bool(self.god_mode)


@dataclass(frozen=True, slots=True)
class GraceAssessment:
    utility_score: float
    multiplier: float
    provisional_grace: float
    reason: str
    abuse_suspected: bool


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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["realm"] = self.realm.value
        return data


class LivingGrace:
    """Contextual value engine. Exact balances and formulas remain server-side."""

    OTHER_PLAYER_MULTIPLIER = 15.0

    @staticmethod
    def _clamp(value: float) -> float:
        return min(1.0, max(0.0, float(value)))

    def assess(
        self,
        *,
        actor: PlayerV17,
        beneficiary_id: str | None,
        utility: float,
        need: float,
        durability: float,
        sacrifice: float,
        novelty: float,
        chain_depth: int = 0,
    ) -> GraceAssessment:
        utility = self._clamp(utility)
        need = self._clamp(need)
        durability = self._clamp(durability)
        sacrifice = self._clamp(sacrifice)
        novelty = self._clamp(novelty)

        pair_key = beneficiary_id or actor.player_id
        repeats = actor.recent_pairs.get(pair_key, 0)
        repetition_decay = 1.0 / (1.0 + repeats * 0.75)
        reciprocal_loop = beneficiary_id is not None and repeats >= 3 and novelty < 0.35
        reciprocity_penalty = 0.08 if reciprocal_loop else 1.0

        # Utility dominates; intention without real change produces little Grace.
        contextual_value = (
            utility
            * (0.20 + 0.80 * need)
            * (0.25 + 0.75 * durability)
            * (0.50 + 0.50 * sacrifice)
            * (0.20 + 0.80 * novelty)
        )
        multiplier = self.OTHER_PLAYER_MULTIPLIER if beneficiary_id and beneficiary_id != actor.player_id else 1.0
        chain_bonus = 1.0 + min(2.0, max(0, chain_depth) * 0.25)
        provisional = 10.0 * contextual_value * multiplier * chain_bonus * repetition_decay * reciprocity_penalty

        if reciprocal_loop:
            reason = "Поступок почти не изменил историю и похож на повторяемый обмен."
        elif beneficiary_id and beneficiary_id != actor.player_id:
            reason = "Мир заметил реальную пользу, принесённую другому страннику."
        else:
            reason = "Мир сохранил след созидания, направленного на собственную жизнь."

        return GraceAssessment(
            utility_score=contextual_value,
            multiplier=multiplier,
            provisional_grace=max(0.0, provisional),
            reason=reason,
            abuse_suspected=reciprocal_loop,
        )

    @staticmethod
    def settle(trace: GraceTrace, realized_impact: float, propagated_good: float = 0.0) -> float:
        """Settle delayed Grace after consequences become known."""
        realized = min(1.0, max(0.0, realized_impact))
        propagation = min(3.0, max(0.0, propagated_good))
        trace.realized_impact = realized
        trace.settled = True
        base = trace.base_utility * trace.need * trace.durability
        chain = 1.0 + propagation + min(1.5, trace.chain_depth * 0.2)
        anti_loop = max(0.0, 1.0 - trace.reciprocity_risk)
        return max(0.0, 12.0 * base * realized * chain * anti_loop)


class GenesisV17Memory:
    def __init__(self, data_dir: str | Path = "data_v17"):
        self.root = Path(data_dir)
        self.players = self.root / "players"
        self.traces = self.root / "grace_traces"
        self.chronicle = self.root / "chronicle_v17.jsonl"
        self.players.mkdir(parents=True, exist_ok=True)
        self.traces.mkdir(parents=True, exist_ok=True)

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

    def load_player(self, player_id: str) -> PlayerV17:
        player_id = self._safe_id(player_id)
        path = self.players / f"{player_id}.json"
        if not path.exists():
            return PlayerV17(player_id=player_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        relationships = {
            key: RelationshipMemory(**value) for key, value in raw.pop("relationships", {}).items()
        }
        player = PlayerV17(**raw, relationships=relationships)
        player.normalize()
        return player

    def save_player(self, player: PlayerV17) -> None:
        player.normalize()
        self._atomic_write(self.players / f"{self._safe_id(player.player_id)}.json", asdict(player))

    def save_trace(self, trace: GraceTrace) -> None:
        self._atomic_write(self.traces / f"{self._safe_id(trace.trace_id)}.json", asdict(trace))

    def load_trace(self, trace_id: str) -> GraceTrace:
        raw = json.loads((self.traces / f"{self._safe_id(trace_id)}.json").read_text(encoding="utf-8"))
        return GraceTrace(**raw)

    def append_event(self, player_id: str, event_type: str, payload: dict[str, Any]) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "player_id": self._safe_id(player_id),
            "event_type": event_type,
            "payload": payload,
        }
        canonical = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        event["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with self.chronicle.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


class JanusGenesisV17:
    def __init__(self, data_dir: str | Path = "data_v17"):
        self.memory = GenesisV17Memory(data_dir)
        self.grace = LivingGrace()

    @staticmethod
    def _branch_id(player_id: str, tick: int) -> str:
        seed = f"{player_id}:{tick}:OTHER_FACE".encode("utf-8")
        return hashlib.sha256(seed).hexdigest()[:16]

    def sever(self, player: PlayerV17, action: str) -> WorldResult:
        player.realm = Realm.OTHER_FACE
        player.god_mode = False
        player.branch_id = self._branch_id(player.player_id, player.tick)
        player.scars.append(action)
        player.chronicle.append(f"Severance: {action}")
        self.memory.append_event(player.player_id, "severance", {"branch_id": player.branch_id, "action": action})
        return WorldResult(
            status="SEVERED",
            narrative=(
                "Янус не отменил твой выбор. Общая Утопия осталась невредима, "
                "а последствия открылись во Втором Лике. Здесь история не стирается."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=["Увидеть последствия", "Начать восстановление", "Позвать неизвестного странника"],
            branch_id=player.branch_id,
        )

    def perform_good(
        self,
        player_id: str,
        action: str,
        *,
        beneficiary_id: str | None = None,
        utility: float,
        need: float,
        durability: float,
        sacrifice: float,
        novelty: float,
        chain_depth: int = 0,
    ) -> WorldResult:
        player = self.memory.load_player(player_id)
        player.tick += 1
        assessment = self.grace.assess(
            actor=player,
            beneficiary_id=beneficiary_id,
            utility=utility,
            need=need,
            durability=durability,
            sacrifice=sacrifice,
            novelty=novelty,
            chain_depth=chain_depth,
        )
        pair_key = beneficiary_id or player.player_id
        player.recent_pairs[pair_key] = player.recent_pairs.get(pair_key, 0) + 1

        trace_id = hashlib.sha256(
            f"{player.player_id}:{player.tick}:{action}:{beneficiary_id}".encode("utf-8")
        ).hexdigest()[:20]
        trace = GraceTrace(
            trace_id=trace_id,
            actor_id=player.player_id,
            beneficiary_id=beneficiary_id,
            action=action,
            base_utility=assessment.utility_score,
            need=max(0.0, min(1.0, need)),
            durability=max(0.0, min(1.0, durability)),
            sacrifice=max(0.0, min(1.0, sacrifice)),
            novelty=max(0.0, min(1.0, novelty)),
            reciprocity_risk=0.92 if assessment.abuse_suspected else 0.0,
            chain_depth=max(0, chain_depth),
            created_tick=player.tick,
        )
        # Only a small provisional echo arrives immediately; the consequence settles later.
        player.grace += assessment.provisional_grace * 0.20
        player.light = min(1.0, player.light + assessment.utility_score * 0.08)
        player.trust = min(1.0, player.trust + assessment.utility_score * 0.06)
        player.chronicle.append(f"Living Grace trace: {trace_id}")
        self.memory.save_trace(trace)
        self.memory.save_player(player)
        self.memory.append_event(player.player_id, "grace_trace_created", {"trace_id": trace_id, "beneficiary_id": beneficiary_id})

        return WorldResult(
            status="GRACE_PENDING",
            narrative=f"{assessment.reason} Его настоящая ценность проявится по последствиям.",
            realm=player.realm,
            visible_grace=None,
            choices=["Не ждать награды", "Продолжить помощь", "Уйти тихо"],
            branch_id=player.branch_id,
            trace_id=trace_id,
        )

    def settle_consequence(self, trace_id: str, *, realized_impact: float, propagated_good: float = 0.0) -> float:
        trace = self.memory.load_trace(trace_id)
        if trace.settled:
            return 0.0
        awarded = self.grace.settle(trace, realized_impact, propagated_good)
        player = self.memory.load_player(trace.actor_id)
        player.grace += awarded
        if propagated_good > 0:
            player.chronicle.append("Твой свет продолжил жить в чужих поступках.")
        self.memory.save_trace(trace)
        self.memory.save_player(player)
        self.memory.append_event(player.player_id, "grace_trace_settled", {"trace_id": trace_id, "impact": realized_impact, "propagated_good": propagated_good})
        return awarded

    def cast_wish(self, player_id: str, wish: str, *, cost: float, for_other: bool = False) -> WorldResult:
        player = self.memory.load_player(player_id)
        effective_cost = max(0.0, float(cost)) * (0.70 if for_other else 1.0)
        if player.grace + 1e-9 < effective_cost:
            narrative = "Мир слышит просьбу, но пока не может удержать её форму."
            manifested = False
        else:
            player.grace -= effective_cost
            player.chronicle.append(f"Manifested wish: {wish}")
            narrative = "Мир не показывает цену. Он лишь отвечает: просьба обрела форму."
            manifested = True
            self.memory.append_event(player.player_id, "wish_manifested", {"wish": wish, "for_other": for_other})
        self.memory.save_player(player)
        return WorldResult(
            status="MANIFESTED" if manifested else "UNREADY",
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=["Принять ответ мира", "Продолжить путь"],
            branch_id=player.branch_id,
            wish_manifested=manifested,
        )

    def remember_encounter(self, player_id: str, subject_id: str, *, name: str | None = None, trust_delta: float = 0.0, anchor: str | None = None) -> RelationshipMemory:
        player = self.memory.load_player(player_id)
        player.tick += 1
        for memory in player.relationships.values():
            memory.decay(player.tick)
        relation = player.relationships.get(subject_id) or RelationshipMemory(subject_id=subject_id)
        relation.strength = min(1.0, relation.strength + 0.20)
        relation.residual_trust = min(1.0, max(-1.0, relation.residual_trust + trust_delta))
        relation.last_contact_tick = player.tick
        if name:
            relation.known_name = name
        if anchor and anchor not in relation.anchors:
            relation.anchors.append(anchor)
        player.relationships[subject_id] = relation
        self.memory.save_player(player)
        return relation

    def process_action(self, player_id: str, action: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        player.tick += 1
        lowered = action.lower()
        destructive = any(word in lowered for word in ("убить", "сломать", "сжечь", "украсть", "kill", "destroy", "burn", "steal"))
        if destructive:
            result = self.sever(player, action)
        else:
            result = WorldResult(
                status="OBSERVED",
                narrative="Genesis сохранил действие в Хронике и ждёт его последствий.",
                realm=player.realm,
                visible_grace=None,
                choices=["Продолжить", "Помочь кому-то", "Сформулировать желание"],
                branch_id=player.branch_id,
            )
        self.memory.save_player(player)
        return result
