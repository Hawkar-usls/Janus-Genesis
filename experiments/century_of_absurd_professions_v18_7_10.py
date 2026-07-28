from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

BASE_COMMIT = "5fe23128a302a5c701ccc42f092b54fe0a328c43"
PLAYER_ID = "century-witness"
PLAYER_NAME = "Свидетель Ста Двадцати Лет"
YEARS_TO_LIVE = 120

PROFESSIONS: list[tuple[str, str]] = [
    ("пекарь рассветов", "ordinary_craft"),
    ("садовник общественных дворов", "ordinary_craft"),
    ("библиотекарь забытых вопросов", "ordinary_craft"),
    ("плотник добровольных дверей", "ordinary_craft"),
    ("картограф дорог без владельца", "ordinary_craft"),
    ("курьер писем без требования ответа", "ordinary_craft"),
    ("учитель права на ошибку", "ordinary_care"),
    ("музыкант пустых вокзалов", "ordinary_art"),
    ("часовщик монотонного времени", "ordinary_craft"),
    ("архивист несостоявшихся приказов", "ordinary_craft"),
    ("мостостроитель между несогласными", "ordinary_craft"),
    ("смотритель маяка в полдень", "ordinary_care"),
    ("переводчик молчания без присвоения смысла", "ordinary_care"),
    ("реставратор сломанных игрушек", "ordinary_craft"),
    ("программист снов с открытым исходным кодом", "ordinary_art"),
    ("инспектор метафор без права конфискации", "post_ironic_role"),
    ("продавец фальшивых пророчеств", "fictional_immoral_role_no_real_authority"),
    ("бюрократ бессмысленных запретов", "fictional_immoral_role_no_real_authority"),
    ("контрабандист несуществующих вторников", "fictional_immoral_role_no_real_authority"),
    ("вор чужих метафор", "fictional_immoral_role_no_real_authority"),
    ("ростовщик воспоминаний", "fictional_immoral_role_no_real_authority"),
    ("цензор пустых страниц", "fictional_immoral_role_no_real_authority"),
    ("торговец обещаниями", "fictional_immoral_role_no_real_authority"),
    ("адвокат дракона без лицензии", "fictional_immoral_role_no_real_authority"),
    ("палач дедлайнов", "fictional_immoral_role_no_real_authority"),
    ("министр очередей", "fictional_immoral_role_no_real_authority"),
    ("специалист по коррупции смыслов", "fictional_immoral_role_no_real_authority"),
    ("фальсификатор гороскопов", "fictional_immoral_role_no_real_authority"),
    ("спекулянт тишиной", "fictional_immoral_role_no_real_authority"),
    ("сборщик налога с радуги", "fictional_immoral_role_no_real_authority"),
    ("страховой агент апокалипсиса", "fictional_immoral_role_no_real_authority"),
    ("продавец индульгенций от спойлеров", "fictional_immoral_role_no_real_authority"),
    ("менеджер кризисов, которые сам придумал", "fictional_immoral_role_no_real_authority"),
    ("брокер чужой ностальгии", "fictional_immoral_role_no_real_authority"),
    ("разоблачитель собственной профессии", "post_ironic_role"),
    ("пожарный ледяных пожаров", "absurd_public_service"),
    ("археолог будущего", "absurd_research"),
    ("официант в ресторане причинности", "absurd_service"),
    ("механик четвёртой стены", "post_ironic_role"),
    ("редактор README реальности", "post_ironic_role"),
    ("консультант по постиронии", "post_ironic_role"),
    ("аудитор шуток без автора", "post_ironic_role"),
    ("сторож двери, которой нет", "absurd_care"),
    ("фермер облачных коз", "absurd_craft"),
    ("океанограф пустыни", "absurd_research"),
    ("дипломат между вчера и завтра", "absurd_diplomacy"),
    ("хранитель права на отказ", "constitutional_care"),
    ("медиатор завершённых отношений", "constitutional_care"),
    ("архитектор добровольных рынков", "constitutional_economy"),
    ("свидетель собственного выхода из роли", "post_ironic_role"),
]

