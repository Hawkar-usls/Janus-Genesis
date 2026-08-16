from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from infinite_faces_async_microstagger import (  # noqa: E402
    COMMIT_GUARD_MS,
    GATHER_WINDOW_MS,
    HARD_CAP_MS,
    INTENTIONAL_LATENCY_BUDGET_MS,
    MAX_ACTIVE_FACES_PER_TURN,
    STAGGER_WINDOW_MS,
    FaceProposal,
    build_schedule,
    classify_deadline,
    gather_concurrently,
    self_test,
)


class InfiniteFacesAsyncMicrostaggerTests(unittest.TestCase):
    def test_budget_is_exactly_24ms_with_32ms_hard_cap(self) -> None:
        self.assertEqual(STAGGER_WINDOW_MS, 6)
        self.assertEqual(GATHER_WINDOW_MS, 12)
        self.assertEqual(COMMIT_GUARD_MS, 6)
        self.assertEqual(INTENTIONAL_LATENCY_BUDGET_MS, 24)
        self.assertEqual(HARD_CAP_MS, 32)

    def test_schedule_is_deterministic(self) -> None:
        proposals = [
            FaceProposal("FACE_0000", "A"),
            FaceProposal("FACE_0001", "B"),
            FaceProposal("FACE_0002", "C"),
        ]
        self.assertEqual(build_schedule("TURN_1", proposals), build_schedule("TURN_1", proposals))

    def test_offsets_do_not_accumulate_with_face_count(self) -> None:
        proposals = [FaceProposal(f"FACE_{i:04d}", str(i)) for i in range(MAX_ACTIVE_FACES_PER_TURN)]
        result = asyncio.run(gather_concurrently("TURN_2", proposals))
        offsets = [row["start_offset_ms"] for row in result["scheduled"]]
        self.assertLessEqual(max(offsets), STAGGER_WINDOW_MS)
        self.assertLessEqual(result["timing"]["actual_logical_total_for_this_schedule_ms"], 24)
        self.assertFalse(result["timing"]["per_face_delay_accumulates_serially"])

    def test_one_host_commit_parallelism_is_one(self) -> None:
        result = asyncio.run(
            gather_concurrently(
                "TURN_3",
                [FaceProposal("FACE_0000", "STAY"), FaceProposal("FACE_0001", "CROSS")],
            )
        )
        self.assertEqual(result["world_commit_parallelism_for_one_host"], 1)
        self.assertFalse(result["invariants"]["proposal_is_world_commit"])

    def test_offset_does_not_encode_authority(self) -> None:
        result = asyncio.run(
            gather_concurrently(
                "TURN_4",
                [FaceProposal("FACE_0000", "A"), FaceProposal("FACE_0001", "B")],
            )
        )
        self.assertFalse(result["invariants"]["start_offset_is_authority"])
        self.assertFalse(result["invariants"]["face_count_is_voting_power"])

    def test_late_proposal_is_deferred_not_erased(self) -> None:
        self.assertEqual(classify_deadline(24), "ADMITTED_TO_CURRENT_GATHER")
        self.assertEqual(classify_deadline(25), "DEFERRED_LATE_PRESERVE_PROVENANCE")
        self.assertEqual(classify_deadline(40), "DEFERRED_AFTER_HARD_CAP_PRESERVE_PROVENANCE")

    def test_active_workset_is_bounded_without_bounding_face_namespace(self) -> None:
        arbitrary = asyncio.run(
            gather_concurrently(
                "TURN_N",
                [FaceProposal("FACE_123456789012345678901234567890", "arbitrary n")],
            )
        )
        self.assertEqual(arbitrary["face_namespace_cardinality"], "UNBOUNDED")
        with self.assertRaises(ValueError):
            build_schedule(
                "TURN_TOO_WIDE",
                [FaceProposal(f"FACE_{i}", str(i)) for i in range(MAX_ACTIVE_FACES_PER_TURN + 1)],
            )

    def test_authoritative_save_boundary_is_preserved(self) -> None:
        result = asyncio.run(gather_concurrently("TURN_5", [FaceProposal("FACE_0000", "A")]))
        self.assertFalse(result["invariants"]["canonical_python_save_changed"])
        self.assertFalse(result["invariants"]["shared_network_changed"])
        self.assertFalse(result["timing"]["human_imperceptibility_proven"])

    def test_embedded_self_test(self) -> None:
        self.assertTrue(all(value == "PASS" for value in self_test().values()))


if __name__ == "__main__":
    unittest.main()
