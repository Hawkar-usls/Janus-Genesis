from __future__ import annotations

import copy
import json
import unittest

from tools.janus_preservation_integration_evidence import (
    PreservationEvidenceError,
    evaluate,
)


class PreservationIntegrationEvidenceV1Tests(unittest.TestCase):
    def refs(self) -> dict[str, dict[str, object]]:
        return {
            "materializer": {
                "repository": "Hawkar-usls/Janus_Genesis",
                "pull_request": 122,
                "sha": "1" * 40,
            },
            "privacy_projection": {
                "repository": "Hawkar-usls/Janus_Genesis",
                "pull_request": 125,
                "sha": "2" * 40,
            },
            "source_pin_contract": {
                "repository": "Hawkar-usls/Janus_Genesis",
                "pull_request": 126,
                "sha": "6" * 40,
            },
            "variant_lineage": {
                "repository": "Hawkar-usls/Janus_Genesis",
                "pull_request": 123,
                "sha": "3" * 40,
            },
            "handoff_ledger": {
                "repository": "Hawkar-usls/Janus_Genesis",
                "pull_request": 124,
                "sha": "4" * 40,
            },
            "swarm_recovery": {
                "repository": "Hawkar-usls/janus-distributed-ai-swarm",
                "pull_request": 5,
                "sha": "5" * 40,
            },
        }

    def lock(self) -> dict[str, object]:
        return {
            "schema": "janus.nexus.preservation_integration_lock.v1",
            "preregistration_receipt": "5308388940",
            "expected_source_count": 44,
            "privacy_mode": "LOCAL_EVIDENCE_PUBLIC_REDACTED_SUMMARY",
            "producer_refs": self.refs(),
        }

    def bundle(self) -> dict[str, object]:
        return {
            "schema": "janus.nexus.preservation_integration_evidence.v1",
            "producer_refs": self.refs(),
            "materializer": {
                "source_count": 44,
                "clean_target_rebuild_exercised": True,
                "rebuild_a_digest": "a" * 64,
                "rebuild_b_digest": "a" * 64,
                "local_exact_replay_passed": True,
                "privacy_projection_passed": True,
                "source_pin_drift": False,
                "source_writeback_observed": False,
                "destructive_cleanup_required_for_pass": False,
            },
            "source_pins": {
                "typed_pinset_validated": True,
                "exact_git_replay_required": True,
                "git_commit_kind": "GIT_COMMIT_SHA1",
                "opaque_version_kind": "OPAQUE_VERSION_TOKEN",
                "type_inference_used": False,
                "private_exact_pin_publication": False,
                "whole_pinset_digest_publication": False,
            },
            "lineage": {
                "expected_head_digest": "b" * 64,
                "observed_head_digest": "b" * 64,
                "failed_variant_ids": ["c" * 64],
                "failed_variants_retained": True,
            },
            "handoff": {
                "expected_head_digest": "d" * 64,
                "observed_head_digest": "d" * 64,
                "conflict_message_ids": ["MSG-A", "MSG-B"],
                "conflicts_retained": True,
                "reconciliation_status": "HOLD_RECONCILE",
                "majority_vote_used": False,
            },
            "swarm": {
                "checkpoint_digest": "e" * 64,
                "receipt_digest": "f" * 64,
                "session_drop_exercised": True,
                "resume_decision": "RESUME",
                "source_pin_drift": False,
                "duplicate_source_mutation_observed": False,
            },
            "source_guard": {
                "before_identity_digest": "9" * 64,
                "after_identity_digest": "9" * 64,
                "writeback_observed": False,
                "destructive_effect_observed": False,
            },
        }

    def test_complete_preregistered_evidence_bundle_is_consistent(self) -> None:
        result = evaluate(self.bundle(), self.lock())
        self.assertEqual(result["decision"], "EVIDENCE_BUNDLE_CONSISTENT")
        self.assertTrue(result["clean_target_rebuild_exercised"])
        self.assertTrue(result["typed_source_pin_contract_passed"])
        self.assertTrue(result["failed_variant_retention"])
        self.assertTrue(result["conflict_retention_and_hold_reconcile"])
        self.assertTrue(result["swarm_session_drop_recovery"])
        self.assertFalse(result["source_writeback_observed"])
        self.assertFalse(result["empirical_replay_claimed_by_this_verifier"])
        self.assertFalse(result["merge_permission_granted"])

    def test_producer_refs_must_match_external_lock(self) -> None:
        bundle = self.bundle()
        bundle["producer_refs"]["materializer"]["sha"] = "7" * 40  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "producer refs do not match"):
            evaluate(bundle, self.lock())

    def test_repository_identity_is_bound_per_producer_role(self) -> None:
        lock = self.lock()
        lock["producer_refs"]["swarm_recovery"]["repository"] = (  # type: ignore[index]
            "Hawkar-usls/Janus_Genesis"
        )
        with self.assertRaisesRegex(PreservationEvidenceError, "janus-distributed-ai-swarm"):
            evaluate(self.bundle(), lock)

    def test_malformed_producer_sha_and_pr_fail_closed(self) -> None:
        lock = self.lock()
        lock["producer_refs"]["swarm_recovery"]["sha"] = "main"  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "exact lowercase 40-hex"):
            evaluate(self.bundle(), lock)

        lock = self.lock()
        lock["producer_refs"]["materializer"]["pull_request"] = True  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "positive integer PR"):
            evaluate(self.bundle(), lock)

    def test_source_pin_contract_is_mandatory_and_never_inferred(self) -> None:
        inferred = self.bundle()
        inferred["source_pins"]["type_inference_used"] = True  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be False"):
            evaluate(inferred, self.lock())

        wrong_kind = self.bundle()
        wrong_kind["source_pins"]["git_commit_kind"] = "OPAQUE_VERSION_TOKEN"  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be GIT_COMMIT_SHA1"):
            evaluate(wrong_kind, self.lock())

        leaked = self.bundle()
        leaked["source_pins"]["private_exact_pin_publication"] = True  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be False"):
            evaluate(leaked, self.lock())

    def test_independent_rebuild_digest_mismatch_is_rejected(self) -> None:
        bundle = self.bundle()
        bundle["materializer"]["rebuild_b_digest"] = "7" * 64  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "rebuild digests differ"):
            evaluate(bundle, self.lock())

    def test_missing_or_malformed_failed_variant_evidence_is_rejected(self) -> None:
        bundle = self.bundle()
        bundle["lineage"]["failed_variant_ids"] = []  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "at least one retained failed variant"):
            evaluate(bundle, self.lock())

        malformed = self.bundle()
        malformed["lineage"]["failed_variant_ids"] = [{"not": "hashable-as-id"}]  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be lowercase 64-hex"):
            evaluate(malformed, self.lock())

    def test_lineage_head_mismatch_is_rejected(self) -> None:
        bundle = self.bundle()
        bundle["lineage"]["observed_head_digest"] = "8" * 64  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "lineage expected/observed"):
            evaluate(bundle, self.lock())

    def test_handoff_must_reconstruct_hold_without_majority_vote(self) -> None:
        not_hold = self.bundle()
        not_hold["handoff"]["reconciliation_status"] = "CONSISTENT"  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be HOLD_RECONCILE"):
            evaluate(not_hold, self.lock())

        majority = self.bundle()
        majority["handoff"]["majority_vote_used"] = True  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be False"):
            evaluate(majority, self.lock())

        malformed = self.bundle()
        malformed["handoff"]["conflict_message_ids"] = ["MSG-A", {"bad": "id"}]  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be a non-empty string"):
            evaluate(malformed, self.lock())

    def test_swarm_session_drop_and_resume_are_mandatory(self) -> None:
        bundle = self.bundle()
        bundle["swarm"]["session_drop_exercised"] = False  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be True"):
            evaluate(bundle, self.lock())

        bundle = self.bundle()
        bundle["swarm"]["resume_decision"] = "HOLD"  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be RESUME"):
            evaluate(bundle, self.lock())

    def test_source_identity_change_or_writeback_is_rejected(self) -> None:
        changed = self.bundle()
        changed["source_guard"]["after_identity_digest"] = "0" * 64  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "source identity changed"):
            evaluate(changed, self.lock())

        wrote = self.bundle()
        wrote["source_guard"]["writeback_observed"] = True  # type: ignore[index]
        with self.assertRaisesRegex(PreservationEvidenceError, "must be False"):
            evaluate(wrote, self.lock())

    def test_unknown_bundle_fields_are_rejected(self) -> None:
        bundle = self.bundle()
        bundle["permission_granted"] = True
        with self.assertRaisesRegex(PreservationEvidenceError, "bundle keys mismatch"):
            evaluate(bundle, self.lock())

    def test_public_summary_does_not_echo_local_sensitive_evidence(self) -> None:
        bundle = self.bundle()
        result = evaluate(bundle, self.lock())
        serialized = json.dumps(result, sort_keys=True)

        local_sensitive = {
            bundle["materializer"]["rebuild_a_digest"],  # type: ignore[index]
            bundle["lineage"]["expected_head_digest"],  # type: ignore[index]
            bundle["lineage"]["failed_variant_ids"][0],  # type: ignore[index]
            bundle["handoff"]["expected_head_digest"],  # type: ignore[index]
            bundle["handoff"]["conflict_message_ids"][0],  # type: ignore[index]
            bundle["handoff"]["conflict_message_ids"][1],  # type: ignore[index]
            bundle["swarm"]["checkpoint_digest"],  # type: ignore[index]
            bundle["swarm"]["receipt_digest"],  # type: ignore[index]
            bundle["source_guard"]["before_identity_digest"],  # type: ignore[index]
        }
        for value in local_sensitive:
            self.assertNotIn(str(value), serialized)
        self.assertFalse(result["local_sensitive_evidence_persisted_in_summary"])
        self.assertEqual(result["producer_refs"], self.refs())

    def test_lock_is_external_and_exact_not_self_declared(self) -> None:
        bundle = self.bundle()
        lock = self.lock()
        bundle_refs = copy.deepcopy(bundle["producer_refs"])
        lock["producer_refs"] = bundle_refs
        result = evaluate(bundle, lock)
        self.assertEqual(result["producer_refs"], self.refs())
        self.assertRegex(result["producer_lock_digest"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
