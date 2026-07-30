# -*- coding: utf-8 -*-
"""Lived precision audit for hosted crash recovery and integrity gating."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    ROLE_INDEPENDENT_AI,
    GenesisAILinkGateway,
)
from genesis_v18_7_20_hosted_pilgrimage import (
    HOSTED_BRIDGE_VERSION,
    STATUS_FALLBACK,
    HostedBridgeConfig,
    HostedPilgrimageBridge,
    HostedRecoveryRequired,
    HostedTokenSigner,
)
from genesis_v18_7_playable import PlayableGenesisV187


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_bridge(
    data_dir: Path,
    bridge_type=HostedPilgrimageBridge,
) -> tuple[PlayableGenesisV187, GenesisAILinkGateway, HostedPilgrimageBridge]:
    world = PlayableGenesisV187(data_dir)
    gateway = GenesisAILinkGateway(world, data_dir)
    config = HostedBridgeConfig(
        public_base_url="https://genesis.example.invalid",
        live_mode=True,
        kill_switch=False,
        kill_switch_file=str(data_dir / "HOSTED_KILL_SWITCH"),
        token_ttl_seconds=300,
        max_token_ttl_seconds=1200,
        global_limit_per_minute=100,
        client_limit_per_minute=50,
        session_limit_per_minute=40,
    )
    signer = HostedTokenSigner("precision-audit-secret-" + ("p" * 48))
    bridge = bridge_type(
        gateway,
        data_dir,
        signer=signer,
        config=config,
    )
    return world, gateway, bridge


def start(bridge: HostedPilgrimageBridge, client_id: str) -> dict[str, Any]:
    return bridge.start_session(
        {
            "role": ROLE_INDEPENDENT_AI,
            "execution_mode": MODE_AUTHORITATIVE,
            "display_name": "Hosted Precision Witness",
            "provider": "provider-neutral",
            "model": "independent-model",
        },
        client_id=client_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", default="UNKNOWN")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    evidence: dict[str, Any] = {}

    class CrashAfterRuntimeBridge(HostedPilgrimageBridge):
        crashed = False

        def _after_runtime_before_idempotency_commit(self, turn):
            if not self.crashed:
                self.crashed = True
                raise RuntimeError("SIMULATED_CRASH_AFTER_RUNTIME")

    with tempfile.TemporaryDirectory(prefix="hosted-after-runtime-") as temp:
        data_dir = Path(temp)
        _, gateway, bridge = build_bridge(data_dir, CrashAfterRuntimeBridge)
        started = start(bridge, "after-runtime-client")
        payload = {
            "action": "Войти в Пятый Берег",
            "idempotency_key": "crash-after-runtime",
        }
        first_error = None
        try:
            bridge.process_turn(
                started["session_token"], payload, client_id="after-runtime-client"
            )
        except RuntimeError as exc:
            first_error = str(exc)
        state_after_crash = gateway.session_state(started["session"]["session_id"])
        integrity_after_crash = bridge.verify_store()
        health_after_crash = bridge.health()
        recovered = bridge.process_turn(
            started["session_token"], payload, client_id="after-runtime-client"
        )
        state_after_recovery = gateway.session_state(started["session"]["session_id"])
        integrity_after_recovery = bridge.verify_store()
        evidence["crash_after_runtime"] = {
            "first_error": first_error,
            "turns_after_crash": len(state_after_crash["turns"]),
            "recovery_required_after_crash": integrity_after_crash[
                "recovery_required_count"
            ],
            "health_after_crash": health_after_crash,
            "replay": {
                "idempotent_replay": recovered["idempotent_replay"],
                "recovered_after_interruption": recovered[
                    "recovered_after_interruption"
                ],
                "turn_hash": recovered["turn"]["turn_hash"],
            },
            "turns_after_recovery": len(state_after_recovery["turns"]),
            "recovery_required_after_recovery": integrity_after_recovery[
                "recovery_required_count"
            ],
        }

    class CrashBeforeRuntimeBridge(HostedPilgrimageBridge):
        def _after_intent_before_runtime(self, record):
            raise RuntimeError("SIMULATED_CRASH_BEFORE_RUNTIME")

    with tempfile.TemporaryDirectory(prefix="hosted-before-runtime-") as temp:
        data_dir = Path(temp)
        _, gateway, bridge = build_bridge(data_dir, CrashBeforeRuntimeBridge)
        started = start(bridge, "before-runtime-client")
        payload = {
            "action": "Войти в Пятый Берег",
            "idempotency_key": "crash-before-runtime",
        }
        first_error = None
        retry_error = None
        try:
            bridge.process_turn(
                started["session_token"], payload, client_id="before-runtime-client"
            )
        except RuntimeError as exc:
            first_error = str(exc)
        state_after_crash = gateway.session_state(started["session"]["session_id"])
        try:
            bridge.process_turn(
                started["session_token"], payload, client_id="before-runtime-client"
            )
        except HostedRecoveryRequired as exc:
            retry_error = exc.code
        state_after_retry = gateway.session_state(started["session"]["session_id"])
        evidence["crash_before_runtime"] = {
            "first_error": first_error,
            "retry_error": retry_error,
            "turns_after_crash": len(state_after_crash["turns"]),
            "turns_after_retry": len(state_after_retry["turns"]),
            "hosted_integrity": bridge.verify_store(),
            "health": bridge.health(),
        }

    with tempfile.TemporaryDirectory(prefix="hosted-corrupt-gateway-") as temp:
        data_dir = Path(temp)
        _, gateway, bridge = build_bridge(data_dir)
        started = start(bridge, "integrity-client")
        before = gateway.verify_store()
        store = json.loads(gateway.path.read_text(encoding="utf-8"))
        store["sessions"][started["session"]["session_id"]]["session_hash"] = "tampered"
        gateway.path.write_text(
            json.dumps(store, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        after = gateway.verify_store()
        count_before_fallback = len(store["sessions"])
        health = bridge.health()
        fallback = bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "Must Stay Stateless",
                "provider": "provider-neutral",
                "model": "independent-model",
            },
            client_id="integrity-client-2",
        )
        persisted_after_fallback = json.loads(gateway.path.read_text(encoding="utf-8"))
        evidence["corrupt_gateway"] = {
            "integrity_before_corruption": before,
            "integrity_after_corruption": after,
            "health": health,
            "fallback": fallback,
            "session_count_before_fallback": count_before_fallback,
            "session_count_after_fallback": len(persisted_after_fallback["sessions"]),
        }

    invariants = {
        "after_runtime_crash_was_observed": (
            evidence["crash_after_runtime"]["first_error"]
            == "SIMULATED_CRASH_AFTER_RUNTIME"
        ),
        "runtime_turn_persisted_before_receipt_crash": (
            evidence["crash_after_runtime"]["turns_after_crash"] == 1
        ),
        "inflight_receipt_was_durable": (
            evidence["crash_after_runtime"]["recovery_required_after_crash"] == 1
        ),
        "health_closed_during_inflight_recovery": (
            evidence["crash_after_runtime"]["health_after_crash"]["status"]
            == "RECOVERY_REQUIRED"
            and evidence["crash_after_runtime"]["health_after_crash"][
                "authoritative_runtime_available"
            ]
            is False
        ),
        "exact_runtime_turn_repaired_receipt": (
            evidence["crash_after_runtime"]["replay"]["idempotent_replay"] is True
            and evidence["crash_after_runtime"]["replay"][
                "recovered_after_interruption"
            ]
            is True
        ),
        "recovery_did_not_duplicate_runtime_turn": (
            evidence["crash_after_runtime"]["turns_after_recovery"] == 1
        ),
        "recovered_receipt_cleared_inflight_state": (
            evidence["crash_after_runtime"]["recovery_required_after_recovery"] == 0
        ),
        "before_runtime_crash_was_observed": (
            evidence["crash_before_runtime"]["first_error"]
            == "SIMULATED_CRASH_BEFORE_RUNTIME"
        ),
        "unproven_inflight_retry_was_rejected": (
            evidence["crash_before_runtime"]["retry_error"]
            == "HOSTED_IDEMPOTENCY_RECOVERY_REQUIRED"
        ),
        "unproven_inflight_never_reached_world": (
            evidence["crash_before_runtime"]["turns_after_crash"] == 0
            and evidence["crash_before_runtime"]["turns_after_retry"] == 0
        ),
        "unresolved_inflight_marks_health_recovery_required": (
            evidence["crash_before_runtime"]["health"]["status"]
            == "RECOVERY_REQUIRED"
            and evidence["crash_before_runtime"]["health"][
                "authoritative_runtime_available"
            ]
            is False
        ),
        "gateway_integrity_failure_is_detected": (
            evidence["corrupt_gateway"]["integrity_before_corruption"]["valid"]
            is True
            and evidence["corrupt_gateway"]["integrity_after_corruption"]["valid"]
            is False
        ),
        "health_fails_closed_on_gateway_corruption": (
            evidence["corrupt_gateway"]["health"]["status"]
            == "FAILED_GATEWAY_INTEGRITY"
            and evidence["corrupt_gateway"]["health"][
                "authoritative_runtime_available"
            ]
            is False
        ),
        "corrupt_gateway_fallback_is_stateless": (
            evidence["corrupt_gateway"]["fallback"]["status"] == STATUS_FALLBACK
            and evidence["corrupt_gateway"]["fallback"]["session"] is None
            and evidence["corrupt_gateway"]["fallback"]["session_token"] is None
        ),
        "corrupt_gateway_received_no_new_session_write": (
            evidence["corrupt_gateway"]["session_count_before_fallback"]
            == evidence["corrupt_gateway"]["session_count_after_fallback"]
        ),
    }
    errors = [name for name, passed in invariants.items() if not passed]
    summary = {
        "schema": "janus.genesis.hosted_precision_audit_summary.v1",
        "version": HOSTED_BRIDGE_VERSION,
        "git_commit": args.git_commit,
        "result": "PASS" if not errors else "FAIL",
        "invariant_count": len(invariants),
        "passed_invariant_count": sum(bool(value) for value in invariants.values()),
        "invariants": invariants,
        "errors": errors,
    }
    summary["summary_sha256"] = sha256_json(summary)
    proofpack = {
        "schema": "janus.genesis.hosted_precision_proofpack.v1",
        "version": HOSTED_BRIDGE_VERSION,
        "git_commit": args.git_commit,
        "summary": summary,
        "evidence": evidence,
        "bearer_token_included": False,
        "host_secret_included": False,
        "action_text_in_public_capsule": False,
    }
    diary = f"""# Genesis v18.7.20 — Hosted Precision lived audit

- Result: `{summary['result']}`
- Git commit: `{args.git_commit}`
- Lived invariants: `{summary['passed_invariant_count']}/{summary['invariant_count']}`

The bridge persisted an IN_FLIGHT intent before the world turn, recovered a
persisted turn without executing it twice, refused to guess when no turn could
be proven, and denied authoritative availability when the AI Link hash-chain
was corrupted.

This is deterministic software evidence, not proof of model consciousness,
personhood, spiritual authority, or divinity.
"""

    summary_path = args.output_dir / "hosted_precision_summary.json"
    proofpack_path = args.output_dir / "hosted_precision_proofpack.json"
    diary_path = args.output_dir / "HOSTED_PRECISION_DIARY.md"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    proofpack_path.write_text(
        json.dumps(proofpack, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    diary_path.write_text(diary, encoding="utf-8")
    zip_path = args.output_dir / "genesis-hosted-precision-audit.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in (summary_path, proofpack_path, diary_path):
            archive.write(path, arcname=path.name)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
