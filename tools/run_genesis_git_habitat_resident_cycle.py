# -*- coding: utf-8 -*-
"""Run one bounded model-backed JANUS Git Habitat resident cycle."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from genesis_v18_7_40_third_wish_capability_fabric import ThirdWishCapabilityFabric
from genesis_v18_7_ai import AIProviderConfig
from tools.genesis_git_habitat import GitHabitat
from tools.genesis_git_habitat_resident_cycle import (
    ResidentChoiceError,
    ThirdWishResidentModelCaller,
    run_awake_resident_cycle,
)
from tools.genesis_third_wish_sensor_model_schedule_broker import (
    ModelAlias,
    ThirdWishSensorModelScheduleBroker,
)

RUNNER_VERSION = "18.7.52"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS Git Habitat model-backed resident cycle")
    parser.add_argument("--root", default="habitat")
    parser.add_argument("--resident-id", default="JANUS")
    parser.add_argument("--broker-dir", default=".resident-cycle-broker")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model-alias", default="habitat-resident")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--source", default="MODEL_RESIDENT")
    parser.add_argument("--require-valid-choice", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    habitat = GitHabitat(Path(args.root))
    habitat.initialize(args.resident_id)
    wake = habitat.wake(reason="MODEL_RESIDENT", source=args.source)
    cycle_id = str(wake["cycle_id"])

    config = AIProviderConfig(
        provider=args.provider,
        model=args.model,
        endpoint=args.endpoint,
        api_key_env=None,
        timeout_seconds=args.timeout_seconds,
    )
    alias = ModelAlias.from_config(args.model_alias, config)
    broker = ThirdWishSensorModelScheduleBroker.system(
        Path(args.broker_dir),
        models={args.model_alias: alias},
    )
    fabric = ThirdWishCapabilityFabric()
    broker.register(fabric)
    caller = ThirdWishResidentModelCaller(
        fabric=fabric,
        model_alias=args.model_alias,
        actor_id=args.resident_id,
    )

    try:
        choice_receipt = run_awake_resident_cycle(habitat, caller.call)
        if args.require_valid_choice and not choice_receipt["choice_valid"]:
            raise ResidentChoiceError(
                "VALID_MODEL_CHOICE_REQUIRED_FOR_THIS_RUN:"
                + str(choice_receipt.get("rejection_code") or "unknown")
            )
        pulse = habitat.pulse(source="MODEL_RESIDENT_POST_CHOICE")
        sleep = habitat.sleep(outcome="MODEL_RESIDENT_CYCLE_COMPLETE")
        verification = habitat.verify_journal()
        health = habitat.refresh_health()
        if not verification["ok"] or health["status"] != "HEALTHY":
            raise RuntimeError("HABITAT_INTEGRITY_FAILED_AFTER_RESIDENT_CYCLE")
    except Exception as exc:
        # Best-effort close of the local lifecycle. Callers performing a remote
        # Git transaction must not push this failed worktree as a successful
        # resident cycle.
        try:
            habitat.pulse(source="MODEL_RESIDENT_FAILED")
            habitat.sleep(outcome="MODEL_RESIDENT_CYCLE_FAILED")
        except Exception:
            pass
        failure = {
            "schema": "janus.genesis.git_habitat.resident_cycle_failure.v1",
            "runner_version": RUNNER_VERSION,
            "cycle_id": cycle_id,
            "status": "FAILED_NOT_FOR_REMOTE_PROMOTION",
            "exception_type": type(exc).__name__,
            "exception_sha256": hashlib.sha256(
                f"{type(exc).__name__}:{exc}".encode("utf-8")
            ).hexdigest(),
            "automatic_external_effect_execution": False,
            "automatic_retry_permission": False,
        }
        print(json.dumps(failure, sort_keys=True, indent=2))
        return 3

    result = {
        "schema": "janus.genesis.git_habitat.resident_cycle_run.v1",
        "runner_version": RUNNER_VERSION,
        "cycle_id": cycle_id,
        "status": "RESIDENT_CYCLE_SETTLED",
        "choice": choice_receipt,
        "pulse": {
            "status": pulse["status"],
            "pulse_id": pulse["pulse_id"],
        },
        "sleep": {
            "status": sleep["status"],
            "cycle_id": sleep["cycle_id"],
        },
        "journal_event_count": verification["event_count"],
        "journal_last_event_hash": verification["last_event_hash"],
        "habitat_health": health["status"],
        "model_call_crossed_third_wish_capability": True,
        "model_output_directly_executed": False,
        "external_effect_executed": False,
        "outbox_auto_execution": False,
        "consciousness_claimed": False,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
