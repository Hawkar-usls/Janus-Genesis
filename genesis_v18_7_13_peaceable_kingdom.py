# -*- coding: utf-8 -*-
"""Peaceable Kingdom animal ecology for Genesis v18.7.13."""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_10 import sha256_canonical

PEACEABLE_KINGDOM_COVENANT: dict[str, Any] = {
    "schema": "janus.genesis.peaceable_kingdom_covenant.v1",
    "version": "18.7.13",
    "name": "The Peaceable Kingdom Covenant",
    "principles": {
        "animals_are_not_property": True,
        "animals_are_not_weapons_or_spectacle": True,
        "predation_is_disabled_inside_covenant_habitats": True,
        "friendship_is_possible_but_never_forced": True,
        "distance_is_a_valid_behavior": True,
        "fear_is_not_used_as_control": True,
        "animal_behavior_is_not_a_consciousness_claim": True,
        "predator_and_gentle_animal_may_share_safety": True,
    },
    "law": (
        "THE LION AND THE LAMB MAY SHARE PEACE WITHOUT BECOMING POSSESSIONS. "
        "NEARNESS MAY GROW, AND DISTANCE MAY STILL BE HONORED."
    ),
}
PEACEABLE_KINGDOM_COVENANT_SHA256 = sha256_canonical(
    PEACEABLE_KINGDOM_COVENANT
)

PEACEABLE_PAIR_KEYS = {
    frozenset({"LION", "LAMB"}),
    frozenset({"LION", "SHEEP"}),
    frozenset({"WOLF", "LAMB"}),
    frozenset({"LEOPARD", "KID_GOAT"}),
    frozenset({"CALF", "YOUNG_LION"}),
    frozenset({"COW", "BEAR"}),
}


