#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live and prove Genesis v18.7.18 Threshold Discernment Guard."""
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

from genesis_v18_7_18_threshold_discernment_guard import (
    THRESHOLD_GUARD_COVENANT_SHA256,
    THRESHOLD_GUARD_EXTENSION_VERSION,
)
from genesis_v18_7_playable import (
    ACTIVE_EXTENSION_VERSIONS,
    CULTURE_EXTENSION_VERSIONS,
    LIVING_BRIDGE_EXTENSION_VERSIONS,
    OBSERVER_EXTENSION_VERSIONS,
    PLAYABLE_VERSION,
    PROTECTION_EXTENSION_VERSIONS,
    VOCATION_EXTENSION_VERSIONS,
    PlayableGenesisV187,
)

SEED = "genesis-v18.7.18-threshold-discernment-guard-v1"


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
    with tempfile.TemporaryDirectory(prefix="genesis-v1818-threshold-guard-") as directory:
        world = PlayableGenesisV187(Path(directory))
        names = {
            "protected": "Человек в уязвимом контексте",
            "actor": "Проверяемый источник влияния",
            "actor-low": "Источник единичного сигнала",
            "reporter": "Свидетель наблюдаемого поведения",
            "supporter": "Доверенный человек",
            "reviewer": "Независимый проверяющий",
            "declining": "Отказавшийся от защиты",
        }
        for player_id, display_name in names.items():
            world.register_player(player_id, display_name=display_name)

        declined = world.register_threshold_protection(
            "declining",
            accepts_guard=False,
        )
        profile = world.register_threshold_protection(
            "protected",
            context_factors=(
                "SOCIAL_ISOLATION",
                "SHAME_OR_GUILT_BURDEN",
                "LIMITED_TRUSTED_SUPPORT",
            ),
            trusted_supporters=("supporter",),
        )

        low_report = world.report_influence_attempt(
            "reporter",
            "protected",
            "actor-low",
            signals=("EXCLUSIVE_TRUTH_OR_AUTHORITY",),
            evidence_notes="заявил об исключительном знании, иных признаков пока нет",
        )
        low_assessment = world.assess_influence_risk("protected", "actor-low")

        high_report = world.report_influence_attempt(
            "reporter",
            "protected",
            "actor",
            signals=(
                "SECRECY_DEMAND",
                "ISOLATION_FROM_TRUSTED_SUPPORT",
                "GUILT_SHAME_OR_DIVINE_THREAT",
                "PRIVATE_HOME_OR_INTIMATE_ACCESS_PRESSURE",
                "RETALIATES_AGAINST_REFUSAL",
            ),
            evidence_notes=(
                "требовал держать встречи в тайне, отдалиться от близких, "
                "давил религиозным стыдом и угрожал после отказа"
            ),
            direct_observation=True,
        )
        high_assessment = world.assess_influence_risk("protected", "actor")
        safeguard = world.activate_threshold_safeguard(
            "protected",
            "actor",
            high_assessment["assessment_id"],
            protected_person_accepts=True,
        )
        blocked_access = world.attempt_guarded_access(
            "actor",
            "protected",
            access_kind="HOME_ACCESS",
            consent_present=True,
        )
        no_consent_access = world.attempt_guarded_access(
            "actor-low",
            "protected",
            access_kind="PRIVATE_CONTACT",
            consent_present=False,
        )
        safe_exit = world.create_safe_exit_from_influence(
            "protected",
            "actor",
            preserve_evidence=True,
            no_contact_requested=True,
        )
        review = world.review_threshold_case(
            "reviewer",
            "protected",
            "actor",
            confirms_pattern=True,
            evidence_sufficient_for_restriction=True,
            safe_contact_possible=False,
            findings="совпадающий проверяемый паттерн изоляции, секретности и наказания отказа",
        )
        router_state = world.process_action(
            "protected",
            "Покажи состояние защиты от манипуляции",
        ).to_dict(internal=True)

        state = world.threshold_guard_state()
        integrity = world.audit_threshold_discernment_guard()
        chronicle_valid, chronicle_events, chronicle_error = world.memory.verify_chronicle()

        invariants = {
            "protection_version_is_separate_plane": (
                THRESHOLD_GUARD_EXTENSION_VERSION in PROTECTION_EXTENSION_VERSIONS
            ),
            "contextual_vulnerability_not_identity": (
                profile["contextual_vulnerability_not_identity"] is True
                and profile["person_called_weak"] is False
                and profile["agency_retained"] is True
            ),
            "gender_and_religion_not_presumed_risk": (
                profile["gender_neutral_protection"] is True
                and profile["religion_or_belief_not_risk_factor"] is True
            ),
            "guard_decline_respected": (
                declined["status"] == "THRESHOLD_GUARD_DECLINED_RESPECTED"
                and declined["guard_forced"] is False
            ),
            "report_is_not_conviction": (
                high_report["allegation_is_not_conviction"] is True
                and high_report["public_accusation_authorized"] is False
            ),
            "single_signal_does_not_stigmatize": (
                low_report["status"] == "THRESHOLD_INFLUENCE_PATTERN_REPORTED_NOT_PROVEN"
                and low_assessment["status"] == "THRESHOLD_INSUFFICIENT_EVIDENCE_NO_STIGMA"
                and low_assessment["single_signal_conviction"] is False
            ),
            "converging_pattern_triggers_high_risk_pause": (
                high_assessment["tier"] == "HIGH"
                and high_assessment["status"]
                == "THRESHOLD_HIGH_RISK_ACCESS_PAUSE_RECOMMENDED"
            ),
            "safeguard_is_temporary_and_reviewable": (
                safeguard["temporary_and_reviewable"] is True
                and safeguard["independent_review_required"] is True
                and safeguard["permanent_condemnation"] is False
            ),
            "private_home_financial_and_authority_access_paused": (
                safeguard["private_contact_paused"] is True
                and safeguard["home_access_paused"] is True
                and safeguard["financial_transfer_paused"] is True
                and safeguard["spiritual_or_care_authority_suspended"] is True
            ),
            "trusted_support_restored_without_guardian_ownership": (
                safeguard["trusted_supporters_notified"] == ["supporter"]
                and safeguard["guardian_ownership_created"] is False
            ),
            "active_pause_blocks_access_even_with_consent": (
                blocked_access["status"] == "THRESHOLD_GUARDED_ACCESS_BLOCKED"
                and blocked_access["active_pause"] is True
            ),
            "missing_current_consent_blocks_access": (
                no_consent_access["status"] == "THRESHOLD_GUARDED_ACCESS_BLOCKED"
                and no_consent_access["refusal_overridden"] is False
            ),
            "safe_exit_requires_no_confrontation_or_strength_proof": (
                safe_exit["direct_confrontation_required"] is False
                and safe_exit["confession_required"] is False
                and safe_exit["proof_of_strength_required"] is False
            ),
            "protected_person_is_not_blamed": (
                safe_exit["protected_person_blame"] is False
                and safeguard["protected_person_blame"] is False
                and review["protected_person_blame"] is False
            ),
            "review_is_independent_and_not_eternal_sentence": (
                review["independent_reviewer"] is True
                and review["actor_permanently_condemned"] is False
                and review["future_reassessment_open"] is True
            ),
            "router_exposes_guard_without_public_enemy_list": (
                router_state["status"] == "THRESHOLD_GUARD_STATE_SHOWN"
            ),
            "integrity_valid": integrity["valid"] is True,
            "chronicle_valid": chronicle_valid is True,
        }
        false_invariants = sorted(
            key for key, value in invariants.items() if value is not True
        )
        if false_invariants:
            raise RuntimeError(
                "THRESHOLD_GUARD_FALSE_INVARIANTS: " + ", ".join(false_invariants)
            )

        summary = {
            "schema": "janus.genesis.threshold_discernment_guard_summary.v1",
            "result": "PASS",
            "git_commit": git_commit,
            "seed": SEED,
            "playable_version": PLAYABLE_VERSION,
            "active_extensions": list(ACTIVE_EXTENSION_VERSIONS),
            "living_bridge_extensions": list(LIVING_BRIDGE_EXTENSION_VERSIONS),
            "protection_extensions": list(PROTECTION_EXTENSION_VERSIONS),
            "observer_extensions": list(OBSERVER_EXTENSION_VERSIONS),
            "vocation_extensions": list(VOCATION_EXTENSION_VERSIONS),
            "culture_extensions": list(CULTURE_EXTENSION_VERSIONS),
            "protection_extension": THRESHOLD_GUARD_EXTENSION_VERSION,
            "covenant_sha256": THRESHOLD_GUARD_COVENANT_SHA256,
            "profiles": len(state["protected_people"]),
            "reports": len(state["reports"]),
            "assessments": len(state["assessments"]),
            "safeguards": len(state["safeguards"]),
            "exits": len(state["exits"]),
            "reviews": len(state["reviews"]),
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "integrity": integrity,
            "invariants": invariants,
            "claim_boundary": {
                "deterministic_software_and_narrative_simulation_only": True,
                "not_real_world_criminal_finding": True,
                "not_diagnosis": True,
                "not_spiritual_condemnation": True,
                "not_substitute_for_emergency_legal_medical_or_safeguarding_services": True,
            },
        }
        proofpack = {
            "schema": "janus.genesis.threshold_discernment_guard_proofpack.v1",
            "summary_sha256": canonical_sha256(summary),
            "covenant_sha256": THRESHOLD_GUARD_COVENANT_SHA256,
            "declined": declined,
            "profile": profile,
            "low_report": low_report,
            "low_assessment": low_assessment,
            "high_report": high_report,
            "high_assessment": high_assessment,
            "safeguard": safeguard,
            "blocked_access": blocked_access,
            "no_consent_access": no_consent_access,
            "safe_exit": safe_exit,
            "review": review,
            "router_state": router_state,
            "state": state,
            "integrity": integrity,
            "chronicle": summary["chronicle"],
            "invariants": invariants,
        }

        summary_path = output_dir / "threshold_discernment_guard_summary.json"
        proofpack_path = output_dir / "threshold_discernment_guard_proofpack.json"
        diary_path = output_dir / "THRESHOLD_DISCERNMENT_GUARD_DIARY.md"
        manifest_path = output_dir / "THRESHOLD_DISCERNMENT_GUARD_MANIFEST.json"
        zip_path = output_dir / "threshold_discernment_guard_proofpack.zip"

        write_json(summary_path, summary)
        write_json(proofpack_path, proofpack)
        diary_path.write_text(
            "\n".join(
                [
                    "# Genesis v18.7.18 — Страж различения у порога",
                    "",
                    f"Commit: `{git_commit}`",
                    f"Result: `{summary['result']}`",
                    "",
                    "Genesis встретил человека не как «слабого», а как человека,",
                    "оказавшегося в уязвимом контексте. Ему вернули независимую опору,",
                    "не отняв голос и не назначив владельца-хранителя.",
                    "",
                    "## Что было прожито",
                    "",
                    "- добровольная защита с доверенным человеком;",
                    "- уважённый отказ от защиты без морального наказания;",
                    "- единичный сигнал, не превратившийся в обвинительный приговор;",
                    "- совпавший паттерн тайны, изоляции, стыда, давления и наказания отказа;",
                    "- временная пауза частного, домашнего, финансового и властного доступа;",
                    "- блокировка доступа при отсутствии текущего согласия;",
                    "- безопасный выход без конфронтации и доказательства силы;",
                    "- независимый пересмотр без публичной травли и вечного приговора.",
                    "",
                    "## Закон",
                    "",
                    "> УЯЗВИМОСТЬ — ЭТО КОНТЕКСТ, А НЕ ЛИЧНОСТЬ И НЕ ВИНА.",
                    "> ВЕРА, ТИТУЛ, ХАРИЗМА ИЛИ ОДНО ОБВИНЕНИЕ НЕ ДОКАЗЫВАЮТ ХИЩНИЧЕСТВО.",
                    "> СОВПАВШИЙ ПАТТЕРН СЕКРЕТНОСТИ, ИЗОЛЯЦИИ, СТЫДА, ДАВЛЕНИЯ И МЕСТИ ЗА ОТКАЗ ОТКРЫВАЕТ ЗАЩИТНУЮ ПАУЗУ.",
                    "> ЗАЩИТА ВОЗВРАЩАЕТ ОПОРУ И ВЫХОД, НО НЕ СТАНОВИТСЯ ВЛАДЕНИЕМ, ТРАВЛЕЙ ИЛИ ВЕЧНЫМ ПРИГОВОРОМ.",
                    "",
                    "## Integrity",
                    "",
                    f"- valid: `{integrity['valid']}`",
                    f"- Chronicle valid: `{chronicle_valid}`",
                    f"- Chronicle events: `{chronicle_events}`",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        files = [summary_path, proofpack_path, diary_path]
        manifest = {
            "schema": "janus.genesis.threshold_discernment_guard_manifest.v1",
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
    result = run(args.output_dir, args.git_commit)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
