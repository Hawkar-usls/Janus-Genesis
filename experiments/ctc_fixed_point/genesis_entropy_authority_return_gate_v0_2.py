#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import multiprocessing as mp
import secrets
import time
from dataclasses import dataclass
from typing import Any

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
except Exception as exc:
    raise SystemExit(
        "This isolated experiment requires the 'cryptography' package for Ed25519 receipts."
    ) from exc

ZERO_HASH = "0" * 64
SCHEMA = "JANUS/genesis-entropy-authority-return-gate/v0.2.0"

def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def sha256(value: Any) -> str:
    return sha256_bytes(canonical(value))

def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")

def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))

def append_event(chain: list[dict[str, Any]], kind: str, payload: dict[str, Any], *, monotonic_ns: int, coordinate_clock_ns: int) -> dict[str, Any]:
    unsigned = {
        "sequence": len(chain) + 1,
        "kind": kind,
        "payload": payload,
        "monotonic_ns": int(monotonic_ns),
        "coordinate_clock_ns": int(coordinate_clock_ns),
        "previous_hash": chain[-1]["event_hash"] if chain else ZERO_HASH,
    }
    event = {**unsigned, "event_hash": sha256(unsigned)}
    chain.append(event)
    return event

def verify_chain(chain: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    prev = ZERO_HASH
    prev_mono: int | None = None
    for i, ev in enumerate(chain, 1):
        if ev.get("sequence") != i:
            failures.append(f"sequence:{i}")
        if ev.get("previous_hash") != prev:
            failures.append(f"previous_hash:{i}")
        unsigned = dict(ev)
        observed = unsigned.pop("event_hash", None)
        if observed != sha256(unsigned):
            failures.append(f"event_hash:{i}")
        mono = ev.get("monotonic_ns")
        if not isinstance(mono, int):
            failures.append(f"monotonic_type:{i}")
        elif prev_mono is not None and mono <= prev_mono:
            failures.append(f"monotonic_order:{i}")
        if isinstance(mono, int):
            prev_mono = mono
        prev = str(observed or "")
    return not failures, failures

def make_bundle(run_id: str, payload_bits: int = 128, nonce_bits: int = 128) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "semantic_class": secrets.randbelow(32),
        "payload_hex": secrets.token_hex(payload_bits // 8),
        "nonce_hex": secrets.token_hex(nonce_bits // 8),
    }

def authority_worker(conn) -> None:
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    public_raw = public.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    conn.send({
        "type": "READY",
        "public_key_b64": b64(public_raw),
        "public_key_sha256": sha256_bytes(public_raw),
    })
    sequence = 1
    while True:
        msg = conn.recv()
        if msg.get("type") == "STOP":
            return
        if msg.get("type") != "ASSIGN":
            conn.send({"type": "ERROR", "error": "unsupported request"})
            continue
        run_id = str(msg["run_id"])
        anchor_hash = str(msg["anchor_hash"])
        bits = int(msg.get("bits", 128))
        bundle = make_bundle(run_id, bits, bits)
        receipt_unsigned = {
            "schema": "JANUS/entropy-authority-receipt/v1",
            "authority_sequence": sequence,
            "run_id": run_id,
            "request_anchor_hash": anchor_hash,
            "generated_monotonic_ns": time.monotonic_ns(),
            "bundle": bundle,
            "bundle_sha256": sha256(bundle),
        }
        signature = private.sign(canonical(receipt_unsigned))
        conn.send({"type": "ASSIGNMENT", "receipt": {**receipt_unsigned, "signature_b64": b64(signature)}})
        sequence += 1

class EntropyAuthority:
    def __init__(self) -> None:
        parent, child = mp.Pipe()
        self._conn = parent
        self._proc = mp.Process(target=authority_worker, args=(child,), daemon=True)
        self._proc.start()
        ready = self._conn.recv()
        if ready.get("type") != "READY":
            raise RuntimeError("authority failed to initialize")
        self.public_key_b64 = ready["public_key_b64"]
        self.public_key_sha256 = ready["public_key_sha256"]

    def assign(self, *, run_id: str, anchor_hash: str, bits: int = 128) -> dict[str, Any]:
        self._conn.send({"type": "ASSIGN", "run_id": run_id, "anchor_hash": anchor_hash, "bits": bits})
        msg = self._conn.recv()
        if msg.get("type") != "ASSIGNMENT":
            raise RuntimeError(msg)
        return msg["receipt"]

    def close(self) -> None:
        try:
            self._conn.send({"type": "STOP"})
        except Exception:
            pass
        self._proc.join(timeout=2)

def verify_receipt(receipt: dict[str, Any], *, pinned_public_key_b64: str, pinned_public_key_sha256: str, expected_run_id: str, expected_anchor_hash: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    try:
        public_raw = unb64(pinned_public_key_b64)
    except Exception:
        return False, ["public_key_decode"]
    if sha256_bytes(public_raw) != pinned_public_key_sha256:
        failures.append("public_key_pin_hash")
    unsigned = dict(receipt)
    sig_text = unsigned.pop("signature_b64", "")
    try:
        signature = unb64(sig_text)
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature, canonical(unsigned))
    except Exception:
        failures.append("receipt_signature")
    if receipt.get("run_id") != expected_run_id:
        failures.append("receipt_run_id")
    if receipt.get("request_anchor_hash") != expected_anchor_hash:
        failures.append("receipt_anchor")
    bundle = receipt.get("bundle")
    if not isinstance(bundle, dict) or receipt.get("bundle_sha256") != sha256(bundle):
        failures.append("receipt_bundle_digest")
    return not failures, failures

@dataclass(frozen=True)
class Verdict:
    candidate: bool
    failed_checks: list[str]
    recomputed_J_ns: int | None

def verify_trial(chain: list[dict[str, Any]]) -> Verdict:
    checks: list[str] = []
    chain_ok, chain_fail = verify_chain(chain)
    if not chain_ok:
        checks.extend(f"chain:{x}" for x in chain_fail)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for ev in chain:
        by_kind.setdefault(str(ev.get("kind")), []).append(ev)
    def one(kind: str) -> dict[str, Any] | None:
        xs = by_kind.get(kind, [])
        if len(xs) != 1:
            checks.append(f"exactly_one:{kind}")
            return None
        return xs[0]
    pin = one("AUTHORITY_PINNED")
    pre = one("PRE_RETURN_FROZEN")
    assign = one("TARGET_ASSIGNED")
    send = one("SEND")
    photon = one("PHOTON_RETURN")
    if any(x is None for x in (pin, pre, assign, send, photon)):
        return Verdict(False, checks, None)
    order = {ev["kind"]: ev["sequence"] for ev in (pin, pre, assign, send, photon)}
    if not (order["AUTHORITY_PINNED"] < order["PRE_RETURN_FROZEN"] < order["TARGET_ASSIGNED"] <= order["SEND"] < order["PHOTON_RETURN"]):
        checks.append("event_order")
    pin_payload = pin["payload"]
    receipt = assign["payload"].get("authority_receipt")
    if not isinstance(receipt, dict):
        checks.append("authority_receipt_present")
    else:
        receipt_ok, receipt_fail = verify_receipt(
            receipt,
            pinned_public_key_b64=str(pin_payload.get("public_key_b64", "")),
            pinned_public_key_sha256=str(pin_payload.get("public_key_sha256", "")),
            expected_run_id=str(send["payload"].get("bundle", {}).get("run_id", "")),
            expected_anchor_hash=str(pre.get("event_hash", "")),
        )
        if not receipt_ok:
            checks.extend(f"receipt:{x}" for x in receipt_fail)
    B_R = pre["payload"].get("bundle")
    B_A = receipt.get("bundle") if isinstance(receipt, dict) else None
    B_S = send["payload"].get("bundle")
    if not (isinstance(B_R, dict) and B_R == B_A == B_S):
        checks.append("exact_bundle_identity")
    try:
        J = int(pre["coordinate_clock_ns"]) - int(send["coordinate_clock_ns"])
        P = int(photon["coordinate_clock_ns"]) - int(send["coordinate_clock_ns"])
    except Exception:
        J = None
        P = None
        checks.append("clock_parse")
    if J is None or J >= -100:
        checks.append("negative_J_margin")
    if P is None or P <= 100:
        checks.append("photon_positive_margin")
    return Verdict(not checks, checks, J)

def make_honest_trial(bits: int = 16, *, force_match: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    auth = EntropyAuthority()
    try:
        run_id = "entropy-honest"
        chain: list[dict[str, Any]] = []
        append_event(chain, "AUTHORITY_PINNED", {"public_key_b64": auth.public_key_b64, "public_key_sha256": auth.public_key_sha256}, monotonic_ns=1_000, coordinate_clock_ns=10_000)
        pre_bundle = make_bundle(run_id, bits, bits)
        pre = append_event(chain, "PRE_RETURN_FROZEN", {"bundle": pre_bundle}, monotonic_ns=2_000, coordinate_clock_ns=10_100)
        receipt = auth.assign(run_id=run_id, anchor_hash=pre["event_hash"], bits=bits)
        if force_match:
            pre["payload"]["bundle"] = receipt["bundle"]
            unsigned = dict(pre); unsigned.pop("event_hash", None)
            pre["event_hash"] = sha256(unsigned)
        append_event(chain, "TARGET_ASSIGNED", {"authority_receipt": receipt}, monotonic_ns=3_000, coordinate_clock_ns=10_200)
        append_event(chain, "SEND", {"bundle": receipt["bundle"]}, monotonic_ns=4_000, coordinate_clock_ns=11_200)
        append_event(chain, "PHOTON_RETURN", {"control": "photon"}, monotonic_ns=5_000, coordinate_clock_ns=21_200)
        return chain, receipt
    finally:
        auth.close()

def oracle_peek_without_authority_proof() -> dict[str, Any]:
    B = make_bundle("oracle-peek", 16, 16)
    return {
        "bundle": B,
        "structurally_possible_to_place_before_assignment": True,
        "problem": "Without an external provenance receipt, a verifier cannot distinguish real preexistence from simulator foreknowledge."
    }

def attack_suite() -> dict[str, Any]:
    results: dict[str, Any] = {}
    honest, receipt = make_honest_trial(bits=16)
    v = verify_trial(honest)
    results["honest_independent_entropy_no_match"] = {"candidate": v.candidate, "failed_checks": v.failed_checks, "expected": False, "correct": not v.candidate and "exact_bundle_identity" in v.failed_checks}
    forced, _ = make_honest_trial(bits=16, force_match=True)
    v = verify_trial(forced)
    results["mutate_pre_return_after_authority_assignment"] = {"candidate": v.candidate, "failed_checks": v.failed_checks, "expected": False, "correct": not v.candidate}
    chain, receipt = make_honest_trial(bits=16)
    fake_key = Ed25519PrivateKey.generate()
    target_event = next(ev for ev in chain if ev["kind"] == "TARGET_ASSIGNED")
    forged = dict(target_event["payload"]["authority_receipt"])
    unsigned = dict(forged); unsigned.pop("signature_b64", None)
    forged["signature_b64"] = b64(fake_key.sign(canonical(unsigned)))
    target_event["payload"]["authority_receipt"] = forged
    for idx in range(chain.index(target_event), len(chain)):
        chain[idx]["previous_hash"] = chain[idx-1]["event_hash"] if idx else ZERO_HASH
        u = dict(chain[idx]); u.pop("event_hash", None)
        chain[idx]["event_hash"] = sha256(u)
    v = verify_trial(chain)
    results["wrong_authority_key_forgery"] = {"candidate": v.candidate, "failed_checks": v.failed_checks, "expected": False, "correct": not v.candidate and any("receipt_signature" in x for x in v.failed_checks)}
    chain, receipt = make_honest_trial(bits=16)
    pre = next(ev for ev in chain if ev["kind"] == "PRE_RETURN_FROZEN")
    pre["payload"]["tag"] = "different-anchor"
    idx = chain.index(pre)
    for j in range(idx, len(chain)):
        chain[j]["previous_hash"] = chain[j-1]["event_hash"] if j else ZERO_HASH
        u = dict(chain[j]); u.pop("event_hash", None)
        chain[j]["event_hash"] = sha256(u)
    v = verify_trial(chain)
    results["receipt_replay_on_changed_anchor"] = {"candidate": v.candidate, "failed_checks": v.failed_checks, "expected": False, "correct": not v.candidate and any("receipt_anchor" in x for x in v.failed_checks)}
    auth = EntropyAuthority()
    try:
        run_id = "early-query"
        chain = []
        append_event(chain, "AUTHORITY_PINNED", {"public_key_b64": auth.public_key_b64, "public_key_sha256": auth.public_key_sha256}, monotonic_ns=1_000, coordinate_clock_ns=10_000)
        dummy = append_event(chain, "DUMMY_ANCHOR", {}, monotonic_ns=2_000, coordinate_clock_ns=10_050)
        receipt = auth.assign(run_id=run_id, anchor_hash=dummy["event_hash"], bits=16)
        append_event(chain, "TARGET_ASSIGNED", {"authority_receipt": receipt}, monotonic_ns=3_000, coordinate_clock_ns=10_100)
        append_event(chain, "PRE_RETURN_FROZEN", {"bundle": receipt["bundle"]}, monotonic_ns=4_000, coordinate_clock_ns=9_000)
        append_event(chain, "SEND", {"bundle": receipt["bundle"]}, monotonic_ns=5_000, coordinate_clock_ns=11_000)
        append_event(chain, "PHOTON_RETURN", {"control": "photon"}, monotonic_ns=6_000, coordinate_clock_ns=21_000)
        v = verify_trial(chain)
        results["query_authority_before_pre_return_then_backdate"] = {"candidate": v.candidate, "failed_checks": v.failed_checks, "expected": False, "correct": not v.candidate and "event_order" in v.failed_checks}
    finally:
        auth.close()
    return {
        "all_pass": all(item["correct"] for item in results.values()),
        "cases_total": len(results),
        "cases_correct": sum(bool(item["correct"]) for item in results.values()),
        "cases": results,
        "oracle_peek_boundary": oracle_peek_without_authority_proof(),
    }

def report() -> dict[str, Any]:
    suite = attack_suite()
    return {
        "schema": SCHEMA,
        "status": "PASS" if suite["all_pass"] else "FAIL",
        "attack_suite": suite,
        "upgrade_from_v0_3": {
            "old_weakness": "rng_independence_audited was a self-attested boolean and could be lied about by an oracle-peek simulator.",
            "new_requirement": "Target assignment must carry an Ed25519-signed receipt from a public key pinned before PRE_RETURN. The receipt binds run_id, the exact PRE_RETURN event hash, authority sequence, generated bundle and bundle digest.",
            "remaining_boundary": "If the candidate process controls or compromises the entropy authority/private key, software alone cannot prove unpredictability. Real experiments need organizational/hardware trust separation."
        },
        "epistemic_boundary": {
            "software_entropy_provenance_architecture_tested": True,
            "physical_retrocausality_tested": False,
            "physical_future_bits_preexistence_observed": False
        }
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    args = parser.parse_args()
    out = report()
    text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return 0 if out["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
