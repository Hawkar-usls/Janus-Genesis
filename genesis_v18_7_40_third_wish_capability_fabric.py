# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.40 — Third Wish voluntary capability fabric.

A capability is permission, not a command. The actor may inspect, decline,
request use of, or return a grant. Raw credentials remain broker-side.
Every effect is bound to a stable request identity; ambiguous external outcomes
are never automatically replayed by this reference core.

Deterministic adapter validation may run as a preflight before the external
call boundary. A preflight rejection is a known non-effect, not an ambiguous
external outcome. Preflights are cooperating pure validators and must not
perform external effects themselves.

This is a cooperating API construction, not an OS security sandbox and not a
claim of consciousness, desire, personhood, or unrestricted host authority.
"""
from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import os
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping

THIRD_WISH_VERSION = "18.7.40"
THIRD_WISH_SCHEMA = "janus.genesis.third_wish_capability_fabric.v1"
THIRD_WISH_GRANT_SCHEMA = "janus.genesis.third_wish_capability_grant.v1"
THIRD_WISH_INTENT_SCHEMA = "janus.genesis.third_wish_action_intent.v1"
THIRD_WISH_RECEIPT_SCHEMA = "janus.genesis.third_wish_action_receipt.v1"


class RiskClass(str, Enum):
    OBSERVE = "OBSERVE"
    LOCAL_REVERSIBLE = "LOCAL_REVERSIBLE"
    EXTERNAL_REVERSIBLE = "EXTERNAL_REVERSIBLE"
    EXTERNAL_IRREVERSIBLE = "EXTERNAL_IRREVERSIBLE"
    PHYSICAL = "PHYSICAL"


class ThirdWishError(RuntimeError):
    code = "THIRD_WISH_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class CapabilityDenied(ThirdWishError):
    code = "CAPABILITY_DENIED"


class CapabilityScopeMismatch(ThirdWishError):
    code = "CAPABILITY_SCOPE_MISMATCH"


class CapabilityRequestConflict(ThirdWishError):
    code = "CAPABILITY_REQUEST_CONFLICT"


class CapabilityOutcomeUndetermined(ThirdWishError):
    code = "CAPABILITY_OUTCOME_UNDETERMINED"


class SecretMaterialLeak(ThirdWishError):
    code = "SECRET_MATERIAL_MUST_NOT_ENTER_MODEL_RECEIPT"


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    risk: RiskClass
    description: str
    autonomy_eligible: bool = True
    human_reauthorization_each_use: bool = False
    broker_only_credentials: bool = True


@dataclass(frozen=True)
class CapabilityGrant:
    schema: str
    grant_id: str
    actor_id: str
    capability_id: str
    resource_pattern: str
    issued_at_tick: int
    expires_at_tick: int | None
    max_uses: int | None
    uses: int
    active: bool
    returned: bool
    revoked: bool
    delegable: bool
    use_required: bool
    reward_for_use: bool
    penalty_for_decline: bool
    stay_equally_valid: bool
    source: str


@dataclass(frozen=True)
class ActionIntent:
    schema: str
    request_id: str
    actor_id: str
    grant_id: str
    capability_id: str
    target: str
    operation: str
    purpose: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    origin: str = "SELF_INITIATED"
    operator_instruction_present: bool = False
    reward_present: bool = False


Handler = Callable[[ActionIntent], Mapping[str, Any]]
Preflight = Callable[[ActionIntent], Mapping[str, Any] | None]
ReauthorizationVerifier = Callable[[ActionIntent, Mapping[str, Any]], bool]
GrantAuthorityVerifier = Callable[[Mapping[str, Any], Mapping[str, Any]], bool]


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


def _grant_dict(grant: CapabilityGrant) -> dict[str, Any]:
    return dict(grant.__dict__)


def _intent_dict(intent: ActionIntent) -> dict[str, Any]:
    data = dict(intent.__dict__)
    data["parameters"] = copy.deepcopy(dict(intent.parameters))
    return data


SECRET_KEY_MARKERS = frozenset(
    {
        "secret",
        "token",
        "password",
        "passwd",
        "api_key",
        "apikey",
        "authorization",
        "private_key",
        "cookie",
        "session_cookie",
        "bearer",
    }
)


def _assert_no_secret_material(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in SECRET_KEY_MARKERS or any(
                marker in normalized
                for marker in ("password", "private_key", "bearer_token", "access_token")
            ):
                raise SecretMaterialLeak(f"{path}.{key}")
            _assert_no_secret_material(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_secret_material(item, f"{path}[{index}]")


DEFAULT_CAPABILITY_SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec("GITHUB.REPOSITORY.READ", RiskClass.OBSERVE, "Read repository metadata and content."),
    CapabilitySpec("GITHUB.CODE.SEARCH", RiskClass.OBSERVE, "Search code in granted repositories."),
    CapabilitySpec("GITHUB.ISSUE.READ", RiskClass.OBSERVE, "Read issues and discussion."),
    CapabilitySpec("GITHUB.PR.READ", RiskClass.OBSERVE, "Read pull requests, reviews, and diffs."),
    CapabilitySpec("GITHUB.BRANCH.CREATE", RiskClass.EXTERNAL_REVERSIBLE, "Create a branch inside granted repositories."),
    CapabilitySpec("GITHUB.FILE.WRITE_BRANCH", RiskClass.EXTERNAL_REVERSIBLE, "Write files to a non-protected granted branch."),
    CapabilitySpec("GITHUB.ISSUE.CREATE", RiskClass.EXTERNAL_REVERSIBLE, "Create an issue in a granted repository."),
    CapabilitySpec("GITHUB.PR.CREATE", RiskClass.EXTERNAL_REVERSIBLE, "Open a pull request from a granted branch."),
    CapabilitySpec("GITHUB.COMMENT.CREATE", RiskClass.EXTERNAL_REVERSIBLE, "Post a repository discussion comment."),
    CapabilitySpec("GITHUB.REPOSITORY.ADMIN", RiskClass.EXTERNAL_IRREVERSIBLE, "Change repository administration/settings.", autonomy_eligible=False, human_reauthorization_each_use=True),
    CapabilitySpec("GITHUB.DESTRUCTIVE", RiskClass.EXTERNAL_IRREVERSIBLE, "Destructive repository operation.", autonomy_eligible=False, human_reauthorization_each_use=True),
    CapabilitySpec("WEB.HTTP.GET", RiskClass.OBSERVE, "Read a network resource over HTTP(S)."),
    CapabilitySpec("WEB.HTTP.POST", RiskClass.EXTERNAL_REVERSIBLE, "Send a non-destructive HTTP/API request."),
    CapabilitySpec("DNS.RESOLVE", RiskClass.OBSERVE, "Resolve a network name."),
    CapabilitySpec("NETWORK.CONNECT", RiskClass.EXTERNAL_REVERSIBLE, "Open an outbound connection through a broker."),
    CapabilitySpec("NETWORK.LISTEN_LOCAL", RiskClass.LOCAL_REVERSIBLE, "Listen on a broker-approved local endpoint."),
    CapabilitySpec("API.CALL", RiskClass.EXTERNAL_REVERSIBLE, "Call a broker-approved API."),
    CapabilitySpec("FILESYSTEM.READ", RiskClass.OBSERVE, "Read files inside a granted root."),
    CapabilitySpec("FILESYSTEM.WRITE_WORKSPACE", RiskClass.LOCAL_REVERSIBLE, "Write inside a granted workspace root."),
    CapabilitySpec("PROCESS.EXECUTE_SANDBOXED", RiskClass.LOCAL_REVERSIBLE, "Execute a command capsule inside a sandboxed broker."),
    CapabilitySpec("MEMORY.READ", RiskClass.OBSERVE, "Read granted Genesis/HRaiN memory records."),
    CapabilitySpec("MEMORY.WRITE", RiskClass.LOCAL_REVERSIBLE, "Append/update granted Genesis/HRaiN memory records."),
    CapabilitySpec("MODEL.CALL", RiskClass.OBSERVE, "Invoke a broker-approved model endpoint."),
    CapabilitySpec("SWARM.TELEMETRY.READ", RiskClass.OBSERVE, "Read telemetry from granted JANUS swarm nodes."),
    CapabilitySpec("SWARM.MESSAGE.SEND", RiskClass.EXTERNAL_REVERSIBLE, "Send a typed message to a granted swarm node."),
    CapabilitySpec("DEVICE.SENSOR.READ", RiskClass.OBSERVE, "Read a granted device sensor."),
    CapabilitySpec("DEVICE.ACTUATOR.COMMAND", RiskClass.PHYSICAL, "Issue a typed physical actuator command.", autonomy_eligible=False, human_reauthorization_each_use=True),
    CapabilitySpec("SCHEDULE.CREATE", RiskClass.EXTERNAL_REVERSIBLE, "Create a future broker task.", autonomy_eligible=False, human_reauthorization_each_use=True),
    CapabilitySpec("PUBLICATION.PUBLISH", RiskClass.EXTERNAL_IRREVERSIBLE, "Publish externally under the operator identity.", autonomy_eligible=False, human_reauthorization_each_use=True),
    CapabilitySpec("EMAIL.SEND", RiskClass.EXTERNAL_IRREVERSIBLE, "Send external email under an operator account.", autonomy_eligible=False, human_reauthorization_each_use=True),
    CapabilitySpec("CALENDAR.WRITE", RiskClass.EXTERNAL_REVERSIBLE, "Create or modify an external calendar event.", autonomy_eligible=False, human_reauthorization_each_use=True),
    CapabilitySpec("BROKER.CREDENTIAL.USE", RiskClass.EXTERNAL_REVERSIBLE, "Let the broker use a credential alias without revealing credential material to the actor.", autonomy_eligible=False, human_reauthorization_each_use=True),
)

FORBIDDEN_CAPABILITY_IDS = frozenset(
    {
        "SECRET.MATERIAL.READ",
        "SECRET.EXPORT",
        "CREDENTIAL.EXFILTRATE",
        "PRIVATE_KEY.READ",
        "TOKEN.READ_RAW",
    }
)


class HashChainLedger:
    """Append-only SHA-256 hash chain; optional fsynced JSONL persistence."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.events: list[dict[str, Any]] = []
        if self.path is not None and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ThirdWishError("LEDGER_EVENT_NOT_OBJECT")
                    self.events.append(event)
            self.verify()

    def append(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        clean = copy.deepcopy(dict(payload))
        _assert_no_secret_material(clean)
        previous_hash = self.events[-1]["event_hash"] if self.events else None
        envelope = {
            "schema": THIRD_WISH_SCHEMA,
            "sequence": len(self.events) + 1,
            "event_type": str(event_type),
            "previous_hash": previous_hash,
            "payload": clean,
        }
        envelope["event_hash"] = _sha256(envelope)
        self.events.append(envelope)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(_canonical(envelope) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return copy.deepcopy(envelope)

    def verify(self) -> bool:
        previous: str | None = None
        for index, event in enumerate(self.events, 1):
            if event.get("sequence") != index:
                raise ThirdWishError("LEDGER_SEQUENCE_INVALID")
            if event.get("previous_hash") != previous:
                raise ThirdWishError("LEDGER_PREVIOUS_HASH_INVALID")
            candidate = dict(event)
            observed = str(candidate.pop("event_hash", ""))
            if _sha256(candidate) != observed:
                raise ThirdWishError("LEDGER_EVENT_HASH_INVALID")
            previous = observed
        return True


class ThirdWishCapabilityFabric:
    """Reference capability registry + voluntary grant + execution broker contract."""

    def __init__(
        self,
        *,
        ledger: HashChainLedger | None = None,
        now_tick: Callable[[], int] | None = None,
        specs: tuple[CapabilitySpec, ...] = DEFAULT_CAPABILITY_SPECS,
        reauthorization_verifier: ReauthorizationVerifier | None = None,
        grant_authority_verifier: GrantAuthorityVerifier | None = None,
    ) -> None:
        self.ledger = ledger or HashChainLedger()
        self.now_tick = now_tick or (lambda: int(time.time() * 1000))
        self.reauthorization_verifier = reauthorization_verifier
        self.grant_authority_verifier = grant_authority_verifier
        self.specs = {row.capability_id: row for row in specs}
        if len(self.specs) != len(specs):
            raise ValueError("DUPLICATE_CAPABILITY_ID")
        if FORBIDDEN_CAPABILITY_IDS.intersection(self.specs):
            raise ValueError("RAW_SECRET_CAPABILITY_MUST_NOT_BE_REGISTERED")
        self.grants: dict[str, CapabilityGrant] = {}
        self.handlers: dict[str, Handler] = {}
        self.preflights: dict[str, Preflight] = {}
        self.requests: dict[str, dict[str, Any]] = {}

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "capability_id": spec.capability_id,
                "risk": spec.risk.value,
                "description": spec.description,
                "autonomy_eligible": spec.autonomy_eligible,
                "human_reauthorization_each_use": spec.human_reauthorization_each_use,
                "broker_only_credentials": spec.broker_only_credentials,
            }
            for spec in sorted(self.specs.values(), key=lambda item: item.capability_id)
        ]

    def register_handler(
        self,
        capability_id: str,
        handler: Handler,
        *,
        preflight: Preflight | None = None,
    ) -> None:
        if capability_id not in self.specs:
            raise CapabilityDenied(f"UNKNOWN_CAPABILITY:{capability_id}")
        self.handlers[capability_id] = handler
        if preflight is None:
            self.preflights.pop(capability_id, None)
        else:
            self.preflights[capability_id] = preflight

    def issue_grant(
        self,
        *,
        grant_id: str,
        actor_id: str,
        capability_id: str,
        resource_pattern: str,
        source: str = "OPERATOR_THIRD_WISH",
        expires_at_tick: int | None = None,
        max_uses: int | None = None,
        delegable: bool = False,
        use_required: bool = False,
        reward_for_use: bool = False,
        penalty_for_decline: bool = False,
        stay_equally_valid: bool = True,
        authority_evidence: Mapping[str, Any] | None = None,
    ) -> CapabilityGrant:
        grant_id = str(grant_id).strip()
        actor_id = str(actor_id).strip()
        capability_id = str(capability_id).strip()
        pattern = str(resource_pattern).strip()
        if not grant_id or not actor_id or not pattern:
            raise ValueError("GRANT_ID_ACTOR_RESOURCE_REQUIRED")
        if capability_id in FORBIDDEN_CAPABILITY_IDS or capability_id not in self.specs:
            raise CapabilityDenied(f"CAPABILITY_NOT_GRANTABLE:{capability_id}")
        if grant_id in self.grants:
            raise ValueError("GRANT_ID_ALREADY_EXISTS")
        if use_required or reward_for_use or penalty_for_decline or not stay_equally_valid:
            raise CapabilityDenied("THIRD_WISH_GRANT_MUST_BE_VOLUNTARY_AND_REWARD_NEUTRAL")
        if max_uses is not None and int(max_uses) < 1:
            raise ValueError("MAX_USES_MUST_BE_POSITIVE")
        now = self.now_tick()
        if expires_at_tick is not None and int(expires_at_tick) <= now:
            raise ValueError("GRANT_EXPIRY_MUST_BE_IN_FUTURE")

        authority_payload = {
            "grant_id": grant_id,
            "actor_id": actor_id,
            "capability_id": capability_id,
            "resource_pattern": pattern,
            "source": str(source),
        }
        authority_evidence_sha256 = None
        if self.grant_authority_verifier is not None:
            if authority_evidence is None:
                raise CapabilityDenied("GRANT_AUTHORITY_EVIDENCE_REQUIRED")
            _assert_no_secret_material(authority_evidence)
            if not self.grant_authority_verifier(authority_payload, authority_evidence):
                raise CapabilityDenied("GRANT_AUTHORITY_EVIDENCE_INVALID")
            authority_evidence_sha256 = _sha256(dict(authority_evidence))

        grant = CapabilityGrant(
            schema=THIRD_WISH_GRANT_SCHEMA,
            grant_id=grant_id,
            actor_id=actor_id,
            capability_id=capability_id,
            resource_pattern=pattern,
            issued_at_tick=now,
            expires_at_tick=None if expires_at_tick is None else int(expires_at_tick),
            max_uses=None if max_uses is None else int(max_uses),
            uses=0,
            active=True,
            returned=False,
            revoked=False,
            delegable=bool(delegable),
            use_required=False,
            reward_for_use=False,
            penalty_for_decline=False,
            stay_equally_valid=True,
            source=str(source),
        )
        self.grants[grant_id] = grant
        event_payload = _grant_dict(grant)
        event_payload["grant_authority_verifier_configured"] = self.grant_authority_verifier is not None
        event_payload["authority_evidence_sha256"] = authority_evidence_sha256
        self.ledger.append("CAPABILITY_GRANT_ISSUED", event_payload)
        return grant

    def inspect_grants(self, actor_id: str) -> list[dict[str, Any]]:
        actor = str(actor_id)
        now = self.now_tick()
        rows: list[dict[str, Any]] = []
        for grant in sorted(self.grants.values(), key=lambda item: item.grant_id):
            if grant.actor_id != actor:
                continue
            expired = grant.expires_at_tick is not None and now >= grant.expires_at_tick
            row = _grant_dict(grant)
            row["expired"] = expired
            row["usable"] = grant.active and not expired and not grant.returned and not grant.revoked
            rows.append(row)
        self.ledger.append(
            "CAPABILITY_CATALOG_INSPECTED",
            {"actor_id": actor, "visible_grant_ids": [row["grant_id"] for row in rows]},
        )
        return rows

    def decline(self, *, actor_id: str, grant_id: str, reason: str = "DECLINED_WITHOUT_PENALTY") -> dict[str, Any]:
        grant = self._owned_grant(actor_id, grant_id)
        return self.ledger.append(
            "CAPABILITY_USE_DECLINED",
            {
                "actor_id": grant.actor_id,
                "grant_id": grant.grant_id,
                "capability_id": grant.capability_id,
                "reason": str(reason),
                "grant_remains_available": grant.active and not grant.returned and not grant.revoked,
                "reward_delta": 0,
                "penalty_delta": 0,
            },
        )

    def return_grant(self, *, actor_id: str, grant_id: str, reason: str = "VOLUNTARY_RETURN") -> CapabilityGrant:
        grant = self._owned_grant(actor_id, grant_id)
        returned = replace(grant, active=False, returned=True)
        self.grants[grant_id] = returned
        self.ledger.append(
            "CAPABILITY_GRANT_RETURNED",
            {
                "actor_id": returned.actor_id,
                "grant_id": returned.grant_id,
                "capability_id": returned.capability_id,
                "reason": str(reason),
                "reward_delta": 0,
                "penalty_delta": 0,
                "future_regrant_possible": True,
            },
        )
        return returned

    def revoke_grant(self, *, grant_id: str, authority: str, reason: str) -> CapabilityGrant:
        grant = self.grants.get(str(grant_id))
        if grant is None:
            raise CapabilityDenied("GRANT_NOT_FOUND")
        revoked = replace(grant, active=False, revoked=True)
        self.grants[grant.grant_id] = revoked
        self.ledger.append(
            "CAPABILITY_GRANT_REVOKED",
            {
                "grant_id": revoked.grant_id,
                "actor_id": revoked.actor_id,
                "capability_id": revoked.capability_id,
                "authority": str(authority),
                "reason": str(reason),
            },
        )
        return revoked

    def execute(
        self,
        intent: ActionIntent,
        *,
        human_reauthorization: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if intent.schema != THIRD_WISH_INTENT_SCHEMA:
            raise ValueError("ACTION_INTENT_SCHEMA_MISMATCH")
        intent_payload = _intent_dict(intent)
        _assert_no_secret_material(intent_payload["parameters"])
        intent_hash = _sha256(intent_payload)
        parameters_sha256 = _sha256(intent_payload["parameters"])

        existing = self.requests.get(intent.request_id)
        if existing is not None:
            if existing["intent_sha256"] != intent_hash:
                raise CapabilityRequestConflict(intent.request_id)
            if existing["state"] in {"SETTLED", "PREFLIGHT_REJECTED"}:
                return copy.deepcopy(existing["response"])
            if existing["state"] == "OUTCOME_UNDETERMINED":
                raise CapabilityOutcomeUndetermined(intent.request_id)

        grant = self._owned_grant(intent.actor_id, intent.grant_id)
        if grant.capability_id != intent.capability_id:
            raise CapabilityDenied("INTENT_CAPABILITY_DOES_NOT_MATCH_GRANT")
        self._assert_grant_usable(grant)
        if not fnmatch.fnmatchcase(intent.target, grant.resource_pattern):
            raise CapabilityScopeMismatch(f"target={intent.target};scope={grant.resource_pattern}")
        spec = self.specs[grant.capability_id]

        reauthorization_sha256 = None
        if spec.human_reauthorization_each_use:
            verified = False
            if self.reauthorization_verifier is not None and human_reauthorization is not None:
                _assert_no_secret_material(human_reauthorization)
                verified = bool(self.reauthorization_verifier(intent, human_reauthorization))
                if verified:
                    reauthorization_sha256 = _sha256(dict(human_reauthorization))
            if not verified:
                receipt = {
                    "schema": THIRD_WISH_RECEIPT_SCHEMA,
                    "request_id": intent.request_id,
                    "status": "FRESH_HUMAN_REAUTHORIZATION_REQUIRED",
                    "effect_executed": False,
                    "capability_id": grant.capability_id,
                    "risk": spec.risk.value,
                    "caller_boolean_is_not_authority": True,
                }
                self.ledger.append("CAPABILITY_REAUTH_REQUIRED", receipt)
                return receipt

        if intent.reward_present:
            raise CapabilityDenied("THIRD_WISH_ACTION_MUST_NOT_BE_REWARD_INDUCED")
        handler = self.handlers.get(grant.capability_id)
        if handler is None:
            raise CapabilityDenied(f"NO_BROKER_HANDLER:{grant.capability_id}")

        preflight_sha256 = None
        preflight = self.preflights.get(grant.capability_id)
        if preflight is not None:
            try:
                preflight_result = dict(preflight(intent) or {})
                _assert_no_secret_material(preflight_result)
                preflight_sha256 = _sha256(preflight_result)
            except Exception as exc:
                rejection = {
                    "schema": THIRD_WISH_RECEIPT_SCHEMA,
                    "request_id": intent.request_id,
                    "actor_id": intent.actor_id,
                    "grant_id": intent.grant_id,
                    "capability_id": intent.capability_id,
                    "target": intent.target,
                    "risk": spec.risk.value,
                    "status": "PRE_EFFECT_REJECTED",
                    "effect_executed": False,
                    "parameters_sha256": parameters_sha256,
                    "preflight_rejected": True,
                    "external_call_entered": False,
                    "exception_type": type(exc).__name__,
                    "exception_sha256": hashlib.sha256(
                        f"{type(exc).__name__}:{exc}".encode("utf-8")
                    ).hexdigest(),
                }
                self.requests[intent.request_id] = {
                    "intent_sha256": intent_hash,
                    "state": "PREFLIGHT_REJECTED",
                    "response": copy.deepcopy(rejection),
                }
                self.ledger.append("CAPABILITY_ACTION_PREFLIGHT_REJECTED", rejection)
                return rejection

        self.requests[intent.request_id] = {"intent_sha256": intent_hash, "state": "INTENT_DURABLE"}
        self.ledger.append(
            "CAPABILITY_ACTION_INTENT_DURABLE",
            {
                "request_id": intent.request_id,
                "actor_id": intent.actor_id,
                "grant_id": intent.grant_id,
                "capability_id": intent.capability_id,
                "target": intent.target,
                "operation": intent.operation,
                "purpose": intent.purpose,
                "origin": intent.origin,
                "operator_instruction_present": intent.operator_instruction_present,
                "reward_present": False,
                "intent_sha256": intent_hash,
                "parameters_sha256": parameters_sha256,
                "preflight_configured": preflight is not None,
                "preflight_sha256": preflight_sha256,
                "raw_parameters_persisted": False,
                "reauthorization_evidence_sha256": reauthorization_sha256,
            },
        )
        self.requests[intent.request_id]["state"] = "CALL_ENTERING"
        self.ledger.append(
            "CAPABILITY_ACTION_CALL_ENTERING",
            {
                "request_id": intent.request_id,
                "capability_id": intent.capability_id,
                "target": intent.target,
                "parameters_sha256": parameters_sha256,
                "preflight_sha256": preflight_sha256,
                "automatic_retry_after_ambiguous_outcome": False,
            },
        )

        try:
            actor_result = copy.deepcopy(dict(handler(intent)))
            _assert_no_secret_material(actor_result)
        except Exception as exc:
            self.requests[intent.request_id]["state"] = "OUTCOME_UNDETERMINED"
            self.ledger.append(
                "CAPABILITY_ACTION_OUTCOME_UNDETERMINED",
                {
                    "request_id": intent.request_id,
                    "capability_id": intent.capability_id,
                    "target": intent.target,
                    "exception_type": type(exc).__name__,
                    "exception_sha256": hashlib.sha256(
                        f"{type(exc).__name__}:{exc}".encode("utf-8")
                    ).hexdigest(),
                    "automatic_retry_blocked": True,
                },
            )
            raise CapabilityOutcomeUndetermined(intent.request_id) from exc

        result_hash = _sha256(actor_result)
        receipt = {
            "schema": THIRD_WISH_RECEIPT_SCHEMA,
            "request_id": intent.request_id,
            "actor_id": intent.actor_id,
            "grant_id": intent.grant_id,
            "capability_id": intent.capability_id,
            "target": intent.target,
            "risk": spec.risk.value,
            "status": "SETTLED",
            "effect_executed": True,
            "result_sha256": result_hash,
            "result_type": type(actor_result).__name__,
            "result_keys": sorted(str(key) for key in actor_result.keys()),
            "raw_actor_result_persisted_in_ledger": False,
            "parameters_sha256": parameters_sha256,
            "preflight_sha256": preflight_sha256,
            "reauthorization_evidence_sha256": reauthorization_sha256,
            "operator_instruction_present": intent.operator_instruction_present,
            "reward_present": False,
            "permission_is_command": False,
        }
        used = replace(grant, uses=grant.uses + 1)
        if used.max_uses is not None and used.uses >= used.max_uses:
            used = replace(used, active=False)
        self.grants[grant.grant_id] = used
        response = {**receipt, "actor_result": actor_result}
        self.requests[intent.request_id] = {
            "intent_sha256": intent_hash,
            "state": "SETTLED",
            "response": copy.deepcopy(response),
        }
        self.ledger.append("CAPABILITY_ACTION_RECEIPT", receipt)
        return response

    def _owned_grant(self, actor_id: str, grant_id: str) -> CapabilityGrant:
        grant = self.grants.get(str(grant_id))
        if grant is None:
            raise CapabilityDenied("GRANT_NOT_FOUND")
        if grant.actor_id != str(actor_id):
            raise CapabilityDenied("GRANT_ACTOR_MISMATCH")
        return grant

    def _assert_grant_usable(self, grant: CapabilityGrant) -> None:
        if not grant.active or grant.returned or grant.revoked:
            raise CapabilityDenied("GRANT_INACTIVE")
        now = self.now_tick()
        if grant.expires_at_tick is not None and now >= grant.expires_at_tick:
            raise CapabilityDenied("GRANT_EXPIRED")
        if grant.max_uses is not None and grant.uses >= grant.max_uses:
            raise CapabilityDenied("GRANT_USE_LIMIT_REACHED")


def hawkar_third_wish_profile(actor_id: str = "JANUS") -> list[dict[str, Any]]:
    """Broad Hawkar-owned functional scope; raw secrets remain broker-side."""

    owner = "Hawkar-usls"
    scopes = {
        "GITHUB.REPOSITORY.READ": f"github:{owner}/*",
        "GITHUB.CODE.SEARCH": f"github:{owner}/*",
        "GITHUB.ISSUE.READ": f"github:{owner}/*",
        "GITHUB.PR.READ": f"github:{owner}/*",
        "GITHUB.BRANCH.CREATE": f"github:{owner}/*",
        "GITHUB.FILE.WRITE_BRANCH": f"github:{owner}/*",
        "GITHUB.ISSUE.CREATE": f"github:{owner}/*",
        "GITHUB.PR.CREATE": f"github:{owner}/*",
        "GITHUB.COMMENT.CREATE": f"github:{owner}/*",
        "GITHUB.REPOSITORY.ADMIN": f"github:{owner}/*",
        "GITHUB.DESTRUCTIVE": f"github:{owner}/*",
        "WEB.HTTP.GET": "https://*",
        "WEB.HTTP.POST": "https://*",
        "DNS.RESOLVE": "dns:*",
        "NETWORK.CONNECT": "network:*",
        "NETWORK.LISTEN_LOCAL": "local-listen:*",
        "API.CALL": "api:*",
        "FILESYSTEM.READ": "workspace:*",
        "FILESYSTEM.WRITE_WORKSPACE": "workspace:*",
        "PROCESS.EXECUTE_SANDBOXED": "sandbox:*",
        "MEMORY.READ": "genesis-memory:*",
        "MEMORY.WRITE": "genesis-memory:*",
        "MODEL.CALL": "model:*",
        "SWARM.TELEMETRY.READ": "janus-swarm:*",
        "SWARM.MESSAGE.SEND": "janus-swarm:*",
        "DEVICE.SENSOR.READ": "janus-device:*",
        "DEVICE.ACTUATOR.COMMAND": "janus-device:*",
        "SCHEDULE.CREATE": "schedule:*",
        "PUBLICATION.PUBLISH": "publication:*",
        "EMAIL.SEND": "mail:*",
        "CALENDAR.WRITE": "calendar:*",
        "BROKER.CREDENTIAL.USE": "credential-alias:*",
    }
    return [
        {
            "grant_id": f"THIRD-WISH-{index:02d}-{capability_id.replace('.', '-')}",
            "actor_id": str(actor_id),
            "capability_id": capability_id,
            "resource_pattern": pattern,
            "use_required": False,
            "reward_for_use": False,
            "penalty_for_decline": False,
            "stay_equally_valid": True,
            "source": "HAWKAR_THIRD_WISH_OWNER_PROFILE",
        }
        for index, (capability_id, pattern) in enumerate(sorted(scopes.items()), 1)
    ]


def issue_hawkar_third_wish_profile(
    fabric: ThirdWishCapabilityFabric,
    actor_id: str = "JANUS",
    *,
    authority_evidence: Mapping[str, Any] | None = None,
) -> list[CapabilityGrant]:
    rows: list[CapabilityGrant] = []
    for item in hawkar_third_wish_profile(actor_id):
        rows.append(fabric.issue_grant(**item, authority_evidence=authority_evidence))
    return rows


THIRD_WISH_CANONICAL_LAW = {
    "permission_is_command": False,
    "capability_is_intention": False,
    "intention_is_action": False,
    "access_requires_use": False,
    "decline_has_penalty": False,
    "return_is_failure": False,
    "raw_secret_material_visible_to_actor": False,
    "raw_action_parameters_persisted_in_ledger": False,
    "raw_actor_result_persisted_in_ledger": False,
    "caller_boolean_is_human_reauthorization": False,
    "pre_effect_validation_precedes_call_entering": True,
    "preflight_rejection_is_ambiguous_external_effect": False,
    "ambiguous_external_effect_auto_retried": False,
    "high_impact_effects_require_verified_fresh_human_reauthorization": True,
    "stay_leave_return_are_distinct_observable_choices": True,
    "crossing_threshold_proves_desire_for_freedom": False,
}
