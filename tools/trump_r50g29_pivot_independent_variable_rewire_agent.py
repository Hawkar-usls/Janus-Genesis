#!/usr/bin/env python3
"""R50G29: pivot-independent single-literal variable-rewire lane.

After R50G28 proved that all 727 pivot-1 closures regain all six alternate
R47J doors, this gate returns to the exact 1424 unique R50G24 pair states and
exhausts the sibling edit-distance-1 non-additive mutation:

    sign*x  ->  sign*y

for one existing literal occurrence, with x != y and y already in the formula.
The sign, clause count, clause width, and complete variable universe are
preserved. Tautologies and canonical duplicate-clause collapse are rejected.

Every unique rewired formula is audited pivot-independently: all existing
variables are checked for an R47J macro candidate, stopping only after a
replay-verified open pivot is found. A formula with no R47J candidate for any
existing pivot is an all-pivot-door-closed witness candidate for the next
operator audit, not a P-vs-NP conclusion.
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

LANE_ID = "JANUS_TRUMP_R50G29_PIVOT_INDEPENDENT_VARIABLE_REWIRE_LANE"
ENGINE = "DETERMINISTIC_R50G29_PIVOT_INDEPENDENT_SINGLE_LITERAL_VARIABLE_REWIRE"
EXPECTED_PAIR_PATHS = 1774
EXPECTED_UNIQUE_PAIR_STATES = 1424
EXPECTED_UNIQUE_RULE_PARTITION = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 589,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 736,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 5,
}
MAX_SAMPLES = 24
MAX_UNIQUE_MUTANTS = 400000


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


def occurrence_counts(formula) -> Counter[int]:
    c: Counter[int] = Counter()
    for clause in formula:
        for lit in clause:
            c[abs(int(lit))] += 1
    return c


def rewire_candidates(r50g23, formula):
    base = list(r50g23.canon(formula))
    base_count = len(base)
    base_vars = {abs(int(lit)) for clause in base for lit in clause}
    counts = occurrence_counts(base)
    for ci, clause in enumerate(base):
        for li, lit0 in enumerate(clause):
            lit0 = int(lit0)
            old_var = abs(lit0)
            sign = 1 if lit0 > 0 else -1
            # Preserve the complete variable universe: old_var must remain elsewhere.
            if counts[old_var] <= 1:
                continue
            for new_var in sorted(base_vars):
                if new_var == old_var:
                    continue
                new_lit = sign * int(new_var)
                new_clause = list(clause)
                new_clause[li] = new_lit
                if len(set(new_clause)) != len(new_clause):
                    continue
                s = set(int(x) for x in new_clause)
                if any(-x in s for x in s):
                    continue
                raw = list(base)
                raw[ci] = tuple(sorted(int(x) for x in new_clause))
                mutated = r50g23.canon(raw)
                if len(mutated) != base_count:
                    continue
                mutated_vars = {abs(int(x)) for c in mutated for x in c}
                if mutated_vars != base_vars:
                    continue
                if mutated == tuple(base):
                    continue
                yield ci, lit0, new_lit, mutated


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

    pair_paths, parent_partition, unique_pairs = r50g27.build_unique_pair_states(r50g23)
    if pair_paths != EXPECTED_PAIR_PATHS or len(unique_pairs) != EXPECTED_UNIQUE_PAIR_STATES:
        raise AssertionError(("R50G29_PARENT_COUNT_DRIFT", pair_paths, len(unique_pairs)))
    unique_partition = Counter(v["first_label"] for v in unique_pairs.values())
    if dict(unique_partition) != EXPECTED_UNIQUE_RULE_PARTITION:
        raise AssertionError(("R50G29_PARENT_PARTITION_DRIFT", dict(unique_partition), EXPECTED_UNIQUE_RULE_PARTITION))

    raw_rewire_paths = 0
    unique_mutants: dict[str, dict[str, Any]] = {}
    for pair_hash, row in sorted(unique_pairs.items()):
        for ci, old_lit, new_lit, mutated in rewire_candidates(r50g23, row["formula"]):
            raw_rewire_paths += 1
            mh = r50g23.r50g4.fhash(mutated)
            rep = {
                "pair_hash": pair_hash,
                "pair_multiplicity": int(row["multiplicity"]),
                "pair_first_transition": row["first_label"],
                "representative_parent_path": row["representative"],
                "clause_index": int(ci),
                "old_literal": int(old_lit),
                "new_literal": int(new_lit),
                "old_variable": abs(int(old_lit)),
                "new_variable": abs(int(new_lit)),
            }
            if mh not in unique_mutants:
                if len(unique_mutants) >= MAX_UNIQUE_MUTANTS:
                    raise AssertionError(("R50G29_RESOURCE_CEILING_UNIQUE_MUTANTS", len(unique_mutants), MAX_UNIQUE_MUTANTS))
                unique_mutants[mh] = {"formula": mutated, "path_multiplicity": 1, "representative": rep}
            else:
                unique_mutants[mh]["path_multiplicity"] += 1

    all_pivot_closed = 0
    any_open = 0
    first_open_pivot_frequency: Counter[int] = Counter()
    first_open_terminal_partition: Counter[str] = Counter()
    first_open_round_partition: Counter[int] = Counter()
    closed_samples: list[dict[str, Any]] = []
    open_samples: list[dict[str, Any]] = []
    audited_pivot_edges = 0
    missing_pivot_edges_before_first_open = 0

    for mh, row in sorted(unique_mutants.items()):
        formula = row["formula"]
        variables = r50g25.formula_variables(formula)
        found = None
        for pivot in variables:
            audited_pivot_edges += 1
            candidate = r47j.macro_candidate_fixpoint(formula, int(pivot))
            if candidate is None:
                missing_pivot_edges_before_first_open += 1
                continue
            replay = r47j.independent_fixpoint_macro_replay(formula, candidate)
            if not replay.get("pass"):
                raise AssertionError(("R50G29_R47J_REPLAY_FAIL", mh, pivot, replay))
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
            all_pivot_closed += 1
            if len(closed_samples) < MAX_SAMPLES:
                closed_samples.append({
                    "mutant_hash": mh,
                    "path_multiplicity": int(row["path_multiplicity"]),
                    "representative": row["representative"],
                    "variables": variables,
                    "formula_CLV": list(r33.measure(formula)),
                    "formula": r50g25.json_formula(formula),
                    "classification": "ALL_R47J_PIVOT_DOORS_CLOSED_SINGLE_VARIABLE_REWIRE",
                })
        else:
            any_open += 1
            first_open_pivot_frequency[int(found["pivot"])] += 1
            terminal_key = "UNRESOLVED" if found["terminal"] is None else str(found["terminal"])
            first_open_terminal_partition[terminal_key] += 1
            first_open_round_partition[int(found["round_count"])] += 1
            if len(open_samples) < MAX_SAMPLES:
                open_samples.append({
                    "mutant_hash": mh,
                    "path_multiplicity": int(row["path_multiplicity"]),
                    "representative": row["representative"],
                    "first_replay_verified_open_pivot": found,
                })

    if any_open + all_pivot_closed != len(unique_mutants):
        raise AssertionError("R50G29_ACCOUNTING_DRIFT")

    if all_pivot_closed:
        next_gate = "R50G30_ALL_R47J_PIVOTS_CLOSED_REWIRE_DIRECT_R33_RUP_AFFINE_OPERATOR_AUDIT"
        answer = (
            f"R50G29 exhaustively generated {raw_rewire_paths} valid variable-rewire paths, compressed to {len(unique_mutants)} unique formulas. "
            f"{all_pivot_closed} formulas close every existing-variable R47J pivot door; {any_open} retain a replay-verified R47J door. "
            "Next: audit the all-pivot-closed class against direct R33/RUP/affine/other frozen operators before any stronger claim."
        )
    else:
        next_gate = "R50G30_SINGLE_VARIABLE_REWIRE_FINITE_NEGATIVE__MINIMUM_TWO_OCCURRENCE_COUPLED_REWIRE"
        answer = (
            f"R50G29 exhaustively generated {raw_rewire_paths} valid variable-rewire paths, compressed to {len(unique_mutants)} unique formulas. "
            "Every mutant retains at least one replay-verified R47J pivot door. Single occurrence variable rewiring is therefore a finite negative as an all-pivot obstruction; next justified edit is a coupled two-occurrence rewire."
        )

    return normalize({
        "engine": ENGINE,
        "parent_seal": {
            "pair_path_count": pair_paths,
            "unique_pair_state_count": len(unique_pairs),
            "unique_pair_rule_partition": dict(unique_partition),
            "seal_replay_pass": True,
        },
        "raw_valid_rewire_path_count": raw_rewire_paths,
        "unique_rewire_mutant_formula_count": len(unique_mutants),
        "compression_ratio_rewire_paths_per_unique_mutant": float(raw_rewire_paths) / len(unique_mutants) if unique_mutants else None,
        "audited_pivot_edge_count_until_first_open": audited_pivot_edges,
        "missing_pivot_edge_count_before_first_open": missing_pivot_edges_before_first_open,
        "mutant_with_replay_verified_open_r47j_pivot_count": any_open,
        "mutant_all_r47j_pivots_closed_count": all_pivot_closed,
        "first_open_pivot_frequency": {str(k): v for k, v in sorted(first_open_pivot_frequency.items())},
        "first_open_terminal_partition": dict(first_open_terminal_partition),
        "first_open_round_partition": {str(k): v for k, v in sorted(first_open_round_partition.items())},
        "all_r47j_pivots_closed_samples": closed_samples,
        "open_pivot_samples": open_samples,
        "search_exhaustive_within_declared_single_variable_rewire_grammar": True,
        "recommended_next_gate": next_gate,
        "answer": answer,
        "scope_firewall": {
            "family_expanded": False,
            "clauses_added": False,
            "clauses_deleted": False,
            "new_variables_added": False,
            "variable_universe_preserved": True,
            "literal_sign_preserved": True,
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
        raise ValueError("R50G29_BAD_REQUEST")
    gate = str((request.get("frontier") or {}).get("gate") or rid)
    if "R50G29_PIVOT_INDEPENDENT_SINGLE_LITERAL_VARIABLE_REWIRE" not in gate:
        raise ValueError(f"R50G29_WRONG_GATE:{gate}")
    report = run(request, Path(args.workspace))
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_7",
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
    write_json(out, receipt); write_json(mem, receipt)
    print(f"TRUMP_R50G29_RECEIPT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
