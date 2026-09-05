#!/usr/bin/env python3
"""R50G27: minimum non-additive single-literal polarity-flip lane.

Starts from the exact sealed R50G24 pair-state space after R50G26 exhausted
all declared width-3 additive debt supports. The only allowed mutation is one
sign flip of one existing literal occurrence in one existing clause.

Firewalls:
- frozen 30 sources only;
- exact 1774 parent pair paths and exact 887/786/94/7 partition;
- exact 1424 unique pair formulas and exact unique-rule partition;
- same R47J pivot 1;
- no clause addition/deletion, no new variables, no width change;
- reject tautologies and canonical clause-count collapse;
- finite search != theorem; P_VS_NP remains OPEN.
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

LANE_ID = "JANUS_TRUMP_R50G27_SINGLE_POLARITY_FLIP_LANE"
ENGINE = "DETERMINISTIC_R50G27_MINIMUM_NONADDITIVE_SINGLE_LITERAL_POLARITY_FLIP"
EXPECTED_PARENT_PAIR_PATHS = 1774
EXPECTED_PARENT_PARTITION = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 786,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 887,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 7,
}
EXPECTED_UNIQUE_PAIR_STATES = 1424
EXPECTED_UNIQUE_RULE_PARTITION = {
    "R33:BOUNDED_VARIABLE_ELIMINATION": 589,
    "R33:PURE_LITERAL_AUTARKY": 94,
    "R33:BLOCKED_CLAUSE_ELIMINATION": 736,
    "R33:UNIT_PROPAGATION_WITH_RECONSTRUCTION_TRACE": 5,
}
MAX_WITNESSES = 20
MAX_NEAR = 24


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(report: dict[str, Any]) -> dict[str, Any]:
    out = dict(report)
    out.update({"lane":"TRUMP_FALSIFICATION_RESEARCH","status":"HYPOTHESIS","proof_claim":False,"p_vs_np":"OPEN","sat_in_p":"NOT_PROVED"})
    return out


def first_pass_strong(state: dict[str, Any]) -> bool:
    if not state.get("ok"):
        return False
    f = state["final"]
    return state["reduced"].get("terminal") == "STALLED_STACK_LEAN_CORE" and bool(f) and all(len(c)>0 for c in f) and r50g25.bipolar(f)


def full_unresolved(state: dict[str, Any]) -> bool:
    if not state.get("ok"):
        return False
    f = state["full_final"]
    return state["candidate"]["normalization"].get("terminal") is None and bool(f) and all(len(c)>0 for c in f)


def build_unique_pair_states(r50g23):
    skeletons = r50g23.clean_skeletons_from_frozen_r50g22()
    if len(skeletons) != 30:
        raise AssertionError(("R50G27_FROZEN_COUNT_DRIFT", len(skeletons)))
    pair_paths = 0
    partition: Counter[str] = Counter()
    unique: dict[str, dict[str, Any]] = {}
    replay_fail = Counter()

    for item in skeletons:
        source = r50g23.canon(item["source"])
        vars_ = r50g25.formula_variables(source)
        base = r50g23.audit_one_skeleton(item)
        base_label = str(base["transition_labels"][0])
        c1s = r50g25.binary_clauses(r50g25.required_literals(base["first_transition_direct_blocking_debt"]), vars_)
        for c1 in c1s:
            if c1 in source:
                continue
            s1 = r50g25.replay_state(r50g23, source, [c1])
            if not s1["ok"]:
                replay_fail["FIRST:"+str(s1["reason"])] += 1
                continue
            if s1["first_label"] == base_label:
                continue
            req2 = r50g25.required_literals(s1.get("debt"))
            if not req2:
                continue
            for c2 in r50g25.binary_clauses(req2, vars_):
                if c2 == c1 or c2 in source:
                    continue
                pair_paths += 1
                s2 = r50g25.replay_state(r50g23, source, [c1,c2])
                if not s2["ok"]:
                    replay_fail["PAIR:"+str(s2["reason"])] += 1
                    continue
                partition[s2["first_label"]] += 1
                formula = r50g23.canon(s2["mutated"])
                h = r50g23.r50g4.fhash(formula)
                rep = {"spec":item["spec"],"source_hash":item["source_hash"],"first_clause":list(c1),"second_clause":list(c2)}
                if h not in unique:
                    unique[h] = {"pair_hash":h,"formula":formula,"first_label":s2["first_label"],"multiplicity":1,"representative":rep}
                else:
                    if unique[h]["first_label"] != s2["first_label"]:
                        raise AssertionError(("R50G27_HASH_LABEL_DRIFT",h))
                    unique[h]["multiplicity"] += 1

    if replay_fail:
        raise AssertionError(("R50G27_PARENT_REPLAY_DRIFT",dict(replay_fail)))
    if pair_paths != EXPECTED_PARENT_PAIR_PATHS:
        raise AssertionError(("R50G27_PARENT_COUNT_DRIFT",pair_paths,EXPECTED_PARENT_PAIR_PATHS))
    if dict(partition) != EXPECTED_PARENT_PARTITION:
        raise AssertionError(("R50G27_PARENT_PARTITION_DRIFT",dict(partition),EXPECTED_PARENT_PARTITION))
    if len(unique) != EXPECTED_UNIQUE_PAIR_STATES:
        raise AssertionError(("R50G27_UNIQUE_COUNT_DRIFT",len(unique),EXPECTED_UNIQUE_PAIR_STATES))
    up = Counter(v["first_label"] for v in unique.values())
    if dict(up) != EXPECTED_UNIQUE_RULE_PARTITION:
        raise AssertionError(("R50G27_UNIQUE_PARTITION_DRIFT",dict(up),EXPECTED_UNIQUE_RULE_PARTITION))
    return pair_paths, partition, unique


def flip_candidates(r50g23, formula):
    base = list(r50g23.canon(formula))
    base_count = len(base)
    for ci, clause in enumerate(base):
        for li, lit in enumerate(clause):
            new_clause = list(clause)
            new_clause[li] = -int(lit)
            if len(set(new_clause)) != len(new_clause):
                continue
            s = set(new_clause)
            if any(-x in s for x in s):
                continue
            new_clause_t = tuple(sorted(new_clause))
            raw = list(base)
            raw[ci] = new_clause_t
            mutated = r50g23.canon(raw)
            if len(mutated) != base_count:
                continue
            if mutated == tuple(base):
                continue
            yield ci, int(lit), -int(lit), mutated


def run(request: dict[str, Any], workspace: Path) -> dict[str, Any]:
    exp = workspace / "experiments"
    for p in (str(workspace), str(exp)):
        if p not in sys.path:
            sys.path.insert(0,p)
    r50g23 = importlib.import_module("janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt")
    r33 = r50g23.r33
    pair_paths, parent_partition, unique = build_unique_pair_states(r50g23)

    raw_flip_paths = 0
    unique_mutants: dict[str, dict[str, Any]] = {}
    for pair_hash,row in sorted(unique.items()):
        for ci, old_lit, new_lit, mutated in flip_candidates(r50g23,row["formula"]):
            raw_flip_paths += 1
            mh = r50g23.r50g4.fhash(mutated)
            rep = {"pair_hash":pair_hash,"pair_multiplicity":row["multiplicity"],"pair_first_transition":row["first_label"],"representative_parent_path":row["representative"],"clause_index":ci,"old_literal":old_lit,"new_literal":new_lit}
            if mh not in unique_mutants:
                unique_mutants[mh] = {"formula":mutated,"multiplicity":1,"representative":rep}
            else:
                unique_mutants[mh]["multiplicity"] += 1

    terminal_partition = Counter()
    first_partition = Counter()
    door_closed = []
    full = []
    first_pass = []
    near = []
    replay_fail = Counter()

    for mh,row in sorted(unique_mutants.items()):
        st = r50g25.replay_state(r50g23,row["formula"],[])
        rep = {**row["representative"],"mutant_hash":mh,"mutant_path_multiplicity":row["multiplicity"]}
        if not st["ok"]:
            if st["reason"] == "R47J_CANDIDATE_MISSING":
                if len(door_closed)<MAX_WITNESSES:
                    door_closed.append({**rep,"classification":"SAME_PIVOT_R47J_DOOR_CLOSED_SINGLE_POLARITY_FLIP"})
                continue
            replay_fail[str(st["reason"])] += 1
            continue
        terminal = str(st["reduced"].get("terminal"))
        first_partition[st["first_label"]] += 1
        terminal_partition[terminal] += 1
        record = {**rep,"width_preserved":True,"clause_count_preserved":True,"variable_universe_preserved":True,"R33_first_transition":st["first_label"],"R33_terminal":terminal,"R33_final_CLV":list(r33.measure(st["final"])),"R33_final_formula":r50g25.json_formula(st["final"]),"full_R47J_terminal":st["candidate"]["normalization"].get("terminal"),"full_R47J_final_CLV":list(r33.measure(st["full_final"])),"full_R47J_final_formula":r50g25.json_formula(st["full_final"]),"r47j_replay_pass":True}
        if full_unresolved(st):
            if len(full)<MAX_WITNESSES:
                full.append({**record,"classification":"FULL_R47J_UNRESOLVED_SINGLE_POLARITY_FLIP_SURVIVOR"})
        elif first_pass_strong(st):
            if len(first_pass)<MAX_WITNESSES:
                first_pass.append({**record,"classification":"FIRST_PASS_BIPOLAR_STALLED_SINGLE_POLARITY_FLIP"})
        elif len(near)<MAX_NEAR and st["first_label"] != rep["pair_first_transition"]:
            near.append({**record,"classification":"SINGLE_POLARITY_FLIP_CHANGED_ESCAPE_BUT_SOLVED"})

    if replay_fail:
        raise AssertionError(("R50G27_REPLAY_FAILURE",dict(replay_fail)))

    if door_closed:
        nxt="R50G28_SINGLE_FLIP_DOOR_CLOSED_ALTERNATE_PIVOT_AUDIT"
    elif full:
        nxt="R50G28_SINGLE_FLIP_SURVIVOR_INDEPENDENT_REPLAY_AND_DELTA_MINIMIZATION"
    elif first_pass:
        nxt="R50G28_SINGLE_FLIP_FIRST_PASS_CORE_DOWNSTREAM_ESCAPE_AUDIT"
    else:
        nxt="R50G28_SINGLE_POLARITY_FLIP_FINITE_NEGATIVE__SINGLE_LITERAL_VARIABLE_REWIRE"

    answer=(f"R50G27 reproduced the sealed 1774-path / 1424-unique pair-state parent and exhaustively tested {raw_flip_paths} valid one-occurrence polarity-flip paths, compressed to {len(unique_mutants)} unique mutant formulas. Recorded door-closed={len(door_closed)}, full-unresolved={len(full)}, first-pass-stalled={len(first_pass)}. Next gate: {nxt}.")
    return normalize({"engine":ENGINE,"parent_seal":{"pair_path_count":pair_paths,"pair_partition":dict(parent_partition),"unique_pair_state_count":len(unique),"unique_pair_rule_partition":dict(Counter(v["first_label"] for v in unique.values())),"seal_replay_pass":True},"raw_valid_flip_path_count":raw_flip_paths,"unique_mutant_formula_count":len(unique_mutants),"compression_ratio_flip_paths_per_unique_mutant":float(raw_flip_paths)/len(unique_mutants) if unique_mutants else None,"mutant_first_transition_partition":dict(first_partition),"mutant_R33_terminal_partition":dict(terminal_partition),"same_pivot_door_closed_count_recorded":len(door_closed),"same_pivot_door_closed_candidates":door_closed,"full_R47J_unresolved_survivor_count_recorded":len(full),"full_R47J_unresolved_survivors":full,"first_pass_strong_count_recorded":len(first_pass),"first_pass_strong_candidates":first_pass,"near_misses":near,"search_exhaustive_within_declared_single_flip_grammar":True,"recommended_next_gate":nxt,"answer":answer,"scope_firewall":{"family_expanded":False,"clauses_added":False,"clauses_deleted":False,"new_variables_added":False,"clause_width_changed":False,"r47j_pivot_changed":False,"mutation":"ONE_EXISTING_LITERAL_OCCURRENCE_SIGN_FLIP","finite_search_is_universal_proof":False}})


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--request",required=True); ap.add_argument("--workspace",required=True); ap.add_argument("--habitat-root",required=True); args=ap.parse_args()
    request_path=Path(args.request); request=json.loads(request_path.read_text(encoding="utf-8")); rid=re.sub(r"[^A-Za-z0-9._-]+","_",str(request.get("request_id") or request_path.stem))[:120]
    if request.get("status")!="QUEUED" or request.get("purpose")!="PARALLEL_TRUMP_CODE_RESEARCH": raise ValueError("R50G27_BAD_REQUEST")
    gate=str((request.get("frontier") or {}).get("gate") or rid)
    if "R50G27_MINIMUM_NONADDITIVE_SINGLE_LITERAL_POLARITY_FLIP" not in gate: raise ValueError(f"R50G27_WRONG_GATE:{gate}")
    report=run(request,Path(args.workspace))
    receipt={"schema":"janus.genesis.trump_research_receipt.v1_5","lane_id":LANE_ID,"request_id":rid,"processed_at_utc":utc_now(),"source_repo":request.get("source_repo"),"source_branch":request.get("source_branch"),"source_commit":os.environ.get("TRUMP_SOURCE_SHA"),"github_run_id":os.environ.get("GITHUB_RUN_ID"),"engine":ENGINE,"authority":"RESEARCH_HYPOTHESIS_ONLY","truth_boundary":{"model_output_is_proof":False,"model_output_is_independent_confirmation":False,"deterministic_finite_search_is_universal_proof":False,"p_vs_np":"OPEN","sat_in_p":"NOT_PROVED"},"report":report}
    habitat=Path(args.habitat_root); out=habitat/"outbox"/"trump"/f"{rid}.json"; mem=habitat/"memory"/"trump"/f"{utc_now().replace(':','-')}_{rid}.json"; write_json(out,receipt); write_json(mem,receipt); print(f"TRUMP_R50G27_RECEIPT={out}"); return 0

if __name__=="__main__": raise SystemExit(main())
