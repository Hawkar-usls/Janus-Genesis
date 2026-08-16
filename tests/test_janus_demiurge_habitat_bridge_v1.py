#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ast
import copy
import json
import unittest
from pathlib import Path

from tools.janus_demiurge_habitat_bridge import (
    FACE_ID,
    LEGACY_PATTERN_SOURCE_COMMIT,
    PROPOSAL_SCHEMA,
    RANKING_SCHEMA,
    DemiurgeHandoffError,
    canonical_sha256,
    make_handoff,
    validate_demiurge_payload,
)


class DemiurgeHabitatBridgeTests(unittest.TestCase):
    def _proposal(self):
        rows = [
            {
                "proposal_id": f"{index:024x}",
                "config": {"alpha": 0.1 + index * 0.01},
                "tested": False,
                "selected": False,
                "authorized": False,
            }
            for index in range(1, 5)
        ]
        payload = {
            "schema": PROPOSAL_SCHEMA,
            "face_id": FACE_ID,
            "source_commit": LEGACY_PATTERN_SOURCE_COMMIT,
            "request_id": "fixture-request",
            "request_digest": "a" * 64,
            "proposal_count": len(rows),
            "proposals": rows,
            "execution_requested": False,
            "source_writeback_requested": False,
            "selection_authority_claimed": False,
        }
        payload["receipt_sha256"] = canonical_sha256(payload)
        return payload

    def _ranking(self):
        proposal = self._proposal()
        ranking = [
            {"proposal_id": row["proposal_id"], "score": float(100 - index)}
            for index, row in enumerate(proposal["proposals"])
        ]
        payload = {
            "schema": RANKING_SCHEMA,
            "face_id": FACE_ID,
            "proposal_receipt_sha256": proposal["receipt_sha256"],
            "objective": "score",
            "maximize": True,
            "ranking": ranking,
            "selected_proposal_id": ranking[0]["proposal_id"],
            "selection_is_recommendation_only": True,
            "authorized": False,
            "execution_requested": False,
            "source_writeback_requested": False,
        }
        payload["receipt_sha256"] = canonical_sha256(payload)
        return payload

    def test_proposal_handoff_is_authority_neutral(self):
        handoff = make_handoff(self._proposal())
        self.assertEqual(handoff["handoff_target"], "NEXUS_VARIANT_LINEAGE_OR_VERIFIER")
        self.assertFalse(handoff["execute"])
        self.assertFalse(handoff["authorized"])
        self.assertFalse(handoff["source_writeback"])
        self.assertFalse(handoff["external_effect"])
        self.assertFalse(handoff["implementation_membership_proven_by_payload"])

    def test_ranking_handoff_routes_only_to_core_reconciler(self):
        handoff = make_handoff(self._ranking())
        self.assertEqual(handoff["handoff_target"], "JANUS_CORE_RECONCILER")
        self.assertFalse(handoff["authorized"])
        unsigned = dict(handoff)
        receipt = unsigned.pop("receipt_sha256")
        self.assertEqual(receipt, canonical_sha256(unsigned))

    def test_tampered_payload_receipt_is_rejected(self):
        payload = self._proposal()
        payload["proposals"][0]["config"]["alpha"] = 0.49
        with self.assertRaises(DemiurgeHandoffError):
            validate_demiurge_payload(payload)

    def test_rehashed_authorized_proposal_is_still_rejected(self):
        payload = self._proposal()
        payload["proposals"][0]["authorized"] = True
        unsigned = dict(payload)
        unsigned.pop("receipt_sha256")
        payload["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeHandoffError):
            validate_demiurge_payload(payload)

    def test_rehashed_authorized_ranking_is_still_rejected(self):
        payload = self._ranking()
        payload["authorized"] = True
        unsigned = dict(payload)
        unsigned.pop("receipt_sha256")
        payload["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeHandoffError):
            validate_demiurge_payload(payload)

    def test_ranking_order_is_checked_not_merely_trusted(self):
        payload = self._ranking()
        payload["ranking"][0]["score"] = -999.0
        unsigned = dict(payload)
        unsigned.pop("receipt_sha256")
        payload["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeHandoffError):
            validate_demiurge_payload(payload)

    def test_unknown_payload_fields_cannot_smuggle_effects(self):
        payload = self._proposal()
        payload["effects"] = {"allow_external_compute": True}
        unsigned = dict(payload)
        unsigned.pop("receipt_sha256")
        payload["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeHandoffError):
            validate_demiurge_payload(payload)

    def test_admission_overlay_binds_green_source_pr_without_active_claim(self):
        path = Path(__file__).resolve().parents[1] / "protocol" / "JANUS_DEMIURGE_HABITAT_ADMISSION-v1.0.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["new_evidence"]["source_head"], "c5bb2c48f084ba6983f33aa562f164b614308f1f")
        self.assertEqual(data["new_evidence"]["conclusion"], "SUCCESS")
        self.assertEqual(data["face"]["activation"], "ADMISSION_CANDIDATE_HOLD")
        self.assertFalse(data["claim_ceiling"]["active_runtime_face"])
        self.assertEqual(data["claim_ceiling"]["authority_delta"], 0)

    def test_bridge_has_no_network_process_or_file_write_surface(self):
        path = Path(__file__).resolve().parents[1] / "tools" / "janus_demiurge_habitat_bridge.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_roots = {
            "aiohttp", "httpx", "requests", "socket", "subprocess", "urllib",
            "os", "pathlib", "shutil", "ftplib", "paramiko"
        }
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "compile", "__import__"})
        self.assertTrue(imports.isdisjoint(forbidden_roots), imports)


if __name__ == "__main__":
    unittest.main()
