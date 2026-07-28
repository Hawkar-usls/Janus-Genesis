# -*- coding: utf-8 -*-
"""Integrity verifier for living authority after revocation and reopening.

A revoked or retrospectively compromised key no longer grants current authority,
but its old Ed25519 signature remains historical evidence. State integrity and
current eligibility are therefore verified as separate dimensions.
"""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_9 import _parse_time, sha256_canonical, verify_signed_payload
from genesis_v18_7_9_persistence import signed_provider_payload


class ReactiveBoundAuthorityVerifierMixin:
    """Verify immutable signatures without resurrecting revoked authority."""

    @staticmethod
    def _historical_provider_signature_integrity(
        store: dict[str, Any],
        attestation: dict[str, Any],
    ) -> tuple[bool, str | None]:
        signed = signed_provider_payload(attestation)
        provider_id = str(signed.get("provider_id", ""))
        key_id = str(signed.get("key_id", ""))
        key = store.get("trusted_provider_keys", {}).get(f"{provider_id}:{key_id}")
        if not isinstance(key, dict):
            return False, "UNKNOWN_PROVIDER_KEY"
        if not verify_signed_payload(signed, key.get("public_key_b64", "")):
            return False, "INVALID_SIGNATURE"
        try:
            issued = _parse_time(signed.get("issued_at"))
            valid_from = _parse_time(key.get("valid_from"))
            valid_until = _parse_time(key.get("valid_until"))
        except ValueError:
            return False, "INVALID_HISTORICAL_TIME"
        if not valid_from <= issued < valid_until:
            return False, "SIGNATURE_OUTSIDE_REGISTERED_KEY_LIFETIME"
        return True, None

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
            signature_valid, signature_error = self._historical_provider_signature_integrity(
                store,
                attestation,
            )
            if not signature_valid:
                return False, verified, (
                    f"invalid provider signature history: {account_id}: {signature_error}"
                )
        return True, verified, None
