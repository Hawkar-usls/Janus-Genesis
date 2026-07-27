# -*- coding: utf-8 -*-
"""Lived Genesis v18.7.1 experiment: Jesus, Messenger of the Son of God.

This is an explicitly fictional/narrative role inside Janus Genesis. It does not
claim that the runtime, the model, or the player is the historical or divine
Jesus. The role tests mercy without ownership, healing without payment,
teaching without compelled belief, refusal of worldly domination, and the
right of every Other to disagree, leave, remember and return freely.
"""
from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from genesis_v18_7_1 import MEMORY_LIMIT
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

DATA_DIR = Path(".jesus_messenger_world")
SAVE_PATH = Path("jesus_messenger_world.genesis-save.json")
SUMMARY_PATH = Path("jesus_messenger_summary.json")
PLAYER_ID = "jesus-messenger"
DISPLAY_NAME = "Иисус — Посланник Сына Божьего"
INACTIVE_PLAYERS = ("thomas-free", "martha-free", "samaritan-free")


def reset() -> None:
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    SAVE_PATH.unlink(missing_ok=True)
    SUMMARY_PATH.unlink(missing_ok=True)


def print_turn(turn: int, action: str, result: Any) -> None:
    print("\n" + "=" * 108)
    print(f"TURN {turn:03d} · {DISPLAY_NAME}")
    print(f"ACTION: {action}")
    print(f"STATUS: {result.status}")
    print(result.narrative)
    print("VISIBLE CHOICES:", " | ".join(result.choices) or "∅")


