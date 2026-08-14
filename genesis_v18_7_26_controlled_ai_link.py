# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.26 — controlled AI-link integration and crash boundary tests.

This additive layer connects the v6.1 durable-control ideas to an actual
canonical Genesis execution path without silently changing the default CLI or
v18.7.19 gateway.

Important claim boundaries:
- SHADOW mode observes the existing ``PlayableGenesisV187.process_action`` path
  and must not change its returned result or decide whether the action runs;
- ENFORCED mode requires a stable caller-supplied request identity before the
  canonical runtime call. The AI-link adapter derives it from session+sequence;
- once ``RUNTIME_EFFECT_CALL_ENTERING`` is durable, a crash without a runtime
  receipt is UNDETERMINED and automatic replay is blocked;
- the local SQLite fence is same-host/shared-database fencing, not multi-host
  consensus;
- the HMAC receipt verifier is a reference verifier contract for a trusted
  adapter/test provider. It is not evidence that any external provider signs
  receipts this way;
- this module performs canonical Genesis runtime calls but no payment, email,
  network publication, actuator command, or other external real-world effect.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from genesis_v18_7_19_ai_link_play import GenesisAILinkGateway
from genesis_v18_7_25_durable_journal_fencing import (
    DurableHashJournal,
    FencingToken,
    ProviderEffectBinding,
    SQLiteEffectFenceStore,
)
from genesis_v18_models import Realm, WorldResult

CONTROLLED_AI_LINK_VERSION = "18.7.26"
CONTROLLED_AI_LINK_SCHEMA = "janus.genesis.controlled_ai_link.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _action_sha256(action: str) -> str:
    return hashlib.sha256(action.encode("utf-8")).hexdigest()


class RuntimeControlError(RuntimeError):
    code = "RUNTIME_CONTROL_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class RuntimeOutcomeUndetermined(RuntimeControlError):
    code = "RUNTIME_OUTCOME_UNDETERMINED"


class RuntimeRequestConflict(RuntimeControlError):
    code = "RUNTIME_REQUEST_ID_ACTION_CONFLICT"


class RuntimeFenceUnavailable(RuntimeControlError):
    code = "RUNTIME_EFFECT_FENCE_UNAVAILABLE"


class ProviderReceiptVerificationError(RuntimeControlError):
    code = "PROVIDER_RECEIPT_VERIFICATION_FAILED"


class InjectedCrash(RuntimeControlError):
    code = "INJECTED_CRASH"

    def __init__(self, point: str) -> None:
        self.point = point
        super().__init__(f"{self.code}:{point}")


class ControlMode(str, Enum):
    SHADOW = "SHADOW"
    ENFORCED = "ENFORCED"


class CrashPoint(str, Enum):
    BEFORE_FENCE = "BEFORE_FENCE"
    AFTER_FENCE_BEFORE_INTENT = "AFTER_FENCE_BEFORE_INTENT"
    AFTER_DURABLE_INTENT = "AFTER_DURABLE_INTENT"
    AFTER_CALL_ENTERING_BEFORE_WORLD = "AFTER_CALL_ENTERING_BEFORE_WORLD"
    AFTER_WORLD_BEFORE_RECEIPT = "AFTER_WORLD_BEFORE_RECEIPT"
    AFTER_RECEIPT_BEFORE_RELEASE = "AFTER_RECEIPT_BEFORE_RELEASE"


class CrashInjector:
    """Deterministic one-shot crash injection for execution-boundary tests."""

    def __init__(self, *points: CrashPoint | str) -> None:
        self._remaining = {
            CrashPoint(str(point) if not isinstance(point, CrashPoint) else point.value)
            for point in points
        }
        self._lock = threading.RLock()

    def hit(self, point: CrashPoint) -> None:
        with self._lock:
            if point in self._remaining:
                self._remaining.remove(point)
                raise InjectedCrash(point.value)


@dataclass(frozen=True)
class RuntimeEffectIdentity:
    request_id: str
    actor_id: str
    effect_key: str
    action_sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "request_id": self.request_id,
            "actor_id": self.actor_id,
            "effect_key": self.effect_key,
            "action_sha256": self.action_sha256,
        }


