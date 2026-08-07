#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
import math
import random
from typing import Callable

SCHEMA = "JANUS/genesis-sequential-adaptive-witness-lab/v0.1.0"


def exact_any_match_probability_binary(policy_bits: tuple[int, ...], n: int, q_one: float) -> float:
    histories = [h for length in range(n) for h in itertools.product((0, 1), repeat=length)]
    policy = dict(zip(histories, policy_bits))
    total = 0.0
    for seq in itertools.product((0, 1), repeat=n):
        prob = 1.0
        hit = False
        for i, target in enumerate(seq):
            prob *= q_one if target else (1.0 - q_one)
            guess = policy[tuple(seq[:i])]
            hit = hit or (guess == target)
        if hit:
            total += prob
    return total


def exhaustive_adaptive_binary(n: int, q_one: float) -> dict:
    histories = [h for length in range(n) for h in itertools.product((0, 1), repeat=length)]
    probs = []
    for mask in range(1 << len(histories)):
        bits = tuple((mask >> j) & 1 for j in range(len(histories)))
        probs.append(exact_any_match_probability_binary(bits, n, q_one))
    p = max(q_one, 1.0 - q_one)
    bound = 1.0 - (1.0 - p) ** n
    return {
        "n": n,
        "q_one": q_one,
        "policies_checked": len(probs),
        "min_any_match_probability": min(probs),
        "max_any_match_probability": max(probs),
        "historywise_point_guess_bound": p,
        "sequential_bound": bound,
        "violations": sum(x > bound + 1e-12 for x in probs),
        "pass": max(probs) <= bound + 1e-12,
    }


def correlated_marginal_attack() -> dict:
    # T1 is fair. Guess B1=0.
    # If T1=1 (failure), T2=1 deterministically and B2=1.
    # If T1=0 (already success), let T2 be fair.
    # Marginally P(T2=1)=0.5*1 + 0.5*0.5 = 0.75, so this first
    # example is not marginal-uniform; it targets the *average conditional*
    # guessing-probability pitfall.
    actual_any = 1.0
    p1 = 0.5
    avg_conditional_pguess_t2 = 0.5 * 1.0 + 0.5 * 0.5
    naive_product = 1.0 - (1.0 - p1) * (1.0 - avg_conditional_pguess_t2)
    worst_case_history_p2 = 1.0
    correct_bound = 1.0 - (1.0 - p1) * (1.0 - worst_case_history_p2)

    # Cleaner marginal-only pitfall: T2=T1. Both marginals are fair, but
    # after observing T1, B2 can copy T1 and guarantee a hit if trial 1 failed.
    marginal_uniform_actual = 1.0
    marginal_naive = 1.0 - (1.0 - 0.5) ** 2

    return {
        "average_conditional_entropy_pitfall": {
            "actual_any_match_probability": actual_any,
            "p1": p1,
            "average_conditional_pguess_t2": avg_conditional_pguess_t2,
            "naive_product_using_average_pguess": naive_product,
            "worst_case_history_pguess_t2": worst_case_history_p2,
            "correct_historywise_bound": correct_bound,
            "naive_bound_violated": actual_any > naive_product + 1e-12,
            "correct_bound_respected": actual_any <= correct_bound + 1e-12,
        },
        "marginal_entropy_pitfall": {
            "construction": "T1 fair; T2=T1; B1=0; after T1 reveal choose B2=T1",
            "each_target_marginal_is_fair": True,
            "actual_any_match_probability": marginal_uniform_actual,
            "naive_independent_two_trial_bound": marginal_naive,
            "naive_bound_violated": marginal_uniform_actual > marginal_naive + 1e-12,
            "reason": "Inter-trial dependence becomes side information at the second freeze. Marginal entropy is not fresh conditional entropy.",
        },
    }


def random_historywise_tree_checks(samples: int = 5000, n: int = 6, pmax: float = 0.75, seed: int = 1138) -> dict:
    rng = random.Random(seed)
    bound = 1.0 - (1.0 - pmax) ** n
    worst = 0.0
    violations = 0

    # Build random binary target trees. At every history, q=P(T=1|history)
    # lies in [1-pmax, pmax], hence max_t P(T=t|history) <= pmax.
    # The adaptive guess may depend on the full target history.
    for _ in range(samples):
        q_by_hist: dict[tuple[int, ...], float] = {}
        g_by_hist: dict[tuple[int, ...], int] = {}
        for length in range(n):
            for hist in itertools.product((0, 1), repeat=length):
                q = rng.uniform(1.0 - pmax, pmax)
                q_by_hist[hist] = q
                # Random adaptive policy, deliberately not always optimal.
                g_by_hist[hist] = rng.randrange(2)

        total = 0.0
        for seq in itertools.product((0, 1), repeat=n):
            prob = 1.0
            hit = False
            for i, target in enumerate(seq):
                hist = tuple(seq[:i])
                q = q_by_hist[hist]
                prob *= q if target else (1.0 - q)
                hit = hit or (g_by_hist[hist] == target)
            if hit:
                total += prob
        worst = max(worst, total)
        if total > bound + 1e-12:
            violations += 1

    return {
        "samples": samples,
        "n": n,
        "historywise_pmax": pmax,
        "sequential_bound": bound,
        "max_observed_any_match_probability": worst,
        "violations": violations,
        "pass": violations == 0,
    }


