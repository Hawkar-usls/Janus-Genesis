#!/usr/bin/env python3
"""R50G31: minimum two-occurrence non-swap variable rewire.

Parent scope is exactly the frozen 1424 unique R50G24 pair states. R50G30
exhausted reciprocal swaps x->y, y->x while preserving the full occurrence
histogram. R50G31 permits the minimum non-zero histogram drift reachable by two
sign-preserving rewires:

    sign_a*x -> sign_a*y
    sign_b*z -> sign_b*x

with x, y, z pairwise distinct and y already present in the formula. Thus x is
a relay (net 0 occurrences), y gains one occurrence, and z loses one. Clause
count, clause widths, literal signs, and the complete variable universe remain
frozen. The histogram L1 drift is exactly 2. No new variables or clauses are
introduced.

Every unique mutant is audited pivot-independently until a replay-verified R47J
macro candidate is found. A mutant with no candidate at any existing pivot is
only an all-R47J-pivots-closed witness candidate for the direct frozen-operator
audit; finite exhaustion is never a P-vs-NP theorem.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import trump_r50g25_adaptive_third_debt_agent as r50g25
import trump_r50g27_single_polarity_flip_agent as r50g27
import trump_r50g30_two_occurrence_coupled_rewire_agent as r50g30

LANE_ID = "JANUS_TRUMP_R50G31_TWO_OCCURRENCE_NONSWAP_REWIRE_LANE"
ENGINE = "DETERMINISTIC_R50G31_PIVOT_INDEPENDENT_MINIMUM_NONSWAP_LOAD_TRANSFER_REWIRE"
EXPECTED_PAIR_PATHS = 1774
EXPECTED_UNIQUE_PAIR_STATES = 1424
EXPECTED_UNIQUE_RULE_PARTITION = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 589,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 736,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 5,
}
MAX_SAMPLES = 24
MAX_UNIQUE_MUTANTS = 2_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(report: dict[str, Any]) -> dict[str, Any]:
    out = dict(report)
    out.update({
        "lane": "TRUMP_FALSIFICATION_RESEARCH",
        "status": "HYPOTHESIS",
        "proof_claim": False,
        "p_vs_np": "OPEN",
        "sat_in_p": "NOT_PROVED",
    })
    return out


def histogram_l1(a: Counter[int], b: Counter[int]) -> int:
    return sum(abs(int(a[k]) - int(b[k])) for k in set(a) | set(b))


def nonswap_load_transfers(r50g23, formula):
    base = list(r50g23.canon(formula))
    base_tuple = tuple(base)
    base_count = len(base)
    base_vars = {abs(int(lit)) for clause in base for lit in clause}
    base_hist = r50g30.occurrence_histogram(base)
    occ = r50g30.occurrences(base)
    vars_sorted = sorted(base_vars)

    # Ordered roles matter: first occurrence supplies relay x->y; second supplies z->x.
    for i, (ci1, li1, lit1) in enumerate(occ):
        x = abs(int(lit1)); sign1 = 1 if int(lit1) > 0 else -1
        for j, (ci2, li2, lit2) in enumerate(occ):
            if i == j:
                continue
            z = abs(int(lit2)); sign2 = 1 if int(lit2) > 0 else -1
            if z == x or base_hist[z] <= 1:
                continue
            for y in vars_sorted:
                if y == x or y == z:
                    continue
                raw = [list(c) for c in base]
                raw[ci1][li1] = sign1 * int(y)
                raw[ci2][li2] = sign2 * int(x)
                touched = {ci1, ci2}
                if any(not r50g30.valid_clause(raw[ci]) for ci in touched):
                    continue
                mutated = r50g23.canon(tuple(tuple(sorted(int(v) for v in c)) for c in raw))
                if len(mutated) != base_count or mutated == base_tuple:
                    continue
                if {abs(int(v)) for c in mutated for v in c} != base_vars:
                    continue
                mhist = r50g30.occurrence_histogram(mutated)
                expected = Counter(base_hist)
                expected[y] += 1
                expected[z] -= 1
                if mhist != expected or histogram_l1(base_hist, mhist) != 2:
                    continue
                yield {
                    "first": {
                        "clause_index": ci1,
                        "literal_index": li1,
                        "old_literal": int(lit1),
                        "new_literal": sign1 * int(y),
                        "old_variable": x,
                        "new_variable": int(y),
                    },
                    "second": {
                        "clause_index": ci2,
                        "literal_index": li2,
                        "old_literal": int(lit2),
                        "new_literal": sign2 * int(x),
                        "old_variable": z,
                        "new_variable": x,
                    },
                    "histogram_delta": {str(int(y)): 1, str(int(z)): -1},
                    "mutated": mutated,
                }


def run(request: dict[str, Any], workspace: Path) -> dict[str, Any]:
    exp = workspace / "experiments"
    for p in (str(workspace), str(exp)):
        if p not in sys.path:
            sys.path.insert(0, p)
    r50g23 = importlib.import_module(
        "janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt"
    )
    r47j = r50g23.r47j
    r33 = r50g23.r33

    pair_paths, _parent_partition, unique_pairs = r50g27.build_unique_pair_states(r50g23)
    if pair_paths != EXPECTED_PAIR_PATHS or len(unique_pairs) != EXPECTED_UNIQUE_PAIR_STATES:
        raise AssertionError(("R50G31_PARENT_COUNT_DRIFT", pair_paths, len(unique_pairs)))
    unique_partition = Counter(v["first_label"] for v in unique_pairs.values())
    if dict(unique_partition) != EXPECTED_UNIQUE_RULE_PARTITION:
        raise AssertionError(("R50G31_PARENT_PARTITION_DRIFT", dict(unique_partition), EXPECTED_UNIQUE_RULE_PARTITION))

    raw_paths = 0
    seen_hashes: set[str] = set()
    duplicate_paths = 0
    any_open = 0
    all_closed = 0
    audited_edges = 0
    missing_edges = 0
    first_open_pivot: Counter[int] = Counter()
    first_open_terminal: Counter[str] = Counter()
    first_open_round: Counter[int] = Counter()
    closed_samples: list[dict[str, Any]] = []
    open_samples: list[dict[str, Any]] = []
    resource_limited = False

    for pair_hash, row in sorted(unique_pairs.items()):
        if resource_limited:
            break
        for edit in nonswap_load_transfers(r50g23, row["formula"]):
            raw_paths += 1
            formula = edit["mutated"]
            mh = r50g23.r50g4.fhash(formula)
            if mh in seen_hashes:
                duplicate_paths += 1
                continue
            if len(seen_hashes) >= MAX_UNIQUE_MUTANTS:
                resource_limited = True
                break
            seen_hashes.add(mh)

            rep = {
                "pair_hash": pair_hash,
                "pair_multiplicity": int(row["multiplicity"]),
                "pair_first_transition": row["first_label"],
                "representative_parent_path": row["representative"],
                "nonswap_load_transfer": [edit["first"], edit["second"]],
                "histogram_delta": edit["histogram_delta"],
            }
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
                    raise AssertionError(("R50G31_R47J_REPLAY_FAIL", mh, pivot, replay))
                norm = candidate["normalization"]
                final_formula = r50g23.canon(norm.get("final_formula", []))
                found = {
                    "pivot": int(pivot),
                    "terminal": norm.get("terminal"),
                    "round_count": int(norm.get("round_count", 0)),
                    "restart_count": int(norm.get("restart_count", 0)),
                    "final_CLV": list(r33.measure(final_formula)),
                    "final_formula": r50g25.json_formula(final_formula),
                }
                break

            if found is None:
                all_closed += 1
                if len(closed_samples) < MAX_SAMPLES:
                    closed_samples.append({
                        "mutant_hash": mh,
                        "representative": rep,
                        "variables": vars_,
                        "formula_CLV": list(r33.measure(formula)),
                        "formula": r50g25.json_formula(formula),
                        "classification": "ALL_R47J_PIVOTS_CLOSED_MINIMUM_NONSWAP_LOAD_TRANSFER",
                    })
            else:
                any_open += 1
                first_open_pivot[int(found["pivot"])] += 1
                first_open_terminal["UNRESOLVED" if found["terminal"] is None else str(found["terminal"])] += 1
                first_open_round[int(found["round_count"])] += 1
                if len(open_samples) < MAX_SAMPLES:
                    open_samples.append({
                        "mutant_hash": mh,
                        "representative": rep,
                        "first_replay_verified_open_pivot": found,
                    })

    unique_count = len(seen_hashes)
    if any_open + all_closed != unique_count:
        raise AssertionError(("R50G31_ACCOUNTING_DRIFT", any_open, all_closed, unique_count))

    if resource_limited:
        next_gate = "R50G31_RESOURCE_LIMIT__CHUNKED_MINIMUM_NONSWAP_LOAD_TRANSFER_REPLAY"
        answer = (
            f"R50G31 reached the declared unique-mutant ceiling at {unique_count} formulas after {raw_paths} valid paths. "
            "This is UNKNOWN_RESOURCE_LIMIT, not a finite negative. Next: chunk/replay the same frozen grammar without changing the edit contract."
        )
    elif all_closed:
        next_gate = "R50G32_ALL_R47J_PIVOTS_CLOSED_NONSWAP_REWIRE__DIRECT_R33_RUP_AFFINE_OTHER_FROZEN_OPERATOR_AUDIT"
        answer = (
            f"R50G31 exhaustively generated {raw_paths} valid minimum-drift non-swap paths, compressed to {unique_count} unique formulas. "
            f"{all_closed} close every existing-variable R47J pivot door. Next: direct R33/RUP/affine/other frozen-operator audit before any stronger claim."
        )
    else:
        next_gate = "R50G32_MINIMUM_NONSWAP_FINITE_NEGATIVE__GENERAL_TWO_OCCURRENCE_NONSWAP_REWIRE"
        answer = (
            f"R50G31 exhaustively generated {raw_paths} valid minimum-drift non-swap paths, compressed to {unique_count} unique formulas. "
            "Every mutant retains at least one replay-verified R47J pivot door. Next: general two-occurrence non-swap rewire beyond L1 histogram drift 2."
        )

    return normalize({
        "engine": ENGINE,
        "parent_seal": {
            "pair_path_count": pair_paths,
            "unique_pair_state_count": len(unique_pairs),
            "unique_pair_rule_partition": dict(unique_partition),
            "seal_replay_pass": True,
        },
        "declared_grammar": "TWO_OCCURRENCE_SIGN_PRESERVING_DIRECTED_LOAD_TRANSFER_X_TO_Y__Z_TO_X__PAIRWISE_DISTINCT_XYZ__HISTOGRAM_L1_2",
        "raw_valid_nonswap_path_count": raw_paths,
        "unique_nonswap_mutant_formula_count": unique_count,
        "duplicate_valid_path_count": duplicate_paths,
        "resource_ceiling_unique_mutants": MAX_UNIQUE_MUTANTS,
        "resource_limit_reached": resource_limited,
        "audited_pivot_edge_count_until_first_open": audited_edges,
        "missing_pivot_edge_count_before_first_open": missing_edges,
        "mutant_with_replay_verified_open_r47j_pivot_count": any_open,
        "mutant_all_r47j_pivots_closed_count": all_closed,
        "first_open_pivot_frequency": {str(k): v for k, v in sorted(first_open_pivot.items())},
        "first_open_terminal_partition": dict(first_open_terminal),
        "first_open_round_partition": {str(k): v for k, v in sorted(first_open_round.items())},
        "all_r47j_pivots_closed_samples": closed_samples,
        "open_pivot_samples": open_samples,
        "search_exhaustive_within_declared_minimum_nonswap_grammar": not resource_limited,
        "recommended_next_gate": next_gate,
        "answer": answer,
        "scope_firewall": {
            "family_expanded": False,
            "clauses_added": False,
            "clauses_deleted": False,
            "new_variables_added": False,
            "variable_universe_preserved": True,
            "variable_occurrence_histogram_preserved": False,
            "minimum_histogram_l1_drift": 2,
            "literal_signs_preserved": True,
            "clause_width_preserved": True,
            "clause_count_preserved": True,
            "r47j_definition_changed": False,
            "finite_search_is_universal_proof": False,
        },
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--habitat-root", required=True)
    args = ap.parse_args()
    request_path = Path(args.request)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    rid = re.sub(r"[^A-Za-z0-9._-]+", "_", str(request.get("request_id") or request_path.stem))[:120]
    if request.get("status") != "QUEUED" or request.get("purpose") != "PARALLEL_TRUMP_CODE_RESEARCH":
        raise ValueError("R50G31_BAD_REQUEST")
    gate = str((request.get("frontier") or {}).get("gate") or rid)
    if "R50G31_MINIMUM_TWO_OCCURRENCE_NONSWAP_REWIRE" not in gate:
        raise ValueError(f"R50G31_WRONG_GATE:{gate}")
    report = run(request, Path(args.workspace))
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_9",
        "lane_id": LANE_ID,
        "request_id": rid,
        "processed_at_utc": utc_now(),
        "source_repo": request.get("source_repo"),
        "source_branch": request.get("source_branch"),
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "engine": ENGINE,
        "authority": "RESEARCH_HYPOTHESIS_ONLY",
        "truth_boundary": {
            "model_output_is_proof": False,
            "model_output_is_independent_confirmation": False,
            "deterministic_finite_search_is_universal_proof": False,
            "p_vs_np": "OPEN",
            "sat_in_p": "NOT_PROVED",
        },
        "report": report,
    }
    habitat = Path(args.habitat_root)
    out = habitat / "outbox" / "trump" / f"{rid}.json"
    mem = habitat / "memory" / "trump" / f"{utc_now().replace(':','-')}_{rid}.json"
    write_json(out, receipt)
    write_json(mem, receipt)
    print(f"TRUMP_R50G31_RECEIPT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
