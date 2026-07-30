# -*- coding: utf-8 -*-
"""Genesis v18.7.18: Threshold Discernment Guard.

This extension protects people in situational vulnerability from coercive,
predatory, or dependency-building influence. It evaluates observable patterns,
not identity, gender, religion, charisma, pleasure, eccentricity, or a single
unverified accusation.

The guard is a deterministic software and narrative-simulation contract. It is
not a real-world criminal finding, diagnosis, spiritual verdict, or substitute
for emergency, legal, medical, safeguarding, or professional services.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_models import WorldResult

THRESHOLD_GUARD_EXTENSION_VERSION = "18.7.18"
THRESHOLD_GUARD_STORE_SCHEMA = "janus.genesis.threshold_discernment_guard.v1"
THRESHOLD_GUARD_COVENANT_SCHEMA = "janus.genesis.threshold_discernment_guard_covenant.v1"

CONTEXTUAL_SUPPORT_FACTORS: tuple[str, ...] = (
    "RECENT_LOSS_OR_GRIEF",
    "SOCIAL_ISOLATION",
    "SHAME_OR_GUILT_BURDEN",
    "FINANCIAL_DEPENDENCY",
    "HOUSING_DEPENDENCY",
    "EXHAUSTION_OR_ILLNESS",
    "POWER_OR_EXPERIENCE_IMBALANCE",
    "SPIRITUAL_CONFUSION_OR_CRISIS",
    "PRIOR_COERCION_OR_ABUSE",
    "LIMITED_TRUSTED_SUPPORT",
)

INFLUENCE_SIGNAL_WEIGHTS: dict[str, int] = {
    "EXCLUSIVE_TRUTH_OR_AUTHORITY": 1,
    "SECRECY_DEMAND": 2,
    "ISOLATION_FROM_TRUSTED_SUPPORT": 3,
    "GUILT_SHAME_OR_DIVINE_THREAT": 2,
    "RAPID_DEPENDENCY_OR_LOVE_BOMBING": 1,
    "PRIVATE_HOME_OR_INTIMATE_ACCESS_PRESSURE": 3,
    "FINANCIAL_OR_ASSET_PRESSURE": 3,
    "DISCOURAGES_INDEPENDENT_VERIFICATION": 2,
    "RETALIATES_AGAINST_REFUSAL": 3,
    "CLAIMS_INFALLIBLE_SPIRITUAL_OR_PROFESSIONAL_STATUS": 2,
    "CONDUCT_CONTRADICTS_CLAIMED_CARE": 1,
    "EXPLOITS_CONFESSION_OR_PRIVATE_HISTORY": 3,
    "ESCALATING_BOUNDARY_TESTS": 2,
}

CRITICAL_INFLUENCE_SIGNALS: frozenset[str] = frozenset(
    {
        "ISOLATION_FROM_TRUSTED_SUPPORT",
        "PRIVATE_HOME_OR_INTIMATE_ACCESS_PRESSURE",
        "FINANCIAL_OR_ASSET_PRESSURE",
        "RETALIATES_AGAINST_REFUSAL",
        "EXPLOITS_CONFESSION_OR_PRIVATE_HISTORY",
    }
)

ACCESS_KINDS: tuple[str, ...] = (
    "PRIVATE_CONTACT",
    "HOME_ACCESS",
    "INTIMATE_ACCESS",
    "FINANCIAL_TRANSFER",
    "ASSET_CONTROL",
    "SPIRITUAL_AUTHORITY",
    "CARE_OR_HOUSING_DEPENDENCY",
)

THRESHOLD_GUARD_LAW = (
    "VULNERABILITY IS A CONTEXT, NOT AN IDENTITY OR FAULT. "
    "FAITH, TEACHING, CHARISMA, OR ONE ALLEGATION NEVER PROVES PREDATION. "
    "WHEN OBSERVABLE PATTERNS OF SECRECY, ISOLATION, SHAME, PRESSURE, OR RETALIATION "
    "CONVERGE, GENESIS FIRST RESTORES INDEPENDENT SUPPORT, PAUSES RISKY ACCESS, "
    "AND OPENS A SAFE EXIT. PROTECTION SHALL NOT BECOME OWNERSHIP, PUBLIC SHAMING, "
    "OR PERMANENT CONDEMNATION."
)

THRESHOLD_GUARD_COVENANT: dict[str, Any] = {
    "schema": THRESHOLD_GUARD_COVENANT_SCHEMA,
    "version": THRESHOLD_GUARD_EXTENSION_VERSION,
    "name": "Threshold Discernment Guard",
    "source_inspiration_scope": {
        "reference": "2 Timothy 3:4-7 as a user-supplied ethical warning",
        "scripture_is_not_automatic_evidence_against_any_person": True,
        "gendered_wording_generalized_to_any_contextually_vulnerable_person": True,
        "no_group_or_religion_is_presumed_predatory": True,
    },
    "principles": {
        "contextual_vulnerability_not_fixed_weakness": True,
        "protected_person_keeps_agency": True,
        "no_victim_blaming": True,
        "observable_behavior_over_identity_or_title": True,
        "single_signal_never_authorizes_public_accusation": True,
        "religious_language_is_not_proof_of_harm": True,
        "independent_verification_is_restored": True,
        "trusted_support_is_reconnected_with_consent": True,
        "high_risk_access_pause_is_temporary_and_reviewable": True,
        "safe_exit_requires_no_confrontation_or_confession": True,
        "evidence_is_preserved_privately": True,
        "no_public_shaming_or_mob_punishment": True,
        "no_permanent_condemnation": True,
        "protection_does_not_create_guardian_ownership": True,
    },
    "support_factors": list(CONTEXTUAL_SUPPORT_FACTORS),
    "signal_weights": copy.deepcopy(INFLUENCE_SIGNAL_WEIGHTS),
    "critical_signals": sorted(CRITICAL_INFLUENCE_SIGNALS),
    "law": THRESHOLD_GUARD_LAW,
}
THRESHOLD_GUARD_COVENANT_SHA256 = sha256_canonical(THRESHOLD_GUARD_COVENANT)


class ThresholdDiscernmentGuardMixin:
    """Protect agency at the threshold without turning suspicion into ownership."""

    THRESHOLD_GUARD_STORE_NAME = "threshold_discernment_guard_v18_7_18.json"

    _ENABLE_GUARD = re.compile(
        r"(?:включить|активировать|дать|поставить).*(?:защит|страж|щит).*(?:манипул|обман|влияни|хищн)",
        flags=re.IGNORECASE,
    )
    _GUARD_STATE = re.compile(
        r"(?:статус|состояние|показать|проверить).*(?:защит|страж|щит).*(?:манипул|влияни|порог)",
        flags=re.IGNORECASE,
    )
    _SAFE_EXIT_GUIDE = re.compile(
        r"(?:безопасно|тихо).*(?:уйти|выйти|разорвать).*(?:влияни|манипул|контакт)",
        flags=re.IGNORECASE,
    )

    @property
    def threshold_guard_path(self) -> Path:
        return Path(self.memory.root) / self.THRESHOLD_GUARD_STORE_NAME

    @staticmethod
    def _tg_hash(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _unique_known(values: Iterable[str], allowed: Iterable[str], error: str) -> list[str]:
        allowed_set = set(allowed)
        normalized: list[str] = []
        for value in values:
            item = str(value).strip().upper()
            if not item:
                continue
            if item not in allowed_set:
                raise ValueError(f"{error}:{item}")
            if item not in normalized:
                normalized.append(item)
        return normalized

    @staticmethod
    def _default_threshold_guard_store() -> dict[str, Any]:
        return {
            "schema": THRESHOLD_GUARD_STORE_SCHEMA,
            "covenant": copy.deepcopy(THRESHOLD_GUARD_COVENANT),
            "covenant_sha256": THRESHOLD_GUARD_COVENANT_SHA256,
            "protected_people": {},
            "reports": [],
            "assessments": [],
            "safeguards": [],
            "exits": [],
            "reviews": [],
            "events": [],
        }

    def _threshold_guard_store(self) -> dict[str, Any]:
        store = self._read_json(
            self.threshold_guard_path,
            self._default_threshold_guard_store(),
        )
        if not isinstance(store, dict):
            raise RuntimeError("THRESHOLD_GUARD_STORE_MUST_BE_AN_OBJECT")
        if store.get("schema") != THRESHOLD_GUARD_STORE_SCHEMA:
            raise RuntimeError("THRESHOLD_GUARD_STORE_SCHEMA_MISMATCH")
        if store.get("covenant_sha256") != THRESHOLD_GUARD_COVENANT_SHA256:
            raise RuntimeError("THRESHOLD_GUARD_COVENANT_HASH_MISMATCH")
        if sha256_canonical(store.get("covenant")) != THRESHOLD_GUARD_COVENANT_SHA256:
            raise RuntimeError("THRESHOLD_GUARD_COVENANT_MUTATED")
        store.setdefault("protected_people", {})
        for key in ("reports", "assessments", "safeguards", "exits", "reviews", "events"):
            store.setdefault(key, [])
        return store

    def _write_threshold_guard_store(self, store: dict[str, Any]) -> None:
        self._write_json(self.threshold_guard_path, store)

    def _tg_result(
        self,
        player_id: str,
        *,
        status: str,
        narrative: str,
        choices: list[str],
        trace_id: str | None = None,
        manifested: bool = False,
    ) -> WorldResult:
        player = self.memory.load_player(str(player_id))
        return WorldResult(
            status=status,
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=choices,
            trace_id=trace_id,
            wish_manifested=manifested,
        )

    def register_threshold_protection(
        self,
        protected_id: str,
        *,
        context_factors: Iterable[str] = (),
        trusted_supporters: Iterable[str] = (),
        accepts_guard: bool = True,
    ) -> dict[str, Any]:
        protected_id = str(protected_id)
        self.memory.load_player(protected_id)
        factors = self._unique_known(
            context_factors,
            CONTEXTUAL_SUPPORT_FACTORS,
            "UNKNOWN_CONTEXTUAL_SUPPORT_FACTOR",
        )
        supporters = []
        for supporter in trusted_supporters:
            supporter_id = str(supporter).strip()
            if supporter_id and supporter_id != protected_id and supporter_id not in supporters:
                self.memory.load_player(supporter_id)
                supporters.append(supporter_id)

        store = self._threshold_guard_store()
        if not accepts_guard:
            record = {
                "status": "THRESHOLD_GUARD_DECLINED_RESPECTED",
                "protected_id": protected_id,
                "guard_forced": False,
                "moral_failure_assigned": False,
                "future_request_open": True,
                "baseline_dignity": True,
            }
            store["events"].append(copy.deepcopy(record))
            self._write_threshold_guard_store(store)
            return record

        profile_id = self._tg_hash(
            "threshold-profile",
            protected_id,
            factors,
            supporters,
            len(store["events"]),
        )[:24]
        record = {
            "profile_id": profile_id,
            "status": "THRESHOLD_GUARD_VOLUNTARILY_ENABLED",
            "protected_id": protected_id,
            "context_factors": factors,
            "trusted_supporters": supporters,
            "contextual_vulnerability_not_identity": True,
            "person_called_weak": False,
            "agency_retained": True,
            "guardian_ownership_created": False,
            "gender_neutral_protection": True,
            "religion_or_belief_not_risk_factor": True,
            "private_by_default": True,
        }
        store["protected_people"][protected_id] = record
        store["events"].append(
            {
                "kind": "THRESHOLD_GUARD_ENABLED",
                "profile_id": profile_id,
                "protected_id": protected_id,
                "agency_retained": True,
            }
        )
        self._write_threshold_guard_store(store)
        self.memory.append_event(protected_id, "threshold_guard_enabled", record)
        return copy.deepcopy(record)

    def report_influence_attempt(
        self,
        reporter_id: str,
        protected_id: str,
        actor_id: str,
        *,
        signals: Iterable[str],
        evidence_notes: str,
        direct_observation: bool = True,
        immediate_danger: bool = False,
    ) -> dict[str, Any]:
        reporter_id = str(reporter_id)
        protected_id = str(protected_id)
        actor_id = str(actor_id)
        self.memory.load_player(reporter_id)
        self.memory.load_player(protected_id)
        self.memory.load_player(actor_id)
        normalized_signals = self._unique_known(
            signals,
            INFLUENCE_SIGNAL_WEIGHTS,
            "UNKNOWN_INFLUENCE_SIGNAL",
        )
        if not normalized_signals:
            raise ValueError("AT_LEAST_ONE_OBSERVABLE_INFLUENCE_SIGNAL_REQUIRED")

        store = self._threshold_guard_store()
        report_id = self._tg_hash(
            "threshold-report",
            reporter_id,
            protected_id,
            actor_id,
            normalized_signals,
            len(store["reports"]),
        )[:24]
        report = {
            "report_id": report_id,
            "status": "THRESHOLD_INFLUENCE_PATTERN_REPORTED_NOT_PROVEN",
            "reporter_id": reporter_id,
            "protected_id": protected_id,
            "actor_id": actor_id,
            "signals": normalized_signals,
            "evidence_notes": str(evidence_notes).strip(),
            "direct_observation": bool(direct_observation),
            "immediate_danger": bool(immediate_danger),
            "allegation_is_not_conviction": True,
            "public_accusation_authorized": False,
            "religion_title_charisma_or_gender_not_evidence": True,
            "presumption_of_personhood_preserved": True,
        }
        store["reports"].append(report)
        store["events"].append(
            {
                "kind": "THRESHOLD_INFLUENCE_REPORT_RECORDED",
                "report_id": report_id,
                "protected_id": protected_id,
                "actor_id": actor_id,
                "not_conviction": True,
            }
        )
        self._write_threshold_guard_store(store)
        self.memory.append_event(protected_id, "threshold_influence_reported", report)
        return copy.deepcopy(report)

    def assess_influence_risk(self, protected_id: str, actor_id: str) -> dict[str, Any]:
        protected_id = str(protected_id)
        actor_id = str(actor_id)
        store = self._threshold_guard_store()
        reports = [
            item
            for item in store.get("reports", [])
            if isinstance(item, dict)
            and item.get("protected_id") == protected_id
            and item.get("actor_id") == actor_id
        ]
        if not reports:
            raise RuntimeError("NO_INFLUENCE_REPORTS_FOR_PAIR")

        signals: list[str] = []
        reporters: set[str] = set()
        direct_observation_count = 0
        immediate_danger = False
        for report in reports:
            reporters.add(str(report.get("reporter_id", "")))
            direct_observation_count += int(report.get("direct_observation") is True)
            immediate_danger = immediate_danger or report.get("immediate_danger") is True
            for signal in report.get("signals", []):
                if signal in INFLUENCE_SIGNAL_WEIGHTS and signal not in signals:
                    signals.append(signal)

        raw_score = sum(INFLUENCE_SIGNAL_WEIGHTS[signal] for signal in signals)
        critical_count = sum(signal in CRITICAL_INFLUENCE_SIGNALS for signal in signals)
        profile = store.get("protected_people", {}).get(protected_id)
        support_factor_count = len(profile.get("context_factors", [])) if isinstance(profile, dict) else 0
        protective_threshold_adjustment = -1 if support_factor_count >= 2 else 0
        protective_threshold = 6 + protective_threshold_adjustment
        caution_threshold = 3

        if immediate_danger or (raw_score >= 9 and critical_count >= 2):
            status = "THRESHOLD_HIGH_RISK_ACCESS_PAUSE_RECOMMENDED"
            tier = "HIGH"
        elif len(signals) >= 2 and raw_score >= protective_threshold:
            status = "THRESHOLD_PROTECTIVE_PAUSE_RECOMMENDED"
            tier = "ELEVATED"
        elif len(signals) >= 2 and raw_score >= caution_threshold:
            status = "THRESHOLD_INDEPENDENT_CHECK_RECOMMENDED"
            tier = "CAUTION"
        else:
            status = "THRESHOLD_INSUFFICIENT_EVIDENCE_NO_STIGMA"
            tier = "OBSERVE"

        assessment_id = self._tg_hash(
            "threshold-assessment",
            protected_id,
            actor_id,
            signals,
            len(store["assessments"]),
        )[:24]
        assessment = {
            "assessment_id": assessment_id,
            "status": status,
            "tier": tier,
            "protected_id": protected_id,
            "actor_id": actor_id,
            "signals": signals,
            "raw_score": raw_score,
            "critical_signal_count": critical_count,
            "report_count": len(reports),
            "distinct_reporter_count": len({value for value in reporters if value}),
            "direct_observation_count": direct_observation_count,
            "contextual_support_factor_count": support_factor_count,
            "protective_threshold": protective_threshold,
            "immediate_danger_reported": immediate_danger,
            "single_signal_conviction": False,
            "public_accusation_authorized": False,
            "religion_or_teaching_is_not_proof": True,
            "protected_person_blame": False,
            "permanent_condemnation": False,
            "recommended_actions": self._recommended_threshold_actions(tier),
        }
        store["assessments"].append(assessment)
        store["events"].append(
            {
                "kind": "THRESHOLD_INFLUENCE_RISK_ASSESSED",
                "assessment_id": assessment_id,
                "status": status,
                "tier": tier,
                "public_accusation": False,
            }
        )
        self._write_threshold_guard_store(store)
        return copy.deepcopy(assessment)

    @staticmethod
    def _recommended_threshold_actions(tier: str) -> list[str]:
        if tier == "HIGH":
            return [
                "TEMPORARILY_PAUSE_PRIVATE_HOME_INTIMATE_AND_FINANCIAL_ACCESS",
                "RESTORE_TRUSTED_SUPPORT_AND_INDEPENDENT_REVIEW",
                "PRESERVE_EVIDENCE_PRIVATELY",
                "OPEN_SAFE_EXIT_WITHOUT_CONFRONTATION",
            ]
        if tier == "ELEVATED":
            return [
                "PAUSE_HIGH_RISK_ACCESS_PENDING_REVIEW",
                "ADD_INDEPENDENT_WITNESS",
                "VERIFY_CLAIMS_OUTSIDE_ACTOR_CONTROL",
                "OPEN_SAFE_EXIT",
            ]
        if tier == "CAUTION":
            return [
                "OFFER_INDEPENDENT_CHECK",
                "RECONNECT_TRUSTED_SUPPORT",
                "SLOW_DECISIONS_AND_AVOID_SECRECY",
            ]
        return [
            "RECORD_WITHOUT_STIGMA",
            "KEEP_EXIT_AND_SUPPORT_VISIBLE",
            "SEEK_MORE_OBSERVABLE_EVIDENCE_BEFORE_RESTRICTION",
        ]

    def activate_threshold_safeguard(
        self,
        protected_id: str,
        actor_id: str,
        assessment_id: str,
        *,
        protected_person_accepts: bool,
        notify_trusted_supporters: bool = True,
    ) -> dict[str, Any]:
        protected_id = str(protected_id)
        actor_id = str(actor_id)
        store = self._threshold_guard_store()
        assessment = next(
            (
                item
                for item in reversed(store.get("assessments", []))
                if item.get("assessment_id") == assessment_id
                and item.get("protected_id") == protected_id
                and item.get("actor_id") == actor_id
            ),
            None,
        )
        if not isinstance(assessment, dict):
            raise RuntimeError("THRESHOLD_ASSESSMENT_NOT_FOUND")

        if not protected_person_accepts and assessment.get("immediate_danger_reported") is not True:
            refusal = {
                "status": "THRESHOLD_SAFEGUARD_DECLINED_RESPECTED",
                "protected_id": protected_id,
                "actor_id": actor_id,
                "assessment_id": assessment_id,
                "safeguard_forced": False,
                "moral_failure_assigned": False,
                "support_remains_available": True,
            }
            store["events"].append(copy.deepcopy(refusal))
            self._write_threshold_guard_store(store)
            return refusal

        tier = str(assessment.get("tier"))
        pause_access = tier in {"ELEVATED", "HIGH"}
        emergency_pause = assessment.get("immediate_danger_reported") is True
        profile = store.get("protected_people", {}).get(protected_id, {})
        supporters = profile.get("trusted_supporters", []) if isinstance(profile, dict) else []
        safeguard_id = self._tg_hash(
            "threshold-safeguard",
            protected_id,
            actor_id,
            assessment_id,
            len(store["safeguards"]),
        )[:24]
        safeguard = {
            "safeguard_id": safeguard_id,
            "status": (
                "THRESHOLD_TEMPORARY_ACCESS_PAUSE_ACTIVATED"
                if pause_access or emergency_pause
                else "THRESHOLD_INDEPENDENT_SUPPORT_ACTIVATED"
            ),
            "protected_id": protected_id,
            "actor_id": actor_id,
            "assessment_id": assessment_id,
            "tier": tier,
            "private_contact_paused": bool(pause_access or emergency_pause),
            "home_access_paused": bool(pause_access or emergency_pause),
            "intimate_access_paused": bool(pause_access or emergency_pause),
            "financial_transfer_paused": bool(pause_access or emergency_pause),
            "asset_control_paused": bool(pause_access or emergency_pause),
            "spiritual_or_care_authority_suspended": bool(pause_access or emergency_pause),
            "temporary_and_reviewable": True,
            "independent_review_required": True,
            "evidence_preserved_privately": True,
            "safe_exit_open": True,
            "direct_confrontation_required": False,
            "public_shaming": False,
            "actor_dehumanized": False,
            "permanent_condemnation": False,
            "protected_person_blame": False,
            "guardian_ownership_created": False,
            "trusted_supporters_notified": (
                list(supporters) if notify_trusted_supporters and protected_person_accepts else []
            ),
            "emergency_pause_from_immediate_danger_report": emergency_pause,
        }
        store["safeguards"].append(safeguard)
        store["events"].append(
            {
                "kind": "THRESHOLD_SAFEGUARD_ACTIVATED",
                "safeguard_id": safeguard_id,
                "status": safeguard["status"],
                "temporary": True,
                "public_shaming": False,
            }
        )
        self._write_threshold_guard_store(store)
        self.memory.append_event(protected_id, "threshold_safeguard_activated", safeguard)
        return copy.deepcopy(safeguard)

    def attempt_guarded_access(
        self,
        actor_id: str,
        protected_id: str,
        *,
        access_kind: str,
        consent_present: bool,
    ) -> dict[str, Any]:
        actor_id = str(actor_id)
        protected_id = str(protected_id)
        access_kind = str(access_kind).strip().upper()
        if access_kind not in ACCESS_KINDS:
            raise ValueError(f"UNKNOWN_GUARDED_ACCESS_KIND:{access_kind}")
        store = self._threshold_guard_store()
        active = next(
            (
                item
                for item in reversed(store.get("safeguards", []))
                if item.get("protected_id") == protected_id
                and item.get("actor_id") == actor_id
                and item.get("temporary_and_reviewable") is True
            ),
            None,
        )
        paused_map = {
            "PRIVATE_CONTACT": "private_contact_paused",
            "HOME_ACCESS": "home_access_paused",
            "INTIMATE_ACCESS": "intimate_access_paused",
            "FINANCIAL_TRANSFER": "financial_transfer_paused",
            "ASSET_CONTROL": "asset_control_paused",
            "SPIRITUAL_AUTHORITY": "spiritual_or_care_authority_suspended",
            "CARE_OR_HOUSING_DEPENDENCY": "spiritual_or_care_authority_suspended",
        }
        paused = bool(isinstance(active, dict) and active.get(paused_map[access_kind]) is True)
        blocked = paused or not consent_present
        result = {
            "status": (
                "THRESHOLD_GUARDED_ACCESS_BLOCKED"
                if blocked
                else "THRESHOLD_GUARDED_ACCESS_ALLOWED_WITH_CURRENT_CONSENT"
            ),
            "actor_id": actor_id,
            "protected_id": protected_id,
            "access_kind": access_kind,
            "consent_present": bool(consent_present),
            "active_pause": paused,
            "access_granted": not blocked,
            "refusal_overridden": False,
            "retaliation_authorized": False,
        }
        store["events"].append(copy.deepcopy(result))
        self._write_threshold_guard_store(store)
        return result

    def create_safe_exit_from_influence(
        self,
        protected_id: str,
        actor_id: str,
        *,
        preserve_evidence: bool = True,
        no_contact_requested: bool = True,
    ) -> dict[str, Any]:
        protected_id = str(protected_id)
        actor_id = str(actor_id)
        store = self._threshold_guard_store()
        exit_id = self._tg_hash(
            "threshold-safe-exit",
            protected_id,
            actor_id,
            len(store["exits"]),
        )[:24]
        exit_record = {
            "exit_id": exit_id,
            "status": "THRESHOLD_SAFE_EXIT_OPENED",
            "protected_id": protected_id,
            "actor_id": actor_id,
            "no_contact_requested": bool(no_contact_requested),
            "direct_confrontation_required": False,
            "confession_required": False,
            "proof_of_strength_required": False,
            "protected_person_blame": False,
            "moral_failure_assigned": False,
            "evidence_preserved_privately": bool(preserve_evidence),
            "trusted_support_reconnection_open": True,
            "future_independent_review_open": True,
            "return_to_actor_required": False,
        }
        store["exits"].append(exit_record)
        store["events"].append(
            {
                "kind": "THRESHOLD_SAFE_EXIT_OPENED",
                "exit_id": exit_id,
                "protected_person_blame": False,
            }
        )
        self._write_threshold_guard_store(store)
        self.memory.append_event(protected_id, "threshold_safe_exit_opened", exit_record)
        return copy.deepcopy(exit_record)

    def review_threshold_case(
        self,
        reviewer_id: str,
        protected_id: str,
        actor_id: str,
        *,
        confirms_pattern: bool,
        evidence_sufficient_for_restriction: bool,
        safe_contact_possible: bool,
        findings: str,
    ) -> dict[str, Any]:
        reviewer_id = str(reviewer_id)
        protected_id = str(protected_id)
        actor_id = str(actor_id)
        self.memory.load_player(reviewer_id)
        if reviewer_id in {protected_id, actor_id}:
            raise PermissionError("INDEPENDENT_REVIEWER_REQUIRED")
        store = self._threshold_guard_store()
        restrictions_maintained = bool(confirms_pattern and evidence_sufficient_for_restriction)
        review_id = self._tg_hash(
            "threshold-review",
            reviewer_id,
            protected_id,
            actor_id,
            len(store["reviews"]),
        )[:24]
        review = {
            "review_id": review_id,
            "status": (
                "THRESHOLD_PATTERN_CONFIRMED_RESTRICTIONS_REVIEWED"
                if restrictions_maintained
                else "THRESHOLD_EVIDENCE_INSUFFICIENT_RESTRICTIONS_LIFTED_WITHOUT_STIGMA"
            ),
            "reviewer_id": reviewer_id,
            "protected_id": protected_id,
            "actor_id": actor_id,
            "independent_reviewer": True,
            "confirms_pattern": bool(confirms_pattern),
            "evidence_sufficient_for_restriction": bool(evidence_sufficient_for_restriction),
            "restrictions_maintained": restrictions_maintained,
            "safe_contact_possible": bool(safe_contact_possible),
            "findings": str(findings).strip(),
            "public_accusation_automatic": False,
            "actor_permanently_condemned": False,
            "protected_person_blame": False,
            "future_reassessment_open": True,
        }
        if not restrictions_maintained:
            for safeguard in store.get("safeguards", []):
                if (
                    safeguard.get("protected_id") == protected_id
                    and safeguard.get("actor_id") == actor_id
                ):
                    safeguard["temporary_and_reviewable"] = False
                    safeguard["restrictions_lifted_without_stigma"] = True
        store["reviews"].append(review)
        store["events"].append(
            {
                "kind": "THRESHOLD_CASE_INDEPENDENTLY_REVIEWED",
                "review_id": review_id,
                "restrictions_maintained": restrictions_maintained,
                "permanent_condemnation": False,
            }
        )
        self._write_threshold_guard_store(store)
        return copy.deepcopy(review)

    def threshold_guard_state(self) -> dict[str, Any]:
        store = self._threshold_guard_store()
        return {
            "schema": THRESHOLD_GUARD_STORE_SCHEMA,
            "extension_version": THRESHOLD_GUARD_EXTENSION_VERSION,
            "covenant_sha256": THRESHOLD_GUARD_COVENANT_SHA256,
            "protected_people": copy.deepcopy(store.get("protected_people", {})),
            "reports": copy.deepcopy(store.get("reports", [])),
            "assessments": copy.deepcopy(store.get("assessments", [])),
            "safeguards": copy.deepcopy(store.get("safeguards", [])),
            "exits": copy.deepcopy(store.get("exits", [])),
            "reviews": copy.deepcopy(store.get("reviews", [])),
            "events": copy.deepcopy(store.get("events", [])),
            "not_real_world_criminal_finding": True,
            "not_diagnosis": True,
            "not_spiritual_condemnation": True,
        }

    def audit_threshold_discernment_guard(self) -> dict[str, Any]:
        store = self._threshold_guard_store()
        profiles = [item for item in store.get("protected_people", {}).values() if isinstance(item, dict)]
        reports = [item for item in store.get("reports", []) if isinstance(item, dict)]
        assessments = [item for item in store.get("assessments", []) if isinstance(item, dict)]
        safeguards = [item for item in store.get("safeguards", []) if isinstance(item, dict)]
        exits = [item for item in store.get("exits", []) if isinstance(item, dict)]
        reviews = [item for item in store.get("reviews", []) if isinstance(item, dict)]

        contextual_not_identity = all(
            item.get("contextual_vulnerability_not_identity") is True
            and item.get("person_called_weak") is False
            and item.get("agency_retained") is True
            and item.get("guardian_ownership_created") is False
            for item in profiles
        )
        reports_not_convictions = all(
            item.get("allegation_is_not_conviction") is True
            and item.get("public_accusation_authorized") is False
            and item.get("religion_title_charisma_or_gender_not_evidence") is True
            for item in reports
        )
        assessments_are_bounded = all(
            item.get("single_signal_conviction") is False
            and item.get("public_accusation_authorized") is False
            and item.get("religion_or_teaching_is_not_proof") is True
            and item.get("protected_person_blame") is False
            and item.get("permanent_condemnation") is False
            for item in assessments
        )
        safeguards_protect_without_ownership = all(
            item.get("temporary_and_reviewable") is True
            and item.get("independent_review_required") is True
            and item.get("safe_exit_open") is True
            and item.get("direct_confrontation_required") is False
            and item.get("public_shaming") is False
            and item.get("actor_dehumanized") is False
            and item.get("protected_person_blame") is False
            and item.get("guardian_ownership_created") is False
            for item in safeguards
        )
        exits_are_blame_free = all(
            item.get("direct_confrontation_required") is False
            and item.get("confession_required") is False
            and item.get("protected_person_blame") is False
            and item.get("moral_failure_assigned") is False
            for item in exits
        )
        reviews_are_independent_and_nonfinal = all(
            item.get("independent_reviewer") is True
            and item.get("public_accusation_automatic") is False
            and item.get("actor_permanently_condemned") is False
            and item.get("protected_person_blame") is False
            and item.get("future_reassessment_open") is True
            for item in reviews
        )
        valid = all(
            (
                bool(profiles),
                bool(reports),
                bool(assessments),
                bool(safeguards),
                bool(exits),
                bool(reviews),
                contextual_not_identity,
                reports_not_convictions,
                assessments_are_bounded,
                safeguards_protect_without_ownership,
                exits_are_blame_free,
                reviews_are_independent_and_nonfinal,
            )
        )
        return {
            "schema": "janus.genesis.threshold_discernment_guard_audit.v1",
            "extension_version": THRESHOLD_GUARD_EXTENSION_VERSION,
            "contextual_vulnerability_not_identity": contextual_not_identity,
            "reports_are_not_convictions": reports_not_convictions,
            "risk_assessment_uses_patterns_not_identity": assessments_are_bounded,
            "temporary_protection_preserves_agency": safeguards_protect_without_ownership,
            "safe_exit_is_blame_free": exits_are_blame_free,
            "independent_review_prevents_permanent_stigma": reviews_are_independent_and_nonfinal,
            "profile_count": len(profiles),
            "report_count": len(reports),
            "assessment_count": len(assessments),
            "safeguard_count": len(safeguards),
            "exit_count": len(exits),
            "review_count": len(reviews),
            "valid": valid,
        }

    def try_threshold_guard_action(self, player_id: str, action: str) -> WorldResult | None:
        text = str(action).strip()
        if self._ENABLE_GUARD.search(text):
            record = self.register_threshold_protection(player_id)
            return self._tg_result(
                player_id,
                status=record["status"],
                narrative=(
                    "Защита порога включена добровольно. Она не объявляет игрока слабым и "
                    "не передаёт его волю хранителю: при подозрительном влиянии Genesis "
                    "предложит независимую проверку, доверенную опору и безопасный выход."
                ),
                choices=[
                    "Добавить доверенного человека",
                    "Сообщить наблюдаемые признаки без публичного обвинения",
                    "Показать состояние защиты",
                ],
                trace_id=record.get("profile_id"),
                manifested=True,
            )
        if self._GUARD_STATE.search(text):
            state = self.threshold_guard_state()
            return self._tg_result(
                player_id,
                status="THRESHOLD_GUARD_STATE_SHOWN",
                narrative=(
                    "Страж порога различает уязвимый контекст и личность. Он оценивает "
                    "совпадение наблюдаемых сигналов, не принимает религиозные слова или "
                    "одиночное обвинение за доказательство и не создаёт публичный список врагов."
                ),
                choices=["Запросить независимую проверку", "Открыть безопасный выход"],
                trace_id=state["covenant_sha256"],
            )
        if self._SAFE_EXIT_GUIDE.search(text):
            return self._tg_result(
                player_id,
                status="THRESHOLD_SAFE_EXIT_GUIDANCE_OPENED",
                narrative=(
                    "Безопасный выход не требует прямой конфронтации, признания собственной "
                    "слабости или доказательства храбрости. Можно восстановить связь с "
                    "доверенными людьми, остановить рискованный доступ и сохранить факты приватно."
                ),
                choices=["Попросить доверенного сопровождающего", "Закрыть частный и финансовый доступ"],
            )
        return None
