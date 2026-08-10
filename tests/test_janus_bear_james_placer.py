import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "tools/evaluate_janus_bear_james_placer.py"
spec = importlib.util.spec_from_file_location("james_placer", MOD_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def scene(scene_id, loc, *tags, explicit=False, **extra):
    row = {
        "scene_id": scene_id,
        "location_key": loc,
        "tags": list(tags),
        "explicit_james_placement_edge": explicit,
    }
    row.update(extra)
    return row


class JanusBearJamesPlacerTests(unittest.TestCase):
    def test_full_james_a_route_overlap_never_proves_placer_without_explicit_edge(self):
        scenes = [scene("A", "CELL1"), scene("B", "CELL2")]
        r = mod.evaluate(scenes, ["CELL1", "CELL2"])
        self.assertTrue(r["all_scenes_on_james_a_route"])
        self.assertEqual(r["single_placer_status"], "NOT_ESTABLISHED")
        self.assertEqual(r["bounded_subset_status"], "NOT_ESTABLISHED")

    def test_explicit_edge_supports_only_bounded_subset(self):
        scenes = [scene("A", "CELL1", explicit=True), scene("B", "CELL2")]
        r = mod.evaluate(scenes, ["CELL1", "CELL2"])
        self.assertEqual(r["explicit_james_placement_edge_count"], 1)
        self.assertEqual(r["bounded_subset_status"], "SUPPORTED_FOR_EXPLICIT_EDGE_SCENES_ONLY")
        self.assertEqual(r["single_placer_status"], "NOT_ESTABLISHED")

    def test_james_b_experimental_route_never_becomes_vanilla_evidence(self):
        scenes = [scene("A", "ZETA")]
        r = mod.evaluate(scenes, [], ["ZETA"])
        self.assertTrue(r["all_scenes_on_james_b_experimental_route"])
        self.assertFalse(r["claim_ceiling"]["james_b_route_is_vanilla_evidence"])
        self.assertEqual(r["single_placer_status"], "NOT_ESTABLISHED")

    def test_offworld_cross_world_and_quest_gated_diagnostics_are_separate(self):
        scenes = [
            scene("ZETA", "Z", mod.OFFWORLD),
            scene("POINT", "P", mod.CROSS_WORLD),
            scene("PRES", "B", mod.QUEST_GATED),
        ]
        r = mod.evaluate(scenes, [])
        self.assertEqual(r["offworld_scene_count"], 1)
        self.assertEqual(r["cross_worldspace_scene_count"], 1)
        self.assertEqual(r["quest_gated_scene_count"], 1)

    def test_missing_location_never_counts_as_route_overlap(self):
        scenes = [{"scene_id": "UNKNOWN", "tags": []}]
        r = mod.evaluate(scenes, ["CELL1"])
        self.assertEqual(r["missing_location_key_count"], 1)
        self.assertEqual(r["james_a_route_overlap_count"], 0)

    def test_pre_james_b_observable_without_lifecycle_is_candidate_not_falsification(self):
        scenes = [scene("ZETA_TABLEAU", "ZETA", mod.PRE_JAMES_B_OBSERVABLE)]
        r = mod.evaluate(scenes, [])
        self.assertEqual(r["temporal_falsifier_candidate_count"], 1)
        self.assertEqual(r["source_bound_temporal_falsifier_count"], 0)
        self.assertEqual(
            r["hypothesis_status"]["H2_JAMES_B_ALL"],
            "TEMPORAL_FALSIFIER_CANDIDATE_PENDING_EXACT_REFR_LIFECYCLE_BINDING",
        )

    def test_source_bound_static_pre_james_b_scene_falsifies_james_b_all(self):
        scenes = [
            scene(
                "ZETA_TABLEAU",
                "ZETA",
                mod.PRE_JAMES_B_OBSERVABLE,
                mod.EXACT_REFR_BOUND,
                mod.LIFECYCLE_BOUND,
            )
        ]
        r = mod.evaluate(scenes, [])
        self.assertEqual(r["source_bound_temporal_falsifier_count"], 1)
        self.assertEqual(
            r["hypothesis_status"]["H2_JAMES_B_ALL"],
            "TEMPORALLY_FALSIFIED_IN_SOURCE_BOUND_TESTED_SCENES",
        )
        self.assertFalse(r["claim_ceiling"]["retrocausality_allowed"])

    def test_dynamic_after_james_b_edge_defeats_static_preexistence_inference(self):
        scenes = [
            scene(
                "DYNAMIC_TABLEAU",
                "CELL1",
                mod.PRE_JAMES_B_OBSERVABLE,
                mod.EXACT_REFR_BOUND,
                mod.LIFECYCLE_BOUND,
                mod.DYNAMIC_AFTER_JAMES_B,
            )
        ]
        r = mod.evaluate(scenes, [])
        self.assertEqual(r["pre_james_b_observable_scene_count"], 1)
        self.assertEqual(r["dynamic_after_james_b_scene_count"], 1)
        self.assertEqual(r["temporal_falsifier_candidate_count"], 0)
        self.assertEqual(r["source_bound_temporal_falsifier_count"], 0)


if __name__ == "__main__":
    unittest.main()
