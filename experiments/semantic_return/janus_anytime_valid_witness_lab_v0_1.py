#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import random
from fractions import Fraction
from itertools import product
from pathlib import Path
from typing import Dict, Tuple

SCHEMA = "JANUS/genesis-anytime-valid-witness-lab/v0.1.0"


def product_factor(x: int, a: Fraction, lam: Fraction) -> Fraction:
    """One-step nonnegative betting factor.
    Valid when E[X_i | F_{i-1}] <= a and lambda is F_{i-1}-measurable in [0,1].
    """
    if not (0 < a <= 1):
        raise ValueError("a must lie in (0,1]")
    if not (0 <= lam <= 1):
        raise ValueError("lambda must lie in [0,1]")
    if x not in (0, 1):
        raise ValueError("x must be binary")
    return (1 - lam) + lam * Fraction(x, 1) / a


def all_histories(n: int):
    out = []
    for d in range(n):
        out.extend(product((0, 1), repeat=d))
    return out


def eval_lambda_policy(policy: Dict[Tuple[int, ...], Fraction], *, n: int,
                       q: Fraction, a: Fraction, threshold: Fraction):
    """Exact iid-Bernoulli path evaluation for a predictable lambda policy."""
    expected_final = Fraction(0)
    crossing_probability = Fraction(0)
    for xs in product((0, 1), repeat=n):
        prob = Fraction(1)
        wealth = Fraction(1)
        crossed = False
        history: Tuple[int, ...] = ()
        for x in xs:
            lam = policy[history]
            wealth *= product_factor(x, a, lam)
            crossed = crossed or (wealth >= threshold)
            prob *= q if x else (1 - q)
            history = history + (x,)
        expected_final += prob * wealth
        if crossed:
            crossing_probability += prob
    return expected_final, crossing_probability


def exhaustive_lambda_policies(*, n: int, q: Fraction, a: Fraction,
                               alpha: Fraction):
    histories = all_histories(n)
    lambda_grid = (Fraction(0), Fraction(1, 2), Fraction(1))
    max_expectation = Fraction(0)
    max_crossing = Fraction(0)
    expectation_violations = 0
    ville_violations = 0
    policies = 0
    for vals in product(lambda_grid, repeat=len(histories)):
        policies += 1
        policy = dict(zip(histories, vals))
        exp_final, cross = eval_lambda_policy(
            policy, n=n, q=q, a=a, threshold=1 / alpha
        )
        max_expectation = max(max_expectation, exp_final)
        max_crossing = max(max_crossing, cross)
        expectation_violations += exp_final > 1
        ville_violations += cross > alpha
    return {
        "n": n,
        "q": float(q),
        "historywise_hit_cap_a": float(a),
        "alpha": float(alpha),
        "threshold_1_over_alpha": float(1 / alpha),
        "policies_checked": policies,
        "max_expected_final_e": float(max_expectation),
        "max_crossing_probability": float(max_crossing),
        "expectation_violations": expectation_violations,
        "ville_violations": ville_violations,
        "pass": expectation_violations == 0 and ville_violations == 0,
    }


def marginal_only_counterexample():
    """T1 fair, T2=T1.
    B1=0. After T1 is revealed, choose B2=T1 before T2.
    Both T1,T2 are marginally fair, but at trial 2 the complete history makes
    T2 deterministic. Using the false marginal cap a2=1/2 breaks the e-process.
    """
    wrong_a = Fraction(1, 2)
    alpha = Fraction(1, 4)
    threshold = 1 / alpha
    outcomes = []
    expectation_wrong = Fraction(0)
    crossing_wrong = Fraction(0)
    expectation_correct = Fraction(0)
    crossing_correct = Fraction(0)

    for t1 in (0, 1):
        prob = Fraction(1, 2)
        t2 = t1
        x1 = int(t1 == 0)
        x2 = 1  # B2 is chosen as revealed T1, and T2=T1.

        # Wrong analysis: uses marginal 1/2 at both steps and all-in lambda=1.
        e_wrong = Fraction(1)
        crossed_wrong = False
        for x, a in ((x1, wrong_a), (x2, wrong_a)):
            e_wrong *= product_factor(x, a, Fraction(1))
            crossed_wrong = crossed_wrong or e_wrong >= threshold
        expectation_wrong += prob * e_wrong
        crossing_wrong += prob * int(crossed_wrong)

        # Correct history-wise cap: a1=1/2, but a2=1.
        e_correct = Fraction(1)
        crossed_correct = False
        for x, a in ((x1, Fraction(1, 2)), (x2, Fraction(1))):
            e_correct *= product_factor(x, a, Fraction(1))
            crossed_correct = crossed_correct or e_correct >= threshold
        expectation_correct += prob * e_correct
        crossing_correct += prob * int(crossed_correct)

        outcomes.append({
            "T1": t1,
            "T2": t2,
            "X1": x1,
            "X2": x2,
            "wrong_final_e": float(e_wrong),
            "correct_final_e": float(e_correct),
        })

    return {
        "construction": "T1 fair; T2=T1; B1=0; after T1 reveal choose B2=T1 before T2",
        "each_target_marginally_fair": True,
        "wrong_marginal_cap": 0.5,
        "true_historywise_cap_trial2": 1.0,
        "alpha": float(alpha),
        "threshold": float(threshold),
        "wrong_expected_final_e": float(expectation_wrong),
        "wrong_crossing_probability": float(crossing_wrong),
        "wrong_ville_bound": float(alpha),
        "wrong_ville_is_violated": crossing_wrong > alpha,
        "correct_expected_final_e": float(expectation_correct),
        "correct_crossing_probability": float(crossing_correct),
        "correct_ville_respected": crossing_correct <= alpha and expectation_correct <= 1,
        "outcomes": outcomes,
    }