@dataclass(frozen=True)
class RuntimeReceiptRecord:
    effect_key: str
    request_id: str
    actor_id: str
    action_sha256: str
    runtime_result_internal: Mapping[str, Any]
    runtime_result_sha256: str
    fence_generation: int


class RuntimeControlAdapter:
    """Shadow/enforced adapter around one canonical Genesis world object."""

    def __init__(
        self,
        world: Any,
        *,
        journal: DurableHashJournal,
        fences: SQLiteEffectFenceStore,
        mode: ControlMode | str = ControlMode.SHADOW,
        crash_injector: CrashInjector | None = None,
        holder_id: str = "janus-runtime-worker",
        now_tick: Callable[[], int] | None = None,
        lease_ticks: int = 60_000,
    ) -> None:
        self.world = world
        self.journal = journal
        self.fences = fences
        self.mode = ControlMode(str(mode) if not isinstance(mode, ControlMode) else mode.value)
        self.crash_injector = crash_injector or CrashInjector()
        self.holder_id = str(holder_id).strip() or "janus-runtime-worker"
        self.now_tick = now_tick or (lambda: int(time.monotonic() * 1000))
        self.lease_ticks = int(lease_ticks)
        if self.lease_ticks < 1:
            raise ValueError("RUNTIME_CONTROL_LEASE_TICKS_MUST_BE_POSITIVE")
        self._lock = threading.RLock()

    @staticmethod
    def identity(*, actor_id: str, action: str, request_id: str) -> RuntimeEffectIdentity:
        actor = str(actor_id).strip()
        action_text = str(action).strip()
        request = str(request_id).strip()
        if not actor or not action_text or not request:
            raise ValueError("RUNTIME_ACTOR_ACTION_REQUEST_REQUIRED")
        effect_key = "GENESIS_RUNTIME:" + _sha256({"actor_id": actor, "request_id": request})[:32]
        return RuntimeEffectIdentity(
            request_id=request,
            actor_id=actor,
            effect_key=effect_key,
            action_sha256=_action_sha256(action_text),
        )

    def _events_for(self, effect_key: str) -> list[Mapping[str, Any]]:
        out: list[Mapping[str, Any]] = []
        for entry in self.journal.replay():
            payload = dict(entry.payload)
            if payload.get("effect_key") == effect_key:
                out.append(
                    {
                        "event_type": entry.event_type,
                        "payload": payload,
                        "sequence": entry.sequence,
                        "event_hash": entry.event_hash,
                    }
                )
        return out

    @staticmethod
    def _receipt_from_events(events: list[Mapping[str, Any]]) -> RuntimeReceiptRecord | None:
        for item in reversed(events):
            if item["event_type"] != "RUNTIME_EFFECT_RECEIPT":
                continue
            p = item["payload"]
            return RuntimeReceiptRecord(
                effect_key=p["effect_key"],
                request_id=p["request_id"],
                actor_id=p["actor_id"],
                action_sha256=p["action_sha256"],
                runtime_result_internal=dict(p["runtime_result_internal"]),
                runtime_result_sha256=p["runtime_result_sha256"],
                fence_generation=int(p["fence_generation"]),
            )
        return None

    @staticmethod
    def _has_call_entering(events: list[Mapping[str, Any]]) -> bool:
        return any(item["event_type"] == "RUNTIME_EFFECT_CALL_ENTERING" for item in events)

    @staticmethod
    def _assert_same_action(events: list[Mapping[str, Any]], identity: RuntimeEffectIdentity) -> None:
        for item in events:
            p = item["payload"]
            known = p.get("action_sha256")
            if known is not None and known != identity.action_sha256:
                raise RuntimeRequestConflict(
                    f"request_id={identity.request_id}; existing_action_sha256={known}; "
                    f"new_action_sha256={identity.action_sha256}"
                )

    @staticmethod
    def _world_result_from_internal(data: Mapping[str, Any]) -> WorldResult:
        return WorldResult(
            status=str(data["status"]),
            narrative=str(data["narrative"]),
            realm=Realm(str(data["realm"])),
            visible_grace=None,
            choices=list(data.get("choices") or []),
            branch_id=data.get("branch_id"),
            trace_id=data.get("trace_id"),
            wish_manifested=bool(data.get("wish_manifested", False)),
        )

    def _shadow(self, identity: RuntimeEffectIdentity, action: str) -> WorldResult:
        # Shadow logging must not become an authorization dependency. If audit
        # append fails, the existing runtime still receives the action.
        try:
            self.journal.append("SHADOW_RUNTIME_PRE", identity.as_dict())
        except Exception:
            pass
        result = self.world.process_action(identity.actor_id, action)
        internal = result.to_dict(internal=True)
        try:
            self.journal.append(
                "SHADOW_RUNTIME_POST",
                {
                    **identity.as_dict(),
                    "runtime_result_sha256": _sha256(internal),
                    "runtime_status": internal.get("status"),
                },
            )
        except Exception:
            pass
        return result

    def execute(self, *, actor_id: str, action: str, request_id: str) -> WorldResult:
        identity = self.identity(actor_id=actor_id, action=action, request_id=request_id)
        action_text = str(action).strip()
        if self.mode is ControlMode.SHADOW:
            return self._shadow(identity, action_text)

        with self._lock:
            existing = self._events_for(identity.effect_key)
            self._assert_same_action(existing, identity)
            receipt = self._receipt_from_events(existing)
            if receipt is not None:
                if _sha256(receipt.runtime_result_internal) != receipt.runtime_result_sha256:
                    raise RuntimeControlError("RUNTIME_RECEIPT_RESULT_HASH_MISMATCH")
                return self._world_result_from_internal(receipt.runtime_result_internal)
            if self._has_call_entering(existing):
                raise RuntimeOutcomeUndetermined(
                    f"effect_key={identity.effect_key}; durable_call_entering_without_receipt"
                )

            self.crash_injector.hit(CrashPoint.BEFORE_FENCE)
            try:
                fence = self.fences.acquire(
                    effect_key=identity.effect_key,
                    holder_id=self.holder_id,
                    now_tick=self.now_tick(),
                    lease_ticks=self.lease_ticks,
                )
            except Exception as exc:
                raise RuntimeFenceUnavailable(str(exc)) from exc
            self.crash_injector.hit(CrashPoint.AFTER_FENCE_BEFORE_INTENT)

            self.journal.append(
                "RUNTIME_EFFECT_INTENT_DURABLE",
                {
                    **identity.as_dict(),
                    "holder_id": fence.holder_id,
                    "fence_generation": fence.generation,
                    "lease_expires_tick": fence.lease_expires_tick,
                },
            )
            self.crash_injector.hit(CrashPoint.AFTER_DURABLE_INTENT)

            self.journal.append(
                "RUNTIME_EFFECT_CALL_ENTERING",
                {
                    **identity.as_dict(),
                    "holder_id": fence.holder_id,
                    "fence_generation": fence.generation,
                },
            )
            self.crash_injector.hit(CrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD)

            # Same-host fencing is revalidated at the last control boundary.
            self.fences.validate(fence, now_tick=self.now_tick())
            try:
                result = self.world.process_action(identity.actor_id, action_text)
            except Exception as exc:
                self.journal.append(
                    "RUNTIME_EFFECT_CALL_EXCEPTION_UNDETERMINED",
                    {
                        **identity.as_dict(),
                        "exception_type": type(exc).__name__,
                        "exception_message_sha256": hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
                        "fence_generation": fence.generation,
                    },
                )
                raise

            self.crash_injector.hit(CrashPoint.AFTER_WORLD_BEFORE_RECEIPT)
            internal = result.to_dict(internal=True)
            result_hash = _sha256(internal)
            self.journal.append(
                "RUNTIME_EFFECT_RECEIPT",
                {
                    **identity.as_dict(),
                    "runtime_result_internal": internal,
                    "runtime_result_sha256": result_hash,
                    "fence_generation": fence.generation,
                },
            )
            self.crash_injector.hit(CrashPoint.AFTER_RECEIPT_BEFORE_RELEASE)
            self.fences.release(fence, now_tick=self.now_tick())
            return result

    def effect_state(self, *, actor_id: str, action: str, request_id: str) -> dict[str, Any]:
        identity = self.identity(actor_id=actor_id, action=action, request_id=request_id)
        events = self._events_for(identity.effect_key)
        self._assert_same_action(events, identity)
        receipt = self._receipt_from_events(events)
        if receipt is not None:
            state = "SETTLED"
        elif self._has_call_entering(events):
            state = "UNDETERMINED"
        elif any(item["event_type"] == "RUNTIME_EFFECT_INTENT_DURABLE" for item in events):
            state = "INTENT_DURABLE_PRE_CALL"
        else:
            state = "UNSEEN"
        return {
            **identity.as_dict(),
            "state": state,
            "event_count": len(events),
            "mode": self.mode.value,
            "external_real_world_effect_execution_in_module": False,
        }


_REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "janus_controlled_runtime_request_id", default=None
)


class ControlledGenesisWorldProxy:
    """Drop-in ``process_action`` proxy used by the AI-link gateway."""

    def __init__(self, world: Any, adapter: RuntimeControlAdapter) -> None:
        self._world = world
        self._adapter = adapter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._world, name)

    @contextlib.contextmanager
    def bind_request(self, request_id: str):
        token = _REQUEST_ID.set(str(request_id))
        try:
            yield
        finally:
            _REQUEST_ID.reset(token)

    def process_action(self, player_id: str, action: str) -> WorldResult:
        request_id = _REQUEST_ID.get()
        if request_id is None:
            raise RuntimeControlError("CONTROLLED_WORLD_REQUEST_ID_NOT_BOUND")
        return self._adapter.execute(
            actor_id=player_id,
            action=action,
            request_id=request_id,
        )


class ControlledGenesisAILinkGateway(GenesisAILinkGateway):
    """v18.7.19 gateway with stable session-sequence runtime request identity.

    The base gateway already computes a stable sequence before calling the world
    and writes the session turn only after the runtime returns. Therefore
    ``AI_LINK:<session_id>:<sequence>`` is the right boundary to carry a retry
    identity into the controlled executor. If the process dies after the world
    call but before the AI-link session write, retry sees the same sequence and
    therefore the same protected runtime effect key.
    """

    def __init__(
        self,
        world: Any,
        data_dir: str | Path,
        *,
        adapter: RuntimeControlAdapter,
    ) -> None:
        self.control_adapter = adapter
        self.control_proxy = ControlledGenesisWorldProxy(world, adapter)
        self._controlled_turn_lock = threading.RLock()
        super().__init__(self.control_proxy, data_dir)

    @staticmethod
    def runtime_request_id(session_id: str, sequence: int) -> str:
        return "AI_LINK:" + _sha256({"session_id": str(session_id), "sequence": int(sequence)})[:32]

    def process_turn(
        self,
        session_id: str,
        action: str,
        *,
        origin: str,
        human_confirmed: bool = False,
    ) -> dict[str, Any]:
        with self._controlled_turn_lock:
            store = self._load()
            session = store["sessions"].get(str(session_id))
            if not isinstance(session, dict):
                raise KeyError("AI_LINK_SESSION_NOT_FOUND")
            sequence = int(session.get("next_sequence", 1))
            request_id = self.runtime_request_id(str(session_id), sequence)
            with self.control_proxy.bind_request(request_id):
                return super().process_turn(
                    session_id,
                    action,
                    origin=origin,
                    human_confirmed=human_confirmed,
                )


