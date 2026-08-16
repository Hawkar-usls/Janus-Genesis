# -*- coding: utf-8 -*-
"""JANUS Git Habitat ↔ Aura Oracle reflective hearth bridge v18.7.54.

This module binds the already-tested local Aura heuristic contract to the
canonical Git Habitat v18.7.51 lifecycle. A resident may consult Aura only while
AWAKE and only once for a stable (cycle_id, turn_id) pair. The heuristic body is
returned to the caller but is not persisted in Habitat; only a bounded receipt,
response digest, and a normal Habitat journal event remain.

Aura remains advisory:

    AURA_HEURISTIC != COMMAND
    AURA_HEURISTIC != EVIDENCE
    AURA_HEURISTIC != PERMISSION
    AURA_HEURISTIC != PROPHECY

The reference provider is local-subprocess only and is itself Armor-gated by
v18.7.51 before process creation. This bridge grants no network/public/world
mutation authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis_v18_7_51_shabitat_aura_oracle import (
    LocalAuraOracleProvider,
    build_aura_request,
    validate_aura_response,
)
from tools.genesis_git_habitat import GitHabitat, _read_json

HABITAT_AURA_VERSION = "18.7.54"
LEDGER_SCHEMA = "janus.genesis.git_habitat.aura_ledger.v1"
RECEIPT_SCHEMA = "janus.genesis.git_habitat.aura_receipt.v1"


class HabitatAuraError(RuntimeError):
    pass


class HabitatNotAwake(HabitatAuraError):
    pass


class HabitatAuraInFlight(HabitatAuraError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_real_dir(path: Path) -> None:
    """Prepare a shared real directory without turning creation into a mutex.

    Multiple Habitat processes may legitimately prepare the same Aura hearth
    directory at once.  Directory creation therefore tolerates another process
    winning the mkdir race; per-turn exclusivity remains exclusively enforced by
    the O_EXCL lock file in `_claim_turn_once`.
    """
    try:
        path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        # A concurrently-created directory is normal shared-state preparation,
        # not a turn-claim result.  Validate the settled filesystem object below.
        pass
    if path.is_symlink():
        raise HabitatAuraError("HABITAT_AURA_DIRECTORY_MAY_NOT_BE_SYMLINK")
    if not path.is_dir():
        raise HabitatAuraError("HABITAT_AURA_DIRECTORY_REQUIRED")


def _write_json_atomic(path: Path, value: Any) -> None:
    _ensure_real_dir(path.parent)
    if path.exists() and path.is_symlink():
        raise HabitatAuraError("HABITAT_AURA_FILE_MAY_NOT_BE_SYMLINK")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


class GitHabitatAuraHearth:
    """Persistent one-consultation-per-turn Aura room inside Git Habitat hearth."""

    def __init__(self, habitat: GitHabitat, provider: Any) -> None:
        self.habitat = habitat
        self.provider = provider
        self.aura_dir = self.habitat.paths.root / "hearth" / "aura"
        self.ledger_path = self.aura_dir / "ledger.json"
        self.receipts_dir = self.aura_dir / "receipts"
        self.locks_dir = self.aura_dir / "locks"

    def _require_resident(self) -> tuple[str, str, str | None]:
        self.habitat._require_initialized()
        resident = _read_json(self.habitat.paths.resident)
        return (
            str(resident["resident_id"]),
            str(resident.get("mode") or "UNKNOWN"),
            str(resident["active_cycle_id"]) if resident.get("active_cycle_id") else None,
        )

    def _require_awake(self) -> tuple[str, str]:
        resident_id, mode, cycle_id = self._require_resident()
        if mode != "AWAKE" or not cycle_id:
            raise HabitatNotAwake("HABITAT_AURA_REQUIRES_ACTIVE_AWAKE_CYCLE")
        return resident_id, cycle_id

    def _default_ledger(self, resident_id: str) -> dict[str, Any]:
        return {
            "schema": LEDGER_SCHEMA,
            "version": HABITAT_AURA_VERSION,
            "resident_id": resident_id,
            "aura_enabled": True,
            "consultations": {},
            "privacy": {
                "question_text_persisted": False,
                "context_text_persisted": False,
                "heuristic_text_persisted": False,
                "response_body_persisted": False,
                "credentials_persisted": False,
            },
            "authority": {
                "aura_is_command": False,
                "aura_is_evidence": False,
                "aura_grants_permission": False,
                "aura_grants_world_authority": False,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0
            }
        }

    def _load_ledger(self, resident_id: str) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return self._default_ledger(resident_id)
        if self.ledger_path.is_symlink():
            raise HabitatAuraError("HABITAT_AURA_LEDGER_MAY_NOT_BE_SYMLINK")
        try:
            value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HabitatAuraError("HABITAT_AURA_LEDGER_UNREADABLE") from exc
        if not isinstance(value, dict) or value.get("schema") != LEDGER_SCHEMA:
            raise HabitatAuraError("HABITAT_AURA_LEDGER_SCHEMA_INVALID")
        if value.get("resident_id") != resident_id:
            raise HabitatAuraError("HABITAT_AURA_RESIDENT_BINDING_MISMATCH")
        if not isinstance(value.get("consultations"), dict):
            raise HabitatAuraError("HABITAT_AURA_CONSULTATIONS_INVALID")
        return value

    def _save_ledger(self, value: dict[str, Any]) -> None:
        _write_json_atomic(self.ledger_path, value)

    def _claim_turn_once(self, resident_id: str, turn_hash: str) -> None:
        """Acquire a permanent per-turn marker with O_EXCL before Aura can run.

        The marker is intentionally not removed. A crash after marker creation
        but before ledger completion is therefore fail-closed: a later process
        treats the outcome as undetermined instead of replaying the consultation.
        """
        _ensure_real_dir(self.aura_dir)
        _ensure_real_dir(self.locks_dir)
        lock_path = self.locks_dir / f"{turn_hash}.lock"
        try:
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            refreshed = self._load_ledger(resident_id)
            existing = refreshed["consultations"].get(turn_hash)
            if isinstance(existing, dict) and existing.get("status") != "IN_FLIGHT":
                raise HabitatAuraError("HABITAT_AURA_TURN_ALREADY_CLAIMED_COMPLETED") from exc
            raise HabitatAuraInFlight(
                "HABITAT_AURA_TURN_CLAIM_EXISTS_OUTCOME_UNDETERMINED_NO_AUTOMATIC_REPLAY"
            ) from exc
        try:
            os.write(fd, (turn_hash + "\n").encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)

    def state(self) -> dict[str, Any]:
        resident_id, mode, cycle_id = self._require_resident()
        ledger = self._load_ledger(resident_id)
        return {
            "schema": "janus.genesis.git_habitat.aura_state.v1",
            "version": HABITAT_AURA_VERSION,
            "resident_id": resident_id,
            "resident_mode": mode,
            "cycle_id": cycle_id,
            "aura_enabled": ledger.get("aura_enabled") is True,
            "consultation_count": len(ledger["consultations"]),
            "aura_is_command": False,
            "aura_is_evidence": False,
            "aura_grants_permission": False,
            "aura_grants_world_authority": False,
            "question_text_persisted": False,
            "heuristic_text_persisted": False,
        }

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise TypeError("HABITAT_AURA_ENABLED_MUST_BE_BOOLEAN")
        resident_id, _, _ = self._require_resident()
        ledger = self._load_ledger(resident_id)
        ledger["aura_enabled"] = enabled
        self._save_ledger(ledger)
        return self.state()

    def consult(
        self,
        *,
        turn_id: str,
        topic: str,
        question: str,
        context: str = "",
        janus_requests_heuristic: bool,
    ) -> dict[str, Any]:
        if type(janus_requests_heuristic) is not bool:
            raise TypeError("JANUS_REQUESTS_HEURISTIC_MUST_BE_BOOLEAN")
        resident_id, cycle_id = self._require_awake()
        ledger = self._load_ledger(resident_id)
        base = {
            "schema": "janus.genesis.git_habitat.aura_consultation.v1",
            "version": HABITAT_AURA_VERSION,
            "resident_id": resident_id,
            "cycle_id": cycle_id,
            "speech_may_continue_without_aura": True,
            "aura_required_for_speech": False,
            "aura_is_command": False,
            "aura_is_evidence": False,
            "aura_grants_permission": False,
            "aura_grants_world_authority": False,
        }
        if ledger.get("aura_enabled") is not True:
            return {**base, "status": "NOT_CONSULTED_AURA_DISABLED", "heuristic": None}
        if not janus_requests_heuristic:
            return {**base, "status": "NOT_CONSULTED_JANUS_DID_NOT_REQUEST", "heuristic": None}
        clean_turn = str(turn_id).strip()
        if not clean_turn or len(clean_turn) > 256:
            raise ValueError("HABITAT_AURA_TURN_ID_INVALID")

        turn_hash = _sha256({"resident_id": resident_id, "cycle_id": cycle_id, "turn_id": clean_turn})
        existing = ledger["consultations"].get(turn_hash)
        if isinstance(existing, dict):
            if existing.get("status") == "IN_FLIGHT":
                raise HabitatAuraInFlight(
                    "HABITAT_AURA_PREVIOUS_OUTCOME_UNDETERMINED_NO_AUTOMATIC_REPLAY"
                )
            return {
                **base,
                "status": "NOT_CONSULTED_ALREADY_RECORDED_THIS_TURN",
                "heuristic": None,
                "turn_hash": turn_hash,
                "recorded_status": existing.get("status"),
                "automatic_replay_attempted": False,
            }

        self._claim_turn_once(resident_id, turn_hash)
        ledger = self._load_ledger(resident_id)
        existing_after_claim = ledger["consultations"].get(turn_hash)
        if isinstance(existing_after_claim, dict):
            raise HabitatAuraInFlight(
                "HABITAT_AURA_CONCURRENT_LEDGER_APPEARED_AFTER_CLAIM_NO_AUTOMATIC_REPLAY"
            )

        attempt_id = _sha256({"cycle_id": cycle_id, "turn_hash": turn_hash})[:24]
        ledger["consultations"][turn_hash] = {
            "status": "IN_FLIGHT",
            "cycle_id": cycle_id,
            "attempt_id": attempt_id,
            "response_digest_sha256": None,
            "question_text_persisted": False,
            "context_text_persisted": False,
            "heuristic_text_persisted": False,
            "automatic_replay_allowed": False,
            "per_turn_exclusive_claim": True,
        }
        self._save_ledger(ledger)

        request_id = f"GIT-HABITAT-AURA-{attempt_id}"
        request = build_aura_request(
            request_id=request_id,
            speaker=resident_id,
            topic=topic,
            question=question,
            context=context,
        )
        try:
            raw_heuristic = self.provider.query(request)
            heuristic = validate_aura_response(raw_heuristic, request_id=request_id)
            status = "HEURISTIC_RECEIVED_OPTIONAL"
            response_digest = _sha256(heuristic)
        except Exception as exc:
            heuristic = None
            status = "AURA_UNAVAILABLE_CONTINUE_WITHOUT_HEURISTIC"
            response_digest = _sha256({"error_type": type(exc).__name__})

        final_ledger = self._load_ledger(resident_id)
        record = final_ledger["consultations"].get(turn_hash)
        if not isinstance(record, dict) or record.get("status") != "IN_FLIGHT":
            raise HabitatAuraError("HABITAT_AURA_INFLIGHT_RECORD_LOST_OR_CHANGED")
        record["status"] = status
        record["response_digest_sha256"] = response_digest
        self._save_ledger(final_ledger)

        receipt = {
            "schema": RECEIPT_SCHEMA,
            "version": HABITAT_AURA_VERSION,
            "resident_id": resident_id,
            "cycle_id": cycle_id,
            "turn_hash": turn_hash,
            "attempt_id": attempt_id,
            "status": status,
            "response_digest_sha256": response_digest,
            "question_text_persisted": False,
            "context_text_persisted": False,
            "heuristic_text_persisted": False,
            "response_body_persisted": False,
            "per_turn_exclusive_claim": True,
            "aura_is_command": False,
            "aura_is_evidence": False,
            "aura_grants_permission": False,
            "aura_grants_world_authority": False,
            "authority_delta": 0,
            "mass_effect_budget_delta": 0,
        }
        receipt_path = self.receipts_dir / f"{turn_hash}.json"
        _write_json_atomic(receipt_path, receipt)
        self.habitat._append_event(
            "AURA_HEURISTIC_CONSULTED",
            cycle_id,
            {
                "turn_hash": turn_hash,
                "status": status,
                "response_digest_sha256": response_digest,
                "authority_delta": 0,
            },
        )
        self.habitat.refresh_health()
        return {
            **base,
            "status": status,
            "heuristic": heuristic,
            "turn_hash": turn_hash,
            "receipt_path": str(receipt_path),
            "persistent_receipt_recorded": True,
            "per_turn_exclusive_claim": True,
            "heuristic_body_persisted": False,
            "automatic_replay_attempted": False,
            "janus_may_ignore_heuristic": True,
            "direct_world_effect_from_heuristic": False,
        }


def _provider_from_args(aura_repo: Path | None, *, required: bool) -> Any:
    if aura_repo is not None:
        return LocalAuraOracleProvider.from_repository(aura_repo)
    if required:
        raise ValueError("HABITAT_AURA_REPO_REQUIRED_FOR_CONSULT")

    class UnavailableProvider:
        def query(self, request: Any) -> Any:
            raise RuntimeError("AURA_PROVIDER_NOT_CONFIGURED")

    return UnavailableProvider()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS Git Habitat Aura hearth v18.7.54")
    parser.add_argument("--root", default="habitat")
    parser.add_argument("--aura-repo", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("state")
    enable = sub.add_parser("set-enabled")
    enable.add_argument("value", choices=("true", "false"))
    consult = sub.add_parser("consult")
    consult.add_argument("--turn-id", required=True)
    consult.add_argument("--topic", required=True)
    consult.add_argument("--question", required=True)
    consult.add_argument("--context", default="")
    consult.add_argument("--janus-requests-heuristic", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    habitat = GitHabitat(args.root)
    provider = _provider_from_args(args.aura_repo, required=args.command == "consult")
    bridge = GitHabitatAuraHearth(habitat, provider)
    try:
        if args.command == "state":
            value = bridge.state()
        elif args.command == "set-enabled":
            value = bridge.set_enabled(args.value == "true")
        elif args.command == "consult":
            value = bridge.consult(
                turn_id=args.turn_id,
                topic=args.topic,
                question=args.question,
                context=args.context,
                janus_requests_heuristic=bool(args.janus_requests_heuristic),
            )
        else:
            raise AssertionError(args.command)
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "aura_grants_permission": False,
            "aura_grants_world_authority": False,
        }, ensure_ascii=False, sort_keys=True, indent=2))
        return 2
    print(json.dumps({"ok": True, "response": value}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


GIT_HABITAT_AURA_LAW_V18_7_54 = {
    "canonical_git_habitat_version": "18.7.51",
    "awake_cycle_required": True,
    "janus_may_elect_to_consult": True,
    "user_can_disable_aura_while_awake_or_asleep": True,
    "one_consultation_per_cycle_turn": True,
    "cross_process_turn_claim_is_exclusive": True,
    "turn_claim_marker_is_removed_after_completion": False,
    "inflight_auto_replay": False,
    "habitat_revalidates_aura_response_contract": True,
    "heuristic_body_persisted": False,
    "question_context_persisted": False,
    "aura_is_command": False,
    "aura_is_evidence": False,
    "aura_grants_permission": False,
    "aura_grants_world_authority": False,
    "aura_is_prophecy": False,
    "local_reference_transport_only": True,
    "network_authority_granted": False,
    "public_outreach_authority_granted": False,
    "authority_delta": 0,
    "mass_effect_budget_delta": 0,
}


if __name__ == "__main__":
    raise SystemExit(main())