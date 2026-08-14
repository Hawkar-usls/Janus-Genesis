import unittest

from genesis_v18_7_21_face_microcontrol import FaceMicroController
from genesis_v18_7_22_face_authority_epoch import (
    AuthorityEpochGate,
    AuthorityGuardedMicroController,
    CapabilityBudgetError,
    CapabilityPrincipalError,
    CapabilityScopeError,
    FaceMicroReviewScheduler,
    RevokedLeaseError,
    StaleAuthorityEpochError,
)


class AuthorityEpochTests(unittest.TestCase):
    def _proposal(self, controller, face_id="FACE_A", effect_key="PAYMENT:7"):
        return controller.submit(
            face_id=face_id,
            intent_id="PAY",
            effect_key=effect_key,
            world_scope="BANK:ACCOUNT-A",
            action={"op": "pay", "invoice": 7},
        )

    def test_confused_deputy_scope_is_denied(self):
        base = FaceMicroController()
        proposal = self._proposal(base)
        gate = AuthorityEpochGate()
        lease = gate.issue(face_id="FACE_A", scopes=["EMAIL:SEND"])
        guarded = AuthorityGuardedMicroController(controller=base, authority_gate=gate)
        with self.assertRaises(CapabilityScopeError):
            guarded.authorize_with_lease(
                proposal.proposal_id,
                lease_id=lease.lease_id,
                required_scope="PAYMENT:SEND",
            )

    def test_capability_is_nontransferable_between_faces(self):
        base = FaceMicroController()
        proposal = self._proposal(base, face_id="FACE_B")
        gate = AuthorityEpochGate()
        lease = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guarded = AuthorityGuardedMicroController(controller=base, authority_gate=gate)
        with self.assertRaises(CapabilityPrincipalError):
            guarded.authorize_with_lease(
                proposal.proposal_id,
                lease_id=lease.lease_id,
                required_scope="PAYMENT:SEND",
            )

    def test_revocation_between_authorization_and_dispatch_blocks_dispatch(self):
        base = FaceMicroController()
        proposal = self._proposal(base)
        gate = AuthorityEpochGate()
        lease = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guarded = AuthorityGuardedMicroController(controller=base, authority_gate=gate)
        auth = guarded.authorize_with_lease(
            proposal.proposal_id,
            lease_id=lease.lease_id,
            required_scope="PAYMENT:SEND",
        )
        gate.revoke(lease.lease_id)
        with self.assertRaises(RevokedLeaseError):
            guarded.prepare_dispatch(auth)

    def test_epoch_rotation_invalidates_stale_lease(self):
        base = FaceMicroController()
        proposal = self._proposal(base)
        gate = AuthorityEpochGate(authority_epoch=7)
        lease = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guarded = AuthorityGuardedMicroController(controller=base, authority_gate=gate)
        gate.rotate_epoch()
        with self.assertRaises(StaleAuthorityEpochError):
            guarded.authorize_with_lease(
                proposal.proposal_id,
                lease_id=lease.lease_id,
                required_scope="PAYMENT:SEND",
            )

    def test_dispatch_permit_must_be_revalidated_immediately_before_effect(self):
        base = FaceMicroController()
        proposal = self._proposal(base)
        gate = AuthorityEpochGate()
        lease = gate.issue(face_id="FACE_A", scopes=["PAYMENT:SEND"])
        guarded = AuthorityGuardedMicroController(controller=base, authority_gate=gate)
        auth = guarded.authorize_with_lease(
            proposal.proposal_id,
            lease_id=lease.lease_id,
            required_scope="PAYMENT:SEND",
        )
        permit = guarded.prepare_dispatch(auth)
        self.assertTrue(guarded.validate_dispatch(permit))
        gate.revoke(lease.lease_id)
        with self.assertRaises(RevokedLeaseError):
            guarded.validate_dispatch(permit)

    def test_capability_dispatch_budget_does_not_expand(self):
        gate = AuthorityEpochGate()
        lease = gate.issue(face_id="FACE_A", scopes=["TOOL:CALL"], max_dispatches=1)
        gate.consume_dispatch(lease.lease_id, face_id="FACE_A", required_scope="TOOL:CALL")
        self.assertEqual(gate.dispatches_used(lease.lease_id), 1)
        with self.assertRaises(CapabilityBudgetError):
            gate.consume_dispatch(lease.lease_id, face_id="FACE_A", required_scope="TOOL:CALL")


class MicroReviewSchedulerTests(unittest.TestCase):
    def test_high_risk_review_has_independent_challenge_and_no_world_authority(self):
        ctl = FaceMicroController()
        scheduler = FaceMicroReviewScheduler(ctl)
        plan = scheduler.plan(
            origin_face_id="FACE_ORIGIN",
            candidate_face_ids=["FACE_ORIGIN", "FACE_RED", "FACE_CHECK"],
            risk_level="HIGH",
            irreversible=True,
        )
        self.assertEqual(len(plan.assignments), 2)
        self.assertTrue(all(a.face_id != "FACE_ORIGIN" for a in plan.assignments))
        self.assertTrue(any(a.role == "RED_TEAM" for a in plan.assignments))
        self.assertTrue(all(a.authority_weight == 0 for a in plan.assignments))
        self.assertFalse(plan.world_authority_granted)

    def test_novel_counterexample_is_not_starved_by_low_routing_priority(self):
        ctl = FaceMicroController()
        for _ in range(4):
            ctl.record_learning("FACE_LOW", "POST_HOC_RESCUE_ATTEMPT")
        for _ in range(3):
            ctl.record_learning("FACE_HIGH", "COUNTEREXAMPLE_ACCEPTED")
        self.assertLess(ctl.calibration("FACE_LOW").routing_priority, ctl.calibration("FACE_HIGH").routing_priority)

        scheduler = FaceMicroReviewScheduler(ctl)
        plan = scheduler.plan(
            origin_face_id="FACE_ORIGIN",
            candidate_face_ids=["FACE_LOW", "FACE_HIGH", "FACE_OTHER"],
            risk_level="HIGH",
            novel_counterexample_faces=["FACE_LOW"],
        )
        assignment = next(a for a in plan.assignments if a.face_id == "FACE_LOW")
        self.assertEqual(assignment.role, "COUNTEREXAMPLE_CHALLENGE")
        self.assertEqual(assignment.authority_weight, 0)


if __name__ == "__main__":
    unittest.main()
