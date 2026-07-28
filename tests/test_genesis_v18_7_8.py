from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_8_playable import PLAYABLE_VERSION, PlayableGenesisV1878


class HistoricalUnboughtVoiceTests(unittest.TestCase):
    def test_historical_version_is_frozen(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.8")

    @staticmethod
    def _claim(
        world: PlayableGenesisV1878,
        *,
        scope: str,
        reader_id: str,
        controller: str,
        text: str,
        index: int,
        campaign_id: str | None = None,
    ) -> str:
        world.register_influence_account(
            reader_id,
            identity_proof=f"identity-proof-{reader_id}-unique",
            controller_proof=controller,
            identity_provider="authenticated-test-provider",
            provider_verified=True,
            operator_disclosed=True,
        )
        origin = world.import_origin_bytes(
            repository="historical/unbought",
            commit="18.7.8",
            path=f"voice/{index}.json",
            raw=json.dumps({"statement": text}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        claim_id = world.record_reader_interpretation(
            origin["origin_key"],
            text,
            reader_id=reader_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            about="historical_unbought_voice",
            confidence=0.8,
            subject_scope_id=scope,
        )
        world.attest_claim_influence(
            claim_id,
            account_id=reader_id,
            evidence_proof=f"evidence-{index}-unique",
            campaign_id=campaign_id,
            campaign_disclosed=campaign_id is not None,
        )
        return claim_id

    def test_old_account_farm_and_disclosed_campaign_laws_remain_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV1878(Path(directory))
            scope = world.create_subject_scope(
                topic="historical_public_opinion",
                event="regression",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            farm = [
                self._claim(
                    world,
                    scope=scope,
                    reader_id=f"farm-{index}",
                    controller="one-controller",
                    text=f"Farm message {index}",
                    index=index,
                )
                for index in range(4)
            ]
            audit = world.audit_influence_claims(farm)
            self.assertEqual(audit["independent_voice_count"], 1)

            campaign = [
                self._claim(
                    world,
                    scope=scope,
                    reader_id=f"campaign-{index}",
                    controller=f"controller-{index}",
                    text=f"Campaign message {index}",
                    index=10 + index,
                    campaign_id="one-disclosed-campaign",
                )
                for index in range(3)
            ]
            campaign_audit = world.audit_influence_claims(campaign)
            self.assertEqual(campaign_audit["independent_voice_count"], 1)

    def test_old_unreviewed_accusation_does_not_silence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV1878(Path(directory))
            scope = world.create_subject_scope(
                topic="historical_dissent",
                event="regression",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            claim = self._claim(
                world,
                scope=scope,
                reader_id="dissent",
                controller="dissent-controller",
                text="Grounded dissent",
                index=99,
            )
            world.record_manipulation_evidence(
                claim,
                kind="IMPERSONATION",
                evidence="verifiable audit reference",
                reporter_id="reporter",
            )
            audit = world.audit_influence_claims([claim])
            self.assertEqual(audit["eligible_claim_ids"], [claim])


if __name__ == "__main__":
    unittest.main()