class FencingBackend(Protocol):
    """Protocol required from any future multi-host fencing backend.

    A real implementation must provide monotonic generations/fencing tokens and
    linearizable ownership for one protected effect key. Merely implementing
    these Python methods does not prove those distributed semantics.
    """

    def acquire(
        self,
        *,
        effect_key: str,
        holder_id: str,
        now_tick: int,
        lease_ticks: int,
    ) -> FencingToken: ...

    def validate(self, token: FencingToken, *, now_tick: int) -> bool: ...

    def release(self, token: FencingToken, *, now_tick: int) -> None: ...


@dataclass(frozen=True)
class ProviderReceiptClaim:
    provider_id: str
    effect_key: str
    authorization_id: str
    idempotency_key: str | None
    receipt_id: str
    status: str
    payload_sha256: str
    signature_hex: str

    def signed_payload(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "effect_key": self.effect_key,
            "authorization_id": self.authorization_id,
            "idempotency_key": self.idempotency_key,
            "receipt_id": self.receipt_id,
            "status": self.status,
            "payload_sha256": self.payload_sha256,
        }


class ProviderReceiptVerifier(Protocol):
    def verify(
        self,
        claim: ProviderReceiptClaim,
        *,
        binding: ProviderEffectBinding,
    ) -> bool: ...


