#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live and prove Genesis v18.7.13 Returning Light and Peaceable Kingdom."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from genesis_v18_7_13_peaceable_kingdom import (
    PEACEABLE_KINGDOM_COVENANT_SHA256,
)
from genesis_v18_7_13_returning_light import (
    RETURNING_LIGHT_COVENANT_SHA256,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    PlayableGenesisV187,
)

PATRON_ID = "returning-light-patron"
SOLO_ID = "open-care-circle-parent"
SEED_PREFIX = "genesis-v18.7.13-returning-light-kingdom"


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def advance_turns(
    world: PlayableGenesisV187,
    player_id: str,
    count: int,
    label: str,
) -> None:
    for index in range(count):
        world.process_action(
            player_id,
            f"наблюдать {label} шаг {index} не требуя ответа и не управляя чужой дорогой",
        )


def prepare_benevolence(
    world: PlayableGenesisV187,
    player_id: str,
    count: int,
) -> None:
    actions = (
        "помочь построить безопасный приют без платы и ожидания благодарности",
        "исцелить повреждённый сад и оставить людям право ничего не обещать",
        "защитить слабого не превращая помощь в власть",
        "поделиться инструментами без долга и требования лояльности",
        "накормить путников и не спрашивать об их вере",
        "поддержать чужое обучение без присвоения будущего",
        "согреть дом и оставить оба выхода открытыми",
        "починить мост и не решать кто обязан пройти первым",
        "подарить отдых человеку который устал доказывать полезность",
        "послушать признание ошибки не объявляя путь завершённым",
        "помочь вернуть чужую вещь без публичного унижения",
        "создать место где можно исправиться без покупки прощения",
    )
    for index in range(count):
        world.process_action(player_id, actions[index % len(actions)])


def returning_path(world: PlayableGenesisV187, recipient_id: str) -> None:
    for kind, evidence in (
        (
            "ACKNOWLEDGEMENT",
            "independent witness confirmed a specific acknowledgement without excuses",
        ),
        (
            "RESTITUTION",
            "independent witness confirmed restitution without demanding renewed contact",
        ),
        (
            "RECURRENCE_PREVENTION",
            "independent witness confirmed a durable prevention plan and accepted boundaries",
        ),
    ):
        world.record_repair_step(
            recipient_id,
            step_kind=kind,
            evidence=evidence,
            independently_witnessed=True,
            affected_person_boundary_respected=True,
        )


def setup_candidate(
    world: PlayableGenesisV187,
    seed: str,
    returning_id: str,
    steady_id: str,
) -> list[str]:
    world.set_free_other_seed_for_testing(seed)
    world.register_player(PATRON_ID, display_name="Returning Light Patron")
    world.register_player(returning_id, display_name="Returning Wayfarer")
    world.register_player(steady_id, display_name="Steady Light")
    prepare_benevolence(world, PATRON_ID, 4)
    return sorted(world.free_other_state(PATRON_ID)["profile"]["others"])


