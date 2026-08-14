import unittest

from genesis_v18_7_21_face_microcontrol import EffectStatus, FaceMicroController
from genesis_v18_7_22_face_authority_epoch import AuthorityEpochGate
from genesis_v18_7_23_face_recovery_saga import (
    AuthorizationCanceledError,
    BoundedBypassReviewQueue,
    CancellationState,
    MultiEffectSagaCoordinator,
    SagaState,
    SagaStep,
    UnsafeRecoveryError,
)
from genesis_v18_7_24_face_recovery_saga_hardened import (
    HardenedRecoverableAuthorityGuardedMicroController,
    LateReceiptConflictError,
)


class HardenedRecoveryTests(unittest.TestCase):
    def _proposal(self, ctl, *, effect_key="PAYMENT:42", face_id="FACE_A", op="pay"):
        return ctl.submit(
            face_id=face_id,
            intent_id=op.upper(),
            effect_key=effect_key,
            world_scope="BANK:ACCOUNT-A",
            action={"op": op, "effect": effect_key},
        )

    def test_predispatch_cancellation_releases_effect_for_explicit_recovery(self):
        base = FaceMicroController()
        proposal = self._proposal(base)
        gate = AuthorityEpochGate()
        lease1 = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guard = HardenedRecoverableAuthorityGuardedMicroController(controller=base, authority_gate=gate)

        guarded1 = guard.authorize_with_lease(
            proposal.proposal_id,
            lease_id=lease1.lease_id,
            required_scope="PAYMENT:SEND",
        )
        old_permit = guard.prepare_dispatch(guarded1)
        gate.revoke(lease1.lease_id)
        cancellation = guard.cancel_authorization(
            guarded1,
            reason="lease revoked before immediate pre-effect validation",
        )
        self.assertEqual(cancellation.state, CancellationState.CANCELED_REOPENABLE)
        self.assertEqual(base.effect_status(proposal.effect_key), EffectStatus.OPEN)
        with self.assertRaises(AuthorizationCanceledError):
            guard.validate_dispatch(old_permit)

        lease2 = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guarded2 = guard.recover_with_lease(
            proposal.proposal_id,
            lease_id=lease2.lease_id,
            required_scope="PAYMENT:SEND",
            recovery_basis="fresh active capability after predispatch revocation",
        )
        self.assertNotEqual(
            guarded1.authorization.authorization_id,
            guarded2.authorization.authorization_id,
        )
        permit2 = guard.prepare_dispatch(guarded2)
        self.assertTrue(guard.validate_dispatch(permit2))
        receipt = guard.record_receipt(
            permit2,
            receipt_id="BANK-RECEIPT-42",
            outcome={"status": "settled"},
        )
        self.assertEqual(receipt.effect_key, proposal.effect_key)
        self.assertEqual(base.effect_status(proposal.effect_key), EffectStatus.SETTLED)

    def test_validated_unreceipted_dispatch_is_not_silently_retried(self):
        base = FaceMicroController()
        proposal = self._proposal(base, effect_key="PAYMENT:43")
        gate = AuthorityEpochGate()
        lease = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guard = HardenedRecoverableAuthorityGuardedMicroController(controller=base, authority_gate=gate)

        guarded = guard.authorize_with_lease(
            proposal.proposal_id,
            lease_id=lease.lease_id,
            required_scope="PAYMENT:SEND",
        )
        permit = guard.prepare_dispatch(guarded)
        self.assertTrue(guard.validate_dispatch(permit))
        cancellation = guard.cancel_authorization(
            guarded,
            reason="authority revoked after validation while provider outcome is unknown",
        )
        self.assertEqual(cancellation.state, CancellationState.RECONCILIATION_REQUIRED)
        self.assertEqual(base.effect_status(proposal.effect_key), EffectStatus.AUTHORIZED)

        fresh_lease = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        with self.assertRaises(UnsafeRecoveryError):
            guard.recover_with_lease(
                proposal.proposal_id,
                lease_id=fresh_lease.lease_id,
                required_scope="PAYMENT:SEND",
                recovery_basis="must not be enough without reconciliation",
            )

        late_receipt = guard.record_receipt(
            permit,
            receipt_id="BANK-LATE-43",
            outcome={"status": "settled-before-revocation-observed"},
        )
        self.assertEqual(late_receipt.effect_key, proposal.effect_key)
        self.assertEqual(base.effect_status(proposal.effect_key), EffectStatus.SETTLED)
        snapshot = guard.hardened_snapshot()
        self.assertTrue(
            any(
                r["outcome"] == "LATE_RECEIPT_SETTLED_EFFECT"
                for r in snapshot["reconciliation_resolutions"]
            )
        )

    def test_authoritative_no_effect_reconciliation_allows_recovery_and_quarantines_old_late_receipt(self):
        base = FaceMicroController()
        proposal = self._proposal(base, effect_key="PAYMENT:44")
        gate = AuthorityEpochGate()
        lease1 = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guard = HardenedRecoverableAuthorityGuardedMicroController(controller=base, authority_gate=gate)

        guarded1 = guard.authorize_with_lease(
            proposal.proposal_id,
            lease_id=lease1.lease_id,
            required_scope="PAYMENT:SEND",
        )
        permit1 = guard.prepare_dispatch(guarded1)
        self.assertTrue(guard.validate_dispatch(permit1))
        guard.cancel_authorization(guarded1, reason="network ambiguity")
        reconciled = guard.reconcile_no_effect(
            proposal.effect_key,
            evidence_ref="BANK-QUERY-NO-TRANSACTION-44",
        )
        self.assertEqual(reconciled.state, CancellationState.RECONCILED_NO_EFFECT)
        self.assertEqual(base.effect_status(proposal.effect_key), EffectStatus.OPEN)

        lease2 = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guard.recover_with_lease(
            proposal.proposal_id,
            lease_id=lease2.lease_id,
            required_scope="PAYMENT:SEND",
            recovery_basis="provider states no original transaction exists",
        )
        with self.assertRaises(LateReceiptConflictError):
            guard.record_receipt(
                permit1,
                receipt_id="CONTRADICTORY-LATE-44",
                outcome={"status": "claimed-late-settlement"},
            )


