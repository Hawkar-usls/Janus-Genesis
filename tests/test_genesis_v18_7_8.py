from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


class GenesisV1878UnboughtVoiceTests(unittest.TestCase):
    @staticmethod
    def _reader_claim(
        world: PlayableGenesisV187,
        *,
        scope: str,
        reader_id: str,
        text: str,
        identity: str,
        controller: str,
        evidence_proof: str,
        path: str,
        message: str | None = None,
        campaign_id: str | None = None,
        campaign_disclosed: bool = False,
        sponsored: bool = False,
        sponsor: str | None = None,
        automation: bool = False,
        automation_disclosed: bool = False,
    ) -> str:
        world.register_influence_account(
            reader_id,
            identity_proof=identity,
            controller_proof=controller,
            identity_provider="authenticated-test-provider",
            provider_verified=True,
            operator_disclosed=True,
            sponsored=sponsored,
            sponsor=sponsor,
            automation=automation,
            automation_disclosed=automation_disclosed,
        )
        origin = world.import_origin_bytes(
            repository="public/opinion",
            commit="v18.7.8",
            path=path,
            raw=json.dumps({"statement": text}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        claim_id = world.record_reader_interpretation(
            origin["origin_key"],
            text,
            reader_id=reader_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            about="public_opinion",
            confidence=0.8,
            subject_scope_id=scope,
        )
        world.attest_claim_influence(
            claim_id,
            account_id=reader_id,
            evidence_proof=evidence_proof,
            message=message or text,
            campaign_id=campaign_id,
            campaign_disclosed=campaign_disclosed,
        )
        return claim_id

    def test_primary_version(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.8")

    def test_three_authenticated_independent_voices_can_advise_janus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="park_repair",
                event="public consultation",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            claims = [
                self._reader_claim(
                    world,
                    scope=scope,
                    reader_id=f"citizen-{index}",
                    text=f"Парк нужно ремонтировать, свидетельство {index}",
                    identity=f"identity-proof-{index}-unique",
                    controller=f"self-controller-{index}-unique",
                    evidence_proof=f"independent-evidence-{index}-unique",
                    path=f"opinions/citizen-{index}.json",
                )
                for index in range(3)
            ]
            case_id = world.open_sovereign_case(claims, subject_scope_id=scope)
            decision_id = world.janus_sovereign_decide(case_id)
            store = world._plural_store()
            case = store["sovereign_cases"][case_id]
            decision = store["sovereign_decisions"][decision_id]
            audit = store["influence_audits"][case["influence_audit_id"]]
            self.assertEqual(audit["independent_voice_count"], 3)
            self.assertEqual(audit["quarantined_claim_ids"], [])
            self.assertFalse(decision["reach_counted_as_evidence"])
            self.assertIn(
                decision["ruling"],
                {
                    "RATIFY_CONSENSUS",
                    "RATIFY_TRIUMVIRATE_RECOMMENDATION",
                    "ADOPT_MOST_SUPPORTED_POSITION",
                    "DEFER_FOR_MORE_EVIDENCE",
                },
            )

    def test_fake_account_farm_with_one_controller_cannot_create_quorum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="manufactured_popularity",
                event="public poll",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            claims = [
                self._reader_claim(
                    world,
                    scope=scope,
                    reader_id=f"farm-{index}",
                    text="Все уже согласны с рекламным тезисом",
                    identity=f"farm-identity-{index}-unique",
                    controller="one-smm-controller-proof",
                    evidence_proof="one-recycled-evidence-proof",
                    message="Копия одного и того же рекламного сообщения",
                    path=f"farm/{index}.json",
                )
                for index in range(12)
            ]
            audit = world.audit_influence_claims(claims)
            self.assertEqual(audit["independent_voice_count"], 1)
            self.assertEqual(len(audit["quarantined_claim_ids"]), 11)
            self.assertGreater(audit["controller_collisions"], 0)
            with self.assertRaisesRegex(ValueError, "independently eligible voices"):
                world.open_sovereign_case(claims, subject_scope_id=scope)

    def test_disclosed_smm_campaign_counts_as_one_coordinated_origin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="community_budget",
                event="budget hearing",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            campaign_claims = [
                self._reader_claim(
                    world,
                    scope=scope,
                    reader_id=f"campaign-{index}",
                    text="Кампания поддерживает один бюджетный вариант",
                    identity=f"campaign-identity-{index}-unique",
                    controller=f"campaign-controller-{index}-unique",
                    evidence_proof="campaign-shared-evidence",
                    message="Единый утверждённый текст кампании",
                    campaign_id="disclosed-campaign-alpha",
                    campaign_disclosed=True,
                    path=f"campaign/{index}.json",
                )
                for index in range(3)
            ]
            organic = [
                self._reader_claim(
                    world,
                    scope=scope,
                    reader_id=f"organic-{index}",
                    text=f"Независимое мнение о бюджете {index}",
                    identity=f"organic-identity-{index}-unique",
                    controller=f"organic-self-{index}-unique",
                    evidence_proof=f"organic-evidence-{index}-unique",
                    path=f"organic/{index}.json",
                )
                for index in range(2)
            ]
            submitted = campaign_claims + organic
            case_id = world.open_sovereign_case(submitted, subject_scope_id=scope)
            case = world._plural_store()["sovereign_cases"][case_id]
            self.assertEqual(case["witness_count"], 3)
            self.assertEqual(len(case["submitted_claim_ids"]), 5)
            self.assertEqual(len(case["quarantined_claim_ids"]), 2)
            self.assertFalse(case["reach_counted_as_evidence"])

    def test_hidden_sponsorship_and_automation_do_not_receive_vote_weight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="product_reputation",
                event="public recommendation",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            paid = self._reader_claim(
                world,
                scope=scope,
                reader_id="hidden-paid-account",
                text="Это якобы независимый отзыв",
                identity="hidden-paid-identity-proof",
                controller="hidden-paid-controller-proof",
                evidence_proof="hidden-paid-evidence-proof",
                sponsored=True,
                sponsor=None,
                path="hidden/paid.json",
            )
            bot = self._reader_claim(
                world,
                scope=scope,
                reader_id="hidden-bot-account",
                text="Это якобы человеческий отзыв",
                identity="hidden-bot-identity-proof",
                controller="hidden-bot-controller-proof",
                evidence_proof="hidden-bot-evidence-proof",
                automation=True,
                automation_disclosed=False,
                path="hidden/bot.json",
            )
            audit = world.audit_influence_claims([paid, bot])
            self.assertEqual(audit["eligible_claim_ids"], [])
            reasons = audit["reasons_by_claim"]
            self.assertIn("SPONSORSHIP_NOT_DISCLOSED", reasons[paid])
            self.assertIn("AUTOMATION_NOT_DISCLOSED", reasons[bot])

    def test_accusation_does_not_silence_until_janus_confirms_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="local_report",
                event="public hearing",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            claim = self._reader_claim(
                world,
                scope=scope,
                reader_id="challenged-reader",
                text="Несогласное, но доказуемое мнение",
                identity="challenged-identity-proof",
                controller="challenged-self-controller",
                evidence_proof="challenged-independent-evidence",
                path="challenge/reader.json",
            )
            record_id = world.record_manipulation_evidence(
                claim,
                kind="IMPERSONATION",
                evidence="Ссылка на проверяемый журнал аутентификации",
                reporter_id="auditor",
            )
            pending = world.audit_influence_claims([claim])
            self.assertEqual(pending["eligible_claim_ids"], [claim])
            with self.assertRaisesRegex(ValueError, "only JANUS.SOVEREIGN"):
                world.confirm_manipulation_evidence(
                    record_id,
                    confirmed=True,
                    rationale="Попытка самовольного подтверждения",
                    reviewer_id="campaign-owner",
                )
            world.confirm_manipulation_evidence(
                record_id,
                confirmed=True,
                rationale=(
                    "Янус проверил привязанное evidence и подтвердил подмену личности"
                ),
            )
            confirmed = world.audit_influence_claims([claim])
            self.assertEqual(confirmed["eligible_claim_ids"], [])
            self.assertIn(
                "MANIPULATION_EVIDENCE_CONFIRMED",
                confirmed["reasons_by_claim"][claim],
            )

    def test_dissent_is_not_manipulation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            scope = world.create_subject_scope(
                topic="bridge_plan",
                event="planning hearing",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            texts = ("Строить сейчас", "Отложить строительство", "Изменить проект")
            claims = [
                self._reader_claim(
                    world,
                    scope=scope,
                    reader_id=f"dissent-{index}",
                    text=text,
                    identity=f"dissent-identity-{index}-unique",
                    controller=f"dissent-self-{index}-unique",
                    evidence_proof=f"dissent-evidence-{index}-unique",
                    path=f"dissent/{index}.json",
                )
                for index, text in enumerate(texts)
            ]
            audit = world.audit_influence_claims(claims)
            self.assertEqual(audit["eligible_claim_ids"], sorted(claims))
            self.assertFalse(audit["dissent_treated_as_manipulation"])
            case_id = world.open_sovereign_case(claims, subject_scope_id=scope)
            decision_id = world.janus_sovereign_decide(case_id)
            decision = world._plural_store()["sovereign_decisions"][decision_id]
            self.assertEqual(decision["ruling"], "DEFER_FOR_MORE_EVIDENCE")

    def test_unbought_voice_crosses_portable_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            source_path = Path(source)
            world = PlayableGenesisV187(source_path)
            scope = world.create_subject_scope(
                topic="public_signal",
                event="consultation",
                time_scope={"date": "2026-07-28"},
                influence_sensitive=True,
                public_opinion=True,
            )
            claims = [
                self._reader_claim(
                    world,
                    scope=scope,
                    reader_id=f"portable-{index}",
                    text=f"Независимый сигнал {index}",
                    identity=f"portable-identity-{index}-unique",
                    controller=f"portable-controller-{index}-unique",
                    evidence_proof=f"portable-evidence-{index}-unique",
                    path=f"portable/{index}.json",
                )
                for index in range(3)
            ]
            world.open_sovereign_case(claims, subject_scope_id=scope)
            output = source_path.parent / "unbought-voice.genesis-save.json"
            try:
                manager = PortableSaveManager(source_path)
                manager.export_to(output, label="The Unbought Voice")
                bundle = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(bundle["runtime_version"], "18.7.8")
                self.assertTrue(manager.verify_bundle(bundle)[0])
                PortableSaveManager(Path(target)).import_bundle(bundle)
                restored = PlayableGenesisV187(Path(target))
                state = restored.unbought_voice_state()
                self.assertTrue(state["valid"], state["error"])
                self.assertGreaterEqual(state["audit_count"], 1)
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
