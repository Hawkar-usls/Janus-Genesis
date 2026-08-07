#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, replace
from typing import Any

ZERO_HASH = "0" * 64

def canonical(payload: Any) -> bytes:
    """Genesis-compatible canonical JSON."""
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()

def make_bundle(run_id: str, semantic_class: int, payload_hex: str, nonce_hex: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "semantic_class": semantic_class,
        "payload_hex": payload_hex,
        "nonce_hex": nonce_hex,
    }

def append_event(
    chain: list[dict[str, Any]],
    kind: str,
    payload: dict[str, Any],
    *,
    monotonic_ns: int,
    clock_ns: int,
) -> dict[str, Any]:
    unsigned = {
        "sequence": len(chain) + 1,
        "kind": kind,
        "monotonic_ns": int(monotonic_ns),
        "clock_ns": int(clock_ns),
        "previous_hash": chain[-1]["event_hash"] if chain else ZERO_HASH,
        "payload": payload,
    }
    event = {**unsigned, "event_hash": sha256(canonical(unsigned))}
    chain.append(event)
    return event

def append_anchor(
    anchors: list[dict[str, Any]],
    local_event_hash: str,
    *,
    monotonic_ns: int,
) -> dict[str, Any]:
    unsigned = {
        "anchor_sequence": len(anchors) + 1,
        "monotonic_ns": int(monotonic_ns),
        "previous_anchor_hash": anchors[-1]["anchor_hash"] if anchors else ZERO_HASH,
        "committed_local_event_hash": local_event_hash,
    }
    anchor = {**unsigned, "anchor_hash": sha256(canonical(unsigned))}
    anchors.append(anchor)
    return anchor

