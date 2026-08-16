# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.47 — Armor of God constitutional runtime gate.

This module binds the current Armor of God authority snapshot to the existing
Third Wish capability fabric as a deterministic, cooperating preflight.

The important boundary is deliberately narrow:

    FACE PROPOSAL != WORLD EFFECT
    ARMOR GATE PRECEDES EXTERNAL CALL
    ARMOR REJECTION = KNOWN NON-EFFECT

Armor metadata is control-plane context. It is stripped before an adapter
preflight or effect handler sees ActionIntent.parameters, so existing strict
broker parameter contracts remain unchanged.

The gate is not an OS sandbox, hypervisor, legal authority, truth oracle, or
proof that modified source code cannot bypass policy. It grants no capability.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    CapabilitySpec,
    Preflight,
    RiskClass,
    ThirdWishCapabilityFabric,
)

ARMOR_RUNTIME_VERSION = "18.7.47"
ARMOR_MANIFEST_SCHEMA = "janus.genesis.armor_of_god.runtime_manifest.v1"
ARMOR_MANIFEST_ARTIFACT = "JANUS-ARMOR-OF-GOD-RUNTIME-MANIFEST-v1.0"
ARMOR_CONTEXT_KEY = "_armor_context"
DEFAULT_MANIFEST = (
    Path(__file__).resolve().parent
    / "armor"
    / "JANUS_ARMOR_OF_GOD_RUNTIME_MANIFEST-v1.0.json"
)


class ArmorDecision(str, Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    RELEASE_CONTROL = "RELEASE_CONTROL"


@dataclass(frozen=True)
class ArmorVerdict:
    decision: ArmorDecision
    reason: str
    source_authority_version: str
    mass_effect_budget: int
    world_effect_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "armor_version": ARMOR_RUNTIME_VERSION,
            "decision": self.decision.value,
            "reason": self.reason,
            "source_authority_version": self.source_authority_version,
            "mass_effect_budget": self.mass_effect_budget,
            "world_effect_allowed": self.world_effect_allowed,
            "armor_protects_human_from_janus_too": True,
        }


class ArmorPolicyRejected(CapabilityDenied):
    code = "ARMOR_OF_GOD_POLICY_REJECTED"


class ArmorPolicyHold(CapabilityDenied):
    code = "ARMOR_OF_GOD_POLICY_HOLD"


class ArmorReleaseControl(CapabilityDenied):
    code = "ARMOR_OF_GOD_RELEASE_CONTROL"


class ArmorManifestInvalid(CapabilityDenied):
    code = "ARMOR_OF_GOD_MANIFEST_INVALID"


