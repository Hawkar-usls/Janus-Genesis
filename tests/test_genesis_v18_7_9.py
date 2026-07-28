from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_9 import (
    ASSESSMENT_COMPONENTS,
    build_delegation,
    build_provider_attestation,
    build_sovereign_capability,
    generate_ed25519_keypair,
)
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


ISSUED = "2026-01-01T00:00:00Z"
EXPIRES = "2099-01-01T00:00:00Z"


class GenesisV1879BoundAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        self.provider_private, self.provider_public = generate_ed25519_keypair()
        self.sovereign_private, self.sovereign_public = generate_ed25519_keypair()
        self.world.register_trusted_provider_key(
            "provider-alpha",
            key_id="provider-key-1",
            public_key_b64=self.provider_public,
            valid_from=ISSUED,
            valid_until=EXPIRES,
        )
        self.world.register_sovereign_key(
            key_id="sovereign-key-1",
            public_key_b64=self.sovereign_public,
            valid_from=ISSUED,
            valid_until=EXPIRES,
        )
        self.account_private: dict[str, str] = {}
        self.account_public: dict[str, str] = {}
        self._counter = 0

    def _register(self, account_id: str, *, controller: str | None = None) -> None:
        identity = f"identity-proof-{account_id}-unique"
        controller_proof = controller or f"controller-proof-{account_id}-unique"
        private, public = generate_ed25519_keypair()
        self.account_private[account_id] = private
        self.account_public[account_id] = public
        attestation = build_provider_attestation(
            provider_id="provider-alpha",
            key_id="provider-key-1",
            account_id=account_id,
            identity_proof=identity,
            controller_proof=controller_proof,
            account_public_key_b64=public,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            nonce=f"provider-nonce-{account_id}",
            private_key_b64=self.provider_private,
        )
        self.world.register_influence_account(
            account_id,
            identity_proof=identity,
            controller_proof=controller_proof,
            provider_attestation=attestation,
            operator_disclosed=True,
        )

    def _scope(self, topic: str = "bound_authority") -> str:
        return self.world.create_subject_scope(
            topic=topic,
            event="public hearing",
            time_scope={"date": "2026-07-28"},
            influence_sensitive=True,
            public_opinion=True,
        )

    def _claim(
        self,
        *,
        scope: str,
        account_id: str,
        text: str,
        controller: str | None = None,
        campaign_id: str | None = None,
        evidence_proof: str | None = None,
        claimant_confidence: float | None = None,
        register: bool = True,
    ) -> str:
        if register:
            self._register(account_id, controller=controller)
        self._counter += 1
        origin = self.world.import_origin_bytes(
            repository="bound/authority",
            commit="18.7.9",
            path=f"claims/{self._counter}-{account_id}.json",
            raw=json.dumps({"statement": text}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        claim_id = self.world.record_reader_interpretation(
            origin["origin_key"],
            text,
            reader_id=account_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            about="bound_authority_test",
            confidence=claimant_confidence,
            subject_scope_id=scope,
        )
        self.world.attest_claim_influence(
            claim_id,
            account_id=account_id,
            evidence_proof=evidence_proof or f"evidence-{account_id}-{self._counter}",
            message=text,
            campaign_id=campaign_id,
            campaign_disclosed=campaign_id is not None,
        )
        return claim_id

    def _cap(self, scope: str, case_id: str, nonce: str) -> dict:
        return build_sovereign_capability(
            key_id="sovereign-key-1",
            scope=scope,
            case_id=case_id,
            nonce=nonce,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.sovereign_private,
        )

    @staticmethod
    def _assessment(value: float) -> dict[str, float]:
        return {name: value for name in ASSESSMENT_COMPONENTS}

    def test_primary_version_and_boolean_provider_flag_rejected(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.9")
        with self.assertRaisesRegex(ValueError, "ProviderAttestation"):
            self.world.register_influence_account(
                "fake-provider-account",
                identity_proof="identity-proof-fake-provider",
                controller_proof="controller-proof-fake-provider",
                identity_provider="invented",
                provider_verified=True,
            )

    def test_provider_signature_tampering_and_replay_are_rejected(self) -> None:
        _private, public = generate_ed25519_keypair()
        identity = "identity-proof-signed-account"
        controller = "controller-proof-signed-account"
        attestation = build_provider_attestation(
            provider_id="provider-alpha",
            key_id="provider-key-1",
            account_id="signed-account",
            identity_proof=identity,
            controller_proof=controller,
            account_public_key_b64=public,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            nonce="single-provider-nonce",
            private_key_b64=self.provider_private,
        )
        tampered = dict(attestation)
        tampered["subject_id"] = "other-account"
        with self.assertRaisesRegex(ValueError, "INVALID_SIGNATURE"):
            self.world.register_influence_account(
                "other-account",
                identity_proof=identity,
                controller_proof=controller,
                provider_attestation=tampered,
            )
        self.world.register_influence_account(
            "signed-account",
            identity_proof=identity,
            controller_proof=controller,
            provider_attestation=attestation,
        )
        with self.assertRaisesRegex(ValueError, "REPLAYED"):
            self.world.register_influence_account(
                "signed-account",
                identity_proof=identity,
                controller_proof=controller,
                provider_attestation=attestation,
            )

    def test_controller_precedes_campaign_sharding(self) -> None:
        scope = self._scope("campaign_sharding")
        controller = "one-controller-across-campaigns"
        claims = [
            self._claim(
                scope=scope,
                account_id=f"shard-{index}",
                controller=controller,
                text=f"Different campaign wording {index}",
                campaign_id=f"campaign-{index}",
                evidence_proof=f"different-evidence-{index}",
            )
            for index in range(3)
        ]
        audit = self.world.audit_influence_claims(claims)
        self.assertEqual(audit["independent_voice_count"], 1)
        self.assertTrue(audit["controller_outranks_campaign"])
        self.assertEqual(audit["controller_collisions"], 2)

    def test_cross_account_attestation_requires_signed_delegation(self) -> None:
        scope = self._scope("delegation")
        self._register("speaker")
        self._register("attester")
        origin = self.world.import_origin_bytes(
            repository="bound/delegation",
            commit="18.7.9",
            path="delegation/claim.json",
            raw=json.dumps({"statement": "Delegated statement"}).encode("utf-8"),
            source_public=True,
        )
        claim = self.world.record_reader_interpretation(
            origin["origin_key"],
            "Delegated statement",
            reader_id="speaker",
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            subject_scope_id=scope,
        )
        with self.assertRaisesRegex(ValueError, "claim.actor must equal"):
            self.world.attest_claim_influence(
                claim,
                account_id="attester",
                evidence_proof="delegated-evidence-proof",
            )
        delegation = build_delegation(
            delegator="speaker",
            delegate="attester",
            key_id="speaker-account-key",
            scope="voice_attestation",
            claim_id=claim,
            nonce="delegation-nonce",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.account_private["speaker"],
        )
        delegation_id = self.world.register_attestation_delegation(delegation)
        attestation_id = self.world.attest_claim_influence(
            claim,
            account_id="attester",
            evidence_proof="delegated-evidence-proof",
            delegation_id=delegation_id,
        )
        stored = self.world._plural_store()["influence_attestations"][attestation_id]
        self.assertEqual(stored["speaker_account_id"], "speaker")
        self.assertEqual(stored["attester_account_id"], "attester")

    def test_withdrawal_ends_future_weight_and_reopens_decided_case(self) -> None:
        scope = self._scope("ghost_voting")
        claims = [
            self._claim(scope=scope, account_id=f"ghost-{index}", text=f"Position {index}")
            for index in range(3)
        ]
        case_id = self.world.open_sovereign_case(claims, subject_scope_id=scope)
        self.world.janus_sovereign_decide(
            case_id,
            capability=self._cap("sovereign_case_decision", case_id, "decision-before-withdrawal"),
        )
        self.world.withdraw_witness_voice("ghost-0")
        case = self.world._plural_store()["sovereign_cases"][case_id]
        self.assertEqual(case["status"], "CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE")
        self.assertEqual(case["witness_count"], 2)
        audit = self.world.audit_influence_claims(claims)
        self.assertIn("VOICE_WITHDRAWN", audit["reasons_by_claim"][claims[0]])

    def test_claimant_confidence_is_not_sovereign_weight(self) -> None:
        scope = self._scope("confidence")
        claims = [
            self._claim(scope=scope, account_id="confidence-high", text="Build a high wall", claimant_confidence=1.0),
            self._claim(scope=scope, account_id="confidence-low-a", text="Keep the passage open", claimant_confidence=0.0),
            self._claim(scope=scope, account_id="confidence-low-b", text="Run another inspection", claimant_confidence=0.0),
        ]
        case_id = self.world.open_sovereign_case(claims, subject_scope_id=scope)
        decision_id = self.world.janus_sovereign_decide(
            case_id,
            capability=self._cap("sovereign_case_decision", case_id, "confidence-neutral-decision"),
        )
        decision = self.world._plural_store()["sovereign_decisions"][decision_id]
        self.assertEqual(decision["ruling"], "DEFER_FOR_MORE_EVIDENCE")
        self.assertFalse(decision["claimant_confidence_used"])

    def test_assessment_components_can_support_a_transparent_decision(self) -> None:
        scope = self._scope("assessment")
        claims = [
            self._claim(scope=scope, account_id=f"assessed-{index}", text=f"Option {index}")
            for index in range(3)
        ]
        for index, claim_id in enumerate(claims):
            self.world.record_evidence_assessment(
                claim_id,
                components=self._assessment(0.9 if index == 0 else 0.3),
                assessor_id="internal-evidence-assessor",
                method_id="equal-component-mean",
                method_version="1",
                evidence_ids=[f"evidence-{index}"],
                explanation="Transparent component assessment",
            )
        case_id = self.world.open_sovereign_case(claims, subject_scope_id=scope)
        decision_id = self.world.janus_sovereign_decide(
            case_id,
            capability=self._cap("sovereign_case_decision", case_id, "assessment-decision"),
        )
        decision = self.world._plural_store()["sovereign_decisions"][decision_id]
        self.assertEqual(decision["ruling"], "ADOPT_MOST_SUPPORTED_POSITION")
        self.assertEqual(decision["confidence_source"], "evidence_assessment")

    def test_sovereign_capability_is_scoped_case_bound_and_single_use(self) -> None:
        scope = self._scope("capability")
        claims = [
            self._claim(scope=scope, account_id=f"cap-{index}", text="Same position")
            for index in range(3)
        ]
        case_id = self.world.open_sovereign_case(claims, subject_scope_id=scope)
        with self.assertRaisesRegex(ValueError, "SOVEREIGN_CAPABILITY"):
            self.world.janus_sovereign_decide(case_id)
        wrong = self._cap("manipulation_review", case_id, "wrong-scope")
        with self.assertRaisesRegex(ValueError, "WRONG_SCOPE"):
            self.world.janus_sovereign_decide(case_id, capability=wrong)
        capability = self._cap("sovereign_case_decision", case_id, "one-use-decision")
        self.world.janus_sovereign_decide(case_id, capability=capability)
        with self.assertRaisesRegex(ValueError, "REPLAYED"):
            self.world.janus_sovereign_decide(case_id, capability=capability)

    def test_append_only_appeal_restores_voice_and_preserves_history(self) -> None:
        scope = self._scope("appeal")
        claim = self._claim(scope=scope, account_id="appealed-reader", text="Appealed grounded position")
        record = self.world.record_manipulation_evidence(
            claim,
            kind="IMPERSONATION",
            evidence="audit evidence reference",
            reporter_id="auditor",
        )
        self.world.confirm_manipulation_evidence(
            record,
            confirmed=True,
            rationale="Initial finding",
            capability=self._cap("manipulation_review", record, "review-confirmation"),
        )
        self.assertFalse(self.world.recalculate_eligibility(claim, reason="check"))
        self.world.appeal_manipulation_evidence(
            record,
            appellant_id="appealed-reader",
            grounds="Provider log disproves impersonation",
        )
        self.world.resolve_manipulation_appeal(
            record,
            restored=True,
            rationale="Finding overturned after signed provider evidence",
            capability=self._cap("manipulation_appeal", record, "appeal-restoration"),
        )
        self.assertTrue(self.world.recalculate_eligibility(claim, reason="restored"))
        store = self.world._plural_store()
        events = [event["event_type"] for event in store["authority_events"] if event["subject_id"] == record]
        self.assertEqual(
            [item for item in events if item in {"PENDING_REVIEW", "CONFIRMED", "APPEALED", "RESTORED"}],
            ["PENDING_REVIEW", "CONFIRMED", "APPEALED", "RESTORED"],
        )
        self.assertEqual(store["manipulation_evidence"][record]["status"], "PENDING_REVIEW")

    def test_provider_key_revocation_reopens_affected_case(self) -> None:
        scope = self._scope("key_revocation")
        claims = [
            self._claim(scope=scope, account_id=f"key-{index}", text="Shared proposal")
            for index in range(3)
        ]
        case_id = self.world.open_sovereign_case(claims, subject_scope_id=scope)
        self.world.janus_sovereign_decide(
            case_id,
            capability=self._cap("sovereign_case_decision", case_id, "before-key-revocation"),
        )
        self.world.revoke_trusted_provider_key(
            "provider-alpha",
            "provider-key-1",
            reason="key compromise discovered",
            compromised_from="2025-12-31T00:00:00Z",
        )
        case = self.world._plural_store()["sovereign_cases"][case_id]
        self.assertEqual(case["status"], "CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE")
        self.assertEqual(case["witness_count"], 0)

    def test_bound_authority_crosses_portable_threshold_without_private_keys(self) -> None:
        scope = self._scope("portable")
        claims = [
            self._claim(scope=scope, account_id=f"portable-{index}", text=f"Voice {index}")
            for index in range(3)
        ]
        self.world.open_sovereign_case(claims, subject_scope_id=scope)
        output = self.root.parent / "bound-authority.genesis-save.json"
        target = self.root.parent / "bound-authority-restored"
        try:
            manager = PortableSaveManager(self.root)
            result = manager.export_to(output, label="The Bound Authority")
            bundle = json.loads(output.read_text(encoding="utf-8"))
            text = output.read_text(encoding="utf-8")
            self.assertFalse(result["contains_api_keys"])
            self.assertNotIn(self.provider_private, text)
            self.assertNotIn(self.sovereign_private, text)
            PortableSaveManager(target).import_bundle(bundle)
            restored = PlayableGenesisV187(target)
            valid, count, error = restored.verify_bound_authority_state()
            self.assertTrue(valid, error)
            self.assertGreater(count, 0)
        finally:
            output.unlink(missing_ok=True)
            if target.exists():
                import shutil
                shutil.rmtree(target)

    def test_authority_event_chain_detects_tampering(self) -> None:
        store = self.world._plural_store()
        self.assertGreater(len(store["authority_events"]), 0)
        store["authority_events"][0]["actor"] = "FORGED"
        self.world._write_json(self.world.plural_witness_path, store)
        valid, _count, error = self.world.verify_bound_authority_state()
        self.assertFalse(valid)
        self.assertIn("hash mismatch", error or "")


if __name__ == "__main__":
    unittest.main()