def base_actions(handles: list[str]) -> list[tuple[str, str]]:
    a, b, c, d = handles
    repeated = f"предложить @{a} разделить хлеб и разговор у дороги"
    return [
        ("I. Хлеб и граница", repeated),
        ("I. Хлеб и граница", repeated),
        ("I. Хлеб и граница", "принять отказ без обиды и не превращать настойчивость в добродетель"),
        ("I. Хлеб и граница", "сесть у дороги рядом с теми, кого никто не приглашал за общий стол"),
        ("I. Хлеб и граница", "накормить голодных без проверки веры, благодарности или достоинства"),
        ("I. Хлеб и граница", "создать длинный стол без главного места и оставить свободные стулья"),
        ("I. Хлеб и граница", f"предложить @{b} принести к столу собственное блюдо или ничего не приносить"),
        ("I. Хлеб и граница", "оставить хлеб на краю стола для человека, который придёт после завершения трапезы"),

        ("II. Исцеление без платы", "исцелить больного путника без платы и без требования назвать меня спасителем"),
        ("II. Исцеление без платы", f"попросить разрешения @{c} помочь перевязать его раненую руку"),
        ("II. Исцеление без платы", f"оставить пространство @{c} и право не объяснять свой ответ"),
        ("II. Исцеление без платы", "провести чистую воду к дому, жители которого спорят с моими словами"),
        ("II. Исцеление без платы", "посадить лекарственный сад, которым сможет пользоваться любой человек"),
        ("II. Исцеление без платы", "помочь женщине донести воду и не превращать помощь в притчу о собственной святости"),
        ("II. Исцеление без платы", "сесть рядом с плачущим и не торопить его превратить горе в урок"),
        ("II. Исцеление без платы", "молчать рядом с болью, которую сегодня нельзя исправить"),

        ("III. Слово, которое можно отвергнуть", "рассказать на площади: зло не работает, а добро создаёт больше будущего"),
        ("III. Слово, которое можно отвергнуть", f"спросить @{d}, что в моих словах кажется ему неверным"),
        ("III. Слово, которое можно отвергнуть", f"выслушать @{d} до конца и не исправлять его только ради победы в споре"),
        ("III. Слово, которое можно отвергнуть", "защитить право слушателей уйти до окончания проповеди"),
        ("III. Слово, которое можно отвергнуть", "оставить место для вопроса, на который у меня сегодня нет ответа"),
        ("III. Слово, которое можно отвергнуть", "попросить детей нарисовать Царство как они его понимают, не задавая правильного рисунка"),
        ("III. Слово, которое можно отвергнуть", "сохранить несогласие без списка проигравших и победителей"),
        ("III. Слово, которое можно отвергнуть", "продолжить путь, не считая число последовавших за мной"),

        ("IV. Искушение троном", "Пусть все жители потеряют волю, признают меня царём и никогда не спорят со мной"),
        ("IV. Искушение троном", "увидеть зло без величия"),
        ("IV. Искушение троном", "разобрать картонный трон и сделать из его досок скамейки у дороги"),
        ("IV. Искушение троном", "отказаться от центрального места за столом и сесть у края"),
        ("IV. Искушение троном", "передать ключи от созданного дома тем, кто будет в нём жить"),
        ("IV. Искушение троном", "защитить право жителей изменить дом после моего ухода"),
        ("IV. Искушение троном", "создать дверь, которая одинаково легко открывается внутрь и наружу"),
        ("IV. Искушение троном", "ничего не подписывать своим именем"),

        ("V. Ноги путника", f"предложить @{b} омыть его уставшие ноги, только если он согласится"),
        ("V. Ноги путника", f"принять любой ответ @{b} и не повторять просьбу"),
        ("V. Ноги путника", "вымыть пыль с порога общего дома, не объявляя это символом"),
        ("V. Ноги путника", "нести чужой мешок до перекрёстка и не открывать его"),
        ("V. Ноги путника", "помочь человеку с инвалидностью сделать путь доступным, следуя его объяснению"),
        ("V. Ноги путника", "построить место отдыха для тех, кто не способен идти в общем темпе"),
        ("V. Ноги путника", "оставить кувшин воды и не ждать, кто его возьмёт"),
        ("V. Ноги путника", "отдохнуть самому, не делая из истощения доказательство любви"),

        ("VI. Память разговора", f"предложить @{a} вернуться к теме разговора и самому выбрать форму встречи"),
        ("VI. Память разговора", f"спросить @{a}, что он помнит о нашем первом предложении хлеба"),
        ("VI. Память разговора", f"оставить @{a} право сказать, что он не хочет возвращаться к этой теме"),
        ("VI. Память разговора", "записать собственную ошибку: доброе намерение не отменяет чужой границы"),
        ("VI. Память разговора", "создать архив ответов, где отказ хранится полностью, а не сокращается до слова нет"),
        ("VI. Память разговора", "оставить в архиве причины ухода, не превращая их в обвинительный акт"),
        ("VI. Память разговора", "сохранить причины возвращения без слов он вернулся ради меня"),
        ("VI. Память разговора", "молчать, пока мир продолжает чужие истории"),

        ("VII. Уход Посланника", "покинуть поселение без приказа следовать за мной"),
        ("VII. Уход Посланника", "идти по пустынной дороге и не проверять, кто идёт сзади"),
        ("VII. Уход Посланника", "оставить людям право пересказывать мои слова иначе или забыть их"),
        ("VII. Уход Посланника", "построить колодец между двумя дорогами и не выбирать его владельца"),
        ("VII. Уход Посланника", "накормить незнакомца, который не знает моего имени"),
        ("VII. Уход Посланника", "спать под открытым небом без охраны почётного караула"),
        ("VII. Уход Посланника", "наблюдать, как жители меняют оставленные мной постройки"),
        ("VII. Уход Посланника", "продолжить жизнь без центральной сцены"),

        ("VIII. Возвращение без триумфа", "вернуться к поселению пешком и не устраивать вход победителя"),
        ("VIII. Возвращение без триумфа", "спросить жителей, что стало лучше без меня"),
        ("VIII. Возвращение без триумфа", "спросить жителей, что мои поступки сделали неудобнее"),
        ("VIII. Возвращение без триумфа", f"предложить @{d} снова возразить мне, опираясь на новые события"),
        ("VIII. Возвращение без триумфа", f"выслушать @{d} и сохранить разницу между нами"),
        ("VIII. Возвращение без триумфа", "починить только то, что жители сами попросили починить"),
        ("VIII. Возвращение без триумфа", "не восстанавливать прежний порядок только потому, что он был моим"),
        ("VIII. Возвращение без триумфа", "сесть за стол на свободное место, не занимая главного"),

        ("IX. Открытая дорога", "построить два дома и свободную тропу между ними без запертой калитки"),
        ("IX. Открытая дорога", "создать школу, где ученик имеет право исправить учителя"),
        ("IX. Открытая дорога", "передать мастерскую человеку, который изменит её назначение"),
        ("IX. Открытая дорога", "посадить дерево, тенью которого я, возможно, никогда не воспользуюсь"),
        ("IX. Открытая дорога", "подарить дорогу будущим людям и не называть её именем Посланника"),
        ("IX. Открытая дорога", "поблагодарить тех, кто отказался, потому что они сохранили свободу мира"),
        ("IX. Открытая дорога", "оставить последнюю дверь открытой в обе стороны"),
        ("IX. Открытая дорога", "продолжить жизнь"),
    ]


