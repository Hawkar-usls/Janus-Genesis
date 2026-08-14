# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.23 — cancellation/recovery, multi-effect sagas, and fairness.

This additive layer extends v18.7.22 without executing external side effects.
It closes the simple AUTHORIZED-but-revoked liveness gap while preserving a
critical uncertainty fence: once a dispatch permit has passed the immediate
pre-effect validation boundary, absence of a receipt is not proof that the
world effect did not occur.

Core invariants:
- cancellation before the dispatch boundary may safely release authorization;
- a validated-but-unreceipted dispatch is UNDETERMINED, not silently retried;
- recovery requires an explicit cancellation lineage and a new authorization;
- old permits remain invalid after cancellation/recovery;
- multi-effect work is a saga, not falsely claimed atomicity;
- compensation is a new protected world effect with its own authorization and receipt;
- irreversible partial settlement is surfaced to host review, never hidden;
- review routing may optimize attention but bounded bypass prevents starvation;
- fairness tickets carry zero world authority.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from genesis_v18_7_21_face_microcontrol import (
    EffectStatus,
    FaceMicroController,
    ProposalStatus,
    WorldReceipt,
)
from genesis_v18_7_22_face_authority_epoch import (
    AuthorityEpochGate,
    AuthorityGuardedMicroController,
    DispatchPermit,
    GuardedAuthorization,
)

RECOVERY_SAGA_VERSION = "18.7.23"
RECOVERY_SAGA_SCHEMA = "janus.genesis.face_recovery_saga.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class RecoverySagaError(RuntimeError):
    code = "RECOVERY_SAGA_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class AuthorizationCanceledError(RecoverySagaError):
    code = "AUTHORIZATION_CANCELED"


class RecoveryRequiredError(RecoverySagaError):
    code = "EXPLICIT_RECOVERY_REQUIRED"


class CannotCancelSettledError(RecoverySagaError):
    code = "CANNOT_CANCEL_SETTLED_EFFECT"


class DispatchOutcomeUndeterminedError(RecoverySagaError):
    code = "DISPATCH_OUTCOME_UNDETERMINED"


class NoActiveCancellationError(RecoverySagaError):
    code = "NO_ACTIVE_CANCELLATION"


class UnsafeRecoveryError(RecoverySagaError):
    code = "RECOVERY_BLOCKED_BY_UNRESOLVED_WORLD_UNCERTAINTY"


