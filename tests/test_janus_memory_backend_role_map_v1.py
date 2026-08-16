# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLE_MAP = ROOT / "protocol" / "JANUS_MEMORY_BACKEND_ROLE_MAP-v1.0.json"
JOURNAL = ROOT / "tools" / "janus_hippocampus_hdd_buffer.py"
CORTEX = ROOT / "tools" / "janus_storj_neighbor_cortex_memory.py"
POWER_ADAPTER = ROOT / "tools" / "janus_power_memory_runtime_adapter.py"


class MemoryBackendRoleMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.role_map = json.loads(ROLE_MAP.read_text(encoding="utf-8"))
        cls.journal = JOURNAL.read_text(encoding="utf-8")
        cls.cortex = CORTEX.read_text(encoding="utf-8")
        cls.power_adapter = POWER_ADAPTER.read_text(encoding="utf-8") if POWER_ADAPTER.exists() else ""

    def test_exact_component_pins_are_frozen(self) -> None:
        lineage = self.role_map["exact_lineage"]
        self.assertEqual(
            lineage["hippocampus_component_sha"],
            "938adb84975fa6a91cf6db89e9c95bf08c8fbdc9",
        )
        self.assertEqual(
            lineage["cortex_component_sha"],
            "bb3c79fbae7f6f6af670562c2e0b868ca056fa89",
        )
        self.assertEqual(
            lineage["combined_memory_parent_sha"],
            "1a274b1891317d69c6f02da18ed7c49bd3568a37",
        )

    def test_backends_use_distinct_tables_and_roles(self) -> None:
        roles = self.role_map["roles"]
        self.assertEqual(roles["OPERATIONAL_THOUGHT_JOURNAL"]["table"], "thoughts")
        self.assertEqual(roles["EPISODIC_SEARCH_STORE"]["table"], "memories")
        self.assertNotEqual(
            roles["OPERATIONAL_THOUGHT_JOURNAL"]["search_role"],
            roles["EPISODIC_SEARCH_STORE"]["search_role"],
        )
        self.assertIn("CREATE TABLE IF NOT EXISTS thoughts", self.journal)
        self.assertIn("CREATE TABLE IF NOT EXISTS memories", self.cortex)

    def test_dual_write_is_fail_closed_by_policy(self) -> None:
        routing = self.role_map["routing"]
        self.assertEqual(routing["dual_write_default"], "DENY")
        self.assertFalse(routing["power_telemetry_to_cortex_default"])
        self.assertFalse(routing["journal_to_cortex_automatic_mirroring"])
        self.assertFalse(routing["cortex_to_journal_automatic_mirroring"])
        self.assertEqual(
            routing["power_telemetry_default_route"],
            ["OPERATIONAL_THOUGHT_JOURNAL"],
        )

    def test_cortex_projection_requires_provenance_and_idempotency(self) -> None:
        projection = self.role_map["routing"]["selective_projection_to_cortex"]
        self.assertEqual(
            projection["status"], "REQUIRES_SEPARATE_ADAPTER_AND_EXPLICIT_POLICY"
        )
        self.assertFalse(projection["implicit_selection"])
        self.assertTrue(projection["projection_receipt_required"])
        self.assertIn("source_record_identity_or_receipt", projection["required_fields"])
        self.assertIn("projection_policy_id", projection["required_fields"])
        self.assertIn("idempotency_key", projection["required_fields"])

    def test_neither_backend_is_promoted_to_truth_or_command(self) -> None:
        authority = self.role_map["authority"]
        self.assertTrue(authority["neither_backend_is_canonical_project_chronicle"])
        self.assertTrue(authority["neither_backend_is_truth_oracle"])
        self.assertFalse(authority["recall_result_is_command"])
        self.assertFalse(authority["memory_row_is_permission"])
        self.assertFalse(authority["memory_row_is_independent_evidence"])
        laws = set(self.role_map["laws"])
        self.assertIn("BOTH_BACKENDS_AGREE != INDEPENDENT_CORROBORATION", laws)
        self.assertIn("SAME_CONTENT_IN_TWO_TABLES != TWO_EVIDENCE_ROOTS", laws)

    def test_storage_default_keeps_failure_domains_separate(self) -> None:
        topology = self.role_map["storage_topology"]
        self.assertFalse(topology["same_sqlite_database_file_default"])
        self.assertEqual(
            topology["recommended_default"],
            "SEPARATE_DB_FILES_OUTSIDE_STORJ_MANAGED_ROOT",
        )
        self.assertFalse(topology["zero_storj_interference_claimed"])

    def test_current_power_adapter_does_not_dual_write_to_cortex(self) -> None:
        # The role map is allowed to exist independently of PR152's files, but
        # when the Power adapter is present it must remain journal-only until a
        # separately admitted projection adapter exists.
        if not self.power_adapter:
            self.skipTest("Power adapter is not part of this exact merge view")
        self.assertIn("JanusHippocampusBufferedJournal", self.power_adapter)
        self.assertNotIn("JanusCortexMemory", self.power_adapter)
        self.assertNotIn("janus_storj_neighbor_cortex_memory", self.power_adapter)

    def test_selective_projection_is_still_unimplemented(self) -> None:
        admission = self.role_map["admission"]
        self.assertEqual(admission["selective_projection_adapter"], "NOT_IMPLEMENTED")
        self.assertFalse(admission["live_runtime_deployment"])
        self.assertFalse(admission["production_nas_benchmark"])


if __name__ == "__main__":
    unittest.main()
