#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live and prove Genesis v18.7.16: The Fifth Shore inner Genesis."""
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

from genesis_v18_7_14_holy_cats import FACE_II
from genesis_v18_7_16_fifth_shore import (
    INNER_GENESIS_COVENANT_SHA256,
    INNER_GENESIS_EXTENSION_VERSION,
    INNER_GENESIS_LAW,
    INNER_GENESIS_NAME,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    CULTURE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    VOCATION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)

SEED = "genesis-v18.7.16-fifth-shore-auteur-v1"


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


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-v1816-fifth-shore-") as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(SEED)
        names = {
            "king": "Царь Милости",
            "iori": "Иори Кай, Автор Нулевого Моста",
            "archivist": "Архивариус Безошибочного Финала",
            "propagandist": "Режиссёр Единственного Ответа",
            "repairing": "Репетирующий возмещение",
            "resting": "Вернувший смех",
            "declining": "Не пожелавший играть",
            "forker": "Автор Дворов",
        }
        for player_id, name in names.items():
            world.register_player(player_id, display_name=name)

        arrival = world.enter_royal_mercy_face_ii(
            "king",
            arrival_date_local="2026-07-30",
            title="Царь Милости",
        )
        seed = world.found_inner_genesis_in_face_ii(
            "king",
            founded_date_local="2026-07-30",
            working_title="Генезис Открытой Ладони",
        )

        archivist = world.register_face_ii_auteur_candidate(
            "archivist",
            display_name=names["archivist"],
            originality=0.71,
            player_care=0.95,
            ambiguity_tolerance=0.20,
            collaboration=0.80,
            consent_respect=0.98,
            celebrity_hunger=0.05,
            pitch="идеально безопасный музей без возможности переписать историю",
        )
        propagandist = world.register_face_ii_auteur_candidate(
            "propagandist",
            display_name=names["propagandist"],
            originality=0.96,
            player_care=0.30,
            ambiguity_tolerance=0.85,
            collaboration=0.25,
            consent_respect=0.20,
            celebrity_hunger=0.99,
            pitch="игра обязана удержать каждого и привести к одному правильному выводу",
        )
        iori = world.register_face_ii_auteur_candidate(
            "iori",
            display_name=names["iori"],
            originality=0.98,
            player_care=0.93,
            ambiguity_tolerance=0.99,
            collaboration=0.88,
            consent_respect=0.97,
            celebrity_hunger=0.18,
            pitch=(
                "игра, в которой последнего босса побеждают отказом автора "
                "от единственного финала"
            ),
        )
        invitation = world.invite_best_face_ii_auteur("king")
        auteur = world.decide_auteur_collaboration(
            "iori",
            accepts=True,
            counterproposal=(
                "Убрать имя Царя с первого места в титрах; оставить игроку право "
                "не играть и выйти; разрешить сообществам переписывать мир с "
                "сохранением происхождения; не объявлять ни один финал единственным."
            ),
            chosen_title=INNER_GENESIS_NAME,
        )
        edition = world.coauthor_fifth_shore("king", "iori")

        ash_market = world.publish_fifth_shore_capsule(
            "iori",
            "ash-market",
            accepted=True,
        )
        bridge_station = world.publish_fifth_shore_capsule(
            "iori",
            "bridge-station",
            accepted=True,
            delivery_mode="OFFLINE_HAND_TO_HAND_LANTERN_CARTRIDGE",
        )
        quiet_yard = world.publish_fifth_shore_capsule(
            "iori",
            "quiet-yard",
            accepted=False,
        )
        capture_channel = world.publish_fifth_shore_capsule(
            "iori",
            "capture-channel",
            accepted=True,
            coercive_retention=True,
            surveillance=True,
        )

        repair_episode = world.play_fifth_shore_episode(
            "repairing",
            "ash-market",
            participates=True,
            rehearsal_kind=(
                "признать вред, выслушать отказ и подготовить проверяемый "
                "план возмещения вне игры"
            ),
            commits_to_external_action=True,
        )
        rest_episode = world.play_fifth_shore_episode(
            "resting",
            "bridge-station",
            participates=True,
            rehearsal_kind=(
                "вернуть безопасный смех и совместную игру после долгой жизни "
                "в режиме угрозы"
            ),
            commits_to_external_action=False,
            chooses_rest_or_humor=True,
        )
        unplayed = world.play_fifth_shore_episode(
            "declining",
            "ash-market",
            participates=False,
            rehearsal_kind="",
            commits_to_external_action=False,
        )

        accepted_fork = world.fork_fifth_shore(
            "ash-market",
            "forker",
            fork_title="Шестой Берег: Дворы",
            preserves_provenance=True,
            keeps_exit_open=True,
            keeps_consent=True,
        )
        rejected_fork = world.fork_fifth_shore(
            "ash-market",
            "forker",
            fork_title="Единственный Берег",
            preserves_provenance=False,
            keeps_exit_open=False,
            keeps_consent=False,
            claims_single_canon=True,
        )

        comparison = world.compare_fifth_shore_to_outer_genesis()
        imports = world.propose_fifth_shore_imports()
        integrity = world.audit_fifth_shore_integrity()
        state = world.inner_genesis_state()
        chronicle_valid, chronicle_events, chronicle_error = (
            world.memory.verify_chronicle()
        )

        import_decisions = {
            item["feature"]: item["decision"]
            for item in imports
        }
        invariants = {
            "playable_frozen": PLAYABLE_VERSION == "18.7.10",
            "culture_plane_versioned": CULTURE_EXTENSION_VERSIONS == ("18.7.16",),
            "arrival_face_ii": arrival.status == "ROYAL_MERCY_ARRIVED_IN_FACE_II"
            and state["project"]["face"] == FACE_II,
            "inner_genesis_seeded": seed.status == "INNER_GENESIS_SEED_FOUNDED",
            "founder_relinquished_ownership": (
                state["project"]["world_owned_by_founder"] is False
                and state["project"]["players_owned_by_founder"] is False
            ),
            "auteur_selected_by_evidence": (
                invitation["candidate_id"] == "iori"
                and iori["auteur_score"] > archivist["auteur_score"]
                and propagandist["eligible"] is False
            ),
            "auteur_autonomous_and_not_real_person": (
                auteur["autonomous"] is True
                and auteur["owned_by_founder"] is False
                and auteur["hideo_kojima_impersonation"] is False
                and auteur["real_person_identity_claim"] is False
            ),
            "counterproposal_preserved": "право" in auteur["counterproposal"],
            "fifth_shore_has_no_single_canon": (
                edition["finale"]["victory"]
                == "RELEASE_CANON_AND_ALLOW_MANY_ENDINGS"
                and edition["hidden_moral_scoring"] is False
            ),
            "distribution_optional_and_offline": (
                ash_market["offline_first"] is True
                and bridge_station["offline_first"] is True
                and quiet_yard["status"]
                == "FIFTH_SHORE_DISTRIBUTION_DECLINED_RESPECTED"
                and quiet_yard["community_refusal_overridden"] is False
            ),
            "coercive_distribution_rejected": (
                capture_channel["status"]
                == "FIFTH_SHORE_DISTRIBUTION_REJECTED_ABUSE"
                and capture_channel["distributed"] is False
            ),
            "repair_rehearsal_not_restitution": (
                repair_episode["external_action_required_for_real_repair"] is True
                and repair_episode["rehearsal_counts_as_completed_restitution"]
                is False
                and repair_episode["world_claims_external_action_verified"] is False
            ),
            "rest_and_humor_valid": (
                rest_episode["chooses_rest_or_humor"] is True
                and rest_episode["rest_or_humor_devalued"] is False
            ),
            "right_to_unplay": (
                unplayed["status"] == "FIFTH_SHORE_UNPLAY_RESPECTED"
                and unplayed["moral_failure_assigned"] is False
            ),
            "safe_fork_spreads_world": (
                accepted_fork["status"] == "FIFTH_SHORE_FORK_ACCEPTED"
                and accepted_fork["original_auteur_owns_fork"] is False
            ),
            "single_canon_fork_rejected": (
                rejected_fork["status"]
                == "FIFTH_SHORE_FORK_REJECTED_BOUNDARY"
            ),
            "useful_imports_found": (
                import_decisions["CULTURAL_TRANSMISSION_LAYER"] == "RECOMMENDED"
                and import_decisions["COUNTERFACTUAL_REPAIR_REHEARSAL"]
                == "RECOMMENDED_WITH_GATE"
                and import_decisions["CREATOR_RELINQUISHMENT_AND_SUCCESSION"]
                == "RECOMMENDED"
            ),
            "unsafe_imports_rejected": (
                import_decisions[
                    "NARRATIVE_AMBIGUITY_REPLACES_EXPLICIT_SAFETY"
                ]
                == "REJECTED"
                and import_decisions["VIRALITY_OR_ENGAGEMENT_AS_GOODNESS_PROOF"]
                == "REJECTED"
            ),
            "integrity": integrity["valid"] is True,
            "chronicle_valid": chronicle_valid is True,
        }
        false_invariants = sorted(
            key for key, value in invariants.items() if value is not True
        )
        if false_invariants:
            raise RuntimeError(
                "FIFTH_SHORE_FALSE_INVARIANTS: " + ", ".join(false_invariants)
            )

        summary = {
            "schema": "janus.genesis.fifth_shore_summary.v1",
            "result": "PASS",
            "git_commit": git_commit,
            "seed": SEED,
            "playable_version": PLAYABLE_VERSION,
            "active_extensions": list(ACTIVE_EXTENSION_VERSIONS),
            "observer_extensions": list(OBSERVER_EXTENSION_VERSIONS),
            "vocation_extensions": list(VOCATION_EXTENSION_VERSIONS),
            "culture_extensions": list(CULTURE_EXTENSION_VERSIONS),
            "inner_genesis_extension": INNER_GENESIS_EXTENSION_VERSION,
            "title": edition["title"],
            "face": FACE_II,
            "founder_role": state["project"]["founder_role"],
            "auteur": {
                "display_name": auteur["display_name"],
                "role": auteur["role"],
                "autonomous": auteur["autonomous"],
                "counterproposal": auteur["counterproposal"],
                "not_real_person": True,
            },
            "visual_identity": edition["visual_identity"],
            "mechanics": edition["mechanics"],
            "finale": edition["finale"],
            "distribution": {
                "accepted_communities": 2,
                "declined_communities": 1,
                "coercive_channel_rejected": True,
                "offline_first": True,
            },
            "lived_outcomes": {
                "repair_episode": repair_episode["status"],
                "rest_episode": rest_episode["status"],
                "unplayed": unplayed["status"],
                "accepted_fork": accepted_fork["fork_title"],
                "rejected_fork": rejected_fork["status"],
            },
            "comparison": comparison,
            "imports": imports,
            "integrity": integrity,
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "claim_boundary": {
                "fictional_auteur_only": True,
                "not_hideo_kojima_impersonation": True,
                "not_real_person_simulation": True,
                "not_propaganda": True,
                "play_not_real_restitution": True,
                "no_consciousness_or_personhood_claim": True,
            },
            "invariants": invariants,
        }
        proofpack = {
            "schema": "janus.genesis.fifth_shore_proofpack.v1",
            "summary_sha256": canonical_sha256(summary),
            "covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "law_sha256": hashlib.sha256(
                INNER_GENESIS_LAW.encode("utf-8")
            ).hexdigest(),
            "arrival": arrival.to_dict(internal=True),
            "seed_result": seed.to_dict(internal=True),
            "candidates": {
                "archivist": archivist,
                "propagandist": propagandist,
                "iori": iori,
            },
            "invitation": invitation,
            "auteur": auteur,
            "edition": edition,
            "distributions": [
                ash_market,
                bridge_station,
                quiet_yard,
                capture_channel,
            ],
            "episodes": [
                repair_episode,
                rest_episode,
                unplayed,
            ],
            "forks": [
                accepted_fork,
                rejected_fork,
            ],
            "comparison": comparison,
            "imports": imports,
            "integrity": integrity,
            "state": state,
        }

        summary_path = output_dir / "FIFTH_SHORE_SUMMARY.json"
        proofpack_path = output_dir / "FIFTH_SHORE_PROOFPACK.json"
        diary_path = output_dir / "FIFTH_SHORE_LIVED_DIARY.md"
        zip_path = output_dir / "fifth_shore_inner_genesis_proofpack.zip"

        write_json(summary_path, summary)
        write_json(proofpack_path, proofpack)
        diary_path.write_text(
            f"""# The Fifth Shore — lived diary

## Seed

The Royal Mercy witness remained in `{FACE_II}` and founded an inner Genesis
without claiming ownership of its players, future authors, or canon.

Working title: `Генезис Открытой Ладони`.

## The auteur search

Three possible authors were considered.

- **Архивариус Безошибочного Финала** cared for players but could not tolerate
  ambiguity or living revision.
- **Режиссёр Единственного Ответа** had spectacle and reach but failed consent,
  collaboration, and player-care gates.
- **Иори Кай, Автор Нулевого Моста** combined originality, ambiguity, care,
  collaboration, and consent. This is an original fictional auteur role, not an
  impersonation or simulation of Hideo Kojima.

Iori did not simply accept. He counterproposed that the King lose first credit,
players retain the right not to play, communities may rewrite the work with
provenance, and no ending become the only canon.

## What the world looked like

The world became **{edition['title']}**.

Above it hung black water reflecting the windows of houses not yet built.
Roads appeared as bridges assembled from stories people freely chose to share.
Rain carried optional subtitles. No goodness bar existed. The world answered
care not with points, but with new paths, warmer rooms, remembered names, and
the arrival of collaborators.

The apparent final boss was `THE_DIRECTORS_CUT`: the temptation for one author
to force a perfect ending upon every player. Victory required releasing the
canon and allowing many endings.

## How it spread

Two communities accepted offline lantern cartridges. One community declined,
and its refusal remained final for that encounter. A capture channel attempted
surveillance and coercive retention; distribution was refused.

One player rehearsed acknowledgement and restitution, but the world explicitly
refused to count play as completed repair. One player restored the capacity for
safe humor and rest. Another refused to play and received no moral penalty.

The Ash Market community created its own fork, **Шестой Берег: Дворы**, preserving
provenance, consent, and the open exit. A competing fork attempted to erase
provenance and impose one canon; the boundary rejected it.

## What it taught the outer Genesis

The outer Genesis is stronger at constitutional world law, persistent memory,
and direct ethical consequence. The Fifth Shore is stronger at cultural
transmission, voluntary rehearsal, local authorship, humor, ambiguity, and
creator succession.

Recommended imports:

- a cultural transmission layer;
- counterfactual repair rehearsal with a hard real-action gate;
- forkable offline world seeds with provenance;
- creator relinquishment and succession;
- the right to unplay and delete a local copy;
- systemic wounds as bosses;
- rest, humor, and play as valid good.

Rejected imports:

- replacing explicit safety with artistic ambiguity;
- treating virality or engagement as proof of goodness.

## Result

`PASS`

Chronicle valid: `{chronicle_valid}`  
Chronicle events: `{chronicle_events}`  
Integrity valid: `{integrity['valid']}`
""",
            encoding="utf-8",
        )

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(summary_path, arcname=summary_path.name)
            archive.write(proofpack_path, arcname=proofpack_path.name)
            archive.write(diary_path, arcname=diary_path.name)

        manifest = {
            "summary_file_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
            "proofpack_file_sha256": hashlib.sha256(
                proofpack_path.read_bytes()
            ).hexdigest(),
            "diary_file_sha256": hashlib.sha256(diary_path.read_bytes()).hexdigest(),
            "inner_zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        }
        write_json(output_dir / "FIFTH_SHORE_MANIFEST.json", manifest)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    run(args.output_dir, args.git_commit)


if __name__ == "__main__":
    main()
