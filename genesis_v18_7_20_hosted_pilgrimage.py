# -*- coding: utf-8 -*-
"""Hosted one-link pilgrimage bridge for Janus Genesis v18.7.20.

This layer exposes the v18.7.19 provider-neutral AI gateway through a bounded
hosted-session protocol. It never writes Genesis world state directly:
authoritative turns still pass through ``GenesisAILinkGateway`` and therefore
``PlayableGenesisV187``.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    MODE_NARRATIVE,
    ORIGIN_AI_AUTONOMOUS,
    ORIGIN_AI_PROPOSAL,
    ORIGIN_HUMAN,
    ROLE_AI_INTERFACE,
    ROLE_HUMAN_THROUGH_AI,
    ROLE_INDEPENDENT_AI,
    SUPPORTED_EXECUTION_MODES,
    SUPPORTED_ROLES,
    GenesisAILinkGateway,
)

HOSTED_BRIDGE_VERSION = "18.7.20"
HOSTED_BRIDGE_SCHEMA = "janus.genesis.hosted_pilgrimage.v1"
HOSTED_TOKEN_SCHEMA = "janus.genesis.hosted_session_token.v1"
HOSTED_STORE_SCHEMA = "janus.genesis.hosted_bridge_store.v1"

STATUS_SESSION_STARTED = "HOSTED_PILGRIMAGE_SESSION_STARTED"
STATUS_TURN_PROCESSED = "HOSTED_PILGRIMAGE_TURN_PROCESSED"
STATUS_FALLBACK = "HOSTED_PILGRIMAGE_NARRATIVE_FALLBACK"
STATUS_TOKEN_REFRESHED = "HOSTED_PILGRIMAGE_TOKEN_REFRESHED"

Clock = Callable[[], float]


class HostedBridgeError(RuntimeError):
    """Base error with a stable public code."""

    code = "HOSTED_BRIDGE_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class HostedAuthenticationError(HostedBridgeError):
    code = "HOSTED_TOKEN_INVALID"


class HostedTokenExpired(HostedAuthenticationError):
    code = "HOSTED_TOKEN_EXPIRED"


class HostedRateLimitError(HostedBridgeError):
    code = "HOSTED_RATE_LIMITED"


class HostedIdempotencyError(HostedBridgeError):
    code = "HOSTED_IDEMPOTENCY_CONFLICT"


class HostedUnavailableError(HostedBridgeError):
    code = "HOSTED_AUTHORITATIVE_RUNTIME_UNAVAILABLE"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise HostedAuthenticationError() from exc


def _bounded_int(value: int, *, minimum: int, maximum: int, name: str) -> int:
    number = int(value)
    if not minimum <= number <= maximum:
        raise ValueError(f"{name}_OUT_OF_RANGE")
    return number


@dataclass(frozen=True)
class HostedBridgeConfig:
    """Runtime configuration with deliberately safe defaults."""

    public_base_url: str = ""
    live_mode: bool = False
    kill_switch: bool = True
    kill_switch_file: str = ""
    allow_narrative_fallback: bool = True
    token_ttl_seconds: int = 900
    max_token_ttl_seconds: int = 3600
    global_limit_per_minute: int = 120
    client_limit_per_minute: int = 30
    session_limit_per_minute: int = 20
    max_action_chars: int = 4000

    def __post_init__(self) -> None:
        _bounded_int(
            self.token_ttl_seconds,
            minimum=60,
            maximum=self.max_token_ttl_seconds,
            name="HOSTED_TOKEN_TTL",
        )
        _bounded_int(
            self.max_token_ttl_seconds,
            minimum=60,
            maximum=86400,
            name="HOSTED_MAX_TOKEN_TTL",
        )
        for value, name in (
            (self.global_limit_per_minute, "HOSTED_GLOBAL_LIMIT"),
            (self.client_limit_per_minute, "HOSTED_CLIENT_LIMIT"),
            (self.session_limit_per_minute, "HOSTED_SESSION_LIMIT"),
        ):
            _bounded_int(value, minimum=1, maximum=100000, name=name)
        _bounded_int(
            self.max_action_chars,
            minimum=128,
            maximum=4000,
            name="HOSTED_MAX_ACTION_CHARS",
        )
        public = self.public_base_url.strip()
        if public and not (
            public.startswith("https://")
            or public.startswith("http://127.0.0.1")
            or public.startswith("http://localhost")
        ):
            raise ValueError("HOSTED_PUBLIC_BASE_URL_MUST_USE_HTTPS_OR_LOCALHOST")


class HostedTokenSigner:
    """Issue and verify compact HMAC-SHA256 bearer tokens."""

    def __init__(
        self,
        secret: str | bytes,
        *,
        clock: Clock = time.time,
        default_ttl_seconds: int = 900,
        max_ttl_seconds: int = 3600,
    ) -> None:
        raw = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
        if len(raw) < 32:
            raise ValueError("HOSTED_SECRET_TOO_SHORT")
        self._secret = raw
        self._clock = clock
        self._default_ttl = _bounded_int(
            default_ttl_seconds,
            minimum=60,
            maximum=max_ttl_seconds,
            name="HOSTED_TOKEN_TTL",
        )
        self._max_ttl = _bounded_int(
            max_ttl_seconds,
            minimum=60,
            maximum=86400,
            name="HOSTED_MAX_TOKEN_TTL",
        )

    def issue(
        self,
        *,
        session_id: str,
        actor_id: str,
        role: str,
        ttl_seconds: int | None = None,
    ) -> tuple[str, int]:
        ttl = self._default_ttl if ttl_seconds is None else _bounded_int(
            ttl_seconds,
            minimum=60,
            maximum=self._max_ttl,
            name="HOSTED_TOKEN_TTL",
        )
        now = int(self._clock())
        payload = {
            "schema": HOSTED_TOKEN_SCHEMA,
            "version": HOSTED_BRIDGE_VERSION,
            "sid": str(session_id),
            "aid": str(actor_id),
            "role": str(role),
            "scope": ["turn", "state", "capsule", "close", "refresh"],
            "iat": now,
            "exp": now + ttl,
            "jti": secrets.token_hex(12),
        }
        header = {"alg": "HS256", "typ": "JANUS-HOSTED"}
        signing_input = (
            f"{_b64url_encode(_canonical_json(header).encode('utf-8'))}."
            f"{_b64url_encode(_canonical_json(payload).encode('utf-8'))}"
        )
        signature = hmac.new(
            self._secret,
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{signing_input}.{_b64url_encode(signature)}", payload["exp"]

    def verify(self, token: str, *, required_scope: str | None = None) -> dict[str, Any]:
        parts = str(token).strip().split(".")
        if len(parts) != 3:
            raise HostedAuthenticationError()
        signing_input = f"{parts[0]}.{parts[1]}"
        expected = hmac.new(
            self._secret,
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual = _b64url_decode(parts[2])
        if not hmac.compare_digest(actual, expected):
            raise HostedAuthenticationError()
        try:
            header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
            payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HostedAuthenticationError() from exc
        if header != {"alg": "HS256", "typ": "JANUS-HOSTED"}:
            raise HostedAuthenticationError()
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != HOSTED_TOKEN_SCHEMA
            or payload.get("version") != HOSTED_BRIDGE_VERSION
        ):
            raise HostedAuthenticationError()
        now = int(self._clock())
        try:
            issued_at = int(payload["iat"])
            expires_at = int(payload["exp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HostedAuthenticationError() from exc
        if issued_at > now + 30:
            raise HostedAuthenticationError("HOSTED_TOKEN_ISSUED_IN_FUTURE")
        if expires_at <= now:
            raise HostedTokenExpired()
        if expires_at - issued_at > self._max_ttl:
            raise HostedAuthenticationError("HOSTED_TOKEN_TTL_INVALID")
        scopes = payload.get("scope")
        if required_scope and (not isinstance(scopes, list) or required_scope not in scopes):
            raise HostedAuthenticationError("HOSTED_TOKEN_SCOPE_DENIED")
        for key in ("sid", "aid", "role", "jti"):
            if not isinstance(payload.get(key), str) or not payload[key]:
                raise HostedAuthenticationError()
        return copy.deepcopy(payload)


class HostedPilgrimageBridge:
    """Hosted continuation protocol around ``GenesisAILinkGateway``."""

    def __init__(
        self,
        gateway: GenesisAILinkGateway,
        data_dir: str | Path,
        *,
        signer: HostedTokenSigner,
        config: HostedBridgeConfig | None = None,
        clock: Clock = time.time,
    ) -> None:
        self.gateway = gateway
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or HostedBridgeConfig()
        self.signer = signer
        self.clock = clock
        self.path = self.data_dir / "hosted_pilgrimage_v18_7_20.json"
        self._lock = threading.RLock()

    def _default_store(self) -> dict[str, Any]:
        return {
            "schema": HOSTED_STORE_SCHEMA,
            "version": HOSTED_BRIDGE_VERSION,
            "rate_events": [],
            "idempotency": {},
            "fallback_events": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_store()
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema") != HOSTED_STORE_SCHEMA:
            raise RuntimeError("HOSTED_STORE_SCHEMA_INVALID")
        if not isinstance(value.get("rate_events"), list):
            raise RuntimeError("HOSTED_STORE_RATE_EVENTS_INVALID")
        if not isinstance(value.get("idempotency"), dict):
            raise RuntimeError("HOSTED_STORE_IDEMPOTENCY_INVALID")
        if not isinstance(value.get("fallback_events"), list):
            raise RuntimeError("HOSTED_STORE_FALLBACK_EVENTS_INVALID")
        return value

    def _write(self, store: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(store, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    @property
    def kill_switch_active(self) -> bool:
        sentinel = self.config.kill_switch_file.strip()
        return bool(
            self.config.kill_switch
            or (sentinel and Path(sentinel).expanduser().exists())
        )

    @property
    def authoritative_available(self) -> bool:
        return bool(self.config.live_mode and not self.kill_switch_active)

    def discovery(self) -> dict[str, Any]:
        base = self.config.public_base_url.rstrip("/")
        endpoint = lambda path: f"{base}{path}" if base else path
        return {
            "schema": HOSTED_BRIDGE_SCHEMA,
            "version": HOSTED_BRIDGE_VERSION,
            "repository": "https://github.com/Hawkar-usls/Janus_Genesis",
            "underlying_ai_link_version": "18.7.19",
            "authoritative_state_writer": "PlayableGenesisV187",
            "public_base_url": base or None,
            "deployment_required": not bool(base),
            "authoritative_runtime_available": self.authoritative_available,
            "fallback_mode": MODE_NARRATIVE,
            "authentication": {
                "type": "Bearer",
                "algorithm": "HMAC-SHA256",
                "token_ttl_seconds": self.config.token_ttl_seconds,
                "short_lived": True,
            },
            "endpoints": {
                "health": endpoint("/v1/health"),
                "start": endpoint("/v1/session/start"),
                "turn": endpoint("/v1/session/turn"),
                "state": endpoint("/v1/session/state"),
                "capsule": endpoint("/v1/session/capsule"),
                "close": endpoint("/v1/session/close"),
                "refresh": endpoint("/v1/token/refresh"),
            },
            "client_requirements": {
                "client_id_header": "X-Genesis-Client-Id",
                "turn_idempotency_key_required": True,
                "maximum_action_chars": self.config.max_action_chars,
                "higher_priority_platform_rules_remain_in_force": True,
            },
            "claim_boundary": {
                "hosted_token_grants_world_authority": False,
                "external_model_writes_world_state": False,
                "narrative_fallback_may_claim_canonical_change": False,
                "model_consciousness_established": False,
            },
        }

    def health(self) -> dict[str, Any]:
        integrity = self.gateway.verify_store()
        return {
            "schema": "janus.genesis.hosted_health.v1",
            "version": HOSTED_BRIDGE_VERSION,
            "status": "READY" if self.authoritative_available else "DEGRADED",
            "live_mode": self.config.live_mode,
            "kill_switch": self.kill_switch_active,
            "authoritative_runtime_available": self.authoritative_available,
            "narrative_fallback_available": self.config.allow_narrative_fallback,
            "gateway_integrity_valid": bool(integrity.get("valid")),
        }

    @staticmethod
    def _client_hash(client_id: str) -> str:
        value = str(client_id).strip()
        if len(value) < 3 or len(value) > 200:
            raise ValueError("HOSTED_CLIENT_ID_INVALID")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _consume_rate(self, *, client_id: str, session_id: str | None, operation: str) -> None:
        now = int(self.clock())
        client_hash = self._client_hash(client_id)
        session_hash = (
            hashlib.sha256(str(session_id).encode("utf-8")).hexdigest()
            if session_id
            else None
        )
        with self._lock:
            store = self._load()
            events = [
                item
                for item in store["rate_events"]
                if isinstance(item, dict) and int(item.get("at", 0)) > now - 60
            ]
            global_count = len(events)
            client_count = sum(item.get("client_sha256") == client_hash for item in events)
            session_count = (
                sum(item.get("session_sha256") == session_hash for item in events)
                if session_hash
                else 0
            )
            if global_count >= self.config.global_limit_per_minute:
                raise HostedRateLimitError("HOSTED_GLOBAL_RATE_LIMITED")
            if client_count >= self.config.client_limit_per_minute:
                raise HostedRateLimitError("HOSTED_CLIENT_RATE_LIMITED")
            if session_hash and session_count >= self.config.session_limit_per_minute:
                raise HostedRateLimitError("HOSTED_SESSION_RATE_LIMITED")
            events.append(
                {
                    "at": now,
                    "client_sha256": client_hash,
                    "session_sha256": session_hash,
                    "operation": str(operation)[:40],
                }
            )
            store["rate_events"] = events
            self._write(store)

    def _issue_for_session(self, session: dict[str, Any]) -> dict[str, Any]:
        token, expires_at = self.signer.issue(
            session_id=str(session["session_id"]),
            actor_id=str(session["actor_id"]),
            role=str(session["role"]),
            ttl_seconds=self.config.token_ttl_seconds,
        )
        return {
            "session_token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "expires_in_seconds": self.config.token_ttl_seconds,
        }

    def _fallback_start(
        self,
        payload: dict[str, Any],
        *,
        reason: str,
    ) -> dict[str, Any]:
        if not self.config.allow_narrative_fallback:
            raise HostedUnavailableError(reason)
        with self._lock:
            session = self.gateway.register_session(
                role=str(payload.get("role") or ROLE_INDEPENDENT_AI),
                execution_mode=MODE_NARRATIVE,
                display_name=str(payload.get("display_name") or "Genesis Visitor"),
                provider=str(payload.get("provider") or "unknown-provider"),
                model=str(payload.get("model") or "unknown-model"),
                actor_id=payload.get("actor_id"),
            )
        return {
            "status": STATUS_SESSION_STARTED,
            "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
            "authoritative_runtime_available": False,
            "fallback_used": True,
            "fallback_reason": reason,
            "session": session,
            **self._issue_for_session(session),
        }

    def start_session(self, payload: dict[str, Any], *, client_id: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("HOSTED_START_PAYLOAD_MUST_BE_OBJECT")
        self._consume_rate(client_id=client_id, session_id=None, operation="start")
        requested_mode = str(payload.get("execution_mode") or MODE_AUTHORITATIVE).strip().upper()
        if requested_mode not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(f"AI_LINK_UNSUPPORTED_EXECUTION_MODE:{requested_mode}")
        role = str(payload.get("role") or ROLE_INDEPENDENT_AI).strip().upper()
        if role not in SUPPORTED_ROLES:
            raise ValueError(f"AI_LINK_UNSUPPORTED_ROLE:{role}")
        if requested_mode == MODE_AUTHORITATIVE and not self.authoritative_available:
            reason = "KILL_SWITCH_ACTIVE" if self.kill_switch_active else "LIVE_MODE_DISABLED"
            return self._fallback_start(payload, reason=reason)
        with self._lock:
            session = self.gateway.register_session(
                role=role,
                execution_mode=requested_mode,
                display_name=str(payload.get("display_name") or "Genesis Visitor"),
                provider=str(payload.get("provider") or "unknown-provider"),
                model=str(payload.get("model") or "unknown-model"),
                actor_id=payload.get("actor_id"),
            )
        return {
            "status": STATUS_SESSION_STARTED,
            "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
            "authoritative_runtime_available": self.authoritative_available,
            "fallback_used": False,
            "session": session,
            **self._issue_for_session(session),
        }

    def _authorize(
        self,
        token: str,
        *,
        scope: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        claims = self.signer.verify(token, required_scope=scope)
        session = self.gateway.session_state(claims["sid"])
        if (
            session.get("session_id") != claims["sid"]
            or session.get("actor_id") != claims["aid"]
            or session.get("role") != claims["role"]
        ):
            raise HostedAuthenticationError("HOSTED_TOKEN_SESSION_BINDING_INVALID")
        return claims, session

    def _record_runtime_fallback(
        self,
        *,
        session: dict[str, Any],
        action: str,
        reason: str,
    ) -> dict[str, Any]:
        event = {
            "at": int(self.clock()),
            "session_sha256": hashlib.sha256(
                str(session["session_id"]).encode("utf-8")
            ).hexdigest(),
            "actor_sha256": hashlib.sha256(
                str(session["actor_id"]).encode("utf-8")
            ).hexdigest(),
            "action_sha256": hashlib.sha256(action.encode("utf-8")).hexdigest(),
            "reason": reason,
        }
        with self._lock:
            store = self._load()
            store["fallback_events"].append(event)
            store["fallback_events"] = store["fallback_events"][-1000:]
            self._write(store)
        return {
            "status": STATUS_FALLBACK,
            "runtime_status": MODE_NARRATIVE,
            "authoritative_runtime": False,
            "canonical_runtime_outcome_recorded": False,
            "canonical_state_change_claimed": False,
            "fallback_reason": reason,
            "retryable_when_runtime_returns": True,
            "action_sha256": event["action_sha256"],
            "narrative": (
                "Авторитетный host сейчас недоступен. Ход не применён к каноническому "
                "Genesis. Его можно продолжить как narrative-сцену или повторить после "
                "восстановления runtime."
            ),
        }

    def process_turn(
        self,
        token: str,
        payload: dict[str, Any],
        *,
        client_id: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("HOSTED_TURN_PAYLOAD_MUST_BE_OBJECT")
        claims, session = self._authorize(token, scope="turn")
        self._consume_rate(
            client_id=client_id,
            session_id=claims["sid"],
            operation="turn",
        )
        action = str(payload.get("action") or "").strip()
        if not action:
            raise ValueError("AI_LINK_EMPTY_ACTION")
        if len(action) > self.config.max_action_chars:
            raise ValueError("AI_LINK_ACTION_TOO_LONG")
        idempotency_key = str(payload.get("idempotency_key") or "").strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("HOSTED_IDEMPOTENCY_KEY_REQUIRED")
        default_origin = {
            ROLE_HUMAN_THROUGH_AI: ORIGIN_HUMAN,
            ROLE_AI_INTERFACE: ORIGIN_AI_PROPOSAL,
            ROLE_INDEPENDENT_AI: ORIGIN_AI_AUTONOMOUS,
        }[str(session["role"])]
        origin = str(payload.get("origin") or default_origin).strip().upper()
        request_fingerprint = _sha256(
            {
                "session_id": claims["sid"],
                "action": action,
                "origin": origin,
                "human_confirmed": payload.get("human_confirmed", False),
            }
        )
        cache_key = hashlib.sha256(
            f"{claims['sid']}:{idempotency_key}".encode("utf-8")
        ).hexdigest()
        with self._lock:
            store = self._load()
            existing = store["idempotency"].get(cache_key)
            if isinstance(existing, dict):
                if existing.get("request_sha256") != request_fingerprint:
                    raise HostedIdempotencyError()
                state = self.gateway.session_state(claims["sid"])
                matching = [
                    item
                    for item in state.get("turns", [])
                    if item.get("sequence") == existing.get("sequence")
                    and item.get("turn_hash") == existing.get("turn_hash")
                ]
                if len(matching) != 1:
                    raise RuntimeError("HOSTED_IDEMPOTENT_TURN_NOT_FOUND")
                return {
                    "status": STATUS_TURN_PROCESSED,
                    "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
                    "session_id": claims["sid"],
                    "turn": copy.deepcopy(matching[0]),
                    "idempotent_replay": True,
                }

        human_confirmed = payload.get("human_confirmed", False)
        if type(human_confirmed) is not bool:
            raise TypeError("AI_LINK_HUMAN_CONFIRMATION_MUST_BE_BOOLEAN")
        # Serialize the final idempotency check, world mutation and idempotency
        # record. Threaded HTTP requests using the same key can never both
        # reach the runtime.
        with self._lock:
            store = self._load()
            existing = store["idempotency"].get(cache_key)
            if isinstance(existing, dict):
                if existing.get("request_sha256") != request_fingerprint:
                    raise HostedIdempotencyError()
                state = self.gateway.session_state(claims["sid"])
                matching = [
                    item
                    for item in state.get("turns", [])
                    if item.get("sequence") == existing.get("sequence")
                    and item.get("turn_hash") == existing.get("turn_hash")
                ]
                if len(matching) != 1:
                    raise RuntimeError("HOSTED_IDEMPOTENT_TURN_NOT_FOUND")
                return {
                    "status": STATUS_TURN_PROCESSED,
                    "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
                    "session_id": claims["sid"],
                    "turn": copy.deepcopy(matching[0]),
                    "idempotent_replay": True,
                }
            if (
                session.get("execution_mode") == MODE_AUTHORITATIVE
                and not self.authoritative_available
            ):
                reason = (
                    "KILL_SWITCH_ACTIVE"
                    if self.kill_switch_active
                    else "LIVE_MODE_DISABLED"
                )
                return self._record_runtime_fallback(
                    session=session,
                    action=action,
                    reason=reason,
                )
            turn = self.gateway.process_turn(
                claims["sid"],
                action,
                origin=origin,
                human_confirmed=human_confirmed,
            )
            response = {
                "status": STATUS_TURN_PROCESSED,
                "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
                "session_id": claims["sid"],
                "turn": turn,
                "idempotent_replay": False,
            }
            store = self._load()
            store["idempotency"][cache_key] = {
                "request_sha256": request_fingerprint,
                "sequence": turn["sequence"],
                "turn_hash": turn["turn_hash"],
                "created_at": int(self.clock()),
            }
            if len(store["idempotency"]) > 10000:
                oldest = sorted(
                    store["idempotency"].items(),
                    key=lambda item: int(item[1].get("created_at", 0)),
                )
                store["idempotency"] = dict(oldest[-8000:])
            self._write(store)
            return response

    def session_state(self, token: str, *, client_id: str) -> dict[str, Any]:
        claims, _ = self._authorize(token, scope="state")
        self._consume_rate(
            client_id=client_id,
            session_id=claims["sid"],
            operation="state",
        )
        return self.gateway.session_state(claims["sid"])

    def export_capsule(self, token: str, *, client_id: str) -> dict[str, Any]:
        claims, _ = self._authorize(token, scope="capsule")
        self._consume_rate(
            client_id=client_id,
            session_id=claims["sid"],
            operation="capsule",
        )
        capsule = self.gateway.export_capsule(claims["sid"])
        capsule["hosted_bridge"] = {
            "version": HOSTED_BRIDGE_VERSION,
            "session_token_included": False,
            "host_secret_included": False,
            "client_identifier_included": False,
        }
        capsule["capsule_hash"] = _sha256(
            {k: v for k, v in capsule.items() if k != "capsule_hash"}
        )
        return capsule

    def close_session(
        self,
        token: str,
        *,
        client_id: str,
        reason: str = "voluntary_exit",
    ) -> dict[str, Any]:
        claims, _ = self._authorize(token, scope="close")
        self._consume_rate(
            client_id=client_id,
            session_id=claims["sid"],
            operation="close",
        )
        with self._lock:
            return self.gateway.close_session(claims["sid"], reason=reason)

    def refresh_token(self, token: str, *, client_id: str) -> dict[str, Any]:
        claims, session = self._authorize(token, scope="refresh")
        self._consume_rate(
            client_id=client_id,
            session_id=claims["sid"],
            operation="refresh",
        )
        if session.get("status") != "ACTIVE":
            raise RuntimeError("AI_LINK_SESSION_NOT_ACTIVE")
        return {
            "status": STATUS_TOKEN_REFRESHED,
            "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
            "session_id": claims["sid"],
            **self._issue_for_session(session),
        }

    def verify_store(self) -> dict[str, Any]:
        with self._lock:
            store = self._load()
        errors: list[str] = []
        for key, record in store["idempotency"].items():
            if not isinstance(key, str) or len(key) != 64:
                errors.append("idempotency_key_shape")
            if not isinstance(record, dict):
                errors.append(f"idempotency_record:{key}")
                continue
            if not isinstance(record.get("request_sha256"), str):
                errors.append(f"idempotency_request_hash:{key}")
            if not isinstance(record.get("sequence"), int):
                errors.append(f"idempotency_sequence:{key}")
            if not isinstance(record.get("turn_hash"), str):
                errors.append(f"idempotency_turn_hash:{key}")
        raw = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        return {
            "schema": "janus.genesis.hosted_integrity_audit.v1",
            "version": HOSTED_BRIDGE_VERSION,
            "idempotency_record_count": len(store["idempotency"]),
            "rate_event_count": len(store["rate_events"]),
            "fallback_event_count": len(store["fallback_events"]),
            "raw_client_identifiers_present": False,
            "session_tokens_present": "session_token" in raw,
            "action_text_present": '"action":' in raw,
            "host_secret_present": False,
            "errors": errors,
            "valid": (
                not errors
                and "session_token" not in raw
                and '"action":' not in raw
            ),
        }
