# -*- coding: utf-8 -*-
"""Completion-first sealing for Genesis v18.7.10 lived audit proofpacks."""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_10 import _iso_utc
from genesis_v18_7_9 import sha256_canonical


class LivedAuditCompletionIntegrityMixin:
    """Ensure the exported proofpack itself witnesses a completed audit."""

    @staticmethod
    def _proofpack_hash_material(proofpack: dict[str, Any]) -> dict[str, Any]:
        material = copy.deepcopy(proofpack)
        material.pop("proofpack_sha256", None)
        audit = material.get("audit")
        if isinstance(audit, dict):
            audit.pop("proofpack_sha256", None)
        return material

    def build_lived_audit_proofpack(
        self,
        audit_id: str,
        *,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        store = self._i0_store()
        stored_audit = store["audits"].get(audit_id)
        if not isinstance(stored_audit, dict):
            raise KeyError(audit_id)

        completed_at = _iso_utc()
        audit = copy.deepcopy(stored_audit)
        audit["status"] = "COMPLETE"
        audit["completed_at"] = completed_at
        audit.pop("proofpack_sha256", None)

        proofpack = {
            "schema": "janus.genesis.lived_audit_proofpack.v1",
            "hash_scope": "exclude_top_level_and_audit_proofpack_sha256",
            "audit": copy.deepcopy(audit),
            "result": copy.deepcopy(result),
            "health": {
                "chronicle": self.memory.verify_chronicle(),
                "hrain_graph": self.verify_possibility_graph(),
                "free_other": self.verify_free_other_state(),
                "bound_assessor": self.verify_bound_assessor_state(),
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
            "written_at": completed_at,
        }
        digest = sha256_canonical(self._proofpack_hash_material(proofpack))
        proofpack["proofpack_sha256"] = digest
        proofpack["audit"]["proofpack_sha256"] = digest
        audit["proofpack_sha256"] = digest
        store["audits"][audit_id] = audit
        self._write_json(self.i0_audit_path, store)
        return proofpack

    def verify_lived_audit_proofpack(
        self,
        proofpack: dict[str, Any],
    ) -> tuple[bool, str | None]:
        if proofpack.get("schema") != "janus.genesis.lived_audit_proofpack.v1":
            return False, "unsupported proofpack schema"
        if proofpack.get("hash_scope") != "exclude_top_level_and_audit_proofpack_sha256":
            return False, "unsupported proofpack hash scope"
        audit = proofpack.get("audit")
        if not isinstance(audit, dict) or audit.get("status") != "COMPLETE":
            return False, "proofpack audit is not complete"
        digest = str(proofpack.get("proofpack_sha256", ""))
        if not digest or audit.get("proofpack_sha256") != digest:
            return False, "proofpack digest projections disagree"
        expected = sha256_canonical(self._proofpack_hash_material(proofpack))
        if digest != expected:
            return False, "proofpack hash mismatch"
        return True, None
