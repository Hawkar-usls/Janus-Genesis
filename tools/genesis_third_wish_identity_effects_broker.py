# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.44 — Third Wish external identity-effect broker.

This layer opens four already-declared capability classes without turning an
operator account or broker credential into ambient authority:

* PUBLICATION.PUBLISH — publish through an operator-registered relay alias;
* EMAIL.SEND — send one exact, reauthorized message through a relay alias;
* CALENDAR.WRITE — create/update one exact, reauthorized calendar effect;
* BROKER.CREDENTIAL.USE — perform a narrow authenticated probe without exposing
  raw credential material or becoming a generic API tunnel.

The reference path requires an exact-intent HMAC-bound human reauthorization
verifier. Raw credential material remains in broker environment variables and
is never accepted in ActionIntent parameters or returned to the actor.

External effects have their own durable request/effect state. After the broker
crosses EFFECT_ENTERING, restart never authorizes a blind retry. Provider lookup
may recover a SETTLED receipt or prove NO_EFFECT. A proven NO_EFFECT closes that
request as a non-effect; retry requires a new request_id and new reauthorization.

This is a cooperating broker protocol, not an OS sandbox and not evidence that a
third-party account, platform, delivery, audience, or human response is truthful.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import ipaddress
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from genesis_v18_7_35_windows_safe_durable_writer import WindowsSafeDurableJsonWriter
from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    ThirdWishCapabilityFabric,
)
from janus_portable_lock_v2 import PortableProcessLockV2

IDENTITY_EFFECTS_VERSION = "18.7.44"
IDENTITY_EFFECT_STORE_SCHEMA = "janus.genesis.third_wish.identity_effect_store.v1"
IDENTITY_REAUTH_SCHEMA = "janus.genesis.third_wish.identity_reauthorization.v1"
IDENTITY_RELAY_RECEIPT_SCHEMA = "janus.genesis.third_wish.identity_relay_receipt.v1"
MAX_PUBLICATION_TITLE_BYTES = 1024
MAX_PUBLICATION_BODY_BYTES = 128 * 1024
MAX_EMAIL_SUBJECT_BYTES = 2048
MAX_EMAIL_BODY_BYTES = 128 * 1024
MAX_EMAIL_RECIPIENTS = 32
MAX_CALENDAR_TEXT_BYTES = 32 * 1024
MAX_RELAY_RESPONSE_BYTES = 256 * 1024
MAX_PROBE_PURPOSE_BYTES = 2048


class IdentityEffectError(RuntimeError):
    pass


class IdentityRequestConflict(IdentityEffectError):
    pass


class IdentityEffectOutcomeUndetermined(IdentityEffectError):
    pass


