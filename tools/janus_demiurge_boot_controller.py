#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boot/runtime controller for the bounded JANUS Demiurge laboratory.

The controller closes the manual "continue" gap inside one explicitly admitted
objective:

    durable objective
      -> recover latest durable checkpoint if present
      -> run/resume injected local supervisor
      -> force-save returned checkpoint through Hippocampus
      -> repeat until WAIT or controller budget

The supervisor implementation is dependency-injected; this module never imports
or executes code from a Janus-Demiurge checkout by path. Exact implementation
membership remains an external admission fact, while the source head is pinned
in every durable objective/checkpoint record.

No objective is self-generated and no external action is authorized.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from tools.janus_demiurge_supervisor_checkpoint_journal import (
    PINNED_SUPERVISOR_HEAD,
    JanusDemiurgeSupervisorCheckpointJournal,
    OperationalJournal,
    SupervisorCheckpointJournalError,
    canonical_sha256,
    validate_checkpoint,
)


OBJECTIVE_RECORD_SCHEMA = "janus.genesis.demiurge_admitted_objective.v1"
OBJECTIVE_RESULT_SCHEMA = "janus.genesis.demiurge_objective_persistence_result.v1"
CONTROLLER_SCHEMA = "janus.genesis.demiurge_boot_controller.v1"
SUPERVISOR_RESULT_SCHEMA = "janus.habitat.demiurge_lab_supervisor.v1"
OBJECTIVE_SOURCE = "JANUS_DEMIURGE_ADMITTED_OBJECTIVE"
DEFAULT_OBJECTIVE_POLICY = "DEMIURGE_ADMITTED_OBJECTIVE_V1"
DEFAULT_CHECKPOINT_POLICY = "DEMIURGE_SUPERVISOR_CHECKPOINT_V1"
MAX_CONTROLLER_SEGMENTS = 64
MAX_SEGMENT_WINDOWS = 64
MAX_GENERATIONS_PER_WINDOW = 64
MAX_CANDIDATES = 16
MAX_PATIENCE_WINDOWS = 16
MAX_OBJECTIVE_ID_CHARS = 128
MAX_POLICY_ID_CHARS = 128
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")
_BOUNDS = {
    "alpha": (0.01, 0.5),
    "gamma": (0.8, 0.999),
    "epsilon": (0.01, 0.9),
}


class DemiurgeBootControllerError(ValueError):
    pass


class DemiurgeSupervisorPort(Protocol):
    def run_objective(
        self,
        *,
        objective_id: str,
        base_config: Mapping[str, Any],
        target_config: Mapping[str, Any],
        root_seed: int,
        generation_window: int,
        max_windows: int,
        candidate_count: int,
        patience_windows: int,
        min_window_improvement: float,
        weights: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]: ...

    def resume_from_checkpoint(
        self,
        checkpoint: Mapping[str, Any],
        *,
        additional_windows: int,
    ) -> Mapping[str, Any]: ...


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _closed_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    extra = set(value) - allowed
    if extra:
        raise DemiurgeBootControllerError(
            f"{label}: unexpected keys: {sorted(extra)}"
        )


def _safe_id(value: Any, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or _SAFE_ID.fullmatch(value) is None
    ):
        raise DemiurgeBootControllerError(
            f"{label} must match {_SAFE_ID.pattern} and be <= {maximum} chars"
        )
    return value


