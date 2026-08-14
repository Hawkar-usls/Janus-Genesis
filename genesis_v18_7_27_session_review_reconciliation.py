# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.27 — cross-process AI-link turn serialization,
lineage-independent face review, and provider lookup reconciliation.

This additive layer strengthens v18.7.26 in three places:

1. A stable session sequence is only useful if two processes cannot allocate the
   same session transition concurrently. ``CrossProcessSessionLock`` serializes
   the controlled AI-link turn transaction through a filesystem lock.
2. Distinct face IDs are not sufficient evidence of independent review when
   several faces may be forks/clones of one lineage. Review independence is
   counted by lineage root, never by raw face count.
3. Ambiguous external outcomes may be reconciled by a provider-specific lookup
   adapter, but the generic layer treats adapter authority as an explicit
   contract boundary rather than proving the provider's truthfulness.

The module does not execute payments, mail, actuators, or other real-world
external effects. It also does not claim that a local file lock is a distributed
multi-host consensus protocol.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, Sequence

from genesis_v18_7_25_durable_journal_fencing import ProviderEffectBinding
from genesis_v18_7_26_controlled_ai_link import ControlledGenesisAILinkGateway

SESSION_REVIEW_VERSION = "18.7.27"
SESSION_REVIEW_SCHEMA = "janus.genesis.session_review_reconciliation.v1"


class SessionControlError(RuntimeError):
    code = "SESSION_CONTROL_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class IndependentReviewUnavailable(SessionControlError):
    code = "INDEPENDENT_REVIEW_LINEAGES_UNAVAILABLE"


class ProviderLookupContractError(SessionControlError):
    code = "PROVIDER_LOOKUP_CONTRACT_ERROR"


