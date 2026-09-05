#!/usr/bin/env python3
"""R50G26: unique-pair-state width-3 structural support / obstruction lane.

This is the minimal structural-width escalation after the corrected R50G25
binary-additive-depth-3 finite negative. It inherits the exact sealed R50G24
pair generator, deduplicates semantically identical pair formulas by canonical
formula hash, and tests one width-3 clause that pays the pair state's actual
first-transition additive debt.

Firewalls:
- exactly the frozen 30 R50G22/R50G23 skeletons;
- exact 1774 parent pair paths and exact 887/786/94/7 first-rule partition;
- same R47J pivot 1;
- no new variables;
- no fourth binary-depth escalation;
- UNIT/no-direct-debt states are recorded as additive obstructions;
- bounded search is not a theorem; P_VS_NP remains OPEN.
"""

from __future__ import annotations

import argparse
import importlib
import itertools
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import trump_r50g25_adaptive_third_debt_agent as r50g25

LANE_ID = "JANUS_TRUMP_R50G26_WIDTH3_UNIQUE_PAIR_STATE_LANE"
ENGINE = "DETERMINISTIC_R50G26_UNIQUE_PAIR_STATE_WIDTH3_STRUCTURAL_SUPPORT"
EXPECTED_PARENT_PAIR_TRIALS = 1774
EXPECTED_PARENT_FINAL_FIRST = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 786,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 887,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 7,
}
MAX_WIDTH3_TRIALS = 160000
MAX_WITNESSES = 16
MAX_NEAR = 24


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(report: dict[str, Any]) -> dict[str, Any]:
    out = dict(report)
    out["lane"] = "TRUMP_FALSIFICATION_RESEARCH"
    out["status"] = "HYPOTHESIS"
    out["proof_claim"] = False
    out["p_vs_np"] = "OPEN"
    out["sat_in_p"] = "NOT_PROVED"
    return out


def clause_has_tautology(clause: tuple[int, ...]) -> bool:
    s = set(int(x) for x in clause)
    return any(-x in s for x in s)


def bce_non_tautological_support(debt: dict[str, Any], clause: tuple[int, ...]) -> bool:
    req = debt.get("required_literal")
    blocked = debt.get("blocked_clause")
    if req is None or not isinstance(blocked, list):
        return False
    req = int(req)
    blocker = -req
    c_rest = [int(x) for x in blocked if int(x) != blocker]
    d_rest = [int(x) for x in clause if int(x) != req]
    resolvent = tuple(c_rest + d_rest)
    return not clause_has_tautology(resolvent)


def width3_debt_clauses(
    debt: dict[str, Any] | None,
    variables: list[int],
) -> list[tuple[int, int, int]]:
    reqs = r50g25.required_literals(debt)
    if not reqs:
        return []
    out: set[tuple[int, int, int]] = set()
    debt_class = str((debt or {}).get("debt_class", ""))
    for req in reqs:
        support_vars = [v for v in variables if v != abs(int(req))]
        for a, b in itertools.combinations(support_vars, 2):
            for sa in (a, -a):
                for sb in (b, -b):
                    clause = tuple(sorted((int(req), int(sa), int(sb))))
                    if len({abs(x) for x in clause}) != 3:
                        continue
                    if clause_has_tautology(clause):
                        continue
                    if debt_class == "NONTAUTOLOGICAL_OPPOSITE_BLOCKER_SUPPORT":
                        if not bce_non_tautological_support(debt or {}, clause):
                            continue
                    out.add(clause)
    return sorted(out)


def full_unresolved_survivor(state: dict[str, Any]) -> bool:
    if not state.get("ok"):
        return False
    normalization = state["candidate"]["normalization"]
    formula = state["full_final"]
    return (
        normalization.get("terminal") is None
        and bool(formula)
        and all(len(clause) > 0 for clause in formula)
    )


def first_pass_strong(state: dict[str, Any]) -> bool:
    if not state.get("ok"):
        return False
    reduced = state["reduced"]
    formula = state["final"]
    return (
        reduced.get("terminal") == "STALLED_STACK_LEAN_CORE"
        and bool(formula)
        and all(len(clause) > 0 for clause in formula)
        and r50g25.bipolar(formula)
    )


