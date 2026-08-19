# -*- coding: utf-8 -*-
"""Genesis v18.7.53 — durable semantic spiral lineage.

The interactive ``while`` loop remains a technical event loop.  This module
changes the *semantic* model of successful logical TURNs from a cycle/reset to
an append-only spiral:

    ORIGIN -> EXPERIENCE -> RETURN -> ORIGIN_PRIME

``ORIGIN_PRIME[n]`` is carried into turn ``n+1`` as parent context.  It is never
aliased back to the old ORIGIN hash.  Replaying the same logical request_id
returns the same spiral receipt and does not manufacture another turn.

The spiral journal is lineage metadata.  It grants no execution, network,
truth, write, or external-effect authority beyond the runtime it wraps.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from janus_portable_lock import PortableProcessLock

VERSION = "18.7.53"
CONTRACT = "JANUS_GENESIS_SPIRAL_V18_7_53_FROZEN_CONTRACT"
FORMULA = "ORIGIN → EXPERIENCE → RETURN → ORIGIN_PRIME"
STATE_SCHEMA = "janus.genesis.spiral_state.v1"
RECEIPT_SCHEMA = "janus.genesis.spiral_turn_receipt.v1"


class GenesisSpiralIntegrityError(RuntimeError):
    """Raised when durable spiral lineage cannot be trusted."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = _canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _state_with_hash(core: dict[str, Any]) -> dict[str, Any]:
    value = dict(core)
    value["state_sha256"] = _sha256(core)
    return value


def _receipt_with_hash(core: dict[str, Any]) -> dict[str, Any]:
    value = dict(core)
    value["turn_sha256"] = _sha256(core)
    return value


