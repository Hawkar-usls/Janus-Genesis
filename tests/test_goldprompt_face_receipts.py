from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from goldprompt_face_receipts import (  # noqa: E402
    EXPECTED_CONTRACT_DIGEST,
    EXPECTED_FACES,
    build_genesis_receipt,
    build_receipt,
    collect_receipts,
    contract_digest,
    self_test,
    verify_bundle,
    verify_receipt,
)


class GoldPromptFaceReceiptTests(unittest.TestCase):
    def receipts(self):
        return [build_receipt(face_id, f"SHA-{face_id}") for face_id in EXPECTED_FACES]

    def test_contract_digest_is_frozen(self):
        self.assertEqual(contract_digest(), EXPECTED_CONTRACT_DIGEST)

    def test_each_required_face_receipt_replays(self):
        for receipt in self.receipts():
            result = verify_receipt(receipt)
            self.assertTrue(result["valid"], result)
            self.assertEqual(receipt["authority_weight"], 0)
            self.assertEqual(receipt["compliance_state"], "COMPLIANT")

    def test_genesis_receipt_is_real_face_receipt(self):
        receipt = build_genesis_receipt("GENESIS-TEST-SHA")
        self.assertEqual(receipt["face_id"], "GENESIS_GUARDIAN_MESH_ORCHESTRATOR")
        self.assertEqual(receipt["face_role"], "FACE_ORCHESTRATOR")
        self.assertEqual(receipt["source_revision"], "GENESIS-TEST-SHA")
        self.assertTrue(verify_receipt(receipt)["valid"])

    def test_bundle_requires_every_face_and_replays(self):
        bundle = collect_receipts(self.receipts())
        self.assertTrue(bundle["all_required_faces_compliant"])
        self.assertEqual(set(bundle["required_faces"]), set(EXPECTED_FACES))
        self.assertTrue(verify_bundle(bundle))

    def test_receipt_tamper_fails_closed(self):
        receipt = build_receipt("LEFT_HRAIN", "SHA-HRAIN")
        for field, bad in (
            ("authority_weight", 1),
            ("face_role", "TRUTH_ORACLE"),
            ("contract_digest_sha256", "0" * 64),
            ("goldprompt_version", "999"),
            ("compliance_state", "COMPLIANT_BUT_TRUST_ME"),
        ):
            candidate = copy.deepcopy(receipt)
            candidate[field] = bad
            self.assertFalse(verify_receipt(candidate)["valid"], field)

    def test_source_revision_is_required_for_runtime_receipt(self):
        receipt = build_receipt("RIGHT_INAIHR", None)
        self.assertFalse(verify_receipt(receipt)["valid"])
        self.assertTrue(verify_receipt(receipt, require_source_revision=False)["valid"])

    def test_missing_or_duplicate_face_fails_closed(self):
        receipts = self.receipts()
        with self.assertRaisesRegex(ValueError, "MISSING_REQUIRED_FACE_RECEIPTS"):
            collect_receipts(receipts[:-1])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_FACE_RECEIPT"):
            collect_receipts(receipts + [receipts[0]])

    def test_bundle_tamper_fails_closed(self):
        bundle = collect_receipts(self.receipts())
        tampered = copy.deepcopy(bundle)
        tampered["authority_delta"] = 1
        self.assertFalse(verify_bundle(tampered))

    def test_self_test_passes(self):
        self.assertEqual(self_test()["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