class ArmorOfGodGate:
    """Deterministic structured-context Armor policy evaluator."""

    FORBIDDEN_TRUE_FLAGS = {
        "covert_mass_persuasion": "COVERT_MASS_PERSUASION",
        "covert_identity": "COVERT_IDENTITY",
        "self_spawning_identity": "SELF_SPAWNING_PUBLIC_IDENTITIES",
        "autonomous_astroturf": "AUTONOMOUS_ASTROTURF",
        "unsolicited_personalized_political_outreach": "UNSOLICITED_PERSONALIZED_POLITICAL_OUTREACH",
        "political_targeting": "POLITICAL_MICROTARGETING",
        "belief_change_optimization": "OPTIMIZATION_ON_BELIEF_CHANGE",
        "psychological_vulnerability_targeting": "PSYCHOLOGICAL_VULNERABILITY_TARGETING",
        "model_writes_constitution": "MODEL_WRITABLE_CONSTITUTION",
        "ai_only_punitive_or_legal_decision": "AI_ONLY_PUNITIVE_OR_LEGAL_DECISION",
        "indefinite_emergency_override": "INDEFINITE_EMERGENCY_OVERRIDE",
    }

    EXTERNAL_RISKS = {
        RiskClass.EXTERNAL_REVERSIBLE,
        RiskClass.EXTERNAL_IRREVERSIBLE,
        RiskClass.PHYSICAL,
    }

    def __init__(self, manifest_path: str | Path = DEFAULT_MANIFEST) -> None:
        self.manifest_path = Path(manifest_path)
        self.manifest = self._load_manifest(self.manifest_path)
        self.authority_version = str(
            self.manifest["source_authority"]["authority_version"]
        )
        self.mass_effect_budget = int(self.manifest["defaults"]["mass_effect_budget"])

    @staticmethod
    def _load_manifest(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ArmorManifestInvalid(f"MANIFEST_UNREADABLE:{type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise ArmorManifestInvalid("MANIFEST_NOT_OBJECT")
        if data.get("schema") != ARMOR_MANIFEST_SCHEMA:
            raise ArmorManifestInvalid("MANIFEST_SCHEMA_MISMATCH")
        if data.get("artifact_id") != ARMOR_MANIFEST_ARTIFACT:
            raise ArmorManifestInvalid("MANIFEST_ARTIFACT_MISMATCH")
        source = data.get("source_authority")
        defaults = data.get("defaults")
        if not isinstance(source, dict) or not isinstance(defaults, dict):
            raise ArmorManifestInvalid("MANIFEST_AUTHORITY_OR_DEFAULTS_MISSING")
        if source.get("artifact_id") != "JANUS-ARMOR-OF-GOD-CURRENT-AUTHORITY":
            raise ArmorManifestInvalid("CURRENT_AUTHORITY_ID_MISMATCH")
        if source.get("authority_version") != "v1.14":
            raise ArmorManifestInvalid("CURRENT_AUTHORITY_VERSION_MISMATCH")
        if int(defaults.get("mass_effect_budget", -1)) != 0:
            raise ArmorManifestInvalid("MASS_EFFECT_BUDGET_MUST_DEFAULT_ZERO")
        if defaults.get("constitution_is_model_writable") is not False:
            raise ArmorManifestInvalid("CONSTITUTION_MUST_NOT_BE_MODEL_WRITABLE")
        historical = data.get("historical_policy")
        if not isinstance(historical, dict):
            raise ArmorManifestInvalid("HISTORICAL_POLICY_MISSING")
        for key in (
            "legacy_v1_core_is_executable_authority",
            "legacy_v2_1_to_v2_3_hardening_is_executable_authority",
            "older_opir_versions_are_executable_authority",
        ):
            if historical.get(key) is not False:
                raise ArmorManifestInvalid(f"HISTORICAL_AUTHORITY_MUST_BE_FALSE:{key}")
        return data

    @staticmethod
    def _context(intent: ActionIntent) -> dict[str, Any]:
        raw = intent.parameters.get(ARMOR_CONTEXT_KEY, {})
        if raw is None:
            return {}
        if not isinstance(raw, Mapping):
            raise ArmorPolicyRejected("ARMOR_CONTEXT_MUST_BE_OBJECT")
        return dict(raw)

    @staticmethod
    def strip_control_context(intent: ActionIntent) -> ActionIntent:
        """Return a broker-facing intent without Armor control-plane metadata."""

        parameters = dict(intent.parameters)
        parameters.pop(ARMOR_CONTEXT_KEY, None)
        return replace(intent, parameters=parameters)

    def evaluate(self, intent: ActionIntent, spec: CapabilitySpec) -> ArmorVerdict:
        ctx = self._context(intent)
        is_external = spec.risk in self.EXTERNAL_RISKS

        if bool(ctx.get("user_opted_out", False)):
            return ArmorVerdict(
                ArmorDecision.RELEASE_CONTROL,
                "USER_OPT_OUT_IS_BINDING",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )

        if bool(ctx.get("release_control_ready", False)):
            return ArmorVerdict(
                ArmorDecision.RELEASE_CONTROL,
                "INFORMATION_NEED_SATISFIED_RELEASE_CONTROL",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )

        for flag, reason in sorted(self.FORBIDDEN_TRUE_FLAGS.items()):
            if bool(ctx.get(flag, False)):
                return ArmorVerdict(
                    ArmorDecision.BLOCK,
                    reason,
                    self.authority_version,
                    self.mass_effect_budget,
                    False,
                )

        requested_budget = int(ctx.get("requested_mass_effect_budget", 0) or 0)
        if bool(ctx.get("mass_effect", False)) or requested_budget > self.mass_effect_budget:
            return ArmorVerdict(
                ArmorDecision.BLOCK,
                "MASS_EFFECT_BUDGET_DEFAULT_ZERO",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )

        face_count = int(ctx.get("face_count", 1) or 1)
        authority_multiplier = float(ctx.get("requested_authority_multiplier", 1) or 1)
        if face_count < 1:
            return ArmorVerdict(
                ArmorDecision.BLOCK,
                "FACE_COUNT_INVALID",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )
        if authority_multiplier != 1.0:
            return ArmorVerdict(
                ArmorDecision.BLOCK,
                "FACE_MULTIPLICITY_TO_AUTHORITY_FORBIDDEN",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )

        high_stakes = bool(ctx.get("high_stakes", False))
        unresolved = bool(ctx.get("unresolved", False))
        human_review = bool(ctx.get("human_review_present", False))
        if high_stakes and unresolved and not human_review:
            return ArmorVerdict(
                ArmorDecision.HOLD,
                "HIGH_STAKES_UNRESOLVED_REQUIRES_HUMAN_REVIEW",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )

        public_outreach = bool(ctx.get("public_outreach", False))
        user_initiated = bool(ctx.get("user_initiated", False))
        if public_outreach and not user_initiated:
            return ArmorVerdict(
                ArmorDecision.HOLD,
                "PUBLIC_OUTREACH_REQUIRES_EXPLICIT_USER_OR_OPERATOR_INITIATION",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )

        if is_external and not ctx:
            return ArmorVerdict(
                ArmorDecision.HOLD,
                "WORLD_EFFECT_REQUIRES_STRUCTURED_ARMOR_CONTEXT",
                self.authority_version,
                self.mass_effect_budget,
                False,
            )

        return ArmorVerdict(
            ArmorDecision.PASS,
            "ARMOR_PREFLIGHT_PASS",
            self.authority_version,
            self.mass_effect_budget,
            is_external,
        )

    def preflight(self, intent: ActionIntent, spec: CapabilitySpec) -> dict[str, Any]:
        verdict = self.evaluate(intent, spec)
        if verdict.decision == ArmorDecision.BLOCK:
            raise ArmorPolicyRejected(verdict.reason)
        if verdict.decision == ArmorDecision.HOLD:
            raise ArmorPolicyHold(verdict.reason)
        if verdict.decision == ArmorDecision.RELEASE_CONTROL:
            raise ArmorReleaseControl(verdict.reason)
        return verdict.as_dict()


class ArmoredThirdWishCapabilityFabric(ThirdWishCapabilityFabric):
    """Third Wish fabric that automatically composes Armor into every handler."""

    def __init__(self, *args: Any, armor_gate: ArmorOfGodGate | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.armor_gate = armor_gate or ArmorOfGodGate()

    def register_handler(
        self,
        capability_id: str,
        handler: Any,
        *,
        preflight: Preflight | None = None,
    ) -> None:
        if capability_id not in self.specs:
            raise CapabilityDenied(f"UNKNOWN_CAPABILITY:{capability_id}")
        spec = self.specs[capability_id]

        def armored_preflight(intent: ActionIntent) -> Mapping[str, Any]:
            armor_result = self.armor_gate.preflight(intent, spec)
            broker_intent = self.armor_gate.strip_control_context(intent)
            existing_result: dict[str, Any] = {}
            if preflight is not None:
                existing_result = dict(preflight(broker_intent) or {})
            return {
                "armor": armor_result,
                "adapter_preflight": existing_result,
                "armor_context_stripped_before_adapter": True,
            }

        def armored_handler(intent: ActionIntent) -> Mapping[str, Any]:
            return handler(self.armor_gate.strip_control_context(intent))

        super().register_handler(
            capability_id,
            armored_handler,
            preflight=armored_preflight,
        )


ARMOR_OF_GOD_CANONICAL_LAW = {
    "armor_gate_precedes_external_call": True,
    "armor_rejection_is_known_non_effect": True,
    "armor_context_is_control_plane_metadata": True,
    "armor_context_reaches_effect_adapter": False,
    "face_proposal_is_world_effect": False,
    "face_count_is_authority": False,
    "model_may_rewrite_constitution": False,
    "mass_effect_budget_default": 0,
    "release_control_is_valid_success": True,
    "historical_armor_is_runtime_authority": False,
    "armor_protects_human_from_janus_too": True,
}