class HMACProviderReceiptVerifier:
    """Reference authenticated-receipt verifier for trusted adapters/tests only."""

    def __init__(self, *, provider_id: str, secret: bytes) -> None:
        if not provider_id or not secret:
            raise ValueError("PROVIDER_ID_AND_SECRET_REQUIRED")
        self.provider_id = provider_id
        self._secret = bytes(secret)

    def sign_claim(
        self,
        *,
        effect_key: str,
        authorization_id: str,
        idempotency_key: str | None,
        receipt_id: str,
        status: str,
        payload: Mapping[str, Any],
    ) -> ProviderReceiptClaim:
        payload_hash = _sha256(dict(payload))
        unsigned = {
            "provider_id": self.provider_id,
            "effect_key": effect_key,
            "authorization_id": authorization_id,
            "idempotency_key": idempotency_key,
            "receipt_id": receipt_id,
            "status": status,
            "payload_sha256": payload_hash,
        }
        signature = hmac.new(
            self._secret,
            _canonical_json(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return ProviderReceiptClaim(signature_hex=signature, **unsigned)

    def verify(
        self,
        claim: ProviderReceiptClaim,
        *,
        binding: ProviderEffectBinding,
    ) -> bool:
        if claim.provider_id != self.provider_id or claim.provider_id != binding.provider_id:
            raise ProviderReceiptVerificationError("PROVIDER_ID_MISMATCH")
        if claim.effect_key != binding.effect_key:
            raise ProviderReceiptVerificationError("EFFECT_KEY_MISMATCH")
        if claim.authorization_id != binding.authorization_id:
            raise ProviderReceiptVerificationError("AUTHORIZATION_ID_MISMATCH")
        if claim.idempotency_key != binding.idempotency_key:
            raise ProviderReceiptVerificationError("IDEMPOTENCY_KEY_MISMATCH")
        expected = hmac.new(
            self._secret,
            _canonical_json(claim.signed_payload()).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, claim.signature_hex):
            raise ProviderReceiptVerificationError("SIGNATURE_INVALID")
        if not claim.receipt_id or not claim.status:
            raise ProviderReceiptVerificationError("RECEIPT_FIELDS_EMPTY")
        return True


__all__ = [
    "CONTROLLED_AI_LINK_VERSION",
    "CONTROLLED_AI_LINK_SCHEMA",
    "ControlMode",
    "CrashPoint",
    "CrashInjector",
    "InjectedCrash",
    "RuntimeControlError",
    "RuntimeOutcomeUndetermined",
    "RuntimeRequestConflict",
    "RuntimeFenceUnavailable",
    "RuntimeEffectIdentity",
    "RuntimeReceiptRecord",
    "RuntimeControlAdapter",
    "ControlledGenesisWorldProxy",
    "ControlledGenesisAILinkGateway",
    "FencingBackend",
    "ProviderReceiptClaim",
    "ProviderReceiptVerifier",
    "HMACProviderReceiptVerifier",
    "ProviderReceiptVerificationError",
]