def _hex(value: Any, length: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise DemiurgeBootControllerError(
            f"{label} must be {length} lowercase hex chars"
        )
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DemiurgeBootControllerError(f"{label} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise DemiurgeBootControllerError(f"{label} must be finite")
    return result


def _positive_int(value: Any, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise DemiurgeBootControllerError(f"{label} must be 1..{maximum}")
    return value


def _core_config(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(_BOUNDS):
        raise DemiurgeBootControllerError(
            f"{label} must contain exactly {sorted(_BOUNDS)}"
        )
    out: dict[str, float] = {}
    for key, (low, high) in _BOUNDS.items():
        number = _finite(value.get(key), f"{label}.{key}")
        if not low <= number <= high:
            raise DemiurgeBootControllerError(
                f"{label}.{key} outside admitted range"
            )
        out[key] = number
    return out


def _weights(value: Any) -> dict[str, float]:
    if value is None:
        return {key: 1.0 for key in _BOUNDS}
    if not isinstance(value, Mapping) or set(value) != set(_BOUNDS):
        raise DemiurgeBootControllerError(
            "weights must contain exactly alpha/gamma/epsilon"
        )
    out: dict[str, float] = {}
    for key in _BOUNDS:
        number = _finite(value.get(key), f"weights.{key}")
        if number <= 0:
            raise DemiurgeBootControllerError("weights must be > 0")
        out[key] = number
    return out


def _validate_objective_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DemiurgeBootControllerError("objective payload must be an object")
    expected = {
        "objective_id", "supervisor_source_head", "base_config", "target_config",
        "root_seed", "generation_window", "segment_windows", "candidate_count",
        "patience_windows", "min_window_improvement", "weights"
    }
    if set(payload) != expected:
        raise DemiurgeBootControllerError("objective payload schema is not closed")
    objective_id = _safe_id(
        payload.get("objective_id"), "objective_id", MAX_OBJECTIVE_ID_CHARS
    )
    source_head = _hex(
        payload.get("supervisor_source_head"), 40, "supervisor_source_head"
    )
    if source_head != PINNED_SUPERVISOR_HEAD:
        raise DemiurgeBootControllerError(
            "supervisor_source_head is not the admitted supervisor head"
        )
    base = _core_config(payload.get("base_config"), "base_config")
    target = _core_config(payload.get("target_config"), "target_config")
    root_seed = payload.get("root_seed")
    if isinstance(root_seed, bool) or not isinstance(root_seed, int):
        raise DemiurgeBootControllerError("root_seed must be an integer")
    generation_window = _positive_int(
        payload.get("generation_window"),
        "generation_window",
        MAX_GENERATIONS_PER_WINDOW,
    )
    segment_windows = _positive_int(
        payload.get("segment_windows"), "segment_windows", MAX_SEGMENT_WINDOWS
    )
    candidate_count = _positive_int(
        payload.get("candidate_count"), "candidate_count", MAX_CANDIDATES
    )
    patience_windows = _positive_int(
        payload.get("patience_windows"),
        "patience_windows",
        MAX_PATIENCE_WINDOWS,
    )
    min_improvement = _finite(
        payload.get("min_window_improvement"), "min_window_improvement"
    )
    if min_improvement < 0:
        raise DemiurgeBootControllerError(
            "min_window_improvement must be >= 0"
        )
    normalized_weights = _weights(payload.get("weights"))
    return {
        "objective_id": objective_id,
        "supervisor_source_head": source_head,
        "base_config": base,
        "target_config": target,
        "root_seed": root_seed,
        "generation_window": generation_window,
        "segment_windows": segment_windows,
        "candidate_count": candidate_count,
        "patience_windows": patience_windows,
        "min_window_improvement": min_improvement,
        "weights": normalized_weights,
    }


def _objective_lookup_key(policy_id: str, objective_id: str, source_head: str) -> str:
    return canonical_sha256(
        {
            "policy_id": policy_id,
            "objective_id": objective_id,
            "supervisor_source_head": source_head,
        }
    )


@dataclass(frozen=True)
class DurableObjectiveStore:
    journal: OperationalJournal

    async def persist(
        self,
        objective: Mapping[str, Any],
        *,
        policy_id: str = DEFAULT_OBJECTIVE_POLICY,
    ) -> dict[str, Any]:
        validated = _validate_objective_payload(objective)
        policy_id = _safe_id(policy_id, "policy_id", MAX_POLICY_ID_CHARS)
        lookup = _objective_lookup_key(
            policy_id,
            validated["objective_id"],
            validated["supervisor_source_head"],
        )
        envelope = {
            "schema": OBJECTIVE_RECORD_SCHEMA,
            "policy_id": policy_id,
            "objective_lookup_key": lookup,
            "objective": validated,
            "admitted": True,
            "self_generated": False,
            "authorized_external_action": False,
            "source_writeback": False,
        }
        envelope["record_receipt_sha256"] = canonical_sha256(envelope)
        content = _canonical_bytes(envelope).decode("utf-8")

        prior = await self._records_for_lookup(lookup, persisted_only=False)
        if prior:
            unique = {item["content"] for item in prior}
            if unique != {content}:
                raise DemiurgeBootControllerError(
                    "HOLD_RECONCILE: objective_id already bound to different durable objective"
                )
            if not all(item["origin"] == "HDD" for item in prior):
                await self.journal.force_save()
            verified = await self._records_for_lookup(lookup, persisted_only=True)
            if not verified:
                raise DemiurgeBootControllerError(
                    "objective replay could not be verified from HDD"
                )
            return await self._persistence_result(
                validated, policy_id, lookup, envelope["record_receipt_sha256"],
                state="IDEMPOTENT_PERSISTED_REPLAY",
            )

        await self.journal.remember(source=OBJECTIVE_SOURCE, content=content)
        await self.journal.force_save()
        verified = await self._records_for_lookup(lookup, persisted_only=True)
        if len(verified) != 1 or verified[0]["content"] != content:
            raise DemiurgeBootControllerError(
                "objective commit could not be verified from HDD"
            )
        return await self._persistence_result(
            validated, policy_id, lookup, envelope["record_receipt_sha256"],
            state="PERSISTED",
        )

    async def recover(
        self,
        objective_id: str,
        *,
        source_head: str = PINNED_SUPERVISOR_HEAD,
        policy_id: str = DEFAULT_OBJECTIVE_POLICY,
    ) -> dict[str, Any] | None:
        objective_id = _safe_id(
            objective_id, "objective_id", MAX_OBJECTIVE_ID_CHARS
        )
        source_head = _hex(source_head, 40, "source_head")
        if source_head != PINNED_SUPERVISOR_HEAD:
            raise DemiurgeBootControllerError("source_head is not admitted")
        policy_id = _safe_id(policy_id, "policy_id", MAX_POLICY_ID_CHARS)
        lookup = _objective_lookup_key(policy_id, objective_id, source_head)
        records = await self._records_for_lookup(lookup, persisted_only=True)
        if not records:
            return None
        parsed = [self._parse_record(item["content"]) for item in records]
        receipts = {item["record_receipt_sha256"] for item in parsed}
        objectives = {
            _canonical_bytes(item["objective"]).decode("utf-8") for item in parsed
        }
        if len(receipts) != 1 or len(objectives) != 1:
            raise DemiurgeBootControllerError(
                "HOLD_RECONCILE: conflicting durable objective records"
            )
        return dict(parsed[0]["objective"])

    async def _records_for_lookup(
        self, lookup: str, *, persisted_only: bool
    ) -> list[Mapping[str, Any]]:
        hits = await self.journal.recall(lookup, limit=64)
        result: list[Mapping[str, Any]] = []
        for hit in hits:
            if persisted_only and hit.get("origin") != "HDD":
                continue
            if hit.get("source") != OBJECTIVE_SOURCE:
                continue
            try:
                parsed = self._parse_record(hit.get("content"))
            except DemiurgeBootControllerError:
                continue
            if parsed["objective_lookup_key"] == lookup:
                result.append(hit)
        return result

    @staticmethod
    def _parse_record(content: Any) -> dict[str, Any]:
        if not isinstance(content, str):
            raise DemiurgeBootControllerError("objective record is not text")
        try:
            value = json.loads(content)
        except (TypeError, ValueError) as exc:
            raise DemiurgeBootControllerError("objective record is invalid JSON") from exc
        if not isinstance(value, Mapping):
            raise DemiurgeBootControllerError("objective record must be an object")
        expected = {
            "schema", "policy_id", "objective_lookup_key", "objective",
            "admitted", "self_generated", "authorized_external_action",
            "source_writeback", "record_receipt_sha256"
        }
        _closed_keys(value, expected, "objective record")
        if value.get("schema") != OBJECTIVE_RECORD_SCHEMA:
            raise DemiurgeBootControllerError("objective record schema mismatch")
        if value.get("admitted") is not True:
            raise DemiurgeBootControllerError("objective record is not admitted")
        if value.get("self_generated") is not False:
            raise DemiurgeBootControllerError("objective record self-generated flag invalid")
        if value.get("authorized_external_action") is not False:
            raise DemiurgeBootControllerError("objective record external action flag invalid")
        if value.get("source_writeback") is not False:
            raise DemiurgeBootControllerError("objective record writeback flag invalid")
        receipt = _hex(
            value.get("record_receipt_sha256"), 64, "objective record receipt"
        )
        unsigned = dict(value)
        unsigned.pop("record_receipt_sha256", None)
        if canonical_sha256(unsigned) != receipt:
            raise DemiurgeBootControllerError("objective record receipt mismatch")
        policy_id = _safe_id(
            value.get("policy_id"), "record policy_id", MAX_POLICY_ID_CHARS
        )
        objective = _validate_objective_payload(value.get("objective"))
        lookup = _hex(
            value.get("objective_lookup_key"), 64, "objective_lookup_key"
        )
        expected_lookup = _objective_lookup_key(
            policy_id,
            objective["objective_id"],
            objective["supervisor_source_head"],
        )
        if lookup != expected_lookup:
            raise DemiurgeBootControllerError("objective lookup key mismatch")
        return {
            **dict(value),
            "objective": objective,
            "record_receipt_sha256": receipt,
        }

    async def _persistence_result(
        self,
        objective: Mapping[str, Any],
        policy_id: str,
        lookup: str,
        record_receipt: str,
        *,
        state: str,
    ) -> dict[str, Any]:
        stats = await self.journal.stats()
        result = {
            "schema": OBJECTIVE_RESULT_SCHEMA,
            "state": state,
            "objective_id": objective["objective_id"],
            "policy_id": policy_id,
            "objective_lookup_key": lookup,
            "record_receipt_sha256": record_receipt,
            "sqlite_transaction_committed": True,
            "journal_synchronous": stats.get("synchronous"),
            "process_restart_recovery_after_commit": True,
            "backup_claimed": False,
            "replication_claimed": False,
            "power_loss_proof_claimed": False,
            "authorized_external_action": False,
            "source_writeback": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result


class JanusDemiurgeBootController:
    """Run a durable admitted local objective until a supervisor WAIT state.

    ``supervisor`` is injected by the local runtime. The controller cannot
    dynamically import, install, fetch, or execute a remote repository.
    """

    def __init__(
        self,
        *,
        journal: OperationalJournal,
        checkpoint_store: JanusDemiurgeSupervisorCheckpointJournal,
        supervisor: DemiurgeSupervisorPort,
        supervisor_source_head: str = PINNED_SUPERVISOR_HEAD,
    ) -> None:
        self.journal = journal
        self.objectives = DurableObjectiveStore(journal)
        self.checkpoints = checkpoint_store
        self.supervisor = supervisor
        self.supervisor_source_head = _hex(
            supervisor_source_head, 40, "supervisor_source_head"
        )
        if self.supervisor_source_head != PINNED_SUPERVISOR_HEAD:
            raise DemiurgeBootControllerError(
                "supervisor_source_head is not the admitted supervisor head"
            )

    async def register_objective(
        self,
        *,
        objective_id: str,
        base_config: Mapping[str, Any],
        target_config: Mapping[str, Any],
        root_seed: int,
        generation_window: int = 16,
        segment_windows: int = 16,
        candidate_count: int = 8,
        patience_windows: int = 2,
        min_window_improvement: float = 0.0,
        weights: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        objective = {
            "objective_id": objective_id,
            "supervisor_source_head": self.supervisor_source_head,
            "base_config": dict(base_config),
            "target_config": dict(target_config),
            "root_seed": root_seed,
            "generation_window": generation_window,
            "segment_windows": segment_windows,
            "candidate_count": candidate_count,
            "patience_windows": patience_windows,
            "min_window_improvement": min_window_improvement,
            "weights": dict(weights) if weights is not None else None,
        }
        return await self.objectives.persist(objective)

    async def run_registered_objective(
        self,
        objective_id: str,
        *,
        max_segments: int = 16,
    ) -> dict[str, Any]:
        max_segments = _positive_int(
            max_segments, "max_segments", MAX_CONTROLLER_SEGMENTS
        )
        objective = await self.objectives.recover(
            objective_id, source_head=self.supervisor_source_head
        )
        if objective is None:
            return self._controller_result(
                state="WAIT_NO_DURABLE_OBJECTIVE",
                objective_id=objective_id,
                segments_executed=0,
                checkpoint=None,
                recovered_checkpoint=False,
            )

        recovered = await self.checkpoints.recover_latest(
            objective_id=objective["objective_id"],
            source_head=self.supervisor_source_head,
            policy_id=DEFAULT_CHECKPOINT_POLICY,
        )
        checkpoint = recovered.get("checkpoint") if recovered.get("state") == "RECOVERED" else None
        recovered_checkpoint = checkpoint is not None

        if checkpoint is not None and checkpoint.get("state") in {
            "WAIT_FIXED_POINT", "WAIT_PLATEAU"
        }:
            return self._controller_result(
                state=checkpoint["state"],
                objective_id=objective["objective_id"],
                segments_executed=0,
                checkpoint=checkpoint,
                recovered_checkpoint=True,
            )

        segments = 0
        latest_checkpoint = checkpoint
        while segments < max_segments:
            if latest_checkpoint is None:
                raw_result = self.supervisor.run_objective(
                    objective_id=objective["objective_id"],
                    base_config=objective["base_config"],
                    target_config=objective["target_config"],
                    root_seed=objective["root_seed"],
                    generation_window=objective["generation_window"],
                    max_windows=objective["segment_windows"],
                    candidate_count=objective["candidate_count"],
                    patience_windows=objective["patience_windows"],
                    min_window_improvement=objective["min_window_improvement"],
                    weights=objective["weights"],
                )
            else:
                if latest_checkpoint.get("state") != "BUDGET_EXHAUSTED":
                    raise DemiurgeBootControllerError(
                        "only BUDGET_EXHAUSTED checkpoint may be resumed"
                    )
                raw_result = self.supervisor.resume_from_checkpoint(
                    latest_checkpoint,
                    additional_windows=objective["segment_windows"],
                )

            validated_result = self._validate_supervisor_result(
                raw_result, objective_id=objective["objective_id"]
            )
            latest_checkpoint = validated_result["checkpoint"]
            await self.checkpoints.persist_checkpoint(
                latest_checkpoint,
                source_head=self.supervisor_source_head,
                policy_id=DEFAULT_CHECKPOINT_POLICY,
            )
            segments += 1

            state = latest_checkpoint["state"]
            if state in {"WAIT_FIXED_POINT", "WAIT_PLATEAU"}:
                return self._controller_result(
                    state=state,
                    objective_id=objective["objective_id"],
                    segments_executed=segments,
                    checkpoint=latest_checkpoint,
                    recovered_checkpoint=recovered_checkpoint,
                )
            if state != "BUDGET_EXHAUSTED":
                raise DemiurgeBootControllerError(
                    f"unexpected checkpoint state: {state}"
                )

        return self._controller_result(
            state="CONTROLLER_BUDGET_EXHAUSTED",
            objective_id=objective["objective_id"],
            segments_executed=segments,
            checkpoint=latest_checkpoint,
            recovered_checkpoint=recovered_checkpoint,
        )

    @staticmethod
    def _validate_supervisor_result(
        result: Mapping[str, Any], *, objective_id: str
    ) -> dict[str, Any]:
        if not isinstance(result, Mapping):
            raise DemiurgeBootControllerError("supervisor result must be an object")
        expected = {
            "schema", "state", "objective_present", "objective_id",
            "self_generated_objective", "initial_config", "final_config",
            "initial_score", "final_score", "weights", "generation_window",
            "window_offset", "windows_executed", "segment_generations",
            "segment_adoptions", "cumulative_generations", "cumulative_adoptions",
            "candidate_count", "patience_windows", "min_window_improvement",
            "windows", "checkpoint", "work_performed", "simulation_only",
            "authorized", "external_effect", "source_writeback", "automatic_merge",
            "receipt_sha256"
        }
        _closed_keys(result, expected, "supervisor result")
        if result.get("schema") != SUPERVISOR_RESULT_SCHEMA:
            raise DemiurgeBootControllerError("supervisor result schema mismatch")
        if result.get("objective_present") is not True:
            raise DemiurgeBootControllerError("supervisor result lost objective")
        if result.get("objective_id") != objective_id:
            raise DemiurgeBootControllerError("supervisor objective_id mismatch")
        if result.get("self_generated_objective") is not False:
            raise DemiurgeBootControllerError("supervisor generated its own objective")
        if result.get("work_performed") is not True:
            raise DemiurgeBootControllerError("supervisor result claims no work")
        if result.get("simulation_only") is not True:
            raise DemiurgeBootControllerError("supervisor escaped simulation-only boundary")
        for field in ("authorized", "external_effect", "source_writeback", "automatic_merge"):
            if result.get(field) is not False:
                raise DemiurgeBootControllerError(
                    f"supervisor result {field} must be false"
                )
        receipt = _hex(result.get("receipt_sha256"), 64, "supervisor result receipt")
        unsigned = dict(result)
        unsigned.pop("receipt_sha256", None)
        if canonical_sha256(unsigned) != receipt:
            raise DemiurgeBootControllerError("supervisor result receipt mismatch")
        checkpoint = result.get("checkpoint")
        try:
            validated_checkpoint = validate_checkpoint(checkpoint)
        except SupervisorCheckpointJournalError as exc:
            raise DemiurgeBootControllerError(str(exc)) from exc
        if validated_checkpoint["objective_id"] != objective_id:
            raise DemiurgeBootControllerError("checkpoint objective_id mismatch")
        if result.get("state") != validated_checkpoint["state"]:
            raise DemiurgeBootControllerError("result/checkpoint state mismatch")
        return {
            "receipt_sha256": receipt,
            "checkpoint": dict(checkpoint),
            "validated_checkpoint": validated_checkpoint,
        }

    @staticmethod
    def _controller_result(
        *,
        state: str,
        objective_id: str,
        segments_executed: int,
        checkpoint: Mapping[str, Any] | None,
        recovered_checkpoint: bool,
    ) -> dict[str, Any]:
        result = {
            "schema": CONTROLLER_SCHEMA,
            "state": state,
            "objective_id": objective_id,
            "segments_executed": segments_executed,
            "checkpoint": dict(checkpoint) if checkpoint is not None else None,
            "recovered_checkpoint": recovered_checkpoint,
            "manual_continue_between_segments_required": False,
            "self_generated_objective": False,
            "local_supervisor_execution": True,
            "autonomous_external_action": False,
            "authorized_external_action": False,
            "source_writeback": False,
            "automatic_merge": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result
