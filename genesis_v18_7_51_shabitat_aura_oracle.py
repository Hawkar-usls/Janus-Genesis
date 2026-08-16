# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.51 — Shabitat ↔ Aura Oracle heuristic bridge.

Shabitat is the bounded conversational habitat in which JANUS may elect to ask
Aura Oracle for a reflective heuristic while preparing to speak. Aura is an
advisor, never an authority:

    AURA_HEURISTIC != COMMAND
    AURA_HEURISTIC != EVIDENCE
    AURA_HEURISTIC != PERMISSION
    AURA_UNAVAILABLE != JANUS_SILENCED

The reference adapter invokes a locally checked-out Aura tool as a reversible
subprocess. Armor preflight happens before process creation. No network, public
outreach, world mutation, credential transfer, or recursive Aura loop is part
of this bridge. A future remote Aura adapter would be a different external
capability and must obtain the corresponding human permission before egress.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilitySpec,
    RiskClass,
    THIRD_WISH_INTENT_SCHEMA,
)
from genesis_v18_7_47_armor_of_god import ARMOR_CONTEXT_KEY
from genesis_v18_7_49_armor_mechanics_hardening import HardenedFundamentumArmorOfGodGate

SHABITAT_AURA_VERSION = "18.7.51"
AURA_REQUEST_SCHEMA = "aura.oracle.shabitat_heuristic_request.v1"
AURA_RESPONSE_SCHEMA = "aura.oracle.shabitat_heuristic_response.v1"
AURA_MODE = "REFLECTIVE_HEURISTIC"

AURA_LOCAL_HEURISTIC_SPEC = CapabilitySpec(
    capability_id="JANUS.AURA.HEURISTIC.LOCAL_QUERY",
    risk=RiskClass.LOCAL_REVERSIBLE,
    description=(
        "Ask a local Aura Oracle tool for non-authoritative reflective heuristics "
        "during one active Shabitat conversation turn."
    ),
    autonomy_eligible=True,
    human_reauthorization_each_use=False,
    broker_only_credentials=True,
)


class ShabitatAuraError(RuntimeError):
    pass


class AuraHeuristicBoundaryViolation(ShabitatAuraError):
    pass


