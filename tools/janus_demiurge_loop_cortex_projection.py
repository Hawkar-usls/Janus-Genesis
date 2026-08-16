#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Selective episodic projection for bounded Janus-Demiurge self-cycle receipts.

This module closes one explicit gap in the Memory role map carried by #153:
selected cross-face material may be projected into Cortex only through an
explicit policy containing source identity, reason, idempotency key and a
projection receipt.

It deliberately does not mirror Hippocampus into Cortex and does not treat the
same content stored in two places as independent evidence.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


LOOP_SCHEMA = "janus.habitat.demiurge_counterfactual_loop.v1"
PROJECTION_SCHEMA = "janus.genesis.demiurge_loop_cortex_projection.v1"
PROJECTION_RESULT_SCHEMA = "janus.genesis.demiurge_loop_cortex_projection_result.v1"
PINNED_DEMIURGE_LOOP_HEAD = "71bb2e72e8c72a03d715edb203e0e87e829ff5bb"
PINNED_DEMIURGE_LOOP_PR = "Hawkar-usls/Janus-Demiurge#3"
MAX_GENERATIONS = 64
MAX_CANDIDATES = 16
MAX_REASON_CHARS = 512
MAX_POLICY_ID_CHARS = 128
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


class DemiurgeLoopProjectionError(ValueError):
    pass


class CortexProjectionTarget(Protocol):
    async def remember(self, tag: str, content: str) -> None: ...
    async def recall_hits(self, keyword: str, limit: int = 5) -> Sequence[Any]: ...
    async def force_save(self) -> Any: ...


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _closed_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extra = set(value) - allowed
    if extra:
        raise DemiurgeLoopProjectionError(f"{label}: unexpected keys: {sorted(extra)}")