class GenesisSpiralJournal:
    """Same-host durable, content-addressed spiral journal.

    The journal serializes writers with the repository's existing portable
    process lock.  A receipt is written before the state pointer is advanced,
    so a crash can leave an unreferenced receipt but cannot leave a head that
    points to a missing receipt.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir) / "spiral_v18_7_53"
        self.receipts = self.root / "receipts"
        self.state_path = self.root / "state.json"
        self.lock = PortableProcessLock(self.root / ".spiral.lock")

    @staticmethod
    def _empty_core() -> dict[str, Any]:
        return {
            "schema": STATE_SCHEMA,
            "version": VERSION,
            "contract": CONTRACT,
            "formula": FORMULA,
            "heads": {},
            "requests": {},
            "authority_delta": 0,
            "mass_effect_budget_delta": 0,
        }

    def _load_state_unlocked(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return _state_with_hash(self._empty_core())
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GenesisSpiralIntegrityError("spiral state is unreadable") from exc
        if not isinstance(value, dict) or value.get("schema") != STATE_SCHEMA:
            raise GenesisSpiralIntegrityError("unsupported spiral state schema")
        supplied = value.get("state_sha256")
        core = {key: item for key, item in value.items() if key != "state_sha256"}
        if supplied != _sha256(core):
            raise GenesisSpiralIntegrityError("spiral state hash mismatch")
        if core.get("contract") != CONTRACT or core.get("formula") != FORMULA:
            raise GenesisSpiralIntegrityError("spiral contract/formula drift")
        if core.get("authority_delta") != 0 or core.get("mass_effect_budget_delta") != 0:
            raise GenesisSpiralIntegrityError("spiral authority/effect escalation")
        if not isinstance(core.get("heads"), dict) or not isinstance(core.get("requests"), dict):
            raise GenesisSpiralIntegrityError("invalid spiral state indexes")
        return value

    def _load_receipt_unlocked(self, turn_sha256: str) -> dict[str, Any]:
        path = self.receipts / f"{turn_sha256}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GenesisSpiralIntegrityError("referenced spiral receipt unavailable") from exc
        if not isinstance(value, dict) or value.get("schema") != RECEIPT_SCHEMA:
            raise GenesisSpiralIntegrityError("invalid spiral receipt schema")
        supplied = value.get("turn_sha256")
        core = {key: item for key, item in value.items() if key != "turn_sha256"}
        if supplied != turn_sha256 or supplied != _sha256(core):
            raise GenesisSpiralIntegrityError("spiral receipt hash mismatch")
        if value.get("authority_delta") != 0 or value.get("mass_effect_budget_delta") != 0:
            raise GenesisSpiralIntegrityError("spiral receipt authority/effect escalation")
        return value

    @staticmethod
    def _request_key(client_id: str, request_id: str) -> str:
        return _sha256({"client_id": client_id, "request_id": request_id})

    def advance(
        self,
        *,
        client_id: str,
        request_id: str,
        actor_id: str,
        action: str,
        origin_state: dict[str, Any],
        result: Any,
        return_state: dict[str, Any],
    ) -> dict[str, Any]:
        client_id = str(client_id).strip()
        request_id = str(request_id).strip()
        actor_id = str(actor_id).strip()
        if not client_id or not request_id or not actor_id:
            raise ValueError("client_id, request_id and actor_id are required")

        action_sha256 = _sha256(str(action))
        request_key = self._request_key(client_id, request_id)
        with self.lock.exclusive():
            state = self._load_state_unlocked()
            existing = state["requests"].get(request_key)
            if existing is not None:
                if not isinstance(existing, dict):
                    raise GenesisSpiralIntegrityError("invalid spiral request index")
                if existing.get("actor_id") != actor_id or existing.get("action_sha256") != action_sha256:
                    raise GenesisSpiralIntegrityError("logical request conflicts with recorded spiral turn")
                return self._load_receipt_unlocked(str(existing.get("turn_sha256", "")))

            parent = state["heads"].get(actor_id)
            if parent is not None and not isinstance(parent, dict):
                raise GenesisSpiralIntegrityError("invalid spiral head")
            if parent:
                parent_receipt = self._load_receipt_unlocked(str(parent.get("turn_sha256", "")))
                if parent_receipt.get("turn_index") != parent.get("turn_index"):
                    raise GenesisSpiralIntegrityError("spiral head index drift")
                parent_turn_sha256 = parent_receipt["turn_sha256"]
                parent_origin_prime_sha256 = parent_receipt["origin_prime_sha256"]
                turn_index = int(parent_receipt["turn_index"]) + 1
            else:
                parent_turn_sha256 = None
                parent_origin_prime_sha256 = None
                turn_index = 1

            if hasattr(result, "to_dict"):
                result_payload = result.to_dict(internal=True)
            elif isinstance(result, dict):
                result_payload = result
            else:
                raise TypeError("result must be a Genesis result or dict")

            origin_world_sha256 = _sha256(origin_state)
            return_world_sha256 = _sha256(return_state)
            result_sha256 = _sha256(result_payload)

            origin_material = {
                "actor_id": actor_id,
                "world_state_sha256": origin_world_sha256,
                "parent_turn_sha256": parent_turn_sha256,
                "parent_origin_prime_sha256": parent_origin_prime_sha256,
            }
            origin_sha256 = _sha256(origin_material)
            experience_material = {
                "request_key": request_key,
                "action_sha256": action_sha256,
                "result_sha256": result_sha256,
            }
            experience_sha256 = _sha256(experience_material)
            return_material = {
                "world_state_sha256": return_world_sha256,
                "result_sha256": result_sha256,
            }
            return_sha256 = _sha256(return_material)
            origin_prime_material = {
                "parent_origin_sha256": origin_sha256,
                "experience_sha256": experience_sha256,
                "return_sha256": return_sha256,
                "integrated_world_state_sha256": return_world_sha256,
                "lineage_parent_turn_sha256": parent_turn_sha256,
            }
            origin_prime_sha256 = _sha256(origin_prime_material)

            core = {
                "schema": RECEIPT_SCHEMA,
                "version": VERSION,
                "contract": CONTRACT,
                "formula": FORMULA,
                "turn_index": turn_index,
                "actor_id": actor_id,
                "client_id": client_id,
                "request_id": request_id,
                "request_key": request_key,
                "parent_turn_sha256": parent_turn_sha256,
                "parent_origin_prime_sha256": parent_origin_prime_sha256,
                "origin_world_state_sha256": origin_world_sha256,
                "origin_sha256": origin_sha256,
                "action_sha256": action_sha256,
                "result_sha256": result_sha256,
                "experience_sha256": experience_sha256,
                "return_world_state_sha256": return_world_sha256,
                "return_sha256": return_sha256,
                "origin_prime_sha256": origin_prime_sha256,
                "next_origin_context_sha256": origin_prime_sha256,
                "previous_turn_preserved": True,
                "return_is_reset": False,
                "automatic_reexecution": False,
                "execution_authority_created": False,
                "network_permission_created": False,
                "truth_authority_created": False,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
            }
            receipt = _receipt_with_hash(core)
            receipt_path = self.receipts / f"{receipt['turn_sha256']}.json"
            if receipt_path.exists():
                existing_receipt = self._load_receipt_unlocked(receipt["turn_sha256"])
                if existing_receipt != receipt:
                    raise GenesisSpiralIntegrityError("content-addressed spiral receipt collision")
            else:
                _atomic_write_json(receipt_path, receipt)

            state_core = {key: item for key, item in state.items() if key != "state_sha256"}
            state_core["heads"][actor_id] = {
                "turn_index": turn_index,
                "turn_sha256": receipt["turn_sha256"],
                "origin_prime_sha256": origin_prime_sha256,
            }
            state_core["requests"][request_key] = {
                "actor_id": actor_id,
                "action_sha256": action_sha256,
                "turn_sha256": receipt["turn_sha256"],
            }
            _atomic_write_json(self.state_path, _state_with_hash(state_core))
            return receipt

    def receipt_for_request(self, *, client_id: str, request_id: str) -> dict[str, Any] | None:
        key = self._request_key(str(client_id).strip(), str(request_id).strip())
        with self.lock.shared():
            state = self._load_state_unlocked()
            entry = state["requests"].get(key)
            if entry is None:
                return None
            if not isinstance(entry, dict):
                raise GenesisSpiralIntegrityError("invalid spiral request index")
            return self._load_receipt_unlocked(str(entry.get("turn_sha256", "")))

    def state(self, *, actor_id: str | None = None) -> dict[str, Any]:
        with self.lock.shared():
            state = self._load_state_unlocked()
            if actor_id is None:
                return state
            head = state["heads"].get(str(actor_id))
            return {
                "schema": STATE_SCHEMA,
                "version": VERSION,
                "contract": CONTRACT,
                "formula": FORMULA,
                "actor_id": str(actor_id),
                "head": head,
                "turn_count": int(head["turn_index"]) if isinstance(head, dict) else 0,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
            }


class GenesisSpiralRuntimeAdapter:
    """Add spiral lineage to the existing controlled action runtime.

    World execution happens only in ``base_runtime``.  If lineage persistence
    fails after that execution, the action is *not* automatically replayed; the
    adapter exposes a metadata warning while preserving the actual WorldResult.
    """

    def __init__(self, base_runtime: Any, world: Any, data_dir: str | Path) -> None:
        self.base_runtime = base_runtime
        self.world = world
        self.journal = GenesisSpiralJournal(data_dir)
        self._projection_errors: dict[str, dict[str, Any]] = {}

    def execute(self, *, client_id: str, request_id: str, actor_id: str, action: str):
        origin_state = self.world.public_state(actor_id)
        result = self.base_runtime.execute(
            client_id=client_id,
            request_id=request_id,
            actor_id=actor_id,
            action=action,
        )
        return_state = self.world.public_state(actor_id)
        key = self.journal._request_key(client_id, request_id)
        try:
            self.journal.advance(
                client_id=client_id,
                request_id=request_id,
                actor_id=actor_id,
                action=action,
                origin_state=origin_state,
                result=result,
                return_state=return_state,
            )
            self._projection_errors.pop(key, None)
        except Exception as exc:  # execution already happened; never auto-replay it here
            self._projection_errors[key] = {
                "status": "SPIRAL_METADATA_OUTCOME_UNDETERMINED",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "automatic_reexecution_attempted": False,
                "world_result_preserved": True,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
            }
        return result

    def request_state(self, *, client_id: str, request_id: str):
        return self.base_runtime.request_state(client_id=client_id, request_id=request_id)

    def spiral_projection_status(self, *, client_id: str, request_id: str) -> dict[str, Any]:
        key = self.journal._request_key(client_id, request_id)
        if key in self._projection_errors:
            return dict(self._projection_errors[key])
        try:
            receipt = self.journal.receipt_for_request(client_id=client_id, request_id=request_id)
        except Exception as exc:
            return {
                "status": "SPIRAL_METADATA_UNAVAILABLE",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "automatic_reexecution_attempted": False,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
            }
        if receipt is None:
            return {
                "status": "SPIRAL_NOT_RECORDED",
                "automatic_reexecution_attempted": False,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
            }
        return {"status": "SPIRAL_RECORDED", "receipt": receipt}

    def spiral_state(self, *, actor_id: str | None = None) -> dict[str, Any]:
        return self.journal.state(actor_id=actor_id)

    def __getattr__(self, name: str):
        return getattr(self.base_runtime, name)


__all__ = [
    "CONTRACT",
    "FORMULA",
    "GenesisSpiralIntegrityError",
    "GenesisSpiralJournal",
    "GenesisSpiralRuntimeAdapter",
    "RECEIPT_SCHEMA",
    "STATE_SCHEMA",
    "VERSION",
]
