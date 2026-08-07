#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SCHEMA = "JANUS/genesis-independent-future-gate/v0.4.0"
ZERO = "0" * 64


def canonical(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def h(v: Any) -> str:
    raw = v if isinstance(v, (bytes, bytearray)) else canonical(v)
    return hashlib.sha256(raw).hexdigest()


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def add_event(chain: list[dict[str, Any]], kind: str, payload: dict[str, Any], mono: int, coord: int) -> dict[str, Any]:
    unsigned = {
        "sequence": len(chain) + 1,
        "kind": kind,
        "monotonic_ns": mono,
        "coordinate_clock_ns": coord,
        "previous_hash": chain[-1]["event_hash"] if chain else ZERO,
        "payload": payload,
    }
    ev = {**unsigned, "event_hash": h(unsigned)}
    chain.append(ev)
    return ev


def verify_chain(chain: list[dict[str, Any]]) -> list[str]:
    fail: list[str] = []
    prev = ZERO
    prev_m = None
    for i, ev in enumerate(chain, 1):
        if ev.get("sequence") != i:
            fail.append(f"sequence:{i}")
        if ev.get("previous_hash") != prev:
            fail.append(f"previous_hash:{i}")
        unsigned = dict(ev)
        observed = unsigned.pop("event_hash", None)
        if observed != h(unsigned):
            fail.append(f"event_hash:{i}")
        m = ev.get("monotonic_ns")
        if not isinstance(m, int):
            fail.append(f"monotonic_type:{i}")
        elif prev_m is not None and m <= prev_m:
            fail.append(f"monotonic_order:{i}")
        if isinstance(m, int):
            prev_m = m
        prev = str(observed or "")
    return fail


@dataclass(frozen=True)
class TrustProfile:
    separate_process: bool
    separate_host_or_hardware: bool
    external_entropy_audit: bool
    externally_anchored_pre_return: bool

    @property
    def independent_future_admissible(self) -> bool:
        return self.separate_process and self.separate_host_or_hardware and self.external_entropy_audit and self.externally_anchored_pre_return


class Authority:
    """Synthetic signing authority for protocol tests.

    Its signature proves provenance only. Because the sandbox controls this object,
    it MUST NOT be treated as proof of unpredictability.
    """
    def __init__(self, seed: int = 1138):
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key()
        self.pub_raw = self.public.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        self.rng = random.Random(seed)
        self.seq = 0

    def pin(self) -> dict[str, Any]:
        return {"public_key_b64": b64(self.pub_raw), "public_key_sha256": h(self.pub_raw)}

    def assign(self, *, run_id: str, pre_hash: str, bits: int = 16, force_bundle: dict[str, Any] | None = None) -> dict[str, Any]:
        self.seq += 1
        if force_bundle is None:
            bundle = {
                "run_id": run_id,
                "semantic_class": self.rng.randrange(32),
                "payload_hex": f"{self.rng.getrandbits(bits):0{bits//4}x}",
                "nonce_hex": f"{self.rng.getrandbits(bits):0{bits//4}x}",
            }
        else:
            bundle = dict(force_bundle)
        unsigned = {
            "schema": "JANUS/entropy-receipt/v2",
            "authority_sequence": self.seq,
            "run_id": run_id,
            "request_pre_return_hash": pre_hash,
            "bundle": bundle,
            "bundle_sha256": h(bundle),
            "provenance_claim": "SIGNED_BY_SYNTHETIC_AUTHORITY",
            "unpredictability_claim": "NOT_PROVEN_BY_SIGNATURE",
        }
        return {**unsigned, "signature_b64": b64(self.private.sign(canonical(unsigned)))}


def verify_receipt(receipt: dict[str, Any], pin: dict[str, Any], expected_run: str, expected_pre_hash: str) -> list[str]:
    fail: list[str] = []
    try:
        pub_raw = unb64(str(pin.get("public_key_b64", "")))
        if h(pub_raw) != pin.get("public_key_sha256"):
            fail.append("pin_hash")
        unsigned = dict(receipt)
        sig = unb64(str(unsigned.pop("signature_b64", "")))
        Ed25519PublicKey.from_public_bytes(pub_raw).verify(sig, canonical(unsigned))
    except Exception:
        fail.append("signature")
    if receipt.get("run_id") != expected_run:
        fail.append("run_id")
    if receipt.get("request_pre_return_hash") != expected_pre_hash:
        fail.append("pre_return_binding")
    bundle = receipt.get("bundle")
    if not isinstance(bundle, dict) or receipt.get("bundle_sha256") != h(bundle):
        fail.append("bundle_digest")
    return fail


def event_one(chain: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    xs = [e for e in chain if e.get("kind") == kind]
    return xs[0] if len(xs) == 1 else None


def verify_transcript(chain: list[dict[str, Any]], trust: TrustProfile, epsilon: int = 100) -> dict[str, Any]:
    failures = [f"chain:{x}" for x in verify_chain(chain)]
    pin = event_one(chain, "AUTHORITY_PINNED")
    pre = event_one(chain, "PRE_RETURN_FROZEN")
    assign = event_one(chain, "TARGET_ASSIGNED")
    send = event_one(chain, "SEND")
    photon = event_one(chain, "PHOTON_RETURN")
    if any(x is None for x in (pin, pre, assign, send, photon)):
        failures.append("required_event_cardinality")
        return {"structural_candidate": False, "independent_future_candidate": False, "failures": failures, "trust_admissible": trust.independent_future_admissible}
    assert pin and pre and assign and send and photon

    seq = {e["kind"]: e["sequence"] for e in (pin, pre, assign, send, photon)}
    if not (seq["AUTHORITY_PINNED"] < seq["PRE_RETURN_FROZEN"] < seq["TARGET_ASSIGNED"] <= seq["SEND"] < seq["PHOTON_RETURN"]):
        failures.append("ordinary_acquisition_order")

    receipt = assign["payload"].get("receipt")
    if not isinstance(receipt, dict):
        failures.append("receipt_missing")
        receipt = {}
    failures += [f"receipt:{x}" for x in verify_receipt(receipt, pin["payload"], expected_run=str(send["payload"].get("bundle", {}).get("run_id", "")), expected_pre_hash=str(pre.get("event_hash", "")))]

    br = pre["payload"].get("bundle")
    ba = receipt.get("bundle")
    bs = send["payload"].get("bundle")
    if not (isinstance(br, dict) and br == ba == bs):
        failures.append("exact_bundle_identity")

    J = int(pre["coordinate_clock_ns"]) - int(send["coordinate_clock_ns"])
    P = int(photon["coordinate_clock_ns"]) - int(send["coordinate_clock_ns"])
    if J >= -epsilon:
        failures.append("negative_coordinate_interval_margin")
    if P <= epsilon:
        failures.append("photon_control_positive")

    structural = not failures
    independent = structural and trust.independent_future_admissible
    if independent:
        classification = "INDEPENDENT_FUTURE_CANDIDATE_REQUIRES_PHYSICAL_REPLICATION"
    elif structural:
        classification = "STRUCTURAL_MATCH_ONLY_ENTROPY_INDEPENDENCE_NOT_ESTABLISHED"
    else:
        classification = "REJECTED_BY_PROTOCOL"
    return {
        "structural_candidate": structural,
        "independent_future_candidate": independent,
        "classification": classification,
        "failures": failures,
        "recomputed_J_ns": J,
        "recomputed_P_gamma_ns": P,
        "trust_admissible": trust.independent_future_admissible,
        "trust_profile": trust.__dict__,
    }


def transcript(*, mode: str, seed: int = 1138) -> list[dict[str, Any]]:
    auth = Authority(seed)
    run = f"run-{mode}"
    chain: list[dict[str, Any]] = []
    add_event(chain, "AUTHORITY_PINNED", auth.pin(), 1000, 10000)

    if mode == "honest_null":
        pre_bundle = {"run_id": run, "semantic_class": 0, "payload_hex": "0000", "nonce_hex": "0000"}
        pre = add_event(chain, "PRE_RETURN_FROZEN", {"bundle": pre_bundle}, 2000, 10100)
        receipt = auth.assign(run_id=run, pre_hash=pre["event_hash"], bits=16)
    elif mode == "simulator_foreknowledge":
        future = {"run_id": run, "semantic_class": 7, "payload_hex": "a453", "nonce_hex": "6e40"}
        pre = add_event(chain, "PRE_RETURN_FROZEN", {"bundle": future}, 2000, 10100)
        receipt = auth.assign(run_id=run, pre_hash=pre["event_hash"], bits=16, force_bundle=future)
    elif mode == "backdated_after_send":
        auth2 = Authority(seed + 9)
        c: list[dict[str, Any]] = []
        add_event(c, "AUTHORITY_PINNED", auth2.pin(), 1000, 10000)
        future = {"run_id": run, "semantic_class": 3, "payload_hex": "abcd", "nonce_hex": "1234"}
        fake_hash = "f" * 64
        r = auth2.assign(run_id=run, pre_hash=fake_hash, force_bundle=future)
        add_event(c, "TARGET_ASSIGNED", {"receipt": r}, 2000, 10200)
        add_event(c, "SEND", {"bundle": future}, 3000, 11300)
        add_event(c, "PRE_RETURN_FROZEN", {"bundle": future}, 4000, 10100)
        add_event(c, "PHOTON_RETURN", {"control": "photon"}, 5000, 21300)
        return c
    else:
        raise ValueError(mode)

    add_event(chain, "TARGET_ASSIGNED", {"receipt": receipt}, 3000, 10200)
    add_event(chain, "SEND", {"bundle": receipt["bundle"]}, 4000, 11300)
    add_event(chain, "PHOTON_RETURN", {"control": "photon"}, 5000, 21300)
    return chain


def run_suite() -> dict[str, Any]:
    sandbox_trust = TrustProfile(True, False, False, False)
    ideal_external_trust = TrustProfile(True, True, True, True)
    cases: dict[str, Any] = {}

    honest = verify_transcript(transcript(mode="honest_null"), sandbox_trust)
    cases["honest_independent_forward_null"] = {
        **honest,
        "expected": "REJECTED_BY_PROTOCOL because independent future bytes do not match by construction",
        "correct": honest["classification"] == "REJECTED_BY_PROTOCOL" and "exact_bundle_identity" in honest["failures"],
    }

    forge = verify_transcript(transcript(mode="simulator_foreknowledge"), sandbox_trust)
    cases["simulator_foreknowledge_with_valid_signature"] = {
        **forge,
        "expected": "STRUCTURAL_MATCH_ONLY; must NOT promote to independent-future evidence",
        "correct": forge["structural_candidate"] and not forge["independent_future_candidate"],
    }

    ideal_gate = verify_transcript(transcript(mode="simulator_foreknowledge"), ideal_external_trust)
    cases["synthetic_gate_logic_with_hypothetical_external_trust"] = {
        **ideal_gate,
        "expected": "logic reaches candidate only when the external trust premises are asserted",
        "correct": ideal_gate["independent_future_candidate"],
        "epistemic_warning": "This is a truth-table/self-test of the gate, not physical evidence and not evidence that the synthetic authority was unpredictable.",
    }

    backdated = verify_transcript(transcript(mode="backdated_after_send"), sandbox_trust)
    cases["backdated_coordinate_timestamp"] = {
        **backdated,
        "expected": "REJECTED_BY_PROTOCOL",
        "correct": backdated["classification"] == "REJECTED_BY_PROTOCOL",
    }

    cases["compromised_authority_private_state"] = {
        "structurally_indistinguishable_from_valid_signed_transcript": True,
        "detectable_from_transcript_alone": False,
        "classification": "UNRESOLVED_TRUST_BOUNDARY",
        "required_mitigation": "organizational/hardware separation, audited entropy source, external append-only anchoring, independent replication",
        "correct": True,
    }

    all_pass = all(c.get("correct") is True for c in cases.values())
    return {
        "schema": SCHEMA,
        "status": "PASS" if all_pass else "FAIL",
        "cases_total": len(cases),
        "cases_correct": sum(c.get("correct") is True for c in cases.values()),
        "all_pass": all_pass,
        "cases": cases,
        "core_correction": "A signed receipt is a provenance primitive, not a proof of future unpredictability. Genesis therefore uses a two-tier verdict: structural candidate vs independent-future candidate.",
        "physical_boundary": "No transcript generated inside Genesis can by itself establish physical FTL/retrocausality; the independent-future grade requires external physical trust premises and then independent replication.",
    }


def main() -> int:
    argparse.ArgumentParser().parse_args()
    report = run_suite()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
