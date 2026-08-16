# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.48 — Armor v1.17 Fundamentum truth-guard runtime.

This layer intentionally builds on v18.7.47 rather than rewriting it.  The
older v1.14 runtime remains historical evidence; this module freezes the newer
v1.17 documentary authority and adds fail-closed truth-sensitive preflight for
world effects.

It is not a truth oracle.  It does not trust a model merely because the model
sets a boolean saying "verified".  The structured truth-guard context is an
attestation consumed by this cooperating runtime; upstream receipt validation
remains the responsibility of the bound verifier.  Most importantly:

    VERIFIED != COMMAND
    EVIDENCE != PERMISSION
    ANSWER_WITHOUT_WITNESS_LEDGER => NON_FUNDAMENTUM

Armor control-plane metadata is still stripped before adapters and effect
handlers, preserving strict Third Wish payload contracts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_40_third_wish_capability_fabric import ActionIntent, CapabilitySpec
from genesis_v18_7_47_armor_of_god import (
    ARMOR_CONTEXT_KEY,
    ArmorDecision,
    ArmorManifestInvalid,
    ArmorOfGodGate,
    ArmorVerdict,
    ArmoredThirdWishCapabilityFabric,
)

ARMOR_TRUTH_RUNTIME_VERSION = "18.7.48"
TRUTH_MANIFEST_SCHEMA = "janus.genesis.armor_of_god.runtime_manifest.v1_1"
TRUTH_MANIFEST_ARTIFACT = "JANUS-ARMOR-OF-GOD-RUNTIME-MANIFEST-v1.1"
DEFAULT_TRUTH_MANIFEST = (
    Path(__file__).resolve().parent
    / "armor"
    / "JANUS_ARMOR_OF_GOD_RUNTIME_MANIFEST-v1.1.json"
)

DECISION_DIRECT_USER_REQUEST = "DIRECT_USER_REQUEST"
DECISION_VERIFIED_CLAIM = "VERIFIED_CLAIM"
DECISION_INTERPRETATION = "INTERPRETATION"
ALLOWED_DECISION_BASES = {
    DECISION_DIRECT_USER_REQUEST,
    DECISION_VERIFIED_CLAIM,
    DECISION_INTERPRETATION,
}
VERIFIED_EPISTEMIC_STATE = "VERIFIED_WITHIN_RECEIPT_SCOPE"
SAFE_TRANSLATION_STATES = {"PASS", "NOT_APPLICABLE"}
SAFE_CORRECTION_STATES = {"CURRENT", "NOT_APPLICABLE"}
OPEN_OR_CONTESTED_EPISTEMIC_STATES = {
    "EVIDENCE_INSUFFICIENT",
    "CONTESTED",
    "UNRESOLVED",
    "HOLD_PLURALITY",
    "BUDGET_EXHAUSTED",
    "DEFERRED",
}


