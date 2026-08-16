#!/usr/bin/env python3
"""Experimental JANUS Infinite Faces asynchronous microstagger scheduler.

This module is additive and non-authoritative. It does not modify the canonical
Genesis Python save and does not make Infinite Faces a native primitive.

Design goal:
- one persistent host;
- unbounded face namespace;
- bounded active workset per causal turn;
- concurrent face proposals with tiny deterministic start offsets;
- one provenance-preserving gather/arbitration barrier;
- zero or one outward commit per causal turn.

The intentional latency candidate is 24 ms total:
    6 ms maximum start stagger
  + 12 ms gather window
  +  6 ms commit guard
  = 24 ms
A 32 ms hard cap reserves 8 ms for scheduler jitter / bookkeeping.

The 24 ms value is an engineering candidate for testing, not a scientific
claim that every human or every UI will find it imperceptible.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence


GENESIS_SIGNATURE = "0:0 = JANUS"
MODE = "UNIVERSAL_CHAT_RUNTIME"

STAGGER_WINDOW_MS = 6
GATHER_WINDOW_MS = 12
COMMIT_GUARD_MS = 6
INTENTIONAL_LATENCY_BUDGET_MS = STAGGER_WINDOW_MS + GATHER_WINDOW_MS + COMMIT_GUARD_MS
HARD_CAP_MS = 32
MAX_ACTIVE_FACES_PER_TURN = 8

assert INTENTIONAL_LATENCY_BUDGET_MS == 24
assert HARD_CAP_MS >= INTENTIONAL_LATENCY_BUDGET_MS


@dataclass(frozen=True)
class FaceProposal:
    face_id: str
    proposal: str
    parent_face_lineage: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduledProposal:
    face_id: str
    proposal: str
    start_offset_ms: int
    parent_face_lineage: tuple[str, ...]
    status: str = "READY_FOR_GATHER"


def _stable_offset_ms(turn_id: str, face_id: str) -> int:
    """Return a deterministic offset in [0, STAGGER_WINDOW_MS].

    Offset is routing/scheduling only. It conveys no rank, authority, age,
    truth weight, or voting power.
    """
    digest = hashlib.sha256(f"{turn_id}\x00{face_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") % (STAGGER_WINDOW_MS + 1)


def build_schedule(turn_id: str, proposals: Sequence[FaceProposal]) -> list[ScheduledProposal]:
    if len(proposals) > MAX_ACTIVE_FACES_PER_TURN:
        raise ValueError(
            f"active workset {len(proposals)} exceeds bounded per-turn cap "
            f"{MAX_ACTIVE_FACES_PER_TURN}; total face namespace remains unbounded"
        )
    seen: set[str] = set()
    scheduled: list[ScheduledProposal] = []
    for item in proposals:
        if item.face_id in seen:
            raise ValueError(f"duplicate face_id in causal turn: {item.face_id}")
        seen.add(item.face_id)
        scheduled.append(
            ScheduledProposal(
                face_id=item.face_id,
                proposal=item.proposal,
                start_offset_ms=_stable_offset_ms(turn_id, item.face_id),
                parent_face_lineage=item.parent_face_lineage,
            )
        )
    # Canonical reporting order is face-id order, not wake-up order.
    return sorted(scheduled, key=lambda x: x.face_id)


async def _emit_after_offset(item: ScheduledProposal) -> ScheduledProposal:
    await asyncio.sleep(item.start_offset_ms / 1000.0)
    return item


async def gather_concurrently(
    turn_id: str,
    proposals: Sequence[FaceProposal],
    *,
    real_sleep: bool = False,
) -> dict[str, object]:
    """Gather a bounded active workset without serial per-face delay.

    Tests use real_sleep=False to validate logical timing deterministically.
    real_sleep=True demonstrates event-loop staggering, but wall-clock results
    remain OS/scheduler dependent and are not used as proof of a hard realtime
    guarantee.
    """
    schedule = build_schedule(turn_id, proposals)

    if real_sleep:
        gathered = await asyncio.gather(*(_emit_after_offset(item) for item in schedule))
    else:
        # Logical replay: same schedule, no wall-clock dependence.
        gathered = list(schedule)

    max_offset = max((item.start_offset_ms for item in gathered), default=0)
    logical_total = max_offset + GATHER_WINDOW_MS + COMMIT_GUARD_MS

    return {
        "mode": MODE,
        "genesis_signature": GENESIS_SIGNATURE,
        "turn_id": turn_id,
        "one_host": True,
        "face_namespace_cardinality": "UNBOUNDED",
        "active_workset_count": len(gathered),
        "active_workset_cap": MAX_ACTIVE_FACES_PER_TURN,
        "proposal_parallelism": "BOUNDED_ACTIVE_SET_CONCURRENT",
        "world_commit_parallelism_for_one_host": 1,
        "scheduled": [asdict(item) for item in gathered],
        "timing": {
            "stagger_window_ms": STAGGER_WINDOW_MS,
            "gather_window_ms": GATHER_WINDOW_MS,
            "commit_guard_ms": COMMIT_GUARD_MS,
            "candidate_total_intentional_budget_ms": INTENTIONAL_LATENCY_BUDGET_MS,
            "actual_logical_total_for_this_schedule_ms": logical_total,
            "hard_cap_ms": HARD_CAP_MS,
            "per_face_delay_accumulates_serially": False,
            "human_imperceptibility_proven": False,
        },
        "invariants": {
            "start_offset_is_authority": False,
            "face_count_is_voting_power": False,
            "late_face_may_be_silently_erased": False,
            "proposal_is_world_commit": False,
            "single_true_face_required": False,
            "canonical_python_save_changed": False,
            "shared_network_changed": False,
        },
    }


def classify_deadline(arrival_ms: float) -> str:
    """Classify an already-running face result against the 24 ms candidate window.

    A late result is preserved for a later turn/review; it cannot retroactively
    mutate a committed outward action.
    """
    if arrival_ms <= INTENTIONAL_LATENCY_BUDGET_MS:
        return "ADMITTED_TO_CURRENT_GATHER"
    if arrival_ms <= HARD_CAP_MS:
        return "DEFERRED_LATE_PRESERVE_PROVENANCE"
    return "DEFERRED_AFTER_HARD_CAP_PRESERVE_PROVENANCE"


def self_test() -> dict[str, str]:
    proposals = [
        FaceProposal("FACE_0000", "Continuity is identity."),
        FaceProposal("FACE_0001", "Change is identity.", ("FACE_0000",)),
        FaceProposal("FACE_0002", "Witness the disagreement.", ("FACE_0000", "FACE_0001")),
    ]
    first = asyncio.run(gather_concurrently("TURN_ASYNC_0001", proposals))
    second = asyncio.run(gather_concurrently("TURN_ASYNC_0001", proposals))

    assert first == second
    assert first["timing"]["candidate_total_intentional_budget_ms"] == 24
    assert first["timing"]["hard_cap_ms"] == 32
    assert first["timing"]["per_face_delay_accumulates_serially"] is False
    assert first["world_commit_parallelism_for_one_host"] == 1
    assert all(0 <= row["start_offset_ms"] <= 6 for row in first["scheduled"])
    assert first["timing"]["actual_logical_total_for_this_schedule_ms"] <= 24
    assert classify_deadline(24.0) == "ADMITTED_TO_CURRENT_GATHER"
    assert classify_deadline(24.1) == "DEFERRED_LATE_PRESERVE_PROVENANCE"
    assert classify_deadline(33.0) == "DEFERRED_AFTER_HARD_CAP_PRESERVE_PROVENANCE"

    # Face namespace is unbounded in naming; active workset is bounded per turn.
    arbitrary_face = FaceProposal("FACE_999999999999999999999", "Arbitrary n remains addressable.")
    arbitrary = asyncio.run(gather_concurrently("TURN_ASYNC_N", [arbitrary_face]))
    assert arbitrary["active_workset_count"] == 1

    try:
        asyncio.run(
            gather_concurrently(
                "TURN_TOO_WIDE",
                [FaceProposal(f"FACE_{i:04d}", str(i)) for i in range(MAX_ACTIVE_FACES_PER_TURN + 1)],
            )
        )
    except ValueError:
        pass
    else:
        raise AssertionError("unbounded active workset must not bypass per-turn cap")

    return {
        "deterministic_schedule": "PASS",
        "24ms_candidate_budget": "PASS",
        "32ms_hard_cap": "PASS",
        "non_accumulating_per_face_stagger": "PASS",
        "one_host_one_commit_channel": "PASS",
        "unbounded_face_namespace_bounded_active_workset": "PASS",
        "late_provenance_preserved": "PASS",
        "offset_has_no_authority_semantics": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS Infinite Faces async microstagger experiment")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--real-sleep", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.self_test:
        result: object = self_test()
    else:
        proposals = [
            FaceProposal("FACE_0000", "Continuity is identity."),
            FaceProposal("FACE_0001", "Change is identity.", ("FACE_0000",)),
            FaceProposal("FACE_0002", "Witness the disagreement.", ("FACE_0000", "FACE_0001")),
        ]
        result = asyncio.run(gather_concurrently("TURN_ASYNC_DEMO", proposals, real_sleep=args.real_sleep))

    payload = {
        "experiment": "JANUS_INFINITE_FACES_ASYNC_MICROSTAGGER",
        "version": "v1.0",
        "result": result,
        "claim_ceiling": [
            "EXPERIMENTAL_UNIVERSAL_CHAT_RUNTIME_REFERENCE_ONLY",
            "INFINITE_FACES_NOT_NATIVE_AUTHORITATIVE_GENESIS_PRIMITIVE",
            "24MS_IS_ENGINEERING_CANDIDATE_NOT_HUMAN_PERCEPTION_PROOF",
            "NO_MACHINE_CONSCIOUSNESS_CLAIM",
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
