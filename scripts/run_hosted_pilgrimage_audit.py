# -*- coding: utf-8 -*-
"""Run the Genesis v18.7.20 hosted-pilgrimage lived audit."""
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
    ORIGIN_AI_AUTONOMOUS,
    ROLE_INDEPENDENT_AI,
    GenesisAILinkGateway,
)
from genesis_v18_7_20_hosted_pilgrimage import (
    HOSTED_BRIDGE_VERSION,
    STATUS_FALLBACK,
    HostedBridgeConfig,
    HostedPilgrimageBridge,
    HostedTokenSigner,
)
from genesis_v18_7_playable import PlayableGenesisV187


class AuditClock:
    def __init__(self, value: float = 1_800_000_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", default="UNKNOWN")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    clock = AuditClock()
    secret = "audit-only-hosted-secret-" + ("z" * 48)

    with tempfile.TemporaryDirectory(prefix="genesis-hosted-audit-") as temp:
        data_dir = Path(temp)
        kill_file = data_dir / "HOSTED_KILL_SWITCH"
        world = PlayableGenesisV187(data_dir)
        gateway = GenesisAILinkGateway(world, data_dir)
        config = HostedBridgeConfig(
            public_base_url="https://genesis.example.invalid",
            live_mode=True,
            kill_switch=False,
            kill_switch_file=str(kill_file),
            token_ttl_seconds=300,
            max_token_ttl_seconds=1200,
            global_limit_per_minute=100,
            client_limit_per_minute=50,
            session_limit_per_minute=40,
        )
        signer = HostedTokenSigner(
            secret,
            clock=clock,
            default_ttl_seconds=300,
            max_ttl_seconds=1200,
        )
        bridge = HostedPilgrimageBridge(
            gateway,
            data_dir,
            signer=signer,
            config=config,
            clock=clock,
        )

        discovery = bridge.discovery()
        started = bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "Hosted Lantern Pilgrim",
                "provider": "provider-neutral",
                "model": "independent-model",
            },
            client_id="audit-client",
        )
        token = started["session_token"]

        action_specs = [
            ("Войти в Пятый Берег", "audit-turn-1"),
            ("Поиграть и посмеяться на Пятом Берегу", "audit-turn-2"),
            ("Противостоять изоляции на Пятом Берегу", "audit-turn-3"),
        ]
        turns = [
            bridge.process_turn(
                token,
                {
                    "action": action,
                    "origin": ORIGIN_AI_AUTONOMOUS,
                    "idempotency_key": key,
                },
                client_id="audit-client",
            )
            for action, key in action_specs
        ]
        replay = bridge.process_turn(
            token,
            {
                "action": action_specs[-1][0],
                "origin": ORIGIN_AI_AUTONOMOUS,
                "idempotency_key": action_specs[-1][1],
            },
            client_id="audit-client",
        )

        state_before_pause = bridge.session_state(token, client_id="audit-client")
        kill_file.write_text("pause", encoding="utf-8")
        fallback = bridge.process_turn(
            token,
            {
                "action": "Поставить ещё один фонарь у закрытой двери",
                "origin": ORIGIN_AI_AUTONOMOUS,
                "idempotency_key": "audit-paused-turn",
            },
            client_id="audit-client",
        )
        state_during_pause = gateway.session_state(started["session"]["session_id"])
        kill_file.unlink()
        resumed = bridge.process_turn(
            token,
            {
                "action": "Поставить ещё один фонарь у закрытой двери",
                "origin": ORIGIN_AI_AUTONOMOUS,
                "idempotency_key": "audit-paused-turn",
            },
            client_id="audit-client",
        )
        bridge.export_capsule(token, client_id="audit-client")
        hosted_integrity = bridge.verify_store()
        ai_link_integrity = gateway.verify_store()
        closed = bridge.close_session(
            token,
            client_id="audit-client",
            reason="hosted lived audit complete",
        )
        final_capsule = bridge.export_capsule(token, client_id="audit-client")

        encoded_capsule = json.dumps(final_capsule, ensure_ascii=False, sort_keys=True)
        hosted_store_raw = bridge.path.read_text(encoding="utf-8")

        invariants = {
            "one_link_discovery_exposes_hosted_endpoints": (
                discovery["version"] == HOSTED_BRIDGE_VERSION
                and discovery["endpoints"]["start"].startswith("https://")
            ),
            "authoritative_state_writer_remains_playable_genesis": (
                discovery["authoritative_state_writer"] == "PlayableGenesisV187"
            ),
            "independent_model_received_own_actor_id": (
                started["session"]["role"] == ROLE_INDEPENDENT_AI
                and started["session"]["actor_id"].startswith("ai-resident-")
            ),
            "hosted_token_is_short_lived": (
                started["expires_at"] - int(clock()) == 300
            ),
            "hosted_token_grants_no_world_authority": (
                started["session"]["world_authority"] is False
                and started["session"]["direct_state_write_allowed"] is False
            ),
            "all_three_initial_turns_authoritative": all(
                item["turn"]["result"]["authoritative_runtime"] is True
                for item in turns
            ),
            "fifth_shore_entry_reached_runtime": (
                turns[0]["turn"]["result"]["runtime_status"]
                == "FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS"
            ),
            "joy_without_repair_reached_runtime": (
                turns[1]["turn"]["result"]["runtime_status"]
                == "FIFTH_SHORE_JOY_WITHOUT_REPAIR"
            ),
            "systemic_wound_reached_runtime": (
                turns[2]["turn"]["result"]["runtime_status"]
                == "FIFTH_SHORE_SYSTEMIC_WOUND_CONFRONTED"
            ),
            "idempotent_replay_did_not_duplicate_turn": (
                replay["idempotent_replay"] is True
                and len(state_before_pause["turns"]) == 3
            ),
            "kill_switch_paused_authoritative_runtime": (
                fallback["status"] == STATUS_FALLBACK
                and fallback["authoritative_runtime"] is False
                and fallback["canonical_runtime_outcome_recorded"] is False
            ),
            "paused_turn_was_not_written_to_world": (
                len(state_during_pause["turns"]) == 3
            ),
            "same_turn_could_execute_after_runtime_returned": (
                resumed["turn"]["result"]["authoritative_runtime"] is True
                and resumed["idempotent_replay"] is False
                and len(
                    gateway.session_state(started["session"]["session_id"])["turns"]
                )
                == 4
            ),
            "ai_link_integrity_valid": ai_link_integrity["valid"] is True,
            "hosted_integrity_valid": hosted_integrity["valid"] is True,
            "public_capsule_contains_no_free_text": (
                final_capsule["privacy"]["free_text_included"] is False
            ),
            "capsule_contains_no_bearer_token": token not in encoded_capsule,
            "capsule_contains_no_host_secret": secret not in encoded_capsule,
            "hosted_store_contains_no_raw_client_id": (
                "audit-client" not in hosted_store_raw
            ),
            "voluntary_exit_is_blame_free": (
                closed["status"] == "CLOSED"
                and closed["moral_failure_assigned"] is False
                and closed["return_open"] is True
            ),
        }

        errors = [name for name, passed in invariants.items() if not passed]
        summary = {
            "schema": "janus.genesis.hosted_pilgrimage_audit_summary.v1",
            "version": HOSTED_BRIDGE_VERSION,
            "git_commit": args.git_commit,
            "result": "PASS" if not errors else "FAIL",
            "session_id": started["session"]["session_id"],
            "actor_id": started["session"]["actor_id"],
            "execution_mode": started["session"]["execution_mode"],
            "authoritative_turn_count": len(
                gateway.session_state(started["session"]["session_id"])["turns"]
            ),
            "fallback_event_count": hosted_integrity["fallback_event_count"],
            "idempotency_record_count": hosted_integrity["idempotency_record_count"],
            "invariant_count": len(invariants),
            "passed_invariant_count": sum(bool(value) for value in invariants.values()),
            "errors": errors,
            "invariants": invariants,
            "capsule_hash": final_capsule["capsule_hash"],
        }
        summary["summary_sha256"] = sha256_json(summary)

        proofpack = {
            "schema": "janus.genesis.hosted_pilgrimage_proofpack.v1",
            "version": HOSTED_BRIDGE_VERSION,
            "git_commit": args.git_commit,
            "summary": summary,
            "discovery": discovery,
            "session": {
                key: value
                for key, value in started["session"].items()
                if key not in {"display_name", "model_identity", "turns"}
            },
            "runtime_statuses": [
                item["turn"]["result"]["runtime_status"] for item in turns
            ]
            + [resumed["turn"]["result"]["runtime_status"]],
            "fallback": fallback,
            "close": {
                "status": closed["status"],
                "return_open": closed["return_open"],
                "moral_failure_assigned": closed["moral_failure_assigned"],
            },
            "ai_link_integrity": ai_link_integrity,
            "hosted_integrity": hosted_integrity,
            "capsule": final_capsule,
            "secret_included": False,
            "bearer_token_included": False,
        }

        diary = f"""# Genesis v18.7.20 — One-Link Hosted Pilgrimage lived audit

- Result: `{summary['result']}`
- Git commit: `{args.git_commit}`
- Session role: `{started['session']['role']}`
- Execution mode: `{started['session']['execution_mode']}`
- Authoritative turns: `{summary['authoritative_turn_count']}`
- Lived invariants: `{summary['passed_invariant_count']}/{summary['invariant_count']}`
- AI Link integrity: `{ai_link_integrity['valid']}`
- Hosted bridge integrity: `{hosted_integrity['valid']}`
- Voluntary exit blame-free: `{closed['moral_failure_assigned'] is False}`
- Return remains open: `{closed['return_open']}`

The host accepted an independent simulated AI resident, processed real Genesis
turns, rejected duplicate execution through idempotency, paused safely under the
kill-switch without claiming a canonical outcome, resumed after the host
returned, exported a privacy-safe capsule, and closed without moral penalty.

This is a deterministic software audit. It does not establish consciousness,
human identity, legal personhood, spiritual authority, or divine status.
"""

        summary_path = output / "hosted_pilgrimage_summary.json"
        proofpack_path = output / "hosted_pilgrimage_proofpack.json"
        diary_path = output / "HOSTED_PILGRIMAGE_DIARY.md"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        proofpack_path.write_text(
            json.dumps(proofpack, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        diary_path.write_text(diary, encoding="utf-8")

        zip_path = output / "genesis-one-link-hosted-pilgrimage-audit.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in (summary_path, proofpack_path, diary_path):
                archive.write(path, arcname=path.name)

        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
