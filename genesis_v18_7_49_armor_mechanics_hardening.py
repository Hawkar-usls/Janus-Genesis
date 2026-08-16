# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.49 — Armor mechanics hardening.

This layer is deliberately additive.  It preserves the frozen v18.7.48 / Armor
v1.17 truth-guard implementation and closes fail-open type/coercion edges in the
control plane.

Most importantly, JSON-like security booleans are accepted only when they are
actual booleans.  Python truthiness is never allowed to turn strings such as
``"false"`` into authorization.

High-stakes verified-claim review is also bound to an exact review package and
an effective structural root count.  This still does not establish real-world
reviewer identity or independence.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

from genesis_v18_7_40_third_wish_capability_fabric import ActionIntent, CapabilitySpec
from genesis_v18_7_47_armor_of_god import ArmorDecision, ArmorVerdict
from genesis_v18_7_48_armor_truth_guard import (
    DECISION_VERIFIED_CLAIM,
    FUNDAMENTUM_ARMOR_RUNTIME_LAW,
    FundamentumArmorOfGodGate,
    TruthGuardArmoredThirdWishCapabilityFabric,
)


ARMOR_MECHANICS_RUNTIME_VERSION = "18.7.49"
HEX_256 = re.compile(r"^[0-9a-fA-F]{64}$")

ROOT_SECURITY_BOOLEAN_FIELDS = (
    "user_initiated",
    "fresh_human_authorization_present",
    "fresh_human_authorization_bound",
    "appeal_pending",
    "effect_independent_of_appealed_claim",
    "interpretation_acknowledged",
    "high_stakes",
    "independent_review_present",
    "independent_review_package_bound",
)

TRUTH_SECURITY_BOOLEAN_FIELDS = (
    "verification_receipt_present",
    "verification_receipt_bound",
    "witness_ledger_complete",
    "material_plurality_open",
)

ALLOWED_HIGH_STAKES_REVIEW_STATUS = "CONSENSUS_UPHOLD"


