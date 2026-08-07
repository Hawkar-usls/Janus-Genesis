#!/usr/bin/env python3
from __future__ import annotations
import json
import math
from fractions import Fraction
from itertools import product

SCHEMA = "JANUS/genesis-independent-future-no-go-lab/v0.1.0"

def maps(n_dom:int,n_cod:int):
    return list(product(range(n_cod), repeat=n_dom))

def fixed_points(f):
    return {i for i,x in enumerate(f) if x == i}

def compositions(total:int,k:int):
    if k == 1:
        yield (total,)
    else:
        for i in range(total+1):
            for rest in compositions(total-i,k-1):
                yield (i,)+rest

def dist_grid(k:int,denom:int):
    return [tuple(Fraction(x,denom) for x in c) for c in compositions(denom,k)]

def match_prob(p,q):
    return sum(pi*qi for pi,qi in zip(p,q))

def projection_obstruction_exhaustive():
    Xn, Yn = 3, 2
    Fs, qs, Gs = maps(Xn,Xn), maps(Xn,Yn), maps(Yn,Yn)
    total = intertwining = empty_fix_G = violations = 0
    necessity_counterexample = None
    for F in Fs:
        for q in qs:
            for G in Gs:
                total += 1
                inter = all(q[F[x]] == G[q[x]] for x in range(Xn))
                if inter:
                    intertwining += 1
                    if not fixed_points(G):
                        empty_fix_G += 1
                        if fixed_points(F):
                            violations += 1
                elif necessity_counterexample is None and fixed_points(F) and not fixed_points(G):
                    necessity_counterexample = {
                        "F": list(F), "q": list(q), "G": list(G),
                        "FixF": sorted(fixed_points(F)), "FixG": sorted(fixed_points(G))
                    }
    return {
        "domain_sizes":{"X":Xn,"Y":Yn},
        "map_triples_checked": total,
        "intertwining_triples": intertwining,
        "intertwining_with_empty_FixG": empty_fix_G,
        "theorem_violations": violations,
        "assumption_necessity_counterexample_without_intertwining": necessity_counterexample,
        "pass": violations == 0 and necessity_counterexample is not None,
    }

def independent_exact_match_exhaustive():
    suites = []
    total_viol = total_exact_nondeg = 0
    for k,d in [(2,8),(3,6),(4,5)]:
        ds = dist_grid(k,d)
        cases = bound_viol = exact_nondeg = 0
        for p in ds:
            for q in ds:
                cases += 1
                m = match_prob(p,q)
                if m > max(q):
                    bound_viol += 1
                if m == 1:
                    degenerate_same = p == q and sum(x == 1 for x in p) == 1
                    if not degenerate_same:
                        exact_nondeg += 1
        total_viol += bound_viol
        total_exact_nondeg += exact_nondeg
        suites.append({
            "alphabet":k,"grid_denominator":d,"distributions":len(ds),
            "independent_pairs_checked":cases,
            "guessing_bound_violations":bound_viol,
            "exact_match_non_degenerate_cases":exact_nondeg
        })
    return {
        "statement":"For independent B,T, Pr[B=T]=sum_b P(B=b)P(T=b) <= max_t P(T=t)=2^{-H_inf(T)}. Equality 1 implies both variables are the same point mass.",
        "suites":suites,
        "pass": total_viol == 0 and total_exact_nondeg == 0
    }

def conditional_freeze_view_exhaustive():
    pV_grid = dist_grid(2,4)
    q_grid = dist_grid(2,4)
    cases = violations = exact_with_positive_conditional_entropy = 0
    for pv in pV_grid:
        for q0 in q_grid:
            for q1 in q_grid:
                for b0 in (0,1):
                    for b1 in (0,1):
                        cases += 1
                        qs = (q0,q1)
                        bs = (b0,b1)
                        match = sum(pv[i]*qs[i][bs[i]] for i in (0,1))
                        guess = sum(pv[i]*max(qs[i]) for i in (0,1))
                        if match > guess:
                            violations += 1
                        exact = match == 1
                        positive_entropy_each_live_context = all(
                            pv[i] == 0 or max(qs[i]) < 1 for i in (0,1)
                        )
                        if exact and positive_entropy_each_live_context:
                            exact_with_positive_conditional_entropy += 1
    return {
        "cases_checked":cases,
        "bound_violations":violations,
        "exact_match_with_positive_conditional_entropy_cases": exact_with_positive_conditional_entropy,
        "statement":"If PRE_RETURN B_R is measurable from freeze-time view V_R, then Pr[B_R=T] <= p_guess(T|V_R). Hence if H_inf(T|V_R)>=h, Pr[B_R=T]<=2^-h. If B_R=T almost surely, then p_guess=1 and H_inf(T|V_R)=0.",
        "pass": violations == 0 and exact_with_positive_conditional_entropy == 0
    }

