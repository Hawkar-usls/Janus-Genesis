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
        cls.power_adapter = POWER_ADAPTER.read_text(encoding="utf-8")

    def test_exact_component_and_integration_pins_are_frozen(self) -> None:
        lineage = self.role_map["exact_lineage"]
        self.assertEqual(
            lineage["hippocampus_component_sha"],
            "938adb84975fa6a91cf6db89e9c95bf08c8fbdc9",
        )
        self.assertEqual(
            lineage["power_memory_adapter_head_sha"],
            "b1d0820eecba33dd04545f31f369f28d090c6d0f",
        )
        self.assertEqual(
            lineage["power_memory_adapter_compatibility_merge_sha"],
            "426d25acdb04b3e9a1256e75670c5b2f5b42d802",
        )
        self.assertEqual(
            lineage["cortex_component_sha"],
            "bb3c79fbae7f6f6af670562c2e0b868ca056fa89",
        )
        self.assertEqual(
            lineage["combined_memory_parent_sha"],
            "950de94d95d18e0a7dd2ba25af1788b9e86c1d92",
        )

    def test_backends_use_distinct_tables_and_roles(self) -> None:
        roles = self.role_map["roles"]
        journal = roles["OPERATIONAL_THOUGHT_JOURNAL"]
        cortex = roles["EPISODIC_SEARCH_STORE"]
        self.assertEqual(journal["table"], "thoughts")
        self.assertEqual(cortex["table"], "memories")
        self.assertNotEqual(journal["search_role"], cortex["search_role"])
        self.assertTrue(journal["historical_schema_compatibility"])
        self.assertFalse(cortex["historical_schema_compatibility"])
        self.assertIn("CREATE TABLE IF NOT EXISTS thoughts", self.journal)
        self.assertIn("CREATE TABLE IF NOT EXISTS memories", self.cortex)

    def test_power_adapter_is_journal_only(self) -> None:
        roles = self.role_map["roles"]
        self.assertTrue(roles["OPERATIONAL_THOUGHT_JOURNAL"]["default_power_telemetry_sink"])
        self.assertFalse(roles["EPISODIC_SEARCH_STORE"]["default_power_telemetry_sink"])
        self.assertIn("JanusHippocampusBufferedJournal", self.power_adapter)
        self.assertNotIn("JanusCortexMemory", self.power_adapter)
        self.assertNotIn("janus_storj_neighbor_cortex_memory", self.power_adapter)

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
        self.assertFalse(projection["source_record_content_may_be_rewritten"])
        for required in (
            "source_backend",
            "source_record_identity_or_receipt",
            "projection_policy_id",
            "projection_reason",
            "idempotency_key",
        ):
            self.assertIn(required, projection["required_fields"])

    def test_same_content_cannot_be_promoted_to_independent_evidence(self) -> None:
        authority = self.role_map["authority"]
        self.assertTrue(authority["neither_backend_is_canonical_project_chronicle"])
        self.assertTrue(authority["neither_backend_is_truth_oracle"])
        self.assertFalse(authority["recall_result_is_command"])
        self.assertFalse(authority["memory_row_is_permission"])
        self.assertFalse(authority["memory_row_is_independent_evidence"])
        laws = set(self.role_map["laws"])
        self.assertIn("BOTH_BACKENDS_AGREE != INDEPENDENT_CORROBORATION", laws)
        self.assertIn("SAME_CONTENT_IN_TWO_TABLES != TWO_EVIDENCE_ROOTS", laws)
        self.assertIn("PROJECTION != SECOND_INDEPENDENT_MEMORY_ROOT", laws)

    def test_storage_default_keeps_write_and_checkpoint_domains_separate(self) -> None:
        topology = self.role_map["storage_topology"]
        self.assertFalse(topology["same_sqlite_database_file_default"])
        self.assertEqual(
            topology["recommended_default"],
            "SEPARATE_DB_FILES_OUTSIDE_STORJ_MANAGED_ROOT",
        )
        self.assertFalse(topology["zero_storj_interference_claimed"])
        self.assertIn("active Cortex DB must not be inside a Storj-managed storage root", self.cortex)

    def test_selective_projection_is_not_implicitly_admitted(self) -> None:
        admission = self.role_map["admission"]
        self.assertEqual(admission["hippocampus_component"], "COMPATIBILITY_PASS")
        self.assertEqual(admission["cortex_component"], "COMPATIBILITY_PASS")
        self.assertEqual(admission["power_memory_adapter_pr152"], "FULL_COMPATIBILITY_PASS")
        self.assertEqual(admission["selective_projection_adapter"], "NOT_IMPLEMENTED")
        self.assertFalse(admission["live_runtime_deployment"])
        self.assertFalse(admission["production_nas_benchmark"])


if __name__ == "__main__":
    unittest.main()
