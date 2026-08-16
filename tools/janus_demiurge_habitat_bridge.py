#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Habitat bridge for the bounded Janus-Demiurge proposal face.

This validates proposal/ranking receipts and produces authority-neutral handoff
envelopes. It deliberately cannot execute a proposal, call Janus-Demiurge,
open a network connection, spawn a process, or mutate source.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping


PROPOSAL_SCHEMA = "janus.habitat.demiurge_proposal_set.v1"
RANKING_SCHEMA = "janus.habitat.demiurge_ranking.v1"
HANDOFF_SCHEMA = "janus.genesis.demiurge_handoff.v1"
FACE_ID = "DEMIURGE_BOUNDED_PROPOSAL_BUILDER"
LEGACY_PATTERN_SOURCE_COMMIT = "98974d9c02637cb471ef73f5b62cf81797895a44"
ADMITTED_SOURCE_PR_HEAD = "c5bb2c48f084ba6983f33aa562f164b614308f1f"
MAX_CANDIDATES = 16


class DemiurgeHandoffError(ValueError):
    pass


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
        raise DemiurgeHandoffError(f"{label}: unexpected keys: {sorted(extra)}")


def _hex(value: Any, length: int, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise DemiurgeHandoffError(f"{label} must be {length} lowercase hex chars")
    return value


def _verify_receipt(payload: Mapping[str, Any]) -> str:
    receipt = _hex(payload.get("receipt_sha256"), 64, "receipt_sha256")
    unsigned = dict(payload)
    unsigned.pop("receipt_sha256", None)
    if canonical_sha256(unsigned) != receipt:
        raise DemiurgeHandoffError("payload receipt mismatch")
    return receipt


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DemiurgeHandoffError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise DemiurgeHandoffError(f"{label} must be finite")
    return result


def validate_demiurge_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DemiurgeHandoffError("payload must be an object")
    schema = payload.get("schema")
    if schema == PROPOSAL_SCHEMA:
        return _validate_proposal(payload)
    if schema == RANKING_SCHEMA:
        return _validate_ranking(payload)
    raise DemiurgeHandoffError("unsupported Demiurge payload schema")


def _validate_proposal(payload: Mapping[str, Any]) -> dict[str, Any]:
    _closed_keys(
        payload,
        {
            "schema", "face_id", "source_commit", "request_id", "request_digest",
            "proposal_count", "proposals", "execution_requested",
            "source_writeback_requested", "selection_authority_claimed", "receipt_sha256"
        },
        "proposal_set",
    )
    if payload.get("face_id") != FACE_ID:
        raise DemiurgeHandoffError("unexpected face_id")
    if payload.get("source_commit") != LEGACY_PATTERN_SOURCE_COMMIT:
        raise DemiurgeHandoffError("legacy pattern source mismatch")
    if payload.get("execution_requested") is not False:
        raise DemiurgeHandoffError("proposal requests execution")
    if payload.get("source_writeback_requested") is not False:
        raise DemiurgeHandoffError("proposal requests source writeback")
    if payload.get("selection_authority_claimed") is not False:
        raise DemiurgeHandoffError("proposal claims selection authority")
    _hex(payload.get("request_digest"), 64, "request_digest")
    receipt = _verify_receipt(payload)

    proposals = payload.get("proposals")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= MAX_CANDIDATES:
        raise DemiurgeHandoffError("proposal list is missing or out of bounds")
    if payload.get("proposal_count") != len(proposals):
        raise DemiurgeHandoffError("proposal_count mismatch")

    ids: set[str] = set()
    for row in proposals:
        if not isinstance(row, Mapping):
            raise DemiurgeHandoffError("proposal row must be an object")
        _closed_keys(row, {"proposal_id", "config", "tested", "selected", "authorized"}, "proposal")
        proposal_id = _hex(row.get("proposal_id"), 24, "proposal_id")
        if proposal_id in ids:
            raise DemiurgeHandoffError("duplicate proposal_id")
        ids.add(proposal_id)
        if not isinstance(row.get("config"), Mapping):
            raise DemiurgeHandoffError("proposal config must be an object")
        if row.get("tested") is not False:
            raise DemiurgeHandoffError("proposal pre-asserts tested state")
        if row.get("selected") is not False:
            raise DemiurgeHandoffError("proposal pre-asserts selected state")
        if row.get("authorized") is not False:
            raise DemiurgeHandoffError("proposal pre-asserts authorization")

    return {
        "payload_schema": PROPOSAL_SCHEMA,
        "payload_receipt_sha256": receipt,
        "proposal_ids": sorted(ids),
        "handoff_target": "NEXUS_VARIANT_LINEAGE_OR_VERIFIER",
    }


def _validate_ranking(payload: Mapping[str, Any]) -> dict[str, Any]:
    _closed_keys(
        payload,
        {
            "schema", "face_id", "proposal_receipt_sha256", "objective", "maximize",
            "ranking", "selected_proposal_id", "selection_is_recommendation_only",
            "authorized", "execution_requested", "source_writeback_requested", "receipt_sha256"
        },
        "ranking",
    )
    if payload.get("face_id") != FACE_ID:
        raise DemiurgeHandoffError("unexpected face_id")
    _hex(payload.get("proposal_receipt_sha256"), 64, "proposal_receipt_sha256")
    if payload.get("selection_is_recommendation_only") is not True:
        raise DemiurgeHandoffError("ranking must remain recommendation-only")
    if payload.get("authorized") is not False:
        raise DemiurgeHandoffError("ranking asserts authorization")
    if payload.get("execution_requested") is not False:
        raise DemiurgeHandoffError("ranking requests execution")
    if payload.get("source_writeback_requested") is not False:
        raise DemiurgeHandoffError("ranking requests source writeback")
    objective = payload.get("objective")
    if not isinstance(objective, str) or not objective or len(objective) > 64:
        raise DemiurgeHandoffError("invalid ranking objective")
    receipt = _verify_receipt(payload)

    ranking = payload.get("ranking")
    if not isinstance(ranking, list) or not 1 <= len(ranking) <= MAX_CANDIDATES:
        raise DemiurgeHandoffError("ranking list is missing or out of bounds")
    ids: list[str] = []
    previous: float | None = None
    maximize = payload.get("maximize")
    if not isinstance(maximize, bool):
        raise DemiurgeHandoffError("maximize must be boolean")
    for row in ranking:
        if not isinstance(row, Mapping):
            raise DemiurgeHandoffError("ranking row must be an object")
        _closed_keys(row, {"proposal_id", objective}, "ranking row")
        proposal_id = _hex(row.get("proposal_id"), 24, "proposal_id")
        if proposal_id in ids:
            raise DemiurgeHandoffError("duplicate ranked proposal_id")
        ids.append(proposal_id)
        score = _finite(row.get(objective), f"ranking.{objective}")
        if previous is not None:
            if maximize and score > previous:
                raise DemiurgeHandoffError("ranking order contradicts maximize=true")
            if not maximize and score < previous:
                raise DemiurgeHandoffError("ranking order contradicts maximize=false")
        previous = score
    if payload.get("selected_proposal_id") != ids[0]:
        raise DemiurgeHandoffError("selected_proposal_id must equal first ranked proposal")

    return {
        "payload_schema": RANKING_SCHEMA,
        "payload_receipt_sha256": receipt,
        "proposal_ids": ids,
        "handoff_target": "JANUS_CORE_RECONCILER",
    }


def make_handoff(payload: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_demiurge_payload(payload)
    handoff = {
        "schema": HANDOFF_SCHEMA,
        "source_face": FACE_ID,
        "source_repository": "Hawkar-usls/Janus-Demiurge",
        "admitted_source_pr_head": ADMITTED_SOURCE_PR_HEAD,
        "payload_schema": validation["payload_schema"],
        "payload_receipt_sha256": validation["payload_receipt_sha256"],
        "handoff_target": validation["handoff_target"],
        "proposal_ids": validation["proposal_ids"],
        "execute": False,
        "authorized": False,
        "source_writeback": False,
        "external_effect": False,
        "implementation_membership_proven_by_payload": False,
    }
    handoff["receipt_sha256"] = canonical_sha256(handoff)
    return handoff
