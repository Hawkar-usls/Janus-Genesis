#!/usr/bin/env python3
"""Deterministic JANUS R50G24 pairwise counterpolarity closure lane.

This lane is intentionally narrower than the generic TRUMP research agent:
- exactly the frozen 30 R50G22/R50G23 skeletons;
- same R47J pivot 1;
- no new variables;
- two additive binary clauses only;
- no writes to the checked-out TRUMP source;
- finite search is never promoted to a theorem.

It is the successor to the finite-negative single-clause search. The first
clause must actually change the original R33 first transition. The second clause
is generated from the direct additive debt of that replacement transition. A
strong candidate must leave the first R33 pass at a nonempty bipolar stalled
core while the independent R47J macro replay still passes.
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

LANE_ID = "JANUS_TRUMP_R50G24_PAIRWISE_COUNTERPOLARITY_LANE"
MAX_PAIR_TRIALS = 12000
MAX_STRONG = 8
MAX_NEAR = 20


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
    return {
        "ok": True,
        "mutated": mutated,
        "candidate": candidate,
        "forced": forced,
        "reduced": reduced,
        "final": final_formula,
        "first_label": first_label(reduced),
        "debt": debt_from_first_record(r50g23, reduced),
    }


def run_pairwise(request: dict[str, Any], workspace: Path) -> dict[str, Any]:
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
        raise AssertionError(("R50G24_PAIRWISE_FROZEN_COUNT_DRIFT", len(skeletons)))

    pair_trials = 0
    first_clause_candidates = 0
    first_transition_breaks = 0
    second_debt_available = 0
    strong: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    failure_partition: Counter[str] = Counter()
    first_replacement_partition: Counter[str] = Counter()
    second_debt_partition: Counter[str] = Counter()

    for item in skeletons:
        if pair_trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG:
            break
        source = r50g23.canon(item["source"])
        source_vars = formula_variables(source)
        base = r50g23.audit_one_skeleton(item)
        base_label = str(base["transition_labels"][0])
        base_debt = base["first_transition_direct_blocking_debt"]
        first_clauses = binary_clauses(required_literals(base_debt), source_vars)

        for c1 in first_clauses:
            if pair_trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG:
                break
            if c1 in source:
                continue
            first_clause_candidates += 1
            s1 = replay_state(r50g23, source, [c1])
            if not s1["ok"]:
                failure_partition[str(s1["reason"])] += 1
                continue
            if s1["first_label"] == base_label:
                continue

            first_transition_breaks += 1
            first_replacement_partition[s1["first_label"]] += 1
            debt2 = s1.get("debt")
            req2 = required_literals(debt2)
            if not req2:
                second_debt_partition["NO_DIRECT_ADDITIVE_DEBT"] += 1
                continue
            second_debt_available += 1
            second_debt_partition[str(debt2.get("debt_class", "UNKNOWN"))] += 1
            second_clauses = binary_clauses(req2, source_vars)

            for c2 in second_clauses:
                if pair_trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG:
                    break
                if c2 == c1 or c2 in source:
                    continue
                pair_trials += 1
                s2 = replay_state(r50g23, source, [c1, c2])
                if not s2["ok"]:
                    failure_partition[str(s2["reason"])] += 1
                    continue

                reduced = s2["reduced"]
                final_formula = s2["final"]
                stalled = reduced.get("terminal") == "STALLED_STACK_LEAN_CORE" and bool(final_formula)
                is_bipolar = bipolar(final_formula) if final_formula else False
                row = {
                    "spec": item["spec"],
                    "source_hash": item["source_hash"],
                    "base_first_transition": base_label,
                    "first_clause": [int(x) for x in c1],
                    "first_clause_replacement_transition": s1["first_label"],
                    "first_clause_replacement_debt": debt2,
                    "second_clause": [int(x) for x in c2],
                    "pair_first_transition": s2["first_label"],
                    "mutated_source_CLV": list(r33.measure(s2["mutated"])),
                    "forced_DP_CLV": list(r33.measure(s2["forced"])),
                    "R33_terminal": reduced.get("terminal"),
                    "R33_transition_labels": ["R33:" + str(x["rule"]) for x in reduced.get("history", [])],
                    "R33_final_CLV": list(r33.measure(final_formula)),
                    "R33_final_formula": json_formula(final_formula),
                    "nonempty_stalled_residual": stalled,
                    "bipolar_residual": is_bipolar,
                    "r47j_replay_pass": True,
                    "full_R47J_terminal": s2["candidate"]["normalization"].get("terminal"),
                    "full_R47J_round_count": int(s2["candidate"]["normalization"].get("round_count", 0)),
                    "full_R47J_restart_count": int(s2["candidate"]["normalization"].get("restart_count", 0)),
                }

                if stalled and is_bipolar:
                    row["classification"] = "STRONG_PAIRWISE_NONEMPTY_BIPOLAR_RESIDUAL"
                    strong.append(row)
                    continue

                failure_partition["PAIR_COLLAPSED_OR_NONBIPOLAR"] += 1
                failure_partition["FINAL_FIRST:" + s2["first_label"]] += 1
                if len(near) < MAX_NEAR and s2["first_label"] != s1["first_label"]:
                    row["classification"] = "SECOND_CLAUSE_CHANGED_REPLACEMENT_BUT_STRONG_GATE_NOT_MET"
                    near.append(row)

    if strong:
        recommended = "R50G24_PAIRWISE_SURVIVOR_INDEPENDENT_REPLAY_AND_DOWNSTREAM_RUP_RESTART_AUDIT"
        answer = (
            f"Pairwise lane проверил {pair_trials} координированных пар и нашёл {len(strong)} strong candidates: "
            "same-pivot R47J replay проходит, а первый R33 pass оставляет непустое биполярное stalled-ядро. "
            "Следующий шаг — независимый replay и проверка, что именно делает полный R47J после этого ядра."
        )
    else:
        dominant = failure_partition.most_common(5)
        recommended = "R50G25_DOMINANT_REPLACEMENT_ESCAPE_STRUCTURAL_DEBT"
        answer = (
            f"Pairwise lane проверил {pair_trials} координированных binary-clause pairs и strong survivor не нашёл. "
            f"Это finite-negative только для этого bounded pairwise space. Доминирующие исходы: {dominant}. "
            "Следующий gate должен атаковать фактический доминирующий replacement escape, а не расширять family."
        )

    return normalize({
        "engine": "DETERMINISTIC_R50G24_PAIRWISE_COUNTERPOLARITY",
        "frozen_skeleton_count": len(skeletons),
        "pair_trial_count": pair_trials,
        "first_clause_candidate_count": first_clause_candidates,
        "first_transition_break_count": first_transition_breaks,
        "second_direct_debt_available_count": second_debt_available,
        "first_replacement_partition": dict(first_replacement_partition),
        "second_debt_partition": dict(second_debt_partition),
        "failure_partition": dict(failure_partition),
        "strong_candidate_count": len(strong),
        "strong_candidates": strong,
        "near_misses": near,
        "recommended_next_gate": recommended,
        "answer": answer,
        "scope_firewall": {
            "family_expanded": False,
            "new_variables_added": False,
            "r47j_changed": False,
            "pair_width": "BINARY_PLUS_BINARY_ONLY",
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
    if "PAIRWISE-COUNTERPOLARITY-CLOSURE" not in request_id:
        raise ValueError("R50G24_PAIRWISE_REQUEST_ID_REQUIRED")

    report = run_pairwise(request, workspace)
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_2",
        "lane_id": LANE_ID,
        "request_id": request_id,
        "processed_at_utc": utc_now(),
        "source_repo": request.get("source_repo"),
        "source_branch": request.get("source_branch"),
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "engine": "DETERMINISTIC_R50G24_PAIRWISE_COUNTERPOLARITY",
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
    print(f"TRUMP_PAIRWISE_RECEIPT={outbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