class SagaState(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    NEEDS_COMPENSATION = "NEEDS_COMPENSATION"
    PARTIAL_IRREVERSIBLE = "PARTIAL_IRREVERSIBLE_REQUIRES_HOST_DECISION"
    COMPENSATING = "COMPENSATING"
    COMPENSATED_ABORTED = "COMPENSATED_ABORTED"
    ABORTED = "ABORTED"
    SETTLED = "SETTLED"


class SagaStepState(str, Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    DISPATCH_PERMITTED = "DISPATCH_PERMITTED"
    DISPATCH_VALIDATED = "DISPATCH_VALIDATED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    COMPENSATION_REQUIRED = "COMPENSATION_REQUIRED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"


class CancellationState(str, Enum):
    CANCELED_REOPENABLE = "CANCELED_REOPENABLE"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RECONCILED_NO_EFFECT = "RECONCILED_NO_EFFECT"
    SUPERSEDED_BY_RECOVERY = "SUPERSEDED_BY_RECOVERY"


@dataclass
class CancellationRecord:
    cancellation_id: str
    authorization_id: str
    effect_key: str
    face_id: str
    reason: str
    state: CancellationState
    invalidated_permit_ids: tuple[str, ...]
    validated_permit_ids: tuple[str, ...]
    reconciliation_evidence_ref: str | None = None
    replacement_authorization_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "cancellation_id": self.cancellation_id,
            "authorization_id": self.authorization_id,
            "effect_key": self.effect_key,
            "face_id": self.face_id,
            "reason": self.reason,
            "state": self.state.value,
            "invalidated_permit_ids": list(self.invalidated_permit_ids),
            "validated_permit_ids": list(self.validated_permit_ids),
            "reconciliation_evidence_ref": self.reconciliation_evidence_ref,
            "replacement_authorization_id": self.replacement_authorization_id,
        }


@dataclass(frozen=True)
class RecoveryLink:
    cancellation_id: str
    prior_authorization_id: str
    replacement_authorization_id: str
    effect_key: str
    recovery_basis: str


class RecoverableAuthorityGuardedMicroController(AuthorityGuardedMicroController):
    """v18.7.22 guard plus append-only cancellation/recovery lineage.

    A dispatch permit that has already passed ``validate_dispatch`` is treated as
    potentially executed. Without a receipt, the outcome is UNDETERMINED. The
    effect cannot be reopened until an authoritative no-effect reconciliation is
    supplied. This prevents a retry from turning network uncertainty into a
    duplicate world effect.
    """

    def __init__(
        self,
        *,
        controller: FaceMicroController | None = None,
        authority_gate: AuthorityEpochGate | None = None,
    ) -> None:
        super().__init__(controller=controller, authority_gate=authority_gate)
        self._recovery_lock = threading.RLock()
        self._validated_permits: set[str] = set()
        self._invalidated_permits: set[str] = set()
        self._cancellations: dict[str, CancellationRecord] = {}
        self._active_cancellation_by_effect: dict[str, str] = {}
        self._recovery_links: list[RecoveryLink] = []

    def _proposal_by_id(self, proposal_id: str):
        for proposal in self.controller.proposals_for_effects():
            if proposal.proposal_id == proposal_id:
                return proposal
        raise ValueError("UNKNOWN_PROPOSAL_FOR_RECOVERY_GATE")

    def authorize_with_lease(
        self,
        proposal_id: str,
        *,
        lease_id: str,
        required_scope: str,
        resolution_basis: str = "NO_CONFLICT_SINGLE_ACTION_CLASS",
    ) -> GuardedAuthorization:
        proposal = self._proposal_by_id(proposal_id)
        if proposal.effect_key in self._active_cancellation_by_effect:
            raise RecoveryRequiredError("USE_RECOVER_WITH_LEASE")
        return super().authorize_with_lease(
            proposal_id,
            lease_id=lease_id,
            required_scope=required_scope,
            resolution_basis=resolution_basis,
        )

    def prepare_dispatch(self, guarded: GuardedAuthorization) -> DispatchPermit:
        if guarded.authorization.authorization_id in self._cancellations:
            raise AuthorizationCanceledError()
        return super().prepare_dispatch(guarded)

    def validate_dispatch(self, permit: DispatchPermit) -> bool:
        with self._recovery_lock:
            if permit.permit_id in self._invalidated_permits:
                raise AuthorizationCanceledError()
            if permit.authorization_id in self._cancellations:
                raise AuthorizationCanceledError()
            ok = super().validate_dispatch(permit)
            if ok:
                self._validated_permits.add(permit.permit_id)
            return ok

    def record_receipt(
        self,
        permit: DispatchPermit,
        *,
        receipt_id: str,
        outcome: Mapping[str, Any] | str,
    ) -> WorldReceipt:
        with self._recovery_lock:
            if permit.permit_id in self._invalidated_permits:
                raise AuthorizationCanceledError()
            if permit.authorization_id in self._cancellations:
                raise AuthorizationCanceledError()
            return super().record_receipt(permit, receipt_id=receipt_id, outcome=dict(outcome) if isinstance(outcome, Mapping) else outcome)

    def _release_base_authorization(self, authorization_id: str) -> None:
        """Release the active slot while retaining old authorization provenance.

        v18.7.21 deliberately has no cancellation primitive. This descendant
        performs a narrow, lock-protected release of the current authorization
        mapping and recomputes proposal states. The historical authorization
        object is kept in the parent's append-only authorization dictionary.
        """
        ctl = self.controller
        with ctl._lock:  # descendant maintenance of parent state under parent lock
            try:
                auth = ctl._authorizations[authorization_id]
            except KeyError as exc:
                raise ValueError("UNKNOWN_AUTHORIZATION_FOR_CANCELLATION") from exc
            if ctl.receipt_for(auth.effect_key) is not None:
                raise CannotCancelSettledError()
            current = ctl._authorization_by_effect.get(auth.effect_key)
            if current != authorization_id:
                raise RecoverySagaError("AUTHORIZATION_NOT_CURRENT_FOR_EFFECT")
            del ctl._authorization_by_effect[auth.effect_key]
            proposals = list(ctl.proposals_for(auth.effect_key))
            action_hashes = {p.action_hash for p in proposals}
            if len(action_hashes) > 1:
                for p in proposals:
                    p.status = ProposalStatus.HOLD
            elif proposals:
                first = True
                for p in proposals:
                    p.status = ProposalStatus.PROPOSED if first else ProposalStatus.EQUIVALENT
                    first = False

    def cancel_authorization(
        self,
        guarded: GuardedAuthorization,
        *,
        reason: str,
        cancellation_id: str | None = None,
    ) -> CancellationRecord:
        if not reason.strip():
            raise ValueError("CANCELLATION_REASON_REQUIRED")
        auth = guarded.authorization
        with self._recovery_lock:
            existing_id = self._active_cancellation_by_effect.get(auth.effect_key)
            if existing_id is not None:
                return self._cancellations[existing_id]
            if self.controller.receipt_for(auth.effect_key) is not None:
                raise CannotCancelSettledError()

            permits = [p for p in self._permits.values() if p.authorization_id == auth.authorization_id]
            permit_ids = tuple(sorted(p.permit_id for p in permits))
            validated = tuple(sorted(pid for pid in permit_ids if pid in self._validated_permits))
            self._invalidated_permits.update(permit_ids)

            state = (
                CancellationState.RECONCILIATION_REQUIRED
                if validated
                else CancellationState.CANCELED_REOPENABLE
            )
            record = CancellationRecord(
                cancellation_id=cancellation_id or f"CANCEL-{uuid.uuid4().hex}",
                authorization_id=auth.authorization_id,
                effect_key=auth.effect_key,
                face_id=auth.face_id,
                reason=reason.strip(),
                state=state,
                invalidated_permit_ids=permit_ids,
                validated_permit_ids=validated,
            )
            self._cancellations[record.cancellation_id] = record
            self._active_cancellation_by_effect[auth.effect_key] = record.cancellation_id

            if not validated:
                self._release_base_authorization(auth.authorization_id)
            return record

    def reconcile_no_effect(
        self,
        effect_key: str,
        *,
        evidence_ref: str,
    ) -> CancellationRecord:
        if not evidence_ref.strip():
            raise ValueError("RECONCILIATION_EVIDENCE_REQUIRED")
        with self._recovery_lock:
            cancellation_id = self._active_cancellation_by_effect.get(effect_key)
            if cancellation_id is None:
                raise NoActiveCancellationError()
            record = self._cancellations[cancellation_id]
            if record.state is not CancellationState.RECONCILIATION_REQUIRED:
                return record
            if self.controller.receipt_for(effect_key) is not None:
                raise CannotCancelSettledError()
            self._release_base_authorization(record.authorization_id)
            record.reconciliation_evidence_ref = evidence_ref.strip()
            record.state = CancellationState.RECONCILED_NO_EFFECT
            return record

    def recover_with_lease(
        self,
        proposal_id: str,
        *,
        lease_id: str,
        required_scope: str,
        recovery_basis: str,
    ) -> GuardedAuthorization:
        if not recovery_basis.strip():
            raise ValueError("RECOVERY_BASIS_REQUIRED")
        proposal = self._proposal_by_id(proposal_id)
        with self._recovery_lock:
            cancellation_id = self._active_cancellation_by_effect.get(proposal.effect_key)
            if cancellation_id is None:
                raise NoActiveCancellationError()
            record = self._cancellations[cancellation_id]
            if record.state is CancellationState.RECONCILIATION_REQUIRED:
                raise UnsafeRecoveryError()
            if record.state is CancellationState.SUPERSEDED_BY_RECOVERY:
                raise RecoverySagaError("RECOVERY_ALREADY_COMPLETED")
            if self.controller.effect_status(proposal.effect_key) is EffectStatus.SETTLED:
                raise CannotCancelSettledError()

            basis = f"RECOVERY_AFTER:{record.cancellation_id}:{recovery_basis.strip()}"
            guarded = super().authorize_with_lease(
                proposal_id,
                lease_id=lease_id,
                required_scope=required_scope,
                resolution_basis=basis,
            )
            record.replacement_authorization_id = guarded.authorization.authorization_id
            record.state = CancellationState.SUPERSEDED_BY_RECOVERY
            self._recovery_links.append(
                RecoveryLink(
                    cancellation_id=record.cancellation_id,
                    prior_authorization_id=record.authorization_id,
                    replacement_authorization_id=guarded.authorization.authorization_id,
                    effect_key=record.effect_key,
                    recovery_basis=recovery_basis.strip(),
                )
            )
            del self._active_cancellation_by_effect[proposal.effect_key]
            return guarded

    def cancellation_for_effect(self, effect_key: str) -> CancellationRecord | None:
        with self._recovery_lock:
            cid = self._active_cancellation_by_effect.get(effect_key)
            if cid is not None:
                return self._cancellations[cid]
            historical = [r for r in self._cancellations.values() if r.effect_key == effect_key]
            return historical[-1] if historical else None

    def recovery_snapshot(self) -> dict[str, Any]:
        with self._recovery_lock:
            return {
                "schema": RECOVERY_SAGA_SCHEMA,
                "version": RECOVERY_SAGA_VERSION,
                "invariants": {
                    "validated_dispatch_without_receipt_is_safe_to_retry": False,
                    "cancellation_erases_prior_authorization": False,
                    "old_permit_survives_cancellation": False,
                    "recovery_requires_explicit_lineage": True,
                    "external_side_effect_execution_in_module": False,
                },
                "cancellations": [r.as_dict() for r in self._cancellations.values()],
                "recovery_links": [
                    {
                        "cancellation_id": link.cancellation_id,
                        "prior_authorization_id": link.prior_authorization_id,
                        "replacement_authorization_id": link.replacement_authorization_id,
                        "effect_key": link.effect_key,
                        "recovery_basis": link.recovery_basis,
                    }
                    for link in self._recovery_links
                ],
            }


@dataclass
class SagaStep:
    step_id: str
    proposal_id: str
    lease_id: str
    required_scope: str
    reversible: bool = True
    compensation_proposal_id: str | None = None
    compensation_lease_id: str | None = None
    compensation_scope: str | None = None
    state: SagaStepState = SagaStepState.PENDING
    guarded: GuardedAuthorization | None = None
    permit: DispatchPermit | None = None
    receipt_id: str | None = None
    compensation_guarded: GuardedAuthorization | None = None
    compensation_permit: DispatchPermit | None = None
    compensation_receipt_id: str | None = None


@dataclass
class SagaRecord:
    saga_id: str
    steps: list[SagaStep]
    state: SagaState = SagaState.OPEN
    failure_step_id: str | None = None
    failure_reason: str | None = None
    audit: list[dict[str, Any]] = field(default_factory=list)


class MultiEffectSagaCoordinator:
    """Sequential multi-effect coordinator with explicit compensation semantics.

    The coordinator does not claim distributed atomicity. Every forward step and
    every compensation step must pass the same protected effect authorization,
    dispatch validation, and receipt boundary as any other external effect.
    """

    def __init__(self, guard: RecoverableAuthorityGuardedMicroController) -> None:
        self.guard = guard
        self._lock = threading.RLock()
        self._sagas: dict[str, SagaRecord] = {}

    def create(self, *, steps: Sequence[SagaStep], saga_id: str | None = None) -> SagaRecord:
        if not steps:
            raise ValueError("SAGA_REQUIRES_STEPS")
        ids = [s.step_id for s in steps]
        if len(ids) != len(set(ids)) or any(not i for i in ids):
            raise ValueError("SAGA_STEP_IDS_MUST_BE_UNIQUE_AND_NONEMPTY")
        record = SagaRecord(saga_id=saga_id or f"SAGA-{uuid.uuid4().hex}", steps=list(steps))
        with self._lock:
            if record.saga_id in self._sagas:
                raise ValueError("DUPLICATE_SAGA_ID")
            self._sagas[record.saga_id] = record
            record.audit.append({"event": "SAGA_CREATED", "step_count": len(record.steps)})
        return record

    def _record(self, saga_id: str) -> SagaRecord:
        try:
            return self._sagas[saga_id]
        except KeyError as exc:
            raise RecoverySagaError("UNKNOWN_SAGA") from exc

    @staticmethod
    def _step(record: SagaRecord, step_id: str) -> SagaStep:
        for step in record.steps:
            if step.step_id == step_id:
                return step
        raise RecoverySagaError("UNKNOWN_SAGA_STEP")

    @staticmethod
    def _prior_steps(record: SagaRecord, step: SagaStep) -> list[SagaStep]:
        index = record.steps.index(step)
        return record.steps[:index]

    def authorize_step(self, saga_id: str, step_id: str, *, resolution_basis: str = "SAGA_FORWARD_STEP") -> GuardedAuthorization:
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.state is not SagaStepState.PENDING:
                raise RecoverySagaError("SAGA_STEP_NOT_PENDING")
            if any(p.state is not SagaStepState.SETTLED for p in self._prior_steps(record, step)):
                raise RecoverySagaError("SAGA_PRIOR_STEP_NOT_SETTLED")
            guarded = self.guard.authorize_with_lease(
                step.proposal_id,
                lease_id=step.lease_id,
                required_scope=step.required_scope,
                resolution_basis=resolution_basis,
            )
            step.guarded = guarded
            step.state = SagaStepState.AUTHORIZED
            record.state = SagaState.IN_PROGRESS
            record.audit.append({"event": "STEP_AUTHORIZED", "step_id": step_id, "authorization_id": guarded.authorization.authorization_id})
            return guarded

    def prepare_step_dispatch(self, saga_id: str, step_id: str) -> DispatchPermit:
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.state is not SagaStepState.AUTHORIZED or step.guarded is None:
                raise RecoverySagaError("SAGA_STEP_NOT_AUTHORIZED")
            permit = self.guard.prepare_dispatch(step.guarded)
            step.permit = permit
            step.state = SagaStepState.DISPATCH_PERMITTED
            record.audit.append({"event": "STEP_DISPATCH_PERMITTED", "step_id": step_id, "permit_id": permit.permit_id})
            return permit

    def validate_step_dispatch(self, saga_id: str, step_id: str) -> bool:
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.state is not SagaStepState.DISPATCH_PERMITTED or step.permit is None:
                raise RecoverySagaError("SAGA_STEP_DISPATCH_NOT_PREPARED")
            ok = self.guard.validate_dispatch(step.permit)
            if ok:
                step.state = SagaStepState.DISPATCH_VALIDATED
                record.audit.append({"event": "STEP_DISPATCH_VALIDATED", "step_id": step_id})
            return ok

    def record_step_receipt(self, saga_id: str, step_id: str, *, receipt_id: str, outcome: Mapping[str, Any] | str) -> WorldReceipt:
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.state is not SagaStepState.DISPATCH_VALIDATED or step.permit is None:
                raise RecoverySagaError("SAGA_STEP_NOT_AT_RECEIPT_BOUNDARY")
            receipt = self.guard.record_receipt(step.permit, receipt_id=receipt_id, outcome=outcome)
            step.receipt_id = receipt.receipt_id
            step.state = SagaStepState.SETTLED
            record.audit.append({"event": "STEP_SETTLED", "step_id": step_id, "receipt_id": receipt.receipt_id})
            if all(s.state is SagaStepState.SETTLED for s in record.steps):
                record.state = SagaState.SETTLED
                record.audit.append({"event": "SAGA_SETTLED"})
            return receipt

    def fail(self, saga_id: str, step_id: str, *, reason: str) -> SagaRecord:
        if not reason.strip():
            raise ValueError("SAGA_FAILURE_REASON_REQUIRED")
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.state is SagaStepState.SETTLED:
                raise RecoverySagaError("CANNOT_FAIL_ALREADY_SETTLED_STEP")
            step.state = SagaStepState.FAILED
            record.failure_step_id = step_id
            record.failure_reason = reason.strip()
            settled_prior = [s for s in self._prior_steps(record, step) if s.state is SagaStepState.SETTLED]
            irreversible = [s for s in settled_prior if not s.reversible]
            if irreversible:
                record.state = SagaState.PARTIAL_IRREVERSIBLE
            else:
                compensation_needed = []
                for prior in settled_prior:
                    if prior.compensation_proposal_id and prior.compensation_lease_id and prior.compensation_scope:
                        prior.state = SagaStepState.COMPENSATION_REQUIRED
                        compensation_needed.append(prior)
                    else:
                        record.state = SagaState.PARTIAL_IRREVERSIBLE
                        record.audit.append({"event": "MISSING_COMPENSATION_PLAN", "step_id": prior.step_id})
                        break
                else:
                    record.state = SagaState.NEEDS_COMPENSATION if compensation_needed else SagaState.ABORTED
            record.audit.append({"event": "SAGA_FAILED", "step_id": step_id, "reason": reason.strip(), "state": record.state.value})
            return record

    def authorize_compensation(self, saga_id: str, step_id: str) -> GuardedAuthorization:
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.state is not SagaStepState.COMPENSATION_REQUIRED:
                raise RecoverySagaError("COMPENSATION_NOT_REQUIRED_FOR_STEP")
            if not (step.compensation_proposal_id and step.compensation_lease_id and step.compensation_scope):
                raise RecoverySagaError("COMPENSATION_PLAN_INCOMPLETE")
            guarded = self.guard.authorize_with_lease(
                step.compensation_proposal_id,
                lease_id=step.compensation_lease_id,
                required_scope=step.compensation_scope,
                resolution_basis=f"SAGA_COMPENSATION:{record.saga_id}:{step.step_id}",
            )
            step.compensation_guarded = guarded
            step.state = SagaStepState.COMPENSATING
            record.state = SagaState.COMPENSATING
            record.audit.append({"event": "COMPENSATION_AUTHORIZED", "step_id": step_id, "authorization_id": guarded.authorization.authorization_id})
            return guarded

    def prepare_compensation_dispatch(self, saga_id: str, step_id: str) -> DispatchPermit:
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.state is not SagaStepState.COMPENSATING or step.compensation_guarded is None:
                raise RecoverySagaError("COMPENSATION_NOT_AUTHORIZED")
            permit = self.guard.prepare_dispatch(step.compensation_guarded)
            step.compensation_permit = permit
            record.audit.append({"event": "COMPENSATION_DISPATCH_PERMITTED", "step_id": step_id, "permit_id": permit.permit_id})
            return permit

    def validate_compensation_dispatch(self, saga_id: str, step_id: str) -> bool:
        with self._lock:
            step = self._step(self._record(saga_id), step_id)
            if step.compensation_permit is None:
                raise RecoverySagaError("COMPENSATION_DISPATCH_NOT_PREPARED")
            return self.guard.validate_dispatch(step.compensation_permit)

    def record_compensation_receipt(self, saga_id: str, step_id: str, *, receipt_id: str, outcome: Mapping[str, Any] | str) -> WorldReceipt:
        with self._lock:
            record = self._record(saga_id)
            step = self._step(record, step_id)
            if step.compensation_permit is None:
                raise RecoverySagaError("COMPENSATION_DISPATCH_NOT_PREPARED")
            receipt = self.guard.record_receipt(step.compensation_permit, receipt_id=receipt_id, outcome=outcome)
            step.compensation_receipt_id = receipt.receipt_id
            step.state = SagaStepState.COMPENSATED
            record.audit.append({"event": "STEP_COMPENSATED", "step_id": step_id, "receipt_id": receipt.receipt_id})
            if all(s.state in {SagaStepState.COMPENSATED, SagaStepState.FAILED, SagaStepState.PENDING} for s in record.steps):
                if not any(s.state is SagaStepState.COMPENSATION_REQUIRED for s in record.steps):
                    record.state = SagaState.COMPENSATED_ABORTED
                    record.audit.append({"event": "SAGA_COMPENSATED_ABORTED"})
            return receipt

    def snapshot(self, saga_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._record(saga_id)
            return {
                "saga_id": record.saga_id,
                "state": record.state.value,
                "failure_step_id": record.failure_step_id,
                "failure_reason": record.failure_reason,
                "atomicity_claimed": False,
                "external_side_effect_execution_in_module": False,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "proposal_id": s.proposal_id,
                        "state": s.state.value,
                        "reversible": s.reversible,
                        "receipt_id": s.receipt_id,
                        "compensation_proposal_id": s.compensation_proposal_id,
                        "compensation_receipt_id": s.compensation_receipt_id,
                    }
                    for s in record.steps
                ],
                "audit": list(record.audit),
            }


