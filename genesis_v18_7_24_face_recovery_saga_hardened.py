# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.24 — hardened recovery uncertainty fence.

v18.7.23 introduced cancellation/recovery, saga coordination, and bounded-bypass
fairness. This hardening layer preserves that work while distinguishing two
very different facts:

1. a canceled permit must never be used for a new dispatch;
2. an authoritative late receipt for a permit that *already passed* the
   immediate pre-effect validation boundary may still prove that the external
   effect happened and therefore must be allowed to settle the effect.

The module still executes no external side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from genesis_v18_7_21_face_microcontrol import WorldReceipt
from genesis_v18_7_22_face_authority_epoch import (
    AuthorityEpochGate,
    AuthorityGuardedMicroController,
    DispatchPermit,
    GuardedAuthorization,
)
from genesis_v18_7_23_face_recovery_saga import (
    AuthorizationCanceledError,
    BoundedBypassReviewQueue,
    CancellationRecord,
    CancellationState,
    FairReviewTicket,
    MultiEffectSagaCoordinator,
    NoActiveCancellationError,
    RecoverableAuthorityGuardedMicroController,
    RecoveryLink,
    RecoverySagaError,
    SagaRecord,
    SagaState,
    SagaStep,
    SagaStepState,
    UnsafeRecoveryError,
)

HARDENED_RECOVERY_VERSION = "18.7.24"
HARDENED_RECOVERY_SCHEMA = "janus.genesis.face_recovery_saga_hardened.v1"


class LateReceiptConflictError(RecoverySagaError):
    code = "LATE_RECEIPT_CONFLICTS_WITH_RECOVERY_ASSUMPTION"


@dataclass(frozen=True)
class ReconciliationResolution:
    cancellation_id: str
    authorization_id: str
    effect_key: str
    outcome: str
    evidence_ref: str

    def as_dict(self) -> dict[str, str]:
        return {
            "cancellation_id": self.cancellation_id,
            "authorization_id": self.authorization_id,
            "effect_key": self.effect_key,
            "outcome": self.outcome,
            "evidence_ref": self.evidence_ref,
        }