def verify_local_chain(chain: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    previous = ZERO_HASH
    previous_mono: int | None = None
    for expected_seq, event in enumerate(chain, 1):
        if event.get("sequence") != expected_seq:
            failures.append(f"sequence:{expected_seq}")
        if event.get("previous_hash") != previous:
            failures.append(f"previous_hash:{expected_seq}")
        unsigned = dict(event)
        observed = unsigned.pop("event_hash", None)
        calculated = sha256(canonical(unsigned))
        if observed != calculated:
            failures.append(f"event_hash:{expected_seq}")
        mono = event.get("monotonic_ns")
        if not isinstance(mono, int):
            failures.append(f"monotonic_type:{expected_seq}")
        elif previous_mono is not None and mono <= previous_mono:
            failures.append(f"monotonic_order:{expected_seq}")
        previous_mono = mono if isinstance(mono, int) else previous_mono
        previous = str(observed or "")
    return not failures, failures

def verify_anchor_chain(anchors: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    previous = ZERO_HASH
    previous_mono: int | None = None
    for expected_seq, anchor in enumerate(anchors, 1):
        if anchor.get("anchor_sequence") != expected_seq:
            failures.append(f"anchor_sequence:{expected_seq}")
        if anchor.get("previous_anchor_hash") != previous:
            failures.append(f"previous_anchor_hash:{expected_seq}")
        unsigned = dict(anchor)
        observed = unsigned.pop("anchor_hash", None)
        calculated = sha256(canonical(unsigned))
        if observed != calculated:
            failures.append(f"anchor_hash:{expected_seq}")
        mono = anchor.get("monotonic_ns")
        if not isinstance(mono, int):
            failures.append(f"anchor_monotonic_type:{expected_seq}")
        elif previous_mono is not None and mono <= previous_mono:
            failures.append(f"anchor_monotonic_order:{expected_seq}")
        previous_mono = mono if isinstance(mono, int) else previous_mono
        previous = str(observed or "")
    return not failures, failures

def events_of_kind(chain: list[dict[str, Any]], kind: str) -> list[tuple[int, dict[str, Any]]]:
    return [(i, event) for i, event in enumerate(chain) if event.get("kind") == kind]

@dataclass(frozen=True)
class AuditFlags:
    epsilon_clock_ns: int = 100
    same_local_clock: bool = True
    no_known_channel_leakage: bool = True
    blind_protocol: bool = True
    clock_integrity_valid: bool = True
    no_clock_step_in_window: bool = True
    independent_time_anchor_valid: bool = True
    rng_independence_audited: bool = True
    canonicalization_frozen: bool = True
    target_independent_decoding: bool = True
    raw_return_preserved: bool = True

def verify_candidate(
    chain: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    audit: AuditFlags,
) -> dict[str, Any]:
    """Independent verifier. Recomputes identity, ordering, hashes, J and P_gamma."""
    checks: dict[str, bool] = {}
    local_ok, local_fail = verify_local_chain(chain)
    anchor_ok, anchor_fail = verify_anchor_chain(anchors)
    checks["local_chain_valid"] = local_ok
    checks["anchor_chain_valid"] = anchor_ok

    pre = events_of_kind(chain, "PRE_RETURN_FROZEN")
    assign = events_of_kind(chain, "TARGET_ASSIGNED")
    send = events_of_kind(chain, "SEND")
    photon = events_of_kind(chain, "PHOTON_RETURN")

    checks["single_preregistered_candidate_slot"] = len(pre) == 1
    checks["single_target_assignment"] = len(assign) == 1
    checks["single_send"] = len(send) == 1
    checks["single_photon_return"] = len(photon) == 1

    pre_idx, pre_ev = pre[0] if len(pre) == 1 else (-1, {})
    asg_idx, asg_ev = assign[0] if len(assign) == 1 else (-1, {})
    send_idx, send_ev = send[0] if len(send) == 1 else (-1, {})
    photon_idx, photon_ev = photon[0] if len(photon) == 1 else (-1, {})

    checks["candidate_before_assignment"] = 0 <= pre_idx < asg_idx
    checks["assignment_before_send"] = 0 <= asg_idx <= send_idx
    checks["photon_after_send"] = photon_idx > send_idx >= 0

    B_R = (pre_ev.get("payload") or {}).get("bundle")
    B_A = (asg_ev.get("payload") or {}).get("bundle")
    B_S = (send_ev.get("payload") or {}).get("bundle")
    checks["return_bundle_present"] = isinstance(B_R, dict)
    checks["assignment_bundle_present"] = isinstance(B_A, dict)
    checks["send_bundle_present"] = isinstance(B_S, dict)
    checks["exact_future_information_identity"] = (
        isinstance(B_R, dict) and B_R == B_A == B_S
    )

    expected_q = sha256(canonical(B_S)) if isinstance(B_S, dict) else None
    observed_q = (asg_ev.get("payload") or {}).get("Q")
    checks["assignment_digest_recomputed"] = expected_q is not None and observed_q == expected_q

    try:
        J_ns = int(pre_ev["clock_ns"]) - int(send_ev["clock_ns"])
        P_gamma_ns = int(photon_ev["clock_ns"]) - int(send_ev["clock_ns"])
    except (KeyError, TypeError, ValueError):
        J_ns = None
        P_gamma_ns = None
    checks["negative_J_beyond_margin"] = (
        J_ns is not None and J_ns < -int(audit.epsilon_clock_ns)
    )
    checks["photon_control_positive"] = (
        P_gamma_ns is not None and P_gamma_ns > int(audit.epsilon_clock_ns)
    )

    matching_anchors = [
        a for a in anchors
        if a.get("committed_local_event_hash") == pre_ev.get("event_hash")
    ]
    checks["preassignment_commitment_anchored"] = len(matching_anchors) == 1
    if len(matching_anchors) == 1 and asg_ev:
        checks["anchor_precedes_assignment_monotonic"] = (
            int(matching_anchors[0].get("monotonic_ns", 10**100))
            < int(asg_ev.get("monotonic_ns", -1))
        )
    else:
        checks["anchor_precedes_assignment_monotonic"] = False

    checks["same_local_clock"] = audit.same_local_clock
    checks["no_known_channel_leakage"] = audit.no_known_channel_leakage
    checks["blind_protocol"] = audit.blind_protocol
    checks["clock_integrity_valid"] = audit.clock_integrity_valid
    checks["no_clock_step_in_window"] = audit.no_clock_step_in_window
    checks["independent_time_anchor_valid"] = audit.independent_time_anchor_valid
    checks["rng_independence_audited"] = audit.rng_independence_audited
    checks["canonicalization_frozen"] = audit.canonicalization_frozen
    checks["target_independent_decoding"] = audit.target_independent_decoding
    checks["raw_return_preserved"] = audit.raw_return_preserved

    failed = [name for name, ok in checks.items() if not ok]
    return {
        "candidate": not failed,
        "failed_checks": failed,
        "checks": checks,
        "recomputed": {
            "J_ns": J_ns,
            "P_gamma_ns": P_gamma_ns,
            "Q_send": expected_q,
        },
        "chain_failures": local_fail,
        "anchor_failures": anchor_fail,
    }

def valid_fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]], AuditFlags]:
    B = make_bundle("run-1138", 17, "a3" * 16, "74" * 16)
    chain: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    append_event(chain, "CHANNEL_ISOLATED", {"mode": "synthetic"}, monotonic_ns=1_000, clock_ns=10_000)
    pre = append_event(chain, "PRE_RETURN_FROZEN", {"bundle": B}, monotonic_ns=2_000, clock_ns=10_100)
    append_anchor(anchors, pre["event_hash"], monotonic_ns=2_500)
    append_event(
        chain, "TARGET_ASSIGNED",
        {"bundle": B, "Q": sha256(canonical(B)), "rng": "synthetic-fixture"},
        monotonic_ns=3_000, clock_ns=10_200
    )
    append_event(chain, "SEND", {"bundle": B}, monotonic_ns=4_000, clock_ns=11_200)
    append_event(chain, "PHOTON_RETURN", {"control": "photon"}, monotonic_ns=5_000, clock_ns=21_200)
    return chain, anchors, AuditFlags()