class MultiEffectSagaTests(unittest.TestCase):
    def _submit(self, ctl, *, face, effect, op, world):
        return ctl.submit(
            face_id=face,
            intent_id=op.upper(),
            effect_key=effect,
            world_scope=world,
            action={"op": op, "effect": effect},
        )

    def test_partial_failure_requires_receipted_compensation_as_new_effect(self):
        base = FaceMicroController()
        reserve = self._submit(base, face="FACE_A", effect="RESERVATION:7", op="reserve", world="HOTEL:7")
        cancel = self._submit(base, face="FACE_A", effect="RESERVATION:7:CANCEL", op="cancel", world="HOTEL:7")
        payment = self._submit(base, face="FACE_A", effect="PAYMENT:7", op="pay", world="BANK:7")

        gate = AuthorityEpochGate()
        reserve_lease = gate.issue(face_id="FACE_A", scopes=["RESERVATION:CREATE"])
        cancel_lease = gate.issue(face_id="FACE_A", scopes=["RESERVATION:CANCEL"])
        payment_lease = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guard = HardenedRecoverableAuthorityGuardedMicroController(controller=base, authority_gate=gate)
        saga = MultiEffectSagaCoordinator(guard)
        record = saga.create(
            saga_id="SAGA-TRIP-7",
            steps=[
                SagaStep(
                    step_id="reserve",
                    proposal_id=reserve.proposal_id,
                    lease_id=reserve_lease.lease_id,
                    required_scope="RESERVATION:CREATE",
                    reversible=True,
                    compensation_proposal_id=cancel.proposal_id,
                    compensation_lease_id=cancel_lease.lease_id,
                    compensation_scope="RESERVATION:CANCEL",
                ),
                SagaStep(
                    step_id="pay",
                    proposal_id=payment.proposal_id,
                    lease_id=payment_lease.lease_id,
                    required_scope="PAYMENT:SEND",
                    reversible=False,
                ),
            ],
        )

        saga.authorize_step(record.saga_id, "reserve")
        saga.prepare_step_dispatch(record.saga_id, "reserve")
        self.assertTrue(saga.validate_step_dispatch(record.saga_id, "reserve"))
        saga.record_step_receipt(
            record.saga_id,
            "reserve",
            receipt_id="HOTEL-RESERVED-7",
            outcome={"reserved": True},
        )

        saga.fail(record.saga_id, "pay", reason="payment provider unavailable before authorization")
        self.assertEqual(record.state, SagaState.NEEDS_COMPENSATION)
        saga.authorize_compensation(record.saga_id, "reserve")
        saga.prepare_compensation_dispatch(record.saga_id, "reserve")
        self.assertTrue(saga.validate_compensation_dispatch(record.saga_id, "reserve"))
        saga.record_compensation_receipt(
            record.saga_id,
            "reserve",
            receipt_id="HOTEL-CANCELED-7",
            outcome={"canceled": True},
        )
        self.assertEqual(record.state, SagaState.COMPENSATED_ABORTED)
        self.assertEqual(base.effect_status("RESERVATION:7"), EffectStatus.SETTLED)
        self.assertEqual(base.effect_status("RESERVATION:7:CANCEL"), EffectStatus.SETTLED)
        self.assertFalse(saga.snapshot(record.saga_id)["atomicity_claimed"])

    def test_irreversible_partial_settlement_is_not_falsely_rolled_back(self):
        base = FaceMicroController()
        publish = self._submit(base, face="FACE_A", effect="PUBLICATION:1", op="publish", world="PUBLIC:FEED")
        notify = self._submit(base, face="FACE_A", effect="NOTIFY:1", op="notify", world="MAIL:USER")
        gate = AuthorityEpochGate()
        publish_lease = gate.issue(face_id="FACE_A", scopes=["PUBLICATION:CREATE"])
        notify_lease = gate.issue(face_id="FACE_A", scopes=["EMAIL:SEND"])
        guard = HardenedRecoverableAuthorityGuardedMicroController(controller=base, authority_gate=gate)
        saga = MultiEffectSagaCoordinator(guard)
        record = saga.create(
            saga_id="SAGA-PUBLISH-1",
            steps=[
                SagaStep(
                    step_id="publish",
                    proposal_id=publish.proposal_id,
                    lease_id=publish_lease.lease_id,
                    required_scope="PUBLICATION:CREATE",
                    reversible=False,
                ),
                SagaStep(
                    step_id="notify",
                    proposal_id=notify.proposal_id,
                    lease_id=notify_lease.lease_id,
                    required_scope="EMAIL:SEND",
                    reversible=True,
                ),
            ],
        )
        saga.authorize_step(record.saga_id, "publish")
        saga.prepare_step_dispatch(record.saga_id, "publish")
        saga.validate_step_dispatch(record.saga_id, "publish")
        saga.record_step_receipt(
            record.saga_id,
            "publish",
            receipt_id="PUBLICATION-RECEIPT-1",
            outcome={"published": True},
        )
        saga.fail(record.saga_id, "notify", reason="mail unavailable")
        self.assertEqual(record.state, SagaState.PARTIAL_IRREVERSIBLE)
        self.assertFalse(saga.snapshot(record.saga_id)["atomicity_claimed"])


class BoundedBypassFairnessTests(unittest.TestCase):
    def test_low_priority_face_cannot_be_starved_by_endless_high_priority_arrivals(self):
        queue = BoundedBypassReviewQueue(max_bypass=2)
        low = queue.enqueue(
            ticket_id="LOW",
            effect_key="EFFECT:X",
            face_id="FACE_LOW",
            routing_priority=0.5,
        )
        queue.enqueue(ticket_id="HIGH-1", effect_key="EFFECT:X", face_id="FACE_HIGH", routing_priority=10.0)
        self.assertEqual(queue.next_ticket().ticket_id, "HIGH-1")
        queue.enqueue(ticket_id="HIGH-2", effect_key="EFFECT:X", face_id="FACE_HIGH", routing_priority=10.0)
        self.assertEqual(queue.next_ticket().ticket_id, "HIGH-2")
        queue.enqueue(ticket_id="HIGH-3", effect_key="EFFECT:X", face_id="FACE_HIGH", routing_priority=10.0)
        selected = queue.next_ticket()
        self.assertEqual(selected.ticket_id, low.ticket_id)
        self.assertEqual(selected.authority_weight, 0)


if __name__ == "__main__":
    unittest.main()
