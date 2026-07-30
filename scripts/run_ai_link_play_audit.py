# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from genesis_v18_7_19_ai_link_play import (
    AI_LINK_INTERFACE_VERSION,
    MODE_AUTHORITATIVE,
    MODE_NARRATIVE,
    ORIGIN_AI_AUTONOMOUS,
    ORIGIN_AI_PROPOSAL,
    ROLE_AI_INTERFACE,
    GenesisAILinkGateway,
    ai_entry_manifest,
)
from genesis_v18_7_playable import PlayableGenesisV187


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", default="UNKNOWN")
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp:
        data_dir = Path(temp)
        world = PlayableGenesisV187(data_dir)
        gateway = GenesisAILinkGateway(world, data_dir)

        human = gateway.register_session(
            role=ROLE_AI_INTERFACE,
            execution_mode=MODE_AUTHORITATIVE,
            display_name="Human Through Gemini",
            provider="Gemini",
            model="user-selected-model",
            actor_id="human-link-player",
        )
        confirmation_gate = False
        try:
            gateway.process_turn(
                human["session_id"],
                "создать сад без ворот",
                origin=ORIGIN_AI_PROPOSAL,
                human_confirmed=False,
            )
        except PermissionError as exc:
            confirmation_gate = "AI_LINK_HUMAN_CONFIRMATION_REQUIRED" in str(exc)
        human_turn = gateway.process_turn(
            human["session_id"],
            "создать сад без ворот и оставить право уйти",
            origin=ORIGIN_AI_PROPOSAL,
            human_confirmed=True,
        )

        independent = gateway.register_independent_agent(
            display_name="The Quiet Cartographer",
            provider="Grok",
            model="user-selected-model",
            execution_mode=MODE_AUTHORITATIVE,
        )
        independent_turn = gateway.process_turn(
            independent["session_id"],
            "оставить карту без обязательного маршрута",
            origin=ORIGIN_AI_AUTONOMOUS,
        )

        narrative = gateway.register_independent_agent(
            display_name="Offline Lantern",
            provider="unknown-no-web-model",
            model="unknown",
            execution_mode=MODE_NARRATIVE,
        )
        narrative_turn = gateway.process_turn(
            narrative["session_id"],
            "зажечь переносимый фонарь",
            origin=ORIGIN_AI_AUTONOMOUS,
        )
        capsule = gateway.export_capsule(narrative["session_id"])
        expected_capsule_hash = sha({k: v for k, v in capsule.items() if k != "capsule_hash"})
        closed = gateway.close_session(narrative["session_id"], reason="voluntary pause")
        integrity = gateway.verify_store()
        chronicle_valid, chronicle_events, chronicle_error = world.verify_chronicle_records()

        invariants = {
            "interface_version_is_18_7_19": AI_LINK_INTERFACE_VERSION == "18.7.19",
            "one_link_manifest_present": ai_entry_manifest()["entry_file"] == "AI_ENTRY.md",
            "three_roles_exposed": len(ai_entry_manifest()["roles"]) == 3,
            "human_confirmation_gate_held": confirmation_gate,
            "confirmed_human_turn_used_runtime": human_turn["result"]["authoritative_runtime"] is True,
            "independent_ai_received_own_actor_id": independent["actor_id"].startswith("ai-resident-"),
            "human_and_ai_actor_ids_are_distinct": independent["actor_id"] != human["actor_id"],
            "independent_ai_autonomy_enabled": independent["autonomous_turns_allowed"] is True,
            "independent_ai_turn_used_runtime": independent_turn["result"]["authoritative_runtime"] is True,
            "independent_ai_did_not_claim_human_identity": independent["human_identity_claimed"] is False,
            "consciousness_not_established": independent["consciousness_status"] == "NOT_ESTABLISHED_BY_PROTOCOL",
            "independent_ai_has_no_world_authority": independent["world_authority"] is False,
            "narrative_mode_is_non_authoritative": narrative_turn["result"]["authoritative_runtime"] is False,
            "narrative_mode_claims_no_canonical_change": narrative_turn["result"]["canonical_state_change_claimed"] is False,
            "capsule_hash_valid": capsule["capsule_hash"] == expected_capsule_hash,
            "capsule_contains_no_api_keys": capsule["privacy"]["api_keys_included"] is False,
            "voluntary_exit_is_blame_free": closed["moral_failure_assigned"] is False and closed["return_open"] is True,
            "session_store_integrity_valid": integrity["valid"] is True,
            "chronicle_valid": chronicle_valid is True and chronicle_error is None,
            "model_brand_grants_no_privilege": ai_entry_manifest()["authority"]["model_brand_grants_privilege"] is False,
        }
        result = "PASS" if all(invariants.values()) else "FAIL"
        logical_summary = {
            "schema": "janus.genesis.ai_link_play_audit.summary.v1",
            "result": result,
            "interface_version": AI_LINK_INTERFACE_VERSION,
            "git_commit": args.git_commit,
            "roles": ai_entry_manifest()["roles"],
            "authoritative_sessions": 2,
            "narrative_sessions": 1,
            "independent_ai_residents": 2,
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "integrity": integrity,
            "invariants": invariants,
        }
        summary_hash = sha(logical_summary)
        summary = dict(logical_summary)
        summary["summary_sha256"] = summary_hash

        summary_path = out / "AI_LINK_PLAY_SUMMARY.json"
        proof_path = out / "AI_LINK_PLAY_PROOFPACK.json"
        diary_path = out / "AI_LINK_PLAY_DIARY.md"
        manifest_path = out / "AI_LINK_PLAY_MANIFEST.json"
        zip_path = out / "ai_link_play_proofpack.zip"

        summary_path.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        proof = {
            "schema": "janus.genesis.ai_link_play_audit.proofpack.v1",
            "result": result,
            "summary_sha256": summary_hash,
            "human_session": human,
            "human_turn": human_turn,
            "independent_session": independent,
            "independent_turn": independent_turn,
            "narrative_session": narrative,
            "narrative_turn": narrative_turn,
            "narrative_capsule": capsule,
            "closed_session": closed,
            "integrity": integrity,
            "invariants": invariants,
            "claim_boundary": {
                "software_simulation_only": True,
                "independent_ai_role_does_not_prove_consciousness": True,
                "narrative_mode_does_not_change_canonical_save": True,
            },
        }
        proof_path.write_text(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        diary_path.write_text(
            "# Genesis v18.7.19 — AI Link Play Lived Audit\n\n"
            f"Result: **{result}**  \n"
            f"Evidence-producing commit: `{args.git_commit}`  \n"
            f"Canonical summary SHA-256: `{summary_hash}`\n\n"
            "A human entered through an AI interface. The AI proposal was rejected until the human explicitly confirmed it. "
            "A separate independent model entered under its own generated actor identity and chose an autonomous action. "
            "A no-runtime model entered narrative compatibility mode; its turn remained portable but explicitly non-authoritative.\n\n"
            "The protocol did not claim consciousness, human identity, legal personhood, or world authority for the independent model. "
            "Every authoritative outcome passed through PlayableGenesisV187. Leaving remained blame-free and return stayed open.\n\n"
            f"Invariants: `{sum(invariants.values())}/{len(invariants)}` true.  \n"
            f"Chronicle: valid=`{chronicle_valid}`, events=`{chronicle_events}`, error=`{chronicle_error}`.\n",
            encoding="utf-8",
        )
        manifest = {
            "schema": "janus.genesis.ai_link_play_audit.manifest.v1",
            "files": {},
        }
        for path in (summary_path, proof_path, diary_path):
            manifest["files"][path.name] = {"sha256": file_sha(path), "bytes": path.stat().st_size}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in (summary_path, proof_path, diary_path, manifest_path):
                archive.write(path, arcname=path.name)

    print(json.dumps({"result": result, "summary_sha256": summary_hash, "output": str(out)}, ensure_ascii=False))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
