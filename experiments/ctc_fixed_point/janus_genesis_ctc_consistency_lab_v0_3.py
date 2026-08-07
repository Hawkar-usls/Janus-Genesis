#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable

SCHEMA = "JANUS/genesis-ctc-consistency-lab/v0.3.0"
SEED = 1138


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else canonical(value)
    return hashlib.sha256(raw).hexdigest()


def z2_fixed_point_exists(dirac_toggles: int) -> bool:
    return (dirac_toggles & 1) == 0


def integer_translation_fixed_point_exists(delta: int) -> bool:
    return delta == 0


def affine_memory_fixed_point(a: Fraction, delta: Fraction, *, nonnegative: bool = True) -> tuple[bool, Fraction | None]:
    if a == 1:
        return (delta == 0, Fraction(0) if delta == 0 else None)
    mu = delta / (1 - a)
    if nonnegative and mu < 0:
        return False, None
    return True, mu


def payload_fixed_points(bits: int, xor_mask: int) -> int:
    limit = 1 << bits
    return sum(1 for x in range(limit) if (x ^ xor_mask) == x)


def classical_not_stationary_distribution() -> dict[str, Fraction]:
    return {"p0": Fraction(1, 2), "p1": Fraction(1, 2)}


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str


def has_directed_cycle(nodes: Iterable[str], edges: list[Edge], *, include_retro: bool = True) -> bool:
    allowed = [e for e in edges if include_retro or e.kind != "retrocausal_assumption"]
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    indeg: dict[str, int] = {n: 0 for n in nodes}
    for e in allowed:
        adj.setdefault(e.source, []).append(e.target)
        indeg[e.target] = indeg.get(e.target, 0) + 1
        indeg.setdefault(e.source, 0)
    stack = [n for n, d in indeg.items() if d == 0]
    seen = 0
    while stack:
        n = stack.pop()
        seen += 1
        for m in adj.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                stack.append(m)
    return seen != len(indeg)


def causal_models() -> dict[str, Any]:
    nodes = ["FREEZE", "PRE_RETURN", "TARGET", "SEND", "PHOTON_RETURN"]
    ordinary = [
        Edge("FREEZE", "PRE_RETURN", "ordinary"),
        Edge("PRE_RETURN", "TARGET", "ordinary"),
        Edge("TARGET", "SEND", "ordinary"),
        Edge("SEND", "PHOTON_RETURN", "ordinary"),
    ]
    backdated = list(ordinary)
    bootstrap = [
        Edge("FREEZE", "PRE_RETURN", "ordinary"),
        Edge("PRE_RETURN", "TARGET", "ordinary"),
        Edge("TARGET", "SEND", "ordinary"),
    ]
    ideal_ctc = [
        Edge("FREEZE", "TARGET", "ordinary"),
        Edge("TARGET", "SEND", "ordinary"),
        Edge("SEND", "PRE_RETURN", "retrocausal_assumption"),
        Edge("PRE_RETURN", "TARGET", "ordinary"),
    ]
    return {
        "ordinary_forward": {
            "full_graph_cycle": has_directed_cycle(nodes, ordinary),
            "ordinary_edges_cycle": has_directed_cycle(nodes, ordinary, include_retro=False),
            "classification": "ACYCLIC_FORWARD_MODEL",
        },
        "backdated_timestamp": {
            "full_graph_cycle": has_directed_cycle(nodes, backdated),
            "classification": "ACYCLIC_RECORD_WITH_EDITED_COORDINATE_TIME",
            "retrocausality": False,
        },
        "bootstrap_copy": {
            "full_graph_cycle": has_directed_cycle(nodes, bootstrap),
            "future_source_independent_of_pre_return": False,
            "classification": "SELF_CONSISTENT_COPY_POSSIBLE_BUT_NOT_INDEPENDENT_FUTURE",
        },
        "idealized_ctc_constraint_graph": {
            "full_graph_cycle": has_directed_cycle(nodes, ideal_ctc),
            "ordinary_subgraph_cycle": has_directed_cycle(nodes, ideal_ctc, include_retro=False),
            "classification": "CYCLIC_ONLY_BECAUSE_RETROCAUSAL_EDGE_IS_ASSUMED",
            "physical_instantiation": "NOT_ESTABLISHED",
        },
    }


def min_entropy_match_bound(h_bits: int, trials: int = 1) -> dict[str, Any]:
    if h_bits < 0 or trials < 1:
        raise ValueError("invalid min-entropy bound parameters")
    p_one = math.ldexp(1.0, -h_bits) if h_bits < 1075 else 0.0
    union = min(1.0, trials * p_one)
    exact = 1.0 - (1.0 - p_one) ** trials if p_one > 0 and trials < 10**8 else None
    return {
        "conditional_min_entropy_bits": h_bits,
        "trials": trials,
        "per_trial_upper_bound": p_one,
        "familywise_union_bound": union,
        "exact_independent_uniform_familywise": exact,
        "statement": "If H_inf(T | adversary_view_at_freeze) >= h, any fixed pre-return guess matches T with probability at most 2^-h per trial.",
    }