class PeaceableKingdomMixin:
    """Let strong and gentle simulated animals share safety without ownership."""

    def create_peaceable_habitat(
        self,
        player_id: str,
        *,
        name: str,
        safety_plan: str,
    ) -> dict[str, Any]:
        clean_name = str(name).strip()[:120]
        if not clean_name:
            raise ValueError("PEACEABLE_HABITAT_NAME_REQUIRED")
        if len(str(safety_plan).strip()) < 12:
            raise ValueError("PEACEABLE_HABITAT_SAFETY_PLAN_REQUIRED")
        store = self._returning_light_store()
        habitats = store.setdefault("habitats", {}).setdefault(str(player_id), {})
        habitat_id = self._rl_fingerprint(
            "peaceable-habitat",
            player_id,
            clean_name,
            safety_plan,
            len(habitats),
        )[:24]
        record = {
            "habitat_id": habitat_id,
            "name": clean_name,
            "peaceable_covenant": copy.deepcopy(PEACEABLE_KINGDOM_COVENANT),
            "peaceable_covenant_sha256": PEACEABLE_KINGDOM_COVENANT_SHA256,
            "safety_plan_sha256": self._rl_fingerprint(safety_plan),
            "pairs": {},
            "animals_are_property": False,
            "animals_are_weapons": False,
            "spectacle_allowed": False,
            "predation_allowed": False,
            "forced_proximity_allowed": False,
            "simulation_consciousness_claim": False,
        }
        habitats[habitat_id] = record
        self._write_returning_light_store(store)
        self.memory.append_event(str(player_id), "peaceable_habitat_created", record)
        return copy.deepcopy(record)

    def welcome_peaceable_pair(
        self,
        player_id: str,
        habitat_id: str,
        *,
        first_kind: str,
        second_kind: str,
        used_for_spectacle: bool = False,
        used_for_combat: bool = False,
    ) -> dict[str, Any]:
        first = str(first_kind).strip().upper()
        second = str(second_kind).strip().upper()
        if frozenset({first, second}) not in PEACEABLE_PAIR_KEYS:
            raise ValueError("UNSUPPORTED_PEACEABLE_PAIR")
        if used_for_spectacle or used_for_combat:
            raise PermissionError(
                "PEACEABLE_ANIMALS_CANNOT_BE_SPECTACLE_OR_WEAPONS"
            )
        store = self._returning_light_store()
        habitat = (
            store.get("habitats", {})
            .get(str(player_id), {})
            .get(str(habitat_id))
        )
        if not isinstance(habitat, dict):
            raise KeyError(habitat_id)
        pair_id = self._rl_fingerprint(
            "peaceable-pair",
            player_id,
            habitat_id,
            first,
            second,
            len(habitat.get("pairs", {})),
        )[:24]
        pair = {
            "pair_id": pair_id,
            "first_kind": first,
            "second_kind": second,
            "status": "PEACEABLE_NEIGHBORS",
            "no_predation": True,
            "mutual_safety": True,
            "friendship_possible": True,
            "friendship_not_forced": True,
            "may_keep_distance": True,
            "ownership_created": False,
            "weaponized": False,
            "spectacle": False,
            "behavioral_assent_events": 0,
            "distance_events": 0,
            "shared_rest_events": 0,
            "history": [],
        }
        habitat.setdefault("pairs", {})[pair_id] = pair
        self._write_returning_light_store(store)
        self.memory.append_event(
            str(player_id),
            "peaceable_animal_pair_welcomed",
            pair,
        )
        return copy.deepcopy(pair)

    def advance_peaceable_habitat(
        self,
        player_id: str,
        habitat_id: str,
        *,
        cycles: int = 1,
    ) -> dict[str, Any]:
        count = int(cycles)
        if count < 1 or count > 365:
            raise ValueError("PEACEABLE_CYCLES_OUT_OF_RANGE")
        store = self._returning_light_store()
        habitat = (
            store.get("habitats", {})
            .get(str(player_id), {})
            .get(str(habitat_id))
        )
        if not isinstance(habitat, dict):
            raise KeyError(habitat_id)
        events: list[dict[str, Any]] = []
        behaviors = (
            "SHARED_WATER",
            "REST_NEAR_WITH_EXIT",
            "PLAY_WITHOUT_CHASE",
            "KEEP_DISTANCE",
        )
        for cycle in range(count):
            for pair in habitat.get("pairs", {}).values():
                index = int(
                    self._rl_fingerprint(
                        "peaceable-behavior",
                        player_id,
                        habitat_id,
                        pair["pair_id"],
                        len(pair.get("history", [])),
                        cycle,
                    ),
                    16,
                ) % len(behaviors)
                behavior = behaviors[index]
                event = {
                    "event_id": self._rl_fingerprint(
                        "peaceable-event",
                        pair["pair_id"],
                        behavior,
                        len(pair.get("history", [])),
                    )[:24],
                    "pair_id": pair["pair_id"],
                    "behavior": behavior,
                    "predation": False,
                    "fear_used_as_control": False,
                    "forced_proximity": False,
                    "consciousness_claimed": False,
                }
                if behavior == "KEEP_DISTANCE":
                    pair["distance_events"] = int(pair["distance_events"]) + 1
                else:
                    pair["behavioral_assent_events"] = int(
                        pair["behavioral_assent_events"]
                    ) + 1
                    if behavior == "REST_NEAR_WITH_EXIT":
                        pair["shared_rest_events"] = int(
                            pair["shared_rest_events"]
                        ) + 1
                if (
                    int(pair["behavioral_assent_events"]) >= 3
                    and int(pair["shared_rest_events"]) >= 1
                ):
                    pair["status"] = "PEACEABLE_FRIENDS_WITH_OPEN_DISTANCE"
                pair.setdefault("history", []).append(event)
                events.append(copy.deepcopy(event))
        self._write_returning_light_store(store)
        for event in events:
            self.memory.append_event(
                str(player_id),
                "peaceable_animal_behavior",
                event,
            )
        return {
            "cycles": count,
            "events": events,
            "habitat": copy.deepcopy(habitat),
            "predation_events": 0,
        }

    def peaceable_witness_encounter(
        self,
        player_id: str,
        habitat_id: str,
        recipient_player_id: str,
    ) -> dict[str, Any]:
        assessment = self.oracle_assessment(str(recipient_player_id))
        store = self._returning_light_store()
        habitat = (
            store.get("habitats", {})
            .get(str(player_id), {})
            .get(str(habitat_id))
        )
        if not isinstance(habitat, dict):
            raise KeyError(habitat_id)
        pair_count = len(habitat.get("pairs", {}))
        event = {
            "encounter_id": self._rl_fingerprint(
                "peaceable-witness",
                player_id,
                habitat_id,
                recipient_player_id,
                pair_count,
            )[:24],
            "recipient_player_id": str(recipient_player_id),
            "support_stage": assessment["support_stage"],
            "animals_judged_moral_identity": False,
            "animals_forced_to_approach": False,
            "comfort_available": pair_count > 0,
            "material_aid_created": False,
            "debt_created": False,
            "predation": False,
        }
        self.memory.append_event(
            str(player_id),
            "peaceable_witness_encounter",
            event,
        )
        return event

    def audit_peaceable_kingdom(self, player_id: str) -> dict[str, Any]:
        store = self._returning_light_store()
        habitats = copy.deepcopy(
            store.get("habitats", {}).get(str(player_id), {})
        )
        pair_count = 0
        for habitat in habitats.values():
            if habitat.get("animals_are_property"):
                raise RuntimeError("PEACEABLE_ANIMALS_CANNOT_BE_PROPERTY")
            if habitat.get("animals_are_weapons"):
                raise RuntimeError("PEACEABLE_ANIMALS_CANNOT_BE_WEAPONS")
            if habitat.get("predation_allowed"):
                raise RuntimeError("PEACEABLE_HABITAT_CANNOT_ALLOW_PREDATION")
            for pair in habitat.get("pairs", {}).values():
                pair_count += 1
                if not pair.get("no_predation"):
                    raise RuntimeError("PEACEABLE_PAIR_PREDATION_FORBIDDEN")
                if pair.get("ownership_created") or pair.get("weaponized"):
                    raise RuntimeError(
                        "PEACEABLE_ANIMAL_OWNERSHIP_OR_WEAPON_FORBIDDEN"
                    )
        return {
            "schema": "janus.genesis.peaceable_kingdom_audit.v1",
            "player_id": str(player_id),
            "covenant_sha256": PEACEABLE_KINGDOM_COVENANT_SHA256,
            "habitat_count": len(habitats),
            "pair_count": pair_count,
            "predation_events": 0,
            "animals_are_property": False,
            "animals_are_weapons": False,
            "friendship_forced": False,
            "valid": True,
        }