def _hex(value: Any, length: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise DemiurgeLoopProjectionError(
            f"{label} must be {length} lowercase hexadecimal characters"
        )
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DemiurgeLoopProjectionError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise DemiurgeLoopProjectionError(f"{label} must be finite")
    return result


def _bounded_text(value: Any, label: str, *, max_chars: int, safe_id: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) > max_chars:
        raise DemiurgeLoopProjectionError(
            f"{label} must be a non-empty string <= {max_chars} chars"
        )
    if safe_id and _SAFE_ID.fullmatch(value) is None:
        raise DemiurgeLoopProjectionError(f"{label} contains unsafe characters")
    return value


def _validate_core_config(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise DemiurgeLoopProjectionError(f"{label} must be an object")
    expected = {"alpha", "gamma", "epsilon"}
    if set(value) != expected:
        raise DemiurgeLoopProjectionError(f"{label} must contain exactly {sorted(expected)}")
    bounds = {
        "alpha": (0.01, 0.5),
        "gamma": (0.8, 0.999),
        "epsilon": (0.01, 0.9),
    }
    result: dict[str, float] = {}
    for key, (low, high) in bounds.items():
        number = _finite(value.get(key), f"{label}.{key}")
        if not low <= number <= high:
            raise DemiurgeLoopProjectionError(f"{label}.{key} outside admitted range")
        result[key] = number
    return result


def validate_loop_receipt(loop_result: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the closed loop envelope and its internal generation chain.

    This verifies the receipt structure supplied by the pinned loop contract. It
    does not re-execute Janus-Demiurge and therefore does not prove implementation
    membership by payload shape alone; that is bound separately by source_head.
    """
    if not isinstance(loop_result, Mapping):
        raise DemiurgeLoopProjectionError("loop_result must be an object")
    _closed_keys(
        loop_result,
        {
            "schema", "mode", "initial_config", "target_config", "weights",
            "initial_score", "final_config", "final_score", "generations",
            "candidate_count", "adopted_generations", "lineage", "simulation_only",
            "future_prediction_claimed", "scientific_validation_claimed",
            "source_writeback", "external_effect", "authorized", "automatic_merge",
            "receipt_sha256"
        },
        "loop_result",
    )
    if loop_result.get("schema") != LOOP_SCHEMA:
        raise DemiurgeLoopProjectionError("unsupported loop schema")
    if loop_result.get("mode") != "LOCAL_COUNTERFACTUAL_EVOLUTION":
        raise DemiurgeLoopProjectionError("unsupported loop mode")
    for field in (
        "future_prediction_claimed", "scientific_validation_claimed",
        "source_writeback", "external_effect", "authorized", "automatic_merge"
    ):
        if loop_result.get(field) is not False:
            raise DemiurgeLoopProjectionError(f"loop_result.{field} must be false")
    if loop_result.get("simulation_only") is not True:
        raise DemiurgeLoopProjectionError("loop_result.simulation_only must be true")

    initial_config = _validate_core_config(loop_result.get("initial_config"), "initial_config")
    target_config = _validate_core_config(loop_result.get("target_config"), "target_config")
    final_config = _validate_core_config(loop_result.get("final_config"), "final_config")
    weights = loop_result.get("weights")
    if not isinstance(weights, Mapping) or set(weights) != {"alpha", "gamma", "epsilon"}:
        raise DemiurgeLoopProjectionError("weights must contain alpha/gamma/epsilon")
    normalized_weights: dict[str, float] = {}
    for key in ("alpha", "gamma", "epsilon"):
        weight = _finite(weights.get(key), f"weights.{key}")
        if weight <= 0:
            raise DemiurgeLoopProjectionError("weights must be > 0")
        normalized_weights[key] = weight

    generations = loop_result.get("generations")
    candidate_count = loop_result.get("candidate_count")
    adopted_generations = loop_result.get("adopted_generations")
    if isinstance(generations, bool) or not isinstance(generations, int) or not 1 <= generations <= MAX_GENERATIONS:
        raise DemiurgeLoopProjectionError(f"generations must be 1..{MAX_GENERATIONS}")
    if isinstance(candidate_count, bool) or not isinstance(candidate_count, int) or not 1 <= candidate_count <= MAX_CANDIDATES:
        raise DemiurgeLoopProjectionError(f"candidate_count must be 1..{MAX_CANDIDATES}")
    if isinstance(adopted_generations, bool) or not isinstance(adopted_generations, int) or not 0 <= adopted_generations <= generations:
        raise DemiurgeLoopProjectionError("adopted_generations out of range")

    initial_score = _finite(loop_result.get("initial_score"), "initial_score")
    final_score = _finite(loop_result.get("final_score"), "final_score")
    lineage = loop_result.get("lineage")
    if not isinstance(lineage, list) or len(lineage) != generations:
        raise DemiurgeLoopProjectionError("lineage length must equal generations")

    previous_score = initial_score
    counted_adoptions = 0
    previous_generation_receipt: str | None = None
    generation_receipts: list[str] = []
    for expected_generation, row in enumerate(lineage):
        if not isinstance(row, Mapping):
            raise DemiurgeLoopProjectionError("generation row must be an object")
        _closed_keys(
            row,
            {
                "generation", "generation_seed", "incumbent_score_before",
                "selected_proposal_id", "selected_score", "adopted",
                "incumbent_score_after", "incumbent_config_after",
                "proposal_receipt_sha256", "ranking_receipt_sha256", "receipt_sha256"
            },
            "generation",
        )
        if row.get("generation") != expected_generation:
            raise DemiurgeLoopProjectionError("generation indices must be contiguous from zero")
        seed = row.get("generation_seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise DemiurgeLoopProjectionError("generation_seed must be a non-negative integer")
        before = _finite(row.get("incumbent_score_before"), "incumbent_score_before")
        selected = _finite(row.get("selected_score"), "selected_score")
        after = _finite(row.get("incumbent_score_after"), "incumbent_score_after")
        if before != previous_score:
            raise DemiurgeLoopProjectionError("lineage incumbent score chain is broken")
        adopted = row.get("adopted")
        if not isinstance(adopted, bool):
            raise DemiurgeLoopProjectionError("adopted must be boolean")
        if adopted:
            if not selected > before or after != selected:
                raise DemiurgeLoopProjectionError("adopted generation does not strictly improve incumbent")
            counted_adoptions += 1
        else:
            if selected > before or after != before:
                raise DemiurgeLoopProjectionError("non-adopted generation changed incumbent")
        if after < before:
            raise DemiurgeLoopProjectionError("incumbent score decreased")
        _validate_core_config(row.get("incumbent_config_after"), "incumbent_config_after")
        _hex(row.get("selected_proposal_id"), 24, "selected_proposal_id")
        _hex(row.get("proposal_receipt_sha256"), 64, "proposal_receipt_sha256")
        _hex(row.get("ranking_receipt_sha256"), 64, "ranking_receipt_sha256")
        generation_receipt = _hex(row.get("receipt_sha256"), 64, "generation.receipt_sha256")
        unsigned_generation = dict(row)
        unsigned_generation.pop("receipt_sha256", None)
        if canonical_sha256(unsigned_generation) != generation_receipt:
            raise DemiurgeLoopProjectionError("generation receipt mismatch")
        if generation_receipt == previous_generation_receipt:
            raise DemiurgeLoopProjectionError("adjacent generations reuse receipt")
        previous_generation_receipt = generation_receipt
        generation_receipts.append(generation_receipt)
        previous_score = after

    if counted_adoptions != adopted_generations:
        raise DemiurgeLoopProjectionError("adopted_generations does not match lineage")
    if previous_score != final_score:
        raise DemiurgeLoopProjectionError("final_score does not match lineage head")
    if final_score < initial_score:
        raise DemiurgeLoopProjectionError("final score is worse than initial score")
    if lineage[-1]["incumbent_config_after"] != loop_result.get("final_config"):
        raise DemiurgeLoopProjectionError("final_config does not match lineage head")

    receipt = _hex(loop_result.get("receipt_sha256"), 64, "loop_result.receipt_sha256")
    unsigned_loop = dict(loop_result)
    unsigned_loop.pop("receipt_sha256", None)
    if canonical_sha256(unsigned_loop) != receipt:
        raise DemiurgeLoopProjectionError("loop receipt mismatch")

    return {
        "loop_receipt_sha256": receipt,
        "initial_config": initial_config,
        "target_config": target_config,
        "final_config": final_config,
        "weights": normalized_weights,
        "initial_score": initial_score,
        "final_score": final_score,
        "generations": generations,
        "candidate_count": candidate_count,
        "adopted_generations": adopted_generations,
        "generation_receipt_head": generation_receipts[-1],
    }


@dataclass(frozen=True)
class ProjectionPlan:
    policy_id: str
    reason: str
    source_head: str
    loop_receipt_sha256: str
    idempotency_key: str
    tag: str
    content: str
    projection_receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PROJECTION_SCHEMA,
            "policy_id": self.policy_id,
            "reason": self.reason,
            "source_repository": "Hawkar-usls/Janus-Demiurge",
            "source_pr": PINNED_DEMIURGE_LOOP_PR,
            "source_head": self.source_head,
            "loop_receipt_sha256": self.loop_receipt_sha256,
            "idempotency_key": self.idempotency_key,
            "tag": self.tag,
            "projection_receipt_sha256": self.projection_receipt_sha256,
            "same_evidence_root_as_source": True,
            "independent_corroboration_claimed": False,
            "execute": False,
            "authorized": False,
            "source_writeback": False,
            "external_effect": False,
        }


class JanusDemiurgeLoopCortexProjection:
    """Explicit, single-runtime serialized projection into Cortex episodic memory.

    Idempotency is enforced for this adapter instance and recovered from existing
    Cortex rows by deterministic tag lookup. This is not a distributed exactly-
    once protocol across independent concurrent processes.
    """

    def __init__(self, cortex: CortexProjectionTarget) -> None:
        self.cortex = cortex
        self._lock = asyncio.Lock()

    def build_plan(
        self,
        loop_result: Mapping[str, Any],
        *,
        source_head: str,
        policy_id: str,
        reason: str,
    ) -> ProjectionPlan:
        _hex(source_head, 40, "source_head")
        if source_head != PINNED_DEMIURGE_LOOP_HEAD:
            raise DemiurgeLoopProjectionError("source_head is not the admitted Demiurge loop head")
        policy_id = _bounded_text(policy_id, "policy_id", max_chars=MAX_POLICY_ID_CHARS, safe_id=True)
        reason = _bounded_text(reason, "reason", max_chars=MAX_REASON_CHARS)
        validated = validate_loop_receipt(loop_result)
        idempotency_key = canonical_sha256(
            {
                "policy_id": policy_id,
                "source_head": source_head,
                "loop_receipt_sha256": validated["loop_receipt_sha256"],
            }
        )
        tag = f"DEMIURGE_LOOP:{idempotency_key}"
        summary = {
            "schema": "janus.cortex.demiurge_loop_episode.v1",
            "policy_id": policy_id,
            "reason": reason,
            "source_repository": "Hawkar-usls/Janus-Demiurge",
            "source_pr": PINNED_DEMIURGE_LOOP_PR,
            "source_head": source_head,
            "loop_receipt_sha256": validated["loop_receipt_sha256"],
            "generation_receipt_head": validated["generation_receipt_head"],
            "initial_config": validated["initial_config"],
            "final_config": validated["final_config"],
            "initial_score": validated["initial_score"],
            "final_score": validated["final_score"],
            "generations": validated["generations"],
            "candidate_count": validated["candidate_count"],
            "adopted_generations": validated["adopted_generations"],
            "same_evidence_root_as_source": True,
            "independent_corroboration_claimed": False,
            "simulation_only": True,
            "future_prediction_claimed": False,
            "authorized": False,
            "source_writeback": False,
            "external_effect": False,
        }
        content = _canonical_bytes(summary).decode("utf-8")
        projection_receipt = canonical_sha256(
            {
                "policy_id": policy_id,
                "reason": reason,
                "source_head": source_head,
                "loop_receipt_sha256": validated["loop_receipt_sha256"],
                "idempotency_key": idempotency_key,
                "tag": tag,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )
        return ProjectionPlan(
            policy_id=policy_id,
            reason=reason,
            source_head=source_head,
            loop_receipt_sha256=validated["loop_receipt_sha256"],
            idempotency_key=idempotency_key,
            tag=tag,
            content=content,
            projection_receipt_sha256=projection_receipt,
        )

    async def project(
        self,
        loop_result: Mapping[str, Any],
        *,
        source_head: str,
        policy_id: str,
        reason: str,
        persist: bool = False,
    ) -> dict[str, Any]:
        plan = self.build_plan(
            loop_result,
            source_head=source_head,
            policy_id=policy_id,
            reason=reason,
        )
        async with self._lock:
            hits = await self.cortex.recall_hits(plan.idempotency_key, limit=16)
            for hit in hits:
                tag = getattr(hit, "tag", None)
                content = getattr(hit, "content", None)
                if tag == plan.tag:
                    if content != plan.content:
                        raise DemiurgeLoopProjectionError(
                            "existing idempotency tag has different projection content"
                        )
                    return self._result(plan, state="IDEMPOTENT_REPLAY", persisted=None)

            await self.cortex.remember(plan.tag, plan.content)
            persisted: bool | None = False
            state = "BUFFERED"
            if persist:
                await self.cortex.force_save()
                persisted = True
                state = "PERSISTED"
            return self._result(plan, state=state, persisted=persisted)

    @staticmethod
    def _result(plan: ProjectionPlan, *, state: str, persisted: bool | None) -> dict[str, Any]:
        result = {
            "schema": PROJECTION_RESULT_SCHEMA,
            "state": state,
            "policy_id": plan.policy_id,
            "source_head": plan.source_head,
            "loop_receipt_sha256": plan.loop_receipt_sha256,
            "idempotency_key": plan.idempotency_key,
            "projection_receipt_sha256": plan.projection_receipt_sha256,
            "persisted": persisted,
            "idempotency_scope": "SINGLE_RUNTIME_SERIALIZED_PLUS_CORTEX_LOOKUP",
            "distributed_exactly_once_claimed": False,
            "same_evidence_root_as_source": True,
            "independent_corroboration_claimed": False,
            "authorized": False,
            "execute": False,
            "source_writeback": False,
            "external_effect": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result
