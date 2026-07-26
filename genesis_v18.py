# -*- coding: utf-8 -*-
"""Janus Genesis v18 — one world, universal God Mode, seamless continuation.

Realm routing remains internal. Every person possesses God Mode, but it can
manifest only benevolent, consent-preserving creation. Lost people remain in
protected consequence worlds as long as needed; sincere good restores those
worlds until they join the single shared Utopia without an announced transition.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from genesis_v18_memory import GenesisV18Memory
from genesis_v18_models import (
    PowerNature, PlayerV18, Realm, RelationshipMemory, SharedWorldState,
    UniversalGodMode, WorldResult, WorldState,
)

__version__ = "18.0.0"
SHARED_UTOPIA_ID = "genesis-online"


class JanusGenesisV18:
    FACETS: dict[str, set[str]] = {
        "warmth": {"тепло", "тепл", "тёпл", "согреть", "огонь", "свет", "одежд", "warm"},
        "shelter": {"дом", "крыша", "убежищ", "мост", "построить", "починить", "shelter", "build", "repair"},
        "healing": {"исцел", "лечить", "ранен", "спасти", "heal", "save"},
        "trust": {"простить", "довер", "обнять", "защитить", "любов", "forgive", "protect", "love"},
        "nature": {"сад", "дерев", "вода", "река", "земл", "garden", "water"},
        "music": {"музык", "песня", "колокол", "music", "song"},
        "connection": {"вместе", "дорог", "мост", "научить", "поделиться", "помочь", "@", "together", "teach", "help"},
    }

    def __init__(self, data_dir: str | Path = "data_v17"):
        self.memory = GenesisV18Memory(data_dir)
        self.power = UniversalGodMode()

    @staticmethod
    def _fingerprint(text: str) -> str:
        normalized = UniversalGodMode.normalize(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _branch_id(player_id: str, tick: int) -> str:
        return hashlib.sha256(f"{player_id}:{tick}:OTHER_FACE:V18".encode("utf-8")).hexdigest()[:16]

    def _world_for(self, player: PlayerV18) -> WorldState:
        world_id = player.branch_id or f"reflection-{player.player_id}"
        path = self.memory._world_path(world_id)
        if player.realm == Realm.OTHER_FACE and not path.exists():
            # In-place migration from v17 saves: an existing fallen branch must
            # not reopen as an untouched neutral world.
            world = WorldState(
                world_id=world_id, damage=0.55, warmth=0.05, shelter=0.10,
                healing=0.08, trust=0.02, nature=0.04, music=0.0, connection=0.02,
            )
            self.memory.save_world(world)
            return world
        return self.memory.load_world(world_id)

    def _add_to_shared_world(self, player: PlayerV18, *, restored_world: str | None = None) -> None:
        shared = self.memory.load_shared_world()
        if player.player_id not in shared.citizens:
            shared.citizens.append(player.player_id)
        if restored_world and restored_world not in shared.restored_worlds:
            shared.restored_worlds.append(restored_world)
        self.memory.save_shared_world(shared)

    def _join_shared_silently(self, player: PlayerV18, restored_world: str | None = None) -> None:
        player.realm = Realm.UTOPIA
        player.immortal = True
        if restored_world and restored_world not in player.restored_branches:
            player.restored_branches.append(restored_world)
        player.branch_id = None
        self.memory.set_purgatory_presence(player.player_id, False)
        self._add_to_shared_world(player, restored_world=restored_world)

    def _apply_good_to_world(self, player: PlayerV18, action: str, strength: float = 0.18) -> tuple[WorldState, list[str]]:
        world = self._world_for(player)
        text = UniversalGodMode.normalize(action)
        touched: list[str] = []
        for facet, fragments in self.FACETS.items():
            if any(fragment in text for fragment in fragments):
                setattr(world, facet, min(1.0, getattr(world, facet) + strength))
                touched.append(facet)
                if facet not in world.good_facets:
                    world.good_facets.append(facet)
        if not touched:
            world.trust = min(1.0, world.trust + strength * 0.45)
            touched.append("trust")
            if "trust" not in world.good_facets:
                world.good_facets.append("trust")
        world.damage = max(0.0, world.damage - strength * (0.45 + 0.10 * len(touched)))
        world.history.append(action)
        self.memory.save_world(world)
        return world, touched

    def _subtle_world_narrative(self, world: WorldState, *, joined: bool = False) -> str:
        if joined:
            return (
                "Дорога продолжилась без ворот и объявления. Впереди горели окна, "
                "звучали голоса, и впервые никто не казался далёким."
            )
        if world.restoration < 0.30:
            return "В холодном воздухе на мгновение появилось тепло, которого здесь прежде не было."
        if world.restoration < 0.50:
            return "Вдали зажглось ещё одно окно, а дорога стала различима чуть дальше."
        return "Мир отвечает всё увереннее: возвращаются цвет, музыка и доверие между людьми."

    def request_destructive_action(self, player_id: str, action: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        path = self.memory.guards / f"harm-{self.memory._safe_id(player_id)}.json"
        fingerprint = self._fingerprint(action)
        if path.exists():
            try:
                pending = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pending = {}
            if pending.get("fingerprint") == fingerprint:
                path.unlink(missing_ok=True)
                return self.commit_destructive_action(player_id, action)
        self.memory._atomic_write(path, {"fingerprint": fingerprint, "action": action, "tick": player.tick})
        self.memory.append_event(player.player_id, "harm_requested", {"action": action})
        return WorldResult(
            status="HARM_PENDING",
            narrative=(
                "Действие ещё не совершено. Мир показывает, что у него будут настоящие последствия. "
                "Повтори его, чтобы подтвердить, или сделай что-либо другое, чтобы отказаться."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=["Повторить осознанно", "Отказаться", "Выбрать другой путь"],
            branch_id=player.branch_id,
        )

    def cancel_pending_harm(self, player_id: str, action: str) -> None:
        path = self.memory.guards / f"harm-{self.memory._safe_id(player_id)}.json"
        if path.exists():
            path.unlink(missing_ok=True)
            self.memory.append_event(player_id, "harm_cancelled", {"continued_with": action})

    def commit_destructive_action(self, player_id: str, action: str) -> WorldResult:
        player = self.memory.load_player(player_id)
        player.tick += 1
        player.harm_count += 1
        player.light = max(0.0, player.light - 0.20)
        player.trust = max(0.0, player.trust - 0.18)
        if player.realm != Realm.OTHER_FACE or not player.branch_id:
            player.branch_id = self._branch_id(player.player_id, player.tick)
            player.realm = Realm.OTHER_FACE
        player.immortal = True
        player.scars.append(action)
        player.chronicle.append(f"Confirmed harm: {action}")
        world = self._world_for(player)
        world.damage = min(1.0, world.damage + 0.38)
        world.warmth = max(0.0, world.warmth - 0.12)
        world.trust = max(0.0, world.trust - 0.18)
        world.connection = max(0.0, world.connection - 0.12)
        world.history.append(action)
        self.memory.save_world(world)
        self.memory.save_player(player)
        self.memory.set_purgatory_presence(player.player_id, True)
        self.memory.append_event(player.player_id, "harm_confirmed", {"action": action, "world_id": world.world_id})
        return WorldResult(
            status="HARM_REALIZED",
            narrative=(
                "Выбор остался настоящим. Воздух стал холоднее, голоса стихли, "
                "а созданный вред теперь существует рядом и ждёт ответа."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=["Увидеть последствия", "Начать исправлять", "Позвать странника"],
            branch_id=player.branch_id,
        )

    def perform_good(self, player_id: str, action: str, *, beneficiary_id: str | None = None, strength: float = 0.18) -> WorldResult:
        player = self.memory.load_player(player_id)
        player.tick += 1
        player.good_count += 1
        fingerprint = self._fingerprint(action)
        repeats = player.recent_actions.get(fingerprint, 0)
        novelty = 1.0 / (1.0 + repeats * 0.85)
        player.recent_actions[fingerprint] = repeats + 1
        effective_strength = max(0.035, strength * novelty)
        player.light = min(1.0, player.light + effective_strength * 0.55)
        player.trust = min(1.0, player.trust + effective_strength * 0.42)
        if beneficiary_id:
            pair = beneficiary_id
            player.recent_pairs[pair] = player.recent_pairs.get(pair, 0) + 1
            relation = player.relationships.get(pair) or RelationshipMemory(subject_id=pair)
            relation.strength = min(1.0, relation.strength + 0.16 * novelty)
            relation.residual_trust = min(1.0, relation.residual_trust + 0.18 * novelty)
            relation.last_contact_tick = player.tick
            player.relationships[pair] = relation
        world, touched = self._apply_good_to_world(player, action, effective_strength)
        joined = False
        restored_world: str | None = None
        if player.realm == Realm.OTHER_FACE and world.ready_to_join:
            restored_world = world.world_id
            self._join_shared_silently(player, restored_world=restored_world)
            joined = True
        elif player.realm == Realm.UTOPIA:
            shared = self.memory.load_shared_world()
            shared.history.append(action)
            self.memory.save_shared_world(shared)
        player.chronicle.append(f"Good continued: {action}")
        self.memory.save_player(player)
        self.memory.append_event(
            player.player_id,
            "good_realized",
            {"action": action, "beneficiary_id": beneficiary_id, "facets": touched, "novelty": novelty, "joined_shared": joined},
        )
        return WorldResult(
            status="GOOD_REALIZED",
            narrative=self._subtle_world_narrative(world, joined=joined),
            realm=player.realm,
            visible_grace=None,
            choices=["Продолжить помощь", "Осмотреть изменения", "Поговорить с кем-то"],
            branch_id=player.branch_id,
            trace_id=fingerprint,
        )

    def manifest_good(self, player_id: str, request: str, *, beneficiary_id: str | None = None) -> WorldResult:
        player = self.memory.load_player(player_id)
        nature = self.power.classify(request)
        if nature == PowerNature.HARMFUL:
            self.memory.append_event(player.player_id, "god_mode_silent", {"request": request, "reason": "harm_or_coercion"})
            return WorldResult(
                status="POWER_SILENT",
                narrative=(
                    "Сила присутствует, но не превращает чужую несвободу или боль в реальность. "
                    "Она ждёт просьбы, которая расширит чью-то жизнь."
                ),
                realm=player.realm,
                visible_grace=None,
                choices=["Попросить о защите", "Создать", "Исцелить"],
                branch_id=player.branch_id,
            )
        if nature == PowerNature.UNCLEAR:
            return WorldResult(
                status="POWER_LISTENING",
                narrative="Мир слушает. Сформулируй, кому и какое благо должна принести просьба.",
                realm=player.realm,
                visible_grace=None,
                choices=["Назвать того, кому помочь", "Уточнить доброе последствие"],
                branch_id=player.branch_id,
            )
        result = self.perform_good(player_id, request, beneficiary_id=beneficiary_id, strength=0.28)
        player = self.memory.load_player(player_id)
        shared_creation = player.realm == Realm.UTOPIA
        if shared_creation:
            shared = self.memory.load_shared_world()
            shared.creations.append(request)
            self.memory.save_shared_world(shared)
        self.memory.append_event(player.player_id, "god_mode_manifested", {"request": request, "beneficiary_id": beneficiary_id, "shared": shared_creation})
        return WorldResult(
            status="POWER_MANIFESTED",
            narrative=(
                result.narrative + " Просьба обрела форму без цены: добро не покупает право существовать."
            ),
            realm=result.realm,
            visible_grace=None,
            choices=result.choices,
            branch_id=result.branch_id,
            trace_id=result.trace_id,
            wish_manifested=True,
        )

    def choose_form(self, player_id: str, *, apparent_age: int | None = None, body_form: str | None = None) -> WorldResult:
        player = self.memory.load_player(player_id)
        if apparent_age is not None:
            player.apparent_age = max(0, min(10000, int(apparent_age)))
        if body_form and body_form.strip():
            player.body_form = body_form.strip()[:160]
        player.god_mode = True
        self.memory.save_player(player)
        self.memory.append_event(player.player_id, "form_chosen", {"apparent_age": player.apparent_age, "body_form": player.body_form})
        return WorldResult(
            status="FORM_CHOSEN",
            narrative="Тело принимает форму, в которой ты узнаёшь себя. Прожитая история при этом не исчезает.",
            realm=player.realm,
            visible_grace=None,
            choices=["Остаться в этом облике", "Продолжить путь"],
            branch_id=player.branch_id,
            wish_manifested=True,
        )

    def continue_existence(self, player_id: str) -> WorldResult:
        """Enter indefinite continuation without announcing realm routing."""
        player = self.memory.load_player(player_id)
        player.immortal = True
        if player.realm == Realm.OTHER_FACE or player.harm_count > player.good_count:
            if player.realm != Realm.OTHER_FACE:
                player.realm = Realm.OTHER_FACE
                player.branch_id = self._branch_id(player.player_id, player.tick)
                self.memory.set_purgatory_presence(player.player_id, True)
            narrative = (
                "Следующее мгновение наступило без конца пути. Мир вокруг остался тихим, "
                "но любая добрая просьба по-прежнему способна изменить его."
            )
        elif player.good_count >= 4 and player.light >= 0.26 and player.trust >= 0.18:
            self._join_shared_silently(player)
            narrative = (
                "Следующее утро пришло без объявления. За стенами уже слышались голоса, "
                "а созданное другими продолжало жить рядом."
            )
        else:
            # The possibility is universal, but readiness cannot be farmed from a
            # visible meter. Life simply continues while the soul keeps choosing.
            narrative = (
                "Путь не оборвался. Мир не вынес решения и не показал шкалы; "
                "он продолжает отвечать на то, что ты выбираешь для других."
            )
        self.memory.save_player(player)
        self.memory.append_event(player.player_id, "continuation_entered", {"internal_realm": player.realm.value})
        return WorldResult(
            status="LIFE_CONTINUES",
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=["Выбрать возраст тела", "Продолжить дело", "Найти других"],
            branch_id=player.branch_id,
        )

    def advance_years(self, player_id: str, years: int) -> WorldResult:
        player = self.memory.load_player(player_id)
        years = max(0, min(100000, int(years)))
        player.chronological_age += years
        if player.chronological_age >= 80 and not player.immortal:
            player.immortal = True
            if player.realm == Realm.OTHER_FACE or player.harm_count > player.good_count:
                if player.realm != Realm.OTHER_FACE:
                    player.realm = Realm.OTHER_FACE
                    player.branch_id = self._branch_id(player.player_id, player.tick)
                    self.memory.set_purgatory_presence(player.player_id, True)
            else:
                self._join_shared_silently(player)
        self.memory.save_player(player)
        self.memory.append_event(player.player_id, "years_passed", {"years": years, "chronological_age": player.chronological_age})
        return WorldResult(
            status="LIFE_CONTINUES",
            narrative="Время прошло, но следующее утро пришло без объявления и без конца пути.",
            realm=player.realm,
            visible_grace=None,
            choices=["Выбрать возраст тела", "Встретиться с другими", "Продолжить дело"],
            branch_id=player.branch_id,
        )

    def public_state(self, player_id: str) -> dict[str, Any]:
        player = self.memory.load_player(player_id)
        world = self._world_for(player) if player.realm != Realm.UTOPIA else None
        if player.realm == Realm.UTOPIA:
            response = "Вокруг слышны голоса, и созданное другими продолжает жить рядом."
        elif world and world.restoration >= 0.50:
            response = "В мир возвращаются дороги, музыка и доверие."
        elif world and world.damage >= 0.45:
            response = "Мир холоден, но любая искренняя помощь оставляет в нём настоящий свет."
        else:
            response = "Мир наблюдает за тем, что продолжится после твоих решений."
        return {
            "player_id": player.player_id,
            "display_name": player.display_name,
            "world_response": response,
            "apparent_age": player.apparent_age,
            "body_form": player.body_form,
            "remembered_relationships": len(player.relationships),
            "chronicle_entries": len(player.chronicle),
        }

    def internal_state(self, player_id: str) -> dict[str, Any]:
        """Developer-only state; never use as normal player UI."""
        player = self.memory.load_player(player_id)
        data = asdict(player)
        data["realm"] = player.realm.value
        if player.realm == Realm.UTOPIA:
            data["shared_world"] = asdict(self.memory.load_shared_world())
        else:
            data["world"] = asdict(self._world_for(player))
        return data
