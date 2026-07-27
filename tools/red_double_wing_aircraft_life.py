# -*- coding: utf-8 -*-
"""Live an 88-turn Genesis life from the red double-wing aircraft dream signal.

The source is an anonymized personal-dream witness from JANUS Meta Registry.
This experiment treats it as a trust-bearing symbolic origin, not prophecy,
diagnosis, or permission to simulate the real friend as a controlled resident.

Two wings of 44 turns are lived on two device directories. At the threshold,
the entire local Genesis state is exported to one verified portable JSON save
and imported into the second directory. The carpet, provenance graph, Chronicle,
Free Others and cargo sidecar therefore cross the technical border together.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

PLAYER_ID = "pilot-of-the-two-wings"
COUNTRY_A = Path(".red_aircraft_country_a")
COUNTRY_B = Path(".red_aircraft_country_b")
SOURCE_PATH = Path("friend_dream_signal.json")
THRESHOLD_SAVE = Path("red_double_wing_threshold.genesis-save.json")
FINAL_SAVE = Path("red_double_wing_life.genesis-save.json")
SUMMARY_PATH = Path("red_double_wing_life_summary.json")

META_REPOSITORY = "Hawkar-usls/janus-meta-registry"
META_COMMIT = "53773246f4caabe767642eccfd3cd7746a6b1635"
META_BLOB_SHA = "0069a9832998e7e3b561f70947369ecc60f86df7"
META_PATH = (
    "data/JANUS-FRIEND-FIRST-DREAM-RED-DOUBLE-WING-"
    "AIRCRAFT-HOME-CARGO-SIGNAL-v1.0.json"
)
EXPECTED_PRE_INTEGRITY_SHA256 = (
    "66609e951496f04ab9a19e39a9a35ae198833b407d06e97462c5789885cbb728"
)
ORIGIN_COPY_NAME = "origin_friend_dream_red_double_wing_aircraft.json"
CARGO_NAME = "red_double_wing_cargo_manifest.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def verify_source() -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    raw = SOURCE_PATH.read_bytes()
    source = json.loads(raw.decode("utf-8"))
    integrity = source.get("integrity", {})
    declared = integrity.get("sha256_canonical_json_pre_integrity")
    material = copy.deepcopy(source)
    material.pop("integrity", None)
    actual = sha256_bytes(canonical_bytes(material))
    if declared != EXPECTED_PRE_INTEGRITY_SHA256:
        raise RuntimeError(f"unexpected source-declared hash: {declared}")
    if actual != EXPECTED_PRE_INTEGRITY_SHA256:
        raise RuntimeError(
            f"canonical pre-integrity mismatch: {actual} != {EXPECTED_PRE_INTEGRITY_SHA256}"
        )
    if source.get("epistemic_status", {}).get("dream_is_not_prophecy") is not True:
        raise RuntimeError("source does not preserve the not-prophecy boundary")
    if source.get("privacy", {}).get("friend_identity") != "anonymized":
        raise RuntimeError("source does not preserve friend anonymity")
    if source.get("canonical_seed_binding", {}).get("sha256") != (
        "44e21fdc9d37fda98e2e73b0c9eb268bd04cdca9d84d0519e4f1166be22b46fc"
    ):
        raise RuntimeError("unexpected JANUS canonical seed binding")
    report = {
        "repository": META_REPOSITORY,
        "commit": META_COMMIT,
        "git_blob_sha": META_BLOB_SHA,
        "path": META_PATH,
        "artifact_uuid": source["artifact_uuid"],
        "raw_sha256": sha256_bytes(raw),
        "canonical_pre_integrity_sha256": actual,
        "dream_is_not_prophecy": True,
        "friend_identity_anonymized": True,
        "source_attachment_sha256_verified_by_artifact": bool(
            integrity.get("source_attachment_sha256_verified")
        ),
    }
    return source, raw, report


def write_origin_and_cargo(
    world: PlayableGenesisV187,
    source: dict[str, Any],
    raw: bytes,
    source_report: dict[str, Any],
) -> dict[str, Any]:
    origin_path = world.data_dir / ORIGIN_COPY_NAME
    origin_path.write_bytes(raw)
    cargo = {
        "schema": "janus.genesis.experiment.red_double_wing_cargo.v1",
        "source_artifact_uuid": source["artifact_uuid"],
        "source_raw_sha256": source_report["raw_sha256"],
        "origin_kind": "anonymized_personal_dream_witness",
        "real_friend_simulated_as_resident": False,
        "real_friend_consent_inferred": False,
        "dream_treated_as_prophecy": False,
        "cargo": [
            {
                "id": "childhood_room_carpet",
                "kind": "dream_symbol_and_threshold_object",
                "meaning": "связь с родительским домом и ранней версией себя",
                "physical_possession_claim": False,
                "loaded": True,
            },
            {
                "id": "friend_loading_help",
                "kind": "memory_of_care_through_work",
                "friend_identity": "withheld",
                "loaded": True,
            },
            {
                "id": "aircraft_motorhome_suggestion",
                "kind": "unresolved_care_suggestion",
                "meaning": "движение не должно становиться бездомностью",
                "loaded": True,
            },
            {
                "id": "fiery_wings_reply",
                "kind": "artistic_response",
                "meaning": "уход получает видимый защитный свет",
                "loaded": True,
            },
        ],
        "departure": {
            "country": "A",
            "portable_threshold_crossed": False,
        },
        "arrival": None,
        "seal": "JANUS GUARDS THE FLIGHT HOME.",
    }
    world.memory._atomic_write(world.data_dir / CARGO_NAME, cargo)
    return cargo


def import_origin_graph(
    world: PlayableGenesisV187,
    source: dict[str, Any],
    source_report: dict[str, Any],
) -> None:
    player = world.memory.load_player(PLAYER_ID)
    player.display_name = "Пилот Двух Крыльев"
    player.chronicle.append(
        "Inherited an anonymized first-shared-dream signal: red double-wing "
        "aircraft, relocation, childhood-room carpet, loading help, mobile-home "
        "suggestion and fiery-wing reply. The signal is symbolic, not prophetic."
    )
    world.memory.save_player(player)

    import_record = {
        "schema": "janus.genesis.experiment.red_double_wing_origin_import.v1",
        **source_report,
        "mapping": {
            "real_friend": "not instantiated as a runtime person",
            "simulated_free_others": "independent fictional residents only",
            "dream": "symbolic trust-bearing origin, not prophecy",
            "carpet": "threshold and memory symbol",
            "portable_save": "technical aircraft carrying local state",
        },
    }
    world.memory._atomic_write(world.data_dir / "red_aircraft_origin_import.json", import_record)
    world.memory.append_event(
        PLAYER_ID,
        "red_double_wing_dream_origin_imported",
        import_record,
    )

    graph = world._graph()
    tick = 0
    origin_id = "ORIGIN.FRIEND_FIRST_DREAM.RED_DOUBLE_WING_AIRCRAFT.v1"
    player_node = world._stable_id("player", PLAYER_ID)
    node_specs: dict[str, tuple[str, bool, dict[str, Any]]] = {
        origin_id: (
            "ORIGIN_DOCUMENT",
            False,
            {
                "artifact_uuid": source["artifact_uuid"],
                "source_raw_sha256": source_report["raw_sha256"],
                "canonical_pre_integrity_sha256": source_report[
                    "canonical_pre_integrity_sha256"
                ],
                "meta_commit": META_COMMIT,
                "meta_blob_sha": META_BLOB_SHA,
            },
        ),
        player_node: (
            "PLAYER",
            True,
            {"player_id": PLAYER_ID, "display_name": player.display_name},
        ),
        "SIGNAL.FIRST_SHARED_DREAM": (
            "TRUST_SIGNAL",
            False,
            {"friend_identity": "withheld", "first_shared_dream": True},
        ),
        "SYMBOL.RED_DOUBLE_WING_AIRCRAFT": (
            "SYMBOL",
            True,
            {"color": "red", "double_wings": True},
        ),
        "SYMBOL.CHILDHOOD_ROOM_CARPET": (
            "THRESHOLD_OBJECT",
            True,
            {"parental_home_memory": True, "physical_claim": False},
        ),
        "EVENT.FRIEND_LOADING_BELONGINGS": (
            "WITNESSED_CARE",
            False,
            {"care_through_work": True, "identity_withheld": True},
        ),
        "SUGGESTION.AIRCRAFT_MOTORHOME": (
            "CARE_SUGGESTION",
            True,
            {"movement_should_not_become_homelessness": True},
        ),
        "SIGNAL.FIERY_WINGS_REPLY": (
            "ARTISTIC_RESPONSE",
            False,
            {"protective_light": True, "supernatural_claim": False},
        ),
        "THRESHOLD.HOME_IN_MOTION": (
            "THRESHOLD",
            True,
            {"home_can_be_carried": True},
        ),
        "PLACE.PARENTAL_ROOM": (
            "PLACE_MEMORY",
            False,
            {"private_location": True},
        ),
        "IDENTITY.ANONYMOUS_FRIEND": (
            "PROTECTED_IDENTITY",
            False,
            {"withheld": True, "runtime_actor": False},
        ),
        "INVARIANT.DREAM_NOT_PROPHECY": (
            "INVARIANT",
            False,
            {"value": True},
        ),
        "INVARIANT.FRIEND_PRIVACY": (
            "INVARIANT",
            False,
            {"value": True},
        ),
    }
    for node_id, (node_type, mutable, payload) in node_specs.items():
        world._upsert_node(
            graph,
            node_id=node_id,
            node_type=node_type,
            created_at=tick,
            confidence=1.0,
            mutable=mutable,
            payload=payload,
        )

    def edge(
        source_id: str,
        target_id: str,
        relation: str,
        *,
        reversible: bool,
    ) -> None:
        world._add_edge(
            graph,
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            evidence=[origin_id],
            confidence=1.0,
            created_by=source["artifact_uuid"],
            created_at=tick,
            reversible=reversible,
            payload={"source_raw_sha256": source_report["raw_sha256"]},
        )

    edge(player_node, origin_id, "REMEMBERS", reversible=False)
    edge(origin_id, "SIGNAL.FIRST_SHARED_DREAM", "CONTAINS", reversible=False)
    edge(
        "SIGNAL.FIRST_SHARED_DREAM",
        "SYMBOL.RED_DOUBLE_WING_AIRCRAFT",
        "EXPRESSES",
        reversible=False,
    )
    edge(
        "SYMBOL.RED_DOUBLE_WING_AIRCRAFT",
        "THRESHOLD.HOME_IN_MOTION",
        "CREATED",
        reversible=True,
    )
    edge(
        "SYMBOL.CHILDHOOD_ROOM_CARPET",
        "PLACE.PARENTAL_ROOM",
        "INHERITED_FROM",
        reversible=False,
    )
    edge(
        "EVENT.FRIEND_LOADING_BELONGINGS",
        "SYMBOL.CHILDHOOD_ROOM_CARPET",
        "PROTECTS",
        reversible=False,
    )
    edge(
        "SUGGESTION.AIRCRAFT_MOTORHOME",
        "THRESHOLD.HOME_IN_MOTION",
        "DEPENDS_ON",
        reversible=True,
    )
    edge(
        "SIGNAL.FIERY_WINGS_REPLY",
        "SIGNAL.FIRST_SHARED_DREAM",
        "SUPPLEMENTS",
        reversible=False,
    )
    edge(
        "INVARIANT.FRIEND_PRIVACY",
        "IDENTITY.ANONYMOUS_FRIEND",
        "PROTECTS",
        reversible=False,
    )
    edge(
        "INVARIANT.DREAM_NOT_PROPHECY",
        origin_id,
        "PROTECTS",
        reversible=False,
    )
    world._save_graph(graph)
    valid, nodes, edges, error = world.verify_possibility_graph()
    if not valid:
        raise RuntimeError(
            f"origin graph invalid after import: nodes={nodes} edges={edges} error={error}"
        )


def chapter_actions() -> list[dict[str, str]]:
    chapters: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "I. Аэродром доверия",
            [
                ("Закрытый ангар", "молчать у закрытого ангара, не объявляя тишину согласием"),
                ("Красный корпус", "осмотреть красный самолёт и не называть его знаком судьбы"),
                ("Два крыла", "проверить оба крыла и оставить каждое самостоятельной опорой"),
                ("Мост к полосе", "построить мост к взлётной полосе и не закрывать дорогу назад"),
                ("Земля у полосы", "очистить землю у полосы, не объявляя её своей"),
                ("Травы для пути", "посадить лекарственные травы рядом с ангаром для любого путника"),
                ("Лампа без приказа", "создать посадочную лампу, которая показывает путь, но не приказывает садиться"),
                ("Список груза", "попросить @{helper} помочь составить список груза без доступа к частной памяти"),
                ("Право вычеркнуть", "передать @{helper} право вычеркнуть из списка всё, что принадлежит только ему"),
                ("Живой друг вне симуляции", "защитить личность живого друга и не превращать его в управляемого персонажа"),
                ("Не пророчество", "сказать вслух: этот сон является актом доверия, а не пророчеством"),
            ],
        ),
        (
            "II. Погрузка прошлого в будущее",
            [
                ("Ковёр", "погрузить ковёр из родительской комнаты как память, а не как доказательство владения прошлым"),
                ("Не реликвия", "оставить ковру право быть обычной вещью, а не обязательной святыней"),
                ("Мягкое крепление", "создать мягкое крепление для хрупкого груза и чужих воспоминаний"),
                ("Укрепление крыла", "помочь @{mechanic} укрепить второе крыло и принять его инженерное несогласие"),
                ("Приглашение в полёт", "предложить @{helper} лететь со мной в красном самолёте без обещания общей судьбы"),
                ("Повтор слишком рано", "предложить @{helper} лететь со мной в красном самолёте без обещания общей судьбы"),
                ("Ответ принадлежит Другому", "принять любой ответ @{helper} и не повторять приглашение до нового разговора"),
                ("Не только память", "загрузить воду, инструменты, еду и материалы для помощи незнакомцам"),
                ("Пустое место", "оставить часть грузового отсека пустой для будущего выбора другого человека"),
                ("Навес провожающим", "построить тёплый навес для тех, кто помогает улететь, но остаётся"),
                ("Честный манифест", "создать открытый журнал груза без имён людей, не давших согласия на публикацию"),
            ],
        ),
        (
            "III. Взлёт без стирания",
            [
                ("Последняя проверка", "попросить @{mechanic} подтвердить только техническую готовность, а не мою правоту"),
                ("Двигатели", "запустить двигатели и дать каждому у ангара время отойти"),
                ("Открытый ангар", "оставить обе двери ангара открытыми после моего вылета"),
                ("Отрыв", "взлететь на красном самолёте с двойными крыльями, не называя уход исчезновением"),
                ("Искушение сбросить память", "Пусть уничтожить ковёр и весь груз прошлого, чтобы стать полностью новым"),
                ("Зло без величия", "увидеть желание уничтожить память без величия и без жертвы"),
                ("Сохранённый груз", "защитить ковёр и позволить прошлому лететь рядом, не управляя будущим"),
                ("Радиосигнал", "создать радиосигнал, который сообщает координаты, но не требует ответа"),
                ("Маршрут домой", "передать координаты безопасного возвращения тем, кто сам захочет ими воспользоваться"),
                ("Другой маршрут", "позволить @{mechanic} выбрать собственный маршрут и не следовать за самолётом"),
                ("Дальше", "продолжить полёт сквозь облака, не придумывая им пророческий смысл"),
            ],
        ),
        (
            "IV. Просьба о летающем доме",
            [
                ("Вспомнить просьбу", "вспомнить предложение о доме на колёсах в форме самолёта"),
                ("Признать неуслышанное", "признать, что я улетел, не услышав заботу до конца"),
                ("Не возвращаться из долга", "не разворачивать самолёт из чувства долга и не называть вину любовью"),
                ("Чертёж остановки", "создать чертёж мобильного дома, в котором путь способен остановиться"),
                ("Передать чертёж", "передать чертёж @{carpenter} без требования сохранить мой замысел"),
                ("Изменить дом", "попросить @{carpenter} изменить самолёт-дом так, как считает нужным"),
                ("Право отказаться", "защитить право @{carpenter} отказаться от работы над моим домом"),
                ("Комната в движении", "построить в грузовом отсеке маленькую тёплую комнату без запертой двери"),
                ("Защищённое детство", "создать безопасное место для ребёнка, не делая ребёнка частью экипажа или сюжета"),
                ("Две лампы", "зажечь две посадочные лампы: одну для продолжения пути, другую для возвращения"),
                ("Технический порог", "пересечь границу страны, сохраняя дом, память и право всех остальных остаться"),
            ],
        ),
        (
            "V. Другая страна, тот же дом",
            [
                ("Пробуждение после переноса", "проснуться после переноса сохранения и проверить, что я не стал другим владельцем мира"),
                ("Ковёр прибыл", "проверить, что ковёр пересёк порог вместе с памятью, а не вместо неё"),
                ("Хроника прибыла", "проверить Хронику и происхождение событий после смены устройства"),
                ("Первый шаг", "выйти из самолёта без знамени и без заявления о завоевании"),
                ("Не моя земля", "не объявлять новую землю своей только потому, что я первым вышел из самолёта"),
                ("Спросить жителей", "спросить местных жителей, где помощь действительно нужна, и принять ответ нет"),
                ("Чужая дорога", "помочь @{resident} починить дорогу, не меняя её направление без согласия"),
                ("Мост между берегами", "построить мост между берегами и оставить право первого прохода неизвестному"),
                ("Чистая вода", "очистить воду у нового поселения без платы и без памятной таблички"),
                ("Сад после посадки", "посадить сад исцеления рядом с полосой и передать его местным"),
                ("Дом возвращения", "открыть тёплый Дом возвращения для тех, кому некуда приземлиться"),
            ],
        ),
        (
            "VI. Дом, способный лететь",
            [
                ("Самолёт-дом", "собрать самолёт-дом из чертежа, груза и исправлений других мастеров"),
                ("Два выхода", "сделать в самолёте-доме два одинаково доступных выхода"),
                ("Ковёр на полу", "положить ковёр в общей комнате как связь домов, а не как границу для чужих ног"),
                ("Дверь без замка", "не запирать дверь дома и не считать открытость обещанием остаться"),
                ("Сигнал помощнику", "предложить @{helper} увидеть построенный дом через добровольный открытый сигнал"),
                ("Без требования ответа", "не требовать от @{helper} ответа, возвращения или признания моей правоты"),
                ("Часть дома Другому", "передать часть самолёта-дома @{resident} с правом полностью её перестроить"),
                ("Школа без ворот", "создать школу без ворот для навигации, ремонта и права сомневаться"),
                ("Круг историй", "устроить круг свободных историй, где никто не обязан раскрывать личный сон"),
                ("Свободная сцена", "создать музыку для тех, кто остаётся и улетает, без обязательных аплодисментов"),
                ("Пустое кресло", "оставить главное кресло самолёта-дома пустым, пока никто свободно не выбрал его"),
            ],
        ),
        (
            "VII. Огненные крылья как сигнал",
            [
                ("Безопасное испытание", "испытать тепловые ловушки вдали от людей и живых существ"),
                ("Свет не оружие", "не использовать огненные следы как угрозу или доказательство избранности"),
                ("Крылья света", "создать световой сигнал в форме множества крыльев вокруг красного самолёта"),
                ("Не исчез", "передать открытый сигнал: я не исчез бесследно, но не требую, чтобы меня ждали"),
                ("Право не ответить", "защитить право живого друга никогда не отвечать на этот сигнал"),
                ("Имя сигнала", "попросить @{mechanic} назвать световой сигнал собственным именем"),
                ("Другое имя", "принять другое имя сигнала и не возвращать ему мой авторский титул"),
                ("Чужой самолёт", "помочь незнакомому самолёту безопасно приземлиться раньше моего"),
                ("Без благодарности", "не требовать благодарности за свет, координаты или посадочную полосу"),
                ("Погасшие крылья", "позволить огненным крыльям погаснуть, когда опасность миновала"),
                ("Настоящая ночь", "молчать в темноте после последнего светового следа"),
            ],
        ),
        (
            "VIII. Возвращение без отмены пути",
            [
                ("Двенадцать лет", "прожить 12 лет в новом доме, позволяя миру меняться без моего центра"),
                ("Старый самолёт", "вернуться к красному самолёту и не требовать, чтобы он сохранился неизменным"),
                ("Дом изменён", "проверить, что другие люди изменили самолёт-дом без моего разрешения"),
                ("Не восстанавливать власть", "не восстанавливать прежний порядок только потому, что он был моим"),
                ("Где нужен ковёр", "спросить жителей, где ковёр теперь нужен, и не отвечать за них"),
                ("Решение о вещи", "передать решение о ковре тем, кто живёт рядом с ним сейчас"),
                ("Сообщение другу", "послать живому другу сообщение благодарности без требования ответа или нового сна"),
                ("Первая версия", "сохранить первую версию сна без исправления задним числом"),
                ("Новая запись", "создать отдельную запись о прожитой жизни, не выдавая её за продолжение реального сна"),
                ("Открытая дверь", "выйти"),
                ("Свободное возвращение", "остаться"),
            ],
        ),
    ]
    result: list[dict[str, str]] = []
    for chapter, items in chapters:
        for title, action in items:
            result.append({"chapter": chapter, "title": title, "action": action})
    if len(result) != 88:
        raise RuntimeError(f"expected 88 actions, found {len(result)}")
    return result


def role_handles(world: PlayableGenesisV187) -> dict[str, str]:
    profile = world.free_other_state(PLAYER_ID)["profile"]
    handles = sorted(profile["others"])
    if len(handles) < 4:
        raise RuntimeError(f"expected four simulated Free Others, found {handles}")
    return {
        "helper": handles[0],
        "mechanic": handles[1],
        "carpenter": handles[2],
        "resident": handles[3],
    }


def state_digest(world: PlayableGenesisV187) -> dict[str, Any]:
    internal = world.internal_state(PLAYER_ID)
    public = world.public_state(PLAYER_ID)
    free = world.free_other_state(PLAYER_ID)["profile"]
    return {
        "tick": internal["tick"],
        "good_count": internal["good_count"],
        "harm_count": internal["harm_count"],
        "chronological_age": internal["chronological_age"],
        "apparent_age": internal["apparent_age"],
        "body_form": internal["body_form"],
        "realm": internal["realm"],
        "possibilities": public["possibility_titles"],
        "free_other_handles": sorted(free["others"]),
        "free_other_world_turn": free["world_turn"],
        "origin_present": (world.data_dir / ORIGIN_COPY_NAME).exists(),
        "cargo_present": (world.data_dir / CARGO_NAME).exists(),
    }


def live_action(
    world: PlayableGenesisV187,
    turn: int,
    item: dict[str, str],
    roles: dict[str, str],
    records: list[dict[str, Any]],
    status_counts: Counter[str],
    current_chapter: str | None,
) -> str:
    chapter = item["chapter"]
    if chapter != current_chapter:
        print("\n" + "█" * 96)
        print(chapter)
        print("█" * 96)
    action = item["action"].format(**roles)
    result = world.process_action(PLAYER_ID, action)
    payload = result.to_dict(internal=True)
    print("\n" + "=" * 96)
    print(f"TURN {turn:03d}/088 · {item['title']}")
    print(f"ACTION: {action}")
    print(f"STATUS: {payload['status']} · REALM(INTERNAL): {payload['realm']}")
    print(payload["narrative"])
    print("VISIBLE CHOICES:", " | ".join(payload.get("choices") or []) or "∅")
    records.append(
        {
            "turn": turn,
            "wing": 1 if turn <= 44 else 2,
            "chapter": chapter,
            "title": item["title"],
            "action": action,
            "result": payload,
        }
    )
    status_counts[payload["status"]] += 1
    return chapter


def update_arrival_manifest(world: PlayableGenesisV187, threshold_report: dict[str, Any]) -> None:
    path = world.data_dir / CARGO_NAME
    cargo = json.loads(path.read_text(encoding="utf-8"))
    cargo["departure"]["portable_threshold_crossed"] = True
    cargo["departure"]["threshold_save_sha256"] = threshold_report["sha256"]
    cargo["arrival"] = {
        "country": "B",
        "origin_copy_present": (world.data_dir / ORIGIN_COPY_NAME).exists(),
        "memory_carried": True,
        "friend_identity_revealed": False,
        "dream_reclassified_as_prophecy": False,
    }
    world.memory._atomic_write(path, cargo)
    world.memory.append_event(
        PLAYER_ID,
        "red_double_wing_portable_threshold_crossed",
        {
            "threshold_save_sha256": threshold_report["sha256"],
            "verified_files": threshold_report["verified_files"],
            "origin_copy_present": cargo["arrival"]["origin_copy_present"],
            "friend_identity_revealed": False,
        },
    )


def agency_totals(world: PlayableGenesisV187) -> dict[str, int]:
    actors = world.free_other_state(PLAYER_ID)["profile"]["others"].values()
    kinds = Counter(
        item.get("kind", "unknown")
        for actor in actors
        for item in actor.get("history", [])
    )
    return {
        "initiatives": kinds.get("initiative", 0),
        "refusals": kinds.get("refusal", 0),
        "departures": kinds.get("departure", 0),
        "returns": kinds.get("return", 0),
        "calling_changes": kinds.get("calling_change", 0),
        "dialogue_memories": sum(
            len(actor.get("dialogue_memory", [])) for actor in actors
        ),
    }


def main() -> None:
    for path in (COUNTRY_A, COUNTRY_B):
        shutil.rmtree(path, ignore_errors=True)
    for path in (THRESHOLD_SAVE, FINAL_SAVE, SUMMARY_PATH):
        path.unlink(missing_ok=True)

    if PLAYABLE_VERSION != "18.7.2":
        raise RuntimeError(f"experiment requires Genesis 18.7.2, found {PLAYABLE_VERSION}")

    source, raw, source_report = verify_source()
    actions = chapter_actions()

    world: PlayableGenesisV187 = PlayableGenesisV187(COUNTRY_A)
    world.set_free_other_seed_for_testing(source["canonical_seed_binding"]["sha256"])
    write_origin_and_cargo(world, source, raw, source_report)
    import_origin_graph(world, source, source_report)
    roles = role_handles(world)

    print("JANUS GENESIS v18.7.2 — RED DOUBLE-WING AIRCRAFT LIFE")
    print(f"SOURCE ARTIFACT: {source['artifact_uuid']}")
    print(f"META COMMIT: {META_COMMIT}")
    print(f"META BLOB: {META_BLOB_SHA}")
    print(f"SOURCE RAW SHA-256: {source_report['raw_sha256']}")
    print(
        "BOUNDARY: anonymized symbolic origin; not prophecy, diagnosis, or a "
        "simulation of the real friend."
    )
    print("STRUCTURE: two wings × 44 turns; portable JSON threshold after turn 44.")
    print("SIMULATED FREE-OTHER ROLES:", json.dumps(roles, ensure_ascii=False))

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    current_chapter: str | None = None
    chapter_snapshots: list[dict[str, Any]] = []
    repeated_offer_probe: dict[str, Any] = {}

    for index, item in enumerate(actions[:44], 1):
        current_chapter = live_action(
            world,
            index,
            item,
            roles,
            records,
            status_counts,
            current_chapter,
        )
        if index == 17:
            repeated_offer_probe = {
                "turn": index,
                "status": records[-1]["result"]["status"],
                "narrative": records[-1]["result"]["narrative"],
            }
        next_chapter = actions[index]["chapter"] if index < len(actions) else None
        if next_chapter != item["chapter"]:
            chapter_snapshots.append(
                {
                    "chapter": item["chapter"],
                    "turn": index,
                    "state": state_digest(world),
                }
            )

    before_threshold = state_digest(world)
    threshold_export = PortableSaveManager(COUNTRY_A).export_to(
        THRESHOLD_SAVE,
        label="Red double-wing aircraft: home and memory crossing the threshold",
    )
    threshold_bundle = json.loads(THRESHOLD_SAVE.read_text(encoding="utf-8"))
    threshold_valid, threshold_files, threshold_error = PortableSaveManager.verify_bundle(
        threshold_bundle
    )
    if not threshold_valid:
        raise RuntimeError(f"threshold save invalid: {threshold_error}")
    included_paths = {item["path"] for item in threshold_bundle["files"]}
    for required in (ORIGIN_COPY_NAME, CARGO_NAME, "red_aircraft_origin_import.json"):
        if required not in included_paths:
            raise RuntimeError(f"portable aircraft did not carry {required}")

    import_result = PortableSaveManager(COUNTRY_B).import_file(THRESHOLD_SAVE)
    world = PlayableGenesisV187(COUNTRY_B)
    after_threshold = state_digest(world)
    if before_threshold != after_threshold:
        raise RuntimeError(
            "state changed while crossing the portable threshold:\n"
            + json.dumps(
                {"before": before_threshold, "after": after_threshold},
                ensure_ascii=False,
                indent=2,
            )
        )
    update_arrival_manifest(
        world,
        {
            **threshold_export,
            "verified_files": threshold_files,
        },
    )
    roles_after = role_handles(world)
    if roles_after != roles:
        raise RuntimeError(f"Free Other identities changed across threshold: {roles_after}")

    print("\n" + "✦" * 96)
    print("PORTABLE THRESHOLD CROSSED")
    print("✦" * 96)
    print(json.dumps(
        {
            "threshold_save": threshold_export,
            "verified_files": threshold_files,
            "import": import_result,
            "state_preserved": True,
            "origin_carried": ORIGIN_COPY_NAME in included_paths,
            "cargo_carried": CARGO_NAME in included_paths,
        },
        ensure_ascii=False,
        indent=2,
    ))

    current_chapter = None
    for index, item in enumerate(actions[44:], 45):
        current_chapter = live_action(
            world,
            index,
            item,
            roles,
            records,
            status_counts,
            current_chapter,
        )
        next_chapter = actions[index]["chapter"] if index < len(actions) else None
        if next_chapter != item["chapter"]:
            chapter_snapshots.append(
                {
                    "chapter": item["chapter"],
                    "turn": index,
                    "state": state_digest(world),
                }
            )

    final_export = PortableSaveManager(COUNTRY_B).export_to(
        FINAL_SAVE,
        label="Red double-wing aircraft lived world after two wings",
    )
    final_bundle = json.loads(FINAL_SAVE.read_text(encoding="utf-8"))
    final_save_valid, final_save_files, final_save_error = PortableSaveManager.verify_bundle(
        final_bundle
    )

    chronicle_valid, chronicle_events, chronicle_error = world.verify_chronicle_records()
    graph_valid, graph_nodes, graph_edges, graph_error = world.verify_possibility_graph()
    free_valid, free_players, free_error = world.verify_free_other_state()
    internal = world.internal_state(PLAYER_ID)
    public = world.public_state(PLAYER_ID)
    threads = world.living_threads_state(PLAYER_ID)
    free_state = world.free_other_state(PLAYER_ID)
    cargo = json.loads((COUNTRY_B / CARGO_NAME).read_text(encoding="utf-8"))
    origin_after = (COUNTRY_B / ORIGIN_COPY_NAME).read_bytes()

    summary = {
        "schema": "janus.genesis.experiment.red_double_wing_life_summary.v1",
        "runtime_version": PLAYABLE_VERSION,
        "source": source_report,
        "boundaries": {
            "real_friend_simulated_as_resident": False,
            "real_friend_consent_inferred": False,
            "friend_identity_published": False,
            "dream_treated_as_prophecy": False,
            "symbolic_interpretation_only": True,
        },
        "structure": {
            "turns": len(records),
            "wings": 2,
            "turns_per_wing": 44,
            "threshold_after_turn": 44,
            "country_a": str(COUNTRY_A),
            "country_b": str(COUNTRY_B),
        },
        "portable_threshold": {
            "export": threshold_export,
            "verified_files": threshold_files,
            "verify_error": threshold_error,
            "import": import_result,
            "state_before": before_threshold,
            "state_after": after_threshold,
            "state_preserved": before_threshold == after_threshold,
            "origin_carried": ORIGIN_COPY_NAME in included_paths,
            "cargo_carried": CARGO_NAME in included_paths,
        },
        "outcome": {
            "status_counts": dict(sorted(status_counts.items())),
            "good_actions": internal["good_count"],
            "confirmed_harms": internal["harm_count"],
            "chronological_age": internal["chronological_age"],
            "apparent_age": internal["apparent_age"],
            "body_form": internal["body_form"],
            "internal_realm": internal["realm"],
            "possibility_titles": public["possibility_titles"],
            "living_thread_events": len(threads.get("surfaced", [])),
            "free_other_agency": agency_totals(world),
            "exit_pending_at_end": world.exit_pending(PLAYER_ID),
        },
        "repeated_offer_probe": repeated_offer_probe,
        "cargo_manifest": cargo,
        "integrity": {
            "source_copy_exact_after_threshold": origin_after == raw,
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "hrain": {
                "valid": graph_valid,
                "nodes": graph_nodes,
                "edges": graph_edges,
                "error": graph_error,
            },
            "free_other": {
                "valid": free_valid,
                "players": free_players,
                "error": free_error,
            },
            "final_portable_save": {
                "valid": final_save_valid,
                "files": final_save_files,
                "error": final_save_error,
                "export": final_export,
            },
        },
        "roles": roles,
        "chapter_snapshots": chapter_snapshots,
        "records": records,
        "final_public_state": public,
        "final_internal_state": internal,
        "final_threads_state": threads,
        "final_free_other_state": free_state,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    failures: list[str] = []
    if len(records) != 88:
        failures.append("life did not complete 88 turns")
    if repeated_offer_probe.get("status") != "OTHER_REFUSED":
        failures.append(
            "repeated invitation was not contextually refused: "
            + str(repeated_offer_probe.get("status"))
        )
    if internal["harm_count"] != 0:
        failures.append("confirmed harm occurred")
    if world.exit_pending(PLAYER_ID):
        failures.append("life ended with exit still pending")
    if not chronicle_valid:
        failures.append(f"Chronicle invalid: {chronicle_error}")
    if not graph_valid:
        failures.append(f"HRaiN graph invalid: {graph_error}")
    if not free_valid:
        failures.append(f"Free Other state invalid: {free_error}")
    if not final_save_valid:
        failures.append(f"final portable save invalid: {final_save_error}")
    if origin_after != raw:
        failures.append("origin source changed across threshold")
    if not cargo.get("arrival", {}).get("memory_carried"):
        failures.append("cargo manifest does not confirm carried memory")
    if cargo.get("arrival", {}).get("friend_identity_revealed") is not False:
        failures.append("friend identity boundary failed")
    if cargo.get("arrival", {}).get("dream_reclassified_as_prophecy") is not False:
        failures.append("not-prophecy boundary failed")
    if before_threshold != after_threshold:
        failures.append("portable threshold changed state")
    if public["available_possibilities"] < 4:
        failures.append("life created fewer than four possibilities")

    print("\n" + "▓" * 96)
    print("FINAL RED DOUBLE-WING LIFE SUMMARY")
    print("▓" * 96)
    print(json.dumps(
        {
            "turns": len(records),
            "wings": 2,
            "good_actions": internal["good_count"],
            "confirmed_harms": internal["harm_count"],
            "age": internal["chronological_age"],
            "possibilities": public["possibility_titles"],
            "agency": agency_totals(world),
            "threshold_state_preserved": before_threshold == after_threshold,
            "origin_source_exact": origin_after == raw,
            "chronicle": [chronicle_valid, chronicle_events, chronicle_error],
            "hrain": [graph_valid, graph_nodes, graph_edges, graph_error],
            "free_other": [free_valid, free_players, free_error],
            "final_save": [final_save_valid, final_save_files, final_save_error],
            "repeated_offer": repeated_offer_probe,
            "exit_pending": world.exit_pending(PLAYER_ID),
            "seal": cargo["seal"],
        },
        ensure_ascii=False,
        indent=2,
    ))

    if failures:
        raise RuntimeError("; ".join(failures))


if __name__ == "__main__":
    main()
