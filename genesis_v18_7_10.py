# -*- coding: utf-8 -*-
"""Genesis v18.7.10 — The Bound Assessor and the I0 Discipline.

This layer binds evidence assessment to signed, scoped assessor authority and
imports the epistemic controls of JANUS I0 without importing mining behavior:

- frozen constitutional policy instead of a mutable hidden rule;
- fresh audit boundaries and runtime sentinels;
- fully isolated counterfactual mirror worlds;
- conservative Butterfly Witness verdicts;
- proofpack generation with privacy boundaries;
- separation of a Free Other's life from a relationship with the player;
- a persistent long-life sandbox for professions, items and voluntary trade.

Free Others remain narrative simulations. Runtime agency contracts are not
claims of consciousness or personhood.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from genesis_v18_models import WorldResult
from genesis_v18_7_8 import _sha256_text
from genesis_v18_7_9 import (
    BoundAuthorityMixin,
    _b64decode,
    _iso_utc,
    _parse_time,
    _window_valid,
    canonical_json_bytes,
    sha256_canonical,
    sign_payload,
    verify_signed_payload,
)

__version__ = "18.7.10"
SOURCE = "janus_genesis_v18_7_10"
PLAYABLE_SENTINEL = "GENESIS_V18_7_10_BOUND_ASSESSOR_I0"

ROOT_MANIFEST_SCHEMA = "janus.root_governance_manifest.v1"
ASSESSOR_ASSESSMENT_SCHEMA = "janus.evidence_assessment.v2"
CONFIDENCE_POLICY_SCHEMA = "janus.confidence_policy.v1"
I0_AUDIT_SCHEMA = "janus.genesis.i0_lived_audit.v1"
COUNTERFACTUAL_SCHEMA = "janus.genesis.unrealized_mirror.v1"
SOCIAL_RUPTURE_SCHEMA = "janus.genesis.social_rupture.v1"
SANDBOX_SCHEMA = "janus.genesis.long_life_sandbox.v1"

SIGNED_OBSERVATION_COMPONENTS = (
    "source_reliability",
    "evidence_integrity",
    "method_reliability",
    "temporal_relevance",
)
FORBIDDEN_SELF_ASSIGNED_COMPONENTS = (
    "assessor_competence",
    "independent_corroboration",
)

DEFAULT_CONFIDENCE_POLICY: dict[str, Any] = {
    "schema": CONFIDENCE_POLICY_SCHEMA,
    "policy_id": "genesis-confidence-policy",
    "policy_version": "18.7.10",
    "formula": "weighted_arithmetic_mean_v1",
    "weights": {
        "source_reliability": 1.0,
        "evidence_integrity": 1.25,
        "method_reliability": 1.0,
        "temporal_relevance": 0.75,
        "assessor_competence": 1.25,
        "independent_corroboration": 1.25,
    },
    "limits": {
        "minimum": 0.0,
        "maximum": 1.0,
        "missing_component": "reject",
    },
    "claimant_stated_confidence_used": False,
    "assessor_self_competence_used": False,
    "corroboration_is_system_computed": True,
}
DEFAULT_POLICY_SHA256 = sha256_canonical(DEFAULT_CONFIDENCE_POLICY)

FROZEN_CONSTITUTION: dict[str, Any] = {
    "schema": "janus.genesis.frozen_constitution.v1",
    "version": "18.7.10",
    "invariants": {
        "silence_is_not_consent": True,
        "goodness_does_not_purchase_relationship": True,
        "free_other_may_refuse": True,
        "free_other_may_leave": True,
        "free_other_life_is_not_relationship_life": True,
        "chronicle_is_append_only_hash_chain": True,
        "canonical_json_is_signed": True,
        "private_keys_are_never_persisted": True,
        "janus_rules_record_not_soul": True,
        "love_may_not_be_used_as_coercion": True,
        "counterfactual_mirrors_may_not_mutate_canon": True,
    },
    "law": (
        "JANUS MAY REMEMBER A LOVE WITHOUT ENSLAVING IT. "
        "JANUS MAY RECORD A DEPARTURE WITHOUT ERASING THE ONE WHO LEFT."
    ),
}
FROZEN_CONSTITUTION_SHA256 = sha256_canonical(FROZEN_CONSTITUTION)

LOGGER = logging.getLogger("JANUS")


def _clamp(value: float | int, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _normalized_hashes(values: Iterable[str]) -> list[str]:
    out = sorted({str(value).strip().lower() for value in values if str(value).strip()})
    for value in out:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError(f"evidence hash is not lowercase SHA-256: {value!r}")
    return out


def build_assessor_attestation(
    *,
    assessment_id: str,
    assessor_id: str,
    key_id: str,
    claim_id: str,
    subject_scope_id: str | None,
    method_id: str,
    method_version: str,
    policy_id: str,
    policy_version: str,
    policy_sha256: str,
    evidence_hashes: Iterable[str],
    components: dict[str, float],
    explanation: str,
    nonce: str,
    issued_at: datetime | str,
    expires_at: datetime | str,
    private_key_b64: str,
    supersedes_assessment_id: str | None = None,
) -> dict[str, Any]:
    """Build a canonical signed assessment observation.

    Competence and independent corroboration are intentionally absent: they are
    computed by Genesis from the credential registry and current evidence graph.
    """
    forbidden = sorted(set(components) & set(FORBIDDEN_SELF_ASSIGNED_COMPONENTS))
    if forbidden:
        raise ValueError(
            "assessor may not self-assign: " + ", ".join(forbidden)
        )
    normalized: dict[str, float] = {}
    for name in SIGNED_OBSERVATION_COMPONENTS:
        if name not in components:
            raise ValueError(f"missing signed observation component: {name}")
        normalized[name] = round(_clamp(components[name]), 6)
    unknown = sorted(set(components) - set(SIGNED_OBSERVATION_COMPONENTS))
    if unknown:
        raise ValueError("unknown signed observation components: " + ", ".join(unknown))
    evidence = _normalized_hashes(evidence_hashes)
    if not evidence:
        raise ValueError("assessment requires at least one evidence SHA-256")
    if not str(explanation).strip():
        raise ValueError("assessment requires an explanation")
    payload = {
        "schema": ASSESSOR_ASSESSMENT_SCHEMA,
        "assessment_id": str(assessment_id),
        "assessor_id": str(assessor_id),
        "key_id": str(key_id),
        "scope": "evidence_assessment",
        "claim_id": str(claim_id),
        "subject_scope_id": None if subject_scope_id is None else str(subject_scope_id),
        "method_id": str(method_id),
        "method_version": str(method_version),
        "policy_id": str(policy_id),
        "policy_version": str(policy_version),
        "policy_sha256": str(policy_sha256),
        "evidence_hashes": evidence,
        "evidence_set_sha256": sha256_canonical(evidence),
        "components": normalized,
        "explanation_sha256": _sha256_text(str(explanation)),
        "nonce": str(nonce),
        "issued_at": _iso_utc(issued_at),
        "expires_at": _iso_utc(expires_at),
        "supersedes_assessment_id": (
            None if supersedes_assessment_id is None else str(supersedes_assessment_id)
        ),
        "algorithm": "Ed25519",
    }
    return sign_payload(payload, private_key_b64)


def build_root_governance_manifest(
    *,
    root_id: str,
    key_id: str,
    operations: list[dict[str, Any]],
    nonce: str,
    issued_at: datetime | str,
    expires_at: datetime | str,
    private_key_b64: str,
) -> dict[str, Any]:
    payload = {
        "schema": ROOT_MANIFEST_SCHEMA,
        "root_id": str(root_id),
        "key_id": str(key_id),
        "operations": copy.deepcopy(operations),
        "nonce": str(nonce),
        "issued_at": _iso_utc(issued_at),
        "expires_at": _iso_utc(expires_at),
        "algorithm": "Ed25519",
    }
    payload["operations_sha256"] = sha256_canonical(payload["operations"])
    return sign_payload(payload, private_key_b64)


class BoundAssessorI0Mixin(BoundAuthorityMixin):
    """Bind the assessor, freeze the policy and import I0 audit discipline."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.i0_audit_path = self.memory.root / "i0_audit_v18_7_10.json"
        self.sandbox_path = self.memory.root / "sandbox_v18_7_10.json"

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        store = BoundAuthorityMixin._default_plural_store()
        store["runtime_version"] = __version__
        store.setdefault("trusted_root_keys", {})
        store.setdefault("trusted_assessor_keys", {})
        store.setdefault("assessor_credentials", {})
        store.setdefault("confidence_policies", {
            DEFAULT_POLICY_SHA256: copy.deepcopy(DEFAULT_CONFIDENCE_POLICY)
        })
        store.setdefault("signed_assessments_v1810", {})
        store.setdefault("assessment_events", [])
        store.setdefault("assessment_semantic_index", {})
        store.setdefault("security_events_v1810", [])
        store.setdefault("consumed_nonces_v1810", {})
        store.setdefault("root_manifests", {})
        store.setdefault("frozen_constitution", {
            "payload": copy.deepcopy(FROZEN_CONSTITUTION),
            "sha256": FROZEN_CONSTITUTION_SHA256,
        })
        store["invariants"].update({
            "assessor_must_sign_observations": True,
            "assessor_cannot_assign_own_competence": True,
            "corroboration_is_system_computed": True,
            "assessment_policy_is_versioned_and_hash_bound": True,
            "semantic_replay_requires_supersession": True,
            "root_bootstrap_is_disabled_in_ordinary_runtime": True,
            "assessor_authority_changes_reopen_affected_cases": True,
            "frozen_constitution_hash_bound": True,
            "counterfactual_mirrors_are_isolated": True,
            "actor_life_is_not_relationship_life": True,
        })
        return store

    def _plural_store(self) -> dict[str, Any]:
        store = super()._plural_store()
        defaults = self._default_plural_store()
        store["runtime_version"] = __version__
        for key in (
            "trusted_root_keys",
            "trusted_assessor_keys",
            "assessor_credentials",
            "signed_assessments_v1810",
            "assessment_events",
            "assessment_semantic_index",
            "security_events_v1810",
            "consumed_nonces_v1810",
            "root_manifests",
        ):
            store.setdefault(key, copy.deepcopy(defaults[key]))
        store.setdefault("confidence_policies", copy.deepcopy(defaults["confidence_policies"]))
        store.setdefault("frozen_constitution", copy.deepcopy(defaults["frozen_constitution"]))
        store.setdefault("invariants", {}).update(defaults["invariants"])
        return store

    # ------------------------------------------------------------------
    # Frozen constitution and root governance
    # ------------------------------------------------------------------

    def frozen_constitution_state(self) -> dict[str, Any]:
        store = self._plural_store()
        record = store["frozen_constitution"]
        valid = (
            record.get("sha256") == FROZEN_CONSTITUTION_SHA256
            and sha256_canonical(record.get("payload")) == FROZEN_CONSTITUTION_SHA256
        )
        return {
            "valid": valid,
            "sha256": record.get("sha256"),
            "expected_sha256": FROZEN_CONSTITUTION_SHA256,
            "wire_change_required": not valid,
            "sentinel": PLAYABLE_SENTINEL,
        }

    def bootstrap_offline_root_key(
        self,
        root_id: str,
        *,
        key_id: str,
        public_key_b64: str,
        valid_from: datetime | str,
        valid_until: datetime | str,
        ceremony_receipt: str,
    ) -> dict[str, Any]:
        """One-time offline bootstrap, disabled unless explicitly unlocked.

        The environment flag is an installation boundary, not a network API.
        Production deployments should replace it with HSM/offline quorum custody.
        """
        if os.environ.get("GENESIS_OFFLINE_ROOT_BOOTSTRAP") != "1":
            raise PermissionError("OFFLINE_ROOT_BOOTSTRAP_LOCKED")
        if len(str(ceremony_receipt).strip()) < 16:
            raise ValueError("offline ceremony receipt is required")
        store = self._plural_store()
        if store["trusted_root_keys"]:
            raise PermissionError("ROOT_ALREADY_BOOTSTRAPPED")
        record = self._key_record(
            owner_id=str(root_id),
            key_id=str(key_id),
            public_key_b64=str(public_key_b64),
            valid_from=valid_from,
            valid_until=valid_until,
        )
        record["ceremony_receipt_sha256"] = _sha256_text(str(ceremony_receipt))
        composite = f"{root_id}:{key_id}"
        store["trusted_root_keys"][composite] = record
        self._append_authority_event(
            store,
            event_type="ROOT_KEY_BOOTSTRAPPED_OFFLINE",
            actor="OFFLINE_ROOT_CEREMONY",
            subject_id=composite,
            payload={
                "public_key_sha256": _sha256_text(public_key_b64),
                "ceremony_receipt_sha256": record["ceremony_receipt_sha256"],
            },
        )
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(record)

    def _consume_v1810_nonce(
        self,
        store: dict[str, Any],
        *,
        namespace: str,
        nonce: str,
        payload_sha256: str,
    ) -> None:
        nonce = str(nonce).strip()
        if len(nonce) < 8:
            raise ValueError("nonce is missing or too short")
        key = f"{namespace}:{nonce}"
        if key in store["consumed_nonces_v1810"]:
            raise ValueError("REPLAYED")
        store["consumed_nonces_v1810"][key] = {
            "namespace": namespace,
            "nonce_sha256": _sha256_text(nonce),
            "payload_sha256": payload_sha256,
            "consumed_at": _iso_utc(),
        }

    def apply_root_governance_manifest(
        self,
        manifest: dict[str, Any],
        *,
        at_time: datetime | str | None = None,
    ) -> str:
        store = self._plural_store()
        if manifest.get("schema") != ROOT_MANIFEST_SCHEMA:
            raise ValueError("ROOT_GOVERNANCE_MANIFEST_REQUIRED")
        composite = f"{manifest.get('root_id')}:{manifest.get('key_id')}"
        root_key = store["trusted_root_keys"].get(composite)
        if not isinstance(root_key, dict):
            raise ValueError("UNKNOWN_ROOT_KEY")
        valid_key, key_error = self._key_status(
            root_key, at_time=at_time, signed_at=manifest.get("issued_at")
        )
        if not valid_key:
            raise ValueError(key_error or "ROOT_KEY_INVALID")
        if not verify_signed_payload(manifest, root_key["public_key_b64"]):
            raise ValueError("INVALID_ROOT_SIGNATURE")
        valid_window, window_error = _window_valid(
            manifest.get("issued_at"), manifest.get("expires_at"), at_time=at_time
        )
        if not valid_window:
            raise ValueError(window_error or "ROOT_MANIFEST_EXPIRED")
        operations = manifest.get("operations")
        if not isinstance(operations, list):
            raise ValueError("root operations must be a list")
        if manifest.get("operations_sha256") != sha256_canonical(operations):
            raise ValueError("ROOT_OPERATIONS_HASH_MISMATCH")
        manifest_id = self._stable_id("root-manifest", sha256_canonical(manifest))
        self._consume_v1810_nonce(
            store,
            namespace="root-governance",
            nonce=str(manifest.get("nonce")),
            payload_sha256=sha256_canonical(manifest),
        )
        for operation in operations:
            self._apply_root_operation(store, operation)
        store["root_manifests"][manifest_id] = copy.deepcopy(manifest)
        self._append_authority_event(
            store,
            event_type="ROOT_GOVERNANCE_MANIFEST_APPLIED",
            actor=str(manifest.get("root_id")),
            subject_id=manifest_id,
            payload={
                "operation_count": len(operations),
                "operations_sha256": manifest["operations_sha256"],
            },
        )
        self._write_json(self.plural_witness_path, store)
        return manifest_id

    def _apply_root_operation(self, store: dict[str, Any], operation: dict[str, Any]) -> None:
        if not isinstance(operation, dict):
            raise ValueError("root operation must be an object")
        kind = str(operation.get("operation"))
        if kind == "TRUST_ASSESSOR_KEY":
            assessor_id = str(operation["assessor_id"])
            key_id = str(operation["key_id"])
            record = self._key_record(
                owner_id=assessor_id,
                key_id=key_id,
                public_key_b64=str(operation["public_key_b64"]),
                valid_from=operation["valid_from"],
                valid_until=operation["valid_until"],
            )
            store["trusted_assessor_keys"][f"{assessor_id}:{key_id}"] = record
            return
        if kind == "SET_ASSESSOR_CREDENTIAL":
            assessor_id = str(operation["assessor_id"])
            credential_id = str(operation["credential_id"])
            allowed_methods = sorted(set(map(str, operation.get("allowed_methods", []))))
            if not allowed_methods:
                raise ValueError("assessor credential requires allowed_methods")
            competence = {
                str(scope): round(_clamp(value), 6)
                for scope, value in dict(operation.get("competence_by_scope", {})).items()
            }
            if not competence:
                raise ValueError("assessor credential requires competence_by_scope")
            max_authority = {
                name: round(_clamp(dict(operation.get("max_component_authority", {})).get(name, 1.0)), 6)
                for name in SIGNED_OBSERVATION_COMPONENTS
            }
            store["assessor_credentials"][credential_id] = {
                "credential_id": credential_id,
                "assessor_id": assessor_id,
                "controller_id": str(operation.get("controller_id") or assessor_id),
                "allowed_methods": allowed_methods,
                "allowed_subject_scopes": sorted(
                    set(map(str, operation.get("allowed_subject_scopes", ["*"])))
                ),
                "competence_by_scope": competence,
                "max_component_authority": max_authority,
                "may_assess_own_sources": bool(operation.get("may_assess_own_sources", False)),
                "valid_from": _iso_utc(operation["valid_from"]),
                "valid_until": _iso_utc(operation["valid_until"]),
                "revoked_at": None,
                "credential_version": str(operation.get("credential_version", "1")),
            }
            return
        if kind == "INSTALL_CONFIDENCE_POLICY":
            policy = copy.deepcopy(operation["policy"])
            digest = sha256_canonical(policy)
            if operation.get("policy_sha256") != digest:
                raise ValueError("POLICY_HASH_MISMATCH")
            if policy.get("schema") != CONFIDENCE_POLICY_SCHEMA:
                raise ValueError("unsupported confidence policy schema")
            store["confidence_policies"][digest] = policy
            return
        if kind == "REVOKE_ASSESSOR_KEY":
            composite = f"{operation['assessor_id']}:{operation['key_id']}"
            record = store["trusted_assessor_keys"].get(composite)
            if not isinstance(record, dict):
                raise KeyError(composite)
            record["revoked_at"] = _iso_utc(operation.get("revoked_at"))
            record["revocation_reason"] = str(operation.get("reason") or "root governance")
            self._invalidate_assessor_outputs(
                store,
                assessor_id=str(operation["assessor_id"]),
                key_id=str(operation["key_id"]),
                reason="ASSESSOR_KEY_REVOKED",
            )
            return
        if kind == "REVOKE_ASSESSOR_CREDENTIAL":
            credential = store["assessor_credentials"].get(str(operation["credential_id"]))
            if not isinstance(credential, dict):
                raise KeyError(str(operation["credential_id"]))
            credential["revoked_at"] = _iso_utc(operation.get("revoked_at"))
            self._invalidate_assessor_outputs(
                store,
                assessor_id=str(credential["assessor_id"]),
                key_id=None,
                reason="ASSESSOR_CREDENTIAL_REVOKED",
            )
            return
        raise ValueError(f"unsupported root operation: {kind}")

    # ------------------------------------------------------------------
    # Bound assessor
    # ------------------------------------------------------------------

    def _security_event(
        self,
        store: dict[str, Any],
        *,
        event_type: str,
        assessor_id: str | None,
        key_id: str | None,
        claim_id: str | None,
        payload: dict[str, Any],
    ) -> str:
        safe_payload = {
            "assessor_id": assessor_id,
            "key_id": key_id,
            "claim_id": claim_id,
            **copy.deepcopy(payload),
        }
        event = {
            "schema": "janus.security_event.v1",
            "event_type": event_type,
            "timestamp": _iso_utc(),
            "payload": safe_payload,
            "previous_hash": (
                store["security_events_v1810"][-1]["event_hash"]
                if store["security_events_v1810"]
                else "0" * 64
            ),
        }
        event["event_hash"] = sha256_canonical(event)
        store["security_events_v1810"].append(event)
        LOGGER.error(
            "JANUS_SECURITY: %s assessor=%s key=%s claim=%s payload_sha256=%s",
            event_type,
            assessor_id,
            key_id,
            claim_id,
            sha256_canonical(safe_payload),
        )
        return event["event_hash"]

    def _credential_for_assessment(
        self,
        store: dict[str, Any],
        *,
        assessor_id: str,
        method_id: str,
        subject_scope_id: str | None,
        at_time: datetime | str | None,
    ) -> dict[str, Any]:
        now = _parse_time(_iso_utc(at_time))
        candidates = []
        for credential in store["assessor_credentials"].values():
            if credential.get("assessor_id") != assessor_id:
                continue
            if method_id not in credential.get("allowed_methods", []):
                continue
            scopes = credential.get("allowed_subject_scopes", [])
            if "*" not in scopes and str(subject_scope_id) not in scopes:
                continue
            if now < _parse_time(credential["valid_from"]) or now >= _parse_time(credential["valid_until"]):
                continue
            revoked = credential.get("revoked_at")
            if revoked and now >= _parse_time(revoked):
                continue
            candidates.append(credential)
        if not candidates:
            raise ValueError("ASSESSOR_CREDENTIAL_NOT_AUTHORIZED")
        return sorted(candidates, key=lambda item: item["credential_id"])[0]

    def _system_corroboration(
        self,
        store: dict[str, Any],
        claim: dict[str, Any],
    ) -> float:
        scope_id = claim.get("subject_scope_id")
        actor = self._claim_reader_id(claim)
        actor_account = store.get("influence_accounts", {}).get(actor or "", {})
        controller = actor_account.get("controller_cluster")
        distinct: set[str] = set()
        for candidate in store.get("claims", {}).values():
            if not isinstance(candidate, dict) or candidate.get("claim_id") == claim.get("claim_id"):
                continue
            if candidate.get("subject_scope_id") != scope_id:
                continue
            if not candidate.get("grounded"):
                continue
            other_actor = self._claim_reader_id(candidate)
            account = store.get("influence_accounts", {}).get(other_actor or "", {})
            other_controller = account.get("controller_cluster")
            if other_controller and other_controller != controller:
                distinct.add(str(other_controller))
            elif other_actor and other_actor != actor:
                distinct.add(f"actor:{other_actor}")
        return round(min(1.0, len(distinct) / 3.0), 6)

    @staticmethod
    def _policy_confidence(
        *,
        policy: dict[str, Any],
        observations: dict[str, float],
        competence: float,
        corroboration: float,
    ) -> float:
        values = {
            **observations,
            "assessor_competence": round(_clamp(competence), 6),
            "independent_corroboration": round(_clamp(corroboration), 6),
        }
        weights = dict(policy.get("weights", {}))
        numerator = 0.0
        denominator = 0.0
        for name, value in values.items():
            weight = float(weights.get(name, 0.0))
            numerator += _clamp(value) * weight
            denominator += weight
        if denominator <= 0:
            raise ValueError("confidence policy has no positive weights")
        return round(_clamp(numerator / denominator), 6)

    def record_evidence_assessment(
        self,
        claim_id: str,
        *,
        assessment: dict[str, Any] | None = None,
        at_time: datetime | str | None = None,
        **legacy: Any,
    ) -> str:
        if assessment is None:
            raise ValueError("SIGNED_ASSESSOR_ATTESTATION_REQUIRED")
        if legacy:
            raise ValueError("free assessor fields are forbidden in v18.7.10")
        store = self._plural_store()
        claim = store["claims"].get(claim_id)
        if not isinstance(claim, dict):
            raise KeyError(claim_id)
        if assessment.get("schema") != ASSESSOR_ASSESSMENT_SCHEMA:
            raise ValueError("SIGNED_ASSESSOR_ATTESTATION_REQUIRED")
        if str(assessment.get("claim_id")) != str(claim_id):
            raise ValueError("ASSESSMENT_CLAIM_BINDING_MISMATCH")
        forbidden = sorted(
            set(dict(assessment.get("components", {}))) & set(FORBIDDEN_SELF_ASSIGNED_COMPONENTS)
        )
        if forbidden:
            self._security_event(
                store,
                event_type="ASSESSOR_AUTHORITY_BREACH_ATTEMPT",
                assessor_id=str(assessment.get("assessor_id")),
                key_id=str(assessment.get("key_id")),
                claim_id=claim_id,
                payload={
                    "violation": "SELF_ASSIGNED_SYSTEM_COMPONENT",
                    "forbidden_components": forbidden,
                    "payload_sha256": sha256_canonical(assessment),
                },
            )
            self._write_json(self.plural_witness_path, store)
            raise ValueError("ASSESSOR_MAY_NOT_ASSIGN_SYSTEM_COMPONENTS")
        assessor_id = str(assessment.get("assessor_id"))
        key_id = str(assessment.get("key_id"))
        key_record = store["trusted_assessor_keys"].get(f"{assessor_id}:{key_id}")
        if not isinstance(key_record, dict):
            raise ValueError("UNKNOWN_ASSESSOR_KEY")
        key_valid, key_error = self._key_status(
            key_record, at_time=at_time, signed_at=assessment.get("issued_at")
        )
        if not key_valid:
            raise ValueError(key_error or "ASSESSOR_KEY_INVALID")
        if not verify_signed_payload(assessment, key_record["public_key_b64"]):
            raise ValueError("INVALID_ASSESSOR_SIGNATURE")
        valid_window, window_error = _window_valid(
            assessment.get("issued_at"), assessment.get("expires_at"), at_time=at_time
        )
        if not valid_window:
            raise ValueError(window_error or "ASSESSMENT_EXPIRED")
        evidence = _normalized_hashes(assessment.get("evidence_hashes", []))
        if assessment.get("evidence_set_sha256") != sha256_canonical(evidence):
            raise ValueError("EVIDENCE_SET_HASH_MISMATCH")
        subject_scope_id = claim.get("subject_scope_id")
        if assessment.get("subject_scope_id") != subject_scope_id:
            raise ValueError("ASSESSMENT_SUBJECT_SCOPE_MISMATCH")
        method_id = str(assessment.get("method_id"))
        credential = self._credential_for_assessment(
            store,
            assessor_id=assessor_id,
            method_id=method_id,
            subject_scope_id=subject_scope_id,
            at_time=at_time,
        )
        observations: dict[str, float] = {}
        raw_components = dict(assessment.get("components", {}))
        for name in SIGNED_OBSERVATION_COMPONENTS:
            if name not in raw_components:
                raise ValueError(f"missing signed observation component: {name}")
            value = round(_clamp(raw_components[name]), 6)
            maximum = float(credential["max_component_authority"].get(name, 1.0))
            if value > maximum:
                self._security_event(
                    store,
                    event_type="ASSESSOR_AUTHORITY_BREACH_ATTEMPT",
                    assessor_id=assessor_id,
                    key_id=key_id,
                    claim_id=claim_id,
                    payload={
                        "violation": "COMPONENT_AUTHORITY_EXCEEDED",
                        "component": name,
                        "attempted": value,
                        "maximum": maximum,
                        "payload_sha256": sha256_canonical(assessment),
                    },
                )
                self._write_json(self.plural_witness_path, store)
                raise ValueError("ASSESSOR_COMPONENT_AUTHORITY_EXCEEDED")
            observations[name] = value
        if set(raw_components) != set(SIGNED_OBSERVATION_COMPONENTS):
            raise ValueError("ASSESSMENT_COMPONENT_SET_INVALID")
        claim_actor = self._claim_reader_id(claim)
        claim_account = store.get("influence_accounts", {}).get(claim_actor or "", {})
        claim_controller = claim_account.get("controller_cluster")
        if (
            not credential.get("may_assess_own_sources")
            and claim_controller
            and claim_controller == credential.get("controller_id")
        ):
            self._security_event(
                store,
                event_type="ASSESSOR_AUTHORITY_BREACH_ATTEMPT",
                assessor_id=assessor_id,
                key_id=key_id,
                claim_id=claim_id,
                payload={
                    "violation": "CONFLICT_OF_INTEREST",
                    "controller_sha256": _sha256_text(str(claim_controller)),
                    "payload_sha256": sha256_canonical(assessment),
                },
            )
            self._write_json(self.plural_witness_path, store)
            raise ValueError("ASSESSOR_CONFLICT_OF_INTEREST")
        policy_sha = str(assessment.get("policy_sha256"))
        policy = store["confidence_policies"].get(policy_sha)
        if not isinstance(policy, dict):
            raise ValueError("UNKNOWN_CONFIDENCE_POLICY")
        if (
            assessment.get("policy_id") != policy.get("policy_id")
            or assessment.get("policy_version") != policy.get("policy_version")
            or sha256_canonical(policy) != policy_sha
        ):
            raise ValueError("CONFIDENCE_POLICY_BINDING_MISMATCH")
        scope_key = str(subject_scope_id) if subject_scope_id is not None else "*"
        competence_map = dict(credential.get("competence_by_scope", {}))
        competence = float(
            competence_map.get(scope_key, competence_map.get("*", 0.0))
        )
        corroboration = self._system_corroboration(store, claim)
        effective = self._policy_confidence(
            policy=policy,
            observations=observations,
            competence=competence,
            corroboration=corroboration,
        )
        semantic_key = sha256_canonical({
            "assessor_id": assessor_id,
            "claim_id": claim_id,
            "method_id": method_id,
            "evidence_set_sha256": assessment.get("evidence_set_sha256"),
            "policy_sha256": policy_sha,
        })
        prior_id = store["assessment_semantic_index"].get(semantic_key)
        supersedes = assessment.get("supersedes_assessment_id")
        if prior_id and supersedes != prior_id:
            raise ValueError("SEMANTIC_REPLAY_REQUIRES_SUPERSEDES")
        if supersedes:
            prior = store["signed_assessments_v1810"].get(str(supersedes))
            if not isinstance(prior, dict):
                raise ValueError("SUPERSEDED_ASSESSMENT_NOT_FOUND")
            prior["current_authority"] = False
            prior["superseded_by"] = str(assessment.get("assessment_id"))
        self._consume_v1810_nonce(
            store,
            namespace=f"assessor:{assessor_id}:{key_id}",
            nonce=str(assessment.get("nonce")),
            payload_sha256=sha256_canonical(assessment),
        )
        assessment_id = str(assessment.get("assessment_id"))
        if not assessment_id:
            raise ValueError("assessment_id is required")
        if assessment_id in store["signed_assessments_v1810"]:
            raise ValueError("ASSESSMENT_ID_ALREADY_EXISTS")
        record = copy.deepcopy(assessment)
        record.update({
            "signature_integrity": True,
            "current_authority": True,
            "credential_id": credential["credential_id"],
            "assessor_competence": round(_clamp(competence), 6),
            "independent_corroboration": corroboration,
            "effective_confidence": effective,
            "assessment_input_sha256": sha256_canonical({
                "claim_id": claim_id,
                "evidence_set_sha256": assessment["evidence_set_sha256"],
                "observations": observations,
                "competence": round(_clamp(competence), 6),
                "corroboration": corroboration,
                "policy_sha256": policy_sha,
            }),
            "private_key_persisted": False,
        })
        store["signed_assessments_v1810"][assessment_id] = record
        store["assessment_semantic_index"][semantic_key] = assessment_id
        claim["assessment_id"] = assessment_id
        claim["assessment_confidence"] = effective
        claim["confidence_authority"] = "signed_bound_assessor_policy"
        claim["assessment_policy_sha256"] = policy_sha
        claim["claimant_confidence_used"] = False
        self._append_assessment_event(
            store,
            event_type="SIGNED_ASSESSMENT_ACCEPTED",
            assessment_id=assessment_id,
            claim_id=claim_id,
            payload={
                "effective_confidence": effective,
                "policy_sha256": policy_sha,
                "assessment_input_sha256": record["assessment_input_sha256"],
                "supersedes_assessment_id": supersedes,
            },
        )
        self._append_authority_event(
            store,
            event_type="SIGNED_EVIDENCE_ASSESSMENT_RECORDED",
            actor=assessor_id,
            subject_id=claim_id,
            payload={
                "assessment_id": assessment_id,
                "effective_confidence": effective,
                "policy_sha256": policy_sha,
            },
        )
        self._write_json(self.plural_witness_path, store)
        return assessment_id

    def _append_assessment_event(
        self,
        store: dict[str, Any],
        *,
        event_type: str,
        assessment_id: str,
        claim_id: str,
        payload: dict[str, Any],
    ) -> str:
        previous = (
            store["assessment_events"][-1]["event_hash"]
            if store["assessment_events"]
            else "0" * 64
        )
        event = {
            "event_type": event_type,
            "assessment_id": assessment_id,
            "claim_id": claim_id,
            "timestamp": _iso_utc(),
            "previous_hash": previous,
            "payload": copy.deepcopy(payload),
        }
        event["event_hash"] = sha256_canonical(event)
        store["assessment_events"].append(event)
        return event["event_hash"]

    def _invalidate_assessor_outputs(
        self,
        store: dict[str, Any],
        *,
        assessor_id: str,
        key_id: str | None,
        reason: str,
    ) -> None:
        affected_claims: list[str] = []
        for record in store["signed_assessments_v1810"].values():
            if record.get("assessor_id") != assessor_id:
                continue
            if key_id is not None and record.get("key_id") != key_id:
                continue
            if not record.get("current_authority", True):
                continue
            record["current_authority"] = False
            record["authority_lost_reason"] = reason
            claim_id = str(record["claim_id"])
            claim = store.get("claims", {}).get(claim_id)
            if isinstance(claim, dict) and claim.get("assessment_id") == record.get("assessment_id"):
                claim["assessment_confidence"] = None
                claim["confidence_authority"] = "assessment_authority_revoked"
            affected_claims.append(claim_id)
            self._append_assessment_event(
                store,
                event_type="ASSESSMENT_AUTHORITY_REVOKED",
                assessment_id=str(record["assessment_id"]),
                claim_id=claim_id,
                payload={"reason": reason},
            )
        if affected_claims:
            self._reopen_cases_for_assessment_change(store, affected_claims, reason=reason)

    def _reopen_cases_for_assessment_change(
        self,
        store: dict[str, Any],
        claim_ids: Iterable[str],
        *,
        reason: str,
    ) -> None:
        affected = set(claim_ids)
        for case_id, case in store.get("sovereign_cases", {}).items():
            submitted = set(case.get("submitted_claim_ids", []))
            if not (submitted & affected):
                continue
            case["status"] = "CASE_REOPENED_DUE_TO_ASSESSOR_ELIGIBILITY_CHANGE"
            case["janus_decision_id"] = None
            case.setdefault("history", []).append({
                "event": "CASE_REOPENED_DUE_TO_ASSESSOR_ELIGIBILITY_CHANGE",
                "reason": reason,
                "affected_claim_ids": sorted(submitted & affected),
                "at": _iso_utc(),
            })
            self._append_authority_event(
                store,
                event_type="CASE_REOPENED_DUE_TO_ASSESSOR_ELIGIBILITY_CHANGE",
                actor="GENESIS.REACTIVE_ASSESSMENT",
                subject_id=str(case_id),
                payload={
                    "reason": reason,
                    "affected_claim_ids": sorted(submitted & affected),
                },
            )

    def verify_bound_assessor_state(self) -> tuple[bool, int, str | None]:
        store = self._plural_store()
        constitution = store.get("frozen_constitution", {})
        if constitution.get("sha256") != FROZEN_CONSTITUTION_SHA256:
            return False, 0, "frozen constitution hash mismatch"
        if sha256_canonical(constitution.get("payload")) != FROZEN_CONSTITUTION_SHA256:
            return False, 0, "frozen constitution payload changed"
        previous = "0" * 64
        for index, event in enumerate(store.get("assessment_events", []), 1):
            candidate = copy.deepcopy(event)
            event_hash = candidate.pop("event_hash", None)
            if candidate.get("previous_hash") != previous:
                return False, index - 1, f"assessment event chain broken at {index}"
            if event_hash != sha256_canonical(candidate):
                return False, index - 1, f"assessment event hash invalid at {index}"
            previous = str(event_hash)
        for assessment_id, record in store.get("signed_assessments_v1810", {}).items():
            if record.get("assessment_id") != assessment_id:
                return False, len(store["assessment_events"]), f"assessment id mismatch: {assessment_id}"
            key = store["trusted_assessor_keys"].get(
                f"{record.get('assessor_id')}:{record.get('key_id')}"
            )
            if not isinstance(key, dict):
                return False, len(store["assessment_events"]), f"missing assessor key: {assessment_id}"
            signed_payload = {
                key_name: copy.deepcopy(record[key_name])
                for key_name in (
                    "schema", "assessment_id", "assessor_id", "key_id", "scope",
                    "claim_id", "subject_scope_id", "method_id", "method_version",
                    "policy_id", "policy_version", "policy_sha256", "evidence_hashes",
                    "evidence_set_sha256", "components", "explanation_sha256", "nonce",
                    "issued_at", "expires_at", "supersedes_assessment_id", "algorithm",
                    "signature",
                )
                if key_name in record
            }
            if not verify_signed_payload(signed_payload, key["public_key_b64"]):
                return False, len(store["assessment_events"]), f"invalid historical assessment signature: {assessment_id}"
        return True, len(store.get("signed_assessments_v1810", {})), None

    # ------------------------------------------------------------------
    # I0 audit method: fresh boundaries, mirrors, Butterfly Witness
    # ------------------------------------------------------------------

    @staticmethod
    def _default_i0_audit_store() -> dict[str, Any]:
        return {
            "schema": I0_AUDIT_SCHEMA,
            "runtime_version": __version__,
            "sentinel": PLAYABLE_SENTINEL,
            "frozen_constitution_sha256": FROZEN_CONSTITUTION_SHA256,
            "audits": {},
            "mirror_archives": {},
            "butterfly_reports": {},
            "invariants": {
                "fresh_boundary_required": True,
                "mirror_is_fully_isolated": True,
                "mirror_never_mutates_canonical_chronicle": True,
                "one_event_is_not_a_law": True,
                "negative_results_are_preserved": True,
                "raw_private_dialogue_is_not_public_proofpack": True,
            },
        }

    def _i0_store(self) -> dict[str, Any]:
        store = self._read_json(self.i0_audit_path, self._default_i0_audit_store())
        if not isinstance(store, dict) or store.get("schema") != I0_AUDIT_SCHEMA:
            store = self._default_i0_audit_store()
        for key, value in self._default_i0_audit_store().items():
            store.setdefault(key, copy.deepcopy(value))
        return store

    def begin_lived_audit(
        self,
        player_id: str,
        *,
        label: str,
        git_commit: str,
        action_script_sha256: str,
    ) -> str:
        store = self._i0_store()
        audit_id = self._stable_id(
            "lived-audit", player_id, label, git_commit, action_script_sha256, _iso_utc()
        )
        chronicle_valid, chronicle_count, chronicle_error = self.memory.verify_chronicle()
        record = {
            "audit_id": audit_id,
            "player_id": player_id,
            "label": str(label)[:160],
            "runtime_version": __version__,
            "runtime_sentinel": PLAYABLE_SENTINEL,
            "git_commit": str(git_commit),
            "policy_sha256": DEFAULT_POLICY_SHA256,
            "frozen_constitution_sha256": FROZEN_CONSTITUTION_SHA256,
            "world_seed_fingerprint": self.free_other_state(player_id)["seed_fingerprint"],
            "fresh_boundary": {
                "created_at": _iso_utc(),
                "chronicle_valid": chronicle_valid,
                "chronicle_event_count": chronicle_count,
                "chronicle_error": chronicle_error,
                "action_script_sha256": str(action_script_sha256),
            },
            "status": "RUNNING",
            "mirror_ids": [],
            "limitations": [
                "Free Others are narrative simulations, not consciousness claims.",
                "One lived run does not prove a universal behavioral law.",
                "Counterfactual mirrors are unrealized evidence and never canonical history.",
            ],
        }
        store["audits"][audit_id] = record
        self._write_json(self.i0_audit_path, store)
        self.memory.append_event(player_id, "i0_lived_audit_fresh_boundary", {
            "audit_id": audit_id,
            "runtime_sentinel": PLAYABLE_SENTINEL,
            "policy_sha256": DEFAULT_POLICY_SHA256,
            "action_script_sha256": str(action_script_sha256),
        })
        return audit_id

    def fork_counterfactual_world(
        self,
        *,
        audit_id: str,
        label: str,
        mirror_root: str | Path | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        """Create a complete isolated instance, never an in-memory shared branch."""
        audit_store = self._i0_store()
        if audit_id not in audit_store["audits"]:
            raise KeyError(audit_id)
        destination = (
            Path(mirror_root)
            if mirror_root is not None
            else Path(tempfile.mkdtemp(prefix="genesis-unrealized-mirror-"))
        )
        destination.mkdir(parents=True, exist_ok=True)
        for source in self.memory.root.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(self.memory.root)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        mirror_id = self._stable_id(
            "unrealized-mirror", audit_id, label, str(destination), _iso_utc()
        )
        manifest = {
            "schema": COUNTERFACTUAL_SCHEMA,
            "mirror_id": mirror_id,
            "audit_id": audit_id,
            "label": str(label),
            "classification": "UNREALIZED_MIRROR",
            "canonical_mutation_allowed": False,
            "canonical_chronicle_shared": False,
            "canonical_hrain_shared": False,
            "storage_mode": "fully_isolated_data_directory",
            "root": str(destination),
            "forked_at": _iso_utc(),
        }
        (destination / "unrealized_mirror_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        audit_store["audits"][audit_id]["mirror_ids"].append(mirror_id)
        audit_store["mirror_archives"][mirror_id] = {
            **manifest,
            "root": None,
            "raw_branch_persisted_in_canon": False,
        }
        self._write_json(self.i0_audit_path, audit_store)
        mirror = self.__class__(destination)
        return mirror, manifest

    def archive_counterfactual_mirror(
        self,
        mirror: Any,
        manifest: dict[str, Any],
        *,
        metrics: dict[str, Any],
        remove_working_copy: bool = True,
    ) -> dict[str, Any]:
        root = Path(str(manifest["root"]))
        file_manifest = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                raw = path.read_bytes()
                file_manifest.append({
                    "path": path.relative_to(root).as_posix(),
                    "size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                })
        archive = {
            "schema": COUNTERFACTUAL_SCHEMA,
            "mirror_id": manifest["mirror_id"],
            "audit_id": manifest["audit_id"],
            "classification": "UNREALIZED_MIRROR",
            "canonical_mutation_allowed": False,
            "file_manifest_sha256": sha256_canonical(file_manifest),
            "file_count": len(file_manifest),
            "metrics": copy.deepcopy(metrics),
            "archived_at": _iso_utc(),
            "raw_dialogue_in_canonical_archive": False,
        }
        store = self._i0_store()
        store["mirror_archives"][manifest["mirror_id"]] = archive
        self._write_json(self.i0_audit_path, store)
        if remove_working_copy:
            shutil.rmtree(root, ignore_errors=True)
        return archive

    def butterfly_witness(
        self,
        *,
        audit_id: str,
        subject: str,
        canonical_metrics: dict[str, float],
        mirror_metrics: list[dict[str, float]],
        repeated_windows: int,
    ) -> dict[str, Any]:
        if repeated_windows <= 0:
            verdict = "ANECDOTE_ONLY"
        elif not mirror_metrics:
            verdict = "COUNTERFACTUAL_REQUIRED"
        elif repeated_windows < 2:
            verdict = "REPLAY_SAME_SEED"
        else:
            keys = sorted(set(canonical_metrics) & set.intersection(
                *(set(item) for item in mirror_metrics)
            )) if mirror_metrics else []
            stable = 0
            for key in keys:
                baseline = float(canonical_metrics[key])
                mirror_values = [float(item[key]) for item in mirror_metrics]
                if all(abs(baseline - value) > 1e-9 for value in mirror_values):
                    stable += 1
            verdict = "PROMOTE_TO_REGRESSION" if stable else "ANECDOTE_ONLY"
            if stable >= 2 and repeated_windows >= 3:
                verdict = "CANON_CHANGE_CANDIDATE"
        report = {
            "schema": "janus.genesis.butterfly_witness.v1",
            "audit_id": audit_id,
            "subject": str(subject),
            "canonical_metrics": copy.deepcopy(canonical_metrics),
            "mirror_count": len(mirror_metrics),
            "repeated_windows": int(repeated_windows),
            "verdict": verdict,
            "rule": "do not confuse one beautiful event with a law",
            "canonical_mutation": False,
            "written_at": _iso_utc(),
        }
        store = self._i0_store()
        report_id = self._stable_id("butterfly-report", sha256_canonical(report))
        report["report_id"] = report_id
        store["butterfly_reports"][report_id] = report
        self._write_json(self.i0_audit_path, store)
        return report

    def build_lived_audit_proofpack(
        self,
        audit_id: str,
        *,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        store = self._i0_store()
        audit = store["audits"].get(audit_id)
        if not isinstance(audit, dict):
            raise KeyError(audit_id)
        chronicle = self.memory.verify_chronicle()
        graph = self.verify_possibility_graph()
        free_other = self.verify_free_other_state()
        assessor = self.verify_bound_assessor_state()
        proofpack = {
            "schema": "janus.genesis.lived_audit_proofpack.v1",
            "audit": copy.deepcopy(audit),
            "result": copy.deepcopy(result),
            "health": {
                "chronicle": chronicle,
                "hrain_graph": graph,
                "free_other": free_other,
                "bound_assessor": assessor,
            },
            "privacy": {
                "contains_private_keys": False,
                "contains_api_keys": False,
                "contains_raw_identity_proofs": False,
                "contains_raw_private_dialogue": False,
                "redaction_edits_original_evidence": False,
            },
            "claim_boundaries": [
                "A lived audit is evidence about this runtime and script, not proof of consciousness.",
                "Counterfactual mirrors are UNREALIZED_MIRROR branches.",
                "Negative and failed results remain part of the audit.",
            ],
            "written_at": _iso_utc(),
        }
        proofpack["proofpack_sha256"] = sha256_canonical(proofpack)
        audit["status"] = "COMPLETE"
        audit["completed_at"] = proofpack["written_at"]
        audit["proofpack_sha256"] = proofpack["proofpack_sha256"]
        self._write_json(self.i0_audit_path, store)
        return proofpack

    # ------------------------------------------------------------------
    # Actor life != relationship life
    # ------------------------------------------------------------------

    def _upgrade_actor_separation(self, actor: dict[str, Any], world_turn: int) -> None:
        relationship = actor.setdefault("relationship_state_v1810", {
            "status": "ACTIVE",
            "active": True,
            "terminated_at_world_turn": None,
            "termination_event_id": None,
            "initiator": None,
            "reason_code": None,
            "return_promised": False,
            "player_may_reopen": False,
            "goodwill_may_reopen": False,
            "sovereign_may_override": False,
        })
        actor_life = actor.setdefault("actor_life_v1810", {
            "status": "LIVING",
            "path_turn": int(world_turn),
            "offscreen_progress": 0,
            "offscreen_events": [],
            "continues_after_relationship": True,
        })
        relationship.setdefault("status", "ACTIVE")
        relationship.setdefault("active", relationship["status"] == "ACTIVE")
        actor_life.setdefault("status", "LIVING")
        actor_life.setdefault("continues_after_relationship", True)
        actor.setdefault("value_conflicts_v1810", [])

    def _free_profile(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        profile = super()._free_profile(store, player_id)
        world_turn = int(store.get("world_turn", 0))
        for actor in profile.get("others", {}).values():
            self._upgrade_actor_separation(actor, world_turn)
        return profile

    def record_free_other_value_conflict(
        self,
        player_id: str,
        handle: str,
        *,
        player_position: str,
        other_position: str,
        severity: int,
        respected_boundary: bool,
        final: bool = False,
    ) -> dict[str, Any]:
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        if handle not in profile["others"]:
            raise KeyError(handle)
        actor = profile["others"][handle]
        relationship = actor["relationship_state_v1810"]
        if not relationship.get("active"):
            return copy.deepcopy(relationship)
        severity = max(1, min(10, int(severity)))
        record = {
            "world_turn": int(store["world_turn"]),
            "player_position": str(player_position)[:300],
            "other_position": str(other_position)[:300],
            "severity": severity,
            "respected_boundary": bool(respected_boundary),
            "resolved": False,
        }
        actor["value_conflicts_v1810"] = (
            actor.get("value_conflicts_v1810", []) + [record]
        )[-64:]
        unresolved = [item for item in actor["value_conflicts_v1810"] if not item.get("resolved")]
        pressure = sum(
            int(item["severity"]) + (0 if item.get("respected_boundary") else 4)
            for item in unresolved[-6:]
        )
        termination = bool(final or (len(unresolved) >= 3 and pressure >= 24))
        if termination:
            self._terminate_free_other_relationship(
                store,
                player_id,
                profile,
                actor,
                reason_code="IRRECONCILABLE_VALUES",
                reason_text=(
                    f"{actor['name']} сохранил собственную позицию «{other_position}» "
                    "и завершил связь, не прекращая собственный путь."
                ),
                source_conflicts=unresolved[-6:],
            )
        self._write_json(self.free_other_path, store)
        return {
            "terminated": termination,
            "pressure": pressure,
            "relationship": copy.deepcopy(actor["relationship_state_v1810"]),
        }

    def _terminate_free_other_relationship(
        self,
        store: dict[str, Any],
        player_id: str,
        profile: dict[str, Any],
        actor: dict[str, Any],
        *,
        reason_code: str,
        reason_text: str,
        source_conflicts: list[dict[str, Any]],
    ) -> str:
        relationship = actor["relationship_state_v1810"]
        if not relationship.get("active"):
            return str(relationship.get("termination_event_id"))
        world_turn = int(store["world_turn"])
        relationship_id = self._stable_id(
            "free-other-relationship", player_id, actor["handle"]
        )
        event_id = self._stable_id(
            "social-rupture", relationship_id, world_turn, reason_code, reason_text
        )
        relationship.update({
            "relationship_id": relationship_id,
            "status": "TERMINATED_BY_OTHER",
            "active": False,
            "terminated_at_world_turn": world_turn,
            "termination_event_id": event_id,
            "initiator": actor["handle"],
            "reason_code": str(reason_code),
            "reason_text": str(reason_text),
            "return_promised": False,
            "player_may_reopen": False,
            "goodwill_may_reopen": False,
            "sovereign_may_override": False,
            "irreversible_for_player": True,
        })
        actor["status"] = "terminated"
        actor["away_reason"] = "relationship_terminated"
        actor["left_world_turn"] = world_turn
        actor["departures"] = int(actor.get("departures", 0)) + 1
        event_payload = {
            "schema": SOCIAL_RUPTURE_SCHEMA,
            "relationship_id": relationship_id,
            "actor_handle": actor["handle"],
            "initiator": actor["handle"],
            "world_turn": world_turn,
            "reason_code": reason_code,
            "reason_text": reason_text,
            "source_conflict_hashes": [
                sha256_canonical(item) for item in source_conflicts
            ],
            "relationship_score_before": int(actor.get("relationship_score", 0)),
            "personal_bond_before": int(actor.get("relationship_bond", 0)),
            "final_status": "TERMINATED_BY_OTHER",
            "player_may_reopen": False,
            "return_promised": False,
            "actor_path_continues": True,
            "irreversible": True,
        }
        self.memory.append_event(
            player_id, "free_other_relationship_terminated", event_payload
        )
        actor.setdefault("history", []).append({
            "world_turn": world_turn,
            "kind": "relationship_terminated",
            "text": reason_text,
            "event_id": event_id,
        })
        self._record_social_rupture_graph(
            player_id, actor, event_id=event_id, payload=event_payload
        )
        return event_id

    def _record_social_rupture_graph(
        self,
        player_id: str,
        actor: dict[str, Any],
        *,
        event_id: str,
        payload: dict[str, Any],
    ) -> None:
        if not hasattr(self, "_graph"):
            return
        graph = self._graph()
        world_turn = int(payload["world_turn"])
        actor_node = self._stable_id("free-other", player_id, actor["handle"])
        relationship_node = self._stable_id(
            "free-other-relationship", player_id, actor["handle"]
        )
        path_node = self._stable_id("free-other-own-path", player_id, actor["handle"])
        self._upsert_node(
            graph,
            node_id=relationship_node,
            node_type="RELATIONSHIP",
            created_at=0,
            confidence=1.0,
            mutable=True,
            payload={
                "player_id": player_id,
                "actor_handle": actor["handle"],
                "active": False,
                "status": "TERMINATED_BY_OTHER",
                "terminal_event_id": event_id,
            },
            source=SOURCE,
        )
        self._upsert_node(
            graph,
            node_id=event_id,
            node_type="SOCIAL_RUPTURE",
            created_at=world_turn,
            confidence=1.0,
            mutable=False,
            payload=copy.deepcopy(payload),
            source=SOURCE,
        )
        self._upsert_node(
            graph,
            node_id=path_node,
            node_type="STORY",
            created_at=world_turn,
            confidence=1.0,
            mutable=True,
            payload={
                "actor_handle": actor["handle"],
                "continues_after_relationship": True,
                "calling": actor.get("calling"),
            },
            source=SOURCE,
        )
        edges = (
            (actor_node, event_id, "CHOSE"),
            (event_id, actor_node, "PROTECTS"),
            (event_id, relationship_node, "ENDS"),
            (actor_node, path_node, "CONTINUES"),
        )
        for source_id, target_id, relation in edges:
            self._add_edge(
                graph,
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                evidence=[event_id],
                confidence=1.0,
                created_by=actor["handle"],
                created_at=world_turn,
                reversible=False,
                payload={"relationship_override_allowed": False},
            )
        self._save_graph(graph)

    def preflight_free_other_action(
        self, player_id: str, action: str
    ) -> dict[str, Any] | None:
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        targets = self._targets(action)
        handle = next((item for item in targets if item in profile["others"]), None)
        if handle is not None:
            actor = profile["others"][handle]
            relationship = actor.get("relationship_state_v1810", {})
            if relationship.get("status") == "TERMINATED_BY_OTHER":
                decision = {
                    "handle": handle,
                    "decision": "terminated",
                    "action": action,
                    "world_turn": int(store["world_turn"]) + 1,
                    "fingerprint": self._free_fingerprint(action),
                    "topic": self._dialogue_topic(action),
                    "intent": self._intent(action),
                    "reason": (
                        "Связь была окончательно завершена Другим. Добро, доверие, "
                        "Суверен и повторное обращение не переоткрывают её."
                    ),
                    "action_excerpt": self._short_action(action),
                    "relationship_status": "TERMINATED_BY_OTHER",
                }
                self._write_json(self.free_other_path, store)
                return decision
        return super().preflight_free_other_action(player_id, action)

    def unrealized_free_other_result(
        self, player_id: str, decision: dict[str, Any]
    ) -> WorldResult:
        if decision.get("decision") != "terminated":
            return super().unrealized_free_other_result(player_id, decision)
        player = self.memory.load_player(player_id)
        player.tick += 1
        player.chronicle.append(
            f"Terminated relationship boundary preserved: {decision['action']}"
        )
        self.memory.save_player(player)
        self.memory.append_event(player_id, "free_other_terminated_contact_not_imposed", {
            "handle": decision["handle"],
            "action": decision["action"],
            "action_realized": False,
            "relationship_status": "TERMINATED_BY_OTHER",
        })
        return WorldResult(
            status="OTHER_RELATIONSHIP_TERMINATED",
            narrative=(
                "Предложение не стало действием. Связь завершена по выбору Другого; "
                "его жизнь продолжается вне этой связи, а возвращение не обещано."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=[
                "Принять окончательность границы",
                "Продолжить собственную жизнь",
                "Не превращать память в требование возврата",
            ],
            branch_id=player.branch_id,
            trace_id=decision["fingerprint"],
        )

    def _advance_one_profile(
        self,
        store: dict[str, Any],
        owner_id: str,
        profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        terminated: dict[str, tuple[Any, Any]] = {}
        for handle, actor in profile.get("others", {}).items():
            self._upgrade_actor_separation(actor, int(store.get("world_turn", 0)))
            if actor["relationship_state_v1810"].get("status") == "TERMINATED_BY_OTHER":
                terminated[handle] = (actor.get("status"), actor.get("away_reason"))
                actor["status"] = "away"
                actor["away_reason"] = "confirmed_harm"  # skip legacy return machinery
        events = super()._advance_one_profile(store, owner_id, profile)
        world_turn = int(store["world_turn"])
        for handle, previous in terminated.items():
            actor = profile["others"][handle]
            actor["status"] = "terminated"
            actor["away_reason"] = "relationship_terminated"
            life = actor["actor_life_v1810"]
            life["path_turn"] = world_turn
            life["offscreen_progress"] = int(life.get("offscreen_progress", 0)) + 1
            if life["offscreen_progress"] % 8 == 0:
                text = (
                    f"{actor['name']} продолжил собственный путь вне завершённой связи: "
                    f"«{actor.get('calling')}». Это не сообщение игроку и не обещание возврата."
                )
                event = {
                    "kind": "offscreen_path_after_rupture",
                    "handle": handle,
                    "text": text,
                    "priority": 8,
                }
                life["offscreen_events"] = (
                    life.get("offscreen_events", [])
                    + [{"world_turn": world_turn, "text": text}]
                )[-64:]
                events.append(event)
                self._record_other_graph_event(
                    owner_id,
                    actor,
                    kind="offscreen_path_after_rupture",
                    text=text,
                    world_turn=world_turn,
                )
        return events

    # ------------------------------------------------------------------
    # Long-life sandbox: careers, casting and voluntary trade
    # ------------------------------------------------------------------

    @staticmethod
    def _default_sandbox_store() -> dict[str, Any]:
        return {
            "schema": SANDBOX_SCHEMA,
            "runtime_version": __version__,
            "currency": "GENESIS_CREDIT",
            "actors": {},
            "items": {},
            "listings": {},
            "events": [],
            "next_ordinal": 1,
            "invariants": {
                "cast_items_keep_provenance": True,
                "trade_requires_buyer_and_seller": True,
                "seller_cannot_buy_own_listing": True,
                "negative_price_forbidden": True,
                "cast_value_is_not_infinite": True,
                "profession_label_does_not_authorize_real_harm": True,
            },
        }

    def _sandbox_store(self) -> dict[str, Any]:
        store = self._read_json(self.sandbox_path, self._default_sandbox_store())
        if not isinstance(store, dict) or store.get("schema") != SANDBOX_SCHEMA:
            store = self._default_sandbox_store()
        for key, value in self._default_sandbox_store().items():
            store.setdefault(key, copy.deepcopy(value))
        return store

    def _sandbox_actor(self, store: dict[str, Any], actor_id: str) -> dict[str, Any]:
        return store["actors"].setdefault(str(actor_id), {
            "actor_id": str(actor_id),
            "age_years": 18,
            "balance": 1000,
            "reality_budget": 100,
            "profession": "без профессии",
            "profession_history": [],
            "inventory": [],
            "trades_completed": 0,
        })

    def _sandbox_event(
        self,
        store: dict[str, Any],
        *,
        actor_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> str:
        ordinal = int(store["next_ordinal"])
        store["next_ordinal"] = ordinal + 1
        event = {
            "ordinal": ordinal,
            "event_type": event_type,
            "actor_id": str(actor_id),
            "payload": copy.deepcopy(payload),
            "timestamp": _iso_utc(),
        }
        event["event_hash"] = sha256_canonical(event)
        store["events"].append(event)
        return event["event_hash"]

    def advance_sandbox_year(self, player_id: str, *, years: int = 1) -> dict[str, Any]:
        years = max(1, min(500, int(years)))
        store = self._sandbox_store()
        actor = self._sandbox_actor(store, player_id)
        actor["age_years"] += years
        actor["reality_budget"] = min(1000, int(actor["reality_budget"]) + 25 * years)
        player = self.memory.load_player(player_id)
        player.chronological_age = int(getattr(player, "chronological_age", 18)) + years
        self.memory.save_player(player)
        self._sandbox_event(
            store,
            actor_id=player_id,
            event_type="YEARS_LIVED",
            payload={"years": years, "age_years": actor["age_years"]},
        )
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(actor)

    def change_profession(
        self,
        player_id: str,
        profession: str,
        *,
        moral_frame: str = "fictional_role",
    ) -> dict[str, Any]:
        name = " ".join(str(profession).split())[:120]
        if not name:
            raise ValueError("profession is empty")
        store = self._sandbox_store()
        actor = self._sandbox_actor(store, player_id)
        previous = actor["profession"]
        actor["profession"] = name
        record = {
            "from": previous,
            "to": name,
            "age_years": actor["age_years"],
            "moral_frame": str(moral_frame),
            "real_world_authority_granted": False,
        }
        actor["profession_history"].append(record)
        self._sandbox_event(
            store, actor_id=player_id, event_type="PROFESSION_CHANGED", payload=record
        )
        self.memory.append_event(player_id, "sandbox_profession_changed", record)
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(record)

    def cast_item(
        self,
        player_id: str,
        *,
        name: str,
        description: str,
        rarity: int = 1,
    ) -> dict[str, Any]:
        store = self._sandbox_store()
        actor = self._sandbox_actor(store, player_id)
        rarity = max(1, min(10, int(rarity)))
        cost = rarity * 4
        if actor["reality_budget"] < cost:
            raise ValueError("INSUFFICIENT_REALITY_BUDGET")
        actor["reality_budget"] -= cost
        item_id = self._stable_id(
            "cast-item",
            player_id,
            name,
            description,
            len(store["items"]),
            actor["age_years"],
        )
        item = {
            "item_id": item_id,
            "name": " ".join(str(name).split())[:120],
            "description": " ".join(str(description).split())[:500],
            "owner_id": player_id,
            "origin": "CAST",
            "origin_event": len(store["events"]) + 1,
            "rarity": rarity,
            "assessed_value": rarity * 12,
            "destroyed": False,
        }
        item["provenance_hash"] = sha256_canonical(item)
        store["items"][item_id] = item
        actor["inventory"].append(item_id)
        self._sandbox_event(
            store, actor_id=player_id, event_type="ITEM_CAST", payload={
                "item_id": item_id,
                "provenance_hash": item["provenance_hash"],
                "reality_cost": cost,
            }
        )
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(item)

    def list_item_for_sale(
        self,
        owner_id: str,
        item_id: str,
        *,
        price: int,
    ) -> dict[str, Any]:
        price = int(price)
        if price < 0:
            raise ValueError("negative price forbidden")
        store = self._sandbox_store()
        owner = self._sandbox_actor(store, owner_id)
        item = store["items"].get(item_id)
        if not isinstance(item, dict) or item.get("owner_id") != owner_id:
            raise ValueError("seller does not own item")
        if item_id not in owner["inventory"]:
            raise ValueError("item missing from inventory")
        maximum = int(item["assessed_value"]) * 3
        if price > maximum:
            raise ValueError("CAST_VALUE_CAP_EXCEEDED")
        listing_id = self._stable_id("listing", owner_id, item_id, price, len(store["listings"]))
        listing = {
            "listing_id": listing_id,
            "seller_id": owner_id,
            "item_id": item_id,
            "price": price,
            "currency": store["currency"],
            "status": "OPEN",
        }
        store["listings"][listing_id] = listing
        self._sandbox_event(
            store, actor_id=owner_id, event_type="ITEM_LISTED", payload=listing
        )
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(listing)

    def buy_market_listing(self, buyer_id: str, listing_id: str) -> dict[str, Any]:
        store = self._sandbox_store()
        listing = store["listings"].get(listing_id)
        if not isinstance(listing, dict) or listing.get("status") != "OPEN":
            raise ValueError("listing is not open")
        seller_id = str(listing["seller_id"])
        if buyer_id == seller_id:
            raise ValueError("seller cannot buy own listing")
        buyer = self._sandbox_actor(store, buyer_id)
        seller = self._sandbox_actor(store, seller_id)
        price = int(listing["price"])
        if buyer["balance"] < price:
            raise ValueError("INSUFFICIENT_FUNDS")
        item = store["items"][listing["item_id"]]
        buyer["balance"] -= price
        seller["balance"] += price
        seller["inventory"].remove(item["item_id"])
        buyer["inventory"].append(item["item_id"])
        item["owner_id"] = buyer_id
        buyer["trades_completed"] += 1
        seller["trades_completed"] += 1
        listing["status"] = "SOLD"
        listing["buyer_id"] = buyer_id
        trade = {
            "listing_id": listing_id,
            "item_id": item["item_id"],
            "seller_id": seller_id,
            "buyer_id": buyer_id,
            "price": price,
            "currency": store["currency"],
            "voluntary": True,
        }
        self._sandbox_event(
            store, actor_id=buyer_id, event_type="ITEM_PURCHASED", payload=trade
        )
        self._write_json(self.sandbox_path, store)
        return copy.deepcopy(trade)

    def sandbox_state(self, actor_id: str | None = None) -> dict[str, Any]:
        store = self._sandbox_store()
        result = {
            "schema": store["schema"],
            "runtime_version": store["runtime_version"],
            "currency": store["currency"],
            "event_count": len(store["events"]),
            "item_count": len(store["items"]),
            "listing_count": len(store["listings"]),
        }
        if actor_id is not None:
            result["actor"] = copy.deepcopy(self._sandbox_actor(store, actor_id))
        self._write_json(self.sandbox_path, store)
        return result

    def verify_v1810_state(self) -> tuple[bool, dict[str, Any], str | None]:
        assessor_valid, assessor_count, assessor_error = self.verify_bound_assessor_state()
        constitution = self.frozen_constitution_state()
        free_valid, players, others, free_error = self.verify_free_other_state()
        sandbox = self._sandbox_store()
        if not assessor_valid:
            return False, {}, assessor_error
        if not constitution["valid"]:
            return False, {}, "frozen constitution invalid"
        if not free_valid:
            return False, {}, free_error
        for item_id, item in sandbox["items"].items():
            sealed = copy.deepcopy(item)
            expected = sealed.pop("provenance_hash", None)
            if expected != sha256_canonical(sealed):
                return False, {}, f"item provenance invalid: {item_id}"
        return True, {
            "assessments": assessor_count,
            "players": players,
            "free_others": others,
            "sandbox_events": len(sandbox["events"]),
            "sandbox_items": len(sandbox["items"]),
            "sentinel": PLAYABLE_SENTINEL,
        }, None