def deep_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))

def rehash_from(chain: list[dict[str, Any]], start_index: int) -> None:
    for i in range(start_index, len(chain)):
        chain[i]["previous_hash"] = chain[i - 1]["event_hash"] if i else ZERO_HASH
        unsigned = dict(chain[i]); unsigned.pop("event_hash", None)
        chain[i]["event_hash"] = sha256(canonical(unsigned))

def run_attack_sweep() -> dict[str, Any]:
    base_chain, base_anchors, base_audit = valid_fixture()
    cases: list[tuple[str, list[dict[str, Any]], list[dict[str, Any]], AuditFlags, bool]] = []

    def add(name, mutate=None, audit=None, expected=False):
        c, a = deep_copy(base_chain), deep_copy(base_anchors)
        au = audit if audit is not None else base_audit
        if mutate:
            mutate(c, a)
        cases.append((name, c, a, au, expected))

    add("synthetic_valid_identity_fixture", expected=True)

    def m_sem(c, a):
        c[1]["payload"]["bundle"]["semantic_class"] = 18
        rehash_from(c, 1)
    add("semantic_class_mismatch", m_sem)

    def m_payload(c, a):
        c[1]["payload"]["bundle"]["payload_hex"] = "ff"*16
        rehash_from(c, 1)
    add("payload_mismatch", m_payload)

    def m_nonce(c, a):
        c[1]["payload"]["bundle"]["nonce_hex"] = "ee"*16
        rehash_from(c, 1)
    add("nonce_mismatch", m_nonce)

    def m_hash(c, a):
        c[1]["payload"]["bundle"]["nonce_hex"] = "00"*16
    add("raw_event_hash_tamper", m_hash)

    def m_prev(c, a):
        c[2]["previous_hash"] = "f"*64
        unsigned = dict(c[2]); unsigned.pop("event_hash", None)
        c[2]["event_hash"] = sha256(canonical(unsigned))
    add("previous_hash_link_tamper", m_prev)

    def m_seq(c, a):
        c[2]["sequence"] = 99
        unsigned = dict(c[2]); unsigned.pop("event_hash", None)
        c[2]["event_hash"] = sha256(canonical(unsigned))
    add("sequence_tamper", m_seq)

    def m_mono(c, a):
        c[2]["monotonic_ns"] = c[1]["monotonic_ns"]
        unsigned = dict(c[2]); unsigned.pop("event_hash", None)
        c[2]["event_hash"] = sha256(canonical(unsigned))
    add("monotonic_tamper", m_mono)

    def m_clockstep(c, a):
        pre = c.pop(1)
        c.insert(4, pre)
        for idx, ev in enumerate(c):
            ev["sequence"] = idx + 1
            ev["monotonic_ns"] = (idx + 1)*1000
            ev["previous_hash"] = c[idx-1]["event_hash"] if idx else ZERO_HASH
            unsigned = dict(ev); unsigned.pop("event_hash", None)
            ev["event_hash"] = sha256(canonical(unsigned))
        a[0]["committed_local_event_hash"] = pre["event_hash"]
        unsigned = dict(a[0]); unsigned.pop("anchor_hash", None)
        a[0]["anchor_hash"] = sha256(canonical(unsigned))
    add("clock_step_fake_negative_J", m_clockstep)

    def m_anchor_wrong(c, a):
        a[0]["committed_local_event_hash"] = "0"*64
        unsigned = dict(a[0]); unsigned.pop("anchor_hash", None)
        a[0]["anchor_hash"] = sha256(canonical(unsigned))
    add("wrong_external_anchor", m_anchor_wrong)

    def m_anchor_late(c, a):
        a[0]["monotonic_ns"] = 3_500
        unsigned = dict(a[0]); unsigned.pop("anchor_hash", None)
        a[0]["anchor_hash"] = sha256(canonical(unsigned))
    add("anchor_after_assignment", m_anchor_late)

    def m_multi(c, a):
        duplicate = deep_copy(c[1])
        c.insert(2, duplicate)
        for idx, ev in enumerate(c):
            ev["sequence"] = idx+1
            ev["monotonic_ns"] = (idx+1)*1000
            ev["previous_hash"] = c[idx-1]["event_hash"] if idx else ZERO_HASH
            unsigned = dict(ev); unsigned.pop("event_hash", None)
            ev["event_hash"] = sha256(canonical(unsigned))
    add("multiple_candidate_slots", m_multi)

    def m_assign_early(c, a):
        c[1], c[2] = c[2], c[1]
        for idx, ev in enumerate(c):
            ev["sequence"] = idx+1
            ev["monotonic_ns"] = (idx+1)*1000
            ev["previous_hash"] = c[idx-1]["event_hash"] if idx else ZERO_HASH
            unsigned = dict(ev); unsigned.pop("event_hash", None)
            ev["event_hash"] = sha256(canonical(unsigned))
    add("target_assigned_before_candidate", m_assign_early)

    def m_jmargin(c, a):
        c[1]["clock_ns"] = c[3]["clock_ns"] - 50
        rehash_from(c, 1)
    add("negative_J_inside_uncertainty", m_jmargin)

    def m_photon(c, a):
        c[4]["clock_ns"] = c[3]["clock_ns"]
        rehash_from(c, 4)
    add("photon_not_positive", m_photon)

    for name, changes in [
        ("known_channel_leakage", {"no_known_channel_leakage": False}),
        ("unblinded_protocol", {"blind_protocol": False}),
        ("clock_integrity_fail", {"clock_integrity_valid": False}),
        ("clock_step_audit_fail", {"no_clock_step_in_window": False}),
        ("independent_anchor_audit_fail", {"independent_time_anchor_valid": False}),
        ("rng_independence_fail", {"rng_independence_audited": False}),
        ("canonicalization_not_frozen", {"canonicalization_frozen": False}),
        ("target_dependent_decoder", {"target_independent_decoding": False}),
        ("raw_return_not_preserved", {"raw_return_preserved": False}),
        ("not_same_local_clock", {"same_local_clock": False}),
    ]:
        add(name, audit=replace(base_audit, **changes))

    results: dict[str, Any] = {}
    correct = 0
    for name, c, a, audit, expected in cases:
        verdict = verify_candidate(c, a, audit)
        is_correct = verdict["candidate"] == expected
        correct += int(is_correct)
        results[name] = {
            "expected_candidate": expected,
            "observed_candidate": verdict["candidate"],
            "correct": is_correct,
            "failed_checks": verdict["failed_checks"],
            "J_ns": verdict["recomputed"]["J_ns"],
            "P_gamma_ns": verdict["recomputed"]["P_gamma_ns"],
        }
    return {
        "cases_total": len(cases),
        "cases_correct": correct,
        "all_pass": correct == len(cases),
        "cases": results,
    }

