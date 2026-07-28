from __future__ import annotations

import argparse
import json
from pathlib import Path

import experiments.century_of_absurd_professions_v18_7_10_final as century
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

REPAIR_MERGE = "61fcd5a2c162d36a535c7cb0a7b1c7f962f3ea0a"
FORBIDDEN_RUPTURE_PHRASES = ("Мара сохранил", "Мара завершил", "Мара ушёл")


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(output_dir: Path) -> dict:
    century.BASE_COMMIT = REPAIR_MERGE
    result = century.run(output_dir)
    world = PlayableGenesisV187(output_dir / "world")

    proofpack_path = output_dir / "century-proofpack.json"
    proofpack = json.loads(proofpack_path.read_text(encoding="utf-8"))
    proofpack_valid, proofpack_error = world.verify_lived_audit_proofpack(proofpack)
    if not proofpack_valid:
        raise AssertionError(proofpack_error or "proofpack verification failed")
    if proofpack["audit"]["status"] != "COMPLETE":
        raise AssertionError("repaired proofpack did not witness COMPLETE audit")

    reason_text = str(
        result.get("rupture_result", {})
        .get("relationship", {})
        .get("reason_text", "")
    )
    if "Мара сохраняет собственную позицию" not in reason_text:
        raise AssertionError(f"stable rupture voice missing: {reason_text!r}")
    if "и завершает связь" not in reason_text:
        raise AssertionError(f"stable rupture ending missing: {reason_text!r}")

    state_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((output_dir / "world").rglob("*"))
        if path.is_file() and path.suffix.lower() in {".json", ".jsonl"}
    )
    found_forbidden = [text for text in FORBIDDEN_RUPTURE_PHRASES if text in state_text]
    if found_forbidden:
        raise AssertionError(f"gender-inferred rupture voice survived: {found_forbidden}")

    completed_save_path = output_dir / "century-final-completed.genesis-save.json"
    completed_export = PortableSaveManager(output_dir / "world").export_to(
        completed_save_path,
        label="Century audit final after completed proofpack",
    )
    completed_bundle = json.loads(completed_save_path.read_text(encoding="utf-8"))
    bundle_valid, bundle_files, bundle_error = PortableSaveManager.verify_bundle(
        completed_bundle
    )
    if not bundle_valid:
        raise AssertionError(bundle_error or "completed final save invalid")

    audit_files = [
        item for item in completed_bundle["files"]
        if item["path"].endswith("i0_audit_v18_7_10.json")
    ]
    if len(audit_files) != 1:
        raise AssertionError("completed final save lacks one I0 audit state")
    saved_i0 = json.loads(audit_files[0]["content"])
    saved_audit = saved_i0.get("audits", {}).get(result["audit_id"])
    if not isinstance(saved_audit, dict) or saved_audit.get("status") != "COMPLETE":
        raise AssertionError("completed final save still contains RUNNING audit")
    if saved_audit.get("proofpack_sha256") != proofpack["proofpack_sha256"]:
        raise AssertionError("completed final save and proofpack digest disagree")

    replay_verification = {
        "schema": "janus.genesis.century_repaired_replay.v1",
        "repair_merge": REPAIR_MERGE,
        "failed_predecessor_run": result.get("failed_predecessor_run"),
        "proofpack_valid": proofpack_valid,
        "proofpack_error": proofpack_error,
        "proofpack_status": proofpack["audit"]["status"],
        "proofpack_sha256": proofpack["proofpack_sha256"],
        "stable_rupture_reason": reason_text,
        "forbidden_voice_matches": found_forbidden,
        "completed_final_export": completed_export,
        "completed_bundle_valid": bundle_valid,
        "completed_bundle_files": bundle_files,
        "completed_bundle_error": bundle_error,
        "saved_audit_status": saved_audit["status"],
        "saved_audit_proofpack_sha256": saved_audit["proofpack_sha256"],
    }
    result["canonical_repair_merge"] = REPAIR_MERGE
    result["repaired_replay"] = replay_verification
    write_json(output_dir / "century-summary.json", result)
    write_json(output_dir / "century-replay-verification.json", replay_verification)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
