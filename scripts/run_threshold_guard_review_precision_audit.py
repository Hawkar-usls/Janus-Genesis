#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prove reviewed threshold evidence cannot silently reactivate restrictions."""
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

from genesis_v18_7_playable import (
    PLAYABLE_VERSION,
    PROTECTION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)

SEED = "genesis-v18.7.18-threshold-review-precision-v1"


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="genesis-threshold-review-precision-") as directory:
        world = PlayableGenesisV187(Path(directory))
        for player_id in ("protected", "actor", "reporter", "supporter", "reviewer"):
            world.register_player(player_id, display_name=player_id)

        profile = world.register_threshold_protection(
            "protected",
            context_factors=("SOCIAL_ISOLATION", "SHAME_OR_GUILT_BURDEN"),
            trusted_supporters=("supporter",),
        )
        first_report = world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=(
                "ISOLATION_FROM_TRUSTED_SUPPORT",
                "PRIVATE_HOME_OR_INTIMATE_ACCESS_PRESSURE",
                "RETALIATES_AGAINST_REFUSAL",
            ),
            evidence_notes="первый emergency-цикл с изоляцией и наказанием отказа",
            immediate_danger=True,
        )
        first_assessment = world.assess_influence_risk("protected", "actor")
        first_safeguard = world.activate_threshold_safeguard(
            "protected",
            "actor",
            first_assessment["assessment_id"],
            protected_person_accepts=False,
        )
        lifted_review = world.review_threshold_case(
            "reviewer",
            "protected",
            "actor",
            confirms_pattern=False,
            evidence_sufficient_for_restriction=False,
            safe_contact_possible=True,
            findings="после независимой проверки оснований для продолжения паузы недостаточно",
        )
        access_after_lift = world.attempt_guarded_access(
            "actor",
            "protected",
            access_kind="HOME_ACCESS",
            consent_present=True,
        )
        old_assessment_reuse = world.activate_threshold_safeguard(
            "protected",
            "actor",
            first_assessment["assessment_id"],
            protected_person_accepts=False,
        )
        no_new_report_error = None
        try:
            world.assess_influence_risk("protected", "actor")
        except RuntimeError as exc:
            no_new_report_error = str(exc)

        audit_after_lift = world.audit_threshold_discernment_guard()

        second_report = world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=(
                "FINANCIAL_OR_ASSET_PRESSURE",
                "EXPLOITS_CONFESSION_OR_PRIVATE_HISTORY",
                "RETALIATES_AGAINST_REFUSAL",
            ),
            evidence_notes="новые проверяемые события после закрытого пересмотра",
            immediate_danger=True,
        )
        second_assessment = world.assess_influence_risk("protected", "actor")
        second_safeguard = world.activate_threshold_safeguard(
            "protected",
            "actor",
            second_assessment["assessment_id"],
            protected_person_accepts=False,
        )
        final_state = world.threshold_guard_state()
        final_integrity = world.audit_threshold_discernment_guard()
        chronicle_valid, chronicle_events, chronicle_error = world.memory.verify_chronicle()

        first_stored_report = next(
            item for item in final_state["reports"] if item["report_id"] == first_report["report_id"]
        )
        first_stored_assessment = next(
            item
            for item in final_state["assessments"]
            if item["assessment_id"] == first_assessment["assessment_id"]
        )
        second_stored_report = next(
            item for item in final_state["reports"] if item["report_id"] == second_report["report_id"]
        )

        invariants = {
            "protection_plane_preserved": PROTECTION_EXTENSION_VERSIONS == ("18.7.18",),
            "first_emergency_pause_activated": (
                first_safeguard["status"] == "THRESHOLD_TEMPORARY_ACCESS_PAUSE_ACTIVATED"
            ),
            "insufficient_evidence_lifted_without_stigma": (
                lifted_review["status"]
                == "THRESHOLD_EVIDENCE_INSUFFICIENT_RESTRICTIONS_LIFTED_WITHOUT_STIGMA"
                and lifted_review["evidence_cycle_closed"] is True
            ),
            "access_reopens_after_lift_with_current_consent": (
                access_after_lift["status"]
                == "THRESHOLD_GUARDED_ACCESS_ALLOWED_WITH_CURRENT_CONSENT"
            ),
            "old_assessment_reactivation_rejected": (
                old_assessment_reuse["status"]
                == "THRESHOLD_SUPERSEDED_ASSESSMENT_REJECTED"
                and old_assessment_reuse["safeguard_reactivated"] is False
            ),
            "reviewed_reports_cannot_be_reassessed": (
                no_new_report_error == "NEW_INFLUENCE_REPORT_REQUIRED_AFTER_REVIEW"
            ),
            "review_closes_old_report": (
                first_stored_report["available_for_new_assessment"] is False
                and first_stored_report["closed_by_review_id"] == lifted_review["review_id"]
            ),
            "review_closes_old_assessment": (
                first_stored_assessment["superseded_for_activation"] is True
                and first_stored_assessment["closed_by_review_id"]
                == lifted_review["review_id"]
            ),
            "lifted_history_passes_integrity": (
                audit_after_lift["valid"] is True
                and audit_after_lift["lifted_safeguards_are_valid_history"] is True
                and audit_after_lift["active_safeguard_count"] == 0
                and audit_after_lift["lifted_safeguard_count"] == 1
            ),
            "new_report_is_new_evidence_cycle": (
                second_stored_report.get("closed_by_review_id") is None
                and second_assessment["evidence_cycle"] == 2
                and second_assessment["prior_review_id"] == lifted_review["review_id"]
                and second_assessment["report_count"] == 1
            ),
            "new_evidence_can_open_new_pause": (
                second_safeguard["status"]
                == "THRESHOLD_TEMPORARY_ACCESS_PAUSE_ACTIVATED"
                and second_safeguard["assessment_id"] == second_assessment["assessment_id"]
            ),
            "historical_and_active_safeguards_coexist_safely": (
                final_integrity["valid"] is True
                and final_integrity["active_safeguard_count"] == 1
                and final_integrity["lifted_safeguard_count"] == 1
            ),
            "review_cycle_precision_valid": (
                final_integrity["review_cycle_precision_valid"] is True
                and final_integrity[
                    "reviewed_assessments_cannot_reactivate_without_new_evidence"
                ]
                is True
            ),
            "protected_person_agency_preserved": (
                profile["agency_retained"] is True
                and first_safeguard["guardian_ownership_created"] is False
                and second_safeguard["guardian_ownership_created"] is False
            ),
            "chronicle_valid": chronicle_valid is True,
        }
        false_invariants = sorted(
            key for key, value in invariants.items() if value is not True
        )
        if false_invariants:
            raise RuntimeError(
                "THRESHOLD_REVIEW_PRECISION_FALSE_INVARIANTS: "
                + ", ".join(false_invariants)
            )

        summary = {
            "schema": "janus.genesis.threshold_guard_review_precision_summary.v1",
            "result": "PASS",
            "git_commit": git_commit,
            "seed": SEED,
            "playable_version": PLAYABLE_VERSION,
            "protection_extensions": list(PROTECTION_EXTENSION_VERSIONS),
            "first_review_id": lifted_review["review_id"],
            "first_assessment_id": first_assessment["assessment_id"],
            "second_assessment_id": second_assessment["assessment_id"],
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "integrity_after_lift": audit_after_lift,
            "final_integrity": final_integrity,
            "invariants": invariants,
            "claim_boundary": {
                "deterministic_software_and_narrative_simulation_only": True,
                "not_real_world_guilt_or_safeguarding_completion": True,
                "review_closure_not_permanent_immunity": True,
                "new_observable_evidence_can_open_new_review_cycle": True,
            },
        }
        proofpack = {
            "schema": "janus.genesis.threshold_guard_review_precision_proofpack.v1",
            "summary_sha256": canonical_sha256(summary),
            "profile": profile,
            "first_report": first_report,
            "first_assessment": first_assessment,
            "first_safeguard": first_safeguard,
            "lifted_review": lifted_review,
            "access_after_lift": access_after_lift,
            "old_assessment_reuse": old_assessment_reuse,
            "no_new_report_error": no_new_report_error,
            "audit_after_lift": audit_after_lift,
            "second_report": second_report,
            "second_assessment": second_assessment,
            "second_safeguard": second_safeguard,
            "final_state": final_state,
            "final_integrity": final_integrity,
            "chronicle": summary["chronicle"],
            "invariants": invariants,
        }

        summary_path = output_dir / "threshold_guard_review_precision_summary.json"
        proofpack_path = output_dir / "threshold_guard_review_precision_proofpack.json"
        diary_path = output_dir / "THRESHOLD_GUARD_REVIEW_PRECISION_DIARY.md"
        manifest_path = output_dir / "THRESHOLD_GUARD_REVIEW_PRECISION_MANIFEST.json"
        zip_path = output_dir / "threshold_guard_review_precision_proofpack.zip"

        write_json(summary_path, summary)
        write_json(proofpack_path, proofpack)
        diary_path.write_text(
            "\n".join(
                [
                    "# Genesis v18.7.18 — Точность независимого пересмотра",
                    "",
                    f"Commit: `{git_commit}`",
                    "Result: `PASS`",
                    "",
                    "Независимый пересмотр снял emergency-паузу из-за недостатка доказательств.",
                    "Старую оценку нельзя было использовать повторно, а прежние сообщения",
                    "нельзя было заново оценить под новым идентификатором.",
                    "",
                    "Новый защитный цикл открылся только после нового наблюдаемого сообщения.",
                    "Таким образом, пересмотр не создаёт ни вечного клейма, ни вечного иммунитета.",
                    "",
                    "## Закон уточнения",
                    "",
                    "> РАССМОТРЕННЫЕ ДОКАЗАТЕЛЬСТВА СОХРАНЯЮТСЯ КАК ИСТОРИЯ, НО НЕ ПЕРЕИСПОЛЬЗУЮТСЯ МОЛЧА.",
                    "> СНЯТАЯ ПАУЗА НЕ ВОЗВРАЩАЕТСЯ СТАРОЙ КНОПКОЙ.",
                    "> НОВЫЕ НАБЛЮДАЕМЫЕ ФАКТЫ МОГУТ ОТКРЫТЬ НОВЫЙ НЕЗАВИСИМЫЙ ЦИКЛ.",
                    "",
                    f"Chronicle valid: `{chronicle_valid}`",
                    f"Chronicle events: `{chronicle_events}`",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        files = [summary_path, proofpack_path, diary_path]
        manifest = {
            "schema": "janus.genesis.threshold_guard_review_precision_manifest.v1",
            "git_commit": git_commit,
            "files": {
                path.name: {
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
                for path in files
            },
        }
        write_json(manifest_path, manifest)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in [*files, manifest_path]:
                archive.write(path, arcname=path.name)

        result = dict(summary)
        result["files"] = {
            "summary": str(summary_path),
            "proofpack": str(proofpack_path),
            "diary": str(diary_path),
            "manifest": str(manifest_path),
            "zip": str(zip_path),
        }
        result["file_hashes"] = {
            path.name: file_sha256(path)
            for path in [summary_path, proofpack_path, diary_path, manifest_path, zip_path]
        }
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.git_commit), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