class CrossProcessSessionLock:
    """Filesystem flock used to serialize one controlled AI-link store mutation.

    The lock protects processes that share this exact lock file on a filesystem
    with working ``flock`` semantics. It is not a multi-host consensus claim.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._thread_lock = threading.RLock()

    @contextlib.contextmanager
    def exclusive(self):
        with self._thread_lock:
            with self.path.open("a+") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def try_acquire_probe(self) -> bool:
        """Non-mutating test/probe for whether an independent open can lock now."""
        handle = self.path.open("a+")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                return True
        finally:
            handle.close()


class LockedControlledGenesisAILinkGateway(ControlledGenesisAILinkGateway):
    """Controlled AI-link descendant with cross-process turn serialization.

    ``process_turn`` holds the store lock across sequence read, controlled
    runtime call/replay, parent turn append, sequence increment, hash update, and
    store replace. Therefore two cooperating v18.7.27 gateways sharing the same
    store cannot race the same session mutation through this path.
    """

    def __init__(self, world: Any, data_dir: str | Path, *, adapter) -> None:
        super().__init__(world, data_dir, adapter=adapter)
        self.session_lock = CrossProcessSessionLock(
            Path(data_dir) / "ai_link_sessions_v18_7_27.lock"
        )

    def process_turn(
        self,
        session_id: str,
        action: str,
        *,
        origin: str,
        human_confirmed: bool = False,
    ) -> dict[str, Any]:
        with self.session_lock.exclusive():
            return super().process_turn(
                session_id,
                action,
                origin=origin,
                human_confirmed=human_confirmed,
            )


@dataclass(frozen=True)
class FaceReviewCandidate:
    face_id: str
    lineage_root: str
    routing_priority: float = 1.0
    novel_counterevidence: bool = False
    red_team_capable: bool = True

    def __post_init__(self) -> None:
        if not self.face_id.strip() or not self.lineage_root.strip():
            raise ValueError("FACE_AND_LINEAGE_ROOT_REQUIRED")


@dataclass(frozen=True)
class LineageReviewAssignment:
    face_id: str
    lineage_root: str
    role: str
    routing_priority: float
    novel_counterevidence: bool
    authority_weight: int = 0
    world_authority_granted: bool = False


class LineageIndependentReviewPlanner:
    """High-risk review planner where one lineage contributes at most one seat."""

    def plan(
        self,
        *,
        origin_lineage_root: str,
        candidates: Sequence[FaceReviewCandidate],
        required_reviews: int = 2,
        require_red_team: bool = True,
    ) -> tuple[LineageReviewAssignment, ...]:
        origin_root = str(origin_lineage_root).strip()
        if not origin_root:
            raise ValueError("ORIGIN_LINEAGE_ROOT_REQUIRED")
        if required_reviews < 1:
            raise ValueError("REQUIRED_REVIEWS_MUST_BE_POSITIVE")

        eligible = [c for c in candidates if c.lineage_root != origin_root]
        by_lineage: dict[str, list[FaceReviewCandidate]] = {}
        for candidate in eligible:
            by_lineage.setdefault(candidate.lineage_root, []).append(candidate)

        representatives: list[FaceReviewCandidate] = []
        for lineage_root, members in by_lineage.items():
            representative = min(
                members,
                key=lambda c: (
                    0 if c.novel_counterevidence else 1,
                    -float(c.routing_priority),
                    c.face_id,
                ),
            )
            representatives.append(representative)

        representatives.sort(
            key=lambda c: (
                0 if c.novel_counterevidence else 1,
                -float(c.routing_priority),
                c.lineage_root,
                c.face_id,
            )
        )
        if len(representatives) < required_reviews:
            raise IndependentReviewUnavailable(
                f"required={required_reviews}; independent_lineages={len(representatives)}"
            )

        selected = representatives[:required_reviews]
        if require_red_team and not any(c.red_team_capable for c in selected):
            replacement = next(
                (c for c in representatives[required_reviews:] if c.red_team_capable),
                None,
            )
            if replacement is None:
                raise IndependentReviewUnavailable("RED_TEAM_INDEPENDENT_LINEAGE_UNAVAILABLE")
            selected[-1] = replacement

        red_team_assigned = False
        assignments: list[LineageReviewAssignment] = []
        for candidate in selected:
            if require_red_team and candidate.red_team_capable and not red_team_assigned:
                role = "COUNTEREXAMPLE_CHALLENGE"
                red_team_assigned = True
            else:
                role = "INDEPENDENT_REVIEW"
            assignments.append(
                LineageReviewAssignment(
                    face_id=candidate.face_id,
                    lineage_root=candidate.lineage_root,
                    role=role,
                    routing_priority=float(candidate.routing_priority),
                    novel_counterevidence=bool(candidate.novel_counterevidence),
                    authority_weight=0,
                    world_authority_granted=False,
                )
            )
        return tuple(assignments)


class ProviderLookupOutcome(str, Enum):
    SETTLED = "SETTLED"
    NO_EFFECT = "NO_EFFECT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProviderLookupObservation:
    provider_id: str
    effect_key: str
    idempotency_key: str | None
    outcome: ProviderLookupOutcome
    evidence_ref: str
    receipt_id: str | None = None
    authoritative_under_adapter_contract: bool = False


class ProviderLookupAdapter(Protocol):
    """Provider-specific lookup contract supplied outside the generic core."""

    provider_id: str

    def lookup(self, binding: ProviderEffectBinding) -> ProviderLookupObservation: ...


@dataclass(frozen=True)
class ProviderReconciliationDecision:
    effect_key: str
    provider_id: str
    state: str
    evidence_ref: str | None
    receipt_id: str | None
    safe_automatic_retry: bool


class ProviderLookupReconciler:
    """Validate structural binding and map provider lookup into recovery policy."""

    def reconcile(
        self,
        *,
        binding: ProviderEffectBinding,
        adapter: ProviderLookupAdapter,
    ) -> ProviderReconciliationDecision:
        observation = adapter.lookup(binding)
        if adapter.provider_id != binding.provider_id:
            raise ProviderLookupContractError("ADAPTER_PROVIDER_ID_MISMATCH")
        if observation.provider_id != binding.provider_id:
            raise ProviderLookupContractError("OBSERVATION_PROVIDER_ID_MISMATCH")
        if observation.effect_key != binding.effect_key:
            raise ProviderLookupContractError("OBSERVATION_EFFECT_KEY_MISMATCH")
        if observation.idempotency_key != binding.idempotency_key:
            raise ProviderLookupContractError("OBSERVATION_IDEMPOTENCY_KEY_MISMATCH")

        if not observation.authoritative_under_adapter_contract:
            return ProviderReconciliationDecision(
                effect_key=binding.effect_key,
                provider_id=binding.provider_id,
                state="UNDETERMINED_PROVIDER_LOOKUP_NOT_AUTHORITATIVE",
                evidence_ref=observation.evidence_ref or None,
                receipt_id=None,
                safe_automatic_retry=False,
            )

        if observation.outcome is ProviderLookupOutcome.SETTLED:
            if not observation.receipt_id:
                raise ProviderLookupContractError("SETTLED_LOOKUP_REQUIRES_RECEIPT_ID")
            return ProviderReconciliationDecision(
                effect_key=binding.effect_key,
                provider_id=binding.provider_id,
                state="SETTLED_BY_PROVIDER_LOOKUP",
                evidence_ref=observation.evidence_ref,
                receipt_id=observation.receipt_id,
                safe_automatic_retry=False,
            )
        if observation.outcome is ProviderLookupOutcome.NO_EFFECT:
            return ProviderReconciliationDecision(
                effect_key=binding.effect_key,
                provider_id=binding.provider_id,
                state="NO_EFFECT_BY_PROVIDER_LOOKUP",
                evidence_ref=observation.evidence_ref,
                receipt_id=None,
                safe_automatic_retry=True,
            )
        return ProviderReconciliationDecision(
            effect_key=binding.effect_key,
            provider_id=binding.provider_id,
            state="UNDETERMINED_PROVIDER_OUTCOME",
            evidence_ref=observation.evidence_ref or None,
            receipt_id=None,
            safe_automatic_retry=False,
        )


__all__ = [
    "SESSION_REVIEW_VERSION",
    "SESSION_REVIEW_SCHEMA",
    "CrossProcessSessionLock",
    "LockedControlledGenesisAILinkGateway",
    "FaceReviewCandidate",
    "LineageReviewAssignment",
    "LineageIndependentReviewPlanner",
    "IndependentReviewUnavailable",
    "ProviderLookupOutcome",
    "ProviderLookupObservation",
    "ProviderLookupAdapter",
    "ProviderReconciliationDecision",
    "ProviderLookupReconciler",
    "ProviderLookupContractError",
]
