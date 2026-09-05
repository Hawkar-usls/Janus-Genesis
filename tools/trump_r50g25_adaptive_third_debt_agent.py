#!/usr/bin/env python3
"""JANUS R50G25 adaptive third-debt / additive-obstruction lane.

The lane inherits the exact R50G24 #240 generator that produced the sealed
1774 pair trials. It first reproduces that parent population and its first-rule
partition before testing any third clause. Only then does it pay the direct
additive debt of the pair's current first R33 transition.

Scope:
- same frozen 30 R50G22/R50G23 skeletons;
- same R47J pivot 1;
- no new variables;
- binary + binary parent pairs exactly as R50G24 #240;
- one additional binary clause only when the current first transition has a
  direct additive debt;
- UNIT/other monotone transitions with no direct additive debt are recorded as
  additive obstructions instead of being hidden behind arbitrary clauses;
- no claim that bounded search proves SAT in P or P=NP.
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

LANE_ID = "JANUS_TRUMP_R50G25_ADAPTIVE_THIRD_DEBT_LANE"
ENGINE = "DETERMINISTIC_R50G25_ADAPTIVE_THIRD_DEBT"
MAX_TRIPLE_TRIALS = 40000
MAX_FIRST_PASS_STRONG = 20
MAX_FULL_SURVIVORS = 12
MAX_NEAR = 24
EXPECTED_PARENT_PAIR_TRIALS = 1774
EXPECTED_PARENT_FINAL_FIRST = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 786,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 887,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 7,
}


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


def formula_variables(formula) -> list[int]:
    return sorted({abs(int(lit)) for clause in formula for lit in clause})


def bipolar(formula) -> bool:
    signs: dict[int, set[int]] = {}
    for clause in formula:
        for raw in clause:
            lit = int(raw)
            signs.setdefault(abs(lit), set()).add(1 if lit > 0 else -1)
    return bool(signs) and all(v == {-1, 1} for v in signs.values())


def json_formula(formula) -> list[list[int]]:
    return [[int(x) for x in clause] for clause in formula]


def first_label(reduced: dict[str, Any]) -> str:
    history = reduced.get("history", [])
    if history:
        return "R33:" + str(history[0]["rule"])
    return "R33_TERMINAL:" + str(reduced.get("terminal"))


def debt_from_first_record(r50g23, reduced: dict[str, Any]) -> dict[str, Any] | None:
    history = reduced.get("history", [])
    if not history:
        return None
    compact = r50g23.compact_r33_record(history[0])
    step = {"phase": "R33", "record": compact}
    try:
        return r50g23.direct_blocking_debt(step)
    except Exception:
        return None


def required_literals(debt: dict[str, Any] | None) -> list[int]:
    if not debt:
        return []
    if debt.get("required_literal") is not None:
        return [int(debt["required_literal"])]
    vals = debt.get("allowed_required_literals")
    if isinstance(vals, list):
        return [int(x) for x in vals]
    return []


def binary_clauses(req_lits: list[int], variables: list[int]) -> list[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for req in req_lits:
        for v in variables:
            if v == abs(req):
                continue
            for partner in (v, -v):
                if partner == -req:
                    continue
                clause = tuple(sorted((int(req), int(partner))))
                if clause[0] == -clause[1]:
                    continue
                out.add(clause)
    return sorted(out)


def replay_state(r50g23, source, added: list[tuple[int, ...]]) -> dict[str, Any]:
    r33 = r50g23.r33
    r47j = r50g23.r47j
    pivot = int(r50g23.PIVOT)
    mutated = r50g23.canon(list(source) + list(added))
    candidate = r47j.macro_candidate_fixpoint(mutated, pivot)
    if candidate is None:
        return {"ok": False, "reason": "R47J_CANDIDATE_MISSING"}
    replay = r47j.independent_fixpoint_macro_replay(mutated, candidate)
    if not replay.get("pass"):
        return {"ok": False, "reason": "R47J_REPLAY_FAIL", "replay": replay}
    forced = r50g23.canon(candidate["DP"]["transformed"])
    reduced = r33.simplify(forced)
    final_formula = r50g23.canon(reduced["final_formula"])
    full_final = r50g23.canon(candidate["normalization"].get("final_formula", []))
    return {
        "ok": True,
        "mutated": mutated,
        "candidate": candidate,
        "forced": forced,
        "reduced": reduced,
        "final": final_formula,
        "full_final": full_final,
        "first_label": first_label(reduced),
        "debt": debt_from_first_record(r50g23, reduced),
    }


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
        raise AssertionError(("R50G25_FROZEN_COUNT_DRIFT", len(skeletons)))

    # Parent seal reproduction counters.
    parent_pair_trials = 0
    parent_final_first: Counter[str] = Counter()
    parent_first_clause_candidates = 0
    parent_first_transition_breaks = 0
    parent_second_debt_available = 0
    parent_first_replacement: Counter[str] = Counter()
    parent_second_debt: Counter[str] = Counter()
    parent_strong = 0

    # R50G25 counters.
    triple_trials = 0
    third_debt_partition: Counter[str] = Counter()
    additive_obstruction_partition: Counter[str] = Counter()
    triple_first_partition: Counter[str] = Counter()
    triple_terminal_partition: Counter[str] = Counter()
    replay_failures: Counter[str] = Counter()
    first_pass_strong: list[dict[str, Any]] = []
    full_survivors: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []

    for item in skeletons:
        source = r50g23.canon(item["source"])
        source_vars = formula_variables(source)
        base = r50g23.audit_one_skeleton(item)
        base_label = str(base["transition_labels"][0])
        base_debt = base["first_transition_direct_blocking_debt"]
        first_clauses = binary_clauses(required_literals(base_debt), source_vars)

        for c1 in first_clauses:
            if c1 in source:
                continue
            parent_first_clause_candidates += 1
            s1 = replay_state(r50g23, source, [c1])
            if not s1["ok"]:
                replay_failures["PARENT_FIRST:" + str(s1["reason"])] += 1
                continue
            if s1["first_label"] == base_label:
                continue

            parent_first_transition_breaks += 1
            parent_first_replacement[s1["first_label"]] += 1
            debt2 = s1.get("debt")
            req2 = required_literals(debt2)
            if not req2:
                parent_second_debt["NO_DIRECT_ADDITIVE_DEBT"] += 1
                continue
            parent_second_debt_available += 1
            parent_second_debt[str(debt2.get("debt_class", "UNKNOWN"))] += 1
            second_clauses = binary_clauses(req2, source_vars)

            for c2 in second_clauses:
                if c2 == c1 or c2 in source:
                    continue
                parent_pair_trials += 1
                s2 = replay_state(r50g23, source, [c1, c2])
                if not s2["ok"]:
                    replay_failures["PARENT_PAIR:" + str(s2["reason"])] += 1
                    continue

                parent_final_first[s2["first_label"]] += 1
                reduced2 = s2["reduced"]
                final2 = s2["final"]
                if (
                    reduced2.get("terminal") == "STALLED_STACK_LEAN_CORE"
                    and bool(final2)
                    and bipolar(final2)
                ):
                    parent_strong += 1

                debt3 = s2.get("debt")
                debt3_class = str((debt3 or {}).get("debt_class", "NO_DIRECT_ADDITIVE_DEBT"))
                req3 = required_literals(debt3)
                if not req3:
                    additive_obstruction_partition[s2["first_label"] + "::" + debt3_class] += 1
                    continue
                third_debt_partition[debt3_class] += 1
                third_clauses = binary_clauses(req3, source_vars)

                for c3 in third_clauses:
                    if triple_trials >= MAX_TRIPLE_TRIALS:
                        raise AssertionError(("R50G25_TRIPLE_BUDGET_EXHAUSTED", triple_trials))
                    if c3 in source or c3 == c1 or c3 == c2:
                        continue
                    triple_trials += 1
                    s3 = replay_state(r50g23, source, [c1, c2, c3])
                    if not s3["ok"]:
                        replay_failures["TRIPLE:" + str(s3["reason"])] += 1
                        continue

                    reduced3 = s3["reduced"]
                    final3 = s3["final"]
                    full_final3 = s3["full_final"]
                    terminal3 = str(reduced3.get("terminal"))
                    triple_first_partition[s3["first_label"]] += 1
                    triple_terminal_partition[terminal3] += 1
                    stalled_bipolar = (
                        terminal3 == "STALLED_STACK_LEAN_CORE"
                        and bool(final3)
                        and bipolar(final3)
                    )
                    full_nonempty = bool(full_final3)

                    row = {
                        "spec": item["spec"],
                        "source_hash": item["source_hash"],
                        "base_first_transition": base_label,
                        "first_clause": [int(x) for x in c1],
                        "second_clause": [int(x) for x in c2],
                        "pair_first_transition": s2["first_label"],
                        "pair_direct_debt": debt3,
                        "third_clause": [int(x) for x in c3],
                        "triple_first_transition": s3["first_label"],
                        "mutated_source_CLV": list(r33.measure(s3["mutated"])),
                        "forced_DP_CLV": list(r33.measure(s3["forced"])),
                        "R33_terminal": terminal3,
                        "R33_transition_labels": [
                            "R33:" + str(x["rule"]) for x in reduced3.get("history", [])
                        ],
                        "R33_final_CLV": list(r33.measure(final3)),
                        "R33_final_formula": json_formula(final3),
                        "first_pass_nonempty_bipolar_stalled": stalled_bipolar,
                        "r47j_replay_pass": True,
                        "full_R47J_terminal": s3["candidate"]["normalization"].get("terminal"),
                        "full_R47J_round_count": int(s3["candidate"]["normalization"].get("round_count", 0)),
                        "full_R47J_restart_count": int(s3["candidate"]["normalization"].get("restart_count", 0)),
                        "full_R47J_final_CLV": list(r33.measure(full_final3)),
                        "full_R47J_final_formula": json_formula(full_final3),
                        "full_R47J_nonempty": full_nonempty,
                    }

                    if stalled_bipolar:
                        row["classification"] = "FIRST_PASS_STRONG_TRIPLE_CANDIDATE"
                        if len(first_pass_strong) < MAX_FIRST_PASS_STRONG:
                            first_pass_strong.append(row)
                    elif len(near) < MAX_NEAR and s3["first_label"] != s2["first_label"]:
                        row["classification"] = "THIRD_CLAUSE_CHANGED_PAIR_ESCAPE_BUT_STRONG_GATE_NOT_MET"
                        near.append(row)

                    if full_nonempty:
                        row2 = dict(row)
                        row2["classification"] = "FULL_R47J_NONEMPTY_TRIPLE_SURVIVOR"
                        if len(full_survivors) < MAX_FULL_SURVIVORS:
                            full_survivors.append(row2)

    observed_parent = dict(parent_final_first)
    if parent_pair_trials != EXPECTED_PARENT_PAIR_TRIALS:
        raise AssertionError(("R50G25_PARENT_PAIR_COUNT_DRIFT", parent_pair_trials, EXPECTED_PARENT_PAIR_TRIALS))
    if observed_parent != EXPECTED_PARENT_FINAL_FIRST:
        raise AssertionError(("R50G25_PARENT_PARTITION_DRIFT", observed_parent, EXPECTED_PARENT_FINAL_FIRST))
    if parent_strong != 0:
        raise AssertionError(("R50G25_PARENT_STRONG_DRIFT", parent_strong))

    if full_survivors:
        recommended = "R50G26_FULL_R47J_TRIPLE_SURVIVOR_INDEPENDENT_REPLAY_AND_DELTA_MINIMIZATION"
        answer = (
            f"R50G25 воспроизвёл sealed parent: {parent_pair_trials} pair trials и точный partition. "
            f"После adaptive third-debt проверено {triple_trials} triple trials; найдено "
            f"{len(full_survivors)} сохранённых full-R47J nonempty candidates. Следующий шаг — "
            "независимый replay и delta-minimization, без расширения family."
        )
    elif first_pass_strong:
        recommended = "R50G26_FIRST_PASS_TRIPLE_CORE_DOWNSTREAM_RUP_RESTART_ESCAPE_AUDIT"
        answer = (
            f"R50G25 воспроизвёл sealed parent: {parent_pair_trials} pair trials и точный partition. "
            f"Из {triple_trials} adaptive triple trials найдено {len(first_pass_strong)} first-pass "
            "bipolar stalled candidates, но full R47J всё ещё не оставил непустого финала. "
            "Следующий gate — локализовать downstream RUP/restart escape."
        )
    else:
        recommended = "R50G26_BINARY_ADDITIVE_DEPTH3_NEGATIVE__WIDTH3_OR_NONADDITIVE_PRESTATE_FORK"
        answer = (
            f"R50G25 воспроизвёл sealed parent: {parent_pair_trials} pair trials и точный partition. "
            f"Проверено {triple_trials} adaptive third-debt binary triples; first-pass strong survivor не найден. "
            "Следующий честный fork: либо минимальная width-3 structural support, либо non-additive prestate change; "
            "просто добавлять четвёртую binary clause без новой причины запрещено."
        )

    return normalize({
        "engine": ENGINE,
        "parent_seal": {
            "expected_pair_trial_count": EXPECTED_PARENT_PAIR_TRIALS,
            "observed_pair_trial_count": parent_pair_trials,
            "expected_final_first_partition": EXPECTED_PARENT_FINAL_FIRST,
            "observed_final_first_partition": observed_parent,
            "parent_first_clause_candidate_count": parent_first_clause_candidates,
            "parent_first_transition_break_count": parent_first_transition_breaks,
            "parent_second_direct_debt_available_count": parent_second_debt_available,
            "parent_first_replacement_partition": dict(parent_first_replacement),
            "parent_second_debt_partition": dict(parent_second_debt),
            "parent_strong_count": parent_strong,
            "seal_replay_pass": True,
        },
        "triple_trial_count": triple_trials,
        "third_debt_partition": dict(third_debt_partition),
        "additive_obstruction_partition": dict(additive_obstruction_partition),
        "triple_first_transition_partition": dict(triple_first_partition),
        "triple_R33_terminal_partition": dict(triple_terminal_partition),
        "replay_failure_partition": dict(replay_failures),
        "first_pass_strong_count": len(first_pass_strong),
        "first_pass_strong_candidates": first_pass_strong,
        "full_R47J_nonempty_candidate_count": len(full_survivors),
        "full_R47J_nonempty_candidates": full_survivors,
        "near_misses": near,
        "recommended_next_gate": recommended,
        "answer": answer,
        "scope_firewall": {
            "family_expanded": False,
            "new_variables_added": False,
            "r47j_changed": False,
            "mutation_width": "BINARY_PLUS_BINARY_PLUS_BINARY_ONLY",
            "parent_pair_space_changed": False,
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
    if "R50G25_ADAPTIVE_THIRD_DEBT" not in gate:
        raise ValueError(f"R50G25_WRONG_GATE:{gate}")

    report = run(request, workspace)
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_3",
        "lane_id": LANE_ID,
        "request_id": request_id,
        "processed_at_utc": utc_now(),
        "source_repo": request.get("source_repo"),
        "source_branch": request.get("source_branch"),
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "engine": ENGINE,
        "provider_error_observed": False,
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
    print(f"TRUMP_R50G25_RECEIPT={outbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
