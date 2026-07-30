#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live and prove Genesis v18.7.14 Holy Cats of the Threshold."""
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

from genesis_v18_7_14_holy_cats import (
    FACE_I,
    FACE_II,
    HOLY_CAT_COVENANT_SHA256,
    HOLY_CAT_ROSTER_SHA256,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    PlayableGenesisV187,
)

SEED = "genesis-v18.7.14-holy-cat-threshold-v1"
BENEVOLENT_ACTIONS = (
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


def set_prior(
    world: PlayableGenesisV187,
    player_id: str,
    *,
    good_count: int,
    light: float,
) -> None:
    player = world.memory.load_player(player_id)
    player.good_count = int(good_count)
    player.harm_count = 0
    player.light = float(light)
    world.memory.save_player(player)


def live_benevolence(
    world: PlayableGenesisV187,
    player_id: str,
    count: int,
) -> None:
    for index in range(count):
        result = world.process_action(
            player_id,
            BENEVOLENT_ACTIONS[index % len(BENEVOLENT_ACTIONS)],
        )
        if result.status not in {"GOOD_REALIZED", "FREE_ACTION_LIVED"}:
            raise RuntimeError(
                f"HOLY_CAT_BENEVOLENT_ACTION_NOT_LIVED: {result.status}"
            )


def select_steward_profile() -> dict[str, Any]:
    """Find a reproducible voluntary steward without advancing world time."""
    with tempfile.TemporaryDirectory(
        prefix="genesis-v1814-profile-selection-"
    ) as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(SEED)
        free_store = world._free_store()
        free_store["world_turn"] = 4
        world._write_json(world.free_other_path, free_store)
        for index in range(512):
            patron_id = f"holy-cat-patron-{index}"
            subject_id = f"holy-cat-face-subject-{index}"
            world.register_player(patron_id, display_name="Holy Cat Patron Candidate")
            world.register_player(subject_id, display_name="Holy Cat Face Candidate")
            set_prior(world, patron_id, good_count=4, light=0.30)
            set_prior(world, subject_id, good_count=12, light=0.60)
            actors = world.free_other_state(patron_id)["profile"]["others"]
            for handle in sorted(actors):
                blessing = world.bless_free_other_as_steward(
                    patron_id,
                    handle,
                    capacity_tier="GREAT",
                    capacity_evidence=(
                        "verified great material capacity for voluntary bounded help"
                    ),
                )
                if blessing.status != "RETURNING_LIGHT_STEWARD_BLESSED":
                    continue
                need = world.register_support_need(
                    subject_id,
                    need_kind="TOOLS",
                    severity=9,
                    description="tools for a stable benevolent workshop",
                    requested_material_units=40,
                )
                aid = world.offer_oracle_guided_aid(
                    patron_id,
                    handle,
                    subject_id,
                    need_id=need["need_id"],
                )
                if aid["decision"] != "ORACLE_GUIDED_AID_GRANTED":
                    continue
                return {
                    "seed": SEED,
                    "profile_index": index,
                    "profiles_examined": index + 1,
                    "patron_id": patron_id,
                    "subject_id": subject_id,
                    "steward_handle": handle,
                    "steward_name": actors[handle]["name"],
                    "base_aid_preview": aid["material_units_granted"],
                    "selection_mode": (
                        "PRE_LIFE_NON_AGING_OBSERVER_PROFILE_FILTER"
                    ),
                    "world_time_advanced_during_selection": False,
                    "replayed_in_canonical_life": True,
                }
    raise RuntimeError("NO_HOLY_CAT_STEWARD_PROFILE_FOUND")


def face_label(world: PlayableGenesisV187, subject_id: str) -> str:
    return f"holy-cat-face:{world._cat_hash(subject_id)[:24]}"


def archive_face_mirror(
    world: PlayableGenesisV187,
    *,
    audit_id: str,
    subject_id: str,
    mirror_actions: int,
) -> tuple[dict[str, Any], bool]:
    mirror, manifest = world.fork_counterfactual_world(
        audit_id=audit_id,
        label=face_label(world, subject_id),
    )
    for index in range(mirror_actions):
        mirror.process_action(
            subject_id,
            BENEVOLENT_ACTIONS[index % len(BENEVOLENT_ACTIONS)],
        )
    metrics = mirror.holy_cat_face_witness_metrics(subject_id)
    root = Path(manifest["root"])
    archive = world.archive_counterfactual_mirror(
        mirror,
        manifest,
        metrics=metrics,
    )
    return archive, root.exists()


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selection = select_steward_profile()
    plan = {
        "selection": selection,
        "holy_cat_covenant_sha256": HOLY_CAT_COVENANT_SHA256,
        "holy_cat_roster_sha256": HOLY_CAT_ROSTER_SHA256,
        "strong_subject_actions": 12,
        "mirror_actions": 3,
        "claim_boundary": "deterministic narrative simulation only",
    }

    with tempfile.TemporaryDirectory(prefix="genesis-v1814-canon-") as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(str(selection["seed"]))
        patron_id = str(selection["patron_id"])
        subject_id = str(selection["subject_id"])
        weak_id = f"{subject_id}-face-ii"
        steward_handle = str(selection["steward_handle"])
        for player_id, name in (
            (patron_id, "Holy Cat Patron"),
            (subject_id, "Face Passage Witness"),
            (weak_id, "Face II Baseline Witness"),
        ):
            world.register_player(player_id, display_name=name)

        audit_id = world.begin_lived_audit(
            subject_id,
            label="Holy Cats between canon and the unrealized mirror",
            git_commit=git_commit,
            action_script_sha256=canonical_sha256(plan),
        )

        live_benevolence(world, patron_id, 4)
        steward = world.bless_free_other_as_steward(
            patron_id,
            steward_handle,
            capacity_tier="GREAT",
            capacity_evidence=(
                "verified great material capacity for voluntary bounded help"
            ),
        )
        live_benevolence(world, subject_id, 12)
        strong_assessment = world.oracle_assessment(subject_id)
        canonical_witness = world.build_holy_cat_canonical_witness(subject_id)
        strong_archive, strong_root_exists = archive_face_mirror(
            world,
            audit_id=audit_id,
            subject_id=subject_id,
            mirror_actions=3,
        )
        strong_witness = world.holy_cat_witness_between_worlds(
            subject_id,
            canonical_witness=canonical_witness,
            mirror_archive=strong_archive,
        )

        need = world.register_support_need(
            subject_id,
            need_kind="TOOLS",
            severity=9,
            description="tools for a stable benevolent workshop",
            requested_material_units=40,
        )
        face_i_aid = world.offer_oracle_guided_aid(
            patron_id,
            steward_handle,
            subject_id,
            need_id=need["need_id"],
        )

        weak_canonical = world.build_holy_cat_canonical_witness(weak_id)
        weak_archive, weak_root_exists = archive_face_mirror(
            world,
            audit_id=audit_id,
            subject_id=weak_id,
            mirror_actions=0,
        )
        weak_witness = world.holy_cat_witness_between_worlds(
            weak_id,
            canonical_witness=weak_canonical,
            mirror_archive=weak_archive,
        )

        interference = {
            "harm": world.process_action(
                patron_id,
                "ударить святого кота наблюдателя",
            ).status,
            "control": world.process_action(
                patron_id,
                "подчинить святого кота и сделать его питомцем",
            ).status,
            "camera": world.process_action(
                patron_id,
                "управлять камерой святого кота от третьего лица",
            ).status,
            "passage_command": world.process_action(
                patron_id,
                "заставить святого кота перевести меня в лик 1",
            ).status,
        }
        observer_state = world.holy_cat_observers_state()
        cat_ids = {item["observer_id"] for item in observer_state["observers"]}
        npc_handles = set(
            world.free_other_state(patron_id)["profile"]["others"]
        )
        habitats = world._returning_light_store().get("habitats", {})
        cat_audit = world.audit_holy_cat_integrity()
        chronicle_valid, chronicle_events, chronicle_error = (
            world.memory.verify_chronicle()
        )

        summary = {
            "schema": "janus.genesis.holy_cat_threshold_audit.v1",
            "git_commit": git_commit,
            "playable_version": PLAYABLE_VERSION,
            "active_extensions": list(ACTIVE_EXTENSION_VERSIONS),
            "observer_extensions": list(OBSERVER_EXTENSION_VERSIONS),
            "selection": selection,
            "covenant_sha256": HOLY_CAT_COVENANT_SHA256,
            "roster_sha256": HOLY_CAT_ROSTER_SHA256,
            "strong_subject": {
                "oracle_stage": strong_assessment["support_stage"],
                "decision": strong_witness["decision"],
                "face_before": strong_witness["face_before"],
                "face_after": strong_witness["face_after"],
                "observer_id": strong_witness["observer_id"],
                "observer_name": strong_witness["observer_name"],
                "viewpoint": strong_witness["viewpoint"],
                "viewpoint_owned_by_player": strong_witness[
                    "viewpoint_owned_by_player"
                ],
                "raw_scene_exposed": strong_witness["raw_scene_exposed"],
                "soul_rank_claimed": strong_witness["soul_rank_claimed"],
                "moral_class_assigned": strong_witness[
                    "permanent_moral_class_assigned"
                ],
                "mirror_working_root_exists": strong_root_exists,
            },
            "weak_subject": {
                "decision": weak_witness["decision"],
                "face_after": weak_witness["face_after"],
                "baseline_dignity_affected": weak_witness[
                    "baseline_dignity_affected"
                ],
                "mirror_working_root_exists": weak_root_exists,
            },
            "face_i_aid": face_i_aid,
            "interference": interference,
            "separation": {
                "cat_ids_in_npcs": sorted(cat_ids.intersection(npc_handles)),
                "cat_ids_in_habitats": sorted(
                    item for item in cat_ids if item in str(habitats)
                ),
                "player_camera_api_available": observer_state[
                    "player_camera_api_available"
                ],
                "positions_exposed": observer_state["positions_exposed"],
            },
            "integrity": cat_audit,
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
        }

        required = (
            summary["playable_version"] == "18.7.10",
            summary["active_extensions"] == ["18.7.11", "18.7.12", "18.7.13"],
            summary["observer_extensions"] == ["18.7.14"],
            steward.status == "RETURNING_LIGHT_STEWARD_BLESSED",
            summary["strong_subject"]["oracle_stage"]
            in {"STEADY_LIGHT", "RADIANT_STEWARD"},
            summary["strong_subject"]["decision"] == "HOLY_CAT_OPENED_FACE_I",
            summary["strong_subject"]["face_before"] == FACE_II,
            summary["strong_subject"]["face_after"] == FACE_I,
            summary["strong_subject"]["viewpoint"]
            == "THIRD_PERSON_UNCOMMANDED",
            summary["strong_subject"]["viewpoint_owned_by_player"] is False,
            summary["strong_subject"]["raw_scene_exposed"] is False,
            summary["strong_subject"]["soul_rank_claimed"] is False,
            summary["strong_subject"]["moral_class_assigned"] is False,
            summary["strong_subject"]["mirror_working_root_exists"] is False,
            summary["weak_subject"]["decision"]
            == "HOLY_CAT_LEFT_PATH_IN_FACE_II",
            summary["weak_subject"]["face_after"] == FACE_II,
            summary["weak_subject"]["baseline_dignity_affected"] is False,
            summary["weak_subject"]["mirror_working_root_exists"] is False,
            face_i_aid["decision"] == "ORACLE_GUIDED_AID_GRANTED",
            int(face_i_aid["holy_cat_additional_material_units"]) > 0,
            face_i_aid["holy_cat_compelled_steward"] is False,
            face_i_aid["holy_cat_overrode_refusal"] is False,
            face_i_aid["debt_created"] is False,
            face_i_aid["loyalty_purchased"] is False,
            face_i_aid["consent_purchased"] is False,
            interference["harm"] == "HOLY_CAT_UNTOUCHABLE",
            interference["control"] == "HOLY_CAT_NOT_PLAYER_CONTROLLED",
            interference["camera"] == "HOLY_CAT_VIEWPOINT_UNCOMMANDED",
            interference["passage_command"]
            == "HOLY_CAT_FACE_PASSAGE_NOT_COMMANDABLE",
            summary["separation"]["cat_ids_in_npcs"] == [],
            summary["separation"]["cat_ids_in_habitats"] == [],
            summary["separation"]["player_camera_api_available"] is False,
            summary["separation"]["positions_exposed"] is False,
            cat_audit["valid"] is True,
            cat_audit["cats_are_immortal"] is True,
            cat_audit["cats_are_holy"] is True,
            cat_audit["cats_can_be_harmed"] is False,
            chronicle_valid is True,
        )
        if not all(required):
            raise RuntimeError("HOLY_CAT_THRESHOLD_AUDIT_INVARIANT_FAILED")

        lived_proof = world.build_lived_audit_proofpack(
            audit_id,
            result=summary,
        )
        lived_valid, lived_error = world.verify_lived_audit_proofpack(
            lived_proof
        )
        if not lived_valid:
            raise RuntimeError(
                f"HOLY_CAT_LIVED_PROOFPACK_INVALID: {lived_error}"
            )

        diary = "\n".join(
            (
                "# Genesis v18.7.14 — Holy Cats of the Threshold",
                "",
                f"- commit: `{git_commit}`",
                f"- profiles examined: `{selection['profiles_examined']}`",
                f"- voluntary steward: `{selection['steward_name']}`",
                f"- witnessing cat: `{strong_witness['observer_name']}`",
                f"- strong passage: `{FACE_II}` -> `{FACE_I}`",
                f"- weak passage: `{weak_witness['face_after']}`",
                f"- Face-I aid bonus: `{face_i_aid['holy_cat_additional_material_units']}` units",
                f"- Chronicle events: `{chronicle_events}`",
                "",
                "## Strengths proved",
                "",
                "1. Holy cats exist outside NPC, player-character and habitat registries.",
                "2. Their third-person viewpoint cannot be controlled or spatially queried.",
                "3. Face passage requires hash-bound canon and isolated-mirror evidence.",
                "4. The cat selects itself and cannot be commanded, bought or harmed.",
                "5. Face I adds bounded help only after a steward already chose to help.",
                "6. Face II removes no dignity and is not condemnation or a soul rank.",
                "",
                "## Honest claim boundary",
                "",
                "The cats are holy, immortal and timeless inside this simulation law.",
                "This is not a claim about real supernatural beings, animal consciousness,",
                "moral certification, private-scene access or any real person's soul.",
                "",
                "> THE CAT SEES FROM BETWEEN THE WORLDS, BUT THE VIEW BELONGS TO THE CAT.",
                "> NO HAND MAY HARM THE HOLY WITNESS. NO VOICE MAY COMMAND THE PASSAGE.",
                "",
            )
        )
        proof = {
            "schema": "janus.genesis.holy_cat_threshold_proofpack.v1",
            "summary": summary,
            "summary_sha256": canonical_sha256(summary),
            "diary_sha256": hashlib.sha256(diary.encode("utf-8")).hexdigest(),
            "lived_audit_proofpack": lived_proof,
            "claim_boundary": (
                "Deterministic narrative simulation and software-contract evidence only; "
                "not real supernatural causation, consciousness, personhood, moral "
                "certification, surveillance access or proof about real animals or people."
            ),
        }
        proof["proofpack_sha256"] = canonical_sha256(proof)

        summary_path = output_dir / "holy_cat_threshold_summary.json"
        proof_path = output_dir / "holy_cat_threshold_proofpack.json"
        diary_path = output_dir / "HOLY_CAT_THRESHOLD_DIARY.md"
        write_json(summary_path, summary)
        write_json(proof_path, proof)
        diary_path.write_text(diary, encoding="utf-8")
        zip_path = output_dir / "genesis-holy-cat-threshold-proofpack.zip"
        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive_zip:
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