def budgeted_spike_process_one_hit(*, bits: int, n: int):
    """Equal capital allocation w_i=1/n.
    E_n = 1 + sum_i w_i (X_i/a - 1), a=2^-bits.
    At the end, exactly one hit gives E_N = 1/(n*a) = 2^bits/n.
    """
    a = 2.0 ** (-bits)
    e_one_hit = (2.0 ** bits) / n
    raw_inverse_e = 1.0 / e_one_hit
    raw_union = n * a
    return {
        "bits": bits,
        "max_trials": n,
        "equal_weight_per_trial": 1.0 / n,
        "point_hit_cap": a,
        "end_e_value_if_exactly_one_hit": e_one_hit,
        "raw_inverse_e": raw_inverse_e,
        "ville_anytime_p_upper_if_hit": min(1.0, raw_inverse_e),
        "raw_union_bound": raw_union,
        "same_as_union_bound": min(1.0, raw_union),
    }


def random_historywise_tree_checks(samples: int = 5000, seed: int = 1138):
    """Random binary trees with history-dependent hit probabilities <= a(h)
    and history-dependent predictable lambda. Exact path sums verify E[M_N]<=1.
    Threshold crossing is compared to Ville at alpha=0.2.
    """
    rng = random.Random(seed)
    n = 5
    alpha = Fraction(1, 5)
    threshold = 1 / alpha
    exp_violations = 0
    ville_violations = 0
    max_exp = 0.0
    max_cross = 0.0

    for _ in range(samples):
        # For each pre-outcome history, pick a cap a in {1/4,1/2,3/4},
        # an actual q <= a, and lambda in {0,1/4,1/2,3/4,1}.
        nodes = {}
        for h in all_histories(n):
            a = rng.choice((Fraction(1,4), Fraction(1,2), Fraction(3,4)))
            q_grid = [Fraction(k, 4) for k in range(0, int(a*4)+1)]
            q = rng.choice(q_grid)
            lam = rng.choice((Fraction(0), Fraction(1,4), Fraction(1,2),
                              Fraction(3,4), Fraction(1)))
            nodes[h] = (q, a, lam)

        expected = Fraction(0)
        cross = Fraction(0)
        for xs in product((0,1), repeat=n):
            prob = Fraction(1)
            wealth = Fraction(1)
            crossed = False
            h: Tuple[int, ...] = ()
            for x in xs:
                q,a,lam = nodes[h]
                prob *= q if x else (1-q)
                wealth *= product_factor(x,a,lam)
                crossed = crossed or wealth >= threshold
                h = h+(x,)
            expected += prob*wealth
            if crossed:
                cross += prob

        max_exp = max(max_exp, float(expected))
        max_cross = max(max_cross, float(cross))
        exp_violations += expected > 1
        ville_violations += cross > alpha

    return {
        "samples": samples,
        "n": n,
        "alpha": float(alpha),
        "max_expected_final_e": max_exp,
        "max_crossing_probability": max_cross,
        "expectation_violations": exp_violations,
        "ville_violations": ville_violations,
        "pass": exp_violations == 0 and ville_violations == 0,
    }


