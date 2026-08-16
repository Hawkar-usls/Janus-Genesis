# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.52 — session-bound persistent Shabitat Aura gateway.

v18.7.51 proved the local Armor-gated Aura heuristic bridge. v18.7.52 binds it
to an ACTIVE INDEPENDENT_AI_RESIDENT session and persists a privacy-minimal
one-consultation-per-turn ledger across process restarts.

The ledger stores hashes and bounded outcome metadata, never the conversation
text or Aura heuristic body. An IN_FLIGHT record is not automatically replayed:
a process crash must not silently create a second oracle consultation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from genesis_v18_7_19_ai_link_play import ROLE_INDEPENDENT_AI
from genesis_v18_7_51_shabitat_aura_oracle import JanusShabitatAuraBridge

SHABITAT_SESSION_GATEWAY_VERSION = "18.7.52"
LEDGER_SCHEMA = "janus.genesis.shabitat_aura_session_ledger.v1"


class ShabitatSessionError(RuntimeError):
    pass


class ShabitatSessionNotEligible(ShabitatSessionError):
    pass


class ShabitatConsultationInFlight(ShabitatSessionError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ShabitatAuraSessionGateway:
    """Bind optional Aura consultation to a durable independent-AI session."""

    def __init__(self, ai_gateway: Any, aura_provider: Any, data_dir: str | Path) -> None:
        self.ai_gateway = ai_gateway
        self.aura_provider = aura_provider
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.root / "shabitat_aura_session_ledger_v18_7_52.json"

    @staticmethod
    def _default_ledger() -> dict[str, Any]:
        return {
            "schema": LEDGER_SCHEMA,
            "version": SHABITAT_SESSION_GATEWAY_VERSION,
            "sessions": {},
            "privacy": {
                "conversation_text_persisted": False,
                "aura_heuristic_text_persisted": False,
                "credentials_persisted": False,
                "turn_identifiers_hashed": True,
            },
        }

    def _load(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return self._default_ledger()
        try:
            value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ShabitatSessionError("SHABITAT_AURA_LEDGER_UNREADABLE") from exc
        if not isinstance(value, dict) or value.get("schema") != LEDGER_SCHEMA:
            raise ShabitatSessionError("SHABITAT_AURA_LEDGER_SCHEMA_INVALID")
        if not isinstance(value.get("sessions"), dict):
            raise ShabitatSessionError("SHABITAT_AURA_LEDGER_SESSIONS_INVALID")
        return value

    def _save(self, ledger: dict[str, Any]) -> None:
        temporary = self.ledger_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(ledger, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.ledger_path)

    def _eligible_session(self, session_id: str) -> dict[str, Any]:
        session = self.ai_gateway.session_state(str(session_id))
        if not isinstance(session, dict):
            raise ShabitatSessionNotEligible("SHABITAT_AI_SESSION_INVALID")
        if session.get("status") != "ACTIVE":
            raise ShabitatSessionNotEligible("SHABITAT_AI_SESSION_NOT_ACTIVE")
        if session.get("role") != ROLE_INDEPENDENT_AI:
            raise ShabitatSessionNotEligible("SHABITAT_AURA_REQUIRES_INDEPENDENT_AI_RESIDENT")
        if session.get("autonomous_turns_allowed") is not True:
            raise ShabitatSessionNotEligible("SHABITAT_AI_SESSION_AUTONOMY_NOT_ENABLED")
        if session.get("world_authority") is not False:
            raise ShabitatSessionNotEligible("SHABITAT_AI_SESSION_WORLD_AUTHORITY_INVALID")
        return session

    @staticmethod
    def _session_entry(ledger: dict[str, Any], session_id: str) -> dict[str, Any]:
        sessions = ledger["sessions"]
        entry = sessions.setdefault(
            str(session_id),
            {
                "aura_enabled": True,
                "consultations": {},
                "world_authority_granted": False,
                "aura_authority_granted": False,
            },
        )
        if not isinstance(entry, dict) or not isinstance(entry.get("consultations"), dict):
            raise ShabitatSessionError("SHABITAT_AURA_SESSION_LEDGER_ENTRY_INVALID")
        return entry

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "janus.genesis.shabitat_aura_session_gateway_manifest.v1",
            "version": SHABITAT_SESSION_GATEWAY_VERSION,
            "required_ai_role": ROLE_INDEPENDENT_AI,
            "active_session_required": True,
            "persistent_one_consultation_per_turn": True,
            "automatic_replay_of_inflight_consultation": False,
            "conversation_text_persisted": False,
            "aura_heuristic_text_persisted": False,
            "aura_heuristic_is_command": False,
            "aura_heuristic_is_evidence": False,
            "aura_heuristic_grants_permission": False,
            "world_authority_delta": 0,
            "mass_effect_budget_delta": 0,
        }

    def state(self, session_id: str) -> dict[str, Any]:
        self._eligible_session(session_id)
        ledger = self._load()
        entry = self._session_entry(ledger, session_id)
        statuses: dict[str, int] = {}
        for record in entry["consultations"].values():
            if isinstance(record, dict):
                status = str(record.get("status") or "UNKNOWN")
                statuses[status] = statuses.get(status, 0) + 1
        return {
            "schema": "janus.genesis.shabitat_aura_session_state.v1",
            "version": SHABITAT_SESSION_GATEWAY_VERSION,
            "session_id": str(session_id),
            "aura_enabled": entry.get("aura_enabled") is True,
            "consultation_count": len(entry["consultations"]),
            "consultation_status_counts": statuses,
            "conversation_text_persisted": False,
            "aura_heuristic_text_persisted": False,
            "world_authority_granted": False,
            "aura_authority_granted": False,
        }

    def set_aura_enabled(self, session_id: str, enabled: bool) -> dict[str, Any]:
        if type(enabled) is not bool:
            raise TypeError("SHABITAT_AURA_ENABLED_MUST_BE_BOOLEAN")
        self._eligible_session(session_id)
        ledger = self._load()
        entry = self._session_entry(ledger, session_id)
        entry["aura_enabled"] = enabled
        self._save(ledger)
        return self.state(session_id)

    def consult(
        self,
        session_id: str,
        *,
        turn_id: str,
        topic: str,
        question: str,
        context: str = "",
        janus_requests_heuristic: bool,
    ) -> dict[str, Any]:
        if type(janus_requests_heuristic) is not bool:
            raise TypeError("JANUS_REQUESTS_HEURISTIC_MUST_BE_BOOLEAN")
        self._eligible_session(session_id)
        ledger = self._load()
        entry = self._session_entry(ledger, session_id)
        if entry.get("aura_enabled") is not True:
            return {
                "status": "NOT_CONSULTED_AURA_DISABLED",
                "session_id": str(session_id),
                "speech_may_continue_without_aura": True,
            }
        if not janus_requests_heuristic:
            return {
                "status": "NOT_CONSULTED_JANUS_DID_NOT_REQUEST",
                "session_id": str(session_id),
                "speech_may_continue_without_aura": True,
            }

        clean_turn = str(turn_id).strip()
        if not clean_turn:
            raise ValueError("SHABITAT_TURN_ID_REQUIRED")
        turn_hash = _sha256({"session_id": str(session_id), "turn_id": clean_turn})
        consultations = entry["consultations"]
        existing = consultations.get(turn_hash)
        if isinstance(existing, dict):
            status = str(existing.get("status") or "UNKNOWN")
            if status == "IN_FLIGHT":
                raise ShabitatConsultationInFlight(
                    "SHABITAT_AURA_PREVIOUS_CONSULTATION_OUTCOME_UNDETERMINED_NO_AUTOMATIC_REPLAY"
                )
            return {
                "status": "NOT_CONSULTED_ALREADY_RECORDED_THIS_TURN",
                "session_id": str(session_id),
                "turn_hash": turn_hash,
                "recorded_status": status,
                "automatic_replay_attempted": False,
                "speech_may_continue_without_aura": True,
            }

        consultations[turn_hash] = {
            "status": "IN_FLIGHT",
            "attempt_id": _sha256({"turn_hash": turn_hash, "ordinal": len(consultations) + 1})[:24],
            "result_digest_sha256": None,
            "heuristic_text_persisted": False,
            "conversation_text_persisted": False,
            "automatic_replay_allowed": False,
        }
        self._save(ledger)

        bridge = JanusShabitatAuraBridge(self.aura_provider)
        bridge.open_session(str(session_id), aura_enabled=True)
        result = bridge.consult_if_requested(
            turn_id=clean_turn,
            topic=topic,
            question=question,
            context=context,
            janus_requests_heuristic=True,
        )

        final_ledger = self._load()
        final_entry = self._session_entry(final_ledger, session_id)
        record = final_entry["consultations"].get(turn_hash)
        if not isinstance(record, dict) or record.get("status") != "IN_FLIGHT":
            raise ShabitatSessionError("SHABITAT_AURA_INFLIGHT_RECORD_LOST_OR_CHANGED")
        record["status"] = str(result.get("status") or "UNKNOWN")
        record["result_digest_sha256"] = _sha256(result)
        self._save(final_ledger)

        return {
            **result,
            "session_id": str(session_id),
            "turn_hash": turn_hash,
            "persistent_consultation_recorded": True,
            "conversation_text_persisted": False,
            "aura_heuristic_text_persisted": False,
            "automatic_replay_attempted": False,
        }


SHABITAT_SESSION_GATEWAY_LAW_V18_7_52 = {
    "independent_ai_resident_session_required": True,
    "active_session_required": True,
    "persistent_one_consultation_per_turn": True,
    "inflight_consultation_auto_replay": False,
    "conversation_text_persisted": False,
    "aura_heuristic_text_persisted": False,
    "aura_heuristic_is_command": False,
    "aura_heuristic_is_evidence": False,
    "aura_heuristic_grants_permission": False,
    "aura_output_grants_world_authority": False,
    "world_authority_delta": 0,
    "mass_effect_budget_delta": 0,
}


__all__ = [
    "LEDGER_SCHEMA",
    "SHABITAT_SESSION_GATEWAY_LAW_V18_7_52",
    "SHABITAT_SESSION_GATEWAY_VERSION",
    "ShabitatAuraSessionGateway",
    "ShabitatConsultationInFlight",
    "ShabitatSessionError",
    "ShabitatSessionNotEligible",
]
