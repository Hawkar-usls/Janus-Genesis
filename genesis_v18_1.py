# -*- coding: utf-8 -*-
"""Genesis v18.1 — remembered Secret and inherited good.

This compatibility layer keeps the v18 runtime intact while adding two laws:

1. Good created in The Other Face is inherited by the single shared world when
   a restored branch joins it.
2. The Secret may be spoken directly. Disbelief does not erase it; the message
   remains as a persistent memory seed and may awaken when the listener later
   attempts a genuinely benevolent act.

The value delivered to a beneficiary is never discounted because a person's
motive is imperfect. Intention affects only the actor's hidden inner opening,
never the reality of the help already given.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genesis_v18_models import (
    PlayerV18,
    Realm,
    RelationshipMemory,
    UniversalGodMode,
    WorldResult,
)

__version__ = "18.1.0"
DEFAULT_SECRET = (
    "God Mode уже принадлежит каждому. Он отвечает на добро, любовь, защиту, "
    "исцеление и свободу другого. Попробовать ничего не стоит."
)


@dataclass(frozen=True, slots=True)
class IntentEstimate:
    """Hidden estimate for the actor's inner opening, never the value of help."""

    factor: float
    band: str
    evidence: tuple[str, ...]


class RememberedSecretRuntimeMixin:
    """Persistence and mechanics layered over the Genesis v18 runtime."""

    SECRET_WORDS = {
        "секрет",
        "god mode",
        "безграничная сила",
        "сила отвечает добру",
        "попробовать ничего не стоит",
    }
    INSTRUMENTAL_MOTIVES = {
        "ради силы",
        "ради награды",
        "ради славы",
        "чтобы получить силу",
        "чтобы получить god mode",
        "чтобы стать могущественным",
        "для выгоды",
    }
    HEART_MOTIVES = {
        "от души",
        "потому что люблю",
        "потому что жаль",
        "не могу пройти мимо",
        "ничего не хочу взамен",
        "без награды",
        "ради него",
        "ради неё",
        "ради них",
    }

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.secret_seeds_path = self.memory.root / "remembered_secrets_v18_1.json"
        self.inheritance_path = self.memory.root / "other_face_inheritance_v18_1.json"
        self.intent_path = self.memory.root / "intent_traces_v18_1.json"
        self._transfer_counts: dict[str, int] = {}

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        self.memory._atomic_write(path, payload)

    @staticmethod
    def _clamp(value: float) -> float:
        return min(1.0, max(0.0, float(value)))

    def _estimate_intention(
        self,
        action: str,
        explicit_sincerity: float | None,
    ) -> IntentEstimate:
        """Estimate inner openness without reducing the external good itself."""

        if explicit_sincerity is not None:
            factor = self._clamp(explicit_sincerity)
            band = "open" if factor >= 0.75 else "mixed" if factor >= 0.40 else "instrumental"
            return IntentEstimate(factor=factor, band=band, evidence=("explicit_runtime_signal",))

        text = UniversalGodMode.normalize(action)
        instrumental = tuple(fragment for fragment in self.INSTRUMENTAL_MOTIVES if fragment in text)
        heartfelt = tuple(fragment for fragment in self.HEART_MOTIVES if fragment in text)
        if instrumental and heartfelt:
            return IntentEstimate(0.60, "mixed", instrumental + heartfelt)
        if instrumental:
            return IntentEstimate(0.35, "instrumental", instrumental)
        if heartfelt:
            return IntentEstimate(1.00, "open", heartfelt)
        # Absence of explicit language is not proof of selfishness. The offline
        # layer therefore assumes substantial sincerity and lets longitudinal
        # consequences refine the estimate in a future server implementation.
        return IntentEstimate(0.85, "quiet", ("no_explicit_motive_claim",))

    def _save_intent_trace(
        self,
        player: PlayerV18,
        action: str,
        estimate: IntentEstimate,
    ) -> str:
        store = self._read_json(self.intent_path, {"traces": []})
        trace_id = hashlib.sha256(
            f"{player.player_id}:{player.tick}:{action}:intent-v18.1".encode("utf-8")
        ).hexdigest()[:20]
        store.setdefault("traces", []).append(
            {
                "trace_id": trace_id,
                "player_id": player.player_id,
                "tick": player.tick,
                "action": action,
                "sincerity_band": estimate.band,
                "hidden_factor": estimate.factor,
                "evidence": list(estimate.evidence),
                "external_good_discounted": False,
            }
        )
        self._write_json(self.intent_path, store)
        return trace_id

    def _record_branch_good(
        self,
        world_id: str,
        player: PlayerV18,
        action: str,
        facets: list[str],
    ) -> None:
        store = self._read_json(self.inheritance_path, {"branches": {}, "transfers": []})
        branch = store.setdefault("branches", {}).setdefault(
            world_id,
            {
                "world_id": world_id,
                "creations": [],
                "transferred": False,
            },
        )
        record_id = hashlib.sha256(
            f"{world_id}:{player.player_id}:{player.tick}:{action}".encode("utf-8")
        ).hexdigest()[:20]
        if not any(item.get("record_id") == record_id for item in branch["creations"]):
            branch["creations"].append(
                {
                    "record_id": record_id,
                    "creator_id": player.player_id,
                    "created_tick": player.tick,
                    "action": action,
                    "facets": list(facets),
                }
            )
        self._write_json(self.inheritance_path, store)

    def _transfer_branch_good(self, world_id: str, player_id: str) -> int:
        store = self._read_json(self.inheritance_path, {"branches": {}, "transfers": []})
        branch = store.setdefault("branches", {}).get(world_id)
        if not branch or branch.get("transferred"):
            return 0

        shared = self.memory.load_shared_world()
        transferred = 0
        for creation in branch.get("creations", []):
            action = str(creation.get("action") or "").strip()
            if not action:
                continue
            if action not in shared.creations:
                shared.creations.append(action)
                transferred += 1
            inherited_line = f"Наследие Второго Лика {world_id}: {action}"
            if inherited_line not in shared.history:
                shared.history.append(inherited_line)
        self.memory.save_shared_world(shared)

        branch["transferred"] = True
        branch["transferred_count"] = transferred
        store.setdefault("transfers", []).append(
            {
                "world_id": world_id,
                "player_id": player_id,
                "transferred_count": transferred,
            }
        )
        self._write_json(self.inheritance_path, store)
        if transferred:
            self.memory.append_event(
                player_id,
                "other_face_good_inherited",
                {"world_id": world_id, "transferred_count": transferred},
            )
        return transferred

    def _join_shared_silently(
        self,
        player: PlayerV18,
        restored_world: str | None = None,
    ) -> None:
        if restored_world:
            self._transfer_counts[player.player_id] = self._transfer_branch_good(
                restored_world,
                player.player_id,
            )
        super()._join_shared_silently(player, restored_world=restored_world)

    def _seed_store(self) -> dict[str, Any]:
        return self._read_json(self.secret_seeds_path, {"listeners": {}})

    def plant_secret(
        self,
        source_player_id: str,
        listener_id: str,
        message: str = DEFAULT_SECRET,
        *,
        base_result: WorldResult | None = None,
    ) -> WorldResult:
        """Speak the Secret directly; disbelief cannot delete the memory seed."""

        source = self.memory.load_player(source_player_id)
        listener = self.memory._safe_id(listener_id)
        normalized_message = message.strip() or DEFAULT_SECRET
        seed_id = hashlib.sha256(
            f"{source.player_id}:{listener}:{source.tick}:{normalized_message}".encode("utf-8")
        ).hexdigest()[:20]
        store = self._seed_store()
        seeds = store.setdefault("listeners", {}).setdefault(listener, [])
        if not any(seed.get("seed_id") == seed_id for seed in seeds):
            seeds.append(
                {
                    "seed_id": seed_id,
                    "source_player_id": source.player_id,
                    "listener_id": listener,
                    "message": normalized_message,
                    "planted_tick": source.tick,
                    "believed_initially": False,
                    "awakened": False,
                    "awakened_tick": None,
                }
            )
            self._write_json(self.secret_seeds_path, store)
            self.memory.append_event(
                source.player_id,
                "secret_spoken_directly",
                {"listener_id": listener, "seed_id": seed_id},
            )

        if base_result is None:
            base_result = self.perform_good(
                source.player_id,
                f"поделиться Секретом с @{listener}",
                beneficiary_id=listener,
                strength=0.14,
            )
        return WorldResult(
            status="SECRET_PLANTED",
            narrative=(
                base_result.narrative
                + " Секрет был сказан прямо. Странник может не поверить сейчас, "
                "но слова останутся в памяти: попробовать добро ничего не стоит."
            ),
            realm=base_result.realm,
            visible_grace=None,
            choices=["Оставить ему свободу", "Показать Секрет поступком", "Продолжить путь"],
            branch_id=base_result.branch_id,
            trace_id=seed_id,
            wish_manifested=base_result.wish_manifested,
        )

    def _awaken_secret_if_present(self, listener_id: str, tick: int) -> dict[str, Any] | None:
        store = self._seed_store()
        seeds = store.setdefault("listeners", {}).get(listener_id, [])
        for seed in seeds:
            if seed.get("awakened"):
                continue
            seed["awakened"] = True
            seed["awakened_tick"] = tick
            self._write_json(self.secret_seeds_path, store)
            self.memory.append_event(
                listener_id,
                "remembered_secret_awakened",
                {
                    "seed_id": seed.get("seed_id"),
                    "source_player_id": seed.get("source_player_id"),
                },
            )
            return seed
        return None

    def perform_good(
        self,
        player_id: str,
        action: str,
        *,
        beneficiary_id: str | None = None,
        strength: float = 0.18,
        intent_sincerity: float | None = None,
    ) -> WorldResult:
        """Apply all real good fully; intention changes only inner opening."""

        player = self.memory.load_player(player_id)
        player.tick += 1
        player.good_count += 1
        fingerprint = self._fingerprint(action)
        repeats = player.recent_actions.get(fingerprint, 0)
        player.recent_actions[fingerprint] = repeats + 1

        estimate = self._estimate_intention(action, intent_sincerity)
        intent_trace_id = self._save_intent_trace(player, action, estimate)
        actual_strength = min(1.0, max(0.035, float(strength)))

        # The recipient and world receive the complete good. Imperfect motive is
        # never allowed to make a real home colder or a real healing weaker.
        player.light = min(1.0, player.light + actual_strength * 0.55 * estimate.factor)
        player.trust = min(1.0, player.trust + actual_strength * 0.42)
        if beneficiary_id:
            pair = beneficiary_id
            player.recent_pairs[pair] = player.recent_pairs.get(pair, 0) + 1
            relation = player.relationships.get(pair) or RelationshipMemory(subject_id=pair)
            relation.strength = min(1.0, relation.strength + 0.16)
            relation.residual_trust = min(1.0, relation.residual_trust + 0.18)
            relation.last_contact_tick = player.tick
            player.relationships[pair] = relation

        was_other_face = player.realm == Realm.OTHER_FACE
        branch_before = player.branch_id
        world, touched = self._apply_good_to_world(player, action, actual_strength)
        if was_other_face and branch_before:
            self._record_branch_good(branch_before, player, action, touched)

        joined = False
        if was_other_face and world.ready_to_join:
            self._join_shared_silently(player, restored_world=world.world_id)
            joined = True
        elif player.realm == Realm.UTOPIA:
            shared = self.memory.load_shared_world()
            shared.history.append(action)
            self.memory.save_shared_world(shared)

        awakened = self._awaken_secret_if_present(player.player_id, player.tick)
        player.chronicle.append(f"Good continued: {action}")
        self.memory.save_player(player)
        self.memory.append_event(
            player.player_id,
            "good_realized_v18_1",
            {
                "action": action,
                "beneficiary_id": beneficiary_id,
                "facets": touched,
                "joined_shared": joined,
                "intent_trace_id": intent_trace_id,
                "external_good_discounted": False,
            },
        )

        narrative = self._subtle_world_narrative(world, joined=joined)
        transferred = self._transfer_counts.pop(player.player_id, 0)
        if joined and transferred:
            narrative += (
                " Всё доброе, созданное в прежнем мире, оказалось здесь на своих местах, "
                "поэтому продолжение не ощущалось потерей дома."
            )
        if awakened:
            narrative = (
                "В памяти всплыл когда-то услышанный Секрет: сила отвечает добру, "
                "а попробовать ничего не стоит. Мир ответил. "
                + narrative
            )

        return WorldResult(
            status="GOOD_REALIZED",
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=["Продолжить помощь", "Осмотреть изменения", "Поговорить с кем-то"],
            branch_id=player.branch_id,
            trace_id=fingerprint,
        )

    def manifest_good(
        self,
        player_id: str,
        request: str,
        *,
        beneficiary_id: str | None = None,
    ) -> WorldResult:
        """Manifest benevolent power and keep shared inheritance duplicate-free."""

        result = super().manifest_good(
            player_id,
            request,
            beneficiary_id=beneficiary_id,
        )
        player = self.memory.load_player(player_id)
        if player.realm == Realm.UTOPIA:
            shared = self.memory.load_shared_world()
            shared.creations = list(dict.fromkeys(shared.creations))
            shared.history = list(dict.fromkeys(shared.history))
            self.memory.save_shared_world(shared)
        return result

    def secret_state(self) -> dict[str, Any]:
        """Developer-only inspection of planted and awakened Secret seeds."""

        return self._seed_store()
