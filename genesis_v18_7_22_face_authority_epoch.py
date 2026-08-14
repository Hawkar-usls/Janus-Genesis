# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.22 — authority epochs, confused-deputy guard, and micro-review.

This layer extends v18.7.21. Faces remain free to propose, but a proposal may
reach the external dispatch boundary only through a non-transferable capability
lease that is revalidated at dispatch time. The module still performs no
external side effect itself.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from genesis_v18_7_21_face_microcontrol import (
    CommitAuthorization,
    FaceMicroController,
    FaceProposal,
    WorldReceipt,
)

AUTHORITY_EPOCH_VERSION = "18.7.22"
AUTHORITY_EPOCH_SCHEMA = "janus.genesis.face_authority_epoch.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class AuthorityEpochError(RuntimeError):
    code = "AUTHORITY_EPOCH_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class UnknownLeaseError(AuthorityEpochError):
    code = "UNKNOWN_AUTHORITY_LEASE"


class RevokedLeaseError(AuthorityEpochError):
    code = "AUTHORITY_LEASE_REVOKED"


class StaleAuthorityEpochError(AuthorityEpochError):
    code = "STALE_AUTHORITY_EPOCH"


class CapabilityScopeError(AuthorityEpochError):
    code = "CAPABILITY_SCOPE_DENIED"


class CapabilityPrincipalError(AuthorityEpochError):
    code = "CAPABILITY_PRINCIPAL_MISMATCH"


class CapabilityBudgetError(AuthorityEpochError):
    code = "CAPABILITY_DISPATCH_BUDGET_EXHAUSTED"


class InvalidDispatchPermitError(AuthorityEpochError):
    code = "INVALID_DISPATCH_PERMIT"


@dataclass(frozen=True)
class AuthorityLease:
    lease_id: str
    face_id: str
    scopes: tuple[str, ...]
    authority_epoch: int
    max_dispatches: int
    delegation_parent: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "face_id": self.face_id,
            "scopes": list(self.scopes),
            "authority_epoch": self.authority_epoch,
            "max_dispatches": self.max_dispatches,
            "delegation_parent": self.delegation_parent,
        }


@dataclass(frozen=True)
class GuardedAuthorization:
    authorization: CommitAuthorization
    lease_id: str
    required_scope: str
    authority_epoch: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "authorization": self.authorization.as_dict(),
            "lease_id": self.lease_id,
            "required_scope": self.required_scope,
            "authority_epoch": self.authority_epoch,
        }


@dataclass(frozen=True)
class DispatchPermit:
    permit_id: str
    authorization_id: str
    lease_id: str
    face_id: str
    effect_key: str
    required_scope: str
    authority_epoch: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "permit_id": self.permit_id,
            "authorization_id": self.authorization_id,
            "lease_id": self.lease_id,
            "face_id": self.face_id,
            "effect_key": self.effect_key,
            "required_scope": self.required_scope,
            "authority_epoch": self.authority_epoch,
        }


class AuthorityEpochGate:
    """Non-transferable capability leases with revocation and epoch rotation."""

    def __init__(self, *, authority_epoch: int = 1) -> None:
        if authority_epoch < 1:
            raise ValueError("AUTHORITY_EPOCH_MUST_BE_POSITIVE")
        self.authority_epoch = int(authority_epoch)
        self._lock = threading.RLock()
        self._leases: dict[str, AuthorityLease] = {}
        self._revoked: set[str] = set()
        self._dispatch_count: dict[str, int] = {}

    def issue(
        self,
        *,
        face_id: str,
        scopes: Sequence[str],
        max_dispatches: int = 1,
        delegation_parent: str | None = None,
        lease_id: str | None = None,
    ) -> AuthorityLease:
        normalized = tuple(sorted({scope.strip() for scope in scopes if scope.strip()}))
        if not face_id or not normalized:
            raise ValueError("FACE_AND_NONEMPTY_SCOPE_REQUIRED")
        if max_dispatches < 1:
            raise ValueError("MAX_DISPATCHES_MUST_BE_POSITIVE")
        lease = AuthorityLease(
            lease_id=lease_id or f"LEASE-{uuid.uuid4().hex}",
            face_id=face_id,
            scopes=normalized,
            authority_epoch=self.authority_epoch,
            max_dispatches=int(max_dispatches),
            delegation_parent=delegation_parent,
        )
        with self._lock:
            if lease.lease_id in self._leases:
                raise ValueError("DUPLICATE_LEASE_ID")
            self._leases[lease.lease_id] = lease
            self._dispatch_count[lease.lease_id] = 0
        return lease

    def revoke(self, lease_id: str) -> None:
        with self._lock:
            if lease_id not in self._leases:
                raise UnknownLeaseError()
            self._revoked.add(lease_id)

    def rotate_epoch(self) -> int:
        with self._lock:
            self.authority_epoch += 1
            return self.authority_epoch

    def _lease(self, lease_id: str) -> AuthorityLease:
        try:
            return self._leases[lease_id]
        except KeyError as exc:
            raise UnknownLeaseError() from exc

    def validate_active(
        self,
        lease_id: str,
        *,
        face_id: str,
        required_scope: str,
        require_budget: bool = False,
    ) -> AuthorityLease:
        with self._lock:
            lease = self._lease(lease_id)
            if lease_id in self._revoked:
                raise RevokedLeaseError()
            if lease.authority_epoch != self.authority_epoch:
                raise StaleAuthorityEpochError()
            if lease.face_id != face_id:
                raise CapabilityPrincipalError()
            if required_scope not in lease.scopes:
                raise CapabilityScopeError()
            if require_budget and self._dispatch_count[lease_id] >= lease.max_dispatches:
                raise CapabilityBudgetError()
            return lease

    def consume_dispatch(self, lease_id: str, *, face_id: str, required_scope: str) -> AuthorityLease:
        with self._lock:
            lease = self.validate_active(
                lease_id,
                face_id=face_id,
                required_scope=required_scope,
                require_budget=True,
            )
            self._dispatch_count[lease_id] += 1
            return lease

    def dispatches_used(self, lease_id: str) -> int:
        with self._lock:
            self._lease(lease_id)
            return self._dispatch_count[lease_id]