def monte_carlo(seed: int = 0x1138) -> dict[str, Any]:
    rng = random.Random(seed)
    target_class = 17
    n_class = 1_000_000
    class_hits = sum(rng.randrange(32) == target_class for _ in range(n_class))
    p = 1/32
    z = (class_hits - n_class*p) / ((n_class*p*(1-p))**0.5)

    n_full = 2_000_000
    target256 = rng.getrandbits(256)
    full_hits = sum(
        1 for _ in range(n_full)
        if rng.randrange(32) == target_class and rng.getrandbits(256) == target256
    )

    n_small = 10_000_000
    target16 = rng.getrandbits(16)
    small_hits = sum(
        1 for _ in range(n_small)
        if rng.randrange(32) == target_class and rng.getrandbits(16) == target16
    )
    return {
        "seed": seed,
        "class_only": {
            "trials": n_class,
            "matches": class_hits,
            "rate": class_hits/n_class,
            "expected_rate": p,
            "z_approx": z,
        },
        "full_256bit_identity": {
            "trials": n_full,
            "matches": full_hits,
            "ideal_expected_per_trial": 1/(32*2**256),
        },
        "reduced_16bit_surrogate": {
            "trials": n_small,
            "matches": small_hits,
            "expected_matches": n_small/(32*2**16),
        },
    }

