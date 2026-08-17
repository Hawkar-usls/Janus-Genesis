from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from goldprompt_face_receipts import (  # noqa: E402
    CANONICAL_REQUIRED_FACES,
    EXPECTED_CONTRACT_DIGEST,
    EXPECTED_FACES,
    STARTUP_CONTRACT_DIGEST,
    build_genesis_receipt,
    build_receipt,
    collect_receipts,
    contract_digest,
    resolve_runtime_source_revision,
    self_test,
    sha256,
    verify_bundle,
    verify_receipt,
)


def fixture_revision(face_id: str) -> str:
    return hashlib.sha256(("TEST:" + face_id).encode("utf-8")).hexdigest()[:40]


class GoldPromptFaceReceiptTests(unittest.TestCase):
    def receipts(self):
        return [build_receipt(face_id, fixture_revision(face_id)) for face_id in EXPECTED_FACES]

    def expected_revisions(self):
        return {face_id: fixture_revision(face_id) for face_id in EXPECTED_FACES}

    def test_contract_digest_is_frozen_at_startup(self):
        self.assertEqual(contract_digest(), EXPECTED_CONTRACT_DIGEST)
        self.assertEqual(STARTUP_CONTRACT_DIGEST, EXPECTED_CONTRACT_DIGEST)

    def test_each_required_face_receipt_replays(self):
        for receipt in self.receipts():
            result = verify_receipt(receipt, expected_source_revision=receipt["source_revision"])
            self.assertTrue(result["valid"], result)
            self.assertEqual(receipt["authority_weight"], 0)
            self.assertEqual(receipt["compliance_state"], "COMPLIANT")

    def test_genesis_fixture_receipt_is_valid_but_not_origin_attestation(self):
        revision = fixture_revision("GENESIS_GUARDIAN_MESH_ORCHESTRATOR")
        receipt = build_genesis_receipt(revision)
        self.assertEqual(receipt["face_id"], "GENESIS_GUARDIAN_MESH_ORCHESTRATOR")
        self.assertEqual(receipt["face_role"], "FACE_ORCHESTRATOR")
        self.assertEqual(receipt["source_revision"], revision)
        self.assertTrue(verify_receipt(receipt)["valid"])

    def test_runtime_source_revision_requires_trusted_environment(self):
        with self.assertRaisesRegex(ValueError, "TRUSTED_SOURCE_REVISION_REQUIRED"):
            resolve_runtime_source_revision({})
        with self.assertRaisesRegex(ValueError, "JANUS_SOURCE_REVISION_INVALID"):
            resolve_runtime_source_revision({"JANUS_SOURCE_REVISION": "TEST-REV"})
        with self.assertRaisesRegex(ValueError, "SOURCE_REVISION_ENV_CONFLICT"):
            resolve_runtime_source_revision({
                "GITHUB_ACTIONS": "true",
                "GITHUB_SHA": "a" * 40,
                "JANUS_SOURCE_REVISION": "b" * 40,
            })

    def test_bundle_requires_exact_canonical_face_set_and_replays(self):
        receipts = self.receipts()
        bundle = collect_receipts(receipts, expected_source_revisions=self.expected_revisions())
        self.assertTrue(bundle["all_required_faces_compliant"])
        self.assertEqual(tuple(bundle["required_faces"]), CANONICAL_REQUIRED_FACES)
        self.assertEqual(set(bundle["required_faces"]), set(EXPECTED_FACES))
        self.assertEqual(bundle["receipt_integrity_model"], "SHA256_CONTENT_ADDRESS_NOT_SIGNATURE")
        self.assertFalse(bundle["end_to_end_message_authentication_established"])
        self.assertTrue(verify_bundle(bundle, expected_source_revisions=self.expected_revisions()))

    def test_receipt_policy_tamper_fails_closed_even_after_rehash(self):
        receipt = build_receipt("LEFT_HRAIN", fixture_revision("LEFT_HRAIN"))
        for field, bad in (
            ("authority_weight", 1),
            ("face_role", "TRUTH_ORACLE"),
            ("contract_digest_sha256", "0" * 64),
            ("goldprompt_version", "999"),
            ("compliance_state", "COMPLIANT_BUT_TRUST_ME"),
            ("user_exit_and_release_control_accepted", False),
            ("capability_scope", ["PROPOSE_STRUCTURAL_CONTEXT"]),
        ):
            candidate = copy.deepcopy(receipt)
            candidate[field] = bad
            payload = dict(candidate)
            payload.pop("receipt_sha256", None)
            candidate["receipt_sha256"] = sha256(payload)
            self.assertFalse(verify_receipt(candidate)["valid"], field)

        extra = copy.deepcopy(receipt)
        extra["extra_authority_hint"] = True
        payload = dict(extra)
        payload.pop("receipt_sha256", None)
        extra["receipt_sha256"] = sha256(payload)
        self.assertFalse(verify_receipt(extra)["valid"])

    def test_source_revision_must_be_git_shaped_and_can_be_exactly_bound(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_REVISION_REQUIRED"):
            build_receipt("RIGHT_INAIHR", "SHA-INAIHR")
        receipt = build_receipt("RIGHT_INAIHR", fixture_revision("RIGHT_INAIHR"))
        self.assertFalse(
            verify_receipt(receipt, expected_source_revision="f" * 40)["valid"]
        )
        self.assertEqual(
            verify_receipt(receipt, expected_source_revision="f" * 40)["reason"],
            "SOURCE_REVISION_MISMATCH",
        )

    def test_missing_duplicate_or_required_face_downgrade_fails_closed(self):
        receipts = self.receipts()
        with self.assertRaisesRegex(ValueError, "MISSING_REQUIRED_FACE_RECEIPTS"):
            collect_receipts(receipts[:-1])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_FACE_RECEIPT"):
            collect_receipts(receipts + [receipts[0]])
        with self.assertRaisesRegex(ValueError, "REQUIRED_FACE_SET_DOWNGRADE"):
            collect_receipts(receipts[:2], required_faces=CANONICAL_REQUIRED_FACES[:2])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REQUIRED_FACE"):
            collect_receipts(receipts, required_faces=CANONICAL_REQUIRED_FACES + (CANONICAL_REQUIRED_FACES[0],))

    def test_bundle_quorum_downgrade_is_rejected_even_after_rehash(self):
        bundle = collect_receipts(self.receipts())
        tampered = copy.deepcopy(bundle)
        removed = tampered["required_faces"].pop()
        tampered["face_receipts"].pop(removed)
        tampered["verification"].pop(removed)
        tampered.pop("bundle_sha256")
        tampered["bundle_sha256"] = sha256(tampered)
        self.assertFalse(verify_bundle(tampered))

    def test_bundle_semantic_tamper_fails_closed_even_after_rehash(self):
        bundle = collect_receipts(self.receipts())
        tampered = copy.deepcopy(bundle)
        tampered["authority_delta"] = 1
        tampered.pop("bundle_sha256")
        tampered["bundle_sha256"] = sha256(tampered)
        self.assertFalse(verify_bundle(tampered))

        auth_claim = copy.deepcopy(bundle)
        auth_claim["end_to_end_message_authentication_established"] = True
        auth_claim.pop("bundle_sha256")
        auth_claim["bundle_sha256"] = sha256(auth_claim)
        self.assertFalse(verify_bundle(auth_claim))

    def test_expected_revision_map_must_cover_exact_face_set(self):
        receipts = self.receipts()
        expected = self.expected_revisions()
        expected.pop("LEFT_HRAIN")
        with self.assertRaisesRegex(ValueError, "EXPECTED_SOURCE_REVISION_FACE_SET_MISMATCH"):
            collect_receipts(receipts, expected_source_revisions=expected)

    def test_self_test_passes(self):
        self.assertEqual(self_test()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
