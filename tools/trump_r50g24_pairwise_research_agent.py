#!/usr/bin/env python3
"""Deterministic pairwise R50G24 research lane for JANUS Git Habitat.

This lane is intentionally narrow:
- exactly the frozen 30 R50G22/R50G23 skeletons;
- same R47J pivot 1;
- no new variables;
- exactly two added binary clauses around the first-transition debt variable;
- no write authority over TRUMP;
- finite search is never promoted to a theorem.
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
from typing import Any, Dict

LANE_ID = "JANUS_TRUMP_GIT_RESEARCH_LANE"
ENGINE = "DETERMINISTIC_R50G24_PAIRWISE_COUNTERPOLARITY_LAB"
MAX_PAIR_TRIALS = 12000
MAX_STRONG_CANDIDATES = 8
MAX_NEAR_MISSES = 20


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def formula_variables(formula) -> list[int]:
    return sorted({abs(int(lit)) for clause in formula for lit in clause})


def canon_clause(*lits: int) -> tuple[int, ...] | None:
    values = sorted({int(x) for x in lits})
    if len(values) != len(lits):
        return None
    if any(-x in values for x in values):
        return None
    return tuple(values)


def clause_json(clause) -> list[int]:
    return [int(x) for x in clause]


def formula_json(formula) -> list[list[int]]:
    return [clause_json(clause) for clause in formula]


def is_bipolar_formula(formula) -> bool:
    signs: dict[int, set[int]] = {}
    for clause in formula:
        for raw in clause:
            lit = int(raw)
            signs.setdefault(abs(lit), set()).add(1 if lit > 0 else -1)
    return bool(signs) and all(s == {-1, 1} for s in signs.values())


def normalize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    report = dict(report)
    report["lane"] = "TRUMP_FALSIFICATION_RESEARCH"
    report["status"] = "HYPOTHESIS"
    report["proof_claim"] = False
    report["p_vs_np"] = "OPEN"
    report["sat_in_p"] = "NOT_PROVED"
    return report


def run_pairwise(request: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
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
    r47j = r50g23.r47j
    pivot = int(r50g23.PIVOT)
    skeletons = r50g23.clean_skeletons_from_frozen_r50g22()
    if len(skeletons) != 30:
        raise AssertionError(("R50G24_PAIRWISE_FROZEN_SKELETON_COUNT_DRIFT", len(skeletons)))

    trials = 0
    strong: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    first_rule_partition: Counter[str] = Counter()
    terminal_partition: Counter[str] = Counter()
    rejected = Counter()

    def evaluate(
        item: Dict[str, Any],
        audit: Dict[str, Any],
        clause1: tuple[int, ...],
        clause2: tuple[int, ...],
    ) -> None:
        nonlocal trials
        if trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
            return
        source = r50g23.canon(item["source"])
        if clause1 == clause2 or clause1 in source or clause2 in source:
            rejected["duplicate_or_existing_clause"] += 1
            return
        trials += 1
        mutated = r50g23.canon(list(source) + [clause1, clause2])
        candidate = r47j.macro_candidate_fixpoint(mutated, pivot)
        if candidate is None:
            rejected["r47j_candidate_missing"] += 1
            return
        replay = r47j.independent_fixpoint_macro_replay(mutated, candidate)
        if not replay.get("pass"):
            rejected["r47j_replay_fail"] += 1
            return

        forced = r50g23.canon(candidate["DP"]["transformed"])
        reduced = r33.simplify(forced)
        final_formula = r50g23.canon(reduced["final_formula"])
        labels = ["R33:" + str(rec.get("rule")) for rec in reduced.get("history", [])]
        first_label = labels[0] if labels else str(reduced.get("terminal"))
        base_first = str(audit["transition_labels"][0])
        first_changed = first_label != base_first
        terminal = str(reduced.get("terminal"))
        stalled_nonempty = terminal == "STALLED_STACK_LEAN_CORE" and bool(final_formula)
        bipolar = is_bipolar_formula(final_formula) if final_formula else False
        first_rule_partition[first_label] += 1
        terminal_partition[terminal] += 1

        row = {
            "spec": item["spec"],
            "source_hash": item["source_hash"],
            "base_first_transition": base_first,
            "base_debt": audit["first_transition_direct_blocking_debt"],
            "added_clauses": [clause_json(clause1), clause_json(clause2)],
            "mutated_source_CLV": list(r33.measure(mutated)),
            "forced_DP_CLV": list(r33.measure(forced)),
            "R33_terminal": terminal,
            "R33_transition_labels": labels,
            "R33_final_CLV": list(r33.measure(final_formula)),
            "first_transition_changed": first_changed,
            "nonempty_stalled_residual": stalled_nonempty,
            "bipolar_residual": bipolar,
            "r47j_replay_pass": True,
            "R47J_terminal": candidate["normalization"].get("terminal"),
            "R47J_round_count": candidate["normalization"].get("round_count"),
            "R47J_restart_count": candidate["normalization"].get("restart_count"),
        }

        if stalled_nonempty and bipolar:
            row["classification"] = "STRONG_R33_NONEMPTY_BIPOLAR_RESIDUAL_CANDIDATE"
            row["residual_cnf"] = formula_json(final_formula)
            strong.append(row)
            return

        if not first_changed:
            rejected["same_first_transition"] += 1
        elif not final_formula or terminal != "STALLED_STACK_LEAN_CORE":
            rejected["first_changed_but_solved_or_empty"] += 1
        elif not bipolar:
            rejected["nonbipolar_residual"] += 1

        if first_changed and len(near) < MAX_NEAR_MISSES:
            row["classification"] = "FIRST_TRANSITION_BROKEN_BUT_STRONG_GATE_NOT_MET"
            near.append(row)

    for item in skeletons:
        if trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
            break
        audit = r50g23.audit_one_skeleton(item)
        debt = audit["first_transition_direct_blocking_debt"]
        req_raw = debt.get("required_literal")
        if req_raw is None:
            rejected["no_required_literal_debt"] += 1
            continue
        req = int(req_raw)
        vars_ = [v for v in formula_variables(item["source"]) if v != abs(req)]

        first_clauses: list[tuple[int, ...]] = []
        second_clauses: list[tuple[int, ...]] = []
        for v in vars_:
            for partner in (v, -v):
                c1 = canon_clause(req, partner)
                if c1 is not None:
                    first_clauses.append(c1)
                for debt_sign in (req, -req):
                    c2 = canon_clause(debt_sign, partner)
                    if c2 is not None:
                        second_clauses.append(c2)
        first_clauses = sorted(set(first_clauses))
        second_clauses = sorted(set(second_clauses))

        # Minimal pairwise closure: C1 must pay the known first-transition debt.
        # C2 must still touch the same debt variable, but may use either polarity,
        # allowing complementary, crossed, and fork closures without new variables.
        for c1 in first_clauses:
            if trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                break
            for c2 in second_clauses:
                if trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                    break
                if c1 == c2:
                    continue
                # Require actual coordination: either the debt-variable polarity
                # flips in C2 or C2 contains the opposite sign of C1's partner.
                partner1 = next(l for l in c1 if abs(l) != abs(req))
                coordinated = (-req in c2) or (-partner1 in c2)
                if not coordinated:
                    continue
                evaluate(item, audit, c1, c2)

    mechanisms: list[dict[str, Any]] = []
    for idx, row in enumerate(strong[:5], 1):
        mechanisms.append({
            "name": f"R50G24_PAIRWISE_SURVIVOR_{idx}",
            "targets_transition": "PAIRWISE_FIRST_COLLAPSE_CLOSURE",
            "construction": (
                f"On frozen skeleton {row['spec']}, add exactly the two recorded clauses "
                f"{row['added_clauses']} before same-pivot R47J."
            ),
            "why_it_might_work": (
                "Repository replay changed/absorbed the local collapse and the first R33 pass "
                "stalled on a nonempty bipolar residual while independent R47J replay passed."
            ),
            "accidental_simplification_risk": (
                "Candidate only: full downstream R47J/RUP/restart behavior may still solve the formula; "
                "the receipt records the full R47J terminal for exactly this reason."
            ),
            "minimal_replay_test": (
                "Rebuild the exact frozen skeleton, add only the two recorded binary clauses, run R47J "
                "pivot 1 and its independent replay, then assert first-pass R33 terminal "
                "STALLED_STACK_LEAN_CORE, residual CNF nonempty, and both polarities for every residual variable."
            ),
            "receipt": row,
        })

    if strong:
        recommended = "R50G25_STRONG_PAIRWISE_SURVIVOR_FULL_FIXPOINT_AND_MINIMIZATION"
        answer = (
            f"Pairwise gate проверил {trials} координированных двухклаузных мутаций и нашёл "
            f"{len(strong)} кандидатов с непустым bipolar stalled-core после первого R33. "
            "Следующий удар — независимый полный fixpoint replay и delta-minimization каждого survivor."
        )
    else:
        dominant = first_rule_partition.most_common(1)[0][0] if first_rule_partition else "NONE"
        recommended = "R50G25_MINIMUM_STRUCTURAL_DEBT_AGAINST_DOMINANT_REPLACEMENT_ESCAPE"
        answer = (
            f"Pairwise gate проверил {trials} координированных двухклаузных мутаций и сильного "
            f"bipolar residual-core не нашёл. Доминирующий первый replacement escape: {dominant}. "
            "Следующий gate должен атаковать именно его, не расширяя frozen 30."
        )

    return normalize_report({
        "engine": ENGINE,
        "repo_observations": [
            {
                "claim": "Exactly the canonical frozen R50G23 selector/audit/R47J/R33 machinery was imported from the read-only TRUMP checkout.",
                "path": "experiments/janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt.py",
                "why_relevant": "The pairwise lane does not reimplement the frozen skeleton family or solver semantics."
            },
            {
                "claim": f"Pairwise bounded trials executed: {trials}; strong candidates: {len(strong)}.",
                "path": "runtime-only",
                "why_relevant": "Every trial adds exactly two binary clauses over already-existing variables to one of the same frozen 30 sources."
            }
        ],
        "candidate_mechanisms": mechanisms,
        "near_misses": near,
        "rejected_summary": dict(sorted(rejected.items())),
        "first_replacement_rule_partition": dict(first_rule_partition.most_common()),
        "R33_terminal_partition": dict(terminal_partition.most_common()),
        "deterministic_pair_trial_count": trials,
        "strong_candidate_count": len(strong),
        "strong_candidates": strong,
        "recommended_next_gate": recommended,
        "answer": answer,
        "finite_search_is_universal_proof": False,
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
    if "PAIRWISE_COUNTERPOLARITY" not in gate:
        raise ValueError(f"TRUMP_PAIRWISE_WRONG_GATE:{gate}")

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
    print(f"TRUMP_PAIRWISE_RESEARCH_RECEIPT={outbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
