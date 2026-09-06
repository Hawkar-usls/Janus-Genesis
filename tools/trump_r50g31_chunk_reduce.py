#!/usr/bin/env python3
"""Exact reducer for R50G31 proof-carrying chunks."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import trump_r50g27_single_polarity_flip_agent as r50g27

REQUEST_ID = "TRUMP-R50G31-CHUNKED-MINIMUM-NONSWAP-LOAD-TRANSFER-010"
EXPECTED_CHUNKS = 16
EXPECTED_PARENT_STATES = 1424
EXPECTED_PAIR_PATHS = 1774
EXPECTED_RULE_PARTITION = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 589,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 736,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 5,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_counter(dst: Counter, src: dict[str, int]) -> None:
    for k, v in src.items():
        dst[str(k)] += int(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks-dir", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    workspace = Path(args.workspace)
    exp = workspace / "experiments"
    for p in (str(workspace), str(exp)):
        if p not in sys.path:
            sys.path.insert(0, p)
    r50g23 = importlib.import_module(
        "janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt"
    )
    pair_paths, _pp, unique_pairs = r50g27.build_unique_pair_states(r50g23)
    rule_partition = Counter(v["first_label"] for v in unique_pairs.values())
    if pair_paths != EXPECTED_PAIR_PATHS or len(unique_pairs) != EXPECTED_PARENT_STATES:
        raise AssertionError("R50G31_REDUCER_PARENT_SEAL_DRIFT")
    if dict(rule_partition) != EXPECTED_RULE_PARTITION:
        raise AssertionError("R50G31_REDUCER_PARENT_PARTITION_DRIFT")

    files = sorted(Path(args.chunks_dir).rglob("chunk-*.json"))
    if len(files) != EXPECTED_CHUNKS:
        raise AssertionError(("R50G31_REDUCER_CHUNK_FILE_COUNT", len(files), EXPECTED_CHUNKS))
    receipts = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    by_index = {int(r["chunk_index"]): r for r in receipts}
    if set(by_index) != set(range(EXPECTED_CHUNKS)):
        raise AssertionError(("R50G31_REDUCER_CHUNK_INDEX_SET", sorted(by_index)))

    ordered_hashes = [h for h, _ in sorted(unique_pairs.items())]
    coverage: list[str] = []
    chunk_manifest = []
    raw_paths = unique_audits = duplicate_paths = 0
    open_count = closed_count = audited_edges = missing_edges = 0
    pivot_freq: Counter[str] = Counter()
    terminal_part: Counter[str] = Counter()
    round_part: Counter[str] = Counter()
    witness_samples: list[dict[str, Any]] = []
    any_resource_limit = False

    for idx in range(EXPECTED_CHUNKS):
        r = by_index[idx]
        if int(r["chunk_count"]) != EXPECTED_CHUNKS:
            raise AssertionError(("R50G31_REDUCER_CHUNK_COUNT_DRIFT", idx, r["chunk_count"]))
        expected = [h for pos, h in enumerate(ordered_hashes) if pos % EXPECTED_CHUNKS == idx]
        got = list(r["selected_parent_hashes"])
        if got != expected:
            raise AssertionError(("R50G31_REDUCER_PARENT_PARTITION_MISMATCH", idx))
        if len(got) != 89:
            raise AssertionError(("R50G31_REDUCER_PARENT_CHUNK_SIZE", idx, len(got)))
        coverage.extend(got)
        any_resource_limit |= bool(r["resource_limit_reached"])
        raw_paths += int(r["raw_valid_nonswap_path_count"])
        unique_audits += int(r["within_chunk_unique_mutant_count"])
        duplicate_paths += int(r["duplicate_valid_path_count"])
        open_count += int(r["mutant_with_replay_verified_open_r47j_pivot_count"])
        closed_count += int(r["mutant_all_r47j_pivots_closed_count"])
        audited_edges += int(r["audited_pivot_edge_count_until_first_open"])
        missing_edges += int(r["missing_pivot_edge_count_before_first_open"])
        add_counter(pivot_freq, r["first_open_pivot_frequency"])
        add_counter(terminal_part, r["first_open_terminal_partition"])
        add_counter(round_part, r["first_open_round_partition"])
        for sample in r.get("all_r47j_pivots_closed_samples", []):
            if len(witness_samples) < 24:
                witness_samples.append(sample)
        chunk_manifest.append({
            "chunk_index": idx,
            "parent_state_count": len(got),
            "receipt_sha256": digest_file(files[receipts.index(r)]),
            "raw_paths": int(r["raw_valid_nonswap_path_count"]),
            "within_chunk_unique_audits": int(r["within_chunk_unique_mutant_count"]),
            "all_pivots_closed": int(r["mutant_all_r47j_pivots_closed_count"]),
            "resource_limit_reached": bool(r["resource_limit_reached"]),
        })

    if len(coverage) != EXPECTED_PARENT_STATES or len(set(coverage)) != EXPECTED_PARENT_STATES:
        raise AssertionError("R50G31_REDUCER_PARENT_COVERAGE_NOT_EXACT")
    all_chunks_exhaustive = all(bool(r["chunk_exhaustive_within_declared_grammar"]) for r in receipts)
    if open_count + closed_count != unique_audits:
        raise AssertionError("R50G31_REDUCER_AUDIT_ACCOUNTING_DRIFT")

    if any_resource_limit or not all_chunks_exhaustive:
        status = "UNKNOWN_RESOURCE_LIMIT"
        next_gate = "R50G31_RECHUNK_MINIMUM_NONSWAP_LOAD_TRANSFER_REPLAY"
        answer = "At least one R50G31 chunk did not exhaust its partition; no finite-negative claim is permitted. Rechunk the identical grammar."
    elif closed_count:
        status = "ALL_R47J_PIVOTS_CLOSED_WITNESS_CANDIDATE_FOUND"
        next_gate = "R50G32_ALL_R47J_PIVOTS_CLOSED_NONSWAP_REWIRE__DIRECT_R33_RUP_AFFINE_OTHER_FROZEN_OPERATOR_AUDIT"
        answer = f"R50G31 chunked replay exactly covered all 1424 frozen parent states and found {closed_count} within-chunk all-R47J-pivots-closed audits. Next: direct frozen-operator audit; this is not a P-vs-NP conclusion."
    else:
        status = "FINITE_NEGATIVE_WITHIN_DECLARED_MINIMUM_NONSWAP_GRAMMAR"
        next_gate = "R50G32_MINIMUM_NONSWAP_FINITE_NEGATIVE__GENERAL_TWO_OCCURRENCE_NONSWAP_REWIRE"
        answer = f"R50G31 chunked replay exactly covered all 1424 frozen parent states across {EXPECTED_CHUNKS} exhaustive chunks. All {unique_audits} within-chunk unique formula audits retained a replay-verified R47J door. Cross-chunk formula uniqueness is intentionally not claimed."

    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_10",
        "lane_id": "JANUS_TRUMP_R50G31_CHUNKED_MINIMUM_NONSWAP_REPLAY_LANE",
        "request_id": REQUEST_ID,
        "processed_at_utc": utc_now(),
        "source_repo": "Hawkar-usls/Janus-Fundamentum",
        "source_branch": "research/r50g23-direct5-skeleton-r47j-collapse-cascade-anti-collapse-debt-2026-09-05",
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "authority": "RESEARCH_HYPOTHESIS_ONLY",
        "truth_boundary": {
            "model_output_is_proof": False,
            "deterministic_finite_search_is_universal_proof": False,
            "p_vs_np": "OPEN",
            "sat_in_p": "NOT_PROVED",
        },
        "report": {
            "status": status,
            "proof_claim": False,
            "parent_seal": {
                "pair_path_count": pair_paths,
                "unique_pair_state_count": len(unique_pairs),
                "unique_pair_rule_partition": dict(rule_partition),
                "exact_parent_partition_coverage": True,
                "parent_state_coverage_count": len(set(coverage)),
            },
            "chunk_count": EXPECTED_CHUNKS,
            "parent_states_per_chunk": 89,
            "partition_rule": "SORTED_PAIR_HASH_POSITION_MOD_16",
            "all_chunks_exhaustive": all_chunks_exhaustive,
            "resource_limit_reached": any_resource_limit,
            "raw_valid_nonswap_path_count": raw_paths,
            "within_chunk_unique_formula_audit_count": unique_audits,
            "cross_chunk_formula_deduplication_claimed": False,
            "duplicate_valid_path_count_within_chunks": duplicate_paths,
            "audited_pivot_edge_count_until_first_open": audited_edges,
            "missing_pivot_edge_count_before_first_open": missing_edges,
            "mutant_with_replay_verified_open_r47j_pivot_count": open_count,
            "mutant_all_r47j_pivots_closed_count": closed_count,
            "first_open_pivot_frequency": dict(pivot_freq),
            "first_open_terminal_partition": dict(terminal_part),
            "first_open_round_partition": dict(round_part),
            "all_r47j_pivots_closed_samples": witness_samples,
            "chunk_manifest": chunk_manifest,
            "recommended_next_gate": next_gate,
            "answer": answer,
            "scope_firewall": {
                "family_expanded": False,
                "clauses_added": False,
                "clauses_deleted": False,
                "new_variables_added": False,
                "variable_universe_preserved": True,
                "literal_signs_preserved": True,
                "clause_width_preserved": True,
                "clause_count_preserved": True,
                "r47j_definition_changed": False,
                "histogram_l1_drift": 2,
                "finite_search_is_universal_proof": False,
            },
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"R50G31_AGGREGATE_RECEIPT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