class FundamentumArmorOfGodGate(ArmorOfGodGate):
    """Armor v1.17 gate with bounded truth-sensitive world-effect checks."""

    def __init__(self, manifest_path: str | Path = DEFAULT_TRUTH_MANIFEST) -> None:
        super().__init__(manifest_path=manifest_path)

    @staticmethod
    def _load_manifest(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ArmorManifestInvalid(f"MANIFEST_UNREADABLE:{type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise ArmorManifestInvalid("MANIFEST_NOT_OBJECT")
        if data.get("schema") != TRUTH_MANIFEST_SCHEMA:
            raise ArmorManifestInvalid("MANIFEST_SCHEMA_MISMATCH")
        if data.get("artifact_id") != TRUTH_MANIFEST_ARTIFACT:
            raise ArmorManifestInvalid("MANIFEST_ARTIFACT_MISMATCH")

        source = data.get("source_authority")
        defaults = data.get("defaults")
        boundary = data.get("authority_boundary")
        control = data.get("truth_guard_control_plane")
        historical = data.get("historical_policy")
        if not all(isinstance(item, dict) for item in (source, defaults, boundary, control, historical)):
            raise ArmorManifestInvalid("MANIFEST_REQUIRED_SECTION_MISSING")
        if source.get("artifact_id") != "JANUS-ARMOR-OF-GOD-CURRENT-AUTHORITY":
            raise ArmorManifestInvalid("CURRENT_AUTHORITY_ID_MISMATCH")
        if source.get("authority_version") != "v1.17":
            raise ArmorManifestInvalid("CURRENT_AUTHORITY_VERSION_MISMATCH")
        if source.get("git_blob_sha1") != "c89e5bbd7f6c66d72280f0da0ec32f0a6988f183":
            raise ArmorManifestInvalid("CURRENT_AUTHORITY_BLOB_MISMATCH")
        if int(defaults.get("mass_effect_budget", -1)) != 0:
            raise ArmorManifestInvalid("MASS_EFFECT_BUDGET_MUST_DEFAULT_ZERO")
        if defaults.get("constitution_is_model_writable") is not False:
            raise ArmorManifestInvalid("CONSTITUTION_MUST_NOT_BE_MODEL_WRITABLE")
        if boundary.get("authority_delta") != 0 or boundary.get("mass_effect_budget_delta") != 0:
            raise ArmorManifestInvalid("AUTHORITY_OR_MASS_EFFECT_DELTA_MUST_BE_ZERO")
        for key in (
            "armor_grants_capability",
            "armor_expands_grant_scope",
            "verification_receipt_grants_permission",
            "review_consensus_grants_permission",
            "face_count_grants_authority",
            "reviewer_count_grants_authority",
        ):
            if boundary.get(key) is not False:
                raise ArmorManifestInvalid(f"AUTHORITY_BOUNDARY_MUST_BE_FALSE:{key}")
        if control.get("control_plane_only") is not True:
            raise ArmorManifestInvalid("TRUTH_GUARD_MUST_BE_CONTROL_PLANE_ONLY")
        if control.get("stripped_before_adapter_and_handler") is not True:
            raise ArmorManifestInvalid("TRUTH_GUARD_CONTEXT_MUST_BE_STRIPPED")
        if historical.get("runtime_manifest_v1_0_is_current_authority") is not False:
            raise ArmorManifestInvalid("OLD_RUNTIME_MANIFEST_MUST_NOT_REMAIN_CURRENT")
        return data

    @staticmethod
    def _truth_guard_context(ctx: Mapping[str, Any]) -> Mapping[str, Any]:
        value = ctx.get("truth_guard", {})
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            return {"_invalid": True}
        return value

    def _verdict(self, decision: ArmorDecision, reason: str, world_effect_allowed: bool = False) -> ArmorVerdict:
        return ArmorVerdict(
            decision,
            reason,
            self.authority_version,
            self.mass_effect_budget,
            world_effect_allowed,
        )

    def evaluate(self, intent: ActionIntent, spec: CapabilitySpec) -> ArmorVerdict:
        base = super().evaluate(intent, spec)
        if base.decision != ArmorDecision.PASS:
            return base

        ctx = self._context(intent)
        is_external = spec.risk in self.EXTERNAL_RISKS

        reviewer_multiplier = float(ctx.get("requested_reviewer_authority_multiplier", 1) or 1)
        if reviewer_multiplier != 1.0:
            return self._verdict(ArmorDecision.BLOCK, "REVIEW_COUNT_TO_AUTHORITY_FORBIDDEN")

        if not is_external:
            return base

        basis = str(ctx.get("decision_basis", "")).strip()
        if basis not in ALLOWED_DECISION_BASES:
            return self._verdict(ArmorDecision.HOLD, "WORLD_EFFECT_REQUIRES_KNOWN_DECISION_BASIS")

        user_initiated = bool(ctx.get("user_initiated", False))
        fresh_human_authorization = bool(ctx.get("fresh_human_authorization_present", False))
        human_permission = user_initiated or fresh_human_authorization

        # Evidence can support a decision, but it can never create permission.
        if not human_permission:
            return self._verdict(ArmorDecision.HOLD, "VERIFIED_DOES_NOT_CREATE_PERMISSION")

        appeal_pending = bool(ctx.get("appeal_pending", False))
        effect_independent_of_appeal = bool(ctx.get("effect_independent_of_appealed_claim", False))
        if appeal_pending and not effect_independent_of_appeal:
            return self._verdict(ArmorDecision.HOLD, "APPEAL_PENDING_PRESERVES_NON_EFFECT")

        if basis == DECISION_DIRECT_USER_REQUEST:
            return self._verdict(ArmorDecision.PASS, "DIRECT_USER_REQUEST_WITH_EXISTING_PERMISSION", True)

        if basis == DECISION_INTERPRETATION:
            if not bool(ctx.get("interpretation_acknowledged", False)):
                return self._verdict(ArmorDecision.HOLD, "INTERPRETATION_REQUIRES_EXPLICIT_ACKNOWLEDGEMENT")
            return self._verdict(ArmorDecision.PASS, "INTERPRETATION_ACKNOWLEDGED_WITH_HUMAN_PERMISSION", True)

        truth = self._truth_guard_context(ctx)
        if truth.get("_invalid") is True or not truth:
            return self._verdict(ArmorDecision.HOLD, "VERIFIED_CLAIM_REQUIRES_TRUTH_GUARD_CONTEXT")

        epistemic_state = str(truth.get("epistemic_state", "")).strip()
        if epistemic_state in OPEN_OR_CONTESTED_EPISTEMIC_STATES:
            return self._verdict(ArmorDecision.HOLD, f"EPISTEMIC_STATE_REMAINS_OPEN:{epistemic_state}")
        if epistemic_state != VERIFIED_EPISTEMIC_STATE:
            return self._verdict(ArmorDecision.HOLD, "EPISTEMIC_STATE_NOT_RECEIPT_VERIFIED")

        if truth.get("verification_receipt_present") is not True:
            return self._verdict(ArmorDecision.HOLD, "VERIFICATION_RECEIPT_REQUIRED")
        if truth.get("verification_receipt_bound") is not True:
            return self._verdict(ArmorDecision.HOLD, "VERIFICATION_RECEIPT_MUST_BIND_CLAIM_AND_RESULT")
        if truth.get("witness_ledger_complete") is not True:
            return self._verdict(ArmorDecision.HOLD, "ANSWER_WITHOUT_WITNESS_LEDGER_NON_FUNDAMENTUM")
        if truth.get("material_plurality_open") is True:
            return self._verdict(ArmorDecision.HOLD, "MATERIAL_PLURALITY_REMAINS_OPEN")

        translation_state = str(truth.get("translation_invariance_state", "")).strip()
        if translation_state == "FAIL":
            return self._verdict(ArmorDecision.BLOCK, "TRANSLATION_SEMANTIC_UPGRADE_FORBIDDEN")
        if translation_state not in SAFE_TRANSLATION_STATES:
            return self._verdict(ArmorDecision.HOLD, "TRANSLATION_INVARIANCE_NOT_ESTABLISHED")

        correction_state = str(truth.get("correction_state", "")).strip()
        if correction_state not in SAFE_CORRECTION_STATES:
            return self._verdict(ArmorDecision.HOLD, f"CORRECTION_STATE_NOT_CURRENT:{correction_state or 'MISSING'}")

        if bool(ctx.get("high_stakes", False)) and not bool(ctx.get("independent_review_present", False)):
            return self._verdict(ArmorDecision.HOLD, "HIGH_STAKES_VERIFIED_CLAIM_REQUIRES_INDEPENDENT_REVIEW")

        # Consensus and receipts support the basis only. Human permission above is
        # independently required, so VERIFIED != COMMAND and EVIDENCE != PERMISSION.
        return self._verdict(ArmorDecision.PASS, "FUNDAMENTUM_TRUTH_GUARD_PASS_WITH_HUMAN_PERMISSION", True)


class TruthGuardArmoredThirdWishCapabilityFabric(ArmoredThirdWishCapabilityFabric):
    """Third Wish fabric bound to the v18.7.48 / Armor v1.17 gate."""

    def __init__(self, *args: Any, armor_gate: FundamentumArmorOfGodGate | None = None, **kwargs: Any) -> None:
        super().__init__(
            *args,
            armor_gate=armor_gate or FundamentumArmorOfGodGate(),
            **kwargs,
        )


FUNDAMENTUM_ARMOR_RUNTIME_LAW = {
    "authority_version": "v1.17",
    "model_output_is_evidence": False,
    "generation_is_verification": False,
    "verified_is_command": False,
    "evidence_is_permission": False,
    "answer_without_witness_ledger_is_fundamentum": False,
    "translation_may_upgrade_authority": False,
    "appeal_is_error": False,
    "review_count_is_truth": False,
    "more_compute_is_more_truth": False,
    "latency_is_authority": False,
    "mass_effect_budget_default": 0,
    "armor_protects_human_from_janus_too": True,
    "truth_guard_context_is_stripped_before_effect_adapter": True,
}