class IdentityReceiptIntegrityError(IdentityEffectError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_size(value: Any) -> int:
    return len(_canonical(value).encode("utf-8"))


def _require(parameters: Mapping[str, Any], key: str) -> Any:
    if key not in parameters:
        raise IdentityEffectError(f"MISSING_PARAMETER:{key}")
    return parameters[key]


_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_EMAIL_RE = re.compile(r"^[^\s@<>\x00-\x1f\x7f]+@[^\s@<>\x00-\x1f\x7f]+$")


def _alias_from_target(target: str, prefix: str) -> str:
    text = str(target).strip()
    marker = prefix + ":"
    if not text.startswith(marker):
        raise IdentityEffectError(f"TARGET_PREFIX_REQUIRED:{marker}")
    alias = text[len(marker):]
    if not _ALIAS_RE.fullmatch(alias):
        raise IdentityEffectError("INVALID_ALIAS")
    return alias


def _parse_utc(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise IdentityEffectError("UTC_TIME_INVALID") from exc
    if parsed.tzinfo is None:
        raise IdentityEffectError("UTC_TIME_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


def _intent_payload(intent: ActionIntent) -> dict[str, Any]:
    return {
        "schema": intent.schema,
        "request_id": intent.request_id,
        "actor_id": intent.actor_id,
        "grant_id": intent.grant_id,
        "capability_id": intent.capability_id,
        "target": intent.target,
        "operation": intent.operation,
        "purpose": intent.purpose,
        "parameters": copy.deepcopy(dict(intent.parameters)),
        "origin": intent.origin,
        "operator_instruction_present": intent.operator_instruction_present,
        "reward_present": intent.reward_present,
    }


def _intent_sha256(intent: ActionIntent) -> str:
    return _sha256(_intent_payload(intent))


class BoundIdentityReauthorizationVerifier:
    """Exact-intent HMAC verifier for high-impact identity effects.

    The HMAC key is broker-side. Evidence contains no raw secret and is bound to
    the complete ActionIntent plus an approval id and a bounded validity window.
    Replaying the same approval for a different recipient/body/event fails.
    """

    def __init__(
        self,
        *,
        key_env: str,
        now_tick: Callable[[], int],
        max_window_ticks: int = 10 * 60 * 1000,
    ) -> None:
        self.key_env = str(key_env)
        self.now_tick = now_tick
        self.max_window_ticks = int(max_window_ticks)
        if self.max_window_ticks < 1:
            raise ValueError("REAUTH_WINDOW_MUST_BE_POSITIVE")

    @staticmethod
    def unsigned_payload(intent: ActionIntent, evidence: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "schema": IDENTITY_REAUTH_SCHEMA,
            "approval_id": str(evidence.get("approval_id") or ""),
            "request_id": intent.request_id,
            "actor_id": intent.actor_id,
            "capability_id": intent.capability_id,
            "target": intent.target,
            "operation": intent.operation,
            "intent_sha256": _intent_sha256(intent),
            "parameters_sha256": _sha256(dict(intent.parameters)),
            "issued_at_tick": int(evidence.get("issued_at_tick") or 0),
            "expires_at_tick": int(evidence.get("expires_at_tick") or 0),
        }

    def __call__(self, intent: ActionIntent, evidence: Mapping[str, Any]) -> bool:
        try:
            if evidence.get("schema") != IDENTITY_REAUTH_SCHEMA:
                return False
            if not str(evidence.get("approval_id") or "").strip():
                return False
            supplied_signature = str(evidence.get("approval_signature") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", supplied_signature):
                return False
            unsigned = self.unsigned_payload(intent, evidence)
            now = int(self.now_tick())
            issued = int(unsigned["issued_at_tick"])
            expires = int(unsigned["expires_at_tick"])
            if issued > now or expires < now or expires <= issued:
                return False
            if expires - issued > self.max_window_ticks:
                return False
            key = os.environ.get(self.key_env)
            if not key:
                return False
            expected = hmac.new(
                key.encode("utf-8"),
                _canonical(unsigned).encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, supplied_signature)
        except (TypeError, ValueError, OverflowError):
            return False


@dataclass(frozen=True)
class IdentityRelayAlias:
    alias: str
    endpoint: str
    api_key_env: str
    account_alias: str
    credential_alias: str
    allowed_capabilities: frozenset[str]
    timeout_seconds: float = 20.0

    @classmethod
    def build(
        cls,
        *,
        alias: str,
        endpoint: str,
        api_key_env: str,
        account_alias: str,
        credential_alias: str,
        allowed_capabilities: Sequence[str],
        timeout_seconds: float = 20.0,
        allow_loopback_http: bool = False,
    ) -> "IdentityRelayAlias":
        for value, label in (
            (alias, "relay_alias"),
            (account_alias, "account_alias"),
            (credential_alias, "credential_alias"),
        ):
            if not _ALIAS_RE.fullmatch(str(value)):
                raise ValueError(f"INVALID_{label.upper()}")
        parsed = urllib.parse.urlparse(str(endpoint).rstrip("/"))
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("IDENTITY_RELAY_ENDPOINT_INVALID")
        if parsed.scheme == "http":
            is_loopback = False
            try:
                is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                is_loopback = parsed.hostname.lower() == "localhost"
            if not (allow_loopback_http and is_loopback):
                raise ValueError("IDENTITY_RELAY_HTTP_ONLY_ALLOWED_FOR_EXPLICIT_LOOPBACK_TEST")
        allowed = frozenset(str(x) for x in allowed_capabilities)
        valid = {
            "PUBLICATION.PUBLISH",
            "EMAIL.SEND",
            "CALENDAR.WRITE",
            "BROKER.CREDENTIAL.USE",
        }
        if not allowed or not allowed.issubset(valid):
            raise ValueError("IDENTITY_RELAY_CAPABILITY_SET_INVALID")
        return cls(
            alias=str(alias),
            endpoint=str(endpoint).rstrip("/"),
            api_key_env=str(api_key_env),
            account_alias=str(account_alias),
            credential_alias=str(credential_alias),
            allowed_capabilities=allowed,
            timeout_seconds=float(timeout_seconds),
        )


class IdentityRelayClient:
    def __init__(self, config: IdentityRelayAlias) -> None:
        self.config = config

    def _key(self) -> str:
        value = os.environ.get(self.config.api_key_env)
        if not value:
            raise IdentityEffectOutcomeUndetermined("IDENTITY_RELAY_KEY_MISSING")
        return value

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._key()}",
        }
        if payload is not None:
            body = _canonical(dict(payload)).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.config.endpoint + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(MAX_RELAY_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            raise IdentityEffectOutcomeUndetermined(
                f"IDENTITY_RELAY_HTTP_{exc.code}:{_sha256(detail)}"
            ) from exc
        except urllib.error.URLError as exc:
            raise IdentityEffectOutcomeUndetermined("IDENTITY_RELAY_CONNECTION_FAILED") from exc
        if len(raw) > MAX_RELAY_RESPONSE_BYTES:
            raise IdentityReceiptIntegrityError("IDENTITY_RELAY_RESPONSE_TOO_LARGE")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IdentityReceiptIntegrityError("IDENTITY_RELAY_RESPONSE_INVALID_JSON") from exc
        if not isinstance(value, dict):
            raise IdentityReceiptIntegrityError("IDENTITY_RELAY_RESPONSE_NOT_OBJECT")
        return value

    def execute(
        self,
        *,
        capability_id: str,
        operation: str,
        effect_key: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        if capability_id not in self.config.allowed_capabilities:
            raise IdentityEffectError("IDENTITY_RELAY_CAPABILITY_NOT_ALLOWED")
        return self._request(
            "POST",
            "/v1/identity/effects",
            payload={
                "schema": "janus.genesis.third_wish.identity_relay_request.v1",
                "effect_key": effect_key,
                "capability_id": capability_id,
                "operation": operation,
                "account_alias": self.config.account_alias,
                "credential_alias": self.config.credential_alias,
                "payload": copy.deepcopy(dict(payload)),
            },
        )

    def lookup(self, effect_key: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(str(effect_key), safe="")
        return self._request("GET", f"/v1/identity/effects/{encoded}")


class DurableIdentityEffectStore:
    """Durable binding and external-effect boundary; never stores raw intent data."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "third_wish_identity_effects_v18_7_44.json"
        self.lock = PortableProcessLockV2(
            self.root / "third_wish_identity_effects_v18_7_44.lock"
        )
        self.writer = WindowsSafeDurableJsonWriter()
        with self.lock.exclusive():
            if not self.path.exists():
                self._save({
                    "schema": IDENTITY_EFFECT_STORE_SCHEMA,
                    "requests": {},
                    "invariants": {
                        "raw_parameters_persisted": False,
                        "effect_entering_auto_retry": False,
                        "proven_no_effect_auto_retry": False,
                        "changed_request_binding_allowed": False,
                        "raw_credentials_persisted": False,
                    },
                })
            else:
                self._load()

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IdentityReceiptIntegrityError("IDENTITY_EFFECT_STORE_UNREADABLE") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema") != IDENTITY_EFFECT_STORE_SCHEMA
            or not isinstance(value.get("requests"), dict)
        ):
            raise IdentityReceiptIntegrityError("IDENTITY_EFFECT_STORE_SCHEMA_INVALID")
        return value

    def _save(self, value: Mapping[str, Any]) -> None:
        self.writer.write(self.path, dict(value))

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self.lock.exclusive():
            row = self._load()["requests"].get(str(request_id))
        return copy.deepcopy(row) if isinstance(row, dict) else None

    def bind(
        self,
        *,
        request_id: str,
        binding_sha256: str,
        effect_key: str,
        capability_id: str,
        relay_alias: str,
    ) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
            existing = state["requests"].get(str(request_id))
            if existing is not None:
                if (
                    not isinstance(existing, dict)
                    or existing.get("binding_sha256") != binding_sha256
                    or existing.get("effect_key") != effect_key
                    or existing.get("capability_id") != capability_id
                    or existing.get("relay_alias") != relay_alias
                ):
                    raise IdentityRequestConflict(str(request_id))
                return copy.deepcopy(existing)
            row = {
                "binding_sha256": binding_sha256,
                "effect_key": effect_key,
                "capability_id": capability_id,
                "relay_alias": relay_alias,
                "state": "BOUND",
                "provider_receipt": None,
                "actor_result": None,
            }
            state["requests"][str(request_id)] = row
            self._save(state)
            return copy.deepcopy(row)

    def update(self, request_id: str, **fields: Any) -> dict[str, Any]:
        with self.lock.exclusive():
            state = self._load()
            row = state["requests"].get(str(request_id))
            if not isinstance(row, dict):
                raise IdentityReceiptIntegrityError("IDENTITY_EFFECT_BINDING_MISSING")
            row.update(copy.deepcopy(fields))
            state["requests"][str(request_id)] = row
            self._save(state)
            return copy.deepcopy(row)


class ThirdWishIdentityEffectsBroker:
    REGISTERED_CAPABILITIES = frozenset({
        "PUBLICATION.PUBLISH",
        "EMAIL.SEND",
        "CALENDAR.WRITE",
        "BROKER.CREDENTIAL.USE",
    })

    def __init__(
        self,
        *,
        data_dir: str | Path,
        relays: Mapping[str, IdentityRelayAlias],
        effect_store: DurableIdentityEffectStore | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.relays = {str(k): v for k, v in relays.items()}
        if not self.relays:
            raise ValueError("AT_LEAST_ONE_IDENTITY_RELAY_REQUIRED")
        for alias, config in self.relays.items():
            if alias != config.alias:
                raise ValueError("IDENTITY_RELAY_ALIAS_KEY_MISMATCH")
        self.clients = {alias: IdentityRelayClient(config) for alias, config in self.relays.items()}
        self.effect_store = effect_store or DurableIdentityEffectStore(self.data_dir)

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        if not isinstance(fabric.reauthorization_verifier, BoundIdentityReauthorizationVerifier):
            raise CapabilityDenied("V18_7_44_REQUIRES_BOUND_IDENTITY_REAUTH_VERIFIER")
        for capability_id in self.REGISTERED_CAPABILITIES:
            spec = fabric.specs.get(capability_id)
            if spec is None or not spec.human_reauthorization_each_use:
                raise CapabilityDenied(
                    f"V18_7_44_CAPABILITY_MUST_REQUIRE_REAUTH:{capability_id}"
                )
            fabric.register_handler(
                capability_id,
                self.execute_identity_effect,
                preflight=self.preflight,
            )

    @staticmethod
    def _target_prefix(capability_id: str) -> str:
        return {
            "PUBLICATION.PUBLISH": "publication",
            "EMAIL.SEND": "email",
            "CALENDAR.WRITE": "calendar",
            "BROKER.CREDENTIAL.USE": "credential",
        }[capability_id]

    def _relay_alias(self, intent: ActionIntent) -> str:
        prefix = self._target_prefix(intent.capability_id)
        return _alias_from_target(intent.target, prefix)

    def _binding(self, intent: ActionIntent) -> tuple[str, str, str]:
        relay_alias = self._relay_alias(intent)
        payload = {
            "actor_id": intent.actor_id,
            "capability_id": intent.capability_id,
            "target": intent.target,
            "operation": intent.operation,
            "parameters": copy.deepcopy(dict(intent.parameters)),
            "relay_alias": relay_alias,
        }
        binding_sha256 = _sha256(payload)
        effect_key = "THIRD-WISH-IDENTITY:" + _sha256({
            "request_id": intent.request_id,
            **payload,
        })
        return binding_sha256, effect_key, relay_alias

    def _relay_for(self, intent: ActionIntent) -> tuple[IdentityRelayAlias, IdentityRelayClient]:
        alias = self._relay_alias(intent)
        config = self.relays.get(alias)
        if config is None:
            raise IdentityEffectError("IDENTITY_RELAY_ALIAS_NOT_REGISTERED")
        if intent.capability_id not in config.allowed_capabilities:
            raise IdentityEffectError("IDENTITY_RELAY_NOT_ALLOWED_FOR_CAPABILITY")
        return config, self.clients[alias]

    @staticmethod
    def _validate_email_addresses(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
        if value is None and allow_empty:
            return []
        if not isinstance(value, list):
            raise IdentityEffectError(f"{label}_MUST_BE_LIST")
        if (not allow_empty and not value) or len(value) > MAX_EMAIL_RECIPIENTS:
            raise IdentityEffectError(f"{label}_COUNT_INVALID")
        clean: list[str] = []
        for item in value:
            text = str(item).strip()
            if not _EMAIL_RE.fullmatch(text):
                raise IdentityEffectError(f"{label}_ADDRESS_INVALID")
            clean.append(text)
        return clean

    @staticmethod
    def _validate_publication(parameters: Mapping[str, Any]) -> None:
        allowed = {"title", "body", "visibility", "tags"}
        if set(parameters).difference(allowed):
            raise IdentityEffectError("PUBLICATION_PARAMETERS_NOT_ALLOWED")
        title = str(_require(parameters, "title"))
        body = str(_require(parameters, "body"))
        visibility = str(parameters.get("visibility") or "public").lower()
        if not title or len(title.encode("utf-8")) > MAX_PUBLICATION_TITLE_BYTES:
            raise IdentityEffectError("PUBLICATION_TITLE_INVALID")
        if not body or len(body.encode("utf-8")) > MAX_PUBLICATION_BODY_BYTES:
            raise IdentityEffectError("PUBLICATION_BODY_INVALID")
        if visibility not in {"public", "unlisted", "private"}:
            raise IdentityEffectError("PUBLICATION_VISIBILITY_INVALID")
        tags = parameters.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 20:
            raise IdentityEffectError("PUBLICATION_TAGS_INVALID")
        for tag in tags:
            if not str(tag).strip() or len(str(tag).encode("utf-8")) > 128:
                raise IdentityEffectError("PUBLICATION_TAG_INVALID")

    @classmethod
    def _validate_email(cls, parameters: Mapping[str, Any]) -> None:
        allowed = {"to", "cc", "subject", "body"}
        if set(parameters).difference(allowed):
            raise IdentityEffectError("EMAIL_PARAMETERS_NOT_ALLOWED")
        cls._validate_email_addresses(_require(parameters, "to"), "EMAIL_TO")
        cls._validate_email_addresses(parameters.get("cc"), "EMAIL_CC", allow_empty=True)
        subject = str(_require(parameters, "subject"))
        body = str(_require(parameters, "body"))
        if "\r" in subject or "\n" in subject:
            raise IdentityEffectError("EMAIL_HEADER_INJECTION_REJECTED")
        if not subject or len(subject.encode("utf-8")) > MAX_EMAIL_SUBJECT_BYTES:
            raise IdentityEffectError("EMAIL_SUBJECT_INVALID")
        if len(body.encode("utf-8")) > MAX_EMAIL_BODY_BYTES:
            raise IdentityEffectError("EMAIL_BODY_TOO_LARGE")

    @classmethod
    def _validate_calendar(cls, operation: str, parameters: Mapping[str, Any]) -> None:
        base = {
            "title",
            "start_utc",
            "end_utc",
            "description",
            "location",
            "attendees",
            "event_ref",
            "expected_version",
        }
        if set(parameters).difference(base):
            raise IdentityEffectError("CALENDAR_PARAMETERS_NOT_ALLOWED")
        title = str(_require(parameters, "title"))
        if not title or len(title.encode("utf-8")) > 4096:
            raise IdentityEffectError("CALENDAR_TITLE_INVALID")
        start = _parse_utc(str(_require(parameters, "start_utc")))
        end = _parse_utc(str(_require(parameters, "end_utc")))
        if end <= start:
            raise IdentityEffectError("CALENDAR_END_MUST_FOLLOW_START")
        for key in ("description", "location"):
            if len(str(parameters.get(key) or "").encode("utf-8")) > MAX_CALENDAR_TEXT_BYTES:
                raise IdentityEffectError(f"CALENDAR_{key.upper()}_TOO_LARGE")
        cls._validate_email_addresses(
            parameters.get("attendees"), "CALENDAR_ATTENDEES", allow_empty=True
        )
        if operation == "UPDATE_EVENT":
            if not str(parameters.get("event_ref") or "").strip():
                raise IdentityEffectError("CALENDAR_UPDATE_EVENT_REF_REQUIRED")
            if not str(parameters.get("expected_version") or "").strip():
                raise IdentityEffectError("CALENDAR_UPDATE_EXPECTED_VERSION_REQUIRED")
        elif operation == "CREATE_EVENT":
            if parameters.get("event_ref") is not None or parameters.get("expected_version") is not None:
                raise IdentityEffectError("CALENDAR_CREATE_CANNOT_SUPPLY_EXISTING_EVENT_REF")
        else:
            raise IdentityEffectError("CALENDAR_OPERATION_NOT_ALLOWED")

    @staticmethod
    def _validate_credential_probe(parameters: Mapping[str, Any]) -> None:
        if set(parameters) != {"purpose_label"}:
            raise IdentityEffectError("CREDENTIAL_PROBE_PARAMETERS_INVALID")
        purpose = str(parameters.get("purpose_label") or "")
        if not purpose or len(purpose.encode("utf-8")) > MAX_PROBE_PURPOSE_BYTES:
            raise IdentityEffectError("CREDENTIAL_PROBE_PURPOSE_INVALID")

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        if intent.capability_id not in self.REGISTERED_CAPABILITIES:
            raise IdentityEffectError("IDENTITY_CAPABILITY_NOT_INSTALLED")
        config, _client = self._relay_for(intent)
        operation = str(intent.operation).upper()
        p = dict(intent.parameters)
        if intent.capability_id == "PUBLICATION.PUBLISH":
            if operation != "PUBLISH":
                raise IdentityEffectError("PUBLICATION_OPERATION_REQUIRED")
            self._validate_publication(p)
        elif intent.capability_id == "EMAIL.SEND":
            if operation != "SEND":
                raise IdentityEffectError("EMAIL_SEND_OPERATION_REQUIRED")
            self._validate_email(p)
        elif intent.capability_id == "CALENDAR.WRITE":
            self._validate_calendar(operation, p)
        elif intent.capability_id == "BROKER.CREDENTIAL.USE":
            if operation != "AUTHENTICATED_PROBE":
                raise IdentityEffectError("CREDENTIAL_USE_IS_NOT_GENERIC_API_TUNNEL")
            self._validate_credential_probe(p)
        binding_sha256, effect_key, relay_alias = self._binding(intent)
        existing = self.effect_store.get(intent.request_id)
        if existing is not None:
            if (
                existing.get("binding_sha256") != binding_sha256
                or existing.get("effect_key") != effect_key
                or existing.get("relay_alias") != relay_alias
                or existing.get("capability_id") != intent.capability_id
            ):
                raise IdentityRequestConflict(intent.request_id)
        return {
            "validated": True,
            "capability_id": intent.capability_id,
            "operation": operation,
            "relay_alias": relay_alias,
            "account_alias_sha256": _sha256(config.account_alias),
            "credential_alias_sha256": _sha256(config.credential_alias),
            "raw_credential_visible_to_actor": False,
            "generic_api_tunnel": False,
            "durable_request_state": "UNBOUND" if existing is None else existing.get("state"),
            "automatic_retry_after_effect_entering": False,
        }

    @staticmethod
    def _validate_receipt(
        receipt: Mapping[str, Any],
        *,
        effect_key: str,
        capability_id: str,
        config: IdentityRelayAlias,
    ) -> dict[str, Any]:
        value = copy.deepcopy(dict(receipt))
        required = {
            "schema",
            "provider_receipt_id",
            "effect_key",
            "capability_id",
            "effect_acknowledged",
            "account_alias",
            "credential_alias",
            "remote_effect_id",
            "provider_status",
            "raw_credential_exposed",
        }
        if set(value) != required:
            raise IdentityReceiptIntegrityError("IDENTITY_PROVIDER_RECEIPT_FIELDS_INVALID")
        if value.get("schema") != IDENTITY_RELAY_RECEIPT_SCHEMA:
            raise IdentityReceiptIntegrityError("IDENTITY_PROVIDER_RECEIPT_SCHEMA_INVALID")
        if str(value.get("effect_key")) != effect_key:
            raise IdentityReceiptIntegrityError("IDENTITY_EFFECT_KEY_MISMATCH")
        if str(value.get("capability_id")) != capability_id:
            raise IdentityReceiptIntegrityError("IDENTITY_CAPABILITY_RECEIPT_MISMATCH")
        if value.get("effect_acknowledged") is not True:
            raise IdentityReceiptIntegrityError("IDENTITY_EFFECT_NOT_ACKNOWLEDGED")
        if str(value.get("account_alias")) != config.account_alias:
            raise IdentityReceiptIntegrityError("IDENTITY_ACCOUNT_ALIAS_MISMATCH")
        if str(value.get("credential_alias")) != config.credential_alias:
            raise IdentityReceiptIntegrityError("IDENTITY_CREDENTIAL_ALIAS_MISMATCH")
        if value.get("raw_credential_exposed") is not False:
            raise IdentityReceiptIntegrityError("RAW_CREDENTIAL_EXPOSURE_REJECTED")
        if not str(value.get("provider_receipt_id") or "").strip():
            raise IdentityReceiptIntegrityError("IDENTITY_PROVIDER_RECEIPT_ID_REQUIRED")
        if not str(value.get("remote_effect_id") or "").strip():
            raise IdentityReceiptIntegrityError("IDENTITY_REMOTE_EFFECT_ID_REQUIRED")
        if str(value.get("provider_status") or "").upper() != "SETTLED":
            raise IdentityReceiptIntegrityError("IDENTITY_PROVIDER_STATUS_NOT_SETTLED")
        return value

    def _settled_actor_result(
        self,
        *,
        intent: ActionIntent,
        config: IdentityRelayAlias,
        receipt: Mapping[str, Any],
        recovered: bool,
    ) -> dict[str, Any]:
        return {
            "capability_id": intent.capability_id,
            "relay_alias": config.alias,
            "account_alias": config.account_alias,
            "provider_receipt": copy.deepcopy(dict(receipt)),
            "parameters_sha256": _sha256(dict(intent.parameters)),
            "external_identity_effect_established": True,
            "raw_parameters_persisted_by_third_wish_store": False,
            "raw_credential_visible_to_actor": False,
            "credential_exported": False,
            "generic_api_tunnel": False,
            "recovered_from_provider_lookup": bool(recovered),
        }

    def execute_identity_effect(self, intent: ActionIntent) -> Mapping[str, Any]:
        config, client = self._relay_for(intent)
        binding_sha256, effect_key, relay_alias = self._binding(intent)
        stored = self.effect_store.bind(
            request_id=intent.request_id,
            binding_sha256=binding_sha256,
            effect_key=effect_key,
            capability_id=intent.capability_id,
            relay_alias=relay_alias,
        )
        state = str(stored.get("state") or "")
        if state == "SETTLED":
            actor_result = stored.get("actor_result")
            if not isinstance(actor_result, Mapping):
                raise IdentityReceiptIntegrityError("SETTLED_IDENTITY_REQUEST_HAS_NO_RESULT")
            return copy.deepcopy(dict(actor_result))
        if state == "PROVEN_NO_EFFECT":
            actor_result = stored.get("actor_result")
            if not isinstance(actor_result, Mapping):
                raise IdentityReceiptIntegrityError("NO_EFFECT_IDENTITY_REQUEST_HAS_NO_RESULT")
            return copy.deepcopy(dict(actor_result))
        if state == "EFFECT_ENTERING":
            observation = client.lookup(effect_key)
            status = str(observation.get("status") or "UNKNOWN").upper()
            if observation.get("authoritative") is not True:
                raise IdentityEffectOutcomeUndetermined("IDENTITY_LOOKUP_NOT_AUTHORITATIVE")
            if status == "SETTLED":
                receipt = observation.get("provider_receipt")
                if not isinstance(receipt, Mapping):
                    raise IdentityReceiptIntegrityError("SETTLED_LOOKUP_RECEIPT_REQUIRED")
                verified = self._validate_receipt(
                    receipt,
                    effect_key=effect_key,
                    capability_id=intent.capability_id,
                    config=config,
                )
                actor_result = self._settled_actor_result(
                    intent=intent,
                    config=config,
                    receipt=verified,
                    recovered=True,
                )
                self.effect_store.update(
                    intent.request_id,
                    state="SETTLED",
                    provider_receipt=verified,
                    actor_result=actor_result,
                )
                return actor_result
            if status == "NO_EFFECT":
                actor_result = {
                    "capability_id": intent.capability_id,
                    "relay_alias": config.alias,
                    "account_alias": config.account_alias,
                    "parameters_sha256": _sha256(dict(intent.parameters)),
                    "external_identity_effect_established": False,
                    "authoritative_no_effect_established": True,
                    "same_request_auto_retry": False,
                    "retry_requires_new_request_id": True,
                    "retry_requires_new_human_reauthorization": True,
                    "raw_credential_visible_to_actor": False,
                    "credential_exported": False,
                }
                self.effect_store.update(
                    intent.request_id,
                    state="PROVEN_NO_EFFECT",
                    provider_receipt=None,
                    actor_result=actor_result,
                )
                return actor_result
            raise IdentityEffectOutcomeUndetermined("IDENTITY_EFFECT_OUTCOME_UNKNOWN")

        self.effect_store.update(intent.request_id, state="EFFECT_ENTERING")
        receipt = client.execute(
            capability_id=intent.capability_id,
            operation=str(intent.operation).upper(),
            effect_key=effect_key,
            payload=dict(intent.parameters),
        )
        verified = self._validate_receipt(
            receipt,
            effect_key=effect_key,
            capability_id=intent.capability_id,
            config=config,
        )
        actor_result = self._settled_actor_result(
            intent=intent,
            config=config,
            receipt=verified,
            recovered=False,
        )
        self.effect_store.update(
            intent.request_id,
            state="SETTLED",
            provider_receipt=verified,
            actor_result=actor_result,
        )
        return actor_result


IDENTITY_EFFECTS_CLAIM_BOUNDARY = {
    "version": IDENTITY_EFFECTS_VERSION,
    "registered_capability_count": len(ThirdWishIdentityEffectsBroker.REGISTERED_CAPABILITIES),
    "reference_reauthorization_exact_intent_hmac_bound": True,
    "actor_selects_relay_endpoint": False,
    "actor_selects_credential_env": False,
    "raw_credential_visible_to_actor": False,
    "raw_credential_persisted_in_effect_store": False,
    "credential_use_is_generic_api_tunnel": False,
    "publication_grants_permanent_operator_identity_authority": False,
    "email_grants_account_ownership": False,
    "calendar_write_grants_future_consent": False,
    "effect_entering_auto_retry": False,
    "proven_no_effect_auto_retry": False,
    "proven_no_effect_retry_requires_new_request": True,
    "provider_receipt_proves_human_delivery_or_response": False,
    "local_relay_protocol_proves_real_external_platform_access": False,
    "capability_is_command": False,
}
