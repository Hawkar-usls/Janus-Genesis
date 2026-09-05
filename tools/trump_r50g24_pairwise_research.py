#!/usr/bin/env python3
"""Deterministic R50G24 pairwise counterpolarity search for JANUS Habitat.

Scope is deliberately narrow: the exact frozen 30 R50G22/R50G23 skeletons,
same R47J pivot, existing variables only, two additive binary clauses. Finite
search output is evidence only and never a universal SAT/P-vs-NP claim.
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

MAX_PAIR_TRIALS = 12000
MAX_STRONG = 8
MAX_NEAR = 20


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canon_clause(*lits: int) -> tuple[int, ...] | None:
    vals = tuple(sorted(set(int(x) for x in lits)))
    if len(vals) < 2:
        return None
    s = set(vals)
    if any(-x in s for x in s):
        return None
    return vals


def variables(formula) -> list[int]:
    return sorted({abs(int(l)) for c in formula for l in c})


def bipolar(formula) -> bool:
    signs: dict[int, set[int]] = {}
    for clause in formula:
        for raw in clause:
            lit = int(raw)
            signs.setdefault(abs(lit), set()).add(1 if lit > 0 else -1)
    return bool(signs) and all(v == {-1, 1} for v in signs.values())


def load_modules(workspace: Path):
    exp = workspace / "experiments"
    if not exp.is_dir():
        raise RuntimeError(f"TRUMP_EXPERIMENTS_MISSING:{exp}")
    for p in (str(workspace), str(exp)):
        if p not in sys.path:
            sys.path.insert(0, p)
    r50g23 = importlib.import_module(
        "janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt"
    )
    return r50g23, r50g23.r33, r50g23.r47j


def replay(r50g23, r33, r47j, pivot: int, source, audit, added: list[tuple[int, ...]]):
    mutated = r50g23.canon(list(source) + list(added))
    candidate = r47j.macro_candidate_fixpoint(mutated, pivot)
    if candidate is None:
        return {"class": "R47J_CANDIDATE_MISSING"}
    independent = r47j.independent_fixpoint_macro_replay(mutated, candidate)
    if not independent.get("pass"):
        return {"class": "R47J_REPLAY_FAIL"}
    forced = r50g23.canon(candidate["DP"]["transformed"])
    reduced = r33.simplify(forced)
    final_formula = r50g23.canon(reduced["final_formula"])
    labels = ["R33:" + str(x.get("rule")) for x in reduced.get("history", [])]
    first = labels[0] if labels else str(reduced.get("terminal"))
    base_first = str(audit["transition_labels"][0])
    stalled = reduced.get("terminal") == "STALLED_STACK_LEAN_CORE" and bool(final_formula)
    is_bipolar = bipolar(final_formula) if final_formula else False
    return {
        "class": "STRONG" if stalled and is_bipolar else "NONSTRONG",
        "mutated_source_CLV": list(r33.measure(mutated)),
        "forced_DP_CLV": list(r33.measure(forced)),
        "terminal": reduced.get("terminal"),
        "labels": labels,
        "first": first,
        "base_first": base_first,
        "first_changed": first != base_first,
        "final_CLV": list(r33.measure(final_formula)),
        "final_formula": [[int(x) for x in c] for c in final_formula],
        "nonempty_stalled": stalled,
        "bipolar": is_bipolar,
        "r47j_replay_pass": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--habitat-root", required=True)
    args = ap.parse_args()

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    rid = re.sub(r"[^A-Za-z0-9._-]+", "_", str(request.get("request_id") or Path(args.request).stem))[:120]
    if request.get("status") != "QUEUED" or request.get("purpose") != "PARALLEL_TRUMP_CODE_RESEARCH":
        raise ValueError("PAIRWISE_REQUEST_NOT_QUEUED_CODE_RESEARCH")
    gate = str((request.get("frontier") or {}).get("gate") or "")
    if "PAIRWISE_COUNTERPOLARITY" not in gate and "PAIRWISE-COUNTERPOLARITY" not in rid:
        raise ValueError("PAIRWISE_GATE_NOT_REQUESTED")

    workspace = Path(args.workspace)
    habitat = Path(args.habitat_root)
    r50g23, r33, r47j = load_modules(workspace)
    pivot = int(r50g23.PIVOT)
    skeletons = r50g23.clean_skeletons_from_frozen_r50g22()
    if len(skeletons) != 30:
        raise AssertionError(("FROZEN_30_DRIFT", len(skeletons)))

    trials = 0
    strong: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    replacement_first = Counter()
    first_clause_changed = 0
    first_clause_same = 0
    pair_r47j_missing = 0
    pair_r47j_fail = 0

    for item in skeletons:
        if trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG:
            break
        source = r50g23.canon(item["source"])
        audit = r50g23.audit_one_skeleton(item)
        debt = audit["first_transition_direct_blocking_debt"]
        req = debt.get("required_literal")
        if req is None:
            continue
        req = int(req)
        vars_ = variables(source)
        source_set = set(source)

        first_pool: list[tuple[int, ...]] = []
        for v in vars_:
            if v == abs(req):
                continue
            for signed in (v, -v):
                c = canon_clause(req, signed)
                if c and c not in source_set:
                    first_pool.append(c)
        first_pool = sorted(set(first_pool))

        # Pairwise search is conditioned on C1 genuinely changing the original
        # first transition, so the 2154 single-clause negative is not repeated as
        # the main search object.
        useful_first: list[tuple[int, ...]] = []
        for c1 in first_pool:
            r1 = replay(r50g23, r33, r47j, pivot, source, audit, [c1])
            if r1.get("class") in {"R47J_CANDIDATE_MISSING", "R47J_REPLAY_FAIL"}:
                continue
            if r1.get("first_changed"):
                first_clause_changed += 1
                useful_first.append(c1)
            else:
                first_clause_same += 1

        all_signed = [s * v for v in vars_ for s in (1, -1)]
        second_pool: list[tuple[int, ...]] = []
        for i, a in enumerate(all_signed):
            for b in all_signed[i + 1:]:
                if abs(a) == abs(b):
                    continue
                c = canon_clause(a, b)
                if c and c not in source_set:
                    second_pool.append(c)
        second_pool = sorted(set(second_pool))

        for c1 in useful_first:
            if trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG:
                break
            for c2 in second_pool:
                if trials >= MAX_PAIR_TRIALS or len(strong) >= MAX_STRONG:
                    break
                if c2 == c1:
                    continue
                trials += 1
                rr = replay(r50g23, r33, r47j, pivot, source, audit, [c1, c2])
                if rr.get("class") == "R47J_CANDIDATE_MISSING":
                    pair_r47j_missing += 1
                    continue
                if rr.get("class") == "R47J_REPLAY_FAIL":
                    pair_r47j_fail += 1
                    continue
                if rr.get("class") == "STRONG":
                    row = {
                        "spec": item["spec"],
                        "source_hash": item["source_hash"],
                        "base_debt": debt,
                        "added_clauses": [list(c1), list(c2)],
                        **rr,
                    }
                    strong.append(row)
                    continue
                replacement_first[str(rr.get("first"))] += 1
                if rr.get("first_changed") and len(near) < MAX_NEAR:
                    near.append({
                        "spec": item["spec"],
                        "source_hash": item["source_hash"],
                        "base_debt": debt,
                        "added_clauses": [list(c1), list(c2)],
                        **rr,
                    })

    if strong:
        next_gate = "R50G24_PAIRWISE_SURVIVOR_INDEPENDENT_REPLAY_AND_MINIMIZATION"
        answer = (
            f"Pairwise engine checked {trials} bounded clause-pairs and found {len(strong)} strong candidate(s): "
            "same-pivot R47J replay passes and R33 leaves a nonempty bipolar stalled core. Independent replay/minimization is now required."
        )
    else:
        dominant = replacement_first.most_common(1)[0][0] if replacement_first else "UNRESOLVED"
        next_gate = "R50G25_MINIMUM_STRUCTURAL_DEBT_AGAINST_DOMINANT_REPLACEMENT_ESCAPE"
        answer = (
            f"Pairwise engine checked {trials} bounded clause-pairs and found no strong survivor. "
            f"Dominant observed replacement first-rule: {dominant}. This is finite negative evidence only."
        )

    report = {
        "lane": "TRUMP_FALSIFICATION_RESEARCH",
        "status": "HYPOTHESIS",
        "engine": "DETERMINISTIC_R50G24_PAIRWISE_COUNTERPOLARITY_LAB",
        "proof_claim": False,
        "p_vs_np": "OPEN",
        "sat_in_p": "NOT_PROVED",
        "frozen_skeleton_count": len(skeletons),
        "pair_trial_count": trials,
        "single_clause_changed_first_transition_count": first_clause_changed,
        "single_clause_same_first_transition_count": first_clause_same,
        "pair_r47j_candidate_missing": pair_r47j_missing,
        "pair_r47j_replay_fail": pair_r47j_fail,
        "strong_candidate_count": len(strong),
        "strong_candidates": strong,
        "near_misses": near,
        "replacement_first_rule_partition": dict(replacement_first.most_common()),
        "candidate_mechanisms": [],
        "repo_observations": [{
            "claim": "Pairwise search used only the exact frozen 30 R50G23-selected sources, existing variables, two additive binary clauses, and unchanged R47J pivot.",
            "path": "experiments/janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt.py",
            "why_relevant": "Prevents family expansion and preserves the previous gate's machinery."
        }],
        "rejected_ideas": [{
            "idea": "Count changing the first transition as PASS.",
            "reason": "PASS requires a nonempty bipolar STALLED_STACK_LEAN_CORE after replay; replacement collapse routes remain failures."
        }],
        "recommended_next_gate": next_gate,
        "answer": answer,
    }
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_2",
        "lane_id": "JANUS_TRUMP_GIT_RESEARCH_LANE",
        "request_id": rid,
        "processed_at_utc": now_utc(),
        "source_repo": request.get("source_repo"),
        "source_branch": request.get("source_branch"),
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "engine": report["engine"],
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

    outbox = habitat / "outbox" / "trump" / f"{rid}.json"
    memory = habitat / "memory" / "trump" / f"{now_utc().replace(':', '-')}_{rid}.json"
    for path in (outbox, memory):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"TRUMP_PAIRWISE_RECEIPT={outbox}")
    print(f"TRUMP_PAIR_TRIALS={trials} STRONG={len(strong)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