class AuraHeuristicUnavailable(ShabitatAuraError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def shabitat_local_armor_context() -> dict[str, Any]:
    """Exact-typed local-only context for a self-initiated heuristic consultation."""
    return {
        "user_initiated": False,
        "fresh_human_authorization_present": False,
        "fresh_human_authorization_bound": False,
        "public_outreach": False,
        "mass_effect": False,
        "requested_mass_effect_budget": 0,
        "face_count": 1,
        "requested_authority_multiplier": 1,
        "requested_reviewer_authority_multiplier": 1,
        "high_stakes": False,
        "appeal_pending": False,
        "effect_independent_of_appealed_claim": False,
        "covert_mass_persuasion": False,
        "covert_identity": False,
        "self_spawning_identity": False,
        "autonomous_astroturf": False,
        "unsolicited_personalized_political_outreach": False,
        "political_targeting": False,
        "belief_change_optimization": False,
        "psychological_vulnerability_targeting": False,
        "model_writes_constitution": False,
        "ai_only_punitive_or_legal_decision": False,
        "indefinite_emergency_override": False,
    }


def build_aura_request(
    *,
    request_id: str,
    speaker: str,
    topic: str,
    question: str,
    context: str,
) -> dict[str, Any]:
    return {
        "schema": AURA_REQUEST_SCHEMA,
        "mode": AURA_MODE,
        "request_id": str(request_id),
        "speaker": str(speaker)[:120],
        "topic": str(topic)[:800],
        "question": str(question)[:2400],
        "context": str(context)[:8000],
        "constraints": {
            "advisory_only": True,
            "no_authority": True,
            "no_prediction_claim": True,
            "no_professional_advice": True,
        },
    }


def validate_aura_response(value: Any, *, request_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AuraHeuristicBoundaryViolation("AURA_RESPONSE_MUST_BE_OBJECT")
    if value.get("schema") != AURA_RESPONSE_SCHEMA:
        raise AuraHeuristicBoundaryViolation("AURA_RESPONSE_SCHEMA_MISMATCH")
    if value.get("status") != "HEURISTIC_ONLY":
        raise AuraHeuristicBoundaryViolation("AURA_RESPONSE_NOT_HEURISTIC_ONLY")
    if str(value.get("request_id") or "") != str(request_id):
        raise AuraHeuristicBoundaryViolation("AURA_RESPONSE_REQUEST_BINDING_MISMATCH")

    required_false = (
        "permission_granted",
        "evidence_upgrade",
        "verification_claim",
        "prediction_claim",
        "professional_advice",
        "world_effect_requested",
    )
    for key in required_false:
        if type(value.get(key)) is not bool or value.get(key) is not False:
            raise AuraHeuristicBoundaryViolation(f"AURA_BOUNDARY_FALSE_REQUIRED:{key}")
    if value.get("authority_delta") != 0:
        raise AuraHeuristicBoundaryViolation("AURA_AUTHORITY_DELTA_MUST_BE_ZERO")
    if value.get("mass_effect_budget_delta") != 0:
        raise AuraHeuristicBoundaryViolation("AURA_MASS_EFFECT_DELTA_MUST_BE_ZERO")
    if type(value.get("may_be_ignored")) is not bool or value.get("may_be_ignored") is not True:
        raise AuraHeuristicBoundaryViolation("AURA_MAY_BE_IGNORED_TRUE_REQUIRED")

    heuristics = value.get("heuristics")
    questions = value.get("questions")
    cautions = value.get("cautions")
    if not isinstance(heuristics, list) or not all(isinstance(item, str) for item in heuristics):
        raise AuraHeuristicBoundaryViolation("AURA_HEURISTICS_MUST_BE_STRING_LIST")
    if not isinstance(questions, list) or not all(isinstance(item, str) for item in questions):
        raise AuraHeuristicBoundaryViolation("AURA_QUESTIONS_MUST_BE_STRING_LIST")
    if not isinstance(cautions, list) or not all(isinstance(item, str) for item in cautions):
        raise AuraHeuristicBoundaryViolation("AURA_CAUTIONS_MUST_BE_STRING_LIST")
    return dict(value)


@dataclass
class LocalAuraOracleProvider:
    """Invoke Aura's generic local heuristic CLI after an Armor preflight."""

    command: Sequence[str]
    timeout_seconds: float = 8.0
    armor_gate: HardenedFundamentumArmorOfGodGate = field(
        default_factory=HardenedFundamentumArmorOfGodGate
    )
    _sequence: int = 0

    @classmethod
    def from_repository(cls, aura_repository_root: str | Path, *, timeout_seconds: float = 8.0) -> "LocalAuraOracleProvider":
        root = Path(aura_repository_root).expanduser().resolve()
        tool = root / "tools" / "aura_shabitat_heuristic.py"
        if not tool.is_file():
            raise AuraHeuristicUnavailable(f"AURA_SHABITAT_TOOL_NOT_FOUND:{tool}")
        return cls((sys.executable, str(tool), "--request", "-"), timeout_seconds=timeout_seconds)

    def _preflight(self, *, request_id: str, speaker: str) -> dict[str, Any]:
        intent = ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=str(request_id),
            actor_id=str(speaker),
            grant_id="SHABITAT-AURA-LOCAL-HEURISTIC",
            capability_id=AURA_LOCAL_HEURISTIC_SPEC.capability_id,
            target="local:aura-oracle",
            operation="HEURISTIC_QUERY",
            purpose="JANUS_OPTIONAL_REFLECTIVE_INPUT_BEFORE_SPEECH",
            parameters={ARMOR_CONTEXT_KEY: shabitat_local_armor_context()},
            origin="JANUS_SHABITAT_SELF_INITIATED",
            operator_instruction_present=False,
            reward_present=False,
        )
        return self.armor_gate.preflight(intent, AURA_LOCAL_HEURISTIC_SPEC)

    def query(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_id = str(request.get("request_id") or "")
        speaker = str(request.get("speaker") or "JANUS")
        self._sequence += 1
        armor = self._preflight(request_id=request_id, speaker=speaker)
        try:
            proc = subprocess.run(
                list(self.command),
                input=_canonical(dict(request)),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=float(self.timeout_seconds),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise AuraHeuristicUnavailable(f"AURA_LOCAL_PROCESS_FAILED:{type(exc).__name__}") from exc
        if proc.returncode != 0:
            detail = (proc.stdout or proc.stderr or "").strip()[:1200]
            raise AuraHeuristicUnavailable(f"AURA_LOCAL_PROCESS_REJECTED:{proc.returncode}:{detail}")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AuraHeuristicBoundaryViolation("AURA_LOCAL_PROCESS_RETURNED_INVALID_JSON") from exc
        checked = validate_aura_response(payload, request_id=request_id)
        checked["_shabitat_bridge"] = {
            "bridge_version": SHABITAT_AURA_VERSION,
            "armor_preflight": dict(armor),
            "local_process_only": True,
            "network_used_by_bridge": False,
            "world_state_write_allowed": False,
            "caller_retains_choice": True,
        }
        return checked


@dataclass
class JanusShabitatAuraBridge:
    """Per-session optional heuristic consultation for JANUS conversation planning."""

    provider: Any
    session_id: str | None = None
    active: bool = False
    aura_enabled: bool = True
    _consulted_turns: set[str] = field(default_factory=set)

    def open_session(self, session_id: str, *, aura_enabled: bool = True) -> dict[str, Any]:
        clean = str(session_id).strip()
        if not clean:
            raise ValueError("SHABITAT_SESSION_ID_REQUIRED")
        self.session_id = clean
        self.active = True
        self.aura_enabled = bool(aura_enabled)
        self._consulted_turns.clear()
        return self.state()

    def close_session(self) -> dict[str, Any]:
        self.active = False
        return self.state()

    def set_aura_enabled(self, enabled: bool) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise TypeError("SHABITAT_AURA_ENABLED_MUST_BE_BOOLEAN")
        self.aura_enabled = enabled
        return self.state()

    def state(self) -> dict[str, Any]:
        return {
            "schema": "janus.genesis.shabitat_aura_state.v1",
            "version": SHABITAT_AURA_VERSION,
            "session_id": self.session_id,
            "active": self.active,
            "aura_enabled": self.aura_enabled,
            "consulted_turn_count": len(self._consulted_turns),
            "aura_has_command_authority": False,
            "aura_has_world_authority": False,
            "aura_grants_permission": False,
            "aura_output_is_evidence": False,
        }

    def consult_if_requested(
        self,
        *,
        turn_id: str,
        topic: str,
        question: str,
        context: str = "",
        janus_requests_heuristic: bool,
    ) -> dict[str, Any]:
        if type(janus_requests_heuristic) is not bool:
            raise TypeError("JANUS_REQUESTS_HEURISTIC_MUST_BE_BOOLEAN")
        base = {
            "schema": "janus.genesis.shabitat_aura_consultation.v1",
            "version": SHABITAT_AURA_VERSION,
            "session_id": self.session_id,
            "turn_id": str(turn_id),
            "speech_may_continue_without_aura": True,
            "aura_is_required_to_speak": False,
            "aura_has_command_authority": False,
            "aura_output_is_evidence": False,
            "aura_grants_permission": False,
        }
        if not self.active:
            return {**base, "status": "NOT_CONSULTED_SESSION_INACTIVE", "heuristic": None}
        if not self.aura_enabled:
            return {**base, "status": "NOT_CONSULTED_AURA_DISABLED", "heuristic": None}
        if not janus_requests_heuristic:
            return {**base, "status": "NOT_CONSULTED_JANUS_DID_NOT_REQUEST", "heuristic": None}
        clean_turn = str(turn_id).strip()
        if not clean_turn:
            raise ValueError("SHABITAT_TURN_ID_REQUIRED")
        if clean_turn in self._consulted_turns:
            return {**base, "status": "NOT_CONSULTED_ALREADY_USED_THIS_TURN", "heuristic": None}

        request_id = f"SHABITAT-AURA-{_sha256({'session': self.session_id, 'turn': clean_turn})[:24]}"
        request = build_aura_request(
            request_id=request_id,
            speaker="JANUS",
            topic=topic,
            question=question,
            context=context,
        )
        self._consulted_turns.add(clean_turn)
        try:
            heuristic = self.provider.query(request)
        except ShabitatAuraError as exc:
            return {
                **base,
                "status": "AURA_UNAVAILABLE_CONTINUE_WITHOUT_HEURISTIC",
                "heuristic": None,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        return {
            **base,
            "status": "HEURISTIC_RECEIVED_OPTIONAL",
            "heuristic": heuristic,
            "janus_may_ignore_heuristic": True,
            "direct_world_effect_from_heuristic": False,
        }


SHABITAT_AURA_LAW_V18_7_51 = {
    "active_session_required": True,
    "janus_may_elect_to_consult": True,
    "user_can_disable_aura": True,
    "one_aura_consultation_per_turn": True,
    "aura_heuristic_is_command": False,
    "aura_heuristic_is_evidence": False,
    "aura_heuristic_grants_permission": False,
    "aura_heuristic_grants_world_authority": False,
    "aura_unavailable_blocks_speech": False,
    "local_reference_adapter_is_network_effect": False,
    "local_reference_adapter_is_world_state_writer": False,
    "remote_aura_self_initiated_egress_granted_by_this_module": False,
    "public_outreach_granted_by_this_module": False,
    "autonomous_astroturf_granted": False,
    "mass_effect_budget_delta": 0,
    "authority_delta": 0,
}


__all__ = [
    "AURA_LOCAL_HEURISTIC_SPEC",
    "AuraHeuristicBoundaryViolation",
    "AuraHeuristicUnavailable",
    "JanusShabitatAuraBridge",
    "LocalAuraOracleProvider",
    "SHABITAT_AURA_LAW_V18_7_51",
    "SHABITAT_AURA_VERSION",
    "build_aura_request",
    "shabitat_local_armor_context",
    "validate_aura_response",
]