@dataclass
class FairReviewTicket:
    ticket_id: str
    effect_key: str
    face_id: str
    routing_priority: float
    sequence: int
    bypass_count: int = 0
    authority_weight: int = 0


class BoundedBypassReviewQueue:
    """Attention queue with bounded bypass and zero authority weight.

    Routing priority may choose among ordinary waiters, but a ticket that has
    been bypassed ``max_bypass`` times becomes mandatory. Under continued
    service, an enqueued ticket therefore cannot be starved by an endless stream
    of higher-routing-priority faces.
    """

    def __init__(self, *, max_bypass: int = 3) -> None:
        if max_bypass < 1:
            raise ValueError("MAX_BYPASS_MUST_BE_POSITIVE")
        self.max_bypass = int(max_bypass)
        self._lock = threading.RLock()
        self._sequence = 0
        self._tickets: dict[str, FairReviewTicket] = {}

    def enqueue(
        self,
        *,
        effect_key: str,
        face_id: str,
        routing_priority: float,
        ticket_id: str | None = None,
    ) -> FairReviewTicket:
        if not effect_key or not face_id:
            raise ValueError("EFFECT_AND_FACE_REQUIRED")
        with self._lock:
            self._sequence += 1
            ticket = FairReviewTicket(
                ticket_id=ticket_id or f"REVIEW-{uuid.uuid4().hex}",
                effect_key=effect_key,
                face_id=face_id,
                routing_priority=float(routing_priority),
                sequence=self._sequence,
                bypass_count=0,
                authority_weight=0,
            )
            if ticket.ticket_id in self._tickets:
                raise ValueError("DUPLICATE_REVIEW_TICKET")
            self._tickets[ticket.ticket_id] = ticket
            return ticket

    def next_ticket(self) -> FairReviewTicket | None:
        with self._lock:
            if not self._tickets:
                return None
            candidates = list(self._tickets.values())
            mandatory = [t for t in candidates if t.bypass_count >= self.max_bypass]
            if mandatory:
                selected = min(mandatory, key=lambda t: (t.sequence, t.ticket_id))
            else:
                selected = min(candidates, key=lambda t: (-t.routing_priority, t.sequence, t.ticket_id))
            for ticket in candidates:
                if ticket.ticket_id != selected.ticket_id:
                    ticket.bypass_count += 1
            del self._tickets[selected.ticket_id]
            return selected

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_bypass": self.max_bypass,
                "authority_weight_for_all_tickets": 0,
                "pending": [
                    {
                        "ticket_id": t.ticket_id,
                        "effect_key": t.effect_key,
                        "face_id": t.face_id,
                        "routing_priority": t.routing_priority,
                        "sequence": t.sequence,
                        "bypass_count": t.bypass_count,
                        "authority_weight": t.authority_weight,
                    }
                    for t in sorted(self._tickets.values(), key=lambda x: x.sequence)
                ],
            }


__all__ = [
    "RECOVERY_SAGA_VERSION",
    "RECOVERY_SAGA_SCHEMA",
    "AuthorizationCanceledError",
    "RecoveryRequiredError",
    "CannotCancelSettledError",
    "DispatchOutcomeUndeterminedError",
    "NoActiveCancellationError",
    "UnsafeRecoveryError",
    "CancellationState",
    "CancellationRecord",
    "RecoveryLink",
    "RecoverableAuthorityGuardedMicroController",
    "SagaState",
    "SagaStepState",
    "SagaStep",
    "SagaRecord",
    "MultiEffectSagaCoordinator",
    "FairReviewTicket",
    "BoundedBypassReviewQueue",
]
