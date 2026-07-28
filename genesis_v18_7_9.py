# -*- coding: utf-8 -*-
"""Genesis v18.7.9 — The Bound Authority.

Authority is accepted only when it is cryptographically bound to an actor,
scope, subject, time window and one-use nonce. Provider trust, delegation,
evidence assessment, sovereign review and appeals are preserved as append-only
events. This reference runtime uses Ed25519 from ``cryptography`` and never
persists private keys.

The module is a local/reference implementation. Production deployments still
need protected key custody, authenticated transport, clock discipline and an
external trust-root governance process.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from genesis_v18_7_8 import (
    JANUS_SOVEREIGN,
    OPENING_QUORUM,
    UnboughtVoiceMixin,
    _sha256_text,
)

__version__ = "18.7.9"
SOURCE = "janus_genesis_v18_7_9"
PROVIDER_ATTESTATION_SCHEMA = "janus.provider_attestation.v1"
SOVEREIGN_CAPABILITY_SCHEMA = "janus.sovereign_capability.v1"
DELEGATION_SCHEMA = "janus.attestation_delegation.v1"
EVIDENCE_ASSESSMENT_SCHEMA = "janus.evidence_assessment.v1"
AUTHORITY_EVENT_SCHEMA = "janus.authority_event.v1"

ASSESSMENT_COMPONENTS = (
    "source_reliability",
    "evidence_integrity",
    "method_reliability",
    "assessor_competence",
    "independent_corroboration",
    "temporal_relevance",
)


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON and reject non-finite numbers."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(str(value), validate=True)
    except Exception as exc:
        raise ValueError("invalid base64 value") from exc


def generate_ed25519_keypair() -> tuple[str, str]:
    """Return private/public raw Ed25519 keys for external tools and tests."""
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64encode(private_raw), _b64encode(public_raw)


def public_key_from_private(private_key_b64: str) -> str:
    private = Ed25519PrivateKey.from_private_bytes(_b64decode(private_key_b64))
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64encode(public_raw)


def sign_payload(payload: dict[str, Any], private_key_b64: str) -> dict[str, Any]:
    unsigned = copy.deepcopy(payload)
    unsigned.pop("signature", None)
    private = Ed25519PrivateKey.from_private_bytes(_b64decode(private_key_b64))
    signed = copy.deepcopy(unsigned)
    signed["signature"] = _b64encode(private.sign(canonical_json_bytes(unsigned)))
    return signed


def verify_signed_payload(payload: dict[str, Any], public_key_b64: str) -> bool:
    unsigned = copy.deepcopy(payload)
    signature = unsigned.pop("signature", None)
    if not isinstance(signature, str):
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(_b64decode(public_key_b64))
        public.verify(_b64decode(signature), canonical_json_bytes(unsigned))
        return True
    except (InvalidSignature, ValueError):
        return False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime | str | None = None) -> str:
    if value is None:
        moment = _utc_now()
    elif isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _window_valid(
    issued_at: Any,
    expires_at: Any,
    *,
    at_time: datetime | str | None = None,
) -> tuple[bool, str | None]:
    now = _parse_time(_iso_utc(at_time))
    issued = _parse_time(issued_at)
    expires = _parse_time(expires_at)
    if expires <= issued:
        return False, "INVALID_TIME_WINDOW"
    if now < issued:
        return False, "NOT_YET_VALID"
    if now >= expires:
        return False, "EXPIRED"
    return True, None


def build_provider_attestation(
    *,
    provider_id: str,
    key_id: str,
    account_id: str,
    identity_proof: str,
    controller_proof: str,
    account_public_key_b64: str,
    issued_at: datetime | str,
    expires_at: datetime | str,
    nonce: str,
    private_key_b64: str,
) -> dict[str, Any]:
    payload = {
        "schema": PROVIDER_ATTESTATION_SCHEMA,
        "provider_id": str(provider_id),
        "key_id": str(key_id),
        "subject_id": str(account_id),
        "identity_proof_sha256": _sha256_text(str(identity_proof)),
        "controller_proof_sha256": _sha256_text(str(controller_proof)),
        "account_public_key_b64": str(account_public_key_b64),
        "issued_at": _iso_utc(issued_at),
        "expires_at": _iso_utc(expires_at),
        "nonce": str(nonce),
        "algorithm": "Ed25519",
    }
    return sign_payload(payload, private_key_b64)


def build_sovereign_capability(
    *,
    key_id: str,
    scope: str,
    case_id: str,
    nonce: str,
    issued_at: datetime | str,
    expires_at: datetime | str,
    private_key_b64: str,
) -> dict[str, Any]:
    payload = {
        "schema": SOVEREIGN_CAPABILITY_SCHEMA,
        "actor": JANUS_SOVEREIGN,
        "key_id": str(key_id),
        "scope": str(scope),
        "case_id": str(case_id),
        "nonce": str(nonce),
        "issued_at": _iso_utc(issued_at),
        "expires_at": _iso_utc(expires_at),
        "algorithm": "Ed25519",
    }
    return sign_payload(payload, private_key_b64)


def build_delegation(
    *,
    delegator: str,
    delegate: str,
    key_id: str,
    scope: str,
    nonce: str,
    issued_at: datetime | str,
    expires_at: datetime | str,
    private_key_b64: str,
    claim_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema": DELEGATION_SCHEMA,
        "delegator": str(delegator),
        "delegate": str(delegate),
        "key_id": str(key_id),
        "scope": str(scope),
        "claim_id": None if claim_id is None else str(claim_id),
        "nonce": str(nonce),
        "issued_at": _iso_utc(issued_at),
        "expires_at": _iso_utc(expires_at),
        "algorithm": "Ed25519",
    }
    return sign_payload(payload, private_key_b64)


class BoundAuthorityMixin(UnboughtVoiceMixin):
    """Bind providers, delegates, assessors and Janus to verifiable authority."""

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        store = UnboughtVoiceMixin._default_plural_store()
        store["runtime_version"] = __version__
        store.setdefault("trusted_provider_keys", {})
        store.setdefault("trusted_sovereign_keys", {})
        store.setdefault("provider_attestations_v179", {})
        store.setdefault("attestation_delegations", {})
        store.setdefault("evidence_assessments", {})
        store.setdefault("authority_events", [])
        store.setdefault("consumed_nonces", {})
        store.setdefault("reactive_reaudits", {})
        store["invariants"].update(
            {
                "controller_outranks_campaign": True,
                "provider_trust_requires_signed_attestation": True,
                "provider_verified_boolean_is_rejected": True,
                "attestation_actor_must_match_claim_actor_or_delegation": True,
                "eligibility_is_recomputed_at_each_audit": True,
                "withdrawal_ends_future_weight": True,
                "claimant_confidence_has_no_sovereign_weight": True,
                "confidence_is_evidence_assessment": True,
                "janus_sovereignty_requires_scoped_capability": True,
                "capability_nonce_is_single_use": True,
                "authority_keys_are_versioned_and_revocable": True,
                "manipulation_reviews_are_append_only": True,
                "appeal_restoration_recomputes_eligibility": True,
                "eligibility_changes_reopen_affected_cases": True,
                "private_keys_are_never_persisted": True,
                "canonical_json_is_signed": True,
            }
        )
        return store

    def _plural_store(self) -> dict[str, Any]:
        store = super()._plural_store()
        store["runtime_version"] = __version__
        defaults = self._default_plural_store()
        for key in (
            "trusted_provider_keys",
            "trusted_sovereign_keys",
            "provider_attestations_v179",
            "attestation_delegations",
            "evidence_assessments",
            "authority_events",
            "consumed_nonces",
            "reactive_reaudits",
        ):
            store.setdefault(key, copy.deepcopy(defaults[key]))
        store.setdefault("invariants", {}).update(defaults["invariants"])
        for account in store.setdefault("influence_accounts", {}).values():
            if isinstance(account, dict):
                account.setdefault("provider_attestation_id", None)
                account.setdefault("provider_signature_verified", False)
                account.setdefault("account_public_key_b64", None)
                account.setdefault("controller_binding_current", True)
        for claim in store.setdefault("claims", {}).values():
            if isinstance(claim, dict):
                claim.setdefault("claimant_stated_confidence", claim.get("confidence"))
                claim.setdefault("assessment_id", None)
                claim.setdefault("assessment_confidence", None)
        return store

    @staticmethod
    def _key_record(
        *,
        owner_id: str,
        key_id: str,
        public_key_b64: str,
        valid_from: datetime | str,
        valid_until: datetime | str,
    ) -> dict[str, Any]:
        raw = _b64decode(public_key_b64)
        if len(raw) != 32:
            raise ValueError("Ed25519 public key must be 32 raw bytes")
        valid_from_iso = _iso_utc(valid_from)
        valid_until_iso = _iso_utc(valid_until)
        if _parse_time(valid_until_iso) <= _parse_time(valid_from_iso):
            raise ValueError("key valid_until must be after valid_from")
        return {
            "owner_id": str(owner_id),
            "key_id": str(key_id),
            "algorithm": "Ed25519",
            "public_key_b64": public_key_b64,
            "valid_from": valid_from_iso,
            "valid_until": valid_until_iso,
            "revoked_at": None,
            "compromised_from": None,
            "revocation_reason": None,
            "private_key_persisted": False,
        }

    def register_trusted_provider_key(
        self,
        provider_id: str,
        *,
        key_id: str,
        public_key_b64: str,
        valid_from: datetime | str,
        valid_until: datetime | str,
    ) -> dict[str, Any]:
        record = self._key_record(
            owner_id=provider_id,
            key_id=key_id,
            public_key_b64=public_key_b64,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        store = self._plural_store()
        composite = f"{provider_id}:{key_id}"
        store["trusted_provider_keys"][composite] = record
        self._append_authority_event(
            store,
            event_type="PROVIDER_KEY_TRUSTED",
            actor="LOCAL_SOVEREIGN_BOOTSTRAP",
            subject_id=composite,
            payload={"public_key_sha256": _sha256_text(public_key_b64)},
        )
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(record)

    def register_sovereign_key(
        self,
        *,
        key_id: str,
        public_key_b64: str,
        valid_from: datetime | str,
        valid_until: datetime | str,
    ) -> dict[str, Any]:
        record = self._key_record(
            owner_id=JANUS_SOVEREIGN,
            key_id=key_id,
            public_key_b64=public_key_b64,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        store = self._plural_store()
        store["trusted_sovereign_keys"][key_id] = record
        self._append_authority_event(
            store,
            event_type="SOVEREIGN_KEY_TRUSTED",
            actor="LOCAL_SOVEREIGN_BOOTSTRAP",
            subject_id=key_id,
            payload={"public_key_sha256": _sha256_text(public_key_b64)},
        )
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(record)

    @staticmethod
    def _key_status(
        record: dict[str, Any],
        *,
        at_time: datetime | str | None = None,
        signed_at: Any = None,
    ) -> tuple[bool, str | None]:
        now = _parse_time(_iso_utc(at_time))
        valid_from = _parse_time(record["valid_from"])
        valid_until = _parse_time(record["valid_until"])
        if now < valid_from:
            return False, "KEY_NOT_YET_VALID"
        if now >= valid_until:
            return False, "KEY_EXPIRED"
        revoked = record.get("revoked_at")
        if revoked and now >= _parse_time(revoked):
            return False, "KEY_REVOKED"
        compromised = record.get("compromised_from")
        if compromised and signed_at is not None and _parse_time(signed_at) >= _parse_time(compromised):
            return False, "KEY_COMPROMISED_FOR_SIGNATURE_TIME"
        return True, None

    def revoke_trusted_provider_key(
        self,
        provider_id: str,
        key_id: str,
        *,
        reason: str,
        revoked_at: datetime | str | None = None,
        compromised_from: datetime | str | None = None,
    ) -> None:
        store = self._plural_store()
        composite = f"{provider_id}:{key_id}"
        record = store["trusted_provider_keys"].get(composite)
        if not isinstance(record, dict):
            raise KeyError(composite)
        record["revoked_at"] = _iso_utc(revoked_at)
        record["compromised_from"] = None if compromised_from is None else _iso_utc(compromised_from)
        record["revocation_reason"] = str(reason)
        self._append_authority_event(
            store,
            event_type="PROVIDER_KEY_REVOKED",
            actor=JANUS_SOVEREIGN,
            subject_id=composite,
            payload={"reason": str(reason), "compromised_from": record["compromised_from"]},
        )
        self._write_json(self.plural_witness_path, store)
        self._reactive_reaudit(reason="provider_key_revoked", provider_key=composite)

    def revoke_sovereign_key(
        self,
        key_id: str,
        *,
        reason: str,
        revoked_at: datetime | str | None = None,
        compromised_from: datetime | str | None = None,
    ) -> None:
        store = self._plural_store()
        record = store["trusted_sovereign_keys"].get(key_id)
        if not isinstance(record, dict):
            raise KeyError(key_id)
        record["revoked_at"] = _iso_utc(revoked_at)
        record["compromised_from"] = None if compromised_from is None else _iso_utc(compromised_from)
        record["revocation_reason"] = str(reason)
        self._append_authority_event(
            store,
            event_type="SOVEREIGN_KEY_REVOKED",
            actor=JANUS_SOVEREIGN,
            subject_id=key_id,
            payload={"reason": str(reason), "compromised_from": record["compromised_from"]},
        )
        self._write_json(self.plural_witness_path, store)
        self._reactive_reaudit(reason="sovereign_key_revoked")

    @staticmethod
    def _nonce_key(kind: str, issuer: str, nonce: str) -> str:
        return _sha256_text(f"{kind}:{issuer}:{nonce}")

    @staticmethod
    def _consume_nonce(
        store: dict[str, Any],
        *,
        kind: str,
        issuer: str,
        nonce: str,
        subject_id: str,
    ) -> None:
        if not str(nonce).strip():
            raise ValueError("nonce is required")
        key = BoundAuthorityMixin._nonce_key(kind, issuer, nonce)
        if key in store["consumed_nonces"]:
            raise ValueError("REPLAYED")
        store["consumed_nonces"][key] = {
            "kind": kind,
            "issuer": issuer,
            "subject_id": subject_id,
            "consumed_at": _iso_utc(),
        }

    @staticmethod
    def _verify_provider_attestation(
        store: dict[str, Any],
        attestation: dict[str, Any],
        *,
        at_time: datetime | str | None = None,
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        if attestation.get("schema") != PROVIDER_ATTESTATION_SCHEMA:
            return False, "UNSUPPORTED_PROVIDER_ATTESTATION_SCHEMA", None
        provider_id = str(attestation.get("provider_id", ""))
        key_id = str(attestation.get("key_id", ""))
        key_record = store["trusted_provider_keys"].get(f"{provider_id}:{key_id}")
        if not isinstance(key_record, dict):
            return False, "UNKNOWN_PROVIDER_KEY", None
        window_valid, window_error = _window_valid(
            attestation.get("issued_at"), attestation.get("expires_at"), at_time=at_time
        )
        if not window_valid:
            return False, window_error, key_record
        key_valid, key_error = BoundAuthorityMixin._key_status(
            key_record, at_time=at_time, signed_at=attestation.get("issued_at")
        )
        if not key_valid:
            return False, key_error, key_record
        if not verify_signed_payload(attestation, key_record["public_key_b64"]):
            return False, "INVALID_SIGNATURE", key_record
        return True, None, key_record

    def register_influence_account(
        self,
        account_id: str,
        *,
        identity_proof: str,
        controller_proof: str | None = None,
        provider_attestation: dict[str, Any] | None = None,
        operator_disclosed: bool = True,
        sponsored: bool = False,
        sponsor: str | None = None,
        automation: bool = False,
        automation_disclosed: bool = False,
        active: bool = True,
        **legacy_flags: Any,
    ) -> dict[str, Any]:
        if "provider_verified" in legacy_flags or "identity_provider" in legacy_flags:
            raise ValueError(
                "provider_verified and caller-supplied identity_provider are removed; "
                "a signed ProviderAttestation is required"
            )
        if not isinstance(provider_attestation, dict):
            raise ValueError("signed ProviderAttestation is required")
        account_id = str(account_id).strip()
        identity_proof = str(identity_proof)
        controller_proof = identity_proof if controller_proof is None else str(controller_proof)
        store = self._plural_store()
        valid, error, _key_record = self._verify_provider_attestation(store, provider_attestation)
        if not valid:
            raise ValueError(error or "provider attestation rejected")
        expected = {
            "subject_id": account_id,
            "identity_proof_sha256": _sha256_text(identity_proof),
            "controller_proof_sha256": _sha256_text(controller_proof),
        }
        for field, value in expected.items():
            if provider_attestation.get(field) != value:
                raise ValueError(f"provider attestation {field} mismatch")
        account_public_key = str(provider_attestation.get("account_public_key_b64", ""))
        if len(_b64decode(account_public_key)) != 32:
            raise ValueError("provider attestation lacks valid account public key")
        provider_id = str(provider_attestation["provider_id"])
        self._consume_nonce(
            store,
            kind="provider_attestation",
            issuer=provider_id,
            nonce=str(provider_attestation.get("nonce", "")),
            subject_id=account_id,
        )
        super().register_influence_account(
            account_id,
            identity_proof=identity_proof,
            controller_proof=controller_proof,
            identity_provider=provider_id,
            provider_verified=False,
            operator_disclosed=operator_disclosed,
            sponsored=sponsored,
            sponsor=sponsor,
            automation=automation,
            automation_disclosed=automation_disclosed,
            active=active,
        )
        store = self._plural_store()
        attestation_id = self._stable_id("provider-attestation-v18.7.9", sha256_canonical(provider_attestation))
        stored_attestation = copy.deepcopy(provider_attestation)
        stored_attestation["attestation_id"] = attestation_id
        stored_attestation["signature_verified"] = True
        stored_attestation["private_key_persisted"] = False
        store["provider_attestations_v179"][attestation_id] = stored_attestation
        entry = store["influence_accounts"][account_id]
        entry["identity_provider"] = provider_id
        entry.pop("provider_verified", None)
        entry.pop("provider_verification_recorded", None)
        entry["provider_attestation_id"] = attestation_id
        entry["provider_signature_verified"] = True
        entry["provider_key_id"] = provider_attestation["key_id"]
        entry["provider_key_ref"] = f"{provider_attestation['provider_id']}:{provider_attestation['key_id']}"
        entry["account_public_key_b64"] = account_public_key
        entry["controller_binding_current"] = True
        entry["provider_trust_mode"] = "signed_ed25519_attestation"
        entry["private_key_persisted"] = False
        self._append_authority_event(
            store,
            event_type="PROVIDER_ATTESTATION_ACCEPTED",
            actor=provider_id,
            subject_id=account_id,
            payload={"attestation_id": attestation_id, "provider_key_ref": entry["provider_key_ref"]},
        )
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(entry)

    def register_attestation_delegation(self, delegation: dict[str, Any]) -> str:
        if delegation.get("schema") != DELEGATION_SCHEMA:
            raise ValueError("unsupported delegation schema")
        store = self._plural_store()
        delegator = str(delegation.get("delegator", ""))
        delegate = str(delegation.get("delegate", ""))
        account = store["influence_accounts"].get(delegator)
        if not isinstance(account, dict):
            raise KeyError(delegator)
        if not verify_signed_payload(delegation, account["account_public_key_b64"]):
            raise ValueError("INVALID_DELEGATION_SIGNATURE")
        valid, error = _window_valid(delegation.get("issued_at"), delegation.get("expires_at"))
        if not valid:
            raise ValueError(error or "delegation outside validity window")
        if delegation.get("scope") != "voice_attestation":
            raise ValueError("delegation scope must be voice_attestation")
        self._consume_nonce(
            store,
            kind="delegation",
            issuer=delegator,
            nonce=str(delegation.get("nonce", "")),
            subject_id=delegate,
        )
        delegation_id = self._stable_id("attestation-delegation", sha256_canonical(delegation))
        record = copy.deepcopy(delegation)
        record.update({"delegation_id": delegation_id, "active": True, "signature_verified": True, "revoked_at": None})
        store["attestation_delegations"][delegation_id] = record
        self._append_authority_event(
            store,
            event_type="ATTESTATION_DELEGATED",
            actor=delegator,
            subject_id=delegate,
            payload={"delegation_id": delegation_id, "claim_id": record.get("claim_id")},
        )
        self._write_json(self.plural_witness_path, store)
        return delegation_id

    def revoke_attestation_delegation(self, delegation_id: str, *, reason: str) -> None:
        store = self._plural_store()
        record = store["attestation_delegations"].get(delegation_id)
        if not isinstance(record, dict):
            raise KeyError(delegation_id)
        record["active"] = False
        record["revoked_at"] = _iso_utc()
        record["revocation_reason"] = str(reason)
        self._append_authority_event(
            store,
            event_type="ATTESTATION_DELEGATION_REVOKED",
            actor=record["delegator"],
            subject_id=record["delegate"],
            payload={"delegation_id": delegation_id, "reason": str(reason)},
        )
        self._write_json(self.plural_witness_path, store)
        self._reactive_reaudit(reason="delegation_revoked")

    @staticmethod
    def _claim_reader_id(claim: dict[str, Any]) -> str | None:
        actor = str(claim.get("actor", ""))
        return actor.removeprefix("reader:") if actor.startswith("reader:") else None

    @staticmethod
    def _valid_delegation(
        store: dict[str, Any],
        *,
        delegator: str,
        delegate: str,
        claim_id: str,
        at_time: datetime | str | None = None,
    ) -> dict[str, Any] | None:
        for record in store["attestation_delegations"].values():
            if not isinstance(record, dict) or not record.get("active"):
                continue
            if record.get("delegator") != delegator or record.get("delegate") != delegate:
                continue
            if record.get("scope") != "voice_attestation":
                continue
            if record.get("claim_id") not in (None, claim_id):
                continue
            valid, _error = _window_valid(record.get("issued_at"), record.get("expires_at"), at_time=at_time)
            if valid:
                return record
        return None

    def attest_claim_influence(
        self,
        claim_id: str,
        *,
        account_id: str,
        evidence_proof: str,
        message: str | None = None,
        campaign_id: str | None = None,
        campaign_disclosed: bool = False,
        origin_authentic: bool = True,
        authenticity_evidence: str | None = None,
        delegation_id: str | None = None,
    ) -> str:
        store = self._plural_store()
        claim = store["claims"].get(claim_id)
        account = store["influence_accounts"].get(account_id)
        if not isinstance(claim, dict):
            raise KeyError(claim_id)
        if not isinstance(account, dict):
            raise KeyError(account_id)
        speaker_id = self._claim_reader_id(claim)
        if speaker_id is None:
            raise ValueError("influence attestation requires a reader claim actor")
        delegation = None
        if speaker_id != account_id:
            if delegation_id is not None:
                delegation = self._valid_delegation(
                    store,
                    delegator=speaker_id,
                    delegate=account_id,
                    claim_id=claim_id,
                )
                if not delegation or delegation.get("delegation_id") != delegation_id:
                    delegation = None
            if delegation is None:
                raise ValueError(
                    "claim.actor must equal attestation.account unless a valid speaker-signed delegation exists"
                )
        attestation_id = super().attest_claim_influence(
            claim_id,
            account_id=account_id,
            evidence_proof=evidence_proof,
            message=message,
            campaign_id=campaign_id,
            campaign_disclosed=campaign_disclosed,
            origin_authentic=origin_authentic,
            authenticity_evidence=authenticity_evidence,
        )
        store = self._plural_store()
        attestation = store["influence_attestations"][attestation_id]
        attestation["speaker_account_id"] = speaker_id
        attestation["attester_account_id"] = account_id
        attestation["actor_binding_valid"] = True
        attestation["delegation_id"] = delegation_id
        attestation["provider_attestation_id"] = account.get("provider_attestation_id")
        attestation["provider_signature_verified"] = bool(account.get("provider_signature_verified"))
        attestation["eligibility_is_dynamic"] = True
        attestation["base_eligible_snapshot_only"] = attestation.pop("base_eligible", False)
        claim["influence_voice_eligible"] = None
        self._append_authority_event(
            store,
            event_type="CLAIM_INFLUENCE_ATTESTED",
            actor=account_id,
            subject_id=claim_id,
            payload={"attestation_id": attestation_id, "speaker_account_id": speaker_id, "delegation_id": delegation_id},
        )
        self._write_json(self.plural_witness_path, store)
        return attestation_id

    def record_source_assertion(
        self,
        origin_key: str,
        *,
        evidence: dict[str, Any],
        about: str | None = None,
        confidence: float | None = None,
        claimant_stated_confidence: float | None = None,
        subject_scope_id: str | None = None,
    ) -> str:
        stated = claimant_stated_confidence if claimant_stated_confidence is not None else confidence
        claim_id = super().record_source_assertion(
            origin_key,
            evidence=evidence,
            about=about,
            confidence=0.5,
            subject_scope_id=subject_scope_id,
        )
        store = self._plural_store()
        claim = store["claims"][claim_id]
        claim["claimant_stated_confidence"] = stated
        claim["confidence"] = 0.5
        claim["confidence_authority"] = "unassessed_default_not_sovereign_weight"
        self._write_json(self.plural_witness_path, store)
        return claim_id

    def record_reader_interpretation(
        self,
        origin_key: str,
        interpretation: str,
        *,
        reader_id: str,
        evidence: dict[str, Any] | None = None,
        about: str | None = None,
        confidence: float | None = None,
        claimant_stated_confidence: float | None = None,
        subject_scope_id: str | None = None,
    ) -> str:
        stated = claimant_stated_confidence if claimant_stated_confidence is not None else confidence
        claim_id = super().record_reader_interpretation(
            origin_key,
            interpretation,
            reader_id=reader_id,
            evidence=evidence,
            about=about,
            confidence=0.5,
            subject_scope_id=subject_scope_id,
        )
        store = self._plural_store()
        claim = store["claims"][claim_id]
        claim["claimant_stated_confidence"] = stated
        claim["confidence"] = 0.5
        claim["confidence_authority"] = "unassessed_default_not_sovereign_weight"
        self._write_json(self.plural_witness_path, store)
        return claim_id

    def record_evidence_assessment(
        self,
        claim_id: str,
        *,
        components: dict[str, float],
        assessor_id: str,
        method_id: str,
        method_version: str,
        evidence_ids: Iterable[str],
        explanation: str,
    ) -> str:
        store = self._plural_store()
        claim = store["claims"].get(claim_id)
        if not isinstance(claim, dict):
            raise KeyError(claim_id)
        normalized: dict[str, float] = {}
        for name in ASSESSMENT_COMPONENTS:
            if name not in components:
                raise ValueError(f"missing assessment component: {name}")
            value = float(components[name])
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"assessment component out of range: {name}")
            normalized[name] = round(value, 6)
        evidence_ids_list = sorted(set(str(item).strip() for item in evidence_ids if str(item).strip()))
        if not evidence_ids_list or not str(explanation).strip():
            raise ValueError("assessment requires evidence_ids and explanation")
        assessment_confidence = round(sum(normalized.values()) / len(normalized), 6)
        material = {
            "schema": EVIDENCE_ASSESSMENT_SCHEMA,
            "claim_id": claim_id,
            "components": normalized,
            "assessment_confidence": assessment_confidence,
            "assessor_id": str(assessor_id),
            "method_id": str(method_id),
            "method_version": str(method_version),
            "evidence_ids": evidence_ids_list,
            "explanation": str(explanation),
            "calculated_at": _iso_utc(),
        }
        assessment_id = self._stable_id("evidence-assessment", sha256_canonical(material))
        material["assessment_id"] = assessment_id
        store["evidence_assessments"][assessment_id] = material
        claim["assessment_id"] = assessment_id
        claim["assessment_confidence"] = assessment_confidence
        claim["confidence_authority"] = "evidence_assessment"
        self._append_authority_event(
            store,
            event_type="EVIDENCE_ASSESSMENT_RECORDED",
            actor=str(assessor_id),
            subject_id=claim_id,
            payload={"assessment_id": assessment_id, "confidence": assessment_confidence},
        )
        self._write_json(self.plural_witness_path, store)
        return assessment_id

    @staticmethod
    def _assessment_confidence(claim: dict[str, Any]) -> float:
        value = claim.get("assessment_confidence")
        return 0.5 if value is None else max(0.0, min(1.0, float(value)))

    @staticmethod
    def _pick_representative(claims: list[dict[str, Any]]) -> dict[str, Any]:
        return sorted(
            claims,
            key=lambda claim: (-BoundAuthorityMixin._assessment_confidence(claim), claim["claim_id"]),
        )[0]

    def _recommend_case(self, claims: list[dict[str, Any]]) -> dict[str, Any]:
        recommendation = super()._recommend_case(claims)
        for position in recommendation["positions"]:
            position["confidence_total"] = round(
                sum(
                    self._assessment_confidence(claim)
                    for claim in claims
                    if claim["claim_id"] in position["claim_ids"]
                ),
                6,
            )
            position["confidence_source"] = "evidence_assessment"
        recommendation["claimant_confidence_used"] = False
        return recommendation

    def _provider_current_reason(
        self,
        store: dict[str, Any],
        account: dict[str, Any],
        *,
        at_time: datetime | str | None = None,
    ) -> str | None:
        attestation_id = account.get("provider_attestation_id")
        attestation = store["provider_attestations_v179"].get(attestation_id)
        if not isinstance(attestation, dict):
            return "NO_SIGNED_PROVIDER_ATTESTATION"
        valid, error, _key = self._verify_provider_attestation(store, attestation, at_time=at_time)
        return None if valid else error or "PROVIDER_ATTESTATION_INVALID"

    def _dynamic_claim_reasons(
        self,
        store: dict[str, Any],
        claim: dict[str, Any],
        attestation: dict[str, Any],
        *,
        at_time: datetime | str | None = None,
    ) -> list[str]:
        reasons: list[str] = []
        account_id = str(attestation.get("attester_account_id") or attestation.get("account_id"))
        account = store["influence_accounts"].get(account_id, {})
        speaker_id = str(attestation.get("speaker_account_id") or self._claim_reader_id(claim) or "")
        voice = store["voice_registry"].get(speaker_id, {})
        if not account.get("active"):
            reasons.append("ACCOUNT_INACTIVE")
        if not voice.get("active"):
            reasons.append("VOICE_INACTIVE")
        if not voice.get("consented"):
            reasons.append("VOICE_NOT_CONSENTING")
        if voice.get("withdrawn"):
            reasons.append("VOICE_WITHDRAWN")
        if not account.get("controller_binding_current", True):
            reasons.append("CONTROLLER_BINDING_STALE")
        provider_reason = self._provider_current_reason(store, account, at_time=at_time)
        if provider_reason:
            reasons.append(provider_reason)
        if speaker_id != account_id:
            delegation = self._valid_delegation(
                store,
                delegator=speaker_id,
                delegate=account_id,
                claim_id=claim["claim_id"],
                at_time=at_time,
            )
            if delegation is None:
                reasons.append("ATTESTATION_DELEGATION_INVALID")
        if not account.get("operator_disclosed"):
            reasons.append("OPERATOR_NOT_DISCLOSED")
        if not account.get("sponsorship_disclosed"):
            reasons.append("SPONSORSHIP_NOT_DISCLOSED")
        if not account.get("automation_transparent"):
            reasons.append("AUTOMATION_NOT_DISCLOSED")
        if attestation.get("campaign_cluster") and not attestation.get("campaign_disclosed"):
            reasons.append("CAMPAIGN_NOT_DISCLOSED")
        if not attestation.get("origin_authentic"):
            reasons.append("ORIGIN_AUTHENTICITY_CHALLENGED")
        if not claim.get("grounded"):
            reasons.append("CLAIM_NOT_GROUNDED")
        if not attestation.get("actor_binding_valid"):
            reasons.append("ATTESTATION_ACTOR_BINDING_INVALID")
        confirmed = [
            record_id
            for record_id in claim.get("manipulation_evidence_ids", [])
            if self._review_status(store, record_id) in {"CONFIRMED", "REJECTED_ON_APPEAL"}
        ]
        if confirmed:
            reasons.append("MANIPULATION_EVIDENCE_CONFIRMED")
        return sorted(set(reasons))

    def audit_influence_claims(
        self,
        claim_ids: Iterable[str],
        *,
        at_time: datetime | str | None = None,
    ) -> dict[str, Any]:
        members = list(dict.fromkeys(str(item).strip() for item in claim_ids if str(item).strip()))
        store = self._plural_store()
        reasons: dict[str, list[str]] = {}
        candidates: list[dict[str, Any]] = []
        for claim_id in members:
            claim = store["claims"].get(claim_id)
            if not isinstance(claim, dict):
                raise KeyError(claim_id)
            attestation = store["influence_attestations"].get(claim.get("influence_attestation_id"))
            if not isinstance(attestation, dict):
                reasons[claim_id] = ["NO_INFLUENCE_ATTESTATION"]
                continue
            claim_reasons = self._dynamic_claim_reasons(store, claim, attestation, at_time=at_time)
            claim["influence_voice_eligible"] = not claim_reasons
            if claim_reasons:
                reasons[claim_id] = claim_reasons
                continue
            candidates.append({"claim": claim, "attestation": attestation})

        controller_groups: dict[str, list[dict[str, Any]]] = {}
        for item in candidates:
            key = item["attestation"]["controller_cluster"]
            controller_groups.setdefault(key, []).append(item)
        controller_representatives: list[dict[str, Any]] = []
        for group in controller_groups.values():
            representative_claim = self._pick_representative([item["claim"] for item in group])
            representative = next(item for item in group if item["claim"]["claim_id"] == representative_claim["claim_id"])
            controller_representatives.append(representative)
            for item in group:
                claim_id = item["claim"]["claim_id"]
                if claim_id != representative_claim["claim_id"]:
                    reasons.setdefault(claim_id, []).append("SAME_CONTROLLER_AMPLIFICATION")

        campaign_groups: dict[str, list[dict[str, Any]]] = {}
        for item in controller_representatives:
            campaign = item["attestation"].get("campaign_cluster")
            key = f"campaign:{campaign}" if campaign else f"organic:{item['attestation']['controller_cluster']}"
            campaign_groups.setdefault(key, []).append(item)
        campaign_representatives: list[dict[str, Any]] = []
        for key, group in campaign_groups.items():
            representative_claim = self._pick_representative([item["claim"] for item in group])
            representative = next(item for item in group if item["claim"]["claim_id"] == representative_claim["claim_id"])
            campaign_representatives.append(representative)
            if key.startswith("campaign:"):
                for item in group:
                    claim_id = item["claim"]["claim_id"]
                    if claim_id != representative_claim["claim_id"]:
                        reasons.setdefault(claim_id, []).append("SAME_CAMPAIGN_AMPLIFICATION")

        message_groups: dict[str, list[dict[str, Any]]] = {}
        for item in campaign_representatives:
            attestation = item["attestation"]
            key = "|".join((attestation["message_fingerprint"], attestation["evidence_family"]))
            message_groups.setdefault(key, []).append(item)
        eligible: list[str] = []
        for group in message_groups.values():
            representative_claim = self._pick_representative([item["claim"] for item in group])
            eligible.append(representative_claim["claim_id"])
            for item in group:
                claim_id = item["claim"]["claim_id"]
                if claim_id != representative_claim["claim_id"]:
                    reasons.setdefault(claim_id, []).append("MIRRORED_MESSAGE_AND_EVIDENCE")

        eligible = sorted(set(eligible))
        quarantined = sorted(set(members) - set(eligible))
        controller_collisions = sum(max(0, len(group) - 1) for group in controller_groups.values())
        campaign_collisions = sum(max(0, len(group) - 1) for key, group in campaign_groups.items() if key.startswith("campaign:"))
        mirrored = sum(max(0, len(group) - 1) for group in message_groups.values())
        explicit_manipulation = sum(
            1
            for claim_id in members
            if any(
                self._review_status(store, record_id) in {"CONFIRMED", "REJECTED_ON_APPEAL"}
                for record_id in store["claims"].get(claim_id, {}).get("manipulation_evidence_ids", [])
            )
        )
        disclosure_failures = sum(
            1
            for items in reasons.values()
            if any("DISCLOSED" in reason or "DISCLOSURE" in reason for reason in items)
        )
        if explicit_manipulation or controller_collisions >= 2 or disclosure_failures:
            risk_level = "HIGH"
        elif controller_collisions or campaign_collisions or mirrored or quarantined:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        material = {
            "submitted_claim_ids": members,
            "eligible_claim_ids": eligible,
            "quarantined_claim_ids": quarantined,
            "reasons_by_claim": {key: sorted(set(value)) for key, value in sorted(reasons.items())},
            "independent_voice_count": len(eligible),
            "controller_cluster_count": len(controller_groups),
            "campaign_cluster_count": len(campaign_groups),
            "message_evidence_cluster_count": len(message_groups),
            "controller_collisions": controller_collisions,
            "campaign_collisions": campaign_collisions,
            "mirrored_amplification": mirrored,
            "explicit_manipulation_evidence_count": explicit_manipulation,
            "risk_level": risk_level,
            "reach_counted_as_evidence": False,
            "truth_verdict_inferred": False,
            "dissent_treated_as_manipulation": False,
            "claims_deleted": False,
            "eligibility_evaluated_at": _iso_utc(at_time),
            "eligibility_is_dynamic": True,
            "controller_outranks_campaign": True,
            "claimant_confidence_used": False,
        }
        audit_id = self._stable_id("bound-authority-influence-audit", _sha256_text(_iso_utc()), sha256_canonical(material))
        audit = {"audit_id": audit_id, **material}
        store["influence_audits"][audit_id] = audit
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(audit)

    def _verify_capability(
        self,
        capability: dict[str, Any] | None,
        *,
        scope: str,
        case_id: str,
        consume: bool,
    ) -> dict[str, Any]:
        if not isinstance(capability, dict):
            raise ValueError("signed SOVEREIGN_CAPABILITY is required")
        if capability.get("schema") != SOVEREIGN_CAPABILITY_SCHEMA:
            raise ValueError("unsupported sovereign capability schema")
        if capability.get("actor") != JANUS_SOVEREIGN:
            raise ValueError("capability actor mismatch")
        if capability.get("scope") != scope:
            raise ValueError("WRONG_SCOPE")
        if capability.get("case_id") != case_id:
            raise ValueError("WRONG_CASE")
        store = self._plural_store()
        key_id = str(capability.get("key_id", ""))
        key = store["trusted_sovereign_keys"].get(key_id)
        if not isinstance(key, dict):
            raise ValueError("UNKNOWN_KEY")
        valid, error = _window_valid(capability.get("issued_at"), capability.get("expires_at"))
        if not valid:
            raise ValueError(error or "capability time invalid")
        key_valid, key_error = self._key_status(key, signed_at=capability.get("issued_at"))
        if not key_valid:
            raise ValueError(key_error or "sovereign key invalid")
        if not verify_signed_payload(capability, key["public_key_b64"]):
            raise ValueError("INVALID_SIGNATURE")
        if consume:
            self._consume_nonce(
                store,
                kind="sovereign_capability",
                issuer=JANUS_SOVEREIGN,
                nonce=str(capability.get("nonce", "")),
                subject_id=f"{scope}:{case_id}",
            )
            self._append_authority_event(
                store,
                event_type="SOVEREIGN_CAPABILITY_CONSUMED",
                actor=JANUS_SOVEREIGN,
                subject_id=case_id,
                payload={
                    "scope": scope,
                    "key_id": key_id,
                    "nonce_sha256": _sha256_text(str(capability.get("nonce", ""))),
                },
            )
            self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(capability)

    def record_manipulation_evidence(
        self,
        claim_id: str,
        *,
        kind: str,
        evidence: str,
        reporter_id: str,
    ) -> str:
        record_id = super().record_manipulation_evidence(
            claim_id, kind=kind, evidence=evidence, reporter_id=reporter_id
        )
        store = self._plural_store()
        record = store["manipulation_evidence"][record_id]
        record["immutable_baseline"] = True
        record["status"] = "PENDING_REVIEW"
        self._append_authority_event(
            store,
            event_type="PENDING_REVIEW",
            actor=str(reporter_id),
            subject_id=record_id,
            payload={"claim_id": claim_id, "kind": str(kind).upper()},
        )
        self._write_json(self.plural_witness_path, store)
        return record_id

    def _append_authority_event(
        self,
        store: dict[str, Any],
        *,
        event_type: str,
        actor: str,
        subject_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        previous_hash = store["authority_events"][-1]["event_hash"] if store["authority_events"] else "GENESIS"
        event = {
            "schema": AUTHORITY_EVENT_SCHEMA,
            "event_index": len(store["authority_events"]) + 1,
            "event_type": str(event_type),
            "actor": str(actor),
            "subject_id": str(subject_id),
            "occurred_at": _iso_utc(),
            "payload": copy.deepcopy(payload),
            "previous_hash": previous_hash,
        }
        event["event_hash"] = sha256_canonical(event)
        store["authority_events"].append(event)
        return event

    @staticmethod
    def _events_for(
        store: dict[str, Any],
        subject_id: str,
        *,
        event_types: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in store.get("authority_events", [])
            if event.get("subject_id") == subject_id
            and (event_types is None or event.get("event_type") in event_types)
        ]

    def _review_status(self, store: dict[str, Any], record_id: str) -> str:
        events = self._events_for(
            store,
            record_id,
            event_types={
                "PENDING_REVIEW",
                "CONFIRMED",
                "REJECTED",
                "APPEALED",
                "REJECTED_ON_APPEAL",
                "RESTORED",
            },
        )
        return str(events[-1]["event_type"]) if events else "PENDING_REVIEW"

    def confirm_manipulation_evidence(
        self,
        record_id: str,
        *,
        confirmed: bool,
        rationale: str,
        capability: dict[str, Any] | None,
        **legacy: Any,
    ) -> None:
        if "reviewer_id" in legacy:
            raise ValueError("reviewer_id strings are removed; capability is required")
        self._verify_capability(
            capability,
            scope="manipulation_review",
            case_id=record_id,
            consume=True,
        )
        store = self._plural_store()
        record = store["manipulation_evidence"].get(record_id)
        if not isinstance(record, dict):
            raise KeyError(record_id)
        self._append_authority_event(
            store,
            event_type="CONFIRMED" if confirmed else "REJECTED",
            actor=JANUS_SOVEREIGN,
            subject_id=record_id,
            payload={"rationale": str(rationale), "claim_id": record["claim_id"], "kind": record["kind"]},
        )
        self._write_json(self.plural_witness_path, store)
        self.recalculate_eligibility(record["claim_id"], reason="manipulation_review_changed")

    def appeal_manipulation_evidence(
        self,
        record_id: str,
        *,
        appellant_id: str,
        grounds: str,
    ) -> None:
        store = self._plural_store()
        if record_id not in store["manipulation_evidence"]:
            raise KeyError(record_id)
        if self._review_status(store, record_id) not in {"CONFIRMED", "REJECTED"}:
            raise ValueError("appeal requires a reviewed manipulation record")
        self._append_authority_event(
            store,
            event_type="APPEALED",
            actor=str(appellant_id),
            subject_id=record_id,
            payload={"grounds": str(grounds)},
        )
        self._write_json(self.plural_witness_path, store)

    def resolve_manipulation_appeal(
        self,
        record_id: str,
        *,
        restored: bool,
        rationale: str,
        capability: dict[str, Any] | None,
    ) -> None:
        self._verify_capability(
            capability,
            scope="manipulation_appeal",
            case_id=record_id,
            consume=True,
        )
        store = self._plural_store()
        record = store["manipulation_evidence"].get(record_id)
        if not isinstance(record, dict):
            raise KeyError(record_id)
        if self._review_status(store, record_id) != "APPEALED":
            raise ValueError("record is not currently appealed")
        event_type = "RESTORED" if restored else "REJECTED_ON_APPEAL"
        self._append_authority_event(
            store,
            event_type=event_type,
            actor=JANUS_SOVEREIGN,
            subject_id=record_id,
            payload={"rationale": str(rationale), "claim_id": record["claim_id"]},
        )
        self._write_json(self.plural_witness_path, store)
        self.recalculate_eligibility(record["claim_id"], reason=event_type.lower())

    def recalculate_eligibility(self, claim_id: str, *, reason: str) -> bool:
        store = self._plural_store()
        claim = store["claims"].get(claim_id)
        if not isinstance(claim, dict):
            raise KeyError(claim_id)
        attestation = store["influence_attestations"].get(claim.get("influence_attestation_id"))
        eligible = False
        current_reasons = ["NO_INFLUENCE_ATTESTATION"]
        if isinstance(attestation, dict):
            current_reasons = self._dynamic_claim_reasons(store, claim, attestation)
            eligible = not current_reasons
        previous = claim.get("influence_voice_eligible")
        claim["influence_voice_eligible"] = eligible
        claim["eligibility_reasons_current"] = current_reasons
        self._append_authority_event(
            store,
            event_type="ELIGIBILITY_RECALCULATED",
            actor=JANUS_SOVEREIGN,
            subject_id=claim_id,
            payload={"previous": previous, "current": eligible, "reason": str(reason), "reasons": current_reasons},
        )
        self._write_json(self.plural_witness_path, store)
        self._reactive_reaudit(reason=reason, affected_claim_id=claim_id)
        return eligible

    def deactivate_influence_account(self, account_id: str, *, reason: str) -> None:
        super().deactivate_influence_account(account_id, reason=reason)
        self._reactive_reaudit(reason="account_deactivated", affected_account_id=account_id)

    def withdraw_witness_voice(self, reader_id: str) -> None:
        super().withdraw_witness_voice(reader_id)
        self._reactive_reaudit(reason="voice_withdrawn", affected_account_id=reader_id)

    def _reactive_reaudit(
        self,
        *,
        reason: str,
        affected_claim_id: str | None = None,
        affected_account_id: str | None = None,
        provider_key: str | None = None,
    ) -> None:
        store = self._plural_store()
        case_ids = list(store["sovereign_cases"])
        affected_cases: list[str] = []
        for case_id in case_ids:
            current_store = self._plural_store()
            case = current_store["sovereign_cases"].get(case_id)
            if not isinstance(case, dict) or not case.get("influence_sensitive"):
                continue
            submitted = case.get("submitted_claim_ids", case.get("claim_ids", []))
            if affected_claim_id and affected_claim_id not in submitted:
                continue
            if affected_account_id:
                involved = False
                for claim_id in submitted:
                    claim = current_store["claims"].get(claim_id, {})
                    attestation = current_store["influence_attestations"].get(claim.get("influence_attestation_id"), {})
                    if affected_account_id in {
                        attestation.get("speaker_account_id"),
                        attestation.get("attester_account_id"),
                        attestation.get("account_id"),
                    }:
                        involved = True
                        break
                if not involved:
                    continue
            if provider_key:
                involved = False
                for claim_id in submitted:
                    claim = current_store["claims"].get(claim_id, {})
                    attestation = current_store["influence_attestations"].get(claim.get("influence_attestation_id"), {})
                    account_id = attestation.get("attester_account_id") or attestation.get("account_id")
                    account = current_store["influence_accounts"].get(account_id, {})
                    if account.get("provider_key_ref") == provider_key:
                        involved = True
                        break
                if not involved:
                    continue
            audit = self.audit_influence_claims(submitted)
            current_store = self._plural_store()
            case = current_store["sovereign_cases"][case_id]
            previous_eligible = set(case.get("claim_ids", []))
            current_eligible = set(audit["eligible_claim_ids"])
            if current_eligible != previous_eligible or case.get("janus_decision_id"):
                case["status"] = "CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE"
                case["janus_decision_id"] = None
                case["claim_ids"] = sorted(current_eligible)
                case["witness_count"] = len(current_eligible)
                case["influence_audit_id"] = audit["audit_id"]
                case["quarantined_claim_ids"] = audit["quarantined_claim_ids"]
                case["history"].append(
                    {
                        "status": case["status"],
                        "reason": reason,
                        "affected_claim_id": affected_claim_id,
                        "affected_account_id": affected_account_id,
                        "provider_key": provider_key,
                        "audit_id": audit["audit_id"],
                    }
                )
                current_store["sovereign_cases"][case_id] = case
                self._write_json(self.plural_witness_path, current_store)
                affected_cases.append(case_id)
        if affected_cases:
            store = self._plural_store()
            reaudit_id = self._stable_id("reactive-reaudit", reason, _iso_utc(), *sorted(affected_cases))
            store["reactive_reaudits"][reaudit_id] = {
                "reaudit_id": reaudit_id,
                "reason": reason,
                "affected_cases": sorted(affected_cases),
                "occurred_at": _iso_utc(),
            }
            self._append_authority_event(
                store,
                event_type="CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE",
                actor=JANUS_SOVEREIGN,
                subject_id=reaudit_id,
                payload={"reason": reason, "affected_cases": sorted(affected_cases)},
            )
            self._write_json(self.plural_witness_path, store)

    def janus_sovereign_decide(
        self,
        case_id: str,
        *,
        capability: dict[str, Any] | None = None,
    ) -> str:
        store = self._plural_store()
        case = store["sovereign_cases"].get(case_id)
        if not isinstance(case, dict):
            raise KeyError(case_id)
        if not case.get("influence_sensitive"):
            return super().janus_sovereign_decide(case_id)
        self._verify_capability(
            capability,
            scope="sovereign_case_decision",
            case_id=case_id,
            consume=True,
        )
        audit = self.audit_influence_claims(case.get("submitted_claim_ids", case.get("claim_ids", [])))
        store = self._plural_store()
        case = store["sovereign_cases"][case_id]
        eligible_ids = audit["eligible_claim_ids"]
        case["claim_ids"] = list(eligible_ids)
        case["witness_count"] = len(eligible_ids)
        case["influence_audit_id"] = audit["audit_id"]
        case["quarantined_claim_ids"] = audit["quarantined_claim_ids"]
        if len(eligible_ids) >= OPENING_QUORUM:
            claims = [store["claims"][claim_id] for claim_id in eligible_ids]
            case["recommendation"] = self._recommend_case(claims)
        self._write_json(self.plural_witness_path, store)
        decision_id = super().janus_sovereign_decide(case_id)
        store = self._plural_store()
        decision = store["sovereign_decisions"][decision_id]
        decision["sovereign_capability_bound"] = True
        decision["sovereign_key_id"] = capability["key_id"] if capability else None
        decision["claimant_confidence_used"] = False
        decision["confidence_source"] = "evidence_assessment"
        decision["authority_event_chain_head"] = store["authority_events"][-1]["event_hash"] if store["authority_events"] else None
        self._append_authority_event(
            store,
            event_type="SOVEREIGN_DECISION_RECORDED",
            actor=JANUS_SOVEREIGN,
            subject_id=case_id,
            payload={"decision_id": decision_id, "ruling": decision["ruling"]},
        )
        self._write_json(self.plural_witness_path, store)
        return decision_id

    def verify_bound_authority_state(self) -> tuple[bool, int, str | None]:
        base_valid, _count, error = self.verify_unbought_voice_state()
        if not base_valid:
            return False, 0, error
        store = self._plural_store()
        required = self._default_plural_store()["invariants"]
        for key, expected in required.items():
            if store.get("invariants", {}).get(key) is not expected:
                return False, 0, f"bound authority invariant mismatch: {key}"
        previous = "GENESIS"
        verified = 0
        for event in store["authority_events"]:
            if event.get("previous_hash") != previous:
                return False, verified, "authority event chain previous_hash mismatch"
            material = copy.deepcopy(event)
            event_hash = material.pop("event_hash", None)
            if event_hash != sha256_canonical(material):
                return False, verified, "authority event hash mismatch"
            previous = event_hash
            verified += 1
        for account_id, account in store["influence_accounts"].items():
            if account.get("provider_signature_verified"):
                attestation = store["provider_attestations_v179"].get(account.get("provider_attestation_id"))
                if not isinstance(attestation, dict):
                    return False, verified, f"missing provider attestation: {account_id}"
                key = store["trusted_provider_keys"].get(f"{attestation.get('provider_id')}:{attestation.get('key_id')}")
                if not isinstance(key, dict) or not verify_signed_payload(attestation, key["public_key_b64"]):
                    return False, verified, f"invalid provider signature: {account_id}"
        return True, verified, None

    def bound_authority_state(self) -> dict[str, Any]:
        store = self._plural_store()
        valid, verified, error = self.verify_bound_authority_state()
        return {
            "runtime_version": __version__,
            "trusted_provider_key_count": len(store["trusted_provider_keys"]),
            "trusted_sovereign_key_count": len(store["trusted_sovereign_keys"]),
            "provider_attestation_count": len(store["provider_attestations_v179"]),
            "delegation_count": len(store["attestation_delegations"]),
            "assessment_count": len(store["evidence_assessments"]),
            "authority_event_count": len(store["authority_events"]),
            "consumed_nonce_count": len(store["consumed_nonces"]),
            "reactive_reaudit_count": len(store["reactive_reaudits"]),
            "verified_authority_events": verified,
            "valid": valid,
            "error": error,
            "private_keys_persisted": False,
        }

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        state["bound_authority_version"] = __version__
        state["bound_authority_law"] = (
            "Янус проверяет не имя власти, а подписанное происхождение полномочия, "
            "его область, срок, одноразовый nonce и неизменяемую историю решений."
        )
        state["bound_authority_integrity"] = self.bound_authority_state()
        return state
