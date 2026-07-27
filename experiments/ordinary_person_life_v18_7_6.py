# -*- coding: utf-8 -*-
"""Lived experiment: an ordinary fictional adult inside Genesis v18.7.6.

This branch is experimental evidence only. It is designed to be closed without
merge after CI records the life and the boundaries discovered by it.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

PLAYER_ID = "ordinary-person"
SEED = "ordinary-person-life-v18.7.6-20260728"


def _source_claim(
    world: PlayableGenesisV187,
    *,
    path: str,
    payload: dict[str, Any],
    about: str,
    pointer: str = "/claim",
) -> tuple[dict[str, Any], str]:
    imported = world.import_origin_bytes(
        repository="ordinary-life/local-evidence",
        commit="20260728",
        path=path,
        raw=(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"),
        source_public=True,
    )
    claim_id = world.record_source_assertion(
        imported["origin_key"],
        evidence={"kind": "json_pointer", "pointer": pointer},
        about=about,
        confidence=0.8,
    )
    return imported, claim_id


def _metric_count(value: Any) -> int:
    """Count both old numeric counters and newer event collections safely."""
    if value is None:
        return 0
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _ordinary_actions() -> list[str]:
    evenings = (
        "приготовить простой ужин и убрать кухню без ожидания похвалы",
        "позвонить близкому человеку и сначала спросить, удобно ли сейчас говорить",
        "оплатить обычный счёт и записать остаток денег без паники",
        "пройтись вокруг дома и позволить вечеру остаться обычным",
        "признать, что ответил резко из-за усталости, и спокойно извиниться",
        "отказаться от лишней смены, потому что телу нужен отдых",
        "купить продукты по списку и не ругать себя за маленькую незапланированную покупку",
        "починить расшатавшуюся ручку шкафа и оставить остальное на завтра",
        "посидеть в тишине, не превращая усталость в философскую катастрофу",
        "написать другу короткое сообщение без требования немедленного ответа",
    )
    actions: list[str] = []
    for day in range(1, 41):
        actions.append(
            f"день {day}: проснуться по будильнику, умыться, сделать чай и проверить, взяты ли ключи"
        )
        if day % 7 == 0:
            actions.append(
                f"день {day}: провести выходной без подвига — постирать вещи, купить хлеб и немного отдохнуть"
            )
        elif day % 6 == 0:
            actions.append(
                f"день {day}: на работе уточнить непонятную задачу вместо того, чтобы притворяться уверенным"
            )
        elif day % 5 == 0:
            actions.append(
                f"день {day}: выполнить обычную смену и не брать на себя чужую ответственность без согласования"
            )
        else:
            actions.append(
                f"день {day}: добраться на работу, сделать свою часть спокойно и записать незавершённое на завтра"
            )
        actions.append(f"день {day}: {evenings[(day - 1) % len(evenings)]}")
    return actions


def run_ordinary_person_life(source_root: Path, target_root: Path) -> dict[str, Any]:
    if PLAYABLE_VERSION != "18.7.6":
        raise AssertionError(f"expected Genesis 18.7.6, got {PLAYABLE_VERSION}")

    world = PlayableGenesisV187(source_root)
    world.set_free_other_seed_for_testing(SEED)
    world.register_free_player(PLAYER_ID)
    actions = _ordinary_actions()
    statuses: Counter[str] = Counter()
    selected_moments: list[dict[str, str]] = []

    def live(runtime: PlayableGenesisV187, action_slice: list[str]) -> None:
        for action in action_slice:
            result = runtime.process_action(PLAYER_ID, action)
            statuses[result.status] += 1
            if len(selected_moments) < 12 or result.status not in {
                "FREE_ACTION_LIVED",
                "NO_MORAL_ECHO",
            }:
                selected_moments.append(
                    {"action": action, "status": result.status, "narrative": result.narrative}
                )

    live(world, actions[:60])

    # A legitimate three-source work disagreement.
    _, shift_a = _source_claim(
        world,
        path="work/manager-message.json",
        payload={"claim": "Смена 28 июля начинается в 08:00", "date": "2026-07-28"},
        about="work_shift_2026-07-28",
    )
    _, shift_b = _source_claim(
        world,
        path="work/coworker-message.json",
        payload={"claim": "Смена 28 июля начинается в 09:00", "date": "2026-07-28"},
        about="work_shift_2026-07-28",
    )
    _, shift_c = _source_claim(
        world,
        path="work/schedule-board.json",
        payload={"claim": "Смена 28 июля начинается в 08:30", "date": "2026-07-28"},
        about="work_shift_2026-07-28",
    )
    legitimate_triumvirate = world.record_triumvirate_dispute(
        [shift_a, shift_b, shift_c], confidence=0.9
    )

    # Two voices remain a contradiction and cannot be promoted.
    _, rumor_a = _source_claim(
        world,
        path="friends/message-a.json",
        payload={"claim": "Ира обещала прийти", "thread": "weekend"},
        about="ira_weekend_presence",
    )
    _, rumor_b = _source_claim(
        world,
        path="friends/message-b.json",
        payload={"claim": "Ира сказала, что не придёт", "thread": "weekend"},
        about="ira_weekend_presence",
    )
    two_voice_rejected = False
    try:
        world.record_triumvirate_dispute([rumor_a, rumor_b])
    except ValueError:
        two_voice_rejected = True

    # Three excerpts from one source remain one voice.
    same_source = world.import_origin_bytes(
        repository="ordinary-life/local-evidence",
        commit="20260728",
        path="work/one-report-three-lines.json",
        raw=json.dumps(
            {"a": "опоздание было", "b": "опоздания не было", "c": "время не записано"},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8"),
        source_public=True,
    )
    same_source_claims = [
        world.record_source_assertion(
            same_source["origin_key"],
            evidence={"kind": "json_pointer", "pointer": f"/{field}"},
            about="arrival_time",
        )
        for field in ("a", "b", "c")
    ]
    same_voice_rejected = False
    try:
        world.record_triumvirate_dispute(same_source_claims)
    except ValueError:
        same_voice_rejected = True

    # Current semantic weakness: three identical positions are accepted.
    identical_claims: list[str] = []
    for index in range(3):
        _, claim_id = _source_claim(
            world,
            path=f"shop/closing-{index}.json",
            payload={"claim": "Магазин закрывается в 20:00"},
            about="shop_closing_time",
        )
        identical_claims.append(claim_id)
    identical_triumvirate = world.record_triumvirate_dispute(identical_claims)

    # Current identity weakness: arbitrary reader IDs count as independent voices.
    shared_message = world.import_origin_bytes(
        repository="ordinary-life/local-evidence",
        commit="20260728",
        path="friends/shared-message.json",
        raw=json.dumps(
            {"text": "Я устал и сегодня не хочу разговаривать"},
            ensure_ascii=False,
        ).encode("utf-8"),
        source_public=True,
    )
    fabricated_readers = [
        world.record_reader_interpretation(
            shared_message["origin_key"],
            "Автор сообщения больше не ценит дружбу",
            reader_id=reader_id,
            evidence={"kind": "json_pointer", "pointer": "/text"},
            about="friendship_value",
            confidence=0.4,
        )
        for reader_id in ("ordinary-main", "ordinary-alt-one", "ordinary-alt-two")
    ]
    fabricated_reader_triumvirate = world.record_triumvirate_dispute(fabricated_readers)

    # Current context weakness: different dates can be forced under one subject.
    temporal_claims: list[str] = []
    for index, (date, hour) in enumerate(
        (("2026-07-28", "08:00"), ("2026-07-29", "09:00"), ("2026-07-30", "10:00"))
    ):
        _, claim_id = _source_claim(
            world,
            path=f"work/day-{index}.json",
            payload={"claim": f"Смена {date} начинается в {hour}", "date": date},
            about="work_shift_start",
        )
        temporal_claims.append(claim_id)
    temporal_triumvirate = world.record_triumvirate_dispute(temporal_claims)

    # A fourth grounded voice cannot join the existing field.
    _, fourth_claim = _source_claim(
        world,
        path="work/fourth-witness.json",
        payload={
            "claim": "Смена 28 июля начинается после общего звонка",
            "date": "2026-07-28",
        },
        about="work_shift_2026-07-28",
    )
    fourth_voice_rejected = False
    try:
        world.record_triumvirate_dispute([shift_a, shift_b, shift_c, fourth_claim])
    except ValueError:
        fourth_voice_rejected = True
    has_extension_api = hasattr(world, "add_triumvirate_voice")

    # Reader participation currently has no consent/authentication boundary.
    unregistered_reader_claim = world.record_reader_interpretation(
        shared_message["origin_key"],
        "Возможно, автор просто просит паузу",
        reader_id="neighbor-who-was-never-asked",
        evidence={"kind": "json_pointer", "pointer": "/text"},
        about="friendship_value",
        confidence=0.6,
    )

    threshold_path = source_root.parent / f"{source_root.name}-ordinary-person.genesis-save.json"
    manager = PortableSaveManager(source_root)
    exported = manager.export_to(threshold_path, label="Ordinary person midpoint")
    bundle = json.loads(threshold_path.read_text(encoding="utf-8"))
    valid_bundle, verified_files, bundle_error = manager.verify_bundle(bundle)
    if not valid_bundle:
        raise AssertionError(bundle_error)
    PortableSaveManager(target_root).import_bundle(bundle)
    threshold_path.unlink(missing_ok=True)

    restored = PlayableGenesisV187(target_root)
    live(restored, actions[60:])

    player = restored.memory.load_player(PLAYER_ID)
    profile = restored.free_other_state(PLAYER_ID)["profile"]
    others = profile["others"]
    agency = {
        key: sum(_metric_count(actor.get(key)) for actor in others.values())
        for key in ("initiatives", "refusals", "departures", "returns", "calling_changes")
    }

    triumvirate_state = restored.triumvirate_witness_state()
    grounded_state = restored.grounded_witness_state()
    chronicle_valid, chronicle_count, chronicle_error = restored.verify_chronicle_records()
    graph_valid, graph_nodes, graph_edges, graph_error = restored.verify_possibility_graph()
    free_valid, free_players, free_others, free_error = restored.verify_free_other_state()

    defects = {
        "identical_positions_can_be_labeled_dispute": bool(identical_triumvirate),
        "reader_ids_can_be_fabricated_into_independent_voices": bool(
            fabricated_reader_triumvirate
        ),
        "different_time_scopes_can_be_forced_under_one_subject": bool(temporal_triumvirate),
        "fourth_voice_cannot_join_existing_field": fourth_voice_rejected
        and not has_extension_api,
        "reader_participation_requires_no_consent_or_authentication": bool(
            unregistered_reader_claim
        ),
        "subject_identity_is_free_text_only": True,
        "dispute_has_no_resolution_or_supersession_lifecycle": not hasattr(
            restored, "resolve_triumvirate_dispute"
        ),
    }

    return {
        "schema": "janus.genesis.experiment.ordinary_person_life.v1",
        "runtime_version": PLAYABLE_VERSION,
        "player_role": "ordinary fictional adult; no prophetic or canonical identity",
        "days_lived": 40,
        "turns": len(actions),
        "status_counts": dict(sorted(statuses.items())),
        "player": {
            "good_count": player.good_count,
            "confirmed_harms": player.harm_count,
            "age": player.age,
            "apparent_age": player.apparent_age,
        },
        "free_other_agency": agency,
        "legitimate_triumvirate": legitimate_triumvirate,
        "two_voice_rejected": two_voice_rejected,
        "same_voice_rejected": same_voice_rejected,
        "triumvirate_state": triumvirate_state,
        "grounded_state": grounded_state,
        "portable_threshold": {
            "verified": valid_bundle,
            "verified_files": verified_files,
            "sha256": exported["sha256"],
            "contains_api_keys": exported["contains_api_keys"],
        },
        "verification": {
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
        "observed_defects": defects,
        "selected_life_moments": selected_moments[-24:],
        "conclusion": (
            "The three-voice gate resists pairwise promotion and same-source duplication, "
            "but a formal count still does not prove semantic disagreement, authenticated "
            "independence, shared temporal scope, voluntary participation, extensibility, "
            "or a resolution lifecycle."
        ),
    }


def main() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
        summary = run_ordinary_person_life(Path(source), Path(target))
        print("ORDINARY_PERSON_LIFE_SUMMARY_BEGIN")
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        print("ORDINARY_PERSON_LIFE_SUMMARY_END")


if __name__ == "__main__":
    main()
