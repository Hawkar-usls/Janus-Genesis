from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from goldprompt_intent_guard import build_intent_anchor, sha256_json  # noqa: E402
from goldprompt_intent_chain import (  # noqa: E402
    CERTIFICATE_SCHEMA,
    DEMIHEAD_RESULT_SCHEMA,
    GENESIS_FACE_ID,
    INTENT_CHAIN_SCHEMA,
    PACKET_SCHEMA,
    _expected_demihead_chain,
    build_certificate,
    build_strict_handoff,
    verify_certificate,
    verify_demihead_intent_result,
    verify_intent_packet,
    verify_strict_handoff,
)


def fixture_anchor() -> dict:
    return build_intent_anchor(
        current_turn="Сравни возвращение Осириса с возвращением Иисуса Христа",
        requested_operation="COMPARE",
        primary_entities={"OSIRIS": ["осирис"], "JESUS_CHRIST": ["иисус", "христос"]},
        must_answer_points=["Compare both models", "Distinguish resurrection and Second Coming"],
        required_answer_evidence=[["осирис"], ["христос"], ["воскрес"], ["второе пришествие"]],
        operation_markers=["сравн"],
        optional_association_markers=["bd101", "janus"],
    )


def fixture_packet(face: str, anchor: dict) -> dict:
    handoff = build_strict_handoff(anchor, face, 2)
    return {
        "schema": PACKET_SCHEMA,
        "hemisphere": face,
        "source": {
            "intent_id": anchor["intent_id"],
            "intent_handoff_sha256": handoff["handoff_sha256"],
            "repository": "fixture",
        },
        "intent_anchor": copy.deepcopy(anchor),
        "intent_handoff": handoff,
        "payload": {"fixture": face},
    }


def fixture_demihead(anchor: dict, left: dict, right: dict) -> dict:
    own = build_strict_handoff(anchor, "DEMIHEAD_ARBITER", 2)
    return {
        "schema": DEMIHEAD_RESULT_SCHEMA,
        "intent_anchor": copy.deepcopy(anchor),
        "upstream_intent_handoffs": {
            "LEFT_HRAIN": copy.deepcopy(left["intent_handoff"]),
            "RIGHT_INAIHR": copy.deepcopy(right["intent_handoff"]),
        },
        "demihead_intent_handoff": own,
        "intent_chain": _expected_demihead_chain(anchor, left, right, own),
        "routing": {
            "intent_alignment_required": True,
            "intent_split_permitted": False,
            "older_context_may_redefine_task": False,
            "optional_association_may_replace_primary_path": False,
        },
    }


class GoldPromptIntentChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = fixture_anchor()
        self.left = fixture_packet("LEFT_HRAIN", self.anchor)
        self.right = fixture_packet("RIGHT_INAIHR", self.anchor)
        self.demi = fixture_demihead(self.anchor, self.left, self.right)

    def test_strict_handoff_replays_for_all_faces(self) -> None:
        for face in ("LEFT_HRAIN", "RIGHT_INAIHR", "DEMIHEAD_ARBITER", GENESIS_FACE_ID):
            handoff = build_strict_handoff(self.anchor, face, 2)
            self.assertTrue(verify_strict_handoff(self.anchor, handoff, face))

    def test_packets_and_demihead_chain_replay(self) -> None:
        self.assertTrue(verify_intent_packet(self.left, self.anchor, "LEFT_HRAIN"))
        self.assertTrue(verify_intent_packet(self.right, self.anchor, "RIGHT_INAIHR"))
        self.assertTrue(verify_demihead_intent_result(self.demi, anchor=self.anchor, left=self.left, right=self.right))

    def test_four_node_certificate_passes(self) -> None:
        cert = build_certificate(anchor=self.anchor, left=self.left, right=self.right, demihead_result=self.demi)
        self.assertEqual(cert["schema"], CERTIFICATE_SCHEMA)
        self.assertTrue(cert["all_nodes_same_intent"])
        self.assertFalse(cert["intent_reinterpretation_permitted"])
        self.assertFalse(cert["emergence_may_replace_primary_intent"])
        self.assertTrue(cert["final_output_alignment_gate_required"])
        self.assertEqual(cert["authority_delta"], 0)
        self.assertTrue(verify_certificate(cert, anchor=self.anchor, left=self.left, right=self.right, demihead_result=self.demi))

    def test_rehashed_operation_drift_in_handoff_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.left)
        candidate["intent_handoff"]["requested_operation"] = "SUMMARIZE"
        h = candidate["intent_handoff"]
        payload = dict(h)
        payload.pop("handoff_sha256")
        h["handoff_sha256"] = sha256_json(payload)
        candidate["source"]["intent_handoff_sha256"] = h["handoff_sha256"]
        self.assertFalse(verify_intent_packet(candidate, self.anchor, "LEFT_HRAIN"))

    def test_packet_body_tamper_breaks_demihead_chain(self) -> None:
        changed = copy.deepcopy(self.left)
        changed["payload"]["fixture"] = "OLDER_BD101_TASK"
        self.assertFalse(verify_demihead_intent_result(self.demi, anchor=self.anchor, left=changed, right=self.right))

    def test_anchor_split_is_rejected(self) -> None:
        changed_anchor = fixture_anchor()
        changed_anchor["requested_operation"] = "DEVELOP_BD101_ARCHITECTURE"
        changed_anchor.pop("intent_id")
        changed_anchor["intent_id"] = sha256_json(changed_anchor)
        changed_right = fixture_packet("RIGHT_INAIHR", changed_anchor)
        self.assertFalse(verify_demihead_intent_result(self.demi, anchor=self.anchor, left=self.left, right=changed_right))

    def test_certificate_semantic_tamper_rejected_even_after_rehash(self) -> None:
        cert = build_certificate(anchor=self.anchor, left=self.left, right=self.right, demihead_result=self.demi)
        candidate = copy.deepcopy(cert)
        candidate["intent_reinterpretation_permitted"] = True
        payload = dict(candidate)
        payload.pop("certificate_sha256")
        candidate["certificate_sha256"] = sha256_json(payload)
        self.assertFalse(verify_certificate(candidate, anchor=self.anchor, left=self.left, right=self.right, demihead_result=self.demi))

    def test_intent_chain_schema_is_bound(self) -> None:
        self.assertEqual(self.demi["intent_chain"]["schema"], INTENT_CHAIN_SCHEMA)
        self.assertFalse(self.demi["intent_chain"]["emergent_association_may_replace_intent"])


if __name__ == "__main__":
    unittest.main()