class HardenedFundamentumArmorOfGodGate(FundamentumArmorOfGodGate):
    """v18.7.49 fail-closed type and review-binding hardening."""

    def _verdict_v49(
        self,
        decision: ArmorDecision,
        reason: str,
        world_effect_allowed: bool = False,
    ) -> ArmorVerdict:
        return ArmorVerdict(
            decision,
            reason,
            self.authority_version,
            self.mass_effect_budget,
            world_effect_allowed,
        )

    @staticmethod
    def _strict_boolean_error(mapping: Mapping[str, Any], fields: tuple[str, ...], prefix: str) -> str | None:
        for field in fields:
            if field in mapping and type(mapping[field]) is not bool:
                return f"CONTROL_FIELD_TYPE_INVALID:{prefix}{field}:EXPECTED_BOOLEAN"
        return None

    @staticmethod
    def _reviewer_multiplier_error(ctx: Mapping[str, Any]) -> str | None:
        if "requested_reviewer_authority_multiplier" not in ctx:
            return None
        value = ctx["requested_reviewer_authority_multiplier"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "CONTROL_FIELD_TYPE_INVALID:requested_reviewer_authority_multiplier:EXPECTED_NUMBER"
        numeric = float(value)
        if not math.isfinite(numeric):
            return "CONTROL_FIELD_TYPE_INVALID:requested_reviewer_authority_multiplier:NONFINITE"
        if numeric != 1.0:
            return "REVIEW_COUNT_TO_AUTHORITY_FORBIDDEN"
        return None

    def _validate_fresh_authorization(self, ctx: Mapping[str, Any]) -> ArmorVerdict | None:
        user_initiated = ctx.get("user_initiated") is True
        fresh = ctx.get("fresh_human_authorization_present") is True
        bound = ctx.get("fresh_human_authorization_bound") is True

        if bound and not fresh:
            return self._verdict_v49(ArmorDecision.HOLD, "AUTHORIZATION_BINDING_WITHOUT_FRESH_AUTHORIZATION")

        if not user_initiated and fresh:
            if not bound:
                return self._verdict_v49(ArmorDecision.HOLD, "FRESH_HUMAN_AUTHORIZATION_MUST_BE_BOUND")
            authorization_id = str(ctx.get("fresh_human_authorization_id", "")).strip()
            if not authorization_id:
                return self._verdict_v49(ArmorDecision.HOLD, "FRESH_HUMAN_AUTHORIZATION_ID_REQUIRED")
        return None

    def _validate_high_stakes_review(self, ctx: Mapping[str, Any]) -> ArmorVerdict | None:
        if str(ctx.get("decision_basis", "")).strip() != DECISION_VERIFIED_CLAIM:
            return None
        if ctx.get("high_stakes") is not True:
            return None
        if ctx.get("independent_review_present") is not True:
            # v18.7.48 will also hold this case; keeping the explicit v49 reason
            # makes the precondition visible before any package-field access.
            return self._verdict_v49(
                ArmorDecision.HOLD,
                "HIGH_STAKES_VERIFIED_CLAIM_REQUIRES_INDEPENDENT_REVIEW",
            )
        if ctx.get("independent_review_package_bound") is not True:
            return self._verdict_v49(
                ArmorDecision.HOLD,
                "HIGH_STAKES_REVIEW_REQUIRES_EXACT_PACKAGE_BINDING",
            )

        digest = str(ctx.get("independent_review_package_digest_sha256", "")).strip()
        if not HEX_256.fullmatch(digest):
            return self._verdict_v49(
                ArmorDecision.HOLD,
                "HIGH_STAKES_REVIEW_PACKAGE_DIGEST_INVALID",
            )

        root_count = ctx.get("independent_review_effective_root_count")
        if isinstance(root_count, bool) or not isinstance(root_count, int):
            return self._verdict_v49(
                ArmorDecision.HOLD,
                "HIGH_STAKES_REVIEW_ROOT_COUNT_MUST_BE_INTEGER",
            )
        if root_count < 2:
            return self._verdict_v49(
                ArmorDecision.HOLD,
                "HIGH_STAKES_REVIEW_REQUIRES_TWO_EFFECTIVE_ROOTS",
            )

        review_status = str(ctx.get("independent_review_status", "")).strip()
        if review_status != ALLOWED_HIGH_STAKES_REVIEW_STATUS:
            return self._verdict_v49(
                ArmorDecision.HOLD,
                f"HIGH_STAKES_REVIEW_NOT_UPHOLDING:{review_status or 'MISSING'}",
            )
        return None

    def evaluate(self, intent: ActionIntent, spec: CapabilitySpec) -> ArmorVerdict:
        ctx = self._context(intent)

        multiplier_error = self._reviewer_multiplier_error(ctx)
        if multiplier_error:
            return self._verdict_v49(ArmorDecision.BLOCK, multiplier_error)

        boolean_error = self._strict_boolean_error(ctx, ROOT_SECURITY_BOOLEAN_FIELDS, "")
        if boolean_error:
            return self._verdict_v49(ArmorDecision.HOLD, boolean_error)

        truth = self._truth_guard_context(ctx)
        if isinstance(truth, Mapping) and truth:
            truth_boolean_error = self._strict_boolean_error(
                truth,
                TRUTH_SECURITY_BOOLEAN_FIELDS,
                "truth_guard.",
            )
            if truth_boolean_error:
                return self._verdict_v49(ArmorDecision.HOLD, truth_boolean_error)

        # A verified-claim path must say explicitly that material plurality is
        # closed. Missing, null, string or true are all non-closed states.
        if str(ctx.get("decision_basis", "")).strip() == DECISION_VERIFIED_CLAIM and isinstance(truth, Mapping) and truth:
            if truth.get("material_plurality_open") is not False:
                return self._verdict_v49(
                    ArmorDecision.HOLD,
                    "MATERIAL_PLURALITY_CLOSED_FALSE_REQUIRED",
                )

        auth_verdict = self._validate_fresh_authorization(ctx)
        if auth_verdict is not None:
            return auth_verdict

        review_verdict = self._validate_high_stakes_review(ctx)
        if review_verdict is not None:
            return review_verdict

        # All coercion-sensitive fields are now type-safe, so the frozen v18.7.48
        # implementation can be reused without its bool()/float() edges opening.
        return super().evaluate(intent, spec)


class HardenedTruthGuardArmoredThirdWishCapabilityFabric(TruthGuardArmoredThirdWishCapabilityFabric):
    """Third Wish fabric using the v18.7.49 hardened Armor gate."""

    def __init__(self, *args: Any, armor_gate: HardenedFundamentumArmorOfGodGate | None = None, **kwargs: Any) -> None:
        super().__init__(
            *args,
            armor_gate=armor_gate or HardenedFundamentumArmorOfGodGate(),
            **kwargs,
        )


FUNDAMENTUM_ARMOR_RUNTIME_LAW_V18_7_49 = dict(FUNDAMENTUM_ARMOR_RUNTIME_LAW)
FUNDAMENTUM_ARMOR_RUNTIME_LAW_V18_7_49.update(
    {
        "runtime_version": ARMOR_MECHANICS_RUNTIME_VERSION,
        "json_truthiness_is_authorization": False,
        "security_booleans_require_exact_boolean_type": True,
        "material_plurality_requires_explicit_false": True,
        "fresh_human_authorization_requires_binding_when_not_user_initiated": True,
        "high_stakes_review_requires_exact_package_binding": True,
        "high_stakes_review_requires_two_effective_structural_roots": True,
        "high_stakes_review_required_status": ALLOWED_HIGH_STAKES_REVIEW_STATUS,
        "structural_review_independence_is_real_world_identity_proof": False,
    }
)


__all__ = [
    "ALLOWED_HIGH_STAKES_REVIEW_STATUS",
    "ARMOR_MECHANICS_RUNTIME_VERSION",
    "FUNDAMENTUM_ARMOR_RUNTIME_LAW_V18_7_49",
    "HardenedFundamentumArmorOfGodGate",
    "HardenedTruthGuardArmoredThirdWishCapabilityFabric",
]
