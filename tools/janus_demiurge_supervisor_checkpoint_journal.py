#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Durable operational checkpoint bridge for the bounded Demiurge supervisor.

Role split:
- counterfactual loop episodes -> Cortex episodic/search projection (#156)
- supervisor continuation checkpoint -> Hippocampus operational journal

A successful ``persist_checkpoint`` always crosses an explicit Hippocampus
``force_save`` boundary and then verifies the record can be recalled from HDD.
This establishes local SQLite transaction persistence, not backup/replication or
power-loss-proof storage.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


CHECKPOINT_SCHEMA = "janus.habitat.demiurge_lab_checkpoint.v1"
RECORD_SCHEMA = "janus.genesis.demiurge_supervisor_checkpoint_record.v1"
RESULT_SCHEMA = "janus.genesis.demiurge_supervisor_checkpoint_result.v1"
RECOVERY_SCHEMA = "janus.genesis.demiurge_supervisor_checkpoint_recovery.v1"
PINNED_SUPERVISOR_HEAD = "74c8a9dc090dba4d3bd7d497e1ff75223e6fe6c0"
PINNED_SUPERVISOR_PR = "Hawkar-usls/Janus-Demiurge#4"
JOURNAL_SOURCE = "JANUS_DEMIURGE_SUPERVISOR_CHECKPOINT"
MAX_GENERATION_WINDOW = 64
MAX_CANDIDATES = 16
MAX_PATIENCE_WINDOWS = 16
MAX_POLICY_ID_CHARS = 128
MAX_OBJECTIVE_ID_CHARS = 128
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")
_BOUNDS = {
    "alpha": (0.01, 0.5),
    "gamma": (0.8, 0.999),
    "epsilon": (0.01, 0.9),
}


class SupervisorCheckpointJournalError(ValueError):
    pass


class OperationalJournal(Protocol):
    async def remember(
        self,
        source: str | None = None,
        content: Any = None,
        vector: Any = None,
        *,
        tag: str | None = None,
    ) -> None: ...
    async def force_save(self) -> int: ...
    async def recall(self, keyword: str, limit: int = 5) -> Sequence[Mapping[str, Any]]: ...
    async def stats(self) -> Mapping[str, Any]: ...


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
        raise SupervisorCheckpointJournalError(
            f"{label}: unexpected keys: {sorted(extra)}"
        )


def _hex(value: Any, length: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise SupervisorCheckpointJournalError(
            f"{label} must be {length} lowercase hex chars"
        )
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SupervisorCheckpointJournalError(f"{label} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise SupervisorCheckpointJournalError(f"{label} must be finite")
    return result


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SupervisorCheckpointJournalError(
            f"{label} must be a non-negative integer"
        )
    return value


def _positive_bounded_int(value: Any, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise SupervisorCheckpointJournalError(f"{label} must be 1..{maximum}")
    return value


def _safe_id(value: Any, label: str, max_chars: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > max_chars
        or _SAFE_ID.fullmatch(value) is None
    ):
        raise SupervisorCheckpointJournalError(
            f"{label} must match {_SAFE_ID.pattern} and be <= {max_chars} chars"
        )
    return value


def _core_config(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(_BOUNDS):
        raise SupervisorCheckpointJournalError(
            f"{label} must contain exactly {sorted(_BOUNDS)}"
        )
    out: dict[str, float] = {}
    for key, (low, high) in _BOUNDS.items():
        number = _finite(value.get(key), f"{label}.{key}")
        if not low <= number <= high:
            raise SupervisorCheckpointJournalError(
                f"{label}.{key} outside admitted range"
            )
        out[key] = number
    return out


def _weights(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != set(_BOUNDS):
        raise SupervisorCheckpointJournalError(
            "weights must contain exactly alpha/gamma/epsilon"
        )
    out: dict[str, float] = {}
    for key in _BOUNDS:
        number = _finite(value.get(key), f"weights.{key}")
        if number <= 0:
            raise SupervisorCheckpointJournalError("weights must be > 0")
        out[key] = number
    return out


def _score(config: Mapping[str, float], target: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    norm = 0.0
    for key, (low, high) in _BOUNDS.items():
        delta = (config[key] - target[key]) / (high - low)
        total += weights[key] * delta * delta
        norm += weights[key]
    return -float(total / norm)


def validate_checkpoint(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(checkpoint, Mapping):
        raise SupervisorCheckpointJournalError("checkpoint must be an object")
    expected = {
        "schema", "objective_id", "resume_config", "resume_score",
        "next_window_index", "root_seed", "target_config", "weights",
        "generation_window", "candidate_count", "patience_windows",
        "min_window_improvement", "total_generations", "total_adoptions",
        "state", "parent_checkpoint_receipt_sha256", "receipt_sha256"
    }
    if set(checkpoint) != expected:
        raise SupervisorCheckpointJournalError("checkpoint schema is not closed")
    if checkpoint.get("schema") != CHECKPOINT_SCHEMA:
        raise SupervisorCheckpointJournalError("unsupported checkpoint schema")

    receipt = _hex(checkpoint.get("receipt_sha256"), 64, "checkpoint receipt")
    unsigned = dict(checkpoint)
    unsigned.pop("receipt_sha256", None)
    if canonical_sha256(unsigned) != receipt:
        raise SupervisorCheckpointJournalError("checkpoint receipt mismatch")

    objective_id = _safe_id(
        checkpoint.get("objective_id"), "objective_id", MAX_OBJECTIVE_ID_CHARS
    )
    resume_config = _core_config(checkpoint.get("resume_config"), "resume_config")
    target_config = _core_config(checkpoint.get("target_config"), "target_config")
    weights = _weights(checkpoint.get("weights"))
    resume_score = _finite(checkpoint.get("resume_score"), "resume_score")
    replayed_score = _score(resume_config, target_config, weights)
    if replayed_score != resume_score:
        raise SupervisorCheckpointJournalError(
            "resume_score does not replay from config/target/weights"
        )

    next_window_index = _nonnegative_int(
        checkpoint.get("next_window_index"), "next_window_index"
    )
    root_seed = checkpoint.get("root_seed")
    if isinstance(root_seed, bool) or not isinstance(root_seed, int):
        raise SupervisorCheckpointJournalError("root_seed must be an integer")
    generation_window = _positive_bounded_int(
        checkpoint.get("generation_window"),
        "generation_window",
        MAX_GENERATION_WINDOW,
    )
    candidate_count = _positive_bounded_int(
        checkpoint.get("candidate_count"), "candidate_count", MAX_CANDIDATES
    )
    patience_windows = _positive_bounded_int(
        checkpoint.get("patience_windows"),
        "patience_windows",
        MAX_PATIENCE_WINDOWS,
    )
    min_improvement = _finite(
        checkpoint.get("min_window_improvement"), "min_window_improvement"
    )
    if min_improvement < 0:
        raise SupervisorCheckpointJournalError(
            "min_window_improvement must be >= 0"
        )
    total_generations = _nonnegative_int(
        checkpoint.get("total_generations"), "total_generations"
    )
    total_adoptions = _nonnegative_int(
        checkpoint.get("total_adoptions"), "total_adoptions"
    )
    if total_generations != next_window_index * generation_window:
        raise SupervisorCheckpointJournalError(
            "total_generations must equal next_window_index * generation_window"
        )
    if total_adoptions > total_generations:
        raise SupervisorCheckpointJournalError(
            "total_adoptions cannot exceed total_generations"
        )

    state = checkpoint.get("state")
    if state not in {"BUDGET_EXHAUSTED", "WAIT_PLATEAU", "WAIT_FIXED_POINT"}:
        raise SupervisorCheckpointJournalError("checkpoint state invalid")
    if state == "WAIT_FIXED_POINT" and resume_score != 0.0:
        raise SupervisorCheckpointJournalError(
            "WAIT_FIXED_POINT requires score 0.0"
        )
    parent = checkpoint.get("parent_checkpoint_receipt_sha256")
    if parent is not None:
        _hex(parent, 64, "parent checkpoint receipt")

    return {
        "receipt_sha256": receipt,
        "objective_id": objective_id,
        "resume_config": resume_config,
        "resume_score": resume_score,
        "next_window_index": next_window_index,
        "root_seed": root_seed,
        "target_config": target_config,
        "weights": weights,
        "generation_window": generation_window,
        "candidate_count": candidate_count,
        "patience_windows": patience_windows,
        "min_window_improvement": min_improvement,
        "total_generations": total_generations,
        "total_adoptions": total_adoptions,
        "state": state,
        "parent_checkpoint_receipt_sha256": parent,
    }


@dataclass(frozen=True)
class CheckpointRecord:
    policy_id: str
    objective_lookup_key: str
    idempotency_key: str
    content: str
    checkpoint_receipt_sha256: str
    record_receipt_sha256: str


class JanusDemiurgeSupervisorCheckpointJournal:
    """Persist/recover exact supervisor checkpoints through Hippocampus."""

    def __init__(self, journal: OperationalJournal) -> None:
        self.journal = journal
        self._lock = asyncio.Lock()

    def build_record(
        self,
        checkpoint: Mapping[str, Any],
        *,
        source_head: str,
        policy_id: str,
    ) -> CheckpointRecord:
        source_head = _hex(source_head, 40, "source_head")
        if source_head != PINNED_SUPERVISOR_HEAD:
            raise SupervisorCheckpointJournalError(
                "source_head is not the admitted supervisor head"
            )
        policy_id = _safe_id(policy_id, "policy_id", MAX_POLICY_ID_CHARS)
        validated = validate_checkpoint(checkpoint)
        objective_lookup_key = canonical_sha256(
            {
                "policy_id": policy_id,
                "objective_id": validated["objective_id"],
                "source_head": source_head,
            }
        )
        idempotency_key = canonical_sha256(
            {
                "objective_lookup_key": objective_lookup_key,
                "checkpoint_receipt_sha256": validated["receipt_sha256"],
            }
        )
        envelope = {
            "schema": RECORD_SCHEMA,
            "policy_id": policy_id,
            "source_repository": "Hawkar-usls/Janus-Demiurge",
            "source_pr": PINNED_SUPERVISOR_PR,
            "source_head": source_head,
            "objective_id": validated["objective_id"],
            "objective_lookup_key": objective_lookup_key,
            "idempotency_key": idempotency_key,
            "checkpoint_receipt_sha256": validated["receipt_sha256"],
            "checkpoint": dict(checkpoint),
            "same_evidence_root_as_source": True,
            "independent_corroboration_claimed": False,
            "authorized": False,
            "execute": False,
            "source_writeback": False,
            "external_effect": False,
        }
        envelope["record_receipt_sha256"] = canonical_sha256(envelope)
        return CheckpointRecord(
            policy_id=policy_id,
            objective_lookup_key=objective_lookup_key,
            idempotency_key=idempotency_key,
            content=_canonical_bytes(envelope).decode("utf-8"),
            checkpoint_receipt_sha256=validated["receipt_sha256"],
            record_receipt_sha256=envelope["record_receipt_sha256"],
        )

    async def persist_checkpoint(
        self,
        checkpoint: Mapping[str, Any],
        *,
        source_head: str,
        policy_id: str = "DEMIURGE_SUPERVISOR_CHECKPOINT_V1",
    ) -> dict[str, Any]:
        record = self.build_record(
            checkpoint, source_head=source_head, policy_id=policy_id
        )
        async with self._lock:
            prior = await self._matching_records(
                record.idempotency_key, persisted_only=False
            )
            if prior:
                if any(item["content"] != record.content for item in prior):
                    raise SupervisorCheckpointJournalError(
                        "idempotency key is already bound to different content"
                    )
                if not all(item["origin"] == "HDD" for item in prior):
                    await self.journal.force_save()
                verified = await self._matching_records(
                    record.idempotency_key, persisted_only=True
                )
                if not verified:
                    raise SupervisorCheckpointJournalError(
                        "idempotent checkpoint is not verifiably persisted"
                    )
                return await self._result(record, "IDEMPOTENT_PERSISTED_REPLAY")

            await self.journal.remember(source=JOURNAL_SOURCE, content=record.content)
            await self.journal.force_save()
            verified = await self._matching_records(
                record.idempotency_key, persisted_only=True
            )
            if len(verified) != 1 or verified[0]["content"] != record.content:
                raise SupervisorCheckpointJournalError(
                    "checkpoint commit could not be verified from HDD recall"
                )
            return await self._result(record, "PERSISTED")

    async def recover_latest(
        self,
        *,
        objective_id: str,
        source_head: str,
        policy_id: str = "DEMIURGE_SUPERVISOR_CHECKPOINT_V1",
        limit: int = 200,
    ) -> dict[str, Any]:
        source_head = _hex(source_head, 40, "source_head")
        if source_head != PINNED_SUPERVISOR_HEAD:
            raise SupervisorCheckpointJournalError(
                "source_head is not the admitted supervisor head"
            )
        policy_id = _safe_id(policy_id, "policy_id", MAX_POLICY_ID_CHARS)
        objective_id = _safe_id(
            objective_id, "objective_id", MAX_OBJECTIVE_ID_CHARS
        )
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise SupervisorCheckpointJournalError("limit must be 1..500")
        lookup = canonical_sha256(
            {
                "policy_id": policy_id,
                "objective_id": objective_id,
                "source_head": source_head,
            }
        )
        hits = await self.journal.recall(lookup, limit=limit)
        records: list[dict[str, Any]] = []
        for hit in hits:
            if hit.get("origin") != "HDD" or hit.get("source") != JOURNAL_SOURCE:
                continue
            parsed = self._parse_record(hit.get("content"))
            if (
                parsed["policy_id"] != policy_id
                or parsed["source_head"] != source_head
                or parsed["objective_id"] != objective_id
                or parsed["objective_lookup_key"] != lookup
            ):
                continue
            records.append(parsed)
        if not records:
            return self._recovery_result(
                state="NOT_FOUND",
                objective_id=objective_id,
                source_head=source_head,
                policy_id=policy_id,
                checkpoint=None,
                record_receipt=None,
                ancestry_complete=False,
            )

        by_index: dict[int, dict[str, Any]] = {}
        receipt_map = {
            item["checkpoint"]["receipt_sha256"]: item for item in records
        }
        for item in records:
            index = item["validated_checkpoint"]["next_window_index"]
            existing = by_index.get(index)
            if (
                existing is not None
                and existing["checkpoint"]["receipt_sha256"]
                != item["checkpoint"]["receipt_sha256"]
            ):
                raise SupervisorCheckpointJournalError(
                    "HOLD_RECONCILE: conflicting persisted checkpoints at same window index"
                )
            by_index[index] = item
        latest = by_index[max(by_index)]

        ancestry_complete = True
        cursor = latest
        seen: set[str] = set()
        while True:
            receipt = cursor["checkpoint"]["receipt_sha256"]
            if receipt in seen:
                raise SupervisorCheckpointJournalError(
                    "checkpoint ancestry cycle detected"
                )
            seen.add(receipt)
            parent = cursor["validated_checkpoint"]["parent_checkpoint_receipt_sha256"]
            if parent is None:
                break
            parent_record = receipt_map.get(parent)
            if parent_record is None:
                ancestry_complete = False
                break
            if (
                parent_record["validated_checkpoint"]["next_window_index"]
                >= cursor["validated_checkpoint"]["next_window_index"]
            ):
                raise SupervisorCheckpointJournalError(
                    "checkpoint ancestry does not move forward"
                )
            cursor = parent_record

        return self._recovery_result(
            state="RECOVERED",
            objective_id=objective_id,
            source_head=source_head,
            policy_id=policy_id,
            checkpoint=latest["checkpoint"],
            record_receipt=latest["record_receipt_sha256"],
            ancestry_complete=ancestry_complete,
        )

    async def _matching_records(
        self, idempotency_key: str, *, persisted_only: bool
    ) -> list[Mapping[str, Any]]:
        hits = await self.journal.recall(idempotency_key, limit=32)
        result = []
        for hit in hits:
            if persisted_only and hit.get("origin") != "HDD":
                continue
            if hit.get("source") != JOURNAL_SOURCE:
                continue
            try:
                parsed = self._parse_record(hit.get("content"))
            except SupervisorCheckpointJournalError:
                continue
            if parsed["idempotency_key"] == idempotency_key:
                result.append(hit)
        return result

    def _parse_record(self, content: Any) -> dict[str, Any]:
        if not isinstance(content, str):
            raise SupervisorCheckpointJournalError("journal record content is not text")
        try:
            value = json.loads(content)
        except (TypeError, ValueError) as exc:
            raise SupervisorCheckpointJournalError("journal record is not valid JSON") from exc
        if not isinstance(value, Mapping):
            raise SupervisorCheckpointJournalError("journal record must be an object")
        expected = {
            "schema", "policy_id", "source_repository", "source_pr", "source_head",
            "objective_id", "objective_lookup_key", "idempotency_key",
            "checkpoint_receipt_sha256", "checkpoint", "same_evidence_root_as_source",
            "independent_corroboration_claimed", "authorized", "execute",
            "source_writeback", "external_effect", "record_receipt_sha256"
        }
        _closed_keys(value, expected, "checkpoint record")
        if value.get("schema") != RECORD_SCHEMA:
            raise SupervisorCheckpointJournalError("record schema mismatch")
        if value.get("source_repository") != "Hawkar-usls/Janus-Demiurge":
            raise SupervisorCheckpointJournalError("record source repository mismatch")
        if value.get("source_pr") != PINNED_SUPERVISOR_PR:
            raise SupervisorCheckpointJournalError("record source PR mismatch")
        if value.get("same_evidence_root_as_source") is not True:
            raise SupervisorCheckpointJournalError("record evidence-root flag invalid")
        for field in (
            "independent_corroboration_claimed", "authorized", "execute",
            "source_writeback", "external_effect"
        ):
            if value.get(field) is not False:
                raise SupervisorCheckpointJournalError(
                    f"record {field} must be false"
                )
        record_receipt = _hex(
            value.get("record_receipt_sha256"), 64, "record receipt"
        )
        unsigned = dict(value)
        unsigned.pop("record_receipt_sha256", None)
        if canonical_sha256(unsigned) != record_receipt:
            raise SupervisorCheckpointJournalError("record receipt mismatch")
        validated = validate_checkpoint(value.get("checkpoint"))
        if value.get("checkpoint_receipt_sha256") != validated["receipt_sha256"]:
            raise SupervisorCheckpointJournalError(
                "record/checkpoint receipt binding mismatch"
            )
        policy_id = _safe_id(
            value.get("policy_id"), "record policy_id", MAX_POLICY_ID_CHARS
        )
        source_head = _hex(value.get("source_head"), 40, "record source_head")
        objective_id = _safe_id(
            value.get("objective_id"), "record objective_id", MAX_OBJECTIVE_ID_CHARS
        )
        objective_lookup_key = _hex(
            value.get("objective_lookup_key"), 64, "objective_lookup_key"
        )
        expected_lookup = canonical_sha256(
            {
                "policy_id": policy_id,
                "objective_id": objective_id,
                "source_head": source_head,
            }
        )
        if objective_lookup_key != expected_lookup:
            raise SupervisorCheckpointJournalError(
                "objective lookup key mismatch"
            )
        idempotency_key = _hex(
            value.get("idempotency_key"), 64, "idempotency_key"
        )
        expected_idempotency = canonical_sha256(
            {
                "objective_lookup_key": objective_lookup_key,
                "checkpoint_receipt_sha256": validated["receipt_sha256"],
            }
        )
        if idempotency_key != expected_idempotency:
            raise SupervisorCheckpointJournalError("idempotency key mismatch")
        return {
            **dict(value),
            "validated_checkpoint": validated,
            "record_receipt_sha256": record_receipt,
        }

    async def _result(self, record: CheckpointRecord, state: str) -> dict[str, Any]:
        stats = await self.journal.stats()
        result = {
            "schema": RESULT_SCHEMA,
            "state": state,
            "policy_id": record.policy_id,
            "source_head": PINNED_SUPERVISOR_HEAD,
            "checkpoint_receipt_sha256": record.checkpoint_receipt_sha256,
            "record_receipt_sha256": record.record_receipt_sha256,
            "idempotency_key": record.idempotency_key,
            "sqlite_transaction_committed": True,
            "journal_synchronous": stats.get("synchronous"),
            "backup_claimed": False,
            "replication_claimed": False,
            "power_loss_proof_claimed": False,
            "process_restart_recovery_after_commit": True,
            "same_evidence_root_as_source": True,
            "independent_corroboration_claimed": False,
            "authorized": False,
            "execute": False,
            "source_writeback": False,
            "external_effect": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result

    @staticmethod
    def _recovery_result(
        *,
        state: str,
        objective_id: str,
        source_head: str,
        policy_id: str,
        checkpoint: Mapping[str, Any] | None,
        record_receipt: str | None,
        ancestry_complete: bool,
    ) -> dict[str, Any]:
        result = {
            "schema": RECOVERY_SCHEMA,
            "state": state,
            "objective_id": objective_id,
            "source_head": source_head,
            "policy_id": policy_id,
            "checkpoint": dict(checkpoint) if checkpoint is not None else None,
            "record_receipt_sha256": record_receipt,
            "ancestry_complete_within_bounded_recall": ancestry_complete,
            "authorized": False,
            "execute": False,
            "source_writeback": False,
            "external_effect": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result
