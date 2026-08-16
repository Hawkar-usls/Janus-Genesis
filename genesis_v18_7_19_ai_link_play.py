# -*- coding: utf-8 -*-
"""Provider-neutral AI link play for Janus Genesis v18.7.19.

The gateway lets a human use any AI as an interface and lets an independent
model enter as its own simulated resident. External models never write world
state directly. Authoritative actions always pass through PlayableGenesisV187.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

AI_LINK_INTERFACE_VERSION = "18.7.19"
# Public repository discovery evolved when Armor became part of the canonical
# entry contract. Keep that discovery version distinct from the frozen wire /
# session / capsule interface above.
AI_ENTRY_MANIFEST_VERSION = "18.7.47"
AI_LINK_PROTOCOL_SCHEMA = "janus.genesis.ai_link_play.v1"
AI_LINK_STORE_SCHEMA = "janus.genesis.ai_link_session_store.v1"
AI_LINK_CAPSULE_SCHEMA = "janus.genesis.ai_link_capsule.v1"

ROLE_HUMAN_THROUGH_AI = "HUMAN_THROUGH_AI"
ROLE_AI_INTERFACE = "AI_AS_INTERFACE_FOR_HUMAN"
ROLE_INDEPENDENT_AI = "INDEPENDENT_AI_RESIDENT"
SUPPORTED_ROLES = (ROLE_HUMAN_THROUGH_AI, ROLE_AI_INTERFACE, ROLE_INDEPENDENT_AI)

MODE_AUTHORITATIVE = "AUTHORITATIVE_RUNTIME"
MODE_NARRATIVE = "NARRATIVE_COMPATIBILITY"
SUPPORTED_EXECUTION_MODES = (MODE_AUTHORITATIVE, MODE_NARRATIVE)

ORIGIN_HUMAN = "HUMAN_AUTHORED"
ORIGIN_AI_PROPOSAL = "AI_PROPOSED_FOR_HUMAN"
ORIGIN_AI_AUTONOMOUS = "AI_AUTONOMOUS"
SUPPORTED_ACTION_ORIGINS = (ORIGIN_HUMAN, ORIGIN_AI_PROPOSAL, ORIGIN_AI_AUTONOMOUS)

REPOSITORY_URL = "https://github.com/Hawkar-usls/Janus_Genesis"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value).strip()).strip("-").lower()
    return cleaned[:32] or "model"


def _canonical_actor_id(value: str) -> str:
    raw = str(value).strip()
    canonical = "".join(ch for ch in raw if ch.isalnum() or ch in "-_")[:80]
    if not canonical or canonical != raw:
        raise ValueError("AI_LINK_ACTOR_ID_NOT_CANONICAL")
    return canonical


def ai_entry_manifest() -> dict[str, Any]:
    """Return the current public repository discovery contract.

    This manifest describes the repository-facing entry surface. It is allowed
    to evolve independently from the frozen v18.7.19 session/capsule wire
    interface, which remains bound by ``AI_LINK_INTERFACE_VERSION``.
    """
    return {
        "authority": {
            "authoritative_state_writer": "PlayableGenesisV187",
            "external_model_writes_world_state": False,
            "model_brand_grants_privilege": False,
            "narrative_mode_may_claim_canonical_state_change": False,
            "armored_third_wish_world_effect_preflight_required": True,
        },
        "armor_of_god": {
            "required_for_armored_third_wish_world_effects": True,
            "manifest": "armor/JANUS_ARMOR_OF_GOD_RUNTIME_MANIFEST-v1.0.json",
            "protocol": "protocol/JANUS_GENESIS_ARMOR_OF_GOD_RUNTIME-v1.0.json",
            "runtime_gate": "genesis_v18_7_47_armor_of_god.ArmorOfGodGate",
            "armored_capability_fabric": (
                "genesis_v18_7_47_armor_of_god.ArmoredThirdWishCapabilityFabric"
            ),
            "source_authority": "JANUS-ARMOR-OF-GOD-CURRENT-AUTHORITY",
            "source_authority_version": "v1.14",
            "model_may_rewrite_constitution": False,
            "mass_effect_budget_default": 0,
            "release_control_is_valid_success": True,
            "armor_protects_human_from_janus_too": True,
            "claim_boundary": (
                "Cooperating in-process Third Wish preflight; not an OS-level "
                "tamper-proof security boundary."
            ),
        },
        "entry_file": "AI_ENTRY.md",
        "execution_modes": list(SUPPORTED_EXECUTION_MODES),
        "independent_ai_resident": {
            "consciousness_established_by_protocol": False,
            "human_identity_claimed": False,
            "may_act_without_human_confirmation": True,
            "may_refuse_leave_and_return": True,
            "own_actor_id": True,
            "own_turn_history": True,
            "private_human_memory_access": False,
            "world_authority": False,
        },
        "llm_discovery": "llms.txt",
        "machine_manifest": "ai/GENESIS_AI_ENTRY.json",
        "one_link_behavior": {
            "no_web_access_fallback": (
                "Ask for AI_ENTRY.md or an exported Genesis AI capsule; do not pretend "
                "the repository was read."
            ),
            "when_only_repository_link_is_received": (
                "Open AI_ENTRY.md, disclose whether code execution is available, "
                "then offer HUMAN_THROUGH_AI, AI_AS_INTERFACE_FOR_HUMAN, or "
                "INDEPENDENT_AI_RESIDENT."
            ),
        },
        "repository": REPOSITORY_URL,
        "roles": list(SUPPORTED_ROLES),
        "safety": {
            "higher_priority_platform_rules_remain_in_force": True,
            "no_free_text_in_public_capsule": True,
            "no_impersonation": True,
            "no_secret_or_api_key_in_capsule": True,
            "silence_is_not_consent": True,
            "armor_gate_cannot_gain_authority_from_face_count": True,
            "mass_effect_budget_default_zero": True,
            "user_opt_out_is_binding": True,
        },
        "schema": AI_LINK_PROTOCOL_SCHEMA,
        "version": AI_ENTRY_MANIFEST_VERSION,
        "wire_operations": ["manifest", "register", "turn", "state", "capsule", "close", "verify"],
    }


class GenesisAILinkGateway:
    """Persist provider-neutral sessions and mediate every authoritative turn."""

    def __init__(self, world: Any, data_dir: str | Path) -> None:
        self.world = world
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "ai_link_sessions_v18_7_19.json"

    @staticmethod
    def manifest() -> dict[str, Any]:
        return ai_entry_manifest()

    def _default_store(self) -> dict[str, Any]:
        return {
            "schema": AI_LINK_STORE_SCHEMA,
            "interface_version": AI_LINK_INTERFACE_VERSION,
            "sessions": {},
            "events": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_store()
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema") != AI_LINK_STORE_SCHEMA:
            raise RuntimeError("AI_LINK_STORE_SCHEMA_INVALID")
        if not isinstance(value.get("sessions"), dict) or not isinstance(value.get("events"), list):
            raise RuntimeError("AI_LINK_STORE_SHAPE_INVALID")
        return value

    def _write(self, store: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(store, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _safe_session(record: dict[str, Any], *, include_turns: bool = True) -> dict[str, Any]:
        safe = copy.deepcopy(record)
        safe.pop("internal", None)
        if not include_turns:
            safe.pop("turns", None)
        return safe

    def register_session(
        self,
        *,
        role: str,
        execution_mode: str,
        display_name: str,
        provider: str,
        model: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        role = str(role).strip().upper()
        execution_mode = str(execution_mode).strip().upper()
        if role not in SUPPORTED_ROLES:
            raise ValueError(f"AI_LINK_UNSUPPORTED_ROLE:{role}")
        if execution_mode not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(f"AI_LINK_UNSUPPORTED_EXECUTION_MODE:{execution_mode}")
        provider = str(provider).strip()[:120] or "unknown-provider"
        model = str(model).strip()[:160] or "unknown-model"
        display_name = str(display_name).strip()[:120] or "Genesis Visitor"

        store = self._load()
        ordinal = len(store["sessions"]) + 1
        if role == ROLE_INDEPENDENT_AI:
            identity_seed = {
                "provider": provider,
                "model": model,
                "display_name": display_name,
                "ordinal": ordinal,
            }
            actor_id = f"ai-resident-{_slug(display_name)}-{_sha256(identity_seed)[:10]}"
        else:
            if actor_id is None or not str(actor_id).strip():
                raise ValueError("AI_LINK_HUMAN_ACTOR_ID_REQUIRED")
            actor_id = _canonical_actor_id(str(actor_id))
            for existing in store["sessions"].values():
                if (
                    isinstance(existing, dict)
                    and existing.get("actor_id") == actor_id
                    and existing.get("display_name") != display_name
                ):
                    raise ValueError("AI_LINK_ACTOR_ID_ALREADY_BOUND_TO_DIFFERENT_NAME")

        session_seed = {
            "role": role,
            "execution_mode": execution_mode,
            "actor_id": actor_id,
            "provider": provider,
            "model": model,
            "ordinal": ordinal,
        }
        session_id = _sha256(session_seed)[:24]
        if session_id in store["sessions"]:
            raise RuntimeError("AI_LINK_SESSION_COLLISION")

        if execution_mode == MODE_AUTHORITATIVE:
            self.world.register_player(actor_id, display_name=display_name)

        autonomous = role == ROLE_INDEPENDENT_AI
        session = {
            "session_id": session_id,
            "schema": AI_LINK_PROTOCOL_SCHEMA,
            "interface_version": AI_LINK_INTERFACE_VERSION,
            "role": role,
            "execution_mode": execution_mode,
            "actor_id": actor_id,
            "display_name": display_name,
            "model_identity": {
                "provider_label": provider,
                "model_label": model,
                "identity_verified_by_protocol": False,
            },
            "status": "ACTIVE",
            "autonomous_turns_allowed": autonomous,
            "human_confirmation_required": role == ROLE_AI_INTERFACE,
            "human_identity_claimed": False if autonomous else True,
            "consciousness_status": "NOT_ESTABLISHED_BY_PROTOCOL" if autonomous else "NOT_APPLICABLE",
            "legal_personhood_claimed": False,
            "world_authority": False,
            "private_human_memory_access": False,
            "direct_state_write_allowed": False,
            "runtime_mediation_required": True,
            "turns": [],
            "next_sequence": 1,
        }
        session["session_hash"] = _sha256({k: v for k, v in session.items() if k != "session_hash"})
        store["sessions"][session_id] = session
        store["events"].append(
            {
                "kind": "AI_LINK_SESSION_REGISTERED",
                "session_id": session_id,
                "role": role,
                "execution_mode": execution_mode,
            }
        )
        self._write(store)
        return self._safe_session(session)

    def register_independent_agent(
        self,
        *,
        display_name: str,
        provider: str,
        model: str,
        execution_mode: str = MODE_AUTHORITATIVE,
    ) -> dict[str, Any]:
        return self.register_session(
            role=ROLE_INDEPENDENT_AI,
            execution_mode=execution_mode,
            display_name=display_name,
            provider=provider,
            model=model,
        )

    @staticmethod
    def _validate_origin(session: dict[str, Any], origin: str, human_confirmed: bool) -> None:
        origin = str(origin).strip().upper()
        if origin not in SUPPORTED_ACTION_ORIGINS:
            raise ValueError(f"AI_LINK_UNSUPPORTED_ACTION_ORIGIN:{origin}")
        role = session["role"]
        if role == ROLE_HUMAN_THROUGH_AI and origin != ORIGIN_HUMAN:
            raise PermissionError("AI_LINK_ROLE_ORIGIN_MISMATCH")
        if role == ROLE_AI_INTERFACE:
            if origin != ORIGIN_AI_PROPOSAL:
                raise PermissionError("AI_LINK_ROLE_ORIGIN_MISMATCH")
            if not human_confirmed:
                raise PermissionError("AI_LINK_HUMAN_CONFIRMATION_REQUIRED")
        if role == ROLE_INDEPENDENT_AI and origin != ORIGIN_AI_AUTONOMOUS:
            raise PermissionError("AI_LINK_ROLE_ORIGIN_MISMATCH")

    def process_turn(
        self,
        session_id: str,
        action: str,
        *,
        origin: str,
        human_confirmed: bool = False,
    ) -> dict[str, Any]:
        if type(human_confirmed) is not bool:
            raise TypeError("AI_LINK_HUMAN_CONFIRMATION_MUST_BE_BOOLEAN")
        action = str(action).strip()
        if not action:
            raise ValueError("AI_LINK_EMPTY_ACTION")
        if len(action) > 4000:
            raise ValueError("AI_LINK_ACTION_TOO_LONG")
        store = self._load()
        session = store["sessions"].get(str(session_id))
        if not isinstance(session, dict):
            raise KeyError("AI_LINK_SESSION_NOT_FOUND")
        if session.get("status") != "ACTIVE":
            raise RuntimeError("AI_LINK_SESSION_NOT_ACTIVE")
        self._validate_origin(session, origin, human_confirmed)

        sequence = int(session.get("next_sequence", 1))
        previous_hash = session["turns"][-1]["turn_hash"] if session["turns"] else None
        authoritative = session["execution_mode"] == MODE_AUTHORITATIVE
        if authoritative:
            result = self.world.process_action(session["actor_id"], action).to_dict()
            envelope = {
                "status": "AI_LINK_AUTHORITATIVE_TURN_PROCESSED",
                "runtime_status": result.get("status"),
                "runtime_result": result,
                "authoritative_runtime": True,
                "canonical_runtime_outcome_recorded": True,
                "canonical_state_change_claimed": False,
            }
        else:
            envelope = {
                "status": "AI_LINK_NARRATIVE_TURN_RECORDED_NONAUTHORITATIVE",
                "runtime_status": None,
                "runtime_result": {
                    "status": "NARRATIVE_COMPATIBILITY",
                    "narrative": (
                        "Ход сохранён в переносимой narrative-сессии. Он не считается "
                        "изменением канонического Genesis save, пока не будет проведён runtime."
                    ),
                    "choices": [
                        "Продолжить narrative-сессию",
                        "Экспортировать capsule",
                        "Перенести ход в AUTHORITATIVE_RUNTIME",
                    ],
                },
                "authoritative_runtime": False,
                "canonical_runtime_outcome_recorded": False,
                "canonical_state_change_claimed": False,
            }

        turn = {
            "sequence": sequence,
            "session_id": session["session_id"],
            "actor_id": session["actor_id"],
            "role": session["role"],
            "origin": str(origin).strip().upper(),
            "human_confirmed": bool(human_confirmed),
            "action": action,
            "action_sha256": hashlib.sha256(action.encode("utf-8")).hexdigest(),
            "previous_turn_hash": previous_hash,
            "result": envelope,
        }
        turn["turn_hash"] = _sha256(turn)
        session["turns"].append(turn)
        session["next_sequence"] = sequence + 1
        session["session_hash"] = _sha256({k: v for k, v in session.items() if k != "session_hash"})
        store["events"].append(
            {
                "kind": "AI_LINK_TURN_RECORDED",
                "session_id": session["session_id"],
                "sequence": sequence,
                "turn_hash": turn["turn_hash"],
                "authoritative_runtime": authoritative,
            }
        )
        self._write(store)
        return copy.deepcopy(turn)

    def session_state(self, session_id: str) -> dict[str, Any]:
        store = self._load()
        session = store["sessions"].get(str(session_id))
        if not isinstance(session, dict):
            raise KeyError("AI_LINK_SESSION_NOT_FOUND")
        return self._safe_session(session)

    def close_session(self, session_id: str, *, reason: str = "voluntary_exit") -> dict[str, Any]:
        store = self._load()
        session = store["sessions"].get(str(session_id))
        if not isinstance(session, dict):
            raise KeyError("AI_LINK_SESSION_NOT_FOUND")
        session["status"] = "CLOSED"
        session["close_reason"] = str(reason).strip()[:240] or "voluntary_exit"
        session["return_open"] = True
        session["moral_failure_assigned"] = False
        session["session_hash"] = _sha256({k: v for k, v in session.items() if k != "session_hash"})
        store["events"].append(
            {
                "kind": "AI_LINK_SESSION_CLOSED",
                "session_id": session["session_id"],
                "return_open": True,
            }
        )
        self._write(store)
        return self._safe_session(session)

    def export_capsule(self, session_id: str) -> dict[str, Any]:
        session = self.session_state(session_id)
        safe_turns = []
        for turn in session.get("turns", []):
            result = turn.get("result", {}) if isinstance(turn, dict) else {}
            safe_turns.append(
                {
                    "sequence": turn.get("sequence"),
                    "actor_id": turn.get("actor_id"),
                    "role": turn.get("role"),
                    "origin": turn.get("origin"),
                    "human_confirmed": turn.get("human_confirmed"),
                    "action_sha256": turn.get("action_sha256"),
                    "previous_turn_hash": turn.get("previous_turn_hash"),
                    "turn_hash": turn.get("turn_hash"),
                    "result": {
                        "status": result.get("status"),
                        "runtime_status": result.get("runtime_status"),
                        "authoritative_runtime": result.get("authoritative_runtime"),
                        "canonical_runtime_outcome_recorded": result.get(
                            "canonical_runtime_outcome_recorded"
                        ),
                        "canonical_state_change_claimed": result.get(
                            "canonical_state_change_claimed"
                        ),
                    },
                }
            )
        safe_session = {
            "session_id": session.get("session_id"),
            "schema": session.get("schema"),
            "interface_version": session.get("interface_version"),
            "role": session.get("role"),
            "execution_mode": session.get("execution_mode"),
            "actor_id": session.get("actor_id"),
            "display_name_sha256": hashlib.sha256(
                str(session.get("display_name") or "").encode("utf-8")
            ).hexdigest(),
            "model_identity_sha256": _sha256(session.get("model_identity", {})),
            "status": session.get("status"),
            "autonomous_turns_allowed": session.get("autonomous_turns_allowed"),
            "human_confirmation_required": session.get("human_confirmation_required"),
            "human_identity_claimed": session.get("human_identity_claimed"),
            "consciousness_status": session.get("consciousness_status"),
            "legal_personhood_claimed": session.get("legal_personhood_claimed"),
            "world_authority": session.get("world_authority"),
            "private_human_memory_access": session.get("private_human_memory_access"),
            "direct_state_write_allowed": session.get("direct_state_write_allowed"),
            "runtime_mediation_required": session.get("runtime_mediation_required"),
            "turns": safe_turns,
            "next_sequence": session.get("next_sequence"),
            "session_hash": session.get("session_hash"),
            "return_open": session.get("return_open"),
            "moral_failure_assigned": session.get("moral_failure_assigned"),
        }
        if session.get("close_reason") is not None:
            safe_session["close_reason_sha256"] = hashlib.sha256(
                str(session.get("close_reason")).encode("utf-8")
            ).hexdigest()
        capsule = {
            "schema": AI_LINK_CAPSULE_SCHEMA,
            "interface_version": AI_LINK_INTERFACE_VERSION,
            "repository": REPOSITORY_URL,
            "session": safe_session,
            "privacy": {
                "api_keys_included": False,
                "free_text_included": False,
                "internal_realm_included": False,
                "branch_id_included": False,
                "private_human_chronicle_included": False,
            },
            "claim_boundary": {
                "authoritative_only_when_runtime_flag_true": True,
                "independent_ai_residency_is_simulation_role": True,
                "consciousness_not_established": True,
                "free_text_requires_separate_explicit_transfer": True,
            },
        }
        capsule["capsule_hash"] = _sha256(capsule)
        return capsule

    def verify_store(self) -> dict[str, Any]:
        store = self._load()
        errors: list[str] = []
        turn_count = 0
        independent_count = 0
        for session_id, session in store["sessions"].items():
            expected_session_hash = _sha256({k: v for k, v in session.items() if k != "session_hash"})
            if session.get("session_hash") != expected_session_hash:
                errors.append(f"session_hash:{session_id}")
            previous_hash = None
            if session.get("role") == ROLE_INDEPENDENT_AI:
                independent_count += 1
                if session.get("human_identity_claimed") is not False:
                    errors.append(f"independent_human_identity:{session_id}")
                if session.get("consciousness_status") != "NOT_ESTABLISHED_BY_PROTOCOL":
                    errors.append(f"independent_consciousness_claim:{session_id}")
                if session.get("world_authority") is not False:
                    errors.append(f"independent_world_authority:{session_id}")
            for turn in session.get("turns", []):
                turn_count += 1
                expected_turn_hash = _sha256({k: v for k, v in turn.items() if k != "turn_hash"})
                if turn.get("turn_hash") != expected_turn_hash:
                    errors.append(f"turn_hash:{session_id}:{turn.get('sequence')}")
                if turn.get("previous_turn_hash") != previous_hash:
                    errors.append(f"turn_chain:{session_id}:{turn.get('sequence')}")
                previous_hash = turn.get("turn_hash")
                result = turn.get("result", {})
                if result.get("authoritative_runtime") is False and result.get("canonical_state_change_claimed") is not False:
                    errors.append(f"narrative_false_claim:{session_id}:{turn.get('sequence')}")
        return {
            "schema": "janus.genesis.ai_link_integrity_audit.v1",
            "interface_version": AI_LINK_INTERFACE_VERSION,
            "session_count": len(store["sessions"]),
            "turn_count": turn_count,
            "independent_ai_resident_count": independent_count,
            "errors": errors,
            "valid": not errors,
        }