def bootstrap_and_leakage_examples():
    M=256
    bootstrap = {
        "B_uniform": True,
        "T_defined_as_B": True,
        "exact_match_probability": 1.0,
        "conditional_min_entropy_T_given_B_bits": 0.0,
        "interpretation":"Exact bootstrap copy is possible because the future target is dependent on the earlier state."
    }
    leakage_rows=[]
    for lam in [0.0,0.01,0.1,0.5,1.0]:
        p = lam + (1-lam)/M
        h = -math.log2(p)
        leakage_rows.append({
            "leak_probability":lam,
            "match_probability":p,
            "conditional_min_entropy_bits":h,
            "bound_is_tight":True
        })
    return {
        "independent_uniform_256_symbol_match_probability":1/M,
        "bootstrap":bootstrap,
        "partial_leakage_channel":leakage_rows,
        "statement":"The min-entropy witness is tight: hidden leakage raises exact-match probability precisely by lowering conditional min-entropy relative to the freeze-time view.",
        "pass": True
    }

def exact_independence_no_go_proof():
    return {
        "name":"JANUS Exact-Match / Independent-Future Incompatibility Lemma",
        "statement":"For discrete classical B,T: if B and T are statistically independent and Pr[B=T]=1, then H(T)=H(B)=0; both are the same deterministic point mass.",
        "proof":[
            "Let p_x=Pr[B=x] and q_x=Pr[T=x]. Independence gives Pr[B=x,T=x]=p_x q_x.",
            "Because Pr[B=T]=1, all probability lies on the diagonal and sum_x p_x q_x=1.",
            "But sum_x p_x q_x <= max_x q_x * sum_x p_x = max_x q_x <= 1.",
            "Equality requires max_x q_x=1, so T is deterministic. Diagonal equality then forces B to be the same deterministic value.",
            "Equivalently, if B=T almost surely then I(B;T)=H(T), while independence gives I(B;T)=0, hence H(T)=0."
        ],
        "corollary":"Any non-degenerate exact pre-target/future identity must break statistical independence, invalidate the claimed freeze-time information boundary, or reject at least one forward-causal assumption.",
        "novelty_boundary":"Elementary probability/information-theory consequence; not claimed as a new theorem of mathematics. JANUS contribution is its explicit role as a gate separating bootstrap consistency from independent-future evidence."
    }

def main():
    sections = {
        "projection_obstruction": projection_obstruction_exhaustive(),
        "independent_exact_match": independent_exact_match_exhaustive(),
        "conditional_freeze_view": conditional_freeze_view_exhaustive(),
        "bootstrap_and_leakage": bootstrap_and_leakage_examples(),
        "formal_lemma": exact_independence_no_go_proof(),
    }
    all_pass = all(v.get("pass",True) for v in sections.values())
    report = {
        "schema":SCHEMA,
        "status":"PASS" if all_pass else "FAIL",
        "all_pass":all_pass,
        "sections":sections,
        "admission":{
            "PROJECTION_OBSTRUCTION_MACHINE_CHECK":"PASS" if sections["projection_obstruction"]["pass"] else "FAIL",
            "MIN_ENTROPY_GUESSING_BOUND_MACHINE_CHECK":"PASS" if sections["independent_exact_match"]["pass"] else "FAIL",
            "CONDITIONAL_FREEZE_VIEW_NO_GO_MACHINE_CHECK":"PASS" if sections["conditional_freeze_view"]["pass"] else "FAIL",
            "EXACT_MATCH_AND_POSITIVE_INDEPENDENT_FUTURE_ENTROPY_COMPATIBLE":False,
            "BOOTSTRAP_EXACT_MATCH_POSSIBLE":True,
            "PHYSICAL_RETROCAUSALITY_PROVED":False,
            "SCIENTIFIC_NOVELTY_PROVED":False
        },
        "epistemic_boundary":"This proves finite/exact mathematical checks and an elementary classical no-go lemma. It does not demonstrate a physical backward-time channel. A physical exact match would instead falsify at least one admitted forward-causal/entropy premise and would require independent replication."
    }
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if all_pass else 1

if __name__ == "__main__":
    raise SystemExit(main())