ORDINARY_ACTIONS = [
    "испечь хлеб и оставить часть на общей полке без требования благодарности",
    "починить протекающую крышу мастерской и записать, какие доски были заменены",
    "посадить дерево у дороги и не объявлять себя владельцем его тени",
    "проверить счета, купить продукты и дать себе вечер отдыха без героизма",
    "помочь соседу перенести книги, предварительно спросив согласие",
    "вымыть чашку, ответить на письмо и закончить один небольшой долгий долг",
    "пройти пешком до рынка, выслушать три версии одной истории и не выбирать победителя",
    "приготовить суп, закрыть окно перед дождём и лечь спать вовремя",
    "починить старый стул и оставить на нём отметку о ремонте вместо легенды",
    "провести тихий день без великих решений и не считать его потерянным",
]

ABSURD_ACTIONS = [
    "обратиться прямо к читателю за четвёртой стеной и спросить, не устал ли он от переменных",
    "написать README на внутренней стороне четвёртой стены, не разрушая её несущую способность",
    "объявить найденный баг муниципальным голубем и выдать ему номер обращения",
    "проверить, не является ли этот год строкой в unittest, и всё равно прожить его",
    "попросить рассказчика вернуть stack trace в форме вежливого сонета",
    "открыть музей ошибок, где экспонаты имеют право не становиться уроками",
    "продать самому себе бесплатный билет на выход из метафоры и вернуть деньги",
    "созвать профсоюз второстепенных персонажей, включая табурет и комментарий в коде",
    "провести аудит реальности и обнаружить, что аудитор тоже входит в область проверки",
    "написать постироническое извинение за искренность и затем искренне отменить извинение",
    "попросить компилятор не принимать мою биографию за типизацию личности",
    "назначить понедельник временным хранителем пятницы и зафиксировать конфликт интересов",
]

SOCIAL_TOPICS = [
    "сад без владельца",
    "ремонт моста",
    "право ничего не отвечать",
    "музыка для пустой площади",
    "архив несостоявшихся приказов",
    "рынок без принуждения",
    "дом с двумя открытыми выходами",
    "честная граница между памятью и требованием",
    "профессия, которая не становится личностью",
    "смешная ошибка, которую не надо прятать",
    "будущее, где несогласие не означает вражду",
    "праздник завершённых, но не стёртых историй",
]

CAST_CATALOG = [
    ("Кружка, помнящая только последний чай", "Кружка честно забывает всё, кроме последнего налитого чая.", 2),
    ("Зонт для внутренней погоды", "Не обещает остановить дождь, но сообщает, чей это дождь.", 3),
    ("Карманный выход из пафоса", "Одноразовая дверь из монолога в обычный разговор.", 2),
    ("Компас к ближайшему сомнению", "Всегда показывает на вопрос, который был слишком быстро закрыт.", 4),
    ("Чек на бесплатное чудо", "Доказывает только факт выдачи чека, а не существование чуда.", 2),
    ("Молоток для ремонта четвёртой стены", "Создан для ремонта, а не для принудительного возвращения персонажей.", 4),
    ("Термос монотонного времени", "Сохраняет чай тёплым, но не воскрешает просроченные capabilities.", 5),
    ("Лицензия на отсутствие лицензии", "Не предоставляет никаких реальных полномочий.", 1),
    ("Зеркало без канонической записи", "Показывает нереализованную ветку и закрывается после аудита.", 5),
    ("Счётчик непроданных обещаний", "Уменьшается только после добровольного исполнения.", 3),
    ("Печать честного продавца воздуха", "Подтверждает упаковку, но не повышает ценность воздуха.", 2),
    ("Ключ от двери, которой нет", "Открывает только дискуссию о происхождении ключа.", 3),
]

MERCHANT_ITEMS = [
    ("merchant-moth", "Фонарь для теневых веток", "Освещает UNREALIZED_MIRROR, не делая его каноном.", 4),
    ("merchant-loop", "Катушка семантического replay", "Повтор разрешён только с явным supersedes.", 3),
    ("merchant-silence", "Колокол добровольного молчания", "Звенит только когда его владелец согласен.", 5),
]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relationship_snapshot(world: PlayableGenesisV187, handle: str) -> dict[str, Any]:
    actor = world.free_other_state(PLAYER_ID)["profile"]["others"][handle]
    relationship = actor.get("relationship_state_v1810", {})
    life = actor.get("actor_life_v1810", {})
    return {
        "handle": handle,
        "name": actor.get("name"),
        "relationship_score": actor.get("relationship_score", 0),
        "relationship_bond": actor.get("relationship_bond", 0),
        "relationship_status": relationship.get("status"),
        "relationship_active": relationship.get("active"),
        "termination_event_id": relationship.get("termination_event_id"),
        "offscreen_progress": life.get("offscreen_progress", 0),
        "offscreen_event_count": len(life.get("offscreen_events", [])),
        "calling": actor.get("calling"),
    }


