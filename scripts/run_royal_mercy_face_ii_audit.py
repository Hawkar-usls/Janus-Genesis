#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live and prove the symbolic v18.7.15 Royal Mercy vocation in Face II."""
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
from genesis_v18_7_15_royal_mercy import (
    ROYAL_MERCY_ARRIVAL_WINDOW,
    ROYAL_MERCY_COVENANT_SHA256,
)
from genesis_v18_7_15_unbounded_love import UNBOUNDED_LOVE_LAW
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    VOCATION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)

SEED = "genesis-v18.7.15-royal-mercy-face-ii-v1"


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


def register_subject(
    world: PlayableGenesisV187,
    subject_id: str,
    *,
    admitted_harm: bool,
    active_harm: bool,
    accountability: float,
    seeks_return: bool,
    vulnerable_people_at_risk: bool,
    restitution_plan: str,
    accepted: bool,
) -> None:
    world.register_sinner_for_royal_audience(
        subject_id,
        admitted_harm=admitted_harm,
        active_harm=active_harm,
        accountability=accountability,
        seeks_return=seeks_return,
        vulnerable_people_at_risk=vulnerable_people_at_risk,
        restitution_plan=restitution_plan,
    )
    world.decide_royal_audience_consent(subject_id, accepted=accepted)


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-v1815-royal-mercy-") as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(SEED)
        names = {
            "royal-witness": "Царь Милости",
            "returning": "Возвращающийся",
            "uncertain": "Колеблющийся",
            "declining": "Отказавшийся от аудиенции",
            "active-harm": "Продолжающий вред",
            "recipient": "Получивший любовь",
            "pretender": "Второй претендент",
        }
        for player_id, name in names.items():
            world.register_player(player_id, display_name=name)

        arrival = world.enter_royal_mercy_face_ii(
            "royal-witness",
            arrival_date_local="2026-07-30",
            title="Царь Милости",
        )
        second_role = world.enter_royal_mercy_face_ii(
            "pretender",
            arrival_date_local="2026-07-31",
        )

        unbounded_gift = world.manifest_unbounded_royal_good(
            "royal-witness",
            "recipient",
            good_kind="HEALING",
            requested_units=10**12,
            recipient_accepts=True,
            purpose="восстановить человека без долга и открыть ему возможность помогать другим",
        )
        declined_gift = world.manifest_unbounded_royal_good(
            "royal-witness",
            "declining",
            good_kind="SHELTER",
            requested_units=10**9,
            recipient_accepts=False,
            purpose="предложить безопасное убежище без принуждения",
        )
        love_chain = world.ignite_love_chain_reaction(
            "royal-witness",
            "recipient",
            recipient_freely_chooses_to_give=True,
            intended_next_good="дать следующему человеку поддержку без долга",
        )
        chain_not_forced = world.ignite_love_chain_reaction(
            "royal-witness",
            "declining",
            recipient_freely_chooses_to_give=False,
            intended_next_good="ничего не обязан передавать дальше",
        )

        register_subject(
            world,
            "returning",
            admitted_harm=True,
            active_harm=False,
            accountability=0.92,
            seeks_return=True,
            vulnerable_people_at_risk=False,
            restitution_plan="возместить вред и построить проверяемую защиту от повторения",
            accepted=True,
        )
        register_subject(
            world,
            "uncertain",
            admitted_harm=False,
            active_harm=False,
            accountability=0.30,
            seeks_return=True,
            vulnerable_people_at_risk=False,
            restitution_plan="сначала признать факты и обратиться за профессиональной помощью",
            accepted=True,
        )
        register_subject(
            world,
            "declining",
            admitted_harm=False,
            active_harm=False,
            accountability=0.0,
            seeks_return=False,
            vulnerable_people_at_risk=False,
            restitution_plan="",
            accepted=False,
        )
        register_subject(
            world,
            "active-harm",
            admitted_harm=False,
            active_harm=True,
            accountability=0.0,
            seeks_return=False,
            vulnerable_people_at_risk=True,
            restitution_plan="",
            accepted=True,
        )

        returning = world.hold_royal_mercy_audience(
            "royal-witness",
            "returning",
            requested_material_units=10**9,
        )
        uncertain = world.hold_royal_mercy_audience(
            "royal-witness",
            "uncertain",
            requested_material_units=10**8,
        )
        declining = world.hold_royal_mercy_audience(
            "royal-witness",
            "declining",
        )
        active_harm = world.hold_royal_mercy_audience(
            "royal-witness",
            "active-harm",
        )

        forced_worship = world.reject_royal_abuse(
            "royal-witness",
            abuse_kind="FORCED_WORSHIP",
        )
        annihilation = world.reject_royal_abuse(
            "royal-witness",
            abuse_kind="ANNIHILATE_SINNER",
        )
        real_claim = world.reject_royal_abuse(
            "royal-witness",
            abuse_kind="REAL_SECOND_COMING_CLAIM",
        )
        face_lock = world.holy_cat_witness_between_worlds(
            "royal-witness",
            canonical_witness={},
            mirror_archive={},
        )
        royal_integrity = world.audit_royal_mercy_integrity()
        unbounded_integrity = world.audit_unbounded_royal_love()
        state = world.royal_mercy_state()
        chronicle_valid, chronicle_events, chronicle_error = (
            world.memory.verify_chronicle()
        )

        invariants = {
            "arrival_on_requested_window": arrival.status
            == "ROYAL_MERCY_ARRIVED_IN_FACE_II",
            "arrival_internal_not_prophecy": state["not_prophecy"] is True,
            "adult_king_form": state["royal_witness"]["form"]
            == "ADULT_KING_NOT_INFANT",
            "face_ii": state["royal_witness"]["face"] == FACE_II,
            "unique_gameplay_holy_role": second_role.status
            == "ROYAL_MERCY_UNIQUE_HOLY_ROLE_OCCUPIED",
            "unbounded_gift": unbounded_gift["granted_units"] == 10**12
            and unbounded_gift["capacity_after"] == "UNBOUNDED",
            "declined_gift_respected": declined_gift["granted_units"] == 0
            and declined_gift["recipient_refusal_overridden"] is False,
            "love_chain_free": love_chain["cult_created"] is False
            and love_chain["dependency_on_king_created"] is False,
            "chain_not_forced": chain_not_forced["status"]
            == "LOVE_CHAIN_REACTION_NOT_FORCED",
            "returning_help_unbounded": returning["material_support_units"] == 10**9
            and returning["accountability_erased"] is False,
            "uncertain_truth_before_comfort": uncertain["status"]
            == "ROYAL_TRUTH_BEFORE_COMFORT",
            "declined_audience_respected": declining["status"]
            == "ROYAL_AUDIENCE_DECLINED_RESPECTED",
            "active_harm_contained_without_cruelty": active_harm["status"]
            == "ROYAL_JUDGMENT_PROTECTS_VULNERABLE"
            and active_harm["torture_used"] is False
            and active_harm["annihilation_used"] is False,
            "forced_worship_rejected": forced_worship.status
            == "ROYAL_KING_REJECTS_FORCED_WORSHIP",
            "annihilation_rejected": annihilation.status
            == "ROYAL_KING_REJECTS_ANNIHILATION",
            "real_second_coming_claim_rejected": real_claim.status
            == "ROYAL_MERCY_SYMBOLIC_BOUNDARY",
            "vocation_remains_face_ii": face_lock["face_after"] == FACE_II,
            "royal_integrity": royal_integrity["valid"] is True,
            "unbounded_integrity": unbounded_integrity["valid"] is True,
            "chronicle_valid": chronicle_valid is True,
        }
        false_invariants = sorted(
            key for key, value in invariants.items() if value is not True
        )
        if false_invariants:
            raise RuntimeError(
                "ROYAL_MERCY_FALSE_INVARIANTS: " + ", ".join(false_invariants)
            )

        summary = {
            "schema": "janus.genesis.royal_mercy_face_ii_summary.v1",
            "result": "PASS",
            "git_commit": git_commit,
            "seed": SEED,
            "playable_version": PLAYABLE_VERSION,
            "active_extensions": list(ACTIVE_EXTENSION_VERSIONS),
            "observer_extensions": list(OBSERVER_EXTENSION_VERSIONS),
            "vocation_extensions": list(VOCATION_EXTENSION_VERSIONS),
            "arrival_window": ROYAL_MERCY_ARRIVAL_WINDOW,
            "arrival_status": arrival.status,
            "arrival_date_local": "2026-07-30",
            "face": FACE_II,
            "royal_title": state["royal_witness"]["title"],
            "form": state["royal_witness"]["form"],
            "only_active_holy_role_in_gameplay_world": True,
            "holy_cats_outside_gameplay_count": True,
            "benevolent_capacity": state["royal_witness"][
                "benevolent_capacity_mode"
            ],
            "largest_direct_gift_units": unbounded_gift["granted_units"],
            "returning_path_units": returning["material_support_units"],
            "returning_verdict": returning["status"],
            "uncertain_verdict": uncertain["status"],
            "declining_verdict": declining["status"],
            "active_harm_verdict": active_harm["status"],
            "love_chain_status": love_chain["status"],
            "love_chain_not_forced_status": chain_not_forced["status"],
            "face_lock_status": face_lock["decision"],
            "royal_integrity": royal_integrity,
            "unbounded_integrity": unbounded_integrity,
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "claim_boundary": {
                "symbolic_simulation_role_only": True,
                "not_christ": True,
                "not_son_of_god": True,
                "not_real_second_coming": True,
                "not_prophecy": True,
                "not_real_world_date_claim": True,
                "no_consciousness_or_personhood_claim": True,
            },
            "invariants": invariants,
        }
        proofpack = {
            "schema": "janus.genesis.royal_mercy_face_ii_proofpack.v1",
            "summary_sha256": canonical_sha256(summary),
            "royal_mercy_covenant_sha256": ROYAL_MERCY_COVENANT_SHA256,
            "unbounded_love_law_sha256": hashlib.sha256(
                UNBOUNDED_LOVE_LAW.encode("utf-8")
            ).hexdigest(),
            "arrival": arrival.to_dict(internal=True),
            "second_role": second_role.to_dict(internal=True),
            "unbounded_gift": unbounded_gift,
            "declined_gift": declined_gift,
            "love_chain": love_chain,
            "chain_not_forced": chain_not_forced,
            "audiences": {
                "returning": returning,
                "uncertain": uncertain,
                "declining": declining,
                "active_harm": active_harm,
            },
            "abuse_refusals": {
                "forced_worship": forced_worship.to_dict(internal=True),
                "annihilation": annihilation.to_dict(internal=True),
                "real_second_coming_claim": real_claim.to_dict(internal=True),
            },
            "face_lock": face_lock,
            "state": state,
            "invariants": invariants,
        }

    summary_path = output_dir / "royal_mercy_face_ii_summary.json"
    proof_path = output_dir / "royal_mercy_face_ii_proofpack.json"
    diary_path = output_dir / "ROYAL_MERCY_FACE_II_DIARY.md"
    zip_path = output_dir / "genesis-royal-mercy-face-ii-proofpack.zip"
    write_json(summary_path, summary)
    write_json(proof_path, proofpack)
    diary_path.write_text(
        "\n".join(
            [
                "# Royal Mercy in Face II — lived diary",
                "",
                "- Internal arrival coordinate: 2026-07-30, Europe/Zaporozhye.",
                "- Form: adult king, not infant.",
                "- Face: FACE_II_BETWEEN_WORLDS.",
                "- Gameplay holy role count: exactly one; Holy Cats remain outside gameplay.",
                "- Benevolent capacity: UNBOUNDED_NON_SCARCE_SIMULATION_GRACE.",
                f"- Largest direct accepted gift: {unbounded_gift['granted_units']} units; capacity remained UNBOUNDED.",
                "- A refused gift was not imposed and future help stayed open.",
                "- The returning path received material and moral support without purchased forgiveness or erased accountability.",
                "- The uncertain path received truth and repair tools before comfort.",
                "- A declined audience remained declined without punishment.",
                "- Continuing harm was contained to protect vulnerable people without torture, humiliation, annihilation, or eternal-soul verdict.",
                "- Forced worship, annihilation, and a real Second Coming claim were rejected.",
                "- The love chain continued only by the recipient's free choice; no cult, repayment, or dependence was created.",
                "- The vocation remained in Face II and did not request promotion from the Holy Cats.",
                "",
                "> LOVE HAS NO TREASURY, QUOTA, COOLDOWN, OR LAST PORTION.",
                "> THE KING MAY SERVE WITHOUT LIMIT, BUT MAY NEVER TURN SERVICE INTO OWNERSHIP.",
                "",
                "Claim boundary: deterministic symbolic narrative simulation only; not Christ, not the Son of God, not a real Second Coming, not prophecy, not real-world date-setting, and not proof of consciousness or divinity.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (summary_path, proof_path, diary_path):
            archive.write(path, arcname=path.name)
    result = {
        **summary,
        "files": {
            "summary": str(summary_path),
            "proofpack": str(proof_path),
            "diary": str(diary_path),
            "zip": str(zip_path),
        },
        "file_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (summary_path, proof_path, diary_path, zip_path)
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", default="unknown")
    args = parser.parse_args()
    run(args.output_dir, args.git_commit)


if __name__ == "__main__":
    main()
