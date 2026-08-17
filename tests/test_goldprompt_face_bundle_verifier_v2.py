from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import goldprompt_face_receipts_v2 as core  # noqa: E402
from goldprompt_face_bundle_verifier_v2 import (  # noqa: E402
    verify_bundle_with_raw_evidence,
    verify_compact_bundle_replay,
)


def rev(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()[:40]


class StrictBundleVerifierV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.revisions = {
            "LEFT_HRAIN": rev("left-main"),
            "RIGHT_INAIHR": rev("right-main"),
            "DEMIHEAD_ARBITER": rev("demihead-main"),
            "GENESIS_GUARDIAN_MESH_ORCHESTRATOR": rev("genesis-main"),
        }
        self.receipts = {face: core.build_receipt(face, revision) for face, revision in self.revisions.items()}
        self.left = self.packet("LEFT_HRAIN")
        self.right = self.packet("RIGHT_INAIHR")
        self.result = self.demihead_result()
        self.bundle = core.collect_bundle(
            self.receipts.values(),
            left_packet=self.left,
            right_packet=self.right,
            demihead_result=self.result,
            expected_revisions=self.revisions,
        )

    def packet(self, face: str) -> dict:
        receipt = self.receipts[face]
        left = face == "LEFT_HRAIN"
        return {
            "schema": core.PACKET_SCHEMA,
            "packet_id": f"strict-{face.lower()}",
            "hemisphere": face,
            "role": core.EXPECTED_FACES[face]["face_role"],
            "captured_at": "2026-08-17T10:00:00Z",
            "source": {
                "repository": receipt["repository"],
                "bridge_contract": "JANUS_DEMIHEAD_BICAMERAL_BRIDGE_V2",
                "source_revision": receipt["source_revision"],
                "goldprompt_receipt_sha256": receipt["receipt_sha256"],
                "workspace_mode": "LOCAL_EDITABLE_GRAPH" if left else "SEMANTIC_GRAPH",
            },
            "goldprompt_receipt": copy.deepcopy(receipt),
            "graph": {
                "nodes": [{"id": 1, "label": "Context", "origin": "USER" if left else "SYSTEM"}],
                "links": [],
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
        upstream = {face: copy.deepcopy(packet["goldprompt_receipt"]) for face, packet in packets.items()}
        packet_receipts = {}
        chain_upstream = {}
        for face, packet in packets.items():
            packet_sha = core.sha256(packet)
            receipt = packet["goldprompt_receipt"]
            packet_receipts[face] = {
                "packet_id": packet["packet_id"],
                "sha256": packet_sha,
                "repository": receipt["repository"],
                "source_revision": receipt["source_revision"],
                "upstream_goldprompt_receipt_sha256": receipt["receipt_sha256"],
                "node_count": 1,
                "link_count": 0,
                "origin_counts": {"USER": 0, "REMOTE_AI": 0, "LOCAL_FALLBACK": 0, "LEGACY_UNKNOWN": 0, "SYSTEM": 0},
            }
            chain_upstream[face] = {
                "repository": receipt["repository"],
                "source_revision": receipt["source_revision"],
                "receipt_sha256": receipt["receipt_sha256"],
                "packet_sha256": packet_sha,
            }
        chain_core = {
            "schema": core.CHAIN_SCHEMA,
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
            "schema": core.DEMIHEAD_RESULT_SCHEMA,
            "hemispheres_present": ["LEFT_HRAIN", "RIGHT_INAIHR"],
            "goldprompt_receipt": copy.deepcopy(own),
            "upstream_goldprompt_receipts": upstream,
            "packet_receipts": packet_receipts,
            "receipt_chain": {**chain_core, "chain_sha256": core.sha256(chain_core)},
        }

    def test_compact_replay_and_raw_replay_pass(self) -> None:
        self.assertTrue(verify_compact_bundle_replay(self.bundle))
        cert = verify_bundle_with_raw_evidence(
            self.bundle,
            left_packet=self.left,
            right_packet=self.right,
            demihead_result=self.result,
            expected_revisions=self.revisions,
        )
        self.assertTrue(cert["raw_packet_bodies_replayed"])
        self.assertTrue(cert["demihead_result_replayed"])
        self.assertTrue(cert["end_to_end_receipt_binding_established"])
        self.assertFalse(cert["cross_repository_artifact_origin_attestation_established"])
        self.assertFalse(cert["live_process_identity_established"])
        self.assertEqual(cert["authority_delta"], 0)

    def test_rehashed_compact_face_hash_drift_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["demihead_chain_evidence"]["face_receipt_sha256s"]["LEFT_HRAIN"] = "0" * 64
        candidate.pop("bundle_sha256")
        candidate["bundle_sha256"] = core.sha256(candidate)
        self.assertFalse(verify_compact_bundle_replay(candidate))

    def test_rehashed_compact_chain_evidence_extra_field_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["demihead_chain_evidence"]["fake_origin_proof"] = True
        candidate.pop("bundle_sha256")
        candidate["bundle_sha256"] = core.sha256(candidate)
        self.assertFalse(verify_compact_bundle_replay(candidate))

    def test_raw_packet_hash_drift_cannot_be_hidden_by_rehashed_bundle(self) -> None:
        left = copy.deepcopy(self.left)
        left["graph"]["nodes"][0]["label"] = "Changed raw packet"
        with self.assertRaises(ValueError):
            verify_bundle_with_raw_evidence(
                self.bundle,
                left_packet=left,
                right_packet=self.right,
                demihead_result=self.result,
            )

    def test_compact_packet_hash_tamper_fails_raw_replay_even_with_valid_shape_and_rehash(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["demihead_chain_evidence"]["packet_sha256s"]["LEFT_HRAIN"] = "1" * 64
        candidate.pop("bundle_sha256")
        candidate["bundle_sha256"] = core.sha256(candidate)
        self.assertTrue(verify_compact_bundle_replay(candidate))
        with self.assertRaisesRegex(ValueError, "RAW_REPLAY_MISMATCH"):
            verify_bundle_with_raw_evidence(
                candidate,
                left_packet=self.left,
                right_packet=self.right,
                demihead_result=self.result,
            )

    def test_expected_revision_map_is_replayed_against_all_four_receipts(self) -> None:
        wrong = dict(self.revisions)
        wrong["GENESIS_GUARDIAN_MESH_ORCHESTRATOR"] = rev("other-genesis")
        with self.assertRaises(ValueError):
            verify_bundle_with_raw_evidence(
                self.bundle,
                left_packet=self.left,
                right_packet=self.right,
                demihead_result=self.result,
                expected_revisions=wrong,
            )


if __name__ == "__main__":
    unittest.main()
