#!/usr/bin/env python3
"""Proof-carrying chunk worker for R50G32 general two-occurrence nonswap roles."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import trump_r50g25_adaptive_third_debt_agent as r50g25
import trump_r50g27_single_polarity_flip_agent as r50g27
import trump_r50g32_general_two_occurrence_nonswap as r50g32

EXPECTED_PAIR_PATHS = 1774
EXPECTED_UNIQUE_PAIR_STATES = 1424
EXPECTED_UNIQUE_RULE_PARTITION = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 589,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 736,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 5,
}
MAX_UNIQUE_PER_CHUNK = 600_000
MAX_SAMPLES = 8


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha_lines(values: list[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode()).hexdigest()


def dump(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(workspace: Path, chunk_index: int, chunk_count: int) -> dict[str, Any]:
    if chunk_count <= 0 or not (0 <= chunk_index < chunk_count):
        raise ValueError("R50G32_BAD_CHUNK_COORDINATES")
    exp = workspace / "experiments"
    for p in (str(workspace), str(exp)):
        if p not in sys.path:
            sys.path.insert(0, p)
    r50g23 = importlib.import_module(
        "janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt"
    )
    r47j, r33 = r50g23.r47j, r50g23.r33
    pair_paths, _parent_partition, unique_pairs = r50g27.build_unique_pair_states(r50g23)
    unique_partition = Counter(v["first_label"] for v in unique_pairs.values())
    if pair_paths != EXPECTED_PAIR_PATHS or len(unique_pairs) != EXPECTED_UNIQUE_PAIR_STATES:
        raise AssertionError(("R50G32_CHUNK_PARENT_COUNT_DRIFT", pair_paths, len(unique_pairs)))
    if dict(unique_partition) != EXPECTED_UNIQUE_RULE_PARTITION:
        raise AssertionError(("R50G32_CHUNK_PARENT_PARTITION_DRIFT", dict(unique_partition)))

    ordered = sorted(unique_pairs.items())
    selected = [(h, row) for pos, (h, row) in enumerate(ordered) if pos % chunk_count == chunk_index]
    selected_hashes = [h for h, _ in selected]

    raw_paths = 0
    duplicate_paths = 0
    raw_pattern_partition: Counter[str] = Counter()
    unique_pattern_partition: Counter[str] = Counter()
    seen: set[str] = set()
    any_open = 0
    all_closed = 0
    audited_edges = 0
    missing_edges = 0
    pivot_freq: Counter[int] = Counter()
    terminal_part: Counter[str] = Counter()
    round_part: Counter[int] = Counter()
    closed_samples: list[dict[str, Any]] = []
    resource_limited = False

    for pair_hash, row in selected:
        if resource_limited:
            break
        for edit in r50g32.remaining_two_occurrence_mutants(r50g23, row["formula"]):
            raw_paths += 1
            pattern = str(edit["pattern"])
            raw_pattern_partition[pattern] += 1
            formula = edit["mutated"]
            mh = r50g23.r50g4.fhash(formula)
            if mh in seen:
                duplicate_paths += 1
                continue
            if len(seen) >= MAX_UNIQUE_PER_CHUNK:
                resource_limited = True
                break
            seen.add(mh)
            unique_pattern_partition[pattern] += 1

            found = None
            vars_ = r50g25.formula_variables(formula)
            for pivot in vars_:
                audited_edges += 1
                candidate = r47j.macro_candidate_fixpoint(formula, int(pivot))
                if candidate is None:
                    missing_edges += 1
                    continue
                replay = r47j.independent_fixpoint_macro_replay(formula, candidate)
                if not replay.get("pass"):
                    raise AssertionError(("R50G32_CHUNK_R47J_REPLAY_FAIL", chunk_index, mh, pivot))
                norm = candidate["normalization"]
                final_formula = r50g23.canon(norm.get("final_formula", []))
                found = {
                    "pivot": int(pivot),
                    "terminal": norm.get("terminal"),
                    "round_count": int(norm.get("round_count", 0)),
                    "restart_count": int(norm.get("restart_count", 0)),
                    "final_CLV": list(r33.measure(final_formula)),
                }
                break

            if found is None:
                all_closed += 1
                if len(closed_samples) < MAX_SAMPLES:
                    closed_samples.append({
                        "mutant_hash": mh,
                        "pair_hash": pair_hash,
                        "pattern": pattern,
                        "two_occurrence_rewire": [edit["first"], edit["second"]],
                        "histogram_delta": edit["histogram_delta"],
                        "variables": vars_,
                        "formula_CLV": list(r33.measure(formula)),
                        "formula": r50g25.json_formula(formula),
                        "classification": "ALL_R47J_PIVOTS_CLOSED_R50G32_WITNESS",
                    })
            else:
                any_open += 1
                pivot_freq[found["pivot"]] += 1
                terminal_part["UNRESOLVED" if found["terminal"] is None else str(found["terminal"])] += 1
                round_part[found["round_count"]] += 1

    if any_open + all_closed != len(seen):
        raise AssertionError("R50G32_CHUNK_ACCOUNTING_DRIFT")
    return {
        "schema": "janus.genesis.trump_r50g32_chunk_receipt.v1",
        "processed_at_utc": utc_now(),
        "authority": "RESEARCH_HYPOTHESIS_ONLY",
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "partition_rule": "SORTED_PAIR_HASH_POSITION_MOD_CHUNK_COUNT",
        "parent_seal": {
            "pair_path_count": pair_paths,
            "unique_pair_state_count": len(unique_pairs),
            "unique_pair_rule_partition": dict(unique_partition),
        },
        "selected_parent_state_count": len(selected_hashes),
        "selected_parent_hashes": selected_hashes,
        "selected_parent_hash_digest": sha_lines(selected_hashes),
        "declared_remaining_role_patterns": list(r50g32.PATTERNS),
        "histogram_l1_drift": 4,
        "raw_valid_general_nonswap_path_count": raw_paths,
        "raw_role_pattern_partition": dict(raw_pattern_partition),
        "within_chunk_unique_mutant_count": len(seen),
        "within_chunk_first_seen_role_pattern_partition": dict(unique_pattern_partition),
        "duplicate_valid_path_count": duplicate_paths,
        "resource_ceiling_unique_mutants": MAX_UNIQUE_PER_CHUNK,
        "resource_limit_reached": resource_limited,
        "audited_pivot_edge_count_until_first_open": audited_edges,
        "missing_pivot_edge_count_before_first_open": missing_edges,
        "mutant_with_replay_verified_open_r47j_pivot_count": any_open,
        "mutant_all_r47j_pivots_closed_count": all_closed,
        "first_open_pivot_frequency": {str(k): v for k, v in sorted(pivot_freq.items())},
        "first_open_terminal_partition": dict(terminal_part),
        "first_open_round_partition": {str(k): v for k, v in sorted(round_part.items())},
        "all_r47j_pivots_closed_samples": closed_samples,
        "chunk_exhaustive_within_declared_remaining_two_occurrence_grammar": not resource_limited,
        "truth_boundary": {
            "finite_chunk_is_universal_proof": False,
            "p_vs_np": "OPEN",
            "sat_in_p": "NOT_PROVED",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--chunk-index", required=True, type=int)
    ap.add_argument("--chunk-count", required=True, type=int)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    dump(Path(args.output), run(Path(args.workspace), args.chunk_index, args.chunk_count))
    print(f"R50G32_CHUNK_RECEIPT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