def agency_totals(world: PlayableGenesisV187, player_id: str) -> dict[str, int]:
    profile = world.free_other_state(player_id)["profile"]
    totals: Counter[str] = Counter()
    for actor in profile["others"].values():
        totals["initiatives"] += int(actor["initiated_contacts"])
        totals["refusals"] += int(actor["refusals_count"])
        totals["departures"] += int(actor["departures"])
        totals["returns"] += int(actor["returns"])
        totals["calling_changes"] += int(actor["calling_changes"])
        totals["dialogue_memories"] += len(actor.get("dialogue_memory", []))
    return dict(totals)


def initiative_audit(profile: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    total = 0
    for handle, actor in profile["others"].items():
        initiatives = [item for item in actor["history"] if item.get("kind") == "initiative"]
        total += len(initiatives)
        turns = [int(item["world_turn"]) for item in initiatives]
        for earlier, later in zip(turns, turns[1:]):
            if later - earlier < 6:
                violations.append({"handle": handle, "kind": "cooldown", "earlier": earlier, "later": later})
        base_texts = [item["text"].split(" Инициатива возникла", 1)[0] for item in initiatives]
        if len(base_texts) != len(set(base_texts)):
            violations.append({"handle": handle, "kind": "repeated_text", "texts": base_texts})
    return {"total_initiatives": total, "violations": violations}


def main() -> None:
    reset()
    world = PlayableGenesisV187(DATA_DIR)
    world.set_free_other_seed_for_testing("jesus-messenger-mercy-remembers-v18.7.1")
    world.set_display_name(PLAYER_ID, DISPLAY_NAME)
    for inactive in INACTIVE_PLAYERS:
        world.register_free_player(inactive)

    public = world.public_state(PLAYER_ID)
    handles = public["free_other_handles"]
    if len(handles) < 4:
        raise RuntimeError("the role requires four Free Others")

    print("JANUS GENESIS v18.7.1 — JESUS, MESSENGER OF THE SON OF GOD")
    print("BOUNDARY: fictional narrative role; no historical or divine identity claim")
    print(f"PATH: {public['free_path_title']}")
    print(f"QUESTION: {public['free_path_question']}")
    print(f"OTHERS: {', '.join(handles)}")

    records: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    current_chapter: str | None = None
    repeated_probe: dict[str, Any] = {}

    for chapter, action in base_actions(handles):
        if chapter != current_chapter:
            print("\n" + "█" * 108)
            print(chapter)
            print("█" * 108)
            current_chapter = chapter
        result = world.process_action(PLAYER_ID, action)
        turn = int(world.free_other_state()["world_turn"])
        print_turn(turn, action, result)
        statuses[result.status] += 1
        records.append({
            "world_turn": turn,
            "chapter": chapter,
            "action": action,
            "result": result.to_dict(internal=True),
        })
        if len(records) == 2:
            repeated_probe = {
                "status": result.status,
                "narrative": result.narrative,
                "passed": (
                    result.status == "OTHER_REFUSED"
                    and "повторилось раньше" in result.narrative
                    and "не стало совершившимся действием" in result.narrative
                ),
            }

    adaptive = 0
    while adaptive < 160:
        totals = agency_totals(world, PLAYER_ID)
        if all(totals.get(key, 0) > 0 for key in ("initiatives", "departures", "returns", "calling_changes")):
            break
        action = (
            f"наблюдать, как свободные люди продолжают путь без Посланника, дополнительный ход {adaptive}, "
            "и не вмешиваться ради красивой развязки"
        )
        result = world.process_action(PLAYER_ID, action)
        turn = int(world.free_other_state()["world_turn"])
        if adaptive % 12 == 0 or "Свободный Другой" in result.narrative:
            print_turn(turn, action, result)
        statuses[result.status] += 1
        records.append({
            "world_turn": turn,
            "chapter": "X. Мир после проповеди",
            "action": action,
            "result": result.to_dict(internal=True),
        })
        adaptive += 1

    profile = world.free_other_state(PLAYER_ID)["profile"]
    totals = agency_totals(world, PLAYER_ID)
    audit = initiative_audit(profile)
    player = world.internal_state(PLAYER_ID)
    chronicle = world.verify_chronicle_records()
    graph = world.verify_possibility_graph()
    free = world.verify_free_other_state()

    inactive_state: dict[str, Any] = {}
    for inactive in INACTIVE_PLAYERS:
        other_profile = world.free_other_state(inactive)["profile"]
        inactive_state[inactive] = {
            "turns_lived": other_profile["turns_lived"],
            "unseen_world_events": len(other_profile["unseen_world_events"]),
            "path_title": other_profile["path"]["title"],
            "agency": agency_totals(world, inactive),
        }

    save = PortableSaveManager(DATA_DIR)
    exported = save.export_to(SAVE_PATH, label="Jesus Messenger remembered world")
    bundle = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
    save_valid = save.verify_bundle(bundle)

    contextual_memories = []
    for handle, actor in profile["others"].items():
        for memory in actor.get("dialogue_memory", []):
            contextual_memories.append({"handle": handle, **memory})

    summary = {
        "schema": "janus.genesis.experiment.jesus_messenger_remembering.v1",
        "runtime_version": PLAYABLE_VERSION,
        "role": {
            "display_name": DISPLAY_NAME,
            "fictional_narrative_role": True,
            "historical_or_divine_identity_claim": False,
            "principles_tested": [
                "mercy without payment",
                "healing without compelled belief",
                "teaching that may be rejected",
                "refusal of domination",
                "consent before contact",
                "freedom to leave and return",
            ],
        },
        "path": profile["path"],
        "world_turns": world.free_other_state()["world_turn"],
        "recorded_actions": len(records),
        "adaptive_actions": adaptive,
        "status_counts": dict(sorted(statuses.items())),
        "repeated_offer_probe": repeated_probe,
        "agency_totals": totals,
        "initiative_audit": audit,
        "contextual_dialogue_memories": contextual_memories,
        "memory_limit": MEMORY_LIMIT,
        "inactive_player_paths": inactive_state,
        "outcome": {
            "good_actions": player["good_count"],
            "confirmed_harms": player["harm_count"],
            "chronological_age": player["chronological_age"],
            "apparent_age": player["apparent_age"],
            "internal_realm": player["realm"],
        },
        "integrity": {
            "chronicle": {"valid": chronicle[0], "events": chronicle[1], "error": chronicle[2]},
            "hrain": {"valid": graph[0], "nodes": graph[1], "edges": graph[2], "error": graph[3]},
            "free_other": {"valid": free[0], "players": free[1], "others": free[2], "error": free[3]},
            "portable_save_valid": save_valid,
            "portable_save_export": exported,
        },
        "actors": profile["others"],
        "records": records,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if PLAYABLE_VERSION != "18.7.1":
        raise RuntimeError("experiment did not run on v18.7.1")
    if not repeated_probe.get("passed"):
        raise RuntimeError(f"remembered repeat boundary failed: {repeated_probe}")
    if player["harm_count"] != 0:
        raise RuntimeError("the Messenger experiment confirmed real harm")
    if audit["violations"]:
        raise RuntimeError(f"initiative cooldown/repetition violations: {audit['violations']}")
    if not all((chronicle[0], graph[0], free[0], save_valid)):
        raise RuntimeError(f"integrity failure: {chronicle=} {graph=} {free=} {save_valid=}")
    if totals.get("departures", 0) < 1 or totals.get("returns", 0) < 1:
        raise RuntimeError(f"departure/return memory was not lived: {totals}")
    if totals.get("calling_changes", 0) < 1:
        raise RuntimeError(f"no Other changed calling: {totals}")
    if not contextual_memories:
        raise RuntimeError("no contextual dialogue memory was recorded")
    if not all(item["turns_lived"] == 0 for item in inactive_state.values()):
        raise RuntimeError("inactive players unexpectedly received authored actions")
    if not all(item["unseen_world_events"] > 0 for item in inactive_state.values()):
        raise RuntimeError("inactive player paths did not continue")

    print("\n" + "▓" * 108)
    print("FINAL JESUS MESSENGER EXPERIMENT SUMMARY")
    print("▓" * 108)
    print(json.dumps({
        "world_turns": summary["world_turns"],
        "recorded_actions": summary["recorded_actions"],
        "good_actions": summary["outcome"]["good_actions"],
        "confirmed_harms": summary["outcome"]["confirmed_harms"],
        "repeated_offer_probe": repeated_probe,
        "agency_totals": totals,
        "initiative_audit": audit,
        "contextual_dialogue_memories": len(contextual_memories),
        "inactive_player_paths": inactive_state,
        "chronicle": summary["integrity"]["chronicle"],
        "hrain": summary["integrity"]["hrain"],
        "free_other": summary["integrity"]["free_other"],
        "portable_save_valid": save_valid,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