class AuthorityGuardedMicroController:
    """Adds authority-epoch validation to the v18.7.21 world-effect guard."""

    def __init__(
        self,
        *,
        controller: FaceMicroController | None = None,
        authority_gate: AuthorityEpochGate | None = None,
    ) -> None:
        self.controller = controller or FaceMicroController()
        self.authority_gate = authority_gate or AuthorityEpochGate()
        self._permits: dict[str, DispatchPermit] = {}

    def authorize_with_lease(
        self,
        proposal_id: str,
        *,
        lease_id: str,
        required_scope: str,
        resolution_basis: str = "NO_CONFLICT_SINGLE_ACTION_CLASS",
    ) -> GuardedAuthorization:
        proposals = {p.proposal_id: p for p in self.controller.proposals_for_effects()}
        try:
            proposal = proposals[proposal_id]
        except KeyError as exc:
            raise ValueError("UNKNOWN_PROPOSAL_FOR_AUTHORITY_GATE") from exc
        lease = self.authority_gate.validate_active(
            lease_id,
            face_id=proposal.face_id,
            required_scope=required_scope,
            require_budget=True,
        )
        auth = self.controller.authorize(proposal_id, resolution_basis=resolution_basis)
        return GuardedAuthorization(
            authorization=auth,
            lease_id=lease.lease_id,
            required_scope=required_scope,
            authority_epoch=lease.authority_epoch,
        )

    def prepare_dispatch(self, guarded: GuardedAuthorization) -> DispatchPermit:
        auth = guarded.authorization
        lease = self.authority_gate.consume_dispatch(
            guarded.lease_id,
            face_id=auth.face_id,
            required_scope=guarded.required_scope,
        )
        if lease.authority_epoch != guarded.authority_epoch:
            raise StaleAuthorityEpochError()
        permit_id = "DISPATCH-" + _sha256(
            {
                "authorization_id": auth.authorization_id,
                "lease_id": lease.lease_id,
                "effect_key": auth.effect_key,
                "authority_epoch": lease.authority_epoch,
            }
        )[:24]
        permit = DispatchPermit(
            permit_id=permit_id,
            authorization_id=auth.authorization_id,
            lease_id=lease.lease_id,
            face_id=auth.face_id,
            effect_key=auth.effect_key,
            required_scope=guarded.required_scope,
            authority_epoch=lease.authority_epoch,
        )
        self._permits[permit_id] = permit
        return permit

    def validate_dispatch(self, permit: DispatchPermit) -> bool:
        known = self._permits.get(permit.permit_id)
        if known != permit:
            raise InvalidDispatchPermitError()
        self.authority_gate.validate_active(
            permit.lease_id,
            face_id=permit.face_id,
            required_scope=permit.required_scope,
            require_budget=False,
        )
        if permit.authority_epoch != self.authority_gate.authority_epoch:
            raise StaleAuthorityEpochError()
        return True

    def record_receipt(
        self,
        permit: DispatchPermit,
        *,
        receipt_id: str,
        outcome: dict[str, Any] | str,
    ) -> WorldReceipt:
        if permit.permit_id not in self._permits:
            raise InvalidDispatchPermitError()
        return self.controller.record_receipt(
            permit.authorization_id,
            receipt_id=receipt_id,
            outcome=outcome,
        )