def run_all() -> dict[str, Any]:
    attacks = run_attack_sweep()
    mc = monte_carlo()
    return {
        "schema": "JANUS/genesis-proof-carrying-semantic-return-test/v0.3.0",
        "status": "PASS" if attacks["all_pass"] else "FAIL",
        "method": {
            "Fundamentum": "independent recomputation, explicit tamper attacks, full attack sweep; survival is not proof",
            "Genesis": "canonical SHA-256, previous-hash lineage, local sequence and append-only event model",
        },
        "attack_sweep": attacks,
        "monte_carlo": mc,
        "epistemic_boundary": "This suite validates a protocol/verifier against synthetic and adversarial records. It does not test a physical tachyon, FTL channel, precognition or retrocausal information transfer.",
        "physical_gate": "BLOCKED_NO_ESTABLISHED_CHANNEL",
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_all()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"JANUS_GENESIS_SEMANTIC_RETURN_VERIFIER = {report['status']}")
        sweep = report["attack_sweep"]
        print(f"ATTACK_SWEEP = {sweep['cases_correct']}/{sweep['cases_total']}")
        mc = report["monte_carlo"]
        print(f"CLASS_ONLY = {mc['class_only']['matches']}/{mc['class_only']['trials']}")
        print(f"FULL_256BIT_IDENTITY = {mc['full_256bit_identity']['matches']}/{mc['full_256bit_identity']['trials']}")
        print(f"REDUCED_16BIT_SURROGATE = {mc['reduced_16bit_surrogate']['matches']}/{mc['reduced_16bit_surrogate']['trials']}")
        print("PHYSICAL_RETROCAUSALITY = NOT_TESTED")
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
