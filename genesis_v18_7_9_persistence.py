# -*- coding: utf-8 -*-
"""Persistence and signed-envelope adapter for Genesis v18.7.9.

The cryptographic payload remains byte-logically unchanged after verification;
local verification metadata is excluded from signature material. Provider nonce
consumption is persisted across the historical v18.7.8 account-registration
compatibility call. The same signed domain is used before and after portable
roundtrip verification.
"""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from genesis_v18_7_9 import (
    PROVIDER_ATTESTATION_SCHEMA,
    BoundAuthorityMixin,
    _iso_utc,
    _window_valid,
    sha256_canonical,
    verify_signed_payload,
)

LOCAL_ATTESTATION_METADATA = {
    "attestation_id",
    "signature_verified",
    "private_key_persisted",
}


def signed_provider_payload(attestation: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in attestation.items()
        if key not in LOCAL_ATTESTATION_METADATA
    }


class BoundAuthorityPersistenceMixin:
    """Keep signature material immutable and nonce state durable."""

    @staticmethod
    def _verify_provider_attestation(
        store: dict[str, Any],
        attestation: dict[str, Any],
        *,
        at_time: datetime | str | None = None,
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        signed = signed_provider_payload(attestation)
        if signed.get("schema") != PROVIDER_ATTESTATION_SCHEMA:
            return False, "UNSUPPORTED_PROVIDER_ATTESTATION_SCHEMA", None
        provider_id = str(signed.get("provider_id", ""))
        key_id = str(signed.get("key_id", ""))
        key_record = store["trusted_provider_keys"].get(f"{provider_id}:{key_id}")
        if not isinstance(key_record, dict):
            return False, "UNKNOWN_PROVIDER_KEY", None
        window_valid, window_error = _window_valid(
            signed.get("issued_at"),
            signed.get("expires_at"),
            at_time=at_time,
        )
        if not window_valid:
            return False, window_error, key_record
        key_valid, key_error = BoundAuthorityMixin._key_status(
            key_record,
            at_time=at_time,
            signed_at=signed.get("issued_at"),
        )
        if not key_valid:
            return False, key_error, key_record
        if not verify_signed_payload(signed, key_record["public_key_b64"]):
            return False, "INVALID_SIGNATURE", key_record
        return True, None, key_record

    def register_influence_account(
        self,
        account_id: str,
        *,
        identity_proof: str,
        controller_proof: str | None = None,
        provider_attestation: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not isinstance(provider_attestation, dict):
            return super().register_influence_account(
                account_id,
                identity_proof=identity_proof,
                controller_proof=controller_proof,
                provider_attestation=provider_attestation,
                **kwargs,
            )
        provider_id = str(provider_attestation.get("provider_id", ""))
        nonce = str(provider_attestation.get("nonce", ""))
        nonce_key = self._nonce_key("provider_attestation", provider_id, nonce)
        before = self._plural_store()
        if nonce_key in before["consumed_nonces"]:
            raise ValueError("REPLAYED")
        result = super().register_influence_account(
            account_id,
            identity_proof=identity_proof,
            controller_proof=controller_proof,
            provider_attestation=provider_attestation,
            **kwargs,
        )
        store = self._plural_store()
        store["consumed_nonces"].setdefault(
            nonce_key,
            {
                "kind": "provider_attestation",
                "issuer": provider_id,
                "subject_id": str(account_id),
                "consumed_at": _iso_utc(),
            },
        )
        self._write_json(self.plural_witness_path, store)
        return result

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
            if not account.get("provider_signature_verified"):
                continue
            attestation = store["provider_attestations_v179"].get(
                account.get("provider_attestation_id")
            )
            if not isinstance(attestation, dict):
                return False, verified, f"missing provider attestation: {account_id}"
            valid, signature_error, _key = self._verify_provider_attestation(
                store,
                attestation,
            )
            if not valid:
                return False, verified, (
                    f"invalid provider signature: {account_id}"
                    if signature_error == "INVALID_SIGNATURE"
                    else f"invalid provider authority: {account_id}: {signature_error}"
                )
        return True, verified, None
