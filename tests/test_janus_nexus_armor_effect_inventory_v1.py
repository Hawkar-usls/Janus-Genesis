# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from tools import audit_armor_effect_drift_v18_7_50 as armor_drift


class JanusNexusArmorEffectInventoryTests(unittest.TestCase):
    def test_materializer_process_surface_is_explicit_and_narrow(self) -> None:
        materializer = armor_drift.ROOT / "tools" / "janus_nexus_materializer.py"
        rows = armor_drift.scan(materializer)

        self.assertTrue(rows)
        self.assertEqual(
            {str(row["call"]) for row in rows},
            {"subprocess.check_output"},
        )
        self.assertEqual(
            {str(row["classification"]) for row in rows},
            {"NEXUS_LOCAL_GIT_QUERY_PROCESS_SURFACE"},
        )
        self.assertTrue(all(bool(row["classified"]) for row in rows))

    def test_inventory_classification_is_not_armor_admission(self) -> None:
        self.assertEqual(
            armor_drift.classification("tools/janus_nexus_materializer.py"),
            "NEXUS_LOCAL_GIT_QUERY_PROCESS_SURFACE",
        )
        # The audit's own contract is deliberately inventory-only. This test
        # prevents future wording from turning classification into authority.
        self.assertNotIn(
            "ARMOR_ADMITTED",
            armor_drift.classification("tools/janus_nexus_materializer.py") or "",
        )


if __name__ == "__main__":
    unittest.main()