class HardenedRecoverableAuthorityGuardedMicroController(RecoverableAuthorityGuardedMicroController):
    """Recovery guard that blocks re-dispatch but admits valid late settlement evidence."""

    def __init__(
        self,
        *,
        controller=None,
        authority_gate: AuthorityEpochGate | None = None,
    ) -> None:
        super().__init__(controller=controller, authority_gate=authority_gate)
        self._canceled_authorization_ids: set[str] = set()
        self._reconciliation_resolutions: dict[str, ReconciliationResolution] = {}

    def _cancellation_for_authorization(self, authorization_id: str) -> CancellationRecord | None:
        for record in self._cancellations.values():
            if record.authorization_id == authorization_id:
                return record
        return None

    def cancel_authorization(
        self,
        guarded: GuardedAuthorization,
        *,
        reason: str,
        cancellation_id: str | None = None,
    ) -> CancellationRecord:
        record = super().cancel_authorization(
            guarded,
            reason=reason,
            cancellation_id=cancellation_id,
        )
        self._canceled_authorization_ids.add(record.authorization_id)
        return record

    def prepare_dispatch(self, guarded: GuardedAuthorization) -> DispatchPermit:
        if guarded.authorization.authorization_id in self._canceled_authorization_ids:
            raise AuthorizationCanceledError()
        return AuthorityGuardedMicroController.prepare_dispatch(self, guarded)

    def validate_dispatch(self, permit: DispatchPermit) -> bool:
        if permit.authorization_id in self._canceled_authorization_ids:
            raise AuthorizationCanceledError()
        ok = AuthorityGuardedMicroController.validate_dispatch(self, permit)
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
        """Record ordinary or reconciliation-time late receipt.

        If the authorization was canceled *after* this permit passed the
        pre-effect validation boundary, a late authoritative receipt is evidence
        that the effect settled. It is admitted even though the permit is now
        invalid for any new dispatch. If the system already reconciled the case
        as NO_EFFECT or recovered onto a replacement authorization, the late
        receipt is contradictory evidence and is quarantined as a conflict.
        """
        record = self._cancellation_for_authorization(permit.authorization_id)
        if record is None:
            return AuthorityGuardedMicroController.record_receipt(
                self,
                permit,
                receipt_id=receipt_id,
                outcome=dict(outcome) if isinstance(outcome, Mapping) else outcome,
            )

        if (
            record.state is CancellationState.RECONCILIATION_REQUIRED
            and permit.permit_id in record.validated_permit_ids
        ):
            receipt = AuthorityGuardedMicroController.record_receipt(
                self,
                permit,
                receipt_id=receipt_id,
                outcome=dict(outcome) if isinstance(outcome, Mapping) else outcome,
            )
            self._reconciliation_resolutions[record.cancellation_id] = ReconciliationResolution(
                cancellation_id=record.cancellation_id,
                authorization_id=record.authorization_id,
                effect_key=record.effect_key,
                outcome="LATE_RECEIPT_SETTLED_EFFECT",
                evidence_ref=receipt.receipt_id,
            )
            self._active_cancellation_by_effect.pop(record.effect_key, None)
            return receipt

        raise LateReceiptConflictError(
            f"authorization={permit.authorization_id}; cancellation_state={record.state.value}"
        )

    def reconcile_no_effect(self, effect_key: str, *, evidence_ref: str) -> CancellationRecord:
        record = super().reconcile_no_effect(effect_key, evidence_ref=evidence_ref)
        self._reconciliation_resolutions[record.cancellation_id] = ReconciliationResolution(
            cancellation_id=record.cancellation_id,
            authorization_id=record.authorization_id,
            effect_key=record.effect_key,
            outcome="AUTHORITATIVE_NO_EFFECT_RECONCILIATION",
            evidence_ref=evidence_ref.strip(),
        )
        return record

    def recover_with_lease(
        self,
        proposal_id: str,
        *,
        lease_id: str,
        required_scope: str,
        recovery_basis: str,
    ) -> GuardedAuthorization:
        proposal = self._proposal_by_id(proposal_id)
        active = self._active_cancellation_by_effect.get(proposal.effect_key)
        if active is not None:
            record = self._cancellations[active]
            if record.state is CancellationState.RECONCILIATION_REQUIRED:
                raise UnsafeRecoveryError()
        return super().recover_with_lease(
            proposal_id,
            lease_id=lease_id,
            required_scope=required_scope,
            recovery_basis=recovery_basis,
        )

    def hardened_snapshot(self) -> dict[str, Any]:
        base = self.recovery_snapshot()
        base.update(
            {
                "schema": HARDENED_RECOVERY_SCHEMA,
                "version": HARDENED_RECOVERY_VERSION,
                "additional_invariants": {
                    "canceled_permit_can_dispatch_again": False,
                    "validated_unreceipted_dispatch_means_no_effect": False,
                    "late_authoritative_receipt_may_settle_uncertain_effect": True,
                    "late_receipt_after_no_effect_reconciliation_is_auto_accepted": False,
                    "external_side_effect_execution_in_module": False,
                },
                "reconciliation_resolutions": [
                    resolution.as_dict()
                    for resolution in self._reconciliation_resolutions.values()
                ],
            }
        )
        return base


__all__ = [
    "HARDENED_RECOVERY_VERSION",
    "HARDENED_RECOVERY_SCHEMA",
    "LateReceiptConflictError",
    "ReconciliationResolution",
    "HardenedRecoverableAuthorityGuardedMicroController",
    "BoundedBypassReviewQueue",
    "FairReviewTicket",
    "MultiEffectSagaCoordinator",
    "SagaRecord",
    "SagaState",
    "SagaStep",
    "SagaStepState",
    "CancellationRecord",
    "CancellationState",
    "RecoveryLink",
    "NoActiveCancellationError",
    "UnsafeRecoveryError",
]