def run_suite():
    fair = exhaustive_lambda_policies(
        n=3, q=Fraction(1,2), a=Fraction(1,2), alpha=Fraction(1,4)
    )
    biased = exhaustive_lambda_policies(
        n=3, q=Fraction(1,4), a=Fraction(1,4), alpha=Fraction(1,4)
    )
    counter = marginal_only_counterexample()
    random_trees = random_historywise_tree_checks()

    practical = {
        "16bit_1e6": budgeted_spike_process_one_hit(bits=16, n=1_000_000),
        "128bit_1e6": budgeted_spike_process_one_hit(bits=128, n=1_000_000),
        "256bit_1e6": budgeted_spike_process_one_hit(bits=256, n=1_000_000),
    }

    checks = {
        "fair_exhaustive_expectation": fair["expectation_violations"] == 0,
        "fair_exhaustive_ville": fair["ville_violations"] == 0,
        "fair_ville_bound_is_attained": abs(fair["max_crossing_probability"] - 0.25) < 1e-15,
        "biased_exhaustive_expectation": biased["expectation_violations"] == 0,
        "biased_exhaustive_ville": biased["ville_violations"] == 0,
        "biased_ville_bound_is_attained": abs(biased["max_crossing_probability"] - 0.25) < 1e-15,
        "marginal_only_counterexample_breaks_e_process": counter["wrong_ville_is_violated"],
        "historywise_repair_restores_validity": counter["correct_ville_respected"],
        "random_historywise_trees": random_trees["pass"],
        "256bit_equal_budget_matches_union_bound": abs(
            practical["256bit_1e6"]["ville_anytime_p_upper_if_hit"]
            - practical["256bit_1e6"]["same_as_union_bound"]
        ) / practical["256bit_1e6"]["same_as_union_bound"] < 1e-12,
        "16bit_million_one_hit_not_strong_evidence": practical["16bit_1e6"]["end_e_value_if_exactly_one_hit"] < 1,
    }
    all_pass = all(checks.values())

    return {
        "schema": SCHEMA,
        "status": "PASS" if all_pass else "FAIL",
        "all_pass": all_pass,
        "checks_total": len(checks),
        "checks_passed": sum(checks.values()),
        "checks": checks,
        "theorem": {
            "name": "JANUS Anytime-Valid Witness E-Process",
            "statement": (
                "Let F_{i-1} be the complete pre-target history. Let X_i=1[T_i in C_i], "
                "where C_i is chosen before T_i and P(X_i=1|F_{i-1})<=a_i almost surely. "
                "For any predictable lambda_i in [0,1], L_i=(1-lambda_i)+lambda_i X_i/a_i "
                "satisfies E[L_i|F_{i-1}]<=1. Hence E_n=product_{i<=n} L_i is a nonnegative "
                "supermartingale with E_0=1, and Ville's inequality gives "
                "P(sup_n E_n >= 1/alpha)<=alpha."
            ),
            "candidate_set_binding": (
                "If |C_i|<=K_i and max_t P(T_i=t|F_{i-1})<=p_i, use "
                "a_i=min(1,K_i p_i)."
            ),
            "proof": [
                "C_i and lambda_i are fixed from F_{i-1} before T_i is generated.",
                "E[X_i|F_{i-1}]<=a_i by the history-wise candidate-hit null bound.",
                "Therefore E[L_i|F_{i-1}] <= (1-lambda_i)+lambda_i=1.",
                "Multiplication by predictable nonnegative L_i makes E_n a nonnegative supermartingale.",
                "Ville's maximal inequality yields anytime-valid type-I control, including arbitrary stopping times."
            ],
            "novelty_boundary": (
                "Nonnegative test supermartingales, Ville's inequality, e-values and e-processes "
                "are established sequential-inference tools. JANUS does not claim this probability "
                "theorem as new mathematics; the contribution under study is its integration into "
                "the independent-future witness protocol with exact-bit identity, freeze-time side "
                "information, candidate multiplicity, and simulator/external-evidence separation."
            ),
        },
        "rare_event_variant": {
            "name": "JANUS Budgeted Spike E-Process",
            "statement": (
                "For predictable w_i>=0 with pathwise cumulative sum <=1, "
                "S_n=1+sum_{i<=n} w_i(X_i/a_i-1) is nonnegative and a supermartingale. "
                "This allocates a protected capital budget across extremely rare exact-match trials."
            ),
            "equal_budget_identity": (
                "With N equal weights 1/N and a=2^-h, one exact hit by horizon N yields "
                "terminal e-value 2^h/N, so Ville gives anytime p <= N*2^-h."
            ),
        },
        "experiments": {
            "fair_binary_exhaustive_lambda_policies": fair,
            "biased_binary_exhaustive_lambda_policies": biased,
            "marginal_only_counterexample": counter,
            "random_historywise_tree_checks": random_trees,
            "practical_budgeted_spike": practical,
        },
        "protocol_correction": {
            "mandatory": (
                "The e-process must use a history-wise conditional hit cap rooted in the complete "
                "pre-target transcript. Marginal entropy or an average p_guess cannot be substituted."
            ),
            "stopping": (
                "Once the null bound is history-wise valid, the e-process permits continuous monitoring "
                "and arbitrary data-dependent stopping without a separately fixed stopping time."
            ),
            "physical_boundary": (
                "An e-process quantifies incompatibility with the specified forward-null model; threshold "
                "crossing is not by itself proof of retrocausality, FTL or a CTC. External provenance, "
                "entropy audit, leakage exclusion and independent replication remain mandatory."
            ),
        },
    }


if __name__ == "__main__":
    report = run_suite()
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["all_pass"] else 1)