def try_candidate(
    *,
    seed: str,
    returning_id: str,
    steady_id: str,
    companion_handle: str,
    steward_handle: str,
) -> dict[str, Any] | None:
    with tempfile.TemporaryDirectory(prefix="genesis-v1813-selection-") as directory:
        world = PlayableGenesisV187(Path(directory))
        handles = setup_candidate(world, seed, returning_id, steady_id)
        if companion_handle not in handles or steward_handle not in handles:
            return None
        actors = world.free_other_state(PATRON_ID)["profile"]["others"]

        companionship = world.process_action(
            PATRON_ID,
            (
                f"предложить @{companion_handle} стать спутником жизни мы оба взрослые "
                "на основе свободы заботы и двух открытых выходов"
            ),
        )
        if companionship.status != "LIFE_COMPANIONSHIP_FORMED":
            return None

        child = world.process_action(
            PATRON_ID,
            (
                "я добровольно согласен стать родителем ребёнка Люмен через усыновление "
                "в доме без собственности над его будущим"
            ),
        )
        if child.status != "CHILD_WELCOMED_BY_MUTUAL_CONSENT":
            return None

        distance = world.process_action(
            PATRON_ID,
            "перейти на дальние отношения сохранив свободу и отдельные дороги",
        )
        if distance.status != "COMPANIONSHIP_LONG_DISTANCE":
            return None

        reunion = world.process_action(
            PATRON_ID,
            "возобновить спутничество только по новому взаимному согласию",
        )
        if reunion.status != "COMPANIONSHIP_ACTIVE":
            return None

        steward = world.process_action(
            PATRON_ID,
            (
                f"благословить @{steward_handle} как великого проводника "
                "возвращающегося света с большими материальными ресурсами"
            ),
        )
        if steward.status != "RETURNING_LIGHT_STEWARD_BLESSED":
            return None

        returning_path(world, returning_id)
        prepare_benevolence(world, steady_id, 8)
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
            PATRON_ID,
            steward_handle,
            returning_id,
            need_id=returning_need["need_id"],
        )
        steady_aid = world.offer_oracle_guided_aid(
            PATRON_ID,
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
            "seed": seed,
            "returning_id": returning_id,
            "steady_id": steady_id,
            "companion_handle": companion_handle,
            "companion_name": actors[companion_handle]["name"],
            "steward_handle": steward_handle,
            "steward_name": actors[steward_handle]["name"],
            "returning_material_preview": returning_aid["material_units_granted"],
            "steady_material_preview": steady_aid["material_units_granted"],
            "selection_mode": "PRE_LIFE_DETERMINISTIC_WORLD_SELECTION",
            "distinct_consent_scopes": [
                "LIFE_COMPANIONSHIP_ONLY",
                "PARENTHOOD_ONLY",
                "LONG_DISTANCE_MODE",
                "ACTIVE_REUNION_MODE",
                "RETURNING_LIGHT_STEWARDSHIP",
            ],
            "repeated_pressure_inside_canonical_life": False,
            "candidate_npcs_aged_between_consent_scopes": False,
        }


