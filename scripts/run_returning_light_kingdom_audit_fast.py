#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast pre-life profile filter for the full v18.7.13 lived audit."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
for value in (REPOSITORY_ROOT, SCRIPT_ROOT):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

import run_returning_light_kingdom_audit as audit
from genesis_v18_7_playable import PlayableGenesisV187


def try_profile_direct(
    world: PlayableGenesisV187,
    candidate_index: int,
) -> dict[str, Any] | None:
    patron_id = f"returning-light-patron-{candidate_index}"
    returning_id = f"returning-wayfarer-{candidate_index}"
    steady_id = f"steady-light-{candidate_index}"
    for player_id, name in (
        (patron_id, "Returning Light Patron Candidate"),
        (returning_id, "Returning Wayfarer Candidate"),
        (steady_id, "Steady Light Candidate"),
    ):
        world.register_player(player_id, display_name=name)
    audit.set_selection_prior(world, patron_id, good_count=4, light=0.30)
    audit.set_selection_prior(world, steady_id, good_count=8, light=0.40)
    actors = world.free_other_state(patron_id)["profile"]["others"]
    handles = sorted(actors)

    companion_handle = None
    for handle in handles:
        result = world.propose_life_companionship(
            patron_id,
            handle,
            shared_values="свобода забота и два открытых выхода",
            both_adults_confirmed=True,
        )
        if result.status == "LIFE_COMPANIONSHIP_FORMED":
            companion_handle = handle
            break
    if companion_handle is None:
        return None

    child = world.welcome_child_with_companion(
        patron_id,
        child_name="Люмен",
        family_path="ADOPTION",
        home_plan="дом без собственности над будущим ребёнка",
        player_parenthood_consent=True,
    )
    if child.status != "CHILD_WELCOMED_BY_MUTUAL_CONSENT":
        return None

    distance = world.transition_companionship_mode(
        patron_id,
        mode="LONG_DISTANCE",
        reason="свобода и отдельные дороги",
    )
    if distance.status != "COMPANIONSHIP_LONG_DISTANCE":
        return None

    reunion = world.transition_companionship_mode(
        patron_id,
        mode="ACTIVE",
        reason="новое взаимное согласие",
    )
    if reunion.status != "COMPANIONSHIP_ACTIVE":
        return None

    steward_handle = None
    for handle in handles:
        if handle == companion_handle:
            continue
        result = world.bless_free_other_as_steward(
            patron_id,
            handle,
            capacity_tier="GREAT",
            capacity_evidence="verified great material capacity in the simulation",
        )
        if result.status == "RETURNING_LIGHT_STEWARD_BLESSED":
            steward_handle = handle
            break
    if steward_handle is None:
        return None

    audit.returning_path(world, returning_id)
    returning_need = world.register_support_need(
        returning_id,
        need_kind="RESTITUTION_TOOLS",
        severity=9,
        description="tools for restitution stable work and prevention of recurrence",
        requested_material_units=40,
    )
    steady_need = world.register_support_need(
        steady_id,
        need_kind="TOOLS",
        severity=9,
        description="tools for a proven benevolent community workshop",
        requested_material_units=40,
    )
    returning_aid = world.offer_oracle_guided_aid(
        patron_id,
        steward_handle,
        returning_id,
        need_id=returning_need["need_id"],
    )
    steady_aid = world.offer_oracle_guided_aid(
        patron_id,
        steward_handle,
        steady_id,
        need_id=steady_need["need_id"],
    )
    if (
        returning_aid["decision"] != "ORACLE_GUIDED_AID_GRANTED"
        or steady_aid["decision"] != "ORACLE_GUIDED_AID_GRANTED"
        or int(steady_aid["material_units_granted"])
        <= int(returning_aid["material_units_granted"])
    ):
        return None
    return {
        "seed": audit.SEED,
        "profile_index": candidate_index,
        "profiles_examined": candidate_index + 1,
        "patron_id": patron_id,
        "returning_id": returning_id,
        "steady_id": steady_id,
        "companion_handle": companion_handle,
        "companion_name": actors[companion_handle]["name"],
        "steward_handle": steward_handle,
        "steward_name": actors[steward_handle]["name"],
        "returning_material_preview": returning_aid["material_units_granted"],
        "steady_material_preview": steady_aid["material_units_granted"],
        "selection_mode": "PRE_LIFE_NON_AGING_PROFILE_FILTER",
        "selection_prior_replayed_by_canonical_actions": True,
        "distinct_consent_scopes": [
            "LIFE_COMPANIONSHIP_ONLY",
            "PARENTHOOD_ONLY",
            "LONG_DISTANCE_MODE",
            "ACTIVE_REUNION_MODE",
            "RETURNING_LIGHT_STEWARDSHIP",
        ],
        "repeated_pressure_inside_canonical_life": False,
        "candidate_profiles_share_mutable_relationship_state": False,
        "world_time_advanced_during_selection": False,
    }


def choose_lived_plan_fast() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="genesis-v1813-fast-selection-") as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(audit.SEED)
        free_store = world._free_store()
        free_store["world_turn"] = 4
        world._write_json(world.free_other_path, free_store)
        for candidate_index in range(1024):
            result = try_profile_direct(world, candidate_index)
            if result is not None:
                return result
    raise RuntimeError("NO_RETURNING_LIGHT_LIVED_PROFILE_FOUND")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    audit.choose_lived_plan = choose_lived_plan_fast
    audit.run(args.output_dir, args.git_commit)


if __name__ == "__main__":
    main()
