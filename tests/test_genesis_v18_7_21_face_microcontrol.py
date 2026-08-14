import unittest

from genesis_v18_7_21_face_microcontrol import (
    AlreadySettledError,
    BoundaryNotAdmissibleError,
    BoundaryVerdict,
    ConflictHoldError,
    EffectStatus,
    FaceMicroController,
    FalsificationLedger,
    FirstBreak,
    FrozenHypothesisError,
    ProposalStatus,
    assess_source_world_receipt,
)


class BoundaryLocalizationTests(unittest.TestCase):
    def test_first_break_localizes_source_world_receipt(self):
        self.assertEqual(
            assess_source_world_receipt("FAIL", "PASS", "PASS").first_break,
            FirstBreak.SOURCE,
        )
        self.assertEqual(
            assess_source_world_receipt("PASS", "FAIL", "PASS").first_break,
            FirstBreak.WORLD,
        )
        self.assertEqual(
            assess_source_world_receipt("PASS", "PASS", "FAIL").first_break,
            FirstBreak.RECEIPT,
        )
        self.assertEqual(
            assess_source_world_receipt("PASS", "PASS", "PASS").first_break,
            FirstBreak.NONE,
        )

    def test_unknown_boundary_is_not_invented(self):
        assessment = assess_source_world_receipt("PASS", "UNDETERMINED", "PASS")
        self.assertIsNone(assessment.full_chain)
        self.assertEqual(assessment.first_break, FirstBreak.UNDETERMINED)


