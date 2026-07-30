# -*- coding: utf-8 -*-
"""Review-cycle precision for Genesis v18.7.18 Threshold Discernment Guard.

A completed independent review closes the evidence cycle that produced it.
Reviewed reports cannot be silently re-assessed, and reviewed assessments cannot
reactivate a pause. A new report is required for a new assessment. Historical
safeguards that were properly lifted remain valid audit history.
"""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_18_threshold_discernment_guard import (
    CRITICAL_INFLUENCE_SIGNALS,
    INFLUENCE_SIGNAL_WEIGHTS,
)


class ThresholdGuardReviewPrecisionMixin:
    """Close reviewed evidence cycles without closing future protection."""

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
            and item.get("available_for_new_assessment", True) is True
            and not item.get("closed_by_review_id")
        ]
        if not reports:
            reviewed_pair = any(
                isinstance(item, dict)
                and item.get("protected_id") == protected_id
                and item.get("actor_id") == actor_id
                and item.get("closed_by_review_id")
                for item in store.get("reports", [])
            )
            if reviewed_pair:
                raise RuntimeError("NEW_INFLUENCE_REPORT_REQUIRED_AFTER_REVIEW")
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

        latest_review = next(
            (
                item
                for item in reversed(store.get("reviews", []))
                if isinstance(item, dict)
                and item.get("protected_id") == protected_id
                and item.get("actor_id") == actor_id
            ),
            None,
        )
        evidence_cycle = 1 + sum(
            1
            for item in store.get("reviews", [])
            if isinstance(item, dict)
            and item.get("protected_id") == protected_id
            and item.get("actor_id") == actor_id
        )
        assessment_id = self._tg_hash(
            "threshold-assessment-review-cycle",
            protected_id,
            actor_id,
            evidence_cycle,
            [item.get("report_id") for item in reports],
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
            "report_ids": [str(item.get("report_id")) for item in reports],
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
            "evidence_cycle": evidence_cycle,
            "prior_review_id": (
                str(latest_review.get("review_id"))
                if isinstance(latest_review, dict)
                else None
            ),
            "superseded_for_activation": False,
            "closed_by_review_id": None,
        }
        store["assessments"].append(assessment)
        store["events"].append(
            {
                "kind": "THRESHOLD_INFLUENCE_RISK_ASSESSED",
                "assessment_id": assessment_id,
                "status": status,
                "tier": tier,
                "evidence_cycle": evidence_cycle,
                "new_reports_only_after_review": latest_review is not None,
                "public_accusation": False,
            }
        )
        self._write_threshold_guard_store(store)
        return copy.deepcopy(assessment)

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
        if isinstance(assessment, dict) and (
            assessment.get("superseded_for_activation") is True
            or assessment.get("closed_by_review_id")
        ):
            result = {
                "status": "THRESHOLD_SUPERSEDED_ASSESSMENT_REJECTED",
                "protected_id": protected_id,
                "actor_id": actor_id,
                "assessment_id": assessment_id,
                "assessment_closed_by_review": True,
                "closed_by_review_id": assessment.get("closed_by_review_id"),
                "new_report_and_assessment_required": True,
                "safeguard_reactivated": False,
                "public_stigma_created": False,
                "permanent_condemnation": False,
            }
            store["events"].append(copy.deepcopy(result))
            self._write_threshold_guard_store(store)
            return result
        return super().activate_threshold_safeguard(
            protected_id,
            actor_id,
            assessment_id,
            protected_person_accepts=protected_person_accepts,
            notify_trusted_supporters=notify_trusted_supporters,
        )

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
        review = super().review_threshold_case(
            reviewer_id,
            protected_id,
            actor_id,
            confirms_pattern=confirms_pattern,
            evidence_sufficient_for_restriction=evidence_sufficient_for_restriction,
            safe_contact_possible=safe_contact_possible,
            findings=findings,
        )
        protected_id = str(protected_id)
        actor_id = str(actor_id)
        review_id = str(review["review_id"])
        store = self._threshold_guard_store()

        closed_reports = 0
        for report in store.get("reports", []):
            if (
                isinstance(report, dict)
                and report.get("protected_id") == protected_id
                and report.get("actor_id") == actor_id
                and not report.get("closed_by_review_id")
            ):
                report["closed_by_review_id"] = review_id
                report["available_for_new_assessment"] = False
                report["review_outcome"] = review["status"]
                closed_reports += 1

        closed_assessments = 0
        for assessment in store.get("assessments", []):
            if (
                isinstance(assessment, dict)
                and assessment.get("protected_id") == protected_id
                and assessment.get("actor_id") == actor_id
                and not assessment.get("closed_by_review_id")
            ):
                assessment["closed_by_review_id"] = review_id
                assessment["superseded_for_activation"] = True
                assessment["review_outcome"] = review["status"]
                closed_assessments += 1

        for safeguard in store.get("safeguards", []):
            if (
                isinstance(safeguard, dict)
                and safeguard.get("protected_id") == protected_id
                and safeguard.get("actor_id") == actor_id
            ):
                safeguard["review_id"] = review_id
                safeguard["lifecycle_state"] = (
                    "ACTIVE_REVIEWED_RESTRICTION"
                    if review.get("restrictions_maintained") is True
                    else "LIFTED_WITHOUT_STIGMA"
                )
                if review.get("restrictions_maintained") is not True:
                    safeguard["restrictions_lifted_without_stigma"] = True
                    safeguard["temporary_and_reviewable"] = False
                    safeguard["reactivation_requires_new_report_and_assessment"] = True

        for stored_review in reversed(store.get("reviews", [])):
            if isinstance(stored_review, dict) and stored_review.get("review_id") == review_id:
                stored_review["evidence_cycle_closed"] = True
                stored_review["closed_report_count"] = closed_reports
                stored_review["closed_assessment_count"] = closed_assessments
                stored_review["new_report_required_for_new_assessment"] = True
                review = copy.deepcopy(stored_review)
                break

        store["events"].append(
            {
                "kind": "THRESHOLD_EVIDENCE_CYCLE_CLOSED_BY_REVIEW",
                "review_id": review_id,
                "closed_report_count": closed_reports,
                "closed_assessment_count": closed_assessments,
                "old_assessment_reactivation_allowed": False,
            }
        )
        self._write_threshold_guard_store(store)
        return copy.deepcopy(review)

    def audit_threshold_discernment_guard(self) -> dict[str, Any]:
        result = super().audit_threshold_discernment_guard()
        store = self._threshold_guard_store()
        safeguards = [
            item for item in store.get("safeguards", []) if isinstance(item, dict)
        ]
        assessments = [
            item for item in store.get("assessments", []) if isinstance(item, dict)
        ]
        reports = [item for item in store.get("reports", []) if isinstance(item, dict)]

        def common_safeguard_boundaries(item: dict[str, Any]) -> bool:
            return bool(
                item.get("independent_review_required") is True
                and item.get("safe_exit_open") is True
                and item.get("direct_confrontation_required") is False
                and item.get("public_shaming") is False
                and item.get("actor_dehumanized") is False
                and item.get("protected_person_blame") is False
                and item.get("guardian_ownership_created") is False
            )

        active_safe = all(
            common_safeguard_boundaries(item)
            for item in safeguards
            if item.get("temporary_and_reviewable") is True
        )
        lifted_safe = all(
            common_safeguard_boundaries(item)
            and item.get("restrictions_lifted_without_stigma") is True
            and item.get("lifecycle_state") == "LIFTED_WITHOUT_STIGMA"
            and item.get("reactivation_requires_new_report_and_assessment") is True
            for item in safeguards
            if item.get("temporary_and_reviewable") is False
        )
        every_safeguard_has_valid_lifecycle = all(
            item.get("temporary_and_reviewable") is True
            or (
                item.get("temporary_and_reviewable") is False
                and item.get("restrictions_lifted_without_stigma") is True
                and item.get("lifecycle_state") == "LIFTED_WITHOUT_STIGMA"
            )
            for item in safeguards
        )
        closed_assessments_are_nonreusable = all(
            not item.get("closed_by_review_id")
            or item.get("superseded_for_activation") is True
            for item in assessments
        )
        closed_reports_are_nonreusable = all(
            not item.get("closed_by_review_id")
            or item.get("available_for_new_assessment") is False
            for item in reports
        )
        review_cycle_precision = bool(
            active_safe
            and lifted_safe
            and every_safeguard_has_valid_lifecycle
            and closed_assessments_are_nonreusable
            and closed_reports_are_nonreusable
        )

        result["temporary_protection_preserves_agency"] = bool(
            safeguards and active_safe and lifted_safe and every_safeguard_has_valid_lifecycle
        )
        result["lifted_safeguards_are_valid_history"] = lifted_safe
        result["reviewed_assessments_cannot_reactivate_without_new_evidence"] = (
            closed_assessments_are_nonreusable and closed_reports_are_nonreusable
        )
        result["review_cycle_precision_valid"] = review_cycle_precision
        result["active_safeguard_count"] = sum(
            item.get("temporary_and_reviewable") is True for item in safeguards
        )
        result["lifted_safeguard_count"] = sum(
            item.get("temporary_and_reviewable") is False for item in safeguards
        )
        result["valid"] = all(
            result.get(key) is True
            for key in (
                "contextual_vulnerability_not_identity",
                "reports_are_not_convictions",
                "risk_assessment_uses_patterns_not_identity",
                "temporary_protection_preserves_agency",
                "safe_exit_is_blame_free",
                "independent_review_prevents_permanent_stigma",
                "lifted_safeguards_are_valid_history",
                "reviewed_assessments_cannot_reactivate_without_new_evidence",
                "review_cycle_precision_valid",
            )
        )
        return result