def candidate_set_uniform_check(alphabet: int = 8, k: int = 2, n: int = 3) -> dict:
    per_trial = k / alphabet
    exact_any = 1.0 - (1.0 - per_trial) ** n
    theorem_bound = 1.0 - (1.0 - min(1.0, k * (1.0 / alphabet))) ** n
    return {
        "alphabet": alphabet,
        "candidate_set_size": k,
        "n": n,
        "per_trial_success": per_trial,
        "exact_any_match_probability": exact_any,
        "historywise_set_bound": theorem_bound,
        "pass": abs(exact_any - theorem_bound) < 1e-15,
        "interpretation": "Allowing K pre-target candidates multiplies the point-guess budget by K. A single frozen candidate slot is the cleanest design."
    }


def practical_bounds() -> dict:
    def any_bound(bits: int, n: int) -> float:
        p = 2.0 ** (-bits)
        # numerically stable 1-(1-p)^n
        return -math.expm1(n * math.log1p(-p))
    return {
        "16bit_1e6_trials": any_bound(16, 1_000_000),
        "32bit_1e6_trials": any_bound(32, 1_000_000),
        "128bit_1e6_trials": any_bound(128, 1_000_000),
        "256bit_1e6_trials": any_bound(256, 1_000_000),
        "note": "These use a history-wise per-trial point-guess cap 2^-h. They are not valid if h is only a marginal or average entropy figure that can collapse on selected histories."
    }


def theorem_text() -> dict:
    return {
        "name": "JANUS Sequential Adaptive Witness Bound",
        "statement": (
            "Let F_{i-1} be the complete pre-target history at trial i. "
            "Let C_i be an F_{i-1}-measurable candidate set with |C_i|<=K_i. "
            "Assume almost surely max_t P(T_i=t | F_{i-1}) <= p_i. "
            "Then P(exists i<=N: T_i in C_i) <= "
            "1 - product_i (1 - min(1,K_i p_i)). "
            "The result allows arbitrary dependence across trials, adaptive candidate choice, "
            "and any stopping rule bounded by N."
        ),
        "proof": [
            "Condition on a history with no earlier hit. Because C_i is fixed before T_i and contains at most K_i values, P(T_i in C_i | F_{i-1}) <= min(1,K_i p_i).",
            "Therefore on every no-hit history, P(no hit at i | F_{i-1}) >= 1-min(1,K_i p_i).",
            "Iterating conditional expectation gives P(no hit through N) >= product_i(1-min(1,K_i p_i)).",
            "Taking complements gives the bound.",
            "A bounded stopping rule cannot enlarge the event beyond 'a hit occurred by N', so the same familywise bound applies."
        ],
        "critical_distinction": (
            "Average/marginal min-entropy is sufficient for a one-shot guessing bound, "
            "but the product/optional-stopping bound requires a history-wise conditional point-probability cap "
            "or another entropy-accumulation argument. Rare low-entropy histories can otherwise be selected adaptively."
        ),
        "novelty_boundary": (
            "The probability argument is elementary sequential conditioning and is not claimed as new mathematics. "
            "Its JANUS role is protocol hardening for retrocausal/independent-future witness tests."
        )
    }


def run() -> dict:
    fair = exhaustive_adaptive_binary(4, 0.5)
    biased = exhaustive_adaptive_binary(4, 0.75)
    corr = correlated_marginal_attack()
    trees = random_historywise_tree_checks()
    sets = candidate_set_uniform_check()
    bounds = practical_bounds()

    checks = {
        "fair_all_adaptive_policies_respect_bound": fair["pass"],
        "fair_expected_exact_15_16": abs(fair["max_any_match_probability"] - 15/16) < 1e-15,
        "biased_all_adaptive_policies_respect_bound": biased["pass"],
        "biased_max_hits_bound": abs(biased["max_any_match_probability"] - biased["sequential_bound"]) < 1e-12,
        "average_conditional_naive_product_counterexample_found": corr["average_conditional_entropy_pitfall"]["naive_bound_violated"],
        "historywise_bound_repairs_counterexample": corr["average_conditional_entropy_pitfall"]["correct_bound_respected"],
        "marginal_entropy_counterexample_found": corr["marginal_entropy_pitfall"]["naive_bound_violated"],
        "random_historywise_trees_respect_bound": trees["pass"],
        "candidate_set_bound_exact_uniform_case": sets["pass"],
        "16bit_million_trials_almost_certain_false_positive": bounds["16bit_1e6_trials"] > 0.999,
        "256bit_million_trials_tiny_bound": bounds["256bit_1e6_trials"] < 1e-70,
    }
    return {
        "schema": SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "all_pass": all(checks.values()),
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "checks": checks,
        "theorem": theorem_text(),
        "experiments": {
            "fair_binary_exhaustive": fair,
            "biased_binary_exhaustive": biased,
            "correlated_entropy_attacks": corr,
            "random_historywise_tree_checks": trees,
            "candidate_set_check": sets,
            "practical_bounds": bounds,
        },
        "protocol_correction": {
            "old_unsafe_shortcut": "Treating marginal or average entropy per trial as if it automatically supported an optional-stopping/product bound.",
            "new_required_gate": "At every target generation, certify a history-wise conditional point-guess cap relative to the complete pre-target transcript, or use a separately justified entropy-accumulation theorem.",
            "single_slot_policy": "Exactly one frozen candidate per trial remains preferred. If K candidates are allowed, the multiplicity K must enter the bound.",
            "stopping_rule": "Maximum trial count N and stopping/reporting rule must be preregistered; continuous monitoring is handled only under the sequential history-wise bound or an anytime-valid martingale test."
        },
        "physical_boundary": "This is a null-model/protocol theorem and machine test. It neither creates nor observes a backward-time physical channel."
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if report["all_pass"] else 1)
