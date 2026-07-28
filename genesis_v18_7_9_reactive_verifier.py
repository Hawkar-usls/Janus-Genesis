# -*- coding: utf-8 -*-
"""Integrity verifier for living authority after revocation and reopening.

A revoked or retrospectively compromised key no longer grants current authority,
but its old Ed25519 signature remains historical evidence. State integrity and
current eligibility are therefore verified as separate dimensions.

A reactive low-quorum case must also prove that it genuinely opened from an
audited independent quorum. Three arbitrary submitted IDs are never enough.
"""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_7 import OPENING_QUORUM
from genesis_v18_7_9 import _parse_time, sha256_canonical, verify_signed_payload
from genesis_v18_7_9_persistence import (
    REACTIVE_REOPENED_STATUS,
    signed_provider_payload,
)

OPENING_AUDIT_REASON = "unbought voice audit applied before quorum"


class ReactiveBoundAuthorityVerifierMixin:
    """Verify immutable signatures and evidenced reactive reopenings."""

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

    @staticmethod
    def _verify_reactive_reopening(
        store: dict[str, Any],
        case_id: str,
        case: dict[str, Any],
    ) -> str | None:
        claim_ids = list(case.get("claim_ids", []))
        if case.get("status") != REACTIVE_REOPENED_STATUS:
            return f"case lacks opening quorum: {case_id}"
        if case.get("janus_decision_id") is not None:
            return f"reopened case retains active sovereign decision: {case_id}"
        if case.get("influence_sensitive") is not True:
            return f"reopened low-quorum case is not influence-sensitive: {case_id}"
        if int(case.get("witness_count", -1)) != len(claim_ids):
            return f"reopened case witness count mismatch: {case_id}"
        if len(claim_ids) != len(set(claim_ids)):
            return f"reopened case repeats eligible claims: {case_id}"
        if any(claim_id not in store.get("claims", {}) for claim_id in claim_ids):
            return f"reopened case references missing claim: {case_id}"

        submitted = list(case.get("submitted_claim_ids", []))
        opening_entries = [
            item
            for item in case.get("history", [])
            if isinstance(item, dict)
            and item.get("reason") == OPENING_AUDIT_REASON
            and item.get("audit_id")
        ]
        if not opening_entries:
            return f"reopened case lacks historical opening audit provenance: {case_id}"
        opening_audit_id = opening_entries[0]["audit_id"]
        opening_audit = store.get("influence_audits", {}).get(opening_audit_id)
        if not isinstance(opening_audit, dict):
            return f"reopened case opening audit is missing: {case_id}"
        opening_eligible = set(opening_audit.get("eligible_claim_ids", []))
        if len(opening_eligible) < OPENING_QUORUM:
            return f"reopened case never had three historically eligible voices: {case_id}"
        if int(opening_audit.get("independent_voice_count", -1)) < OPENING_QUORUM:
            return f"reopened case opening audit lacked independent quorum: {case_id}"
        if not opening_eligible.issubset(set(submitted)):
            return f"reopened case opening audit is outside submitted field: {case_id}"
        if len(set(case.get("voice_scopes", []))) < OPENING_QUORUM:
            return f"reopened case lacks preserved opening voice scopes: {case_id}"
        if int(case.get("opening_quorum", -1)) != OPENING_QUORUM:
            return f"reopened case opening quorum contract changed: {case_id}"

        audit_id = case.get("influence_audit_id")
        audit = store.get("influence_audits", {}).get(audit_id)
        if not isinstance(audit, dict):
            return f"reopened case lacks current influence audit: {case_id}"
        if set(audit.get("eligible_claim_ids", [])) != set(claim_ids):
            return f"reopened case does not match current eligible audit: {case_id}"
        if set(audit.get("submitted_claim_ids", [])) != set(submitted):
            return f"reopened case audit changed submitted field: {case_id}"
        reopening_history = [
            item
            for item in case.get("history", [])
            if isinstance(item, dict)
            and item.get("status") == REACTIVE_REOPENED_STATUS
        ]
        if not reopening_history:
            return f"reopened case lacks append-only reopening provenance: {case_id}"
        latest = reopening_history[-1]
        if latest.get("audit_id") != audit_id or not latest.get("reason"):
            return f"reopened case provenance lacks audit or reason: {case_id}"
        return None

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