def run(request: dict[str, Any], workspace: Path) -> dict[str, Any]:
    exp = workspace / "experiments"
    if not exp.is_dir():
        raise RuntimeError(f"TRUMP_EXPERIMENTS_MISSING:{exp}")
    for p in (str(workspace), str(exp)):
        if p not in sys.path:
            sys.path.insert(0, p)

    r50g23 = importlib.import_module(
        "janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt"
    )
    r33 = r50g23.r33
    skeletons = r50g23.clean_skeletons_from_frozen_r50g22()
    if len(skeletons) != 30:
        raise AssertionError(("R50G26_FROZEN_COUNT_DRIFT", len(skeletons)))

    parent_pair_paths = 0
    parent_partition: Counter[str] = Counter()
    parent_strong = 0
    parent_replay_failures: Counter[str] = Counter()
    unique: dict[str, dict[str, Any]] = {}

    # Reproduce the exact historical pair generator before width escalation.
    for item in skeletons:
        source = r50g23.canon(item["source"])
        source_vars = r50g25.formula_variables(source)
        base = r50g23.audit_one_skeleton(item)
        base_label = str(base["transition_labels"][0])
        first_clauses = r50g25.binary_clauses(
            r50g25.required_literals(base["first_transition_direct_blocking_debt"]),
            source_vars,
        )

        for c1 in first_clauses:
            if c1 in source:
                continue
            s1 = r50g25.replay_state(r50g23, source, [c1])
            if not s1["ok"]:
                parent_replay_failures["FIRST:" + str(s1["reason"])] += 1
                continue
            if s1["first_label"] == base_label:
                continue
            debt2 = s1.get("debt")
            req2 = r50g25.required_literals(debt2)
            if not req2:
                continue
            second_clauses = r50g25.binary_clauses(req2, source_vars)

            for c2 in second_clauses:
                if c2 == c1 or c2 in source:
                    continue
                parent_pair_paths += 1
                s2 = r50g25.replay_state(r50g23, source, [c1, c2])
                if not s2["ok"]:
                    parent_replay_failures["PAIR:" + str(s2["reason"])] += 1
                    continue
                parent_partition[s2["first_label"]] += 1
                if first_pass_strong(s2):
                    parent_strong += 1

                pair_formula = r50g23.canon(s2["mutated"])
                pair_hash = r50g23.r50g4.fhash(pair_formula)
                debt3 = s2.get("debt")
                debt_class = str((debt3 or {}).get("debt_class", "NO_DIRECT_ADDITIVE_DEBT"))
                existing = unique.get(pair_hash)
                path = {
                    "spec": item["spec"],
                    "source_hash": item["source_hash"],
                    "first_clause": [int(x) for x in c1],
                    "second_clause": [int(x) for x in c2],
                }
                if existing is None:
                    unique[pair_hash] = {
                        "pair_hash": pair_hash,
                        "formula": pair_formula,
                        "variables": r50g25.formula_variables(pair_formula),
                        "first_label": s2["first_label"],
                        "debt": debt3,
                        "debt_class": debt_class,
                        "multiplicity": 1,
                        "representative": path,
                    }
                else:
                    if existing["first_label"] != s2["first_label"]:
                        raise AssertionError(("R50G26_HASH_FIRST_LABEL_DRIFT", pair_hash))
                    if existing["debt_class"] != debt_class:
                        raise AssertionError(("R50G26_HASH_DEBT_CLASS_DRIFT", pair_hash))
                    existing["multiplicity"] += 1

    observed_parent = dict(parent_partition)
    if parent_pair_paths != EXPECTED_PARENT_PAIR_TRIALS:
        raise AssertionError(("R50G26_PARENT_PAIR_COUNT_DRIFT", parent_pair_paths, EXPECTED_PARENT_PAIR_TRIALS))
    if observed_parent != EXPECTED_PARENT_FINAL_FIRST:
        raise AssertionError(("R50G26_PARENT_PARTITION_DRIFT", observed_parent, EXPECTED_PARENT_FINAL_FIRST))
    if parent_strong != 0:
        raise AssertionError(("R50G26_PARENT_STRONG_DRIFT", parent_strong))
    if parent_replay_failures:
        raise AssertionError(("R50G26_PARENT_REPLAY_DRIFT", dict(parent_replay_failures)))

    unique_rule_partition: Counter[str] = Counter()
    unique_debt_partition: Counter[str] = Counter()
    weighted_obstruction_partition: Counter[str] = Counter()
    unique_obstruction_partition: Counter[str] = Counter()
    width3_first_partition: Counter[str] = Counter()
    width3_terminal_partition: Counter[str] = Counter()
    width3_trials = 0
    weighted_trial_multiplicity = 0
    r47j_closed: list[dict[str, Any]] = []
    full_survivors: list[dict[str, Any]] = []
    first_pass: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    replay_failures: Counter[str] = Counter()

    for pair_hash, row in sorted(unique.items()):
        unique_rule_partition[row["first_label"]] += 1
        unique_debt_partition[row["debt_class"]] += 1
        debt = row["debt"]
        reqs = r50g25.required_literals(debt)
        if not reqs:
            key = row["first_label"] + "::" + row["debt_class"]
            unique_obstruction_partition[key] += 1
            weighted_obstruction_partition[key] += int(row["multiplicity"])
            continue

        candidates = width3_debt_clauses(debt, row["variables"])
        for c3 in candidates:
            if c3 in row["formula"]:
                continue
            width3_trials += 1
            weighted_trial_multiplicity += int(row["multiplicity"])
            if width3_trials > MAX_WIDTH3_TRIALS:
                raise AssertionError(("R50G26_WIDTH3_BUDGET_EXHAUSTED", width3_trials, MAX_WIDTH3_TRIALS))

            s3 = r50g25.replay_state(r50g23, row["formula"], [c3])
            base_record = {
                "pair_hash": pair_hash,
                "pair_multiplicity": int(row["multiplicity"]),
                "pair_first_transition": row["first_label"],
                "pair_direct_debt": debt,
                "representative_parent_path": row["representative"],
                "width3_clause": [int(x) for x in c3],
            }

            if not s3["ok"]:
                if s3["reason"] == "R47J_CANDIDATE_MISSING":
                    if len(r47j_closed) < MAX_WITNESSES:
                        r47j_closed.append({
                            **base_record,
                            "classification": "SAME_PIVOT_R47J_DOOR_CLOSED_WIDTH3_CANDIDATE",
                        })
                    continue
                replay_failures[str(s3["reason"])] += 1
                continue

            terminal = str(s3["reduced"].get("terminal"))
            width3_first_partition[s3["first_label"]] += 1
            width3_terminal_partition[terminal] += 1
            record = {
                **base_record,
                "width3_first_transition": s3["first_label"],
                "R33_terminal": terminal,
                "R33_final_CLV": list(r33.measure(s3["final"])),
                "R33_final_formula": r50g25.json_formula(s3["final"]),
                "full_R47J_terminal": s3["candidate"]["normalization"].get("terminal"),
                "full_R47J_final_CLV": list(r33.measure(s3["full_final"])),
                "full_R47J_final_formula": r50g25.json_formula(s3["full_final"]),
                "r47j_replay_pass": True,
            }

            if full_unresolved_survivor(s3):
                if len(full_survivors) < MAX_WITNESSES:
                    full_survivors.append({
                        **record,
                        "classification": "FULL_R47J_UNRESOLVED_WIDTH3_SURVIVOR",
                    })
            elif first_pass_strong(s3):
                if len(first_pass) < MAX_WITNESSES:
                    first_pass.append({
                        **record,
                        "classification": "FIRST_PASS_WIDTH3_BIPOLAR_STALLED_CANDIDATE",
                    })
            elif len(near) < MAX_NEAR and s3["first_label"] != row["first_label"]:
                near.append({
                    **record,
                    "classification": "WIDTH3_CHANGED_ESCAPE_BUT_SOLVED",
                })

    if replay_failures:
        raise AssertionError(("R50G26_R47J_REPLAY_FAILURE", dict(replay_failures)))

    exhaustive = width3_trials <= MAX_WIDTH3_TRIALS
    if r47j_closed:
        next_gate = "R50G27_WIDTH3_SAME_PIVOT_DOOR_CLOSED_WITNESS_ALTERNATE_DOOR_AUDIT"
        answer = (
            f"R50G26 reproduced the sealed 1774 parent paths and compressed them to {len(unique)} unique pair states. "
            f"Across {width3_trials} exact width-3 debt trials, at least {len(r47j_closed)} recorded candidates closed the same-pivot R47J door. "
            "Next: independently replay those witnesses and test alternate pivots/operators before any claim promotion."
        )
    elif full_survivors:
        next_gate = "R50G27_WIDTH3_FULL_FIXPOINT_SURVIVOR_INDEPENDENT_REPLAY_AND_DELTA_MINIMIZATION"
        answer = (
            f"R50G26 reproduced the sealed parent and tested {width3_trials} width-3 debt mutations over {len(unique)} unique pair states. "
            f"Recorded {len(full_survivors)} unresolved full-R47J survivor candidates. Next: independent replay and delta-minimization."
        )
    elif first_pass:
        next_gate = "R50G27_WIDTH3_FIRST_PASS_CORE_DOWNSTREAM_ESCAPE_AUDIT"
        answer = (
            f"R50G26 tested {width3_trials} width-3 debt mutations over {len(unique)} unique pair states. "
            f"Recorded {len(first_pass)} first-pass bipolar stalled candidates but no full unresolved survivor. Next: audit downstream RUP/restart escape."
        )
    else:
        next_gate = "R50G27_WIDTH3_ADDITIVE_FINITE_NEGATIVE__NONADDITIVE_PRESTATE_FORK"
        answer = (
            f"R50G26 exhaustively tested {width3_trials} width-3 direct-debt mutations over {len(unique)} unique pair states with no same-pivot closure or unresolved residual witness. "
            "The next justified escalation is non-additive prestate mutation; blind fourth binary or wider additive clauses are not authorized by this result."
        )

    return normalize({
        "engine": ENGINE,
        "parent_seal": {
            "observed_pair_path_count": parent_pair_paths,
            "expected_pair_path_count": EXPECTED_PARENT_PAIR_TRIALS,
            "observed_final_first_partition": observed_parent,
            "expected_final_first_partition": EXPECTED_PARENT_FINAL_FIRST,
            "parent_strong_count": parent_strong,
            "seal_replay_pass": True,
        },
        "unique_pair_state_count": len(unique),
        "compression_ratio_pair_paths_per_unique_state": (
            float(parent_pair_paths) / float(len(unique)) if unique else None
        ),
        "unique_pair_first_rule_partition": dict(unique_rule_partition),
        "unique_pair_debt_partition": dict(unique_debt_partition),
        "unique_additive_obstruction_partition": dict(unique_obstruction_partition),
        "weighted_additive_obstruction_partition": dict(weighted_obstruction_partition),
        "width3_trial_count": width3_trials,
        "weighted_path_equivalent_trial_multiplicity": weighted_trial_multiplicity,
        "width3_first_transition_partition": dict(width3_first_partition),
        "width3_R33_terminal_partition": dict(width3_terminal_partition),
        "same_pivot_r47j_door_closed_candidate_count_recorded": len(r47j_closed),
        "same_pivot_r47j_door_closed_candidates": r47j_closed,
        "full_R47J_unresolved_survivor_count_recorded": len(full_survivors),
        "full_R47J_unresolved_survivors": full_survivors,
        "first_pass_strong_count_recorded": len(first_pass),
        "first_pass_strong_candidates": first_pass,
        "near_misses": near,
        "search_exhaustive_within_declared_width3_grammar": exhaustive,
        "recommended_next_gate": next_gate,
        "answer": answer,
        "scope_firewall": {
            "family_expanded": False,
            "new_variables_added": False,
            "r47j_pivot_changed": False,
            "parent_pair_space_changed": False,
            "third_mutation_width": 3,
            "unit_direct_additive_obstruction_respected": True,
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
    workspace = Path(args.workspace)
    habitat = Path(args.habitat_root)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(request.get("request_id") or request_path.stem))[:120]
    if request.get("status") != "QUEUED":
        raise ValueError("TRUMP_REQUEST_NOT_QUEUED")
    if request.get("purpose") != "PARALLEL_TRUMP_CODE_RESEARCH":
        raise ValueError("TRUMP_REQUEST_WRONG_PURPOSE")
    gate = str((request.get("frontier") or {}).get("gate") or request_id)
    if "R50G26_UNIQUE_PAIR_STATE_WIDTH3" not in gate:
        raise ValueError(f"R50G26_WRONG_GATE:{gate}")

    report = run(request, workspace)
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_4",
        "lane_id": LANE_ID,
        "request_id": request_id,
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
            "sat_in_p": "NOT_PROVED"
        },
        "report": report,
    }
    outbox = habitat / "outbox" / "trump" / f"{request_id}.json"
    memory = habitat / "memory" / "trump" / f"{utc_now().replace(':', '-')}_{request_id}.json"
    write_json(outbox, receipt)
    write_json(memory, receipt)
    print(f"TRUMP_R50G26_RECEIPT={outbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
