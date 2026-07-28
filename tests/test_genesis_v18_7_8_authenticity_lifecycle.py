from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


class GenesisV1878AuthenticityLifecycleTests(unittest.TestCase):
    @staticmethod
    def _claim(
        world: PlayableGenesisV187,
        *,
        scope: str,
        index: int,
    ) -> str:
        reader_id = f"late-audit-{index}"
        world.register_influence_account(
            reader_id,
            identity_proof=f"late-identity-proof-{index}-unique",
            controller_proof=f"late-controller-proof-{index}-unique",
            identity_provider="authenticated-test-provider",
            provider_verified=True,
        )
        origin = world.import_origin_bytes(
            repository="public/late-audit",
            commit="v18.7.8",
            path=f"late/{index}.json",
            raw=json.dumps(
                {"statement": f"Независимое свидетельство {index}"},
                ensure_ascii=False,
            ).encode("utf-8"),
            source_public=True,
        )
        claim_id = world.record_reader_interpretation(
            origin["origin_key"],
            f"Независимое свидетельство {index}",
            reader_id=reader_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            about="late_authenticity_case",
            confidence=0.8,
            subject_scope_id=scope,
        )
        world.attest_claim_influence(
            claim_id,
            account_id=reader_id,
            evidence_proof=f"late-independent-evidence-{index}-unique",
        )
        return claim_id

    def test_late_confirmed_impersonation_breaks_quorum_and_defers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="late_authenticity",
                event="public consultation",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            claims = [self._claim(world, scope=scope, index=index) for index in range(3)]
            case_id = world.open_sovereign_case(claims, subject_scope_id=scope)

            record_id = world.record_manipulation_evidence(
                claims[0],
                kind="IMPERSONATION",
                evidence="Проверяемый журнал провайдера связывает аккаунт с подменой",
                reporter_id="authenticated-auditor",
            )
            world.confirm_manipulation_evidence(
                record_id,
                confirmed=True,
                rationale="JANUS.SOVEREIGN подтвердил подмену по привязанному журналу",
            )
            decision_id = world.janus_sovereign_decide(case_id)
            store = world._plural_store()
            case = store["sovereign_cases"][case_id]
            decision = store["sovereign_decisions"][decision_id]

            self.assertEqual(decision["ruling"], "DEFER_FOR_AUTHENTICITY_AUDIT")
            self.assertFalse(decision["canonical_record_decided"])
            self.assertEqual(case["status"], "OPEN_FOR_AUTHENTICITY_EVIDENCE")
            self.assertEqual(set(decision["dissent_preserved"]), set(claims))
            self.assertIn(claims[0], decision["quarantined_claim_ids"])
            self.assertFalse(decision["reach_counted_as_evidence"])
            self.assertFalse(decision["truth_verdict_inferred"])
            self.assertTrue(world.verify_unbought_voice_state()[0])


if __name__ == "__main__":
    unittest.main()
