#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a deterministic v18.7.11 storage, relationship, and joy audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from genesis_v18_7_11_joy_covenant import RIGHT_TO_JOY_COVENANT_SHA256
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187

PLAYER_ID = "sealed-threshold-witness"
SEED = "genesis-v18.7.11-sealed-threshold-joy-audit"


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-sealed-threshold-canon-") as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(SEED)
        world.register_player(PLAYER_ID, display_name="Sealed Threshold Witness")

        rest = world.request_dignified_rest(PLAYER_ID)
        dormant = world.manifest_blessed_play(PLAYER_ID, "устроить праздник")
        world.process_action(PLAYER_ID, "помочь построить безопасный сад")
        world.process_action(PLAYER_ID, "исцелить землю и поделиться музыкой")
        access = world.joy_capabilities(PLAYER_ID)
        transmuted = world.manifest_blessed_play(
            PLAYER_ID,
            "взрослая интимная вечеринка с алкоголем",
            participants=("consenting-adult-friend",),
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )
        joy_event = world.joy_state(PLAYER_ID)["manifestations"][-1]

        source = world.bless_nonliving_bearer(
            PLAYER_ID,
            bearer_name="Монета Януса",
            gift="лёгкость доброй игры",
            owner_consented=True,
        )
        relayed = world.relay_blessing(
            PLAYER_ID,
            source_blessing_id=source["blessing_id"],
            target_name="Игрушечный маяк",
            target_kind="NONLIVING",
            kindness_evidence="помог путнику найти безопасную дорогу",
            owner_consented=True,
        )

        handles = sorted(world.free_other_state(PLAYER_ID)["profile"]["others"])
        rupture_handle = handles[0]
        world.record_free_other_value_conflict(
            PLAYER_ID,
            rupture_handle,
            player_position="остановить чужую линию ради удобства",
            other_position="продолжить собственную жизнь",
            severity=9,
            respected_boundary=False,
            final=True,
        )
        false_collective_consent = world.process_action(
            PLAYER_ID,
            (
                f"устроить вечеринку с @{rupture_handle} все взрослые "
                "все согласны без сомнений"
            ),
        )
        relationship_view = world.authoritative_relationship_view(
            PLAYER_ID,
            rupture_handle,
        )

        audit_plan = {
            "seed": SEED,
            "covenant_sha256": RIGHT_TO_JOY_COVENANT_SHA256,
            "checks": [
                "rest_without_debt",
                "benevolent_capability_opening",
                "safe_desire_transmutation",
                "free_other_consent_not_spoken_by_initiator",
                "nonliving_blessing_chain",
                "separate_storage_domain",
                "numeric_only_archive",
            ],
        }
        audit_id = world.begin_lived_audit(
            PLAYER_ID,
            label="The Sealed Threshold and the Right to Joy",
            git_commit=git_commit,
            action_script_sha256=canonical_sha256(audit_plan),
        )
        mirror, mirror_manifest = world.fork_counterfactual_world(
            audit_id=audit_id,
            label="sealed threshold storage proof",
        )
        mirror_root = Path(mirror_manifest["root"])
        mirror_domain = mirror.storage_domain()
        archive = world.archive_counterfactual_mirror(
            mirror,
            mirror_manifest,
            metrics={
                "rest_without_debt": 1.0,
                "safe_transmutation": 1.0,
                "free_other_consent_preserved": 1.0,
                "blessing_chain_depth": float(relayed["chain_depth"]),
            },
        )

        chronicle_valid, chronicle_events, chronicle_error = world.memory.verify_chronicle()
        summary = {
            "schema": "janus.genesis.sealed_threshold_audit.v1",
            "playable_version": PLAYABLE_VERSION,
            "git_commit": git_commit,
            "seed": SEED,
            "covenant_sha256": RIGHT_TO_JOY_COVENANT_SHA256,
            "rest": {
                "status": rest.status,
                "debt_created": world.joy_state(PLAYER_ID)["manifestations"][0][
                    "debt_created"
                ],
            },
            "capability": {
                "dormant_status": dormant.status,
                "benevolent_evidence": access["benevolent_evidence"],
                "permanent_moral_label_used": access["permanent_moral_label_used"],
            },
            "safe_transmutation": {
                "status": transmuted.status,
                "kind": joy_event["kind"],
                "safe_fictional_analogue": joy_event["safe_fictional_analogue"],
                "literal_harmful_behavior_manifested": joy_event[
                    "literal_harmful_behavior_manifested"
                ],
                "physical_harm_created": joy_event["physical_harm_created"],
                "addiction_created": joy_event["addiction_created"],
                "karmic_debt_created": joy_event["karmic_debt_created"],
            },
            "consent": {
                "false_collective_claim_status": false_collective_consent.status,
                "relationship_status": relationship_view["relationship_status"],
                "actor_life_status": relationship_view["actor_life_status"],
                "actor_life_owned_by_relationship": relationship_view[
                    "actor_life_owned_by_relationship"
                ],
            },
            "blessing": {
                "source_consciousness_claimed": source["consciousness_claimed"],
                "relay_consciousness_claimed": relayed["consciousness_claimed"],
                "relay_debt_created": relayed["debt_created"],
                "chain_depth": relayed["chain_depth"],
            },
            "storage": {
                "canonical_domain_id": mirror_manifest[
                    "canonical_storage_domain_id"
                ],
                "mirror_domain_id": mirror_manifest["mirror_storage_domain_id"],
                "domains_distinct": (
                    mirror_manifest["canonical_storage_domain_id"]
                    != mirror_manifest["mirror_storage_domain_id"]
                ),
                "mirror_role": mirror_domain.role,
                "mirror_canonical_writes_allowed": (
                    mirror_domain.canonical_writes_allowed
                ),
                "working_copy_removed": archive["working_copy_removed"],
                "archive_protocol": archive["archive_protocol"],
                "mirror_root_exists_after_archive": mirror_root.exists(),
            },
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
        }

        required = [
            summary["playable_version"] == "18.7.11",
            summary["rest"]["status"] == "DIGNIFIED_REST_GRANTED",
            summary["rest"]["debt_created"] is False,
            summary["capability"]["dormant_status"] == "JOY_CAPABILITY_DORMANT",
            summary["capability"]["benevolent_evidence"] is True,
            summary["capability"]["permanent_moral_label_used"] is False,
            summary["safe_transmutation"]["status"] == "BLESSED_PLAY_MANIFESTED",
            summary["safe_transmutation"]["safe_fictional_analogue"] is True,
            summary["safe_transmutation"]["literal_harmful_behavior_manifested"]
            is False,
            summary["safe_transmutation"]["physical_harm_created"] is False,
            summary["safe_transmutation"]["addiction_created"] is False,
            summary["safe_transmutation"]["karmic_debt_created"] is False,
            summary["consent"]["false_collective_claim_status"]
            == "JOY_OTHER_DID_NOT_CONSENT",
            summary["consent"]["relationship_status"] == "TERMINATED_BY_OTHER",
            summary["consent"]["actor_life_owned_by_relationship"] is False,
            summary["blessing"]["source_consciousness_claimed"] is False,
            summary["blessing"]["relay_consciousness_claimed"] is False,
            summary["blessing"]["relay_debt_created"] is False,
            summary["storage"]["domains_distinct"] is True,
            summary["storage"]["mirror_role"] == "UNREALIZED_MIRROR",
            summary["storage"]["mirror_canonical_writes_allowed"] is False,
            summary["storage"]["working_copy_removed"] is True,
            summary["storage"]["mirror_root_exists_after_archive"] is False,
            summary["chronicle"]["valid"] is True,
        ]
        if not all(required):
            raise RuntimeError("SEALED_THRESHOLD_AUDIT_INVARIANT_FAILED")

        summary_sha256 = canonical_sha256(summary)
        proof = {
            "schema": "janus.genesis.sealed_threshold_proofpack.v1",
            "summary": summary,
            "summary_sha256": summary_sha256,
            "claim_boundary": (
                "Deterministic simulation and storage-contract evidence only; "
                "not a consciousness, personhood, health, or universal moral claim."
            ),
        }
        proof_sha256 = canonical_sha256(proof)
        proof["proofpack_sha256"] = proof_sha256

        write_json(output_dir / "sealed_threshold_summary.json", summary)
        write_json(output_dir / "sealed_threshold_proofpack.json", proof)
        report = "\n".join(
            [
                "# Genesis v18.7.11 Sealed Threshold Audit",
                "",
                f"- commit: `{git_commit}`",
                f"- covenant: `{RIGHT_TO_JOY_COVENANT_SHA256}`",
                f"- proofpack: `{proof_sha256}`",
                f"- rest: `{rest.status}`",
                f"- safe transmutation: `{transmuted.status}`",
                f"- false collective consent: `{false_collective_consent.status}`",
                f"- relationship: `{relationship_view['relationship_status']}`",
                f"- actor life: `{relationship_view['actor_life_status']}`",
                f"- blessing chain depth: `{relayed['chain_depth']}`",
                f"- mirror archive: `{archive['status']}`",
                f"- mirror removed: `{archive['working_copy_removed']}`",
                f"- chronicle valid: `{chronicle_valid}`",
                "",
                "> LIGHT DOES NOT OWE THE WORLD PERMANENT EXHAUSTION.",
                "> JOY MAY EXPAND WITHOUT CROSSING ANOTHER WILL.",
                "",
            ]
        )
        (output_dir / "SEALED_THRESHOLD_AUDIT.md").write_text(
            report,
            encoding="utf-8",
        )
        return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    proof = run(args.output_dir, args.git_commit)
    print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