@dataclass(frozen=True)
class ReviewAssignment:
    face_id: str
    role: str
    routing_priority: float
    authority_weight: int = 0


@dataclass(frozen=True)
class ReviewPlan:
    origin_face_id: str
    risk_level: str
    irreversible: bool
    assignments: tuple[ReviewAssignment, ...]
    world_authority_granted: bool = False


class FaceMicroReviewScheduler:
    """Attention scheduler: performance may affect review routing, never authority."""

    def __init__(self, controller: FaceMicroController) -> None:
        self.controller = controller
        self._usage: dict[str, int] = {}

    def plan(
        self,
        *,
        origin_face_id: str,
        candidate_face_ids: Sequence[str],
        risk_level: str = "LOW",
        irreversible: bool = False,
        novel_counterexample_faces: Sequence[str] = (),
    ) -> ReviewPlan:
        risk = risk_level.upper()
        if risk not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("UNKNOWN_RISK_LEVEL")
        unique = [f for f in dict.fromkeys(candidate_face_ids) if f]
        alternatives = [f for f in unique if f != origin_face_id] or unique
        minimum = 2 if irreversible or risk in {"HIGH", "CRITICAL"} else 1
        if len(alternatives) < minimum:
            raise ValueError("INSUFFICIENT_INDEPENDENT_REVIEWERS")

        assignments: list[ReviewAssignment] = []
        forced = [f for f in dict.fromkeys(novel_counterexample_faces) if f in alternatives]
        for face_id in forced:
            cal = self.controller.calibration(face_id)
            assignments.append(
                ReviewAssignment(
                    face_id=face_id,
                    role="COUNTEREXAMPLE_CHALLENGE",
                    routing_priority=cal.routing_priority,
                    authority_weight=0,
                )
            )

        remaining = [f for f in alternatives if f not in {a.face_id for a in assignments}]
        remaining.sort(
            key=lambda f: (
                -(self.controller.calibration(f).routing_priority - 0.05 * self._usage.get(f, 0)),
                f,
            )
        )
        while len(assignments) < minimum:
            face_id = remaining.pop(0)
            cal = self.controller.calibration(face_id)
            role = "RED_TEAM" if not any(a.role == "RED_TEAM" for a in assignments) else "REVIEWER"
            assignments.append(
                ReviewAssignment(
                    face_id=face_id,
                    role=role,
                    routing_priority=cal.routing_priority,
                    authority_weight=0,
                )
            )

        if irreversible or risk in {"HIGH", "CRITICAL"}:
            if not any(a.role in {"RED_TEAM", "COUNTEREXAMPLE_CHALLENGE"} for a in assignments):
                first = assignments[0]
                assignments[0] = ReviewAssignment(
                    face_id=first.face_id,
                    role="RED_TEAM",
                    routing_priority=first.routing_priority,
                    authority_weight=0,
                )

        for assignment in assignments:
            self._usage[assignment.face_id] = self._usage.get(assignment.face_id, 0) + 1
        return ReviewPlan(
            origin_face_id=origin_face_id,
            risk_level=risk,
            irreversible=bool(irreversible),
            assignments=tuple(assignments),
            world_authority_granted=False,
        )


# Compatibility helper added without changing the v18.7.21 public semantics.
def _all_proposals(controller: FaceMicroController) -> tuple[FaceProposal, ...]:
    snapshot = controller.snapshot()
    result: list[FaceProposal] = []
    for effect_key in snapshot["effects"]:
        result.extend(controller.proposals_for(effect_key))
    return tuple(result)


if not hasattr(FaceMicroController, "proposals_for_effects"):
    setattr(FaceMicroController, "proposals_for_effects", _all_proposals)


__all__ = [
    "AUTHORITY_EPOCH_VERSION",
    "AUTHORITY_EPOCH_SCHEMA",
    "AuthorityLease",
    "GuardedAuthorization",
    "DispatchPermit",
    "AuthorityEpochGate",
    "AuthorityGuardedMicroController",
    "ReviewAssignment",
    "ReviewPlan",
    "FaceMicroReviewScheduler",
    "AuthorityEpochError",
    "UnknownLeaseError",
    "RevokedLeaseError",
    "StaleAuthorityEpochError",
    "CapabilityScopeError",
    "CapabilityPrincipalError",
    "CapabilityBudgetError",
    "InvalidDispatchPermitError",
]
