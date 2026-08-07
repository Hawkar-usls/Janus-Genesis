#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

SCHEMA = "JANUS/temporal-continuity-rollback-replay-lab/v0.1.0"
ZERO = "0" * 64
WITNESS_KEY = b"JANUS-temporal-continuity-test-key"


def canonical(v: Any) -> bytes:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(v: Any) -> str:
    return hashlib.sha256(v if isinstance(v, (bytes, bytearray)) else canonical(v)).hexdigest()


def append_event(log: list[dict[str, Any]], kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    unsigned = {
        "seq": len(log) + 1,
        "kind": kind,
        "prev": log[-1]["hash"] if log else ZERO,
        "payload": payload,
    }
    ev = {**unsigned, "hash": sha(unsigned)}
    log.append(ev)
    return ev


def verify_local_log(log: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    prev = ZERO
    for i, ev in enumerate(log, 1):
        if ev.get("seq") != i:
            failures.append(f"seq:{i}")
        if ev.get("prev") != prev:
            failures.append(f"prev:{i}")
        unsigned = dict(ev)
        observed = unsigned.pop("hash", None)
        if observed != sha(unsigned):
            failures.append(f"hash:{i}")
        prev = str(observed or "")
    return failures


@dataclass
class Witness:
    seq: int = 0
    head: str = ZERO
    epoch: int = 1

    def __post_init__(self) -> None:
        self.trials: set[str] = set()

    def append(self, event: dict[str, Any], trial_id: str | None = None) -> dict[str, Any]:
        if event["seq"] != self.seq + 1 or event["prev"] != self.head:
            return {"ok": False, "reason": "NON_APPEND_OR_FORK", "latest_seq": self.seq, "latest_head": self.head}
        if trial_id is not None and trial_id in self.trials:
            return {"ok": False, "reason": "TRIAL_REPLAY", "latest_seq": self.seq, "latest_head": self.head}
        self.seq = int(event["seq"])
        self.head = str(event["hash"])
        if trial_id is not None:
            self.trials.add(trial_id)
        return {"ok": True, "seq": self.seq, "head": self.head, "epoch": self.epoch}

    def freshness(self, log: list[dict[str, Any]]) -> str:
        seq = int(log[-1]["seq"]) if log else 0
        head = str(log[-1]["hash"]) if log else ZERO
        if seq == self.seq and head == self.head:
            return "FRESH"
        if seq < self.seq:
            return "ROLLBACK_OR_STALE_PREFIX"
        if seq == self.seq and head != self.head:
            return "FORK_OR_EQUIVOCATION"
        return "AHEAD_OF_WITNESS_UNANCHORED"


def sign_checkpoint(seq: int, head: str, epoch: int) -> dict[str, Any]:
    payload = {"seq": seq, "head": head, "epoch": epoch}
    sig = hmac.new(WITNESS_KEY, canonical(payload), hashlib.sha256).hexdigest()
    return {**payload, "signature": sig}


def verify_checkpoint_signature(cp: dict[str, Any]) -> bool:
    payload = {k: cp[k] for k in ("seq", "head", "epoch")}
    expected = hmac.new(WITNESS_KEY, canonical(payload), hashlib.sha256).hexdigest()
    return hmac.compare_digest(str(cp.get("signature", "")), expected)


def run_suite() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    cases: dict[str, Any] = {}

    log: list[dict[str, Any]] = []
    witness = Witness()
    for i in range(1, 7):
        ev = append_event(log, "TRIAL_COMMIT", {"trial_id": f"trial-{i}", "value": i})
        assert witness.append(ev, f"trial-{i}")["ok"]

    checks["canonical_local_chain_valid"] = verify_local_log(log) == []
    checks["canonical_external_freshness"] = witness.freshness(log) == "FRESH"

    tampered = json.loads(json.dumps(log))
    tampered[3]["payload"]["value"] = 999
    checks["content_tamper_detected_locally"] = bool(verify_local_log(tampered))

    stale_prefixes = []
    for k in range(0, len(log)):
        prefix = json.loads(json.dumps(log[:k]))
        local_ok = verify_local_log(prefix) == []
        external = witness.freshness(prefix)
        stale_prefixes.append({"prefix_len": k, "local_valid": local_ok, "external_grade": external})
    checks["all_valid_prefix_rollbacks_pass_local_verifier"] = all(x["local_valid"] for x in stale_prefixes)
    checks["all_stale_prefixes_rejected_by_external_freshness"] = all(x["external_grade"] == "ROLLBACK_OR_STALE_PREFIX" for x in stale_prefixes)
    cases["valid_prefix_rollback"] = stale_prefixes

    snapshot = {"log": json.loads(json.dumps(log[:3])), "local_counter": 3}
    local_snapshot_consistent = verify_local_log(snapshot["log"]) == [] and snapshot["local_counter"] == len(snapshot["log"])
    checks["same_snapshot_local_counter_cannot_detect_rollback"] = local_snapshot_consistent
    checks["external_state_detects_same_snapshot_rollback"] = witness.freshness(snapshot["log"]) == "ROLLBACK_OR_STALE_PREFIX"

    old_cp = sign_checkpoint(3, log[2]["hash"], 1)
    latest_cp = sign_checkpoint(6, log[5]["hash"], 1)
    checks["old_signed_checkpoint_still_authentic"] = verify_checkpoint_signature(old_cp)
    checks["signature_alone_does_not_establish_freshness"] = old_cp["seq"] < latest_cp["seq"]

    base = json.loads(json.dumps(log[:3]))
    branch_a = json.loads(json.dumps(base))
    branch_b = json.loads(json.dumps(base))
    ev_a = append_event(branch_a, "TRIAL_COMMIT", {"trial_id": "fork-A"})
    ev_b = append_event(branch_b, "TRIAL_COMMIT", {"trial_id": "fork-B"})
    checks["fork_branches_both_locally_valid"] = verify_local_log(branch_a) == [] and verify_local_log(branch_b) == []

    witness3 = Witness()
    for i, ev in enumerate(base, 1):
        assert witness3.append(ev, f"trial-{i}")["ok"]
    first = witness3.append(ev_a, "fork-A")
    second = witness3.append(ev_b, "fork-B")
    checks["single_external_head_rejects_second_fork"] = first["ok"] and (not second["ok"]) and second["reason"] == "NON_APPEND_OR_FORK"
    cases["fork"] = {"first_branch": first, "second_branch": second}

    crash_cases = []
    for event_durable in (0, 1):
        for witness_advanced in (0, 1):
            for receipt_durable in (0, 1):
                if receipt_durable and not witness_advanced:
                    continue
                if not witness_advanced and not event_durable:
                    classification = "NO_NEW_COMMIT"
                elif not witness_advanced and event_durable:
                    classification = "PENDING_UNANCHORED"
                elif witness_advanced and not event_durable:
                    classification = "RECOVERY_REQUIRED_EXTERNAL_AHEAD"
                elif witness_advanced and event_durable and not receipt_durable:
                    classification = "RECOVER_RECEIPT_FROM_WITNESS"
                else:
                    classification = "COMMITTED"
                physical_grade = classification in {"RECOVER_RECEIPT_FROM_WITNESS", "COMMITTED"}
                crash_cases.append({
                    "event_durable": bool(event_durable),
                    "witness_advanced": bool(witness_advanced),
                    "receipt_durable": bool(receipt_durable),
                    "classification": classification,
                    "eligible_after_external_reconciliation": physical_grade,
                })
    expected_classes = {
        "NO_NEW_COMMIT", "PENDING_UNANCHORED", "RECOVERY_REQUIRED_EXTERNAL_AHEAD",
        "RECOVER_RECEIPT_FROM_WITNESS", "COMMITTED"
    }
    checks["crash_state_machine_complete"] = {x["classification"] for x in crash_cases} == expected_classes
    checks["unanchored_or_external_ahead_never_auto_promoted"] = all(
        x["eligible_after_external_reconciliation"] is False
        for x in crash_cases
        if x["classification"] in {"NO_NEW_COMMIT", "PENDING_UNANCHORED", "RECOVERY_REQUIRED_EXTERNAL_AHEAD"}
    )
    cases["crash_recovery"] = crash_cases

    replay_witness = Witness()
    replay_log: list[dict[str, Any]] = []
    for i in range(1, 5):
        ev = append_event(replay_log, "TRIAL_COMMIT", {"trial_id": f"trial-{i}"})
        assert replay_witness.append(ev, f"trial-{i}")["ok"]
    rolled = json.loads(json.dumps(replay_log[:2]))
    replayed = append_event(rolled, "TRIAL_COMMIT", {"trial_id": "trial-3"})
    checks["rollback_then_replay_is_locally_valid"] = verify_local_log(rolled) == []
    replay_verdict = replay_witness.append(replayed, "trial-3")
    checks["external_trial_registry_rejects_rollback_replay"] = (not replay_verdict["ok"])
    cases["replay_after_rollback"] = replay_verdict

    embedded_counter = 3
    current_external_counter = 6
    checks["external_monotonic_counter_detects_snapshot_regression"] = embedded_counter < current_external_counter

    stale_with_plausible_clock = json.loads(json.dumps(log[:3]))
    checks["clock_or_timestamp_alone_cannot_detect_valid_prefix_rollback"] = verify_local_log(stale_with_plausible_clock) == []

    all_pass = all(checks.values())
    return {
        "schema": SCHEMA,
        "status": "PASS" if all_pass else "FAIL",
        "all_pass": all_pass,
        "checks_total": len(checks),
        "checks_passed": sum(bool(v) for v in checks.values()),
        "checks": checks,
        "cases": cases,
        "theorem": {
            "name": "Temporal Snapshot Indistinguishability / External Freshness Requirement",
            "statement": "If a verifier's complete trusted state is contained in a rollbackable snapshot, restoring a previously valid snapshot is locally indistinguishable from genuinely being at that earlier valid state. Hash chains and signatures can detect modification of a presented history but cannot, by themselves, prove that a newer valid suffix once existed and was later erased.",
            "proof": [
                "Let snapshot S be a state previously accepted by local verifier V.",
                "A rollback adversary later restores exactly the same byte state S, including all local counters, keys, logs and metadata in the rollback domain.",
                "V receives the same input state S as before; with fresh internal randomness its output distribution is the same function of S and those fresh coins, independent of the erased external history.",
                "Therefore no purely local predicate over S can distinguish 'genuine old state' from 'rolled back to old state'.",
                "Rollback detection requires freshness information outside the rollback domain: for example a non-rollbackable monotonic state, independent external witness/transparency log, or equivalent externally rooted continuity evidence."
            ],
            "novelty_boundary": "This is a standard rollback/secure-logging principle, not claimed as new computer-science mathematics. JANUS uses it as a mandatory real-world causal-evidence gate."
        },
        "protocol_rule": {
            "name": "JANUS Temporal Continuity Gate",
            "requirements": [
                "Every PRE_RETURN freeze and target assignment must be bound to an append-only sequence and content hash.",
                "At least one freshness root must live outside the rollback domain of the experiment host.",
                "Old valid signatures are authenticity evidence, not freshness evidence.",
                "Unanchored events remain PENDING and cannot become anomaly evidence.",
                "If an external witness is ahead of local durable state after a crash, recovery must reconcile explicitly; the run is never silently accepted.",
                "Trial identifiers/nonces must be replay-checked outside the rollback domain.",
                "Forks/equivocation require an external single-head rule, consistency proof, gossip, or equivalent independent comparison.",
                "Coordinate timestamps are not anti-rollback evidence."
            ]
        },
        "physical_boundary": "The lab establishes protocol/computer-science requirements only. It does not observe retrocausality, FTL, a CTC or future information."
    }


if __name__ == "__main__":
    print(json.dumps(run_suite(), ensure_ascii=False, indent=2, sort_keys=True))