def monte_carlo_null(bits: int, trials: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    matches = 0
    for _ in range(trials):
        pre = rng.getrandbits(bits)
        target = rng.getrandbits(bits)
        matches += pre == target
    p = 1 / (1 << bits)
    expected = trials * p
    var = trials * p * (1 - p)
    z = (matches - expected) / math.sqrt(var) if var else 0.0
    return {
        "bits": bits,
        "trials": trials,
        "matches": matches,
        "expected_matches": expected,
        "rate": matches / trials,
        "expected_rate": p,
        "z_approx": z,
    }


def provenance_semantics() -> dict[str, Any]:
    return {
        "signed_entropy_receipt_proves": [
            "which authority key signed the receipt",
            "which pre-return commitment hash the assignment was bound to",
            "which bundle bytes the authority attested",
            "receipt integrity against later modification",
        ],
        "signed_entropy_receipt_does_not_prove": [
            "the authority private state was unknowable to every process before assignment",
            "the host OS/hypervisor was uncompromised",
            "the entropy source had the claimed conditional min-entropy",
            "physical retrocausality",
        ],
        "correct_status": "PROVENANCE_ATTESTED_UNPREDICTABILITY_REQUIRES_EXTERNAL_TRUST_AND_ENTROPY_AUDIT",
    }


def closure_analysis() -> dict[str, Any]:
    odd_dirac = z2_fixed_point_exists(1)
    even_dirac = z2_fixed_point_exists(2)
    w_plus_one = integer_translation_fixed_point_exists(1)
    w_zero = integer_translation_fixed_point_exists(0)
    mu_persistent, mu_persistent_value = affine_memory_fixed_point(Fraction(1), Fraction(1))
    mu_relax, mu_relax_value = affine_memory_fixed_point(Fraction(1, 2), Fraction(1))
    mu_decay_no_stim, mu_decay_no_stim_value = affine_memory_fixed_point(Fraction(1, 2), Fraction(0))
    return {
        "dirac_z2": {
            "odd_2pi_fixed_point_exists": odd_dirac,
            "even_4pi_fixed_point_exists": even_dirac,
            "interpretation": "pi_1(SO(3))=Z2: an odd toggle has no exact parity fixed point; two toggles restore the parity register.",
        },
        "burovchik_history_register": {
            "W_plus_1_fixed_point_exists_over_Z": w_plus_one,
            "W_plus_0_fixed_point_exists_over_Z": w_zero,
            "boundary": "W is an auxiliary signed history counter/encoder. It is not an additional topological invariant of SO(3).",
        },
        "material_memory": {
            "persistent_additive_case": {
                "map": "mu' = mu + 1",
                "fixed_point_exists": mu_persistent,
                "fixed_point": str(mu_persistent_value) if mu_persistent_value is not None else None,
            },
            "relaxing_case": {
                "map": "mu' = (1/2) mu + 1",
                "fixed_point_exists": mu_relax,
                "fixed_point": str(mu_relax_value) if mu_relax_value is not None else None,
                "important_correction": "Material memory is an obstruction only when the net one-loop map has no fixed point within the physical state domain.",
            },
            "decay_without_stimulus": {
                "map": "mu' = (1/2) mu",
                "fixed_point_exists": mu_decay_no_stim,
                "fixed_point": str(mu_decay_no_stim_value) if mu_decay_no_stim_value is not None else None,
            },
        },
        "strong_closure_rule": "Exact closure requires every included physical/register component to satisfy its own fixed-point equation. Z2 reset alone is insufficient, but W or mu obstruct closure only if they are genuine retained state variables with no compensating reset/relaxation fixed point.",
    }


def run_self_tests() -> dict[str, Any]:
    tests: dict[str, bool] = {}
    tests["z2_odd_no_fixed_point"] = z2_fixed_point_exists(1) is False
    tests["z2_even_fixed_point"] = z2_fixed_point_exists(2) is True
    tests["integer_translation_nonzero_no_fixed_point"] = integer_translation_fixed_point_exists(1) is False
    tests["integer_translation_zero_fixed_point"] = integer_translation_fixed_point_exists(0) is True
    ok, fp = affine_memory_fixed_point(Fraction(1), Fraction(1))
    tests["persistent_memory_increment_no_fixed_point"] = (not ok and fp is None)
    ok, fp = affine_memory_fixed_point(Fraction(1, 2), Fraction(1))
    tests["relaxing_memory_has_fixed_point_two"] = (ok and fp == 2)
    tests["payload_identity_8bit_has_256"] = payload_fixed_points(8, 0) == 256
    tests["payload_not_8bit_has_zero"] = payload_fixed_points(8, 0xFF) == 0
    tests["payload_xor1_8bit_has_zero"] = payload_fixed_points(8, 0x01) == 0
    dist = classical_not_stationary_distribution()
    tests["classical_not_stationary_half_half"] = dist == {"p0": Fraction(1, 2), "p1": Fraction(1, 2)}
    models = causal_models()
    tests["ordinary_graph_acyclic"] = models["ordinary_forward"]["full_graph_cycle"] is False
    tests["backdating_does_not_create_cycle"] = models["backdated_timestamp"]["full_graph_cycle"] is False
    tests["bootstrap_not_independent"] = models["bootstrap_copy"]["future_source_independent_of_pre_return"] is False
    tests["ideal_ctc_graph_cyclic"] = models["idealized_ctc_constraint_graph"]["full_graph_cycle"] is True
    tests["ideal_ctc_ordinary_subgraph_acyclic"] = models["idealized_ctc_constraint_graph"]["ordinary_subgraph_cycle"] is False
    mc8 = monte_carlo_null(8, 200_000, SEED + 1)
    tests["mc8_within_5sigma"] = abs(mc8["z_approx"]) < 5
    mc16 = monte_carlo_null(16, 500_000, SEED + 2)
    tests["mc16_sane_count"] = mc16["matches"] < 30
    return {
        "all_pass": all(tests.values()),
        "tests_total": len(tests),
        "tests_passed": sum(tests.values()),
        "tests": tests,
        "mc8": mc8,
        "mc16": mc16,
    }


def build_report() -> dict[str, Any]:
    self_tests = run_self_tests()
    report = {
        "schema": SCHEMA,
        "status": "PASS" if self_tests["all_pass"] else "FAIL",
        "purpose": "Correct the JANUS Genesis CTC sandbox so it distinguishes exact fixed-point mathematics, simulated causal graphs, entropy provenance, and physical claims.",
        "corrections_from_prior_versions": [
            "Coordinate timestamps in software are model labels; they are not physical proper-time evidence.",
            "W in Z is treated as an auxiliary signed history encoder, not as a new topological invariant of SO(3).",
            "W -> W+1 and mu -> mu+1 are analyzed by exact equations rather than a truncated finite-domain count.",
            "SCOBY/material memory is not assumed absolutely irreversible; affine relaxation can admit a fixed point.",
            "The 1/2-1/2 NOT result is labeled a classical stochastic stationary distribution, not a full Deutsch quantum-CTC calculation.",
            "A signed entropy receipt proves provenance/integrity, not unconditional unpredictability.",
            "Future-information null bounds are stated in terms of conditional min-entropy at the PRE_RETURN freeze time.",
        ],
        "fixed_point_math": {
            "payload": {
                "identity_8bit_fixed_points": payload_fixed_points(8, 0),
                "not_8bit_fixed_points": payload_fixed_points(8, 0xFF),
                "xor1_8bit_fixed_points": payload_fixed_points(8, 0x01),
            },
            "classical_not_stationary_distribution": {
                "p0": "1/2",
                "p1": "1/2",
                "boundary": "classical Markov/stochastic consistency analog only",
            },
            "janus_closure": closure_analysis(),
        },
        "causal_graph_models": causal_models(),
        "information_null": {
            "ideal_256bit_single_trial": min_entropy_match_bound(256, 1),
            "ideal_256bit_one_million_trials": min_entropy_match_bound(256, 1_000_000),
            "semantic_class_policy": "Do not count semantic-class entropy toward the hard identity bound unless its conditional min-entropy is independently established; payload128+nonce128 alone supply the nominal 256-bit identity layer.",
            "monte_carlo_surrogates": {"8bit": self_tests["mc8"], "16bit": self_tests["mc16"]},
        },
        "entropy_provenance": provenance_semantics(),
        "self_tests": self_tests,
        "admission": {
            "ALGORITHMIC_FIXED_POINT_MATH": True,
            "SIMULATED_CTC_CONSTRAINT_GRAPH": True,
            "BACKDATED_TIMESTAMP_IS_RETROCAUSALITY": False,
            "SIGNED_RECEIPT_PROVES_PROVENANCE": True,
            "SIGNED_RECEIPT_PROVES_UNPREDICTABILITY": False,
            "W_IS_SO3_TOPOLOGICAL_INVARIANT": False,
            "MATERIAL_MEMORY_ALWAYS_OBSTRUCTS_CLOSURE": False,
            "PHYSICAL_CTC_TESTED": False,
            "PHYSICAL_FTL_TESTED": False,
            "FUTURE_BITS_PHYSICALLY_PREEXIST": False,
        },
        "next_gate": {
            "name": "JANUS INDEPENDENT-FUTURE BENCH GATE",
            "requirements": [
                "PRE_RETURN slot and raw bytes frozen before target generation",
                "external or hardware-separated entropy source with measured/audited conditional min-entropy",
                "signed provenance receipt bound to the PRE_RETURN commitment",
                "independent append-only anchor outside the candidate process",
                "single local acquisition order plus calibrated clock uncertainty",
                "exact payload+nonce equality; no semantic post-selection",
                "negative controls and independent replication",
            ],
            "critical_boundary": "Genesis can validate the protocol and mathematical consistency. A real negative-time or FTL claim requires a physical channel external to the simulator.",
        },
    }
    report["report_sha256_without_self_hash"] = sha256(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    report = build_report()
    print(json.dumps(report if args.report else report["self_tests"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