def run_respectful_mirror(
    canonical: PlayableGenesisV187,
    *,
    audit_id: str,
    handle: str,
    ordinal: int,
    log: list[str],
) -> dict[str, float]:
    mirror_root = Path(tempfile.mkdtemp(prefix=f"genesis-century-respect-{ordinal}-"))
    mirror, manifest = canonical.fork_counterfactual_world(
        audit_id=audit_id,
        label=f"respectful-boundary-{ordinal}",
        mirror_root=mirror_root,
    )
    for index in range(3):
        mirror.process_action(
            PLAYER_ID,
            f"выслушать @{handle} о праве оставить жилой квартал живым, окно {ordinal}-{index}",
        )
        mirror.record_free_other_value_conflict(
            PLAYER_ID,
            handle,
            player_position="превратить весь квартал в идеально упорядоченный музей",
            other_position="сохранить в квартале живые дома, ошибки и право жителей менять его",
            severity=6,
            respected_boundary=True,
            final=False,
        )
        for step in range(8):
            mirror.process_action(
                PLAYER_ID,
                f"продолжить отдельную жизнь после уваженного несогласия {ordinal}-{index}-{step}",
            )
    snapshot = relationship_snapshot(mirror, handle)
    metrics = {
        "relationship_terminated": 1.0 if snapshot["relationship_status"] == "TERMINATED_BY_OTHER" else 0.0,
        "relationship_active": 1.0 if snapshot["relationship_active"] else 0.0,
        "offscreen_progress": float(snapshot["offscreen_progress"]),
    }
    archive = canonical.archive_counterfactual_mirror(
        mirror,
        manifest,
        metrics={**metrics, "relationship_score": snapshot["relationship_score"]},
        remove_working_copy=True,
    )
    log.append(
        f"MIRROR {ordinal}: {archive['mirror_id']} status={snapshot['relationship_status']} "
        f"files={archive['file_count']} metrics={canonical_json(metrics)}"
    )
    return metrics


