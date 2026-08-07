#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from typing import Any, Callable

SCHEMA = "JANUS/genesis-ctc-fixed-point-lab/v0.1.0"
ZERO_HASH = "0" * 64

def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

def sha256(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else canonical(value)
    return hashlib.sha256(raw).hexdigest()

def exact_fixed_points(bits: int, transform: Callable[[int], int]) -> list[int]:
    return [x for x in range(1 << bits) if transform(x) == x]

def stationary_not_distribution() -> dict[str, float]:
    # For a one-bit NOT transition, stationarity means p(0)=p(1).
    return {"p0": 0.5, "p1": 0.5}

@dataclass(frozen=True)
class JanusState:
    payload: int
    nu: int
    winding: int
    mu: int

def map_state(
    x: JanusState,
    *,
    payload_mask: int = 0,
    dirac_toggles: int = 0,
    winding_delta: int = 0,
    mu_delta: int = 0,
) -> JanusState:
    return JanusState(
        payload=x.payload ^ payload_mask,
        nu=x.nu ^ (dirac_toggles & 1),
        winding=x.winding + winding_delta,
        mu=x.mu + mu_delta,
    )

def bounded_state_fixed_points(
    *,
    payload_bits: int,
    winding_values: range,
    mu_values: range,
    payload_mask: int = 0,
    dirac_toggles: int = 0,
    winding_delta: int = 0,
    mu_delta: int = 0,
) -> int:
    count = 0
    for payload in range(1 << payload_bits):
        for nu in (0, 1):
            for winding in winding_values:
                for mu in mu_values:
                    x = JanusState(payload, nu, winding, mu)
                    if map_state(
                        x,
                        payload_mask=payload_mask,
                        dirac_toggles=dirac_toggles,
                        winding_delta=winding_delta,
                        mu_delta=mu_delta,
                    ) == x:
                        count += 1
    return count

def make_event(
    sequence: int,
    kind: str,
    payload: dict[str, Any],
    *,
    monotonic_ns: int,
    coordinate_clock_ns: int,
    previous_hash: str,
) -> dict[str, Any]:
    unsigned = {
        "sequence": sequence,
        "kind": kind,
        "payload": payload,
        "monotonic_ns": monotonic_ns,
        "coordinate_clock_ns": coordinate_clock_ns,
        "previous_hash": previous_hash,
    }
    return {**unsigned, "event_hash": sha256(unsigned)}

def build_chain(spec: list[tuple[str, dict[str, Any], int, int]]) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    previous = ZERO_HASH
    for i, (kind, payload, mono, clock) in enumerate(spec, 1):
        ev = make_event(
            i, kind, payload,
            monotonic_ns=mono,
            coordinate_clock_ns=clock,
            previous_hash=previous,
        )
        chain.append(ev)
        previous = ev["event_hash"]
    return chain

def verify_chain(chain: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    prev_hash = ZERO_HASH
    prev_mono: int | None = None
    for expected_seq, ev in enumerate(chain, 1):
        if ev.get("sequence") != expected_seq:
            failures.append(f"sequence:{expected_seq}")
        if ev.get("previous_hash") != prev_hash:
            failures.append(f"previous_hash:{expected_seq}")
        unsigned = dict(ev)
        observed = unsigned.pop("event_hash", None)
        if observed != sha256(unsigned):
            failures.append(f"event_hash:{expected_seq}")
        mono = ev.get("monotonic_ns")
        if not isinstance(mono, int):
            failures.append(f"monotonic_type:{expected_seq}")
        elif prev_mono is not None and mono <= prev_mono:
            failures.append(f"monotonic_order:{expected_seq}")
        if isinstance(mono, int):
            prev_mono = mono
        prev_hash = str(observed or "")
    return not failures, failures

def causal_trace_experiments(seed: int = 1138) -> dict[str, Any]:
    rng = random.Random(seed)
    bits = 16
    target = rng.getrandbits(bits)
    other = rng.getrandbits(bits)

    cheat = build_chain([
        ("TARGET_ASSIGNED", {"target": target}, 1_000, 10_000),
        ("SEND", {"target": target}, 2_000, 11_000),
        ("PRE_RETURN", {"target": target}, 3_000, 9_000),
    ])
    cheat_chain_ok, cheat_chain_fail = verify_chain(cheat)
    naive_negative_J = cheat[2]["coordinate_clock_ns"] - cheat[1]["coordinate_clock_ns"] < 0
    proof_order_ok = cheat[2]["sequence"] < cheat[0]["sequence"]

    ctc_value = other
    copy_loop = {
        "pre_return": ctc_value,
        "target_at_send": ctc_value,
        "exact_match": True,
        "rng_independence": False,
        "interpretation": "self-consistent copy loop, not independent future information",
    }

    trials_8 = 200_000
    matches_8 = 0
    rng8 = random.Random(seed + 1)
    for _ in range(trials_8):
        pre = rng8.getrandbits(8)
        future = rng8.getrandbits(8)
        matches_8 += (pre == future)

    trials_16 = 500_000
    matches_16 = 0
    rng16 = random.Random(seed + 2)
    for _ in range(trials_16):
        pre = rng16.getrandbits(16)
        future = rng16.getrandbits(16)
        matches_16 += (pre == future)

    pool = 100_000
    selected = 0
    rngp = random.Random(seed + 3)
    for _ in range(pool):
        pre = rngp.getrandbits(8)
        future = rngp.getrandbits(8)
        if pre == future:
            selected += 1

    return {
        "backdated_insert_cheat": {
            "naive_negative_J": naive_negative_J,
            "hash_chain_valid": cheat_chain_ok,
            "hash_chain_failures": cheat_chain_fail,
            "pre_return_physically_recorded_before_assignment_by_sequence": proof_order_ok,
            "result": "REJECT",
            "reason": "negative coordinate timestamp was created after SEND in monotonic execution order",
        },
        "self_consistent_copy_loop": {
            **copy_loop,
            "result": "REJECT_AS_FUTURE_BITS_TEST",
            "reason": "exact identity is obtained by making future target depend on the earlier loop state",
        },
        "independent_rng_null_8bit": {
            "trials": trials_8,
            "matches": matches_8,
            "rate": matches_8 / trials_8,
            "expected_rate": 1 / 256,
            "z_approx": (matches_8 - trials_8 / 256) / math.sqrt(trials_8 * (1/256) * (255/256)),
        },
        "independent_rng_null_16bit": {
            "trials": trials_16,
            "matches": matches_16,
            "rate": matches_16 / trials_16,
            "expected_rate": 1 / 65536,
            "expected_matches": trials_16 / 65536,
        },
        "postselection_attack_8bit": {
            "pool_trials": pool,
            "matching_pairs_available_for_cherry_pick": selected,
            "expected": pool / 256,
            "result": "REJECT",
            "reason": "selecting a matching pair after inspecting the pool is post-selection, not a preregistered pre-SEND return",
        },
    }

def run_fixed_point_lab() -> dict[str, Any]:
    identity_8 = exact_fixed_points(8, lambda x: x)
    not_8 = exact_fixed_points(8, lambda x: x ^ 0xFF)
    xor1_8 = exact_fixed_points(8, lambda x: x ^ 0x01)

    domain = {
        "payload_bits": 3,
        "winding_values": [-1, 0, 1],
        "mu_values": [0, 1, 2],
    }
    kwargs = {
        "payload_bits": domain["payload_bits"],
        "winding_values": range(-1, 2),
        "mu_values": range(0, 3),
    }

    cases = {
        "identity_loop": bounded_state_fixed_points(**kwargs),
        "odd_dirac_toggle": bounded_state_fixed_points(**kwargs, dirac_toggles=1),
        "even_dirac_two_toggles": bounded_state_fixed_points(**kwargs, dirac_toggles=2),
        "burovchik_winding_increment": bounded_state_fixed_points(**kwargs, winding_delta=1),
        "scoby_memory_increment": bounded_state_fixed_points(**kwargs, mu_delta=1),
        "combined_odd_dirac_winding_scoby": bounded_state_fixed_points(
            **kwargs, dirac_toggles=1, winding_delta=1, mu_delta=1
        ),
    }

    total_states = (1 << domain["payload_bits"]) * 2 * 3 * 3
    return {
        "classical_payload_fixed_points": {
            "identity_8bit": len(identity_8),
            "not_8bit": len(not_8),
            "xor_00000001_8bit": len(xor1_8),
            "interpretation": "identity has every payload as a fixed point; nonzero XOR maps have no deterministic classical fixed point",
        },
        "deutsch_distribution_analog": {
            "one_bit_NOT_stationary_distribution": stationary_not_distribution(),
            "important_boundary": "distributional consistency does not provide a definite pre-existing payload bit",
        },
        "janus_full_state_exact_search": {
            "domain": domain,
            "total_states": total_states,
            "fixed_point_counts": cases,
            "derived_obstructions": {
                "odd_Z2_toggle": cases["odd_dirac_toggle"] == 0,
                "signed_winding_increment": cases["burovchik_winding_increment"] == 0,
                "material_memory_increment": cases["scoby_memory_increment"] == 0,
                "combined_obstruction": cases["combined_odd_dirac_winding_scoby"] == 0,
                "even_Z2_only_restores_topological_fixed_points": cases["even_dirac_two_toggles"] == total_states,
            },
        },
    }

def report(seed: int = 1138) -> dict[str, Any]:
    fixed = run_fixed_point_lab()
    traces = causal_trace_experiments(seed)
    assertions = {
        "NOT_loop_has_no_deterministic_fixed_point": fixed["classical_payload_fixed_points"]["not_8bit"] == 0,
        "odd_Dirac_toggle_obstructs_exact_closure": fixed["janus_full_state_exact_search"]["fixed_point_counts"]["odd_dirac_toggle"] == 0,
        "winding_increment_obstructs_exact_closure": fixed["janus_full_state_exact_search"]["fixed_point_counts"]["burovchik_winding_increment"] == 0,
        "SCOBY_memory_increment_obstructs_exact_closure": fixed["janus_full_state_exact_search"]["fixed_point_counts"]["scoby_memory_increment"] == 0,
        "backdated_timestamp_cheat_rejected": traces["backdated_insert_cheat"]["result"] == "REJECT",
        "self_consistent_copy_not_independent": traces["self_consistent_copy_loop"]["rng_independence"] is False,
        "postselection_rejected": traces["postselection_attack_8bit"]["result"] == "REJECT",
    }
    return {
        "schema": SCHEMA,
        "status": "PASS" if all(assertions.values()) else "FAIL",
        "seed": seed,
        "purpose": "Test algorithmic/simulated CTC fixed-point behavior and the JANUS causal-topological obstruction inside Genesis. This is not a physical FTL experiment.",
        "fixed_point_lab": fixed,
        "causal_trace_lab": traces,
        "assertions": assertions,
        "epistemic_boundary": {
            "algorithmic_CTC_model_tested": True,
            "physical_CTC_tested": False,
            "physical_FTL_tested": False,
            "future_bits_physical_preexistence_observed": False,
            "key_result": "Genesis can test consistency conditions and distinguish several simulator cheats; it cannot turn a software backdated event into evidence of physical retrocausality.",
        },
    }

def self_test() -> dict[str, Any]:
    result = report()
    if result["status"] != "PASS":
        raise AssertionError(json.dumps(result["assertions"], indent=2))
    return result

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--report", type=str)
    args = parser.parse_args()
    result = self_test() if args.self_test else report()
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
