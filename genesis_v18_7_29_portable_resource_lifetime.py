# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.29 — Windows-safe SQLite resource lifetime correction.

v18.7.28 correctly made the control primitives importable on Windows, but the
first Windows CI run exposed a real implementation defect: using a sqlite3
Connection as a context manager commits/rolls back yet does not close the
connection. On Windows that retained a file handle long enough to block cleanup
of the request-ledger database.

This descendant preserves the v18.7.28 request-binding semantics while making
connection ownership explicit. The failed v18.7.28 Windows run remains evidence
and is not reclassified as a pass.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from genesis_v18_7_28_client_ledger_attestation import (
    AttestedReviewAssignment,
    AttestedReviewCandidate,
    ClientControlError,
    ClientRequestBinding,
    ClientRequestConflict,
    ControlledClientExecutor,
    HMACLineageAttestor,
    HMACProviderEvidenceVerifier,
    IndependentAttestedReviewUnavailable,
    LifecycleSerializedGateway,
    LineageAttestation,
    LineageAttestationError,
    LineageAttestationVerifier,
    PersistentClientRequestLedger as _PersistentClientRequestLedgerV28,
    ProviderEvidenceContractError,
    ProviderEvidenceVerifier,
    RuntimeRequestExecutor,
    VerifiedLineageReviewPlanner,
    VerifiedProviderAdapter,
    VerifiedProviderDecision,
    VerifiedProviderLookupReconciler,
    VerifiedProviderObservation,
    VerifiedProviderOutcome,
)

PORTABLE_RESOURCE_LIFETIME_VERSION = "18.7.29"
PORTABLE_RESOURCE_LIFETIME_SCHEMA = "janus.genesis.portable_resource_lifetime.v1"


class PersistentClientRequestLedger(_PersistentClientRequestLedgerV28):
    """v18.7.28 ledger with explicit SQLite connection close on every path."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_requests (
                    client_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    runtime_request_id TEXT NOT NULL UNIQUE,
                    actor_id TEXT NOT NULL,
                    action_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    result_sha256 TEXT,
                    PRIMARY KEY(client_id, request_id)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, *, client_id: str, request_id: str) -> ClientRequestBinding | None:
        client = str(client_id).strip()
        request = str(request_id).strip()
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT runtime_request_id, actor_id, action_sha256, state, result_sha256
                FROM client_requests WHERE client_id=? AND request_id=?
                """,
                (client, request),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        runtime_id, actor_id, action_hash, state, result_hash = row
        return ClientRequestBinding(
            client_id=client,
            request_id=request,
            runtime_request_id=runtime_id,
            actor_id=actor_id,
            action_sha256=action_hash,
            state=state,
            result_sha256=result_hash,
        )


class PortableControlledClientExecutor(ControlledClientExecutor):
    """Nominal v18.7.29 type for the corrected persistent ledger path."""

    def __init__(self, *, ledger: PersistentClientRequestLedger, runtime: RuntimeRequestExecutor) -> None:
        super().__init__(ledger=ledger, runtime=runtime)


__all__ = [
    "PORTABLE_RESOURCE_LIFETIME_VERSION",
    "PORTABLE_RESOURCE_LIFETIME_SCHEMA",
    "ClientControlError",
    "ClientRequestConflict",
    "ClientRequestBinding",
    "PersistentClientRequestLedger",
    "RuntimeRequestExecutor",
    "ControlledClientExecutor",
    "PortableControlledClientExecutor",
    "LifecycleSerializedGateway",
    "LineageAttestation",
    "LineageAttestationVerifier",
    "HMACLineageAttestor",
    "LineageAttestationError",
    "AttestedReviewCandidate",
    "AttestedReviewAssignment",
    "VerifiedLineageReviewPlanner",
    "IndependentAttestedReviewUnavailable",
    "VerifiedProviderOutcome",
    "VerifiedProviderObservation",
    "VerifiedProviderAdapter",
    "ProviderEvidenceVerifier",
    "HMACProviderEvidenceVerifier",
    "ProviderEvidenceContractError",
    "VerifiedProviderDecision",
    "VerifiedProviderLookupReconciler",
]
