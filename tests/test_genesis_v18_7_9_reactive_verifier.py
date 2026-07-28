from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_9 import (
    build_provider_attestation,
    build_sovereign_capability,
    generate_ed25519_keypair,
)
from genesis_v18_7_playable import PlayableGenesisV187

ISSUED = "2026-01-01T00:00:00Z"
EXPIRES = "2099-01-01T00:00:00Z"


class ReactiveVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.world = PlayableGenesisV187(Path(self.temp.name))
        self.provider_private, provider_public = generate_ed25519_keypair()
        self.sovereign_private, sovereign_public = generate_ed25519_keypair()
        self.world.register_trusted_provider_key(
            "reactive-provider",
            key_id="provider-key",
            public_key_b64=provider_public,
            valid_from=ISSUED,
            valid_until=EXPIRES,
        )
        self.world.register_sovereign_key(
            key_id="sovereign-key",
            public_key_b64=sovereign_public,
            valid_from=ISSUED,
            valid_until=EXPIRES,
        )
        self.counter = 0

    def _claim(self, scope_id: str, reader_id: str) -> str:
        self.counter += 1
        account_private, account_public = generate_ed25519_keypair()
        del account_private
        identity = f"identity-{reader_id}"
        controller = f"controller-{reader_id}"
        provider_attestation = build_provider_attestation(
            provider_id="reactive-provider",
            key_id="provider-key",
            account_id=reader_id,
            identity_proof=identity,
            controller_proof=controller,
            account_public_key_b64=account_public,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            nonce=f"provider-nonce-{reader_id}",
            private_key_b64=self.provider_private,
        )
        self.world.register_influence_account(
            reader_id,
            identity_proof=identity,
            controller_proof=controller,
            provider_attestation=provider_attestation,
        )
        text = f"Grounded reactive position {reader_id}"
        origin = self.world.import_origin_bytes(
            repository="reactive/verifier",
            commit="18.7.9",
            path=f"claims/{self.counter}.json",
            raw=json.dumps({"statement": text}).encode("utf-8"),
            source_public=True,
        )
        claim_id = self.world.record_reader_interpretation(
            origin["origin_key"],
            text,
            reader_id=reader_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            subject_scope_id=scope_id,
        )
        self.world.attest_claim_influence(
            claim_id,
            account_id=reader_id,
            evidence_proof=f"evidence-{reader_id}",
        )
        return claim_id

    def _case(self) -> tuple[str, list[str]]:
        scope_id = self.world.create_subject_scope(
            topic="reactive verifier",
            event="eligibility changes",
            time_scope={"date": "2026-07-28"},
            influence_sensitive=True,
            public_opinion=True,
        )
        claims = [self._claim(scope_id, f"reader-{index}") for index in range(3)]
        case_id = self.world.open_sovereign_case(claims, subject_scope_id=scope_id)
        capability = build_sovereign_capability(
            key_id="sovereign-key",
            scope="sovereign_case_decision",
            case_id=case_id,
            nonce=f"decision-{case_id}",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.sovereign_private,
        )
        self.world.janus_sovereign_decide(case_id, capability=capability)
        return case_id, claims

    def test_withdrawal_reopening_with_two_voices_is_valid(self) -> None:
        case_id, _claims = self._case()
        self.world.withdraw_witness_voice("reader-0")
        store = self.world._plural_store()
        case = store["sovereign_cases"][case_id]
        self.assertEqual(case["status"], "CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE")
        self.assertEqual(case["witness_count"], 2)
        self.assertIsNone(case["janus_decision_id"])
        valid, _count, error = self.world.verify_bound_authority_state()
        self.assertTrue(valid, error)

    def test_provider_compromise_reopening_with_zero_voices_is_valid(self) -> None:
        case_id, _claims = self._case()
        self.world.revoke_trusted_provider_key(
            "reactive-provider",
            "provider-key",
            reason="retrospective compromise",
            compromised_from="2025-12-31T00:00:00Z",
        )
        case = self.world._plural_store()["sovereign_cases"][case_id]
        self.assertEqual(case["status"], "CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE")
        self.assertEqual(case["witness_count"], 0)
        valid, _count, error = self.world.verify_bound_authority_state()
        self.assertTrue(valid, error)

    def test_reopened_low_quorum_case_cannot_keep_active_decision(self) -> None:
        case_id, _claims = self._case()
        self.world.withdraw_witness_voice("reader-0")
        store = self.world._plural_store()
        case = store["sovereign_cases"][case_id]
        case["janus_decision_id"] = next(iter(store["sovereign_decisions"]))
        self.world._write_json(self.world.plural_witness_path, store)
        valid, _count, error = self.world.verify_bound_authority_state()
        self.assertFalse(valid)
        self.assertIn("retains active sovereign decision", error or "")

    def test_reopened_low_quorum_case_requires_matching_audit_and_provenance(self) -> None:
        case_id, _claims = self._case()
        self.world.withdraw_witness_voice("reader-0")
        store = self.world._plural_store()
        store["sovereign_cases"][case_id]["history"][-1].pop("reason", None)
        self.world._write_json(self.world.plural_witness_path, store)
        valid, _count, error = self.world.verify_bound_authority_state()
        self.assertFalse(valid)
        self.assertIn("provenance lacks audit or reason", error or "")


if __name__ == "__main__":
    unittest.main()
