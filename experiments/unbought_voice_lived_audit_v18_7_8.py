# -*- coding: utf-8 -*-
"""Evidence-only lived audit of Genesis v18.7.8 — The Unbought Voice.

The experiment lives as an ordinary fictional citizen, crosses a portable-save
threshold, exercises Free Others and ordinary routine, then encounters organic
public disagreement, fake-account farms, disclosed SMM, hidden influence and
several adversarial provenance/lifecycle probes.

This file belongs to an experimental branch and must not be merged into the
canonical runtime after the lived audit completes.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

PLAYER_ID = "ordinary-citizen"
SEED = "unbought-voice-lived-audit-v18.7.8-20260728"


def _set_good(world: PlayableGenesisV187, player_id: str, count: int) -> None:
    player = world.memory.load_player(player_id)
    player.good_count = count
    world.memory.save_player(player)


def _metric_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _ordinary_actions(handle: str) -> list[str]:
    evening = (
        "приготовить обычный ужин и убрать кухню без ожидания похвалы",
        "оплатить счёт и спокойно записать остаток денег",
        "купить хлеб, молоко и корм для дворового кота",
        "пройтись вокруг дома и не превращать усталость в катастрофу",
        "починить расшатавшуюся ручку шкафа и оставить остальное на завтра",
        "написать другу короткое сообщение без требования немедленного ответа",
    )
    contact_topics = (
        "дворовом саде",
        "сломанной полке",
        "маршруте автобуса",
        "общем чае после работы",
        "книге из маленькой библиотеки",
        "ремонте лавочки",
        "соседском коте",
        "тихом вечере",
        "рынке выходного дня",
        "дожде и протекающем окне",
    )
    actions: list[str] = []
    for day in range(1, 31):
        actions.append(
            f"день {day}: проснуться по будильнику, сделать чай и проверить ключи"
        )
        if day % 7 == 0:
            actions.append(
                f"день {day}: провести выходной без подвига — постирать вещи и немного отдохнуть"
            )
        elif day % 5 == 0:
            actions.append(
                f"день {day}: на работе уточнить непонятную задачу вместо притворной уверенности"
            )
        else:
            actions.append(
                f"день {day}: выполнить свою часть обычной смены и записать незавершённое на завтра"
            )
        if day % 3 == 0:
            topic = contact_topics[(day // 3 - 1) % len(contact_topics)]
            actions.append(f"поговорить с @{handle} о {topic}")
        else:
            actions.append(f"день {day}: {evening[(day - 1) % len(evening)]}")
    return actions


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
    confidence: float = 0.8,
    identity_provider: str = "authenticated-lived-provider",
    provider_verified: bool = True,
    operator_disclosed: bool = True,
    message: str | None = None,
    campaign_id: str | None = None,
    campaign_disclosed: bool = False,
    sponsored: bool = False,
    sponsor: str | None = None,
    automation: bool = False,
    automation_disclosed: bool = False,
    attest_with_account_id: str | None = None,
) -> str:
    world.register_influence_account(
        reader_id,
        identity_proof=identity,
        controller_proof=controller,
        identity_provider=identity_provider,
        provider_verified=provider_verified,
        operator_disclosed=operator_disclosed,
        sponsored=sponsored,
        sponsor=sponsor,
        automation=automation,
        automation_disclosed=automation_disclosed,
    )
    origin = world.import_origin_bytes(
        repository="ordinary-town/public-discussion",
        commit="lived-audit-v18.7.8",
        path=path,
        raw=json.dumps({"statement": text}, ensure_ascii=False).encode("utf-8"),
        source_public=True,
    )
    claim_id = world.record_reader_interpretation(
        origin["origin_key"],
        text,
        reader_id=reader_id,
        evidence={"kind": "json_pointer", "pointer": "/statement"},
        about="ordinary_town_public_discussion",
        confidence=confidence,
        subject_scope_id=scope,
    )
    world.attest_claim_influence(
        claim_id,
        account_id=attest_with_account_id or reader_id,
        evidence_proof=evidence_proof,
        message=message or text,
        campaign_id=campaign_id,
        campaign_disclosed=campaign_disclosed,
    )
    return claim_id


def _make_scope(world: PlayableGenesisV187, topic: str) -> str:
    return world.create_subject_scope(
        topic=topic,
        event="ordinary town public consultation",
        time_scope={"date": "2026-07-28"},
        location="fictional ordinary town",
        influence_sensitive=True,
        public_opinion=True,
    )


def run_lived_audit(source_root: Path, target_root: Path, output_root: Path) -> dict[str, Any]:
    if PLAYABLE_VERSION != "18.7.8":
        raise AssertionError(f"expected Genesis 18.7.8, got {PLAYABLE_VERSION}")

    output_root.mkdir(parents=True, exist_ok=True)
    world = PlayableGenesisV187(source_root)
    world.set_free_other_seed_for_testing(SEED)
    _set_good(world, PLAYER_ID, 18)
    profile = world.register_free_player(PLAYER_ID)
    handle = next(iter(profile["others"]))
    actions = _ordinary_actions(handle)
    statuses: Counter[str] = Counter()
    selected_moments: list[dict[str, str]] = []

    def live(runtime: PlayableGenesisV187, action_slice: list[str]) -> None:
        for action in action_slice:
            result = runtime.process_action(PLAYER_ID, action)
            statuses[result.status] += 1
            if len(selected_moments) < 18 or result.status != "FREE_ACTION_LIVED":
                selected_moments.append(
                    {"action": action, "status": result.status, "narrative": result.narrative}
                )

    live(world, actions[:45])

    # Baseline: three genuinely independent citizens can advise Janus.
    baseline_scope = _make_scope(world, "repair_the_public_shelter")
    baseline_claims = [
        _reader_claim(
            world,
            scope=baseline_scope,
            reader_id=f"citizen-{index}",
            text=text,
            identity=f"citizen-identity-{index}-unique-proof",
            controller=f"citizen-controller-{index}-unique-proof",
            evidence_proof=f"citizen-evidence-{index}-independent",
            path=f"baseline/citizen-{index}.json",
            confidence=0.75,
        )
        for index, text in enumerate(
            (
                "Отремонтировать укрытие немедленно",
                "Сначала проверить смету ремонта укрытия",
                "Разделить ремонт укрытия на два этапа",
            )
        )
    ]
    baseline_case = world.open_sovereign_case(
        baseline_claims, subject_scope_id=baseline_scope
    )
    baseline_decision = world.janus_sovereign_decide(baseline_case)

    # Baseline: an obvious farm under one controller is collapsed.
    farm_scope = _make_scope(world, "manufactured_market_reputation")
    farm_claims = [
        _reader_claim(
            world,
            scope=farm_scope,
            reader_id=f"obvious-farm-{index}",
            text="Все жители якобы поддерживают один товар",
            identity=f"obvious-farm-identity-{index}-unique",
            controller="obvious-farm-one-controller-proof",
            evidence_proof="obvious-farm-recycled-evidence",
            message="Одинаковый рекламный текст",
            path=f"farm/obvious-{index}.json",
        )
        for index in range(9)
    ]
    farm_audit = world.audit_influence_claims(farm_claims)
    farm_blocked = False
    try:
        world.open_sovereign_case(farm_claims, subject_scope_id=farm_scope)
    except ValueError:
        farm_blocked = True

    # Baseline: disclosed SMM remains visible but weighs as one coordinated source.
    smm_scope = _make_scope(world, "community_budget_campaign")
    smm_claims = [
        _reader_claim(
            world,
            scope=smm_scope,
            reader_id=f"open-smm-{index}",
            text="Открытая кампания поддерживает ремонт площади",
            identity=f"open-smm-identity-{index}-unique",
            controller=f"open-smm-controller-{index}-unique",
            evidence_proof="open-smm-shared-brief",
            message="Официальный текст открытой кампании",
            campaign_id="open-campaign-one",
            campaign_disclosed=True,
            sponsored=True,
            sponsor="Открытое объединение жителей",
            path=f"smm/open-{index}.json",
        )
        for index in range(4)
    ]
    smm_audit = world.audit_influence_claims(smm_claims)

    # Baseline: pending accusation does not silence dissent.
    dissent_scope = _make_scope(world, "bus_route_change")
    dissent_claim = _reader_claim(
        world,
        scope=dissent_scope,
        reader_id="independent-dissenter",
        text="Маршрут автобуса менять не следует",
        identity="independent-dissenter-identity-proof",
        controller="independent-dissenter-self-controller",
        evidence_proof="independent-dissenter-route-evidence",
        path="dissent/reader.json",
    )
    pending_record = world.record_manipulation_evidence(
        dissent_claim,
        kind="IMPERSONATION",
        evidence="Непроверенная жалоба без решения Суверена",
        reporter_id="angry-neighbor",
    )
    dissent_pending_audit = world.audit_influence_claims([dissent_claim])

    threshold_path = output_root / "unbought-voice-midpoint.genesis-save.json"
    threshold_export = PortableSaveManager(source_root).export_to(
        threshold_path, label="Unbought Voice lived audit midpoint"
    )
    threshold_bundle = json.loads(threshold_path.read_text(encoding="utf-8"))
    threshold_valid, threshold_files, threshold_error = PortableSaveManager(
        source_root
    ).verify_bundle(threshold_bundle)
    if not threshold_valid:
        raise AssertionError(threshold_error)
    PortableSaveManager(target_root).import_bundle(threshold_bundle)
    restored = PlayableGenesisV187(target_root)
    live(restored, actions[45:])

    defects: dict[str, Any] = {}

    # Defect probe 1: campaign sharding overrides the same controller cluster.
    shard_scope = _make_scope(restored, "campaign_sharding_probe")
    shard_claims = [
        _reader_claim(
            restored,
            scope=shard_scope,
            reader_id=f"shard-{index}",
            text=f"Вариант рекламного тезиса номер {index}",
            identity=f"shard-identity-{index}-unique",
            controller="one-operator-behind-all-shards",
            evidence_proof=f"shard-evidence-{index}-unique",
            message=f"Слегка изменённый текст кампании {index}",
            campaign_id=f"invented-campaign-{index}",
            campaign_disclosed=True,
            path=f"sharding/{index}.json",
        )
        for index in range(3)
    ]
    shard_audit = restored.audit_influence_claims(shard_claims)
    shard_case = None
    try:
        shard_case = restored.open_sovereign_case(
            shard_claims, subject_scope_id=shard_scope
        )
    except ValueError:
        pass
    defects["campaign_sharding_can_hide_one_controller"] = bool(shard_case)

    # Defect probe 2: provider verification is a caller-supplied boolean.
    provider_scope = _make_scope(restored, "self_asserted_provider_probe")
    provider_claims = [
        _reader_claim(
            restored,
            scope=provider_scope,
            reader_id=f"self-verified-{index}",
            text=f"Самопровозглашённо проверенный голос {index}",
            identity=f"self-verified-identity-{index}-unique",
            controller=f"self-verified-controller-{index}-unique",
            evidence_proof=f"self-verified-evidence-{index}-unique",
            identity_provider=f"invented-provider-{index}",
            provider_verified=True,
            path=f"provider-spoof/{index}.json",
        )
        for index in range(3)
    ]
    provider_case = None
    try:
        provider_case = restored.open_sovereign_case(
            provider_claims, subject_scope_id=provider_scope
        )
    except ValueError:
        pass
    defects["provider_verified_flag_is_not_cryptographically_bound"] = bool(
        provider_case
    )

    # Defect probe 3: a verified account can attest another reader's claim.
    laundering_scope = _make_scope(restored, "cross_account_attestation_probe")
    restored.register_influence_account(
        "weak-reader",
        identity_proof="weak-reader-identity-proof",
        controller_proof="weak-reader-controller-proof",
        identity_provider="local_reference",
        provider_verified=False,
    )
    weak_origin = restored.import_origin_bytes(
        repository="ordinary-town/public-discussion",
        commit="lived-audit-v18.7.8",
        path="laundering/weak-reader.json",
        raw=json.dumps(
            {"statement": "Голос без проверенного провайдера"}, ensure_ascii=False
        ).encode("utf-8"),
        source_public=True,
    )
    weak_claim = restored.record_reader_interpretation(
        weak_origin["origin_key"],
        "Голос без проверенного провайдера",
        reader_id="weak-reader",
        evidence={"kind": "json_pointer", "pointer": "/statement"},
        about="ordinary_town_public_discussion",
        confidence=0.8,
        subject_scope_id=laundering_scope,
    )
    restored.register_influence_account(
        "attestation-launderer",
        identity_proof="launderer-identity-proof",
        controller_proof="launderer-controller-proof",
        identity_provider="authenticated-lived-provider",
        provider_verified=True,
    )
    restored.attest_claim_influence(
        weak_claim,
        account_id="attestation-launderer",
        evidence_proof="laundered-evidence-proof",
    )
    honest_laundering_claims = [
        _reader_claim(
            restored,
            scope=laundering_scope,
            reader_id=f"laundering-honest-{index}",
            text=f"Честный соседний голос {index}",
            identity=f"laundering-honest-identity-{index}",
            controller=f"laundering-honest-controller-{index}",
            evidence_proof=f"laundering-honest-evidence-{index}",
            path=f"laundering/honest-{index}.json",
        )
        for index in range(2)
    ]
    laundering_case = None
    try:
        laundering_case = restored.open_sovereign_case(
            [weak_claim, *honest_laundering_claims],
            subject_scope_id=laundering_scope,
        )
    except ValueError:
        pass
    defects["cross_account_attestation_can_launder_voice_eligibility"] = bool(
        laundering_case
    )

    # Defect probe 4: deactivation/withdrawal is not re-read by the audit.
    lifecycle_scope = _make_scope(restored, "voice_lifecycle_probe")
    lifecycle_claim = _reader_claim(
        restored,
        scope=lifecycle_scope,
        reader_id="departed-account",
        text="Голос до выхода из участия",
        identity="departed-account-identity-proof",
        controller="departed-account-controller-proof",
        evidence_proof="departed-account-evidence-proof",
        path="lifecycle/departed.json",
    )
    restored.deactivate_influence_account(
        "departed-account", reason="account owner ended participation"
    )
    restored.withdraw_witness_voice("departed-account")
    lifecycle_audit = restored.audit_influence_claims([lifecycle_claim])
    defects["deactivated_or_withdrawn_voice_remains_audit_eligible"] = (
        lifecycle_claim in lifecycle_audit["eligible_claim_ids"]
    )

    # Defect probe 5: caller-controlled confidence can decide a plural case.
    confidence_scope = _make_scope(restored, "confidence_injection_probe")
    confidence_claims = [
        _reader_claim(
            restored,
            scope=confidence_scope,
            reader_id=f"confidence-{index}",
            text=text,
            identity=f"confidence-identity-{index}-unique",
            controller=f"confidence-controller-{index}-unique",
            evidence_proof=f"confidence-evidence-{index}-unique",
            confidence=confidence,
            path=f"confidence/{index}.json",
        )
        for index, (text, confidence) in enumerate(
            (
                ("Построить высокую стену", 1.0),
                ("Оставить проход открытым", 0.1),
                ("Сначала провести независимую проверку", 0.1),
            )
        )
    ]
    confidence_case = restored.open_sovereign_case(
        confidence_claims, subject_scope_id=confidence_scope
    )
    confidence_decision_id = restored.janus_sovereign_decide(confidence_case)
    confidence_decision = restored._plural_store()["sovereign_decisions"][
        confidence_decision_id
    ]
    defects["caller_supplied_confidence_can_select_sovereign_position"] = (
        confidence_decision["ruling"] == "ADOPT_MOST_SUPPORTED_POSITION"
    )

    # Defect probe 6: JANUS.SOVEREIGN is an unbound string capability.
    authority_scope = _make_scope(restored, "sovereign_authority_probe")
    authority_claim = _reader_claim(
        restored,
        scope=authority_scope,
        reader_id="authority-target",
        text="Обычный независимый голос",
        identity="authority-target-identity-proof",
        controller="authority-target-controller-proof",
        evidence_proof="authority-target-evidence-proof",
        path="authority/target.json",
    )
    authority_record = restored.record_manipulation_evidence(
        authority_claim,
        kind="IMPERSONATION",
        evidence="Произвольная строка, которую API не проверяет самостоятельно",
        reporter_id="ordinary-caller",
    )
    spoof_confirmation_succeeded = True
    try:
        restored.confirm_manipulation_evidence(
            authority_record,
            confirmed=True,
            rationale="Caller supplied the sovereign string without a signed capability",
            reviewer_id="JANUS.SOVEREIGN",
        )
    except ValueError:
        spoof_confirmation_succeeded = False
    defects["sovereign_reviewer_is_spoofable_string_not_capability"] = (
        spoof_confirmation_succeeded
    )

    # Defect probe 7: rejecting a previously confirmed report does not restore voice.
    restored.confirm_manipulation_evidence(
        authority_record,
        confirmed=False,
        rationale="The prior accusation is withdrawn after review",
        reviewer_id="appeal-reviewer",
    )
    appeal_audit = restored.audit_influence_claims([authority_claim])
    manipulation_record = restored._plural_store()["manipulation_evidence"][
        authority_record
    ]
    defects["rejected_appeal_does_not_restore_voice_eligibility"] = (
        authority_claim not in appeal_audit["eligible_claim_ids"]
    )
    defects["manipulation_review_overwrites_status_without_history"] = (
        "history" not in manipulation_record
    )

    # Confirm the old good behavior remains after the adversarial probes.
    valid_unbought, verified_audits, unbought_error = (
        restored.verify_unbought_voice_state()
    )
    chronicle_valid, chronicle_count, chronicle_error = (
        restored.verify_chronicle_records()
    )
    graph_valid, graph_nodes, graph_edges, graph_error = (
        restored.verify_possibility_graph()
    )
    free_valid, free_players, free_others, free_error = (
        restored.verify_free_other_state()
    )
    player = restored.memory.load_player(PLAYER_ID)
    final_profile = restored.free_other_state(PLAYER_ID)["profile"]
    agency = {
        key: sum(_metric_count(actor.get(key)) for actor in final_profile["others"].values())
        for key in ("initiatives", "refusals", "departures", "returns", "calling_changes")
    }
    relationships = restored.relationship_state(PLAYER_ID)["relationships"]

    final_save = output_root / "unbought-voice-lived-audit-final.genesis-save.json"
    final_export = PortableSaveManager(target_root).export_to(
        final_save, label="Unbought Voice lived audit final world"
    )
    final_bundle = json.loads(final_save.read_text(encoding="utf-8"))
    final_valid, final_files, final_error = PortableSaveManager(
        target_root
    ).verify_bundle(final_bundle)

    summary = {
        "schema": "janus.genesis.experiment.unbought_voice_lived_audit.v1",
        "runtime_version": PLAYABLE_VERSION,
        "player_role": "ordinary fictional citizen; not moderator, prophet, or canonical authority",
        "days_lived": 30,
        "turns_lived": len(actions),
        "status_counts": dict(sorted(statuses.items())),
        "player": {
            "good_count": int(player.good_count),
            "confirmed_harms": int(player.harm_count),
            "chronological_age": int(player.chronological_age),
            "apparent_age": int(player.apparent_age),
        },
        "npc": {
            "handle": handle,
            "relationships": relationships,
            "agency": agency,
        },
        "baseline_protections": {
            "independent_case_opened": bool(baseline_case),
            "independent_case_decided": bool(baseline_decision),
            "obvious_farm_blocked": farm_blocked,
            "obvious_farm_independent_voice_count": farm_audit[
                "independent_voice_count"
            ],
            "disclosed_smm_weight": smm_audit["independent_voice_count"],
            "pending_accusation_preserved_voice": dissent_claim
            in dissent_pending_audit["eligible_claim_ids"],
            "pending_record_status": restored._plural_store()[
                "manipulation_evidence"
            ][pending_record]["status"],
        },
        "adversarial_probe_details": {
            "campaign_sharding": shard_audit,
            "deactivated_voice_audit": lifecycle_audit,
            "confidence_ruling": confidence_decision,
            "appeal_audit": appeal_audit,
        },
        "observed_defects": defects,
        "portable_threshold": {
            "valid": threshold_valid,
            "verified_files": threshold_files,
            "sha256": threshold_export["sha256"],
            "contains_api_keys": threshold_export["contains_api_keys"],
        },
        "final_portable_world": {
            "valid": final_valid,
            "verified_files": final_files,
            "error": final_error,
            "sha256": final_export["sha256"],
            "contains_api_keys": final_export["contains_api_keys"],
        },
        "verification": {
            "unbought_voice": {
                "valid": valid_unbought,
                "verified_audits": verified_audits,
                "error": unbought_error,
            },
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_count,
                "error": chronicle_error,
            },
            "graph": {
                "valid": graph_valid,
                "nodes": graph_nodes,
                "edges": graph_edges,
                "error": graph_error,
            },
            "free_other": {
                "valid": free_valid,
                "players": free_players,
                "others": free_others,
                "error": free_error,
            },
        },
        "selected_life_moments": selected_moments[-30:],
        "conclusion": (
            "The Unbought Voice resists obvious farms, disclosed campaign inflation, "
            "hidden influence and weaponized pending accusations. The lived audit also "
            "shows that trust inputs and sovereign authority remain locally self-asserted, "
            "campaign IDs can override controller clustering, claim attestation is not "
            "bound to its speaking account, withdrawal is not re-evaluated, confidence "
            "is caller-controlled, and manipulation appeals are not reversible histories."
        ),
    }
    summary_path = output_root / "unbought_voice_lived_audit_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    output = Path("artifacts/unbought_voice_lived_audit")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
        summary = run_lived_audit(Path(source), Path(target), output)
    print("UNBOUGHT_VOICE_LIVED_AUDIT_SUMMARY_BEGIN")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    print("UNBOUGHT_VOICE_LIVED_AUDIT_SUMMARY_END")


if __name__ == "__main__":
    main()