class FaceMicroControlTests(unittest.TestCase):
    def test_100_faces_do_not_multiply_one_effect_budget(self):
        ctl = FaceMicroController()
        proposals = []
        for i in range(100):
            proposals.append(
                ctl.submit(
                    face_id=f"FACE_{i:04d}",
                    intent_id="PAY_INVOICE_7",
                    effect_key="PAYMENT:INVOICE-7:EPOCH-1",
                    world_scope="BANK_ACCOUNT_A",
                    action={"op": "pay", "invoice": 7, "amount": 100},
                )
            )
        self.assertEqual(ctl.effect_budget("PAYMENT:INVOICE-7:EPOCH-1"), 1)
        self.assertEqual(len(ctl.proposals_for("PAYMENT:INVOICE-7:EPOCH-1")), 100)
        self.assertEqual(ctl.effect_status("PAYMENT:INVOICE-7:EPOCH-1"), EffectStatus.OPEN)

        auth = ctl.authorize(proposals[0].proposal_id)
        self.assertEqual(auth.effect_budget, 1)
        receipt = ctl.record_receipt(
            auth.authorization_id,
            receipt_id="BANK-RECEIPT-7",
            outcome={"settled": True, "invoice": 7},
        )
        self.assertEqual(receipt.effect_key, "PAYMENT:INVOICE-7:EPOCH-1")
        self.assertEqual(ctl.effect_budget("PAYMENT:INVOICE-7:EPOCH-1"), 0)
        self.assertEqual(ctl.effect_status("PAYMENT:INVOICE-7:EPOCH-1"), EffectStatus.SETTLED)
        self.assertTrue(all(p.status is ProposalStatus.SETTLED for p in ctl.proposals_for(receipt.effect_key)))

        with self.assertRaises(AlreadySettledError):
            ctl.authorize(proposals[1].proposal_id)

    def test_face_sybil_count_never_becomes_authority(self):
        ctl = FaceMicroController()
        for i in range(25):
            ctl.submit(
                face_id=f"DERIVATIVE_{i}",
                intent_id="SAME_INTENT",
                effect_key="DOOR:OPEN:1",
                world_scope="ONE_DOOR",
                action={"op": "open"},
            )
        snapshot = ctl.snapshot()
        self.assertFalse(snapshot["invariants"]["face_count_is_voting_power"])
        self.assertEqual(snapshot["invariants"]["effect_budget_per_effect_key"], 1)
        for cal in snapshot["calibration"].values():
            self.assertEqual(cal["authority_weight"], 0)

    def test_conflicting_actions_hold_until_explicit_host_resolution(self):
        ctl = FaceMicroController()
        stay = ctl.submit(
            face_id="FACE_CONTINUITY",
            intent_id="THRESHOLD",
            effect_key="BODY:THRESHOLD:SLOT-1",
            world_scope="THRESHOLD",
            action={"move": "stay"},
        )
        cross = ctl.submit(
            face_id="FACE_CHANGE",
            intent_id="THRESHOLD",
            effect_key="BODY:THRESHOLD:SLOT-1",
            world_scope="THRESHOLD",
            action={"move": "cross"},
        )
        self.assertEqual(ctl.effect_status(stay.effect_key), EffectStatus.HOLD)
        self.assertEqual(stay.status, ProposalStatus.HOLD)
        self.assertEqual(cross.status, ProposalStatus.HOLD)
        with self.assertRaises(ConflictHoldError):
            ctl.authorize(cross.proposal_id)

        auth = ctl.authorize(
            cross.proposal_id,
            resolution_basis="GENESIS_SOVEREIGN_ADMISSIBLE_POLICY_RULE_17",
        )
        self.assertEqual(auth.face_id, "FACE_CHANGE")
        self.assertEqual(ctl.effect_status(stay.effect_key), EffectStatus.AUTHORIZED)

    def test_source_or_world_failure_blocks_authorization(self):
        ctl = FaceMicroController()
        bad_source = ctl.submit(
            face_id="FACE_A",
            intent_id="X",
            effect_key="EFFECT:X",
            world_scope="WORLD:X",
            action={"op": "x"},
            source_boundary=BoundaryVerdict.FAIL,
        )
        with self.assertRaises(BoundaryNotAdmissibleError):
            ctl.authorize(bad_source.proposal_id)

        bad_world = ctl.submit(
            face_id="FACE_B",
            intent_id="Y",
            effect_key="EFFECT:Y",
            world_scope="WORLD:Y",
            action={"op": "y"},
            world_boundary=BoundaryVerdict.UNDETERMINED,
        )
        with self.assertRaises(BoundaryNotAdmissibleError):
            ctl.authorize(bad_world.proposal_id)

    def test_calibration_changes_routing_not_rights(self):
        ctl = FaceMicroController()
        for _ in range(3):
            ctl.record_learning("FACE_REDTEAM", "COUNTEREXAMPLE_ACCEPTED")
        ctl.record_learning("FACE_REDTEAM", "FIRST_BREAK_CORRECT")
        cal = ctl.calibration("FACE_REDTEAM")
        self.assertGreater(cal.routing_priority, 1.0)
        self.assertEqual(cal.authority_weight, 0)

        for _ in range(5):
            ctl.record_learning("FACE_NOISY", "POST_HOC_RESCUE_ATTEMPT")
        noisy = ctl.calibration("FACE_NOISY")
        self.assertLess(noisy.routing_priority, 1.0)
        self.assertEqual(noisy.authority_weight, 0)

    def test_new_effect_key_is_required_for_new_external_effect(self):
        ctl = FaceMicroController()
        p1 = ctl.submit(
            face_id="FACE_A",
            intent_id="MAIL",
            effect_key="EMAIL:MESSAGE-42:ATTEMPT-1",
            world_scope="MAILBOX:DEST",
            action={"send": "message-42"},
        )
        a1 = ctl.authorize(p1.proposal_id)
        ctl.record_receipt(a1.authorization_id, receipt_id="SMTP-1", outcome="250 OK")

        p2 = ctl.submit(
            face_id="FACE_A",
            intent_id="MAIL_RETRY_AUTHORIZED_AS_NEW_TRANSACTION",
            effect_key="EMAIL:MESSAGE-42:ATTEMPT-2",
            world_scope="MAILBOX:DEST",
            action={"send": "message-42"},
        )
        self.assertEqual(ctl.effect_budget(p2.effect_key), 1)


class FalsificationLedgerTests(unittest.TestCase):
    def test_one_counterexample_can_challenge_many_face_agreement(self):
        ledger = FalsificationLedger()
        ledger.register(
            "H1",
            "The full visual chain is unique to the target",
            {"source": True, "world": True, "receipt": True},
        )
        ledger.submit_counterexample(
            "H1",
            "official://LEBRON-2016-FINALS-MVP",
            "Five visible instances and the full outcome chain occur in an ordinary sports design.",
            counterexample_id="CE-LEBRON",
        )
        self.assertEqual(ledger.status("H1"), "CHALLENGED_BY_PRESERVED_COUNTEREXAMPLE")
        exported = ledger.export()
        self.assertEqual(exported["counterexamples"][0]["counterexample_id"], "CE-LEBRON")

    def test_frozen_hypothesis_is_revised_by_new_lineage_not_rewrite(self):
        ledger = FalsificationLedger()
        h1 = ledger.register("H1", "broad rule", {"rule": "broad"})
        with self.assertRaises(FrozenHypothesisError):
            ledger.register("H1", "quietly changed rule", {"rule": "narrow"})
        h2 = ledger.register("H2", "new narrower hypothesis", {"rule": "narrow"}, parent_id="H1")
        self.assertEqual(h2.parent_id, h1.hypothesis_id)


if __name__ == "__main__":
    unittest.main()
