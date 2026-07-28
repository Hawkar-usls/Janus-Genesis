from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_9 import build_provider_attestation, generate_ed25519_keypair
from genesis_v18_7_10 import (
    DEFAULT_CONFIDENCE_POLICY,
    DEFAULT_POLICY_SHA256,
    SIGNED_OBSERVATION_COMPONENTS,
    build_assessor_attestation,
    build_root_governance_manifest,
)
from genesis_v18_7_playable import PlayableGenesisV187

ISSUED = "2026-01-01T00:00:00Z"
EXPIRES = "2099-01-01T00:00:00Z"


def sha256_text(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class BoundAssessorReviewRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.world = PlayableGenesisV187(Path(self.temp.name))
        self.root_private, root_public = generate_ed25519_keypair()
        self.provider_private, provider_public = generate_ed25519_keypair()
        self.assessor_private, assessor_public = generate_ed25519_keypair()
        old = os.environ.get("GENESIS_OFFLINE_ROOT_BOOTSTRAP")
        os.environ["GENESIS_OFFLINE_ROOT_BOOTSTRAP"] = "1"
        try:
            self.world.bootstrap_offline_root_key(
                "review-root",
                key_id="root-key",
                public_key_b64=root_public,
                valid_from=ISSUED,
                valid_until=EXPIRES,
                ceremony_receipt="review regression offline ceremony",
            )
        finally:
            if old is None:
                os.environ.pop("GENESIS_OFFLINE_ROOT_BOOTSTRAP", None)
            else:
                os.environ["GENESIS_OFFLINE_ROOT_BOOTSTRAP"] = old
        manifest = build_root_governance_manifest(
            root_id="review-root",
            key_id="root-key",
            operations=[
                {
                    "operation": "TRUST_PROVIDER_KEY",
                    "provider_id": "review-provider",
                    "key_id": "provider-key",
                    "public_key_b64": provider_public,
                    "valid_from": ISSUED,
                    "valid_until": EXPIRES,
                },
                {
                    "operation": "TRUST_ASSESSOR_KEY",
                    "assessor_id": "review-assessor",
                    "key_id": "assessor-key",
                    "public_key_b64": assessor_public,
                    "valid_from": ISSUED,
                    "valid_until": EXPIRES,
                },
                {
                    "operation": "SET_ASSESSOR_CREDENTIAL",
                    "credential_id": "review-assessor-general-v1",
                    "assessor_id": "review-assessor",
                    "controller_id": sha256_text("independent-review-controller"),
                    "allowed_methods": ["triangulation-v2"],
                    "allowed_subject_scopes": ["*"],
                    "competence_by_scope": {"*": 0.8},
                    "max_component_authority": {
                        name: 0.95 for name in SIGNED_OBSERVATION_COMPONENTS
                    },
                    "may_assess_own_sources": False,
                    "valid_from": ISSUED,
                    "valid_until": EXPIRES,
                    "credential_version": "1",
                },
            ],
            nonce="review-root-manifest",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.root_private,
        )
        self.world.apply_root_governance_manifest(manifest)
        self.counter = 0

    def _claim(self, label: str) -> tuple[str, str]:
        self.counter += 1
        account_id = f"reader-{label}"
        identity = f"identity-{label}-{self.counter}"
        controller = f"controller-{label}-{self.counter}"
        _private, public = generate_ed25519_keypair()
        provider = build_provider_attestation(
            provider_id="review-provider",
            key_id="provider-key",
            account_id=account_id,
            identity_proof=identity,
            controller_proof=controller,
            account_public_key_b64=public,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            nonce=f"provider-{label}-{self.counter}",
            private_key_b64=self.provider_private,
        )
        self.world.register_influence_account(
            account_id,
            identity_proof=identity,
            controller_proof=controller,
            provider_attestation=provider,
        )
        scope = self.world.create_subject_scope(
            topic=f"review-{label}",
            event="review regression",
            time_scope={"date": "2026-07-28"},
            influence_sensitive=True,
            public_opinion=True,
        )
        text = f"review claim {label}"
        origin = self.world.import_origin_bytes(
            repository="review/regression",
            commit="18.7.10",
            path=f"claims/{label}.json",
            raw=json.dumps({"statement": text}).encode("utf-8"),
            source_public=True,
        )
        claim = self.world.record_reader_interpretation(
            origin["origin_key"],
            text,
            reader_id=account_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            subject_scope_id=scope,
        )
        self.world.attest_claim_influence(
            claim,
            account_id=account_id,
            evidence_proof=f"evidence-proof-{label}",
        )
        return claim, scope

    def _assessment(
        self,
        claim: str,
        scope: str,
        *,
        assessment_id: str,
        nonce: str,
        evidence: str,
        supersedes: str | None = None,
    ) -> dict:
        return build_assessor_attestation(
            assessment_id=assessment_id,
            assessor_id="review-assessor",
            key_id="assessor-key",
            claim_id=claim,
            subject_scope_id=scope,
            method_id="triangulation-v2",
            method_version="2",
            policy_id=DEFAULT_CONFIDENCE_POLICY["policy_id"],
            policy_version=DEFAULT_CONFIDENCE_POLICY["policy_version"],
            policy_sha256=DEFAULT_POLICY_SHA256,
            evidence_hashes=[sha256_text(evidence)],
            components={name: 0.8 for name in SIGNED_OBSERVATION_COMPONENTS},
            explanation="review regression evidence",
            nonce=nonce,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.assessor_private,
            supersedes_assessment_id=supersedes,
        )

    def test_derived_weight_and_claim_projection_tampering_is_detected(self) -> None:
        claim, scope = self._claim("derived")
        assessment = self._assessment(
            claim,
            scope,
            assessment_id="assessment-derived",
            nonce="nonce-derived",
            evidence="evidence-derived",
        )
        assessment_id = self.world.record_evidence_assessment(claim, assessment=assessment)
        store = self.world._plural_store()
        store["signed_assessments_v1810"][assessment_id]["effective_confidence"] = 1.0
        store["signed_assessments_v1810"][assessment_id]["assessment_input_sha256"] = "f" * 64
        store["claims"][claim]["assessment_confidence"] = 1.0
        self.world._write_json(self.world.plural_witness_path, store)

        valid, _count, error = self.world.verify_bound_assessor_state()
        self.assertFalse(valid)
        self.assertTrue(
            any(fragment in (error or "") for fragment in (
                "assessment input projection changed",
                "effective confidence changed",
                "claim confidence projection changed",
            )),
            error,
        )

    def test_cross_claim_supersession_cannot_disable_unrelated_assessment(self) -> None:
        first_claim, first_scope = self._claim("first")
        first = self._assessment(
            first_claim,
            first_scope,
            assessment_id="assessment-first",
            nonce="nonce-first",
            evidence="evidence-first",
        )
        first_id = self.world.record_evidence_assessment(first_claim, assessment=first)

        second_claim, second_scope = self._claim("second")
        forged_supersession = self._assessment(
            second_claim,
            second_scope,
            assessment_id="assessment-second",
            nonce="nonce-second",
            evidence="evidence-second",
            supersedes=first_id,
        )
        with self.assertRaisesRegex(ValueError, "SUPERSEDES_MUST_MATCH_SEMANTIC_PREDECESSOR"):
            self.world.record_evidence_assessment(
                second_claim,
                assessment=forged_supersession,
            )
        stored = self.world._plural_store()["signed_assessments_v1810"][first_id]
        self.assertTrue(stored["current_authority"])
        self.assertNotIn("superseded_by", stored)


if __name__ == "__main__":
    unittest.main()