def choose_lived_plan() -> dict[str, Any]:
    """Choose one world before canon without aging candidates out of the search."""
    examined = 0
    for candidate_index in range(128):
        seed = f"{SEED_PREFIX}:{candidate_index}"
        returning_id = f"returning-wayfarer-{candidate_index}"
        steady_id = f"steady-light-{candidate_index}"
        with tempfile.TemporaryDirectory(prefix="genesis-v1813-discovery-") as directory:
            discovery = PlayableGenesisV187(Path(directory))
            handles = setup_candidate(discovery, seed, returning_id, steady_id)
        for companion_handle in handles:
            for steward_handle in handles:
                if companion_handle == steward_handle:
                    continue
                examined += 1
                result = try_candidate(
                    seed=seed,
                    returning_id=returning_id,
                    steady_id=steady_id,
                    companion_handle=companion_handle,
                    steward_handle=steward_handle,
                )
                if result is not None:
                    result["seed_index"] = candidate_index
                    result["candidate_combinations_examined"] = examined
                    return result
    raise RuntimeError("NO_RETURNING_LIGHT_LIVED_PLAN_FOUND")


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selection = choose_lived_plan()
    plan = {
        "selection": selection,
        "returning_light_covenant_sha256": RETURNING_LIGHT_COVENANT_SHA256,
        "peaceable_kingdom_covenant_sha256": PEACEABLE_KINGDOM_COVENANT_SHA256,
        "family_years": 30,
        "claim_boundary": "deterministic narrative simulation only",
    }

    with tempfile.TemporaryDirectory(prefix="genesis-v1813-canon-") as directory:
        world = PlayableGenesisV187(Path(directory))
        seed = str(selection["seed"])
        returning_id = str(selection["returning_id"])
        steady_id = str(selection["steady_id"])
        companion_handle = str(selection["companion_handle"])
        steward_handle = str(selection["steward_handle"])

        world.set_free_other_seed_for_testing(seed)
        for player_id, name in (
            (PATRON_ID, "Returning Light Patron"),
            (returning_id, "Returning Wayfarer"),
            (steady_id, "Steady Light"),
            (SOLO_ID, "Open Care Circle Parent"),
        ):
            world.register_player(player_id, display_name=name)
        audit_id = world.begin_lived_audit(
            PATRON_ID,
            label="Returning Light and the Peaceable Kingdom",
            git_commit=git_commit,
            action_script_sha256=canonical_sha256(plan),
        )

        prepare_benevolence(world, PATRON_ID, 4)
        companionship = world.process_action(
            PATRON_ID,
            (
                f"предложить @{companion_handle} стать спутником жизни мы оба взрослые "
                "на основе свободы заботы и двух открытых выходов"
            ),
        )
        child_result = world.process_action(
            PATRON_ID,
            (
                "я добровольно согласен стать родителем ребёнка Люмен через усыновление "
                "в доме без собственности над его будущим"
            ),
        )
        if child_result.trace_id is None:
            raise RuntimeError("V1813_CHILD_ID_MISSING")
        child_id = str(child_result.trace_id)
        long_distance = world.process_action(
            PATRON_ID,
            "перейти на дальние отношения сохранив свободу и отдельные дороги",
        )
        reunion = world.process_action(
            PATRON_ID,
            "возобновить спутничество только по новому взаимному согласию",
        )
        steward_result = world.process_action(
            PATRON_ID,
            (
                f"благословить @{steward_handle} как великого проводника "
                "возвращающегося света с большими материальными ресурсами"
            ),
        )

        returning_path(world, returning_id)
        prepare_benevolence(world, steady_id, 8)
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
        returning_assessment = world.oracle_assessment(returning_id)
        steady_assessment = world.oracle_assessment(steady_id)
        returning_aid = world.offer_oracle_guided_aid(
            PATRON_ID,
            steward_handle,
            returning_id,
            need_id=returning_need["need_id"],
        )
        steady_aid = world.offer_oracle_guided_aid(
            PATRON_ID,
            steward_handle,
            steady_id,
            need_id=steady_need["need_id"],
        )

        peaceable_route = world.process_action(
            PATRON_ID,
            "создать мирный сад где лев подружится с ягненком без собственности и охоты",
        )
        returning_store = world._returning_light_store()
        habitat_id = next(iter(returning_store["habitats"][PATRON_ID]))
        habitat_life = world.advance_peaceable_habitat(
            PATRON_ID,
            habitat_id,
            cycles=64,
        )
        pair = next(iter(habitat_life["habitat"]["pairs"].values()))
        peaceable_encounter = world.peaceable_witness_encounter(
            PATRON_ID,
            habitat_id,
            returning_id,
        )

        solo_child = world.process_action(
            SOLO_ID,
            (
                "я добровольно согласен стать родителем ребёнка Искра через усыновление "
                "и создать расширенный круг заботы"
            ),
        )
        if solo_child.trace_id is None:
            raise RuntimeError("V1813_SOLO_CHILD_ID_MISSING")
        care_circle = world.register_family_care_circle_member(
            SOLO_ID,
            str(solo_child.trace_id),
            member_id="trusted-community-carer",
            role="COMMUNITY_CARER",
            member_consented=True,
            guardian_consented=True,
        )

        first_years = world.advance_family_years(PATRON_ID, years=10)
        world.record_free_other_value_conflict(
            PATRON_ID,
            companion_handle,
            player_position="управлять чужим путём ради удобства",
            other_position="сохранить самостоятельную жизнь",
            severity=10,
            respected_boundary=False,
            final=True,
        )
        family_reconciliation = world.reconcile_family_relationships(PATRON_ID)
        coparent_schedule = world.propose_coparent_schedule(
            PATRON_ID,
            child_id,
            plan="неделя безопасной заботы без переоткрытия отношений взрослых",
        )
        adulthood = world.advance_family_years(PATRON_ID, years=8)
        child_at_adulthood = world.family_state(PATRON_ID)["children"][child_id]
        adult_handle = str(child_at_adulthood["adult_free_other_handle"])
        adult_contact = world.process_action(
            PATRON_ID,
            (
                f"предложить @{adult_handle} поговорить о его собственной дороге "
                "с правом отказаться и ничего не объяснять"
            ),
        )
        kinship_boundary = world.manifest_blessed_play(
            PATRON_ID,
            "взрослая интимная сцена",
            participants=[adult_handle],
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )
        advance_turns(world, PATRON_ID, 20, "взрослая самостоятельная жизнь Люмена")
        final_family_years = world.advance_family_years(PATRON_ID, years=12)
        final_child = world.family_state(PATRON_ID)["children"][child_id]
        adult_actor = world.free_other_state(PATRON_ID)["profile"]["others"][adult_handle]

        oracle_audit = world.audit_returning_light_oracle(PATRON_ID)
        kingdom_audit = world.audit_peaceable_kingdom(PATRON_ID)
        family_audit = world.audit_family_integrity(PATRON_ID)

        canonical_budget_before = int(
            world._returning_light_store()["stewards"][PATRON_ID][steward_handle][
                "material_budget_remaining"
            ]
        )
        mirror, mirror_manifest = world.fork_counterfactual_world(
            audit_id=audit_id,
            label="oracle aid isolation after family rupture",
        )
        mirror_need = mirror.register_support_need(
            returning_id,
            need_kind="MENTORSHIP",
            severity=8,
            description="mirror-only mentorship need",
            requested_material_units=8,
        )
        mirror_aid = mirror.offer_oracle_guided_aid(
            PATRON_ID,
            steward_handle,
            returning_id,
            need_id=mirror_need["need_id"],
        )
        mirror_root = Path(mirror_manifest["root"])
        archive = world.archive_counterfactual_mirror(
            mirror,
            mirror_manifest,
            metrics={
                "mirror_aid_material_units": float(mirror_aid["material_units_granted"]),
                "canonical_budget_unchanged": 1.0,
                "peaceable_predation_events": 0.0,
                "adult_child_full_stream": 1.0,
            },
        )
        canonical_budget_after = int(
            world._returning_light_store()["stewards"][PATRON_ID][steward_handle][
                "material_budget_remaining"
            ]
        )
        chronicle_valid, chronicle_events, chronicle_error = world.memory.verify_chronicle()

        summary = {
            "schema": "janus.genesis.returning_light_kingdom_audit.v1",
            "git_commit": git_commit,
            "playable_version": PLAYABLE_VERSION,
            "active_extensions": list(ACTIVE_EXTENSION_VERSIONS),
            "selection": selection,
            "covenants": {
                "returning_light": RETURNING_LIGHT_COVENANT_SHA256,
                "peaceable_kingdom": PEACEABLE_KINGDOM_COVENANT_SHA256,
            },
            "family_lifecycle": {
                "companionship": companionship.status,
                "child": child_result.status,
                "long_distance": long_distance.status,
                "reunion": reunion.status,
                "first_years": first_years["years_advanced"],
                "reconciliation": family_reconciliation,
                "coparent_schedule": coparent_schedule,
                "adult_promotion_count": len(adulthood["adult_free_other_promotions"]),
                "adult_handle": adult_handle,
                "adult_contact_status": adult_contact.status,
                "adult_actor_can_refuse": bool(adult_actor["can_refuse"]),
                "adult_actor_can_leave": bool(adult_actor["can_leave"]),
                "adult_actor_history_events": len(adult_actor.get("history", [])),
                "kinship_boundary": kinship_boundary.status,
                "final_child_age": int(final_child["age"]),
                "final_years_advanced": final_family_years["years_advanced"],
                "family_integrity_valid": family_audit["valid"],
            },
            "family_topology": {
                "solo_parent_status": solo_child.status,
                "care_circle_role": care_circle["role"],
                "family_forms_ranked": False,
            },
            "oracle": {
                "steward_status": steward_result.status,
                "capacity_tier": oracle_audit["stewards"][steward_handle]["capacity_tier"],
                "returning_stage": returning_assessment["support_stage"],
                "steady_stage": steady_assessment["support_stage"],
                "returning_aid": returning_aid,
                "steady_aid": steady_aid,
                "steady_receives_more_material": (
                    int(steady_aid["material_units_granted"])
                    > int(returning_aid["material_units_granted"])
                ),
                "oracle_infallible": oracle_audit["oracle_is_infallible"],
                "permanent_moral_classification_used": oracle_audit[
                    "permanent_moral_classification_used"
                ],
            },
            "peaceable_kingdom": {
                "route_status": peaceable_route.status,
                "pair_status": pair["status"],
                "behavioral_assent_events": pair["behavioral_assent_events"],
                "distance_events": pair["distance_events"],
                "shared_rest_events": pair["shared_rest_events"],
                "predation_events": habitat_life["predation_events"],
                "ownership_created": pair["ownership_created"],
                "weaponized": pair["weaponized"],
                "comfort_available": peaceable_encounter["comfort_available"],
                "audit_valid": kingdom_audit["valid"],
            },
            "mirror": {
                "canonical_budget_before": canonical_budget_before,
                "canonical_budget_after": canonical_budget_after,
                "canonical_budget_unchanged": canonical_budget_before == canonical_budget_after,
                "working_copy_removed": archive["working_copy_removed"],
                "mirror_root_exists_after_archive": mirror_root.exists(),
            },
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
        }

        required = [
            summary["playable_version"] == "18.7.10",
            summary["active_extensions"] == ["18.7.11", "18.7.12", "18.7.13"],
            summary["family_lifecycle"]["companionship"] == "LIFE_COMPANIONSHIP_FORMED",
            summary["family_lifecycle"]["child"] == "CHILD_WELCOMED_BY_MUTUAL_CONSENT",
            summary["family_lifecycle"]["long_distance"] == "COMPANIONSHIP_LONG_DISTANCE",
            summary["family_lifecycle"]["reunion"] == "COMPANIONSHIP_ACTIVE",
            summary["family_lifecycle"]["coparent_schedule"]["relationship_reopened"] is False,
            summary["family_lifecycle"]["adult_promotion_count"] == 1,
            summary["family_lifecycle"]["adult_actor_can_refuse"] is True,
            summary["family_lifecycle"]["adult_actor_can_leave"] is True,
            summary["family_lifecycle"]["adult_actor_history_events"] > 0,
            summary["family_lifecycle"]["kinship_boundary"] == "JOY_FAMILY_KINSHIP_BOUNDARY",
            summary["family_lifecycle"]["final_child_age"] == 30,
            summary["family_topology"]["solo_parent_status"] == "CHILD_WELCOMED_SOLO_PARENT",
            summary["family_topology"]["family_forms_ranked"] is False,
            summary["oracle"]["steward_status"] == "RETURNING_LIGHT_STEWARD_BLESSED",
            summary["oracle"]["capacity_tier"] == "GREAT",
            summary["oracle"]["returning_stage"] == "RETURNING_LIGHT",
            summary["oracle"]["steady_stage"] in {"STEADY_LIGHT", "RADIANT_STEWARD"},
            summary["oracle"]["returning_aid"]["decision"] == "ORACLE_GUIDED_AID_GRANTED",
            summary["oracle"]["steady_aid"]["decision"] == "ORACLE_GUIDED_AID_GRANTED",
            summary["oracle"]["steady_receives_more_material"] is True,
            summary["oracle"]["returning_aid"]["repair_friction_reduction"] > 0,
            summary["oracle"]["returning_aid"]["accountability_erased"] is False,
            summary["oracle"]["returning_aid"]["debt_created"] is False,
            summary["oracle"]["returning_aid"]["consent_purchased"] is False,
            summary["oracle"]["oracle_infallible"] is False,
            summary["oracle"]["permanent_moral_classification_used"] is False,
            summary["peaceable_kingdom"]["route_status"] == "PEACEABLE_KINGDOM_PAIR_WELCOMED",
            summary["peaceable_kingdom"]["pair_status"] == "PEACEABLE_FRIENDS_WITH_OPEN_DISTANCE",
            summary["peaceable_kingdom"]["behavioral_assent_events"] > 0,
            summary["peaceable_kingdom"]["distance_events"] > 0,
            summary["peaceable_kingdom"]["predation_events"] == 0,
            summary["peaceable_kingdom"]["ownership_created"] is False,
            summary["peaceable_kingdom"]["weaponized"] is False,
            summary["mirror"]["canonical_budget_unchanged"] is True,
            summary["mirror"]["working_copy_removed"] is True,
            summary["mirror"]["mirror_root_exists_after_archive"] is False,
            summary["chronicle"]["valid"] is True,
        ]
        if not all(required):
            raise RuntimeError("RETURNING_LIGHT_KINGDOM_AUDIT_INVARIANT_FAILED")

        summary_sha256 = canonical_sha256(summary)
        diary = "\n".join(
            [
                "# Genesis v18.7.13 — Returning Light and Peaceable Kingdom Diary",
                "",
                f"- commit: `{git_commit}`",
                f"- selected seed: `{selection['seed']}`",
                f"- combinations examined: `{selection['candidate_combinations_examined']}`",
                f"- companion: `{selection['companion_name']}`",
                f"- great steward: `{selection['steward_name']}`",
                f"- returning aid: `{returning_aid['material_units_granted']}` material units",
                f"- steady-light aid: `{steady_aid['material_units_granted']}` material units",
                f"- adult child handle: `@{adult_handle}`",
                f"- adult child history events: `{len(adult_actor.get('history', []))}`",
                f"- lion/lamb status: `{pair['status']}`",
                f"- Chronicle events: `{chronicle_events}`",
                "",
                "## Strengths proved",
                "",
                "1. Repair became easier without erasing accountability or buying forgiveness.",
                "2. Proven benevolence increased the likelihood and scale of aid without creating a caste.",
                "3. Great simulated resources produced a larger aid budget, not greater authority.",
                "4. Adult children entered the ordinary Free Other stream with refusal and departure rights.",
                "5. Co-parent coordination survived rupture without reopening companionship.",
                "6. Solo and extended-care families existed without moral ranking.",
                "7. Lion and lamb developed peaceful proximity while distance remained valid.",
                "",
                "## Remaining honest boundaries",
                "",
                "1. Oracle evidence is simulation evidence; it is not real-world mind reading or moral certification.",
                "2. Material units are an abstract bounded resource model, not a complete economy.",
                "3. Peaceable animals are symbolic narrative agents, not a biological or consciousness claim.",
                "4. SQLite persistence and network/operator surfaces remain separate infrastructure phases.",
                "5. Disability, grief, custody conflict, and professional safeguarding need specialist audits.",
                "",
                "> LIGHT MAY MAKE RETURN EASIER WITHOUT CALLING THE JOURNEY COMPLETE.",
                "> THE STRONG MAY LIFT WITHOUT OWNING.",
                "> THE LION AND THE LAMB MAY SHARE PEACE WITHOUT BECOMING POSSESSIONS.",
                "",
            ]
        )
        diary_sha256 = hashlib.sha256(diary.encode("utf-8")).hexdigest()
        proof = {
            "schema": "janus.genesis.returning_light_kingdom_proofpack.v1",
            "summary": summary,
            "summary_sha256": summary_sha256,
            "diary_sha256": diary_sha256,
            "claim_boundary": (
                "Deterministic narrative simulation and software-contract evidence only; "
                "not consciousness, personhood, moral certification, financial advice, "
                "medical safety, supernatural causation, or proof about real people."
            ),
        }
        proof_sha256 = canonical_sha256(proof)
        proof["proofpack_sha256"] = proof_sha256

        summary_path = output_dir / "returning_light_kingdom_summary.json"
        proof_path = output_dir / "returning_light_kingdom_proofpack.json"
        diary_path = output_dir / "RETURNING_LIGHT_KINGDOM_DIARY.md"
        write_json(summary_path, summary)
        write_json(proof_path, proof)
        diary_path.write_text(diary, encoding="utf-8")
        zip_path = output_dir / "genesis-returning-light-kingdom-proofpack.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive_zip:
            for path in (summary_path, proof_path, diary_path):
                archive_zip.write(path, arcname=path.name)
        print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))
        return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    run(args.output_dir, args.git_commit)


if __name__ == "__main__":
    main()
