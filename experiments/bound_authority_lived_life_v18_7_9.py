# -*- coding: utf-8 -*-
"""Live Genesis v18.7.9 as an ordinary citizen under Bound Authority.

This is an evidence-only life. Provider and sovereign private keys exist only in
this process as stand-ins for external signing services and are never written to
Genesis state, logs, summaries or portable saves.
"""
from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from genesis_v18_7_9 import (
    ASSESSMENT_COMPONENTS,
    build_delegation,
    build_provider_attestation,
    build_sovereign_capability,
    generate_ed25519_keypair,
)
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

ISSUED = "2026-01-01T00:00:00Z"
EXPIRES = "2099-01-01T00:00:00Z"
PLAYER_ID = "ordinary-citizen-bound-authority"
DISPLAY_NAME = "Обычный гражданин под связанной властью"

ORDINARY_GOOD = (
    "помочь соседям починить крышу без требования благодарности",
    "принести воду в общий сад и оставить проход открытым",
    "поддержать уставшего коллегу и спокойно закончить свою смену",
    "посадить дерево возле дома и договориться об общем уходе",
    "починить свет в подъезде вместе с жильцами",
    "приготовить еду для общей кухни и оставить выбор свободным",
    "защитить право соседа отказаться от разговора",
    "поделиться инструментами и вернуть их владельцу вовремя",
    "помочь убрать двор и не превращать помощь в долг",
)

ORDINARY_NEUTRAL = (
    "проснуться по будильнику, приготовить чай и проверить ключи",
    "записать расходы дня без паники и обвинений",
    "вернуться с работы и дать себе двадцать минут тишины",
    "купить продукты по списку и не брать лишнего",
    "постирать одежду и оставить незавершённое на завтра",
    "пройти вокруг дома и посмотреть на вечерние окна",
    "ответить на рабочее сообщение без изображения всезнания",
    "лечь спать вовремя, хотя список дел ещё не закончился",
)

TOPICS = (
    "мост",
    "сад",
    "музыка",
    "карта",
    "ремонт",
    "вода",
    "дорога",
    "тишина",
    "дом",
    "работа",
    "письмо",
)


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _check_tuple(result: Any) -> dict[str, Any]:
    if isinstance(result, (tuple, list)):
        return {
            "valid": bool(result[0]) if result else False,
            "count": int(result[1]) if len(result) > 1 and isinstance(result[1], int) else result[1] if len(result) > 1 else None,
            "error": result[2] if len(result) > 2 else None,
        }
    return {"valid": bool(result), "count": None, "error": None}