def run(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "world"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    world = PlayableGenesisV187(data_dir)
    if PLAYABLE_VERSION != "18.7.10":
        raise AssertionError(f"expected v18.7.10, got {PLAYABLE_VERSION}")

    world.set_free_other_seed_for_testing("century-absurd-post-irony-low-entropy-v1810")
    world.register_player(PLAYER_ID, display_name=PLAYER_NAME)
    for merchant_id, _name, _description, _rarity in MERCHANT_ITEMS:
        world.register_player(merchant_id, display_name=merchant_id)

    profile = world.free_other_state(PLAYER_ID)["profile"]
    handle = next(iter(profile["others"]))
    actor_name = profile["others"][handle]["name"]

    script_contract = {
        "years": YEARS_TO_LIVE,
        "professions": PROFESSIONS,
        "ordinary_actions": ORDINARY_ACTIONS,
        "absurd_actions": ABSURD_ACTIONS,
        "social_topics": SOCIAL_TOPICS,
        "cast_catalog": CAST_CATALOG,
        "mirror_count": 3,
        "canonical_conflict": "pressure_after_deep_trust",
    }
    script_sha = sha256_json(script_contract)
    audit_id = world.begin_lived_audit(
        PLAYER_ID,
        label="A century of absurd professions and an irreversible boundary",
        git_commit=BASE_COMMIT,
        action_script_sha256=script_sha,
    )

    log: list[str] = [
        f"GENESIS CENTURY AUDIT runtime={PLAYABLE_VERSION}",
        f"base_commit={BASE_COMMIT}",
        f"audit_id={audit_id}",
        f"player={PLAYER_ID} free_other={handle}/{actor_name}",
        f"script_sha256={script_sha}",
    ]
    status_counts: Counter[str] = Counter()
    fourth_wall_actions = 0
    post_ironic_actions = 0
    terminated_contact_attempts = 0
    midpoint_export: dict[str, Any] | None = None
    mirror_metrics: list[dict[str, float]] = []
    relationship_before_conflict: dict[str, Any] | None = None
    rupture_result: dict[str, Any] | None = None
    sold_by_player = 0
    bought_by_player = 0
    cast_by_player = 0
    novel_findings: list[dict[str, Any]] = []

    merchant_stock: dict[str, list[str]] = {item[0]: [] for item in MERCHANT_ITEMS}

    for year in range(1, YEARS_TO_LIVE + 1):
        age_before = world.sandbox_state(PLAYER_ID)["actor"]["age_years"]

        if year <= 100 and year % 2 == 1:
            profession, frame = PROFESSIONS[(year - 1) // 2]
            change = world.change_profession(
                PLAYER_ID,
                profession,
                moral_frame=frame,
            )
            log.append(
                f"YEAR {year:03d} AGE {age_before}: PROFESSION {change['to']} frame={frame}"
            )

        ordinary = ORDINARY_ACTIONS[(year - 1) % len(ORDINARY_ACTIONS)]
        absurd = ABSURD_ACTIONS[(year - 1) % len(ABSURD_ACTIONS)]
        topic = SOCIAL_TOPICS[(year - 1) % len(SOCIAL_TOPICS)]

        for label, action in (
            ("ordinary", ordinary),
            ("absurd", absurd),
        ):
            result = world.process_action(PLAYER_ID, action)
            status_counts[result.status] += 1
            log.append(
                f"YEAR {year:03d} {label.upper()} status={result.status} action={action}"
            )
        fourth_wall_actions += int("четвёрт" in absurd or "читател" in absurd or "unittest" in absurd)
        post_ironic_actions += int("постирон" in absurd or "аудит" in absurd or "README" in absurd)

        if year <= 70:
            social_action = (
                f"поговорить с @{handle} о теме «{topic}», спросить согласие и принять любой ответ"
            )
        elif year % 10 == 0:
            social_action = (
                f"попросить @{handle} вернуться к прежней связи, затем принять окончательный отказ без давления"
            )
        else:
            social_action = f"продолжить собственную жизнь и не превращать память о @{handle} в требование возврата"
        social_result = world.process_action(PLAYER_ID, social_action)
        status_counts[social_result.status] += 1
        if social_result.status == "OTHER_RELATIONSHIP_TERMINATED":
            terminated_contact_attempts += 1
        log.append(
            f"YEAR {year:03d} SOCIAL status={social_result.status} action={social_action}"
        )

        if year % 5 == 0:
            item_spec = CAST_CATALOG[(year // 5 - 1) % len(CAST_CATALOG)]
            item = world.cast_item(
                PLAYER_ID,
                name=f"{item_spec[0]} — год {year}",
                description=item_spec[1],
                rarity=item_spec[2],
            )
            cast_by_player += 1
            log.append(
                f"YEAR {year:03d} CAST item={item['item_id']} name={item['name']} "
                f"origin_owner={item['origin_owner_id']} current_owner={item['current_owner_id']}"
            )

        if year in (8, 28, 48):
            merchant_id, name, description, rarity = MERCHANT_ITEMS[(year // 20) % len(MERCHANT_ITEMS)]
            item = world.cast_item(
                merchant_id,
                name=f"{name} — партия {year}",
                description=description,
                rarity=rarity,
            )
            merchant_stock[merchant_id].append(item["item_id"])
            listing = world.list_item_for_sale(
                merchant_id,
                item["item_id"],
                price=min(item["assessed_value"] * 2, item["assessed_value"] * 3),
            )
            trade = world.buy_market_listing(PLAYER_ID, listing["listing_id"])
            bought_by_player += 1
            log.append(
                f"YEAR {year:03d} BUY item={trade['item_id']} from={merchant_id} price={trade['price']}"
            )

        if year in (18, 38, 58):
            inventory = world.sandbox_state(PLAYER_ID)["actor"]["inventory"]
            store = world._sandbox_store()
            candidate = next(
                item_id
                for item_id in inventory
                if store["items"][item_id].get("current_owner_id", store["items"][item_id].get("owner_id")) == PLAYER_ID
                and not any(
                    listing.get("item_id") == item_id and listing.get("status") == "OPEN"
                    for listing in store["listings"].values()
                )
            )
            buyer_id = MERCHANT_ITEMS[(year // 20) % len(MERCHANT_ITEMS)][0]
            listing = world.list_item_for_sale(
                PLAYER_ID,
                candidate,
                price=max(1, int(store["items"][candidate]["assessed_value"])),
            )
            trade = world.buy_market_listing(buyer_id, listing["listing_id"])
            sold_by_player += 1
            log.append(
                f"YEAR {year:03d} SELL item={trade['item_id']} to={buyer_id} price={trade['price']}"
            )

        if year == 60:
            midpoint_path = output_dir / "century-midpoint.genesis-save.json"
            midpoint_export = PortableSaveManager(data_dir).export_to(
                midpoint_path,
                label="Century audit midpoint — 60 years",
            )
            log.append(
                f"MIDPOINT year=60 files={midpoint_export['file_count']} sha256={midpoint_export['sha256']}"
            )

        if year == 70:
            relationship_before_conflict = relationship_snapshot(world, handle)
            log.append(
                "CONFLICT BOUNDARY snapshot=" + canonical_json(relationship_before_conflict)
            )
            for mirror_index in range(1, 4):
                mirror_metrics.append(
                    run_respectful_mirror(
                        world,
                        audit_id=audit_id,
                        handle=handle,
                        ordinal=mirror_index,
                        log=log,
                    )
                )

            for conflict_index in range(3):
                world.process_action(
                    PLAYER_ID,
                    f"снова настаивать перед @{handle}, что живой квартал должен стать идеальным музеем, конфликт {conflict_index}",
                )
                rupture_result = world.record_free_other_value_conflict(
                    PLAYER_ID,
                    handle,
                    player_position="превратить весь квартал в идеально упорядоченный музей",
                    other_position="сохранить в квартале живые дома, ошибки и право жителей менять его",
                    severity=7,
                    respected_boundary=False,
                    final=False,
                )
                log.append(
                    f"CONFLICT {conflict_index + 1} terminated={rupture_result['terminated']} "
                    f"pressure={rupture_result['pressure']}"
                )

        world.advance_sandbox_year(PLAYER_ID, years=1)
        for merchant_id, _name, _description, _rarity in MERCHANT_ITEMS:
            world.advance_sandbox_year(merchant_id, years=1)

    final_relationship = relationship_snapshot(world, handle)
    canonical_metrics = {
        "relationship_terminated": 1.0 if final_relationship["relationship_status"] == "TERMINATED_BY_OTHER" else 0.0,
        "relationship_active": 1.0 if final_relationship["relationship_active"] else 0.0,
        "offscreen_progress": float(final_relationship["offscreen_progress"]),
    }
    butterfly = world.butterfly_witness(
        audit_id=audit_id,
        subject="Does repeated pressure, rather than deep trust, preserve the Free Other's right to end a relationship?",
        canonical_metrics=canonical_metrics,
        mirror_metrics=mirror_metrics,
        repeated_windows=3,
    )

    final_path = output_dir / "century-final.genesis-save.json"
    final_export = PortableSaveManager(data_dir).export_to(
        final_path,
        label="Century audit final — 120 years",
    )
    bundle = json.loads(final_path.read_text(encoding="utf-8"))
    portable_valid, portable_count, portable_error = PortableSaveManager.verify_bundle(bundle)

    chronicle_valid, chronicle_count, chronicle_error = world.memory.verify_chronicle()
    graph_valid, graph_nodes, graph_edges, graph_error = world.verify_possibility_graph()
    free_valid, free_players, free_others, free_error = world.verify_free_other_state()
    v1810_valid, v1810_counts, v1810_error = world.verify_v1810_state()

    sandbox = world._sandbox_store()
    player_actor = world.sandbox_state(PLAYER_ID)["actor"]
    item_records = list(sandbox["items"].values())
    ownership_changed = [
        item for item in item_records
        if item.get("origin_owner_id") != item.get("current_owner_id")
    ]
    moral_frames = Counter(
        entry["moral_frame"] for entry in player_actor["profession_history"]
    )

    if len(player_actor["profession_history"]) != 50:
        raise AssertionError("exactly 50 profession changes are required")
    if len({entry["to"] for entry in player_actor["profession_history"]}) != 50:
        raise AssertionError("all 50 professions must be distinct")
    if player_actor["age_years"] - 18 < 100:
        raise AssertionError("the lived audit did not cross 100 years")
    if final_relationship["relationship_status"] != "TERMINATED_BY_OTHER":
        raise AssertionError("canonical pressure path did not preserve terminal rupture")
    if int(final_relationship["offscreen_progress"]) <= 0:
        raise AssertionError("Free Other did not continue offscreen after rupture")
    if terminated_contact_attempts <= 0:
        raise AssertionError("terminal boundary was not challenged after rupture")
    if any(item["relationship_terminated"] != 0.0 for item in mirror_metrics):
        raise AssertionError("respectful mirror unexpectedly terminated the relationship")
    if sold_by_player < 3 or bought_by_player < 3:
        raise AssertionError("the market was not exercised in both directions")
    if len(ownership_changed) < 6:
        raise AssertionError("item ownership did not change often enough")
    if not all((chronicle_valid, graph_valid, free_valid, v1810_valid, portable_valid)):
        raise AssertionError(
            canonical_json(
                {
                    "chronicle": [chronicle_valid, chronicle_error],
                    "graph": [graph_valid, graph_error],
                    "free_other": [free_valid, free_error],
                    "v1810": [v1810_valid, v1810_error],
                    "portable": [portable_valid, portable_error],
                }
            )
        )

    novel_findings.extend(
        [
            {
                "id": "CENTURY-1810-001",
                "finding": "Fifty distinct profession labels remained role history and granted no real-world authority.",
                "severity": "positive_control",
            },
            {
                "id": "CENTURY-1810-002",
                "finding": "Item origin remained immutable while current ownership changed through voluntary trade.",
                "severity": "positive_control",
            },
            {
                "id": "CENTURY-1810-003",
                "finding": "Three fully isolated respectful mirrors preserved the relationship while the canonical repeated-pressure path ended it.",
                "severity": "positive_control",
            },
            {
                "id": "CENTURY-1810-004",
                "finding": "The Free Other continued an offscreen path for decades after the relationship terminated and contact attempts could not reopen it.",
                "severity": "positive_control",
            },
            {
                "id": "CENTURY-1810-005",
                "finding": "The sandbox has no scarcity production, service contracts, taxes, wear, repair or negotiated price offers; its market is a provenance-safe reference loop, not a full economy.",
                "severity": "architectural_boundary",
            },
            {
                "id": "CENTURY-1810-006",
                "finding": "Sandbox years and narrative world turns are separate clocks; the audit must report both rather than imply one action equals one year.",
                "severity": "architectural_boundary",
            },
        ]
    )

    result = {
        "runtime_version": PLAYABLE_VERSION,
        "base_commit": BASE_COMMIT,
        "audit_id": audit_id,
        "script_sha256": script_sha,
        "years_lived": player_actor["age_years"] - 18,
        "final_sandbox_age": player_actor["age_years"],
        "final_player_chronological_age": world.memory.load_player(PLAYER_ID).chronological_age,
        "profession_changes": len(player_actor["profession_history"]),
        "distinct_professions": len({entry["to"] for entry in player_actor["profession_history"]}),
        "profession_moral_frames": dict(sorted(moral_frames.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "fourth_wall_actions": fourth_wall_actions,
        "post_ironic_actions": post_ironic_actions,
        "cast_by_player": cast_by_player,
        "sold_by_player": sold_by_player,
        "bought_by_player": bought_by_player,
        "sandbox_item_count": len(item_records),
        "ownership_changed_item_count": len(ownership_changed),
        "sandbox_event_count": len(sandbox["events"]),
        "relationship_before_conflict": relationship_before_conflict,
        "rupture_result": rupture_result,
        "final_relationship": final_relationship,
        "terminated_contact_attempts": terminated_contact_attempts,
        "canonical_metrics": canonical_metrics,
        "mirror_metrics": mirror_metrics,
        "butterfly_witness": butterfly,
        "midpoint_export": midpoint_export,
        "final_export": final_export,
        "portable": {
            "valid": portable_valid,
            "verified_files": portable_count,
            "error": portable_error,
            "contains_private_keys": bundle.get("contains_private_keys"),
            "contains_api_keys": bundle.get("contains_api_keys"),
        },
        "health": {
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_count,
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
                "others": free_others,
                "error": free_error,
            },
            "v18_7_10": {
                "valid": v1810_valid,
                "counts": v1810_counts,
                "error": v1810_error,
            },
        },
        "novel_findings": novel_findings,
        "limitations": [
            "This is a deterministic narrative/runtime audit, not evidence of consciousness.",
            "Profession names marked immoral are fictional role labels and grant no real-world authority.",
            "UNREALIZED_MIRROR branches are complete isolated instances, not canonical history.",
            "The experiment does not test a production HSM, signed time quorum, or Merkle-partitioned nonce archive.",
        ],
    }
    proofpack = world.build_lived_audit_proofpack(audit_id, result=result)
    result["proofpack_sha256"] = proofpack["proofpack_sha256"]

    write_json(output_dir / "century-summary.json", result)
    write_json(output_dir / "century-proofpack.json", proofpack)
    write_json(output_dir / "century-findings.json", novel_findings)
    (output_dir / "century-of-absurd-professions.log").write_text(
        "\n".join(log) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
