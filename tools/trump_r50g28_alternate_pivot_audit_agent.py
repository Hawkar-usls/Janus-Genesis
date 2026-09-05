#!/usr/bin/env python3
"""R50G28: exhaustive alternate-pivot audit for R50G27 door-closed mutants.

Reconstructs the exact R50G27 single-polarity-flip space, seals the exhaustive
pivot-1 door-closed count at 727, then tests every existing variable as an R47J
pivot for each of those 727 unique mutant formulas.

A missing pivot-1 macro candidate is only a local door closure. This lane asks
whether another R47J pivot remains available, or whether a mutant closes every
R47J pivot door and therefore deserves a separate non-R47J operator audit.

Firewalls: frozen 30 sources; exact 1774/1424 parent; exact 61112/59486 R50G27
space; no mutation beyond the already-sealed single sign flip; no new variables;
no TRUMP writes; finite search != theorem; P_VS_NP remains OPEN.
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

LANE_ID = "JANUS_TRUMP_R50G28_ALTERNATE_PIVOT_AUDIT_LANE"
ENGINE = "DETERMINISTIC_R50G28_SINGLE_FLIP_DOOR_CLOSED_ALTERNATE_PIVOT_AUDIT"
EXPECTED_RAW_FLIP_PATHS = 61112
EXPECTED_UNIQUE_MUTANTS = 59486
EXPECTED_PIVOT1_SUCCESS_FIRST = {
    "R33:BLOCKED_CLAUSE_ELIMINATION": 39601,
    "R33:PURE_LITERAL_AUTARKY": 8972,
    "R33:BOUNDED_VARIABLE_ELIMINATION": 9985,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 201,
}
EXPECTED_PIVOT1_TERMINALS = {"EMPTY_CNF_SAT": 58758, "EMPTY_CLAUSE_UNSAT": 1}
EXPECTED_PIVOT1_DOOR_CLOSED = 727
MAX_SAMPLES = 24


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


def build_unique_mutants(r50g23):
    pair_paths, parent_partition, unique_pairs = r50g27.build_unique_pair_states(r50g23)
    raw_flip_paths = 0
    unique_mutants: dict[str, dict[str, Any]] = {}
    for pair_hash, row in sorted(unique_pairs.items()):
        for ci, old_lit, new_lit, mutated in r50g27.flip_candidates(r50g23, row["formula"]):
            raw_flip_paths += 1
            mh = r50g23.r50g4.fhash(mutated)
            rep = {
                "pair_hash": pair_hash,
                "pair_multiplicity": int(row["multiplicity"]),
                "pair_first_transition": row["first_label"],
                "representative_parent_path": row["representative"],
                "clause_index": int(ci),
                "old_literal": int(old_lit),
                "new_literal": int(new_lit),
            }
            if mh not in unique_mutants:
                unique_mutants[mh] = {
                    "formula": mutated,
                    "path_multiplicity": 1,
                    "representative": rep,
                }
            else:
                unique_mutants[mh]["path_multiplicity"] += 1
    if raw_flip_paths != EXPECTED_RAW_FLIP_PATHS:
        raise AssertionError(("R50G28_RAW_FLIP_COUNT_DRIFT", raw_flip_paths, EXPECTED_RAW_FLIP_PATHS))
    if len(unique_mutants) != EXPECTED_UNIQUE_MUTANTS:
        raise AssertionError(("R50G28_UNIQUE_MUTANT_COUNT_DRIFT", len(unique_mutants), EXPECTED_UNIQUE_MUTANTS))
    return pair_paths, parent_partition, unique_pairs, raw_flip_paths, unique_mutants


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

    pair_paths, parent_partition, unique_pairs, raw_flip_paths, unique_mutants = build_unique_mutants(r50g23)

    pivot1_success_first: Counter[str] = Counter()
    pivot1_terminals: Counter[str] = Counter()
    pivot1_closed: dict[str, dict[str, Any]] = {}
    for mh, row in sorted(unique_mutants.items()):
        st = r50g25.replay_state(r50g23, row["formula"], [])
        if not st["ok"]:
            if st["reason"] != "R47J_CANDIDATE_MISSING":
                raise AssertionError(("R50G28_PIVOT1_REPLAY_FAILURE", mh, st))
            pivot1_closed[mh] = row
            continue
        pivot1_success_first[st["first_label"]] += 1
        pivot1_terminals[str(st["reduced"].get("terminal"))] += 1

    if dict(pivot1_success_first) != EXPECTED_PIVOT1_SUCCESS_FIRST:
        raise AssertionError(("R50G28_PIVOT1_FIRST_PARTITION_DRIFT", dict(pivot1_success_first), EXPECTED_PIVOT1_SUCCESS_FIRST))
    if dict(pivot1_terminals) != EXPECTED_PIVOT1_TERMINALS:
        raise AssertionError(("R50G28_PIVOT1_TERMINAL_PARTITION_DRIFT", dict(pivot1_terminals), EXPECTED_PIVOT1_TERMINALS))
    if len(pivot1_closed) != EXPECTED_PIVOT1_DOOR_CLOSED:
        raise AssertionError(("R50G28_PIVOT1_DOOR_CLOSED_DRIFT", len(pivot1_closed), EXPECTED_PIVOT1_DOOR_CLOSED))

    mutant_with_any_alternate = 0
    mutant_all_r47j_pivots_closed = 0
    alternate_candidate_edge_count = 0
    alternate_missing_edge_count = 0
    alternate_terminal_partition: Counter[str] = Counter()
    alternate_unresolved_edge_count = 0
    alternate_direct_sat_edge_count = 0
    alternate_direct_unsat_edge_count = 0
    pivot_open_frequency: Counter[int] = Counter()
    pivot_missing_frequency: Counter[int] = Counter()
    open_pivot_count_per_mutant: Counter[int] = Counter()
    all_closed_samples: list[dict[str, Any]] = []
    alternate_open_samples: list[dict[str, Any]] = []
    unresolved_samples: list[dict[str, Any]] = []

    for mh, row in sorted(pivot1_closed.items()):
        formula = row["formula"]
        variables = r50g25.formula_variables(formula)
        if 1 not in variables:
            # A pivot-1 door can be absent because variable 1 was structurally removed.
            # Still audit every remaining variable; record this fact explicitly.
            pivot1_present = False
        else:
            pivot1_present = True
        open_edges: list[dict[str, Any]] = []

        for pivot in variables:
            candidate = r47j.macro_candidate_fixpoint(formula, int(pivot))
            if candidate is None:
                pivot_missing_frequency[int(pivot)] += 1
                if int(pivot) != 1:
                    alternate_missing_edge_count += 1
                continue
            replay = r47j.independent_fixpoint_macro_replay(formula, candidate)
            if not replay.get("pass"):
                raise AssertionError(("R50G28_ALTERNATE_PIVOT_REPLAY_FAIL", mh, pivot, replay))
            if int(pivot) == 1:
                raise AssertionError(("R50G28_PIVOT1_UNEXPECTEDLY_OPEN", mh, pivot))

            alternate_candidate_edge_count += 1
            pivot_open_frequency[int(pivot)] += 1
            norm = candidate["normalization"]
            terminal = norm.get("terminal")
            final_formula = r50g23.canon(norm.get("final_formula", []))
            terminal_key = "UNRESOLVED" if terminal is None else str(terminal)
            alternate_terminal_partition[terminal_key] += 1
            if terminal is None:
                alternate_unresolved_edge_count += 1
            elif terminal == "DIRECT_EMPTY_CNF":
                alternate_direct_sat_edge_count += 1
            elif terminal == "DIRECT_EMPTY_CLAUSE":
                alternate_direct_unsat_edge_count += 1
            edge = {
                "pivot": int(pivot),
                "terminal": terminal,
                "final_CLV": list(r33.measure(final_formula)),
                "final_formula": r50g25.json_formula(final_formula),
                "round_count": int(norm.get("round_count", 0)),
                "restart_count": int(norm.get("restart_count", 0)),
            }
            open_edges.append(edge)
            if terminal is None and len(unresolved_samples) < MAX_SAMPLES:
                unresolved_samples.append({
                    "mutant_hash": mh,
                    "representative": row["representative"],
                    "pivot1_present": pivot1_present,
                    "alternate_edge": edge,
                })

        open_pivot_count_per_mutant[len(open_edges)] += 1
        if open_edges:
            mutant_with_any_alternate += 1
            if len(alternate_open_samples) < MAX_SAMPLES:
                alternate_open_samples.append({
                    "mutant_hash": mh,
                    "path_multiplicity": int(row["path_multiplicity"]),
                    "representative": row["representative"],
                    "pivot1_present": pivot1_present,
                    "variable_count": len(variables),
                    "open_edges": open_edges[:8],
                    "open_edge_count": len(open_edges),
                })
        else:
            mutant_all_r47j_pivots_closed += 1
            if len(all_closed_samples) < MAX_SAMPLES:
                all_closed_samples.append({
                    "mutant_hash": mh,
                    "path_multiplicity": int(row["path_multiplicity"]),
                    "representative": row["representative"],
                    "pivot1_present": pivot1_present,
                    "variables": variables,
                    "formula_CLV": list(r33.measure(formula)),
                    "formula": r50g25.json_formula(formula),
                    "classification": "ALL_R47J_PIVOT_DOORS_CLOSED_SINGLE_FLIP_CANDIDATE",
                })

    if mutant_with_any_alternate + mutant_all_r47j_pivots_closed != EXPECTED_PIVOT1_DOOR_CLOSED:
        raise AssertionError("R50G28_MUTANT_ACCOUNTING_DRIFT")

    if mutant_all_r47j_pivots_closed:
        next_gate = "R50G29_ALL_R47J_PIVOTS_CLOSED_DIRECT_R33_RUP_AFFINE_OPERATOR_AUDIT"
        answer = (
            f"R50G28 sealed all {EXPECTED_PIVOT1_DOOR_CLOSED} pivot-1 door-closed mutants and exhaustively audited every existing-variable R47J pivot. "
            f"{mutant_with_any_alternate} mutants regain at least one alternate R47J pivot door, while {mutant_all_r47j_pivots_closed} close every R47J pivot door. "
            "Next: independently audit those all-pivot-closed mutants against direct R33/RUP/affine/other frozen operators before any stronger interpretation."
        )
    elif alternate_unresolved_edge_count:
        next_gate = "R50G29_ALTERNATE_PIVOT_UNRESOLVED_EDGE_INDEPENDENT_REPLAY_AND_OPERATOR_AUDIT"
        answer = (
            f"All {EXPECTED_PIVOT1_DOOR_CLOSED} pivot-1 closures have an alternate R47J pivot, but {alternate_unresolved_edge_count} alternate pivot edges remain unresolved under R47J normalization. "
            "Next: independently replay and audit those unresolved alternate edges."
        )
    else:
        next_gate = "R50G29_PIVOT1_CLOSURE_FINITE_NEGATIVE__ALL_HAVE_SOLVING_ALTERNATE_R47J_DOOR"
        answer = (
            f"All {EXPECTED_PIVOT1_DOOR_CLOSED} pivot-1 door-closed mutants regain at least one alternate R47J pivot and every alternate candidate normalizes terminally. "
            "Thus pivot-1 closure alone is a finite negative as a global obstruction; next search must target pivot-independent structure."
        )

    return normalize({
        "engine": ENGINE,
        "parent_seal": {
            "pair_path_count": pair_paths,
            "unique_pair_state_count": len(unique_pairs),
            "raw_valid_flip_path_count": raw_flip_paths,
            "unique_mutant_formula_count": len(unique_mutants),
            "pivot1_success_first_partition": dict(pivot1_success_first),
            "pivot1_terminal_partition": dict(pivot1_terminals),
            "pivot1_door_closed_actual_count": len(pivot1_closed),
            "seal_replay_pass": True,
        },
        "pivot1_door_closed_mutant_count": len(pivot1_closed),
        "mutant_with_any_alternate_r47j_pivot_count": mutant_with_any_alternate,
        "mutant_all_r47j_pivots_closed_count": mutant_all_r47j_pivots_closed,
        "alternate_candidate_edge_count": alternate_candidate_edge_count,
        "alternate_missing_edge_count": alternate_missing_edge_count,
        "alternate_terminal_partition": dict(alternate_terminal_partition),
        "alternate_unresolved_edge_count": alternate_unresolved_edge_count,
        "alternate_direct_sat_edge_count": alternate_direct_sat_edge_count,
        "alternate_direct_unsat_edge_count": alternate_direct_unsat_edge_count,
        "pivot_open_frequency": {str(k): v for k, v in sorted(pivot_open_frequency.items())},
        "pivot_missing_frequency": {str(k): v for k, v in sorted(pivot_missing_frequency.items())},
        "open_pivot_count_per_mutant": {str(k): v for k, v in sorted(open_pivot_count_per_mutant.items())},
        "all_r47j_pivots_closed_samples": all_closed_samples,
        "alternate_open_samples": alternate_open_samples,
        "unresolved_alternate_samples": unresolved_samples,
        "search_exhaustive_within_declared_alternate_pivot_grammar": True,
        "recommended_next_gate": next_gate,
        "answer": answer,
        "scope_firewall": {
            "new_mutations_introduced": False,
            "family_expanded": False,
            "new_variables_added": False,
            "r47j_definition_changed": False,
            "all_existing_variable_pivots_audited": True,
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
        raise ValueError("R50G28_BAD_REQUEST")
    gate = str((request.get("frontier") or {}).get("gate") or rid)
    if "R50G28_SINGLE_FLIP_DOOR_CLOSED_ALTERNATE_PIVOT_AUDIT" not in gate:
        raise ValueError(f"R50G28_WRONG_GATE:{gate}")
    report = run(request, Path(args.workspace))
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_6",
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
    print(f"TRUMP_R50G28_RECEIPT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