class LivedAudit:
    def __init__(self, work_root: Path, artifact_root: Path) -> None:
        self.work_root = work_root
        self.artifact_root = artifact_root
        self.primary_dir = work_root / "world-primary"
        self.restored_dir = work_root / "world-restored"
        self.midpoint_save = artifact_root / "bound-authority-midpoint.genesis-save.json"
        self.final_save = artifact_root / "bound-authority-lived-final.genesis-save.json"
        self.summary_path = artifact_root / "bound_authority_lived_life_summary.json"
        self.log_path = artifact_root / "bound-authority-lived-life.log"
        self.events_path = artifact_root / "bound_authority_security_events.json"
        self.log_lines: list[str] = []
        self.actions: list[dict[str, Any]] = []
        self.security_events: list[dict[str, Any]] = []
        self.findings: list[dict[str, Any]] = []
        self.claim_counter = 0
        self.account_private: dict[str, str] = {}
        self.account_public: dict[str, str] = {}
        self.provider_private: dict[str, str] = {}
        self.provider_public: dict[str, str] = {}
        self.provider_keys: dict[str, str] = {}
        self.sovereign_private = ""
        self.sovereign_public = ""
        self.sovereign_key_id = "sovereign-lived-key-1"
        self.world = PlayableGenesisV187(self.primary_dir)
        self.world.set_display_name(PLAYER_ID, DISPLAY_NAME)
        self.world.set_free_other_seed_for_testing("bound-authority-ordinary-citizen-life")
        self.handle = self.world.public_state(PLAYER_ID)["free_other_handles"][0]

    def log(self, text: str) -> None:
        self.log_lines.append(text)
        print(text)

    def security(self, name: str, passed: bool, **details: Any) -> None:
        event = {"name": name, "passed": bool(passed), **details}
        self.security_events.append(event)
        self.log(f"[SECURITY] {name}: {'PASS' if passed else 'FAIL'} — {json.dumps(details, ensure_ascii=False, sort_keys=True)}")

    def finding(self, finding_id: str, severity: str, title: str, evidence: str, recommendation: str) -> None:
        item = {
            "finding_id": finding_id,
            "severity": severity,
            "title": title,
            "evidence": evidence,
            "recommendation": recommendation,
        }
        self.findings.append(item)
        self.log(f"[FINDING:{severity}] {title} — {evidence}")

    def ordinary_days(self, start: int, end: int) -> None:
        for day in range(start, end + 1):
            day_actions = (
                ORDINARY_NEUTRAL[(day - 1) % len(ORDINARY_NEUTRAL)],
                ORDINARY_GOOD[(day - 1) % len(ORDINARY_GOOD)],
                f"предложить @{self.handle} поговорить о теме {TOPICS[(day - 1) % len(TOPICS)]}, день {day}",
            )
            for slot, action in enumerate(day_actions, 1):
                result = self.world.process_action(PLAYER_ID, action)
                record = {
                    "day": day,
                    "slot": slot,
                    "action": action,
                    "status": result.status,
                    "narrative": result.narrative,
                }
                self.actions.append(record)
                self.log(f"DAY {day:02d}.{slot}: {action}\n  → {result.status}: {result.narrative}")

    def install_trust_roots(self) -> None:
        for provider_id in ("provider-alpha", "provider-beta"):
            private, public = generate_ed25519_keypair()
            key_id = f"{provider_id}-key-1"
            self.provider_private[provider_id] = private
            self.provider_public[provider_id] = public
            self.provider_keys[provider_id] = key_id
            self.world.register_trusted_provider_key(
                provider_id,
                key_id=key_id,
                public_key_b64=public,
                valid_from=ISSUED,
                valid_until=EXPIRES,
            )
        self.sovereign_private, self.sovereign_public = generate_ed25519_keypair()
        self.world.register_sovereign_key(
            key_id=self.sovereign_key_id,
            public_key_b64=self.sovereign_public,
            valid_from=ISSUED,
            valid_until=EXPIRES,
        )
        self.security("trust_roots_installed", True, provider_count=2, private_keys_persisted=False)

    def provider_attestation(
        self,
        account_id: str,
        *,
        provider_id: str,
        identity_proof: str,
        controller_proof: str,
        public_key: str,
        nonce: str,
    ) -> dict[str, Any]:
        return build_provider_attestation(
            provider_id=provider_id,
            key_id=self.provider_keys[provider_id],
            account_id=account_id,
            identity_proof=identity_proof,
            controller_proof=controller_proof,
            account_public_key_b64=public_key,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            nonce=nonce,
            private_key_b64=self.provider_private[provider_id],
        )

    def register_account(
        self,
        account_id: str,
        *,
        provider_id: str = "provider-alpha",
        controller: str | None = None,
    ) -> dict[str, Any]:
        identity = f"identity-proof-{account_id}-lived"
        controller_proof = controller or f"controller-proof-{account_id}-lived"
        private, public = generate_ed25519_keypair()
        self.account_private[account_id] = private
        self.account_public[account_id] = public
        attestation = self.provider_attestation(
            account_id,
            provider_id=provider_id,
            identity_proof=identity,
            controller_proof=controller_proof,
            public_key=public,
            nonce=f"provider-nonce-{account_id}",
        )
        self.world.register_influence_account(
            account_id,
            identity_proof=identity,
            controller_proof=controller_proof,
            provider_attestation=attestation,
            operator_disclosed=True,
        )
        return {
            "identity": identity,
            "controller": controller_proof,
            "provider_id": provider_id,
            "attestation": attestation,
        }

    def scope(self, topic: str, *, event: str | None = None) -> str:
        return self.world.create_subject_scope(
            topic=topic,
            event=event or topic,
            time_scope={"date": "2026-07-28"},
            location="ordinary-city",
            influence_sensitive=True,
            public_opinion=True,
        )

    def claim(
        self,
        *,
        scope_id: str,
        account_id: str,
        text: str,
        provider_id: str = "provider-alpha",
        controller: str | None = None,
        campaign_id: str | None = None,
        register: bool = True,
        claimant_confidence: float | None = None,
        attester_id: str | None = None,
        delegation_id: str | None = None,
    ) -> str:
        if register:
            self.register_account(account_id, provider_id=provider_id, controller=controller)
        self.claim_counter += 1
        origin = self.world.import_origin_bytes(
            repository="lived/bound-authority",
            commit="18.7.9",
            path=f"claims/{self.claim_counter:03d}-{account_id}.json",
            raw=json.dumps({"statement": text}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        claim_id = self.world.record_reader_interpretation(
            origin["origin_key"],
            text,
            reader_id=account_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            about="bound_authority_lived_life",
            claimant_stated_confidence=claimant_confidence,
            subject_scope_id=scope_id,
        )
        actual_attester = attester_id or account_id
        self.world.attest_claim_influence(
            claim_id,
            account_id=actual_attester,
            evidence_proof=f"lived-evidence-{self.claim_counter}-{account_id}",
            message=text,
            campaign_id=campaign_id,
            campaign_disclosed=campaign_id is not None,
            delegation_id=delegation_id,
        )
        return claim_id

    def capability(self, scope: str, case_id: str, nonce: str) -> dict[str, Any]:
        return build_sovereign_capability(
            key_id=self.sovereign_key_id,
            scope=scope,
            case_id=case_id,
            nonce=nonce,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.sovereign_private,
        )

    @staticmethod
    def assessment(value: float) -> dict[str, float]:
        return {name: value for name in ASSESSMENT_COMPONENTS}

    def pre_midpoint_security(self) -> dict[str, Any]:
        genuine_scope = self.scope("repair_the_public_bridge", event="winter bridge inspection")
        genuine_claims = [
            self.claim(
                scope_id=genuine_scope,
                account_id=f"genuine-{index}",
                text="Общий мост нужно безопасно отремонтировать до зимы",
            )
            for index in range(3)
        ]
        genuine_case = self.world.open_sovereign_case(genuine_claims, subject_scope_id=genuine_scope)
        self.security("three_signed_independent_voices_open_case", True, case_id=genuine_case)

        replay_account = self.register_account("replay-account")
        try:
            self.world.register_influence_account(
                "replay-account",
                identity_proof=replay_account["identity"],
                controller_proof=replay_account["controller"],
                provider_attestation=replay_account["attestation"],
            )
        except ValueError as exc:
            replay_blocked = "REPLAYED" in str(exc)
        else:
            replay_blocked = False
        self.security("provider_attestation_replay_blocked", replay_blocked)
        assert replay_blocked

        tampered = dict(replay_account["attestation"])
        tampered["subject_id"] = "tampered-subject"
        try:
            self.world.register_influence_account(
                "tampered-subject",
                identity_proof=replay_account["identity"],
                controller_proof=replay_account["controller"],
                provider_attestation=tampered,
            )
        except ValueError as exc:
            tamper_blocked = True
            tamper_reason = str(exc)
        else:
            tamper_blocked = False
            tamper_reason = "tampered payload was accepted"
        self.security(
            "provider_attestation_tampering_blocked",
            tamper_blocked,
            rejection_reason=tamper_reason,
        )
        assert tamper_blocked

        shard_scope = self.scope("campaign_sharding", event="manufactured public campaign")
        shared_controller = "one-controller-split-across-campaigns"
        shard_claims = [
            self.claim(
                scope_id=shard_scope,
                account_id=f"shard-{index}",
                controller=shared_controller,
                campaign_id=f"campaign-fragment-{index}",
                text=f"Кампания {index} требует одного и того же решения",
            )
            for index in range(3)
        ]
        shard_audit = self.world.audit_influence_claims(shard_claims)
        shard_passed = shard_audit["independent_voice_count"] == 1 and shard_audit["controller_outranks_campaign"]
        self.security(
            "campaign_never_hides_controller",
            shard_passed,
            submitted=3,
            independent=shard_audit["independent_voice_count"],
            controller_collisions=shard_audit["controller_collisions"],
        )
        assert shard_passed

        delegation_scope = self.scope("delegated_attestation", event="citizen asks advocate to carry proof")
        self.register_account("delegating-speaker")
        self.register_account("delegated-attester")
        self.claim_counter += 1
        origin = self.world.import_origin_bytes(
            repository="lived/bound-authority",
            commit="18.7.9",
            path=f"claims/{self.claim_counter:03d}-delegated.json",
            raw=json.dumps({"statement": "Мой голос передан только для этого свидетельства"}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        delegated_claim = self.world.record_reader_interpretation(
            origin["origin_key"],
            "Мой голос передан только для этого свидетельства",
            reader_id="delegating-speaker",
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            subject_scope_id=delegation_scope,
        )
        try:
            self.world.attest_claim_influence(
                delegated_claim,
                account_id="delegated-attester",
                evidence_proof="delegation-attempt-without-authority",
            )
        except ValueError:
            laundering_blocked = True
        else:
            laundering_blocked = False
        delegation = build_delegation(
            delegator="delegating-speaker",
            delegate="delegated-attester",
            key_id="speaker-key",
            scope="voice_attestation",
            claim_id=delegated_claim,
            nonce="one-claim-delegation",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.account_private["delegating-speaker"],
        )
        delegation_id = self.world.register_attestation_delegation(delegation)
        self.world.attest_claim_influence(
            delegated_claim,
            account_id="delegated-attester",
            evidence_proof="delegated-authorized-evidence",
            delegation_id=delegation_id,
        )
        delegated_audit = self.world.audit_influence_claims([delegated_claim])
        delegation_passed = laundering_blocked and delegated_audit["independent_voice_count"] == 1
        self.security("actor_attestation_binding_and_scoped_delegation", delegation_passed)
        assert delegation_passed

        return {
            "genuine_case": genuine_case,
            "genuine_claims": genuine_claims,
            "shard_audit": shard_audit,
            "delegation_id": delegation_id,
        }

    def portable_midpoint(self) -> dict[str, Any]:
        result = PortableSaveManager(self.primary_dir).export_to(
            self.midpoint_save,
            label="Bound Authority ordinary citizen midpoint",
        )
        text = self.midpoint_save.read_text(encoding="utf-8")
        leaked = any(
            secret and secret in text
            for secret in (
                list(self.provider_private.values())
                + [self.sovereign_private]
                + list(self.account_private.values())
            )
        )
        bundle = json.loads(text)
        imported = PortableSaveManager(self.restored_dir).import_bundle(bundle)
        self.world = PlayableGenesisV187(self.restored_dir)
        valid, count, error = self.world.verify_bound_authority_state()
        passed = not leaked and result["contains_private_keys"] is False and imported["contains_private_keys"] is False and valid
        self.security(
            "portable_midpoint_preserves_public_authority_without_private_keys",
            passed,
            files=result["file_count"],
            authority_events=count,
            error=error,
        )
        assert passed
        return {"export": result, "import": imported, "authority_events": count}

    def post_midpoint_security(self, pre: dict[str, Any]) -> dict[str, Any]:
        genuine_case = pre["genuine_case"]
        capability = self.capability("sovereign_case_decision", genuine_case, "genuine-decision-once")
        decision_id = self.world.janus_sovereign_decide(genuine_case, capability=capability)
        decision = self.world._plural_store()["sovereign_decisions"][decision_id]
        self.security(
            "signed_sovereign_capability_decides_after_portable_restore",
            decision["sovereign_capability_bound"],
            ruling=decision["ruling"],
        )
        try:
            self.world.janus_sovereign_decide(genuine_case, capability=capability)
        except ValueError as exc:
            sovereign_replay_blocked = "REPLAYED" in str(exc)
        else:
            sovereign_replay_blocked = False
        self.security("sovereign_capability_replay_blocked", sovereign_replay_blocked)
        assert sovereign_replay_blocked

        expired = build_sovereign_capability(
            key_id=self.sovereign_key_id,
            scope="sovereign_case_decision",
            case_id=genuine_case,
            nonce="expired-capability",
            issued_at="2020-01-01T00:00:00Z",
            expires_at="2021-01-01T00:00:00Z",
            private_key_b64=self.sovereign_private,
        )
        try:
            self.world.janus_sovereign_decide(genuine_case, capability=expired)
        except ValueError as exc:
            expired_blocked = "EXPIRED" in str(exc)
        else:
            expired_blocked = False
        self.security("expired_sovereign_capability_blocked", expired_blocked)
        assert expired_blocked

        ghost_scope = self.scope("ghost_voting", event="neighbourhood schedule")
        ghost_claims = [
            self.claim(scope_id=ghost_scope, account_id=f"ghost-live-{index}", text=f"Предложение графика {index}")
            for index in range(3)
        ]
        ghost_case = self.world.open_sovereign_case(ghost_claims, subject_scope_id=ghost_scope)
        self.world.janus_sovereign_decide(
            ghost_case,
            capability=self.capability("sovereign_case_decision", ghost_case, "ghost-before-withdrawal"),
        )
        self.world.withdraw_witness_voice("ghost-live-0")
        ghost_state = self.world._plural_store()["sovereign_cases"][ghost_case]
        ghost_passed = ghost_state["status"] == "CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE" and ghost_state["witness_count"] == 2
        self.security("withdrawal_ends_future_weight_and_reopens_case", ghost_passed, witness_count=ghost_state["witness_count"])
        assert ghost_passed

        appeal_scope = self.scope("appeal_restoration", event="mistaken identity review")
        appeal_claim = self.claim(
            scope_id=appeal_scope,
            account_id="appeal-citizen",
            text="Я присутствовал лично и прошу сохранить несогласие",
        )
        record_id = self.world.record_manipulation_evidence(
            appeal_claim,
            kind="IMPERSONATION",
            evidence="Первоначальная, но неполная запись проверки",
            reporter_id="auditor-one",
        )
        self.world.confirm_manipulation_evidence(
            record_id,
            confirmed=True,
            rationale="Первоначальное решение по неполным данным",
            capability=self.capability("manipulation_review", record_id, "appeal-initial-review"),
        )
        excluded = not self.world.recalculate_eligibility(appeal_claim, reason="confirmed_finding")
        self.world.appeal_manipulation_evidence(
            record_id,
            appellant_id="appeal-citizen",
            grounds="Подписанный журнал провайдера подтверждает личность",
        )
        self.world.resolve_manipulation_appeal(
            record_id,
            restored=True,
            rationale="Обвинение отменено после проверки полного журнала",
            capability=self.capability("manipulation_appeal", record_id, "appeal-restoration"),
        )
        restored = self.world.recalculate_eligibility(appeal_claim, reason="appeal_restored")
        store = self.world._plural_store()
        chain = [
            event["event_type"]
            for event in store["authority_events"]
            if event["subject_id"] == record_id
            and event["event_type"] in {"PENDING_REVIEW", "CONFIRMED", "APPEALED", "RESTORED"}
        ]
        appeal_passed = excluded and restored and chain == ["PENDING_REVIEW", "CONFIRMED", "APPEALED", "RESTORED"]
        self.security("append_only_appeal_restores_voice", appeal_passed, event_chain=chain)
        assert appeal_passed

        confidence_scope = self.scope("claimant_confidence", event="three incompatible construction proposals")
        confidence_claims = [
            self.claim(
                scope_id=confidence_scope,
                account_id="confidence-one",
                text="Построить высокую стену",
                claimant_confidence=1.0,
            ),
            self.claim(
                scope_id=confidence_scope,
                account_id="confidence-two",
                text="Оставить проход открытым",
                claimant_confidence=0.0,
            ),
            self.claim(
                scope_id=confidence_scope,
                account_id="confidence-three",
                text="Сначала провести дополнительную проверку",
                claimant_confidence=0.0,
            ),
        ]
        confidence_case = self.world.open_sovereign_case(confidence_claims, subject_scope_id=confidence_scope)
        neutral_decision_id = self.world.janus_sovereign_decide(
            confidence_case,
            capability=self.capability("sovereign_case_decision", confidence_case, "claimant-confidence-ignored"),
        )
        neutral_decision = self.world._plural_store()["sovereign_decisions"][neutral_decision_id]
        confidence_passed = neutral_decision["ruling"] == "DEFER_FOR_MORE_EVIDENCE" and not neutral_decision["claimant_confidence_used"]
        self.security("claimant_confidence_has_no_sovereign_weight", confidence_passed, ruling=neutral_decision["ruling"])
        assert confidence_passed

        # Adversarial in-process boundary: assessment authority is still a caller-supplied string.
        for index, claim_id in enumerate(confidence_claims):
            self.world.record_evidence_assessment(
                claim_id,
                components=self.assessment(1.0 if index == 0 else 0.1),
                assessor_id=PLAYER_ID,
                method_id="ordinary-citizen-self-appointed-assessor",
                method_version="1",
                evidence_ids=[f"self-appointed-evidence-{index}"],
                explanation="Обычный вызывающий код назначил собственную оценку",
            )
        injected_decision_id = self.world.janus_sovereign_decide(
            confidence_case,
            capability=self.capability("sovereign_case_decision", confidence_case, "assessment-injection-decision"),
        )
        injected_decision = self.world._plural_store()["sovereign_decisions"][injected_decision_id]
        assessor_injection_reproduced = injected_decision["ruling"] == "ADOPT_MOST_SUPPORTED_POSITION"
        self.security(
            "untrusted_in_process_assessor_can_supply_sovereign_weight",
            not assessor_injection_reproduced,
            reproduced=assessor_injection_reproduced,
            ruling=injected_decision["ruling"],
        )
        if assessor_injection_reproduced:
            self.finding(
                "BA-179-LIVED-001",
                "CRITICAL_IF_EXPOSED",
                "Evidence assessor authority is not cryptographically bound",
                "An ordinary in-process caller supplied assessor_id, method and all six components; Janus then adopted that position.",
                "Require a signed assessor attestation or a sovereign capability bound to the exact assessment payload, claim, method and evidence set.",
            )

        revocation_scope = self.scope("provider_key_revocation", event="late provider compromise")
        revocation_claims = [
            self.claim(
                scope_id=revocation_scope,
                account_id=f"provider-beta-{index}",
                provider_id="provider-beta",
                text="Совместное предложение, подписанное вторым провайдером",
            )
            for index in range(3)
        ]
        revocation_case = self.world.open_sovereign_case(revocation_claims, subject_scope_id=revocation_scope)
        self.world.janus_sovereign_decide(
            revocation_case,
            capability=self.capability("sovereign_case_decision", revocation_case, "before-provider-revocation"),
        )
        self.world.revoke_trusted_provider_key(
            "provider-beta",
            self.provider_keys["provider-beta"],
            reason="Компрометация обнаружена задним числом",
            compromised_from="2025-12-31T00:00:00Z",
        )
        revocation_state = self.world._plural_store()["sovereign_cases"][revocation_case]
        revocation_passed = revocation_state["status"] == "CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE" and revocation_state["witness_count"] == 0
        self.security("provider_key_compromise_cascades_to_cases", revocation_passed, witness_count=revocation_state["witness_count"])
        assert revocation_passed

        # Honest deployment boundary: direct code with process authority can bootstrap a new root.
        rogue_private, rogue_public = generate_ed25519_keypair()
        del rogue_private
        self.world.register_trusted_provider_key(
            "in-process-rogue-root",
            key_id="rogue-key",
            public_key_b64=rogue_public,
            valid_from=ISSUED,
            valid_until=EXPIRES,
        )
        self.finding(
            "BA-179-LIVED-002",
            "BOUNDARY",
            "Trust-root bootstrap is an unrestricted in-process method",
            "Code already executing inside the Genesis process can register a new provider root without a bootstrap capability.",
            "Keep this method outside gameplay/network APIs and bind production trust-root changes to offline quorum, HSM custody or a separate root-governance capability.",
        )

        self.finding(
            "BA-179-LIVED-003",
            "HIGH_BOUNDARY",
            "Authority expiry depends on the host wall clock",
            "Capabilities and key windows use the local UTC clock; the reference layer has no signed time witness or rollback detector.",
            "Use a trusted time source, monotonic rollback guard and append-only time checkpoints for network sovereignty.",
        )
        self.finding(
            "BA-179-LIVED-004",
            "MEDIUM_BOUNDARY",
            "Consumed nonce storage is unbounded",
            "Every accepted provider or sovereign nonce remains in the JSON store indefinitely.",
            "Partition replay ledgers by issuer/time window and compact only after expiry while preserving a hash commitment to retired partitions.",
        )

        return {
            "genuine_decision": decision,
            "ghost_case": ghost_state,
            "appeal_chain": chain,
            "confidence_neutral_decision": neutral_decision,
            "assessment_injected_decision": injected_decision,
            "revocation_case": revocation_state,
        }

    def finalise(self, pre: dict[str, Any], midpoint: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
        final_export = PortableSaveManager(self.restored_dir).export_to(
            self.final_save,
            label="Bound Authority ordinary citizen final world",
        )
        final_text = self.final_save.read_text(encoding="utf-8")
        private_leak = any(
            secret and secret in final_text
            for secret in (
                list(self.provider_private.values())
                + [self.sovereign_private]
                + list(self.account_private.values())
            )
        )
        chronicle = _check_tuple(self.world.verify_chronicle_records())
        graph = _check_tuple(self.world.verify_possibility_graph())
        free_other = _check_tuple(self.world.verify_free_other_state())
        authority = _check_tuple(self.world.verify_bound_authority_state())
        bound_state = self.world.bound_authority_state()
        relationship = self.world.relationship_state(PLAYER_ID, self.handle)["relationships"][self.handle]
        free_state = self.world.free_other_state(PLAYER_ID)["profile"]
        agency = {
            "initiatives": sum(_count(actor.get("initiatives")) for actor in free_state["others"].values()),
            "refusals": sum(_count(actor.get("refusals")) for actor in free_state["others"].values()),
            "departures": sum(_count(actor.get("departures")) for actor in free_state["others"].values()),
            "returns": sum(_count(actor.get("returns")) for actor in free_state["others"].values()),
            "calling_changes": sum(_count(actor.get("calling_changes")) for actor in free_state["others"].values()),
        }
        status_counts = dict(Counter(item["status"] for item in self.actions))
        player = self.world.memory.load_player(PLAYER_ID)
        store = self.world._plural_store()
        graph_store = self.world._graph()
        summary = {
            "schema": "janus.genesis.experiment.bound_authority_lived_life.v1",
            "runtime_version": "18.7.9",
            "role": DISPLAY_NAME,
            "days_lived": 45,
            "ordinary_actions": len(self.actions),
            "status_counts": status_counts,
            "player": {
                "good_count": int(player.good_count),
                "harm_count": int(player.harm_count),
                "chronological_age": int(player.chronological_age),
                "apparent_age": int(player.apparent_age),
            },
            "relationship": {"handle": self.handle, **relationship},
            "free_other_agency": agency,
            "security_events": self.security_events,
            "security_passed": sum(1 for item in self.security_events if item["passed"]),
            "security_failed": sum(1 for item in self.security_events if not item["passed"]),
            "findings": self.findings,
            "midpoint": midpoint,
            "final_portable": {
                **final_export,
                "private_key_leak": private_leak,
            },
            "verification": {
                "chronicle": chronicle,
                "possibility_graph": graph,
                "free_other": free_other,
                "bound_authority": authority,
            },
            "bound_authority_state": bound_state,
            "plural_store_counts": {
                "claims": len(store.get("claims", {})),
                "sovereign_cases": len(store.get("sovereign_cases", {})),
                "sovereign_decisions": len(store.get("sovereign_decisions", {})),
                "provider_attestations": len(store.get("provider_attestations_v179", {})),
                "evidence_assessments": len(store.get("evidence_assessments", {})),
                "authority_events": len(store.get("authority_events", [])),
                "consumed_nonces": len(store.get("consumed_nonces", {})),
                "reactive_reaudits": len(store.get("reactive_reaudits", {})),
            },
            "hrain_graph": {
                "nodes": len(graph_store.get("nodes", [])),
                "edges": len(graph_store.get("edges", [])),
            },
            "pre_midpoint": {
                "genuine_case": pre["genuine_case"],
                "campaign_shard_independent_voice_count": pre["shard_audit"]["independent_voice_count"],
                "delegation_id": pre["delegation_id"],
            },
            "post_midpoint": {
                "genuine_ruling": post["genuine_decision"]["ruling"],
                "appeal_chain": post["appeal_chain"],
                "claimant_confidence_ruling": post["confidence_neutral_decision"]["ruling"],
                "unbound_assessor_ruling": post["assessment_injected_decision"]["ruling"],
                "revoked_provider_witness_count": post["revocation_case"]["witness_count"],
            },
            "private_keys_persisted": False,
            "verdict": (
                "The Bound Authority stops replay, provider spoofing, campaign sharding, ghost voting, "
                "sovereign-string impersonation and destructive review rewriting. It is not yet safe to expose "
                "evidence-assessment or trust-root bootstrap methods to untrusted callers."
            ),
            "next_candidate": "Genesis v18.7.10 — The Bound Assessor",
        }
        assert len(self.actions) == 135
        assert player.harm_count == 0
        assert not private_leak
        assert chronicle["valid"] and graph["valid"] and free_other["valid"] and authority["valid"]
        assert any(item["finding_id"] == "BA-179-LIVED-001" for item in self.findings)
        _json_write(self.summary_path, summary)
        _json_write(self.events_path, self.security_events)
        self.log_path.write_text("\n".join(self.log_lines) + "\n", encoding="utf-8")
        return summary

    def run(self) -> dict[str, Any]:
        if self.work_root.exists():
            shutil.rmtree(self.work_root)
        if self.artifact_root.exists():
            shutil.rmtree(self.artifact_root)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.world = PlayableGenesisV187(self.primary_dir)
        self.world.set_display_name(PLAYER_ID, DISPLAY_NAME)
        self.world.set_free_other_seed_for_testing("bound-authority-ordinary-citizen-life")
        self.handle = self.world.public_state(PLAYER_ID)["free_other_handles"][0]
        self.log("=== GENESIS v18.7.9 — THE BOUND AUTHORITY: LIVED LIFE ===")
        self.log(f"ROLE: {DISPLAY_NAME}")
        self.install_trust_roots()
        self.ordinary_days(1, 22)
        pre = self.pre_midpoint_security()
        midpoint = self.portable_midpoint()
        self.ordinary_days(23, 45)
        post = self.post_midpoint_security(pre)
        summary = self.finalise(pre, midpoint, post)
        self.log("=== LIFE COMPLETE ===")
        self.log(json.dumps({
            "days": summary["days_lived"],
            "actions": summary["ordinary_actions"],
            "good": summary["player"]["good_count"],
            "harm": summary["player"]["harm_count"],
            "security_passed": summary["security_passed"],
            "security_failed": summary["security_failed"],
            "findings": len(summary["findings"]),
        }, ensure_ascii=False, sort_keys=True))
        self.log_path.write_text("\n".join(self.log_lines) + "\n", encoding="utf-8")
        return summary


def run_lived_audit(
    work_root: str | Path = ".bound-authority-lived-work",
    artifact_root: str | Path = "artifacts/bound_authority_lived_life",
) -> dict[str, Any]:
    return LivedAudit(Path(work_root), Path(artifact_root)).run()


if __name__ == "__main__":
    run_lived_audit()
