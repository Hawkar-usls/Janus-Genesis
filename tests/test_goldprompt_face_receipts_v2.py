from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import goldprompt_face_receipts_v2 as gp  # noqa: E402


def rev(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()[:40]


class GoldPromptReceiptChainV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.revisions = {
            "LEFT_HRAIN": rev("left-main"),
            "RIGHT_INAIHR": rev("right-main"),
            "DEMIHEAD_ARBITER": rev("demihead-main"),
            "GENESIS_GUARDIAN_MESH_ORCHESTRATOR": rev("genesis-main"),
        }
        self.receipts = {face: gp.build_receipt(face, revision) for face, revision in self.revisions.items()}
        self.left = self.packet("LEFT_HRAIN", self.receipts["LEFT_HRAIN"])
        self.right = self.packet("RIGHT_INAIHR", self.receipts["RIGHT_INAIHR"])
        self.result = self.demihead_result()

    def packet(self, face: str, receipt: dict) -> dict:
        left = face == "LEFT_HRAIN"
        return {
            "schema": gp.PACKET_SCHEMA,
            "packet_id": "fixture-left" if left else "fixture-right",
            "hemisphere": face,
            "role": gp.EXPECTED_FACES[face]["face_role"],
            "captured_at": "2026-08-17T09:40:00Z",
            "source": {
                "repository": gp.EXPECTED_FACES[face]["repository"],
                "bridge_contract": "JANUS_DEMIHEAD_BICAMERAL_BRIDGE_V2",
                "source_revision": receipt["source_revision"],
                "goldprompt_receipt_sha256": receipt["receipt_sha256"],
                "workspace_mode": "LOCAL_EDITABLE_GRAPH" if left else "SEMANTIC_GRAPH",
            },
            "goldprompt_receipt": copy.deepcopy(receipt),
            "graph": {
                "nodes": [
                    {"id": 1, "label": "Context", "origin": "USER" if left else "SYSTEM"},
                    {"id": 2, "label": "Evidence", "origin": "USER" if left else "LOCAL_FALLBACK"},
                ],
                "links": [{"source": 1, "target": 2}],
            },
            "control": {
                "read_only_transfer": True,
                "direct_cross_hemisphere_mutation": False,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
            },
        }

    def demihead_result(self) -> dict:
        own = self.receipts["DEMIHEAD_ARBITER"]
        packets = {"LEFT_HRAIN": self.left, "RIGHT_INAIHR": self.right}
        packet_receipts = {}
        upstream = {}
        chain_upstream = {}
        for face, packet in packets.items():
            packet_sha = gp.sha256(packet)
            receipt = packet["goldprompt_receipt"]
            upstream[face] = copy.deepcopy(receipt)
            packet_receipts[face] = {
                "packet_id": packet["packet_id"],
                "sha256": packet_sha,
                "repository": packet["source"]["repository"],
                "source_revision": packet["source"]["source_revision"],
                "upstream_goldprompt_receipt_sha256": receipt["receipt_sha256"],
                "node_count": len(packet["graph"]["nodes"]),
                "link_count": len(packet["graph"]["links"]),
                "origin_counts": {"USER": 0, "REMOTE_AI": 0, "LOCAL_FALLBACK": 0, "LEGACY_UNKNOWN": 0, "SYSTEM": 0},
            }
            chain_upstream[face] = {
                "repository": receipt["repository"],
                "source_revision": receipt["source_revision"],
                "receipt_sha256": receipt["receipt_sha256"],
                "packet_sha256": packet_sha,
            }
        chain_core = {
            "schema": gp.CHAIN_SCHEMA,
            "upstream": chain_upstream,
            "demihead": {
                "repository": own["repository"],
                "source_revision": own["source_revision"],
                "receipt_sha256": own["receipt_sha256"],
            },
            "binding_scope": "UPSTREAM_FACE_RECEIPT_TO_PACKET_TO_DEMIHEAD_RESULT",
            "canonical_bicameral_chain_complete": True,
            "end_to_end_receipt_binding_established": True,
            "origin_authentication_established": False,
            "live_process_identity_established": False,
            "authority_delta": 0,
        }
        return {
            "schema": gp.DEMIHEAD_RESULT_SCHEMA,
            "hemispheres_present": ["LEFT_HRAIN", "RIGHT_INAIHR"],
            "goldprompt_receipt": copy.deepcopy(own),
            "upstream_goldprompt_receipts": upstream,
            "packet_receipts": packet_receipts,
            "receipt_chain": {**chain_core, "chain_sha256": gp.sha256(chain_core)},
        }

    def test_frozen_contract_and_manifest_match(self) -> None:
        self.assertEqual(gp.contract_digest(), gp.EXPECTED_CONTRACT_DIGEST)
        self.assertEqual(gp.dependency_manifest_digest(), gp.EXPECTED_DEPENDENCY_MANIFEST_DIGEST)
        self.assertEqual(gp.STARTUP_CONTRACT_DIGEST, gp.EXPECTED_CONTRACT_DIGEST)
        self.assertEqual(gp.STARTUP_DEPENDENCY_MANIFEST_DIGEST, gp.EXPECTED_DEPENDENCY_MANIFEST_DIGEST)

    def test_all_v1_1_receipts_bind_transitive_manifest(self) -> None:
        for face, receipt in self.receipts.items():
            self.assertTrue(gp.verify_receipt(receipt, self.revisions[face]), face)
            self.assertEqual(receipt["dependency_manifest_digest_sha256"], gp.EXPECTED_DEPENDENCY_MANIFEST_DIGEST)
            self.assertEqual(receipt["authority_weight"], 0)

    def test_genesis_independently_recomputes_raw_packet_and_chain_hashes(self) -> None:
        evidence = gp.verify_demihead_result_with_raw_packets(
            self.result, self.left, self.right, expected_revisions=self.revisions
        )
        self.assertTrue(evidence["valid"])
        self.assertTrue(evidence["verified_raw_packet_binding"])
        self.assertTrue(evidence["end_to_end_receipt_binding_established"])
        self.assertFalse(evidence["origin_authentication_established"])
        self.assertFalse(evidence["live_process_identity_established"])
        self.assertEqual(evidence["packet_sha256s"]["LEFT_HRAIN"], gp.sha256(self.left))
        self.assertEqual(evidence["packet_sha256s"]["RIGHT_INAIHR"], gp.sha256(self.right))

    def test_canonical_v2_bundle_requires_chain_receipts_to_equal_face_receipts(self) -> None:
        bundle = gp.collect_bundle(
            self.receipts.values(),
            left_packet=self.left,
            right_packet=self.right,
            demihead_result=self.result,
            expected_revisions=self.revisions,
        )
        self.assertTrue(gp.verify_bundle(bundle))
        self.assertTrue(bundle["end_to_end_receipt_binding_established"])
        self.assertTrue(bundle["raw_packet_binding_verified_by_genesis"])
        self.assertFalse(bundle["cross_repository_artifact_origin_attestation_established"])
        self.assertFalse(bundle["end_to_end_message_authentication_established"])
        self.assertFalse(bundle["live_process_identity_established"])
        self.assertEqual(bundle["authority_delta"], 0)

    def test_rehashed_manifest_drift_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.receipts["LEFT_HRAIN"])
        candidate["dependency_manifest_digest_sha256"] = "0" * 64
        payload = dict(candidate)
        payload.pop("receipt_sha256")
        candidate["receipt_sha256"] = gp.sha256(payload)
        self.assertFalse(gp.verify_receipt(candidate))

    def test_raw_packet_tamper_is_rejected_even_if_demihead_result_is_unchanged(self) -> None:
        left = copy.deepcopy(self.left)
        left["graph"]["nodes"][0]["label"] = "Tampered after DemiHead"
        with self.assertRaisesRegex(ValueError, "RAW_PACKET_SHA_MISMATCH"):
            gp.verify_demihead_result_with_raw_packets(self.result, left, self.right)

    def test_chain_hash_tamper_is_rejected(self) -> None:
        result = copy.deepcopy(self.result)
        result["receipt_chain"]["chain_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "CHAIN_SHA_MISMATCH"):
            gp.verify_demihead_result_with_raw_packets(result, self.left, self.right)

    def test_swapped_upstream_receipt_is_rejected(self) -> None:
        result = copy.deepcopy(self.result)
        result["upstream_goldprompt_receipts"]["LEFT_HRAIN"] = copy.deepcopy(self.receipts["RIGHT_INAIHR"])
        with self.assertRaisesRegex(ValueError, "UPSTREAM_RECEIPT_NOT_RAW_PACKET_RECEIPT"):
            gp.verify_demihead_result_with_raw_packets(result, self.left, self.right)

    def test_bundle_face_receipt_not_in_chain_is_rejected(self) -> None:
        receipts = copy.deepcopy(self.receipts)
        receipts["LEFT_HRAIN"] = gp.build_receipt("LEFT_HRAIN", rev("different-left"))
        with self.assertRaisesRegex(ValueError, "BUNDLE_FACE_RECEIPT_NOT_CHAIN_RECEIPT"):
            gp.collect_bundle(
                receipts.values(), left_packet=self.left, right_packet=self.right,
                demihead_result=self.result,
            )

    def test_bundle_rehash_cannot_promote_origin_or_live_auth(self) -> None:
        bundle = gp.collect_bundle(
            self.receipts.values(), left_packet=self.left, right_packet=self.right,
            demihead_result=self.result,
        )
        for field in (
            "cross_repository_artifact_origin_attestation_established",
            "end_to_end_message_authentication_established",
            "live_process_identity_established",
        ):
            candidate = copy.deepcopy(bundle)
            candidate[field] = True
            candidate.pop("bundle_sha256")
            candidate["bundle_sha256"] = gp.sha256(candidate)
            self.assertFalse(gp.verify_bundle(candidate), field)

    def test_four_face_set_and_expected_revision_map_are_exact(self) -> None:
        with self.assertRaisesRegex(ValueError, "CANONICAL_FOUR_FACE_RECEIPT_SET_REQUIRED"):
            gp.collect_bundle(
                list(self.receipts.values())[:-1], left_packet=self.left, right_packet=self.right,
                demihead_result=self.result,
            )
        bad_expected = dict(self.revisions)
        bad_expected.pop("LEFT_HRAIN")
        with self.assertRaisesRegex(ValueError, "EXPECTED_SOURCE_REVISION_FACE_SET_MISMATCH"):
            gp.collect_bundle(
                self.receipts.values(), left_packet=self.left, right_packet=self.right,
                demihead_result=self.result, expected_revisions=bad_expected,
            )


if __name__ == "__main__":
    unittest.main()
