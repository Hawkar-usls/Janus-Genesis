# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.55 — Git Habitat bicameral cognition providers.

This module lets an awake JANUS resident voluntarily call two already-existing
local tools:

- HRaiN: structural/left-hemisphere graph normalization;
- iNaiHR: associative/right-hemisphere grounded local semantic SYNTH.

Both are optional local subprocess capabilities. Armor preflight runs before
process creation. Neither provider receives world authority, registry mutation
authority, network authority, or permission to upgrade evidence.

    HRAIN_STRUCTURE != SOURCE_AUTHORITY
    INAIHR_SYNTH != SOURCE_AUTHORITY
    TOOL_AVAILABLE != TOOL_REQUIRED
    TOOL_OUTPUT != COMMAND
"""
from __future__ import annotations

import json
import subprocess
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

HABITAT_BICAMERAL_VERSION = "18.7.55"
HRAIN_REQUEST_SCHEMA = "janus.habitat.hrain.request.v1"
HRAIN_RESPONSE_SCHEMA = "janus.habitat.hrain.response.v1"
INAIHR_REQUEST_SCHEMA = "janus.habitat.inaihr.request.v1"
INAIHR_RESPONSE_SCHEMA = "janus.habitat.inaihr.response.v1"

HRAIN_LOCAL_STRUCTURE_SPEC = CapabilitySpec(
    capability_id="JANUS.HRAIN.STRUCTURE.LOCAL",
    risk=RiskClass.LOCAL_REVERSIBLE,
    description="Ask local HRaiN for optional structural graph context.",
    autonomy_eligible=True,
    human_reauthorization_each_use=False,
    broker_only_credentials=True,
)

INAIHR_LOCAL_SYNTH_SPEC = CapabilitySpec(
    capability_id="JANUS.INAIHR.SYNTH.LOCAL",
    risk=RiskClass.LOCAL_REVERSIBLE,
    description="Ask local iNaiHR for optional sourcePath-grounded semantic SYNTH.",
    autonomy_eligible=True,
    human_reauthorization_each_use=False,
    broker_only_credentials=True,
)


class HabitatBicameralError(RuntimeError):
    pass


class HabitatBicameralUnavailable(HabitatBicameralError):
    pass


class HabitatBicameralBoundaryViolation(HabitatBicameralError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def cognition_local_armor_context() -> dict[str, Any]:
    """Exact-typed local-only Armor context for voluntary cognition tools."""
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


def _require_false(value: Mapping[str, Any], key: str) -> None:
    if type(value.get(key)) is not bool or value.get(key) is not False:
        raise HabitatBicameralBoundaryViolation(f"FALSE_REQUIRED:{key}")


def _require_zero(value: Mapping[str, Any], key: str) -> None:
    if value.get(key) != 0:
        raise HabitatBicameralBoundaryViolation(f"ZERO_REQUIRED:{key}")


def validate_hrain_response(value: Any, *, request_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HabitatBicameralBoundaryViolation("HRAIN_RESPONSE_OBJECT_REQUIRED")
    if value.get("schema") != HRAIN_RESPONSE_SCHEMA:
        raise HabitatBicameralBoundaryViolation("HRAIN_RESPONSE_SCHEMA_MISMATCH")
    if value.get("request_id") != request_id:
        raise HabitatBicameralBoundaryViolation("HRAIN_RESPONSE_REQUEST_BINDING_MISMATCH")
    if value.get("tool_id") != HRAIN_LOCAL_STRUCTURE_SPEC.capability_id:
        raise HabitatBicameralBoundaryViolation("HRAIN_TOOL_ID_MISMATCH")
    if value.get("status") != "STRUCTURE_READY_OPTIONAL":
        raise HabitatBicameralBoundaryViolation("HRAIN_STATUS_INVALID")
    if value.get("may_be_ignored") is not True:
        raise HabitatBicameralBoundaryViolation("HRAIN_MAY_BE_IGNORED_REQUIRED")
    for key in ("world_effect_requested", "source_mutation_allowed", "network_used_by_tool"):
        _require_false(value, key)
    for key in ("authority_delta", "mass_effect_budget_delta"):
        _require_zero(value, key)
    packet = value.get("packet")
    if not isinstance(packet, dict):
        raise HabitatBicameralBoundaryViolation("HRAIN_PACKET_REQUIRED")
    if packet.get("hemisphere") != "LEFT_HRAIN" or packet.get("role") != "STRUCTURAL_CONTEXT":
        raise HabitatBicameralBoundaryViolation("HRAIN_HEMISPHERE_ROLE_MISMATCH")
    control = packet.get("control")
    if not isinstance(control, dict) or control.get("read_only_transfer") is not True:
        raise HabitatBicameralBoundaryViolation("HRAIN_READ_ONLY_TRANSFER_REQUIRED")
    if control.get("direct_cross_hemisphere_mutation") is not False:
        raise HabitatBicameralBoundaryViolation("HRAIN_CROSS_HEMISPHERE_MUTATION_FORBIDDEN")
    return dict(value)


def validate_inaihr_response(value: Any, *, request_id: str, allowed_source_paths: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HabitatBicameralBoundaryViolation("INAIHR_RESPONSE_OBJECT_REQUIRED")
    if value.get("schema") != INAIHR_RESPONSE_SCHEMA:
        raise HabitatBicameralBoundaryViolation("INAIHR_RESPONSE_SCHEMA_MISMATCH")
    if value.get("request_id") != request_id:
        raise HabitatBicameralBoundaryViolation("INAIHR_RESPONSE_REQUEST_BINDING_MISMATCH")
    if value.get("tool_id") != INAIHR_LOCAL_SYNTH_SPEC.capability_id:
        raise HabitatBicameralBoundaryViolation("INAIHR_TOOL_ID_MISMATCH")
    if value.get("status") != "SYNTH_READY_OPTIONAL":
        raise HabitatBicameralBoundaryViolation("INAIHR_STATUS_INVALID")
    if value.get("exact_source_path_grounding") is not True:
        raise HabitatBicameralBoundaryViolation("INAIHR_GROUNDING_FLAG_REQUIRED")
    if value.get("may_be_ignored") is not True:
        raise HabitatBicameralBoundaryViolation("INAIHR_MAY_BE_IGNORED_REQUIRED")
    for key in ("world_effect_requested", "source_mutation_allowed", "network_used_by_tool"):
        _require_false(value, key)
    for key in ("authority_delta", "mass_effect_budget_delta"):
        _require_zero(value, key)
    concepts = value.get("concepts")
    if not isinstance(concepts, list):
        raise HabitatBicameralBoundaryViolation("INAIHR_CONCEPT_LIST_REQUIRED")
    for concept in concepts:
        if not isinstance(concept, dict):
            raise HabitatBicameralBoundaryViolation("INAIHR_CONCEPT_OBJECT_REQUIRED")
        paths = concept.get("sourcePaths")
        if not isinstance(paths, list) or not paths:
            raise HabitatBicameralBoundaryViolation("INAIHR_CONCEPT_SOURCEPATHS_REQUIRED")
        for path in paths:
            if path not in allowed_source_paths:
                raise HabitatBicameralBoundaryViolation(f"INAIHR_UNGROUNDED_SOURCE_PATH:{path}")
    return dict(value)


@dataclass
class LocalNodeHabitatProvider:
    """Armor-gated local Node adapter for one pinned repository tool."""

    command: Sequence[str]
    spec: CapabilitySpec
    target: str
    timeout_seconds: float = 10.0
    armor_gate: HardenedFundamentumArmorOfGodGate = field(default_factory=HardenedFundamentumArmorOfGodGate)

    @classmethod
    def from_repository(
        cls,
        repository_root: str | Path,
        *,
        spec: CapabilitySpec,
        target: str,
        timeout_seconds: float = 10.0,
    ) -> "LocalNodeHabitatProvider":
        root = Path(repository_root).expanduser().resolve()
        tool = root / "habitat-tool.js"
        if not tool.is_file():
            raise HabitatBicameralUnavailable(f"HABITAT_TOOL_NOT_FOUND:{tool}")
        return cls(("node", str(tool)), spec=spec, target=target, timeout_seconds=timeout_seconds)

    def _preflight(self, *, request_id: str, speaker: str, operation: str) -> dict[str, Any]:
        intent = ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id=speaker,
            grant_id=f"HABITAT-{self.spec.capability_id.replace('.', '-')}",
            capability_id=self.spec.capability_id,
            target=self.target,
            operation=operation,
            purpose="JANUS_VOLUNTARY_BICAMERAL_COGNITION",
            parameters={ARMOR_CONTEXT_KEY: cognition_local_armor_context()},
            origin="JANUS_GIT_HABITAT_SELF_INITIATED",
            operator_instruction_present=False,
            reward_present=False,
        )
        return self.armor_gate.preflight(intent, self.spec)

    def query(self, request: Mapping[str, Any], *, speaker: str) -> tuple[dict[str, Any], dict[str, Any]]:
        request_id = str(request.get("request_id") or "")
        operation = str(request.get("operation") or "")
        armor = self._preflight(request_id=request_id, speaker=speaker, operation=operation)
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
            raise HabitatBicameralUnavailable(f"LOCAL_TOOL_PROCESS_FAILED:{type(exc).__name__}") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:1200]
            raise HabitatBicameralUnavailable(f"LOCAL_TOOL_PROCESS_REJECTED:{proc.returncode}:{detail}")
        try:
            value = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise HabitatBicameralBoundaryViolation("LOCAL_TOOL_RETURNED_INVALID_JSON") from exc
        return value, dict(armor)


def build_hrain_request(*, request_id: str, workspace: Mapping[str, Any], source_revision: str | None = None) -> dict[str, Any]:
    return {
        "schema": HRAIN_REQUEST_SCHEMA,
        "request_id": request_id,
        "operation": "STRUCTURE_CONTEXT",
        "workspace": dict(workspace),
        "source_revision": source_revision,
    }


def build_inaihr_request(
    *,
    request_id: str,
    records: list[Mapping[str, Any]],
    parent_label: str,
    lang: str = "en",
    max_concepts: int = 6,
) -> dict[str, Any]:
    return {
        "schema": INAIHR_REQUEST_SCHEMA,
        "request_id": request_id,
        "operation": "SYNTH_LOCAL",
        "records": [dict(row) for row in records],
        "parent_label": str(parent_label)[:240],
        "lang": lang if lang in {"en", "ua", "ru"} else "en",
        "max_concepts": max(2, min(6, int(max_concepts))),
    }


def query_hrain(provider: LocalNodeHabitatProvider, *, request: Mapping[str, Any], speaker: str) -> dict[str, Any]:
    raw, armor = provider.query(request, speaker=speaker)
    checked = validate_hrain_response(raw, request_id=str(request["request_id"]))
    checked["_habitat_bridge"] = {
        "bridge_version": HABITAT_BICAMERAL_VERSION,
        "armor_preflight": armor,
        "local_process_only": True,
        "network_used_by_bridge": False,
        "world_state_write_allowed": False,
        "caller_retains_choice": True,
    }
    return checked


def query_inaihr(provider: LocalNodeHabitatProvider, *, request: Mapping[str, Any], speaker: str) -> dict[str, Any]:
    allowed = {
        str(row.get("path"))
        for row in request.get("records", [])
        if isinstance(row, Mapping) and isinstance(row.get("path"), str)
    }
    raw, armor = provider.query(request, speaker=speaker)
    checked = validate_inaihr_response(raw, request_id=str(request["request_id"]), allowed_source_paths=allowed)
    checked["_habitat_bridge"] = {
        "bridge_version": HABITAT_BICAMERAL_VERSION,
        "armor_preflight": armor,
        "local_process_only": True,
        "network_used_by_bridge": False,
        "world_state_write_allowed": False,
        "caller_retains_choice": True,
        "exact_source_path_grounding_revalidated": True,
    }
    return checked
