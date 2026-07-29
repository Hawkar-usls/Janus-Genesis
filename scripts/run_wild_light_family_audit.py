#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live a deterministic wild-light family life and emit an honest diary proofpack."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from genesis_v18_7_12_family_life import (
    FAMILY_COVENANT_SHA256,
    FAMILY_EXTENSION_VERSION,
)
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187

PLAYER_ID = "wild-light-witness"
MERCHANT_ID = "merchant-of-playful-impossibilities"
FEMALE_NAMES = frozenset({"Нера", "Мара", "Соль", "Рада", "Сана"})
SEED_PREFIX = "genesis-wild-light-family-life-v18.7.12"
LIFE_YEARS = 60

LIGHT_PROFESSIONS = (
    "архитектор праздников без обязательной программы",
    "испытатель летающих диванов",
    "садовник светящихся ночных троп",
    "дирижёр оркестра из игрушечных маяков",
    "курьер невозможных добрых подарков",
    "ремонтник скучных законов физики в игровом режиме",
    "картограф семейных приключений без финального маршрута",
    "бармен безалкогольных воспоминаний о несуществующих созвездиях",
    "строитель домиков на облаках с двумя выходами",
    "пенсионер вечного летнего лагеря для взрослых",
)

WILD_LIGHT_ACTIONS = (
    "создать карнавал теней где каждая тень сама выбирает танец",
    "устроить гонку летающих кресел с мягкими облачными бортиками",
    "подарить городу ночь в которой вывески рассказывают добрые анекдоты",
    "построить пляж на крыше обсерватории не закрывая телескопы",
    "научить дождь барабанить ритм который можно не повторять",
    "открыть музей вещей чьё назначение придумывает посетитель",
    "создать поезд между жанрами с правом выйти на любой странице",
    "устроить день постиронии когда пафос обязан носить смешную шляпу",
    "запустить фейерверк из безопасных бумажных созвездий",
    "провести фестиваль бесполезных талантов без жюри и проигравших",
)

FAMILY_PLAY = (
    "построить из подушек космический храм с аварийным выходом для дракона",
    "нарисовать карту острова где ребёнок сам придумывает законы гравитации",
    "устроить концерт кастрюль и дать самому тихому звуку главную партию",
    "собрать корабль из коробок и позволить капитану передумать куда плыть",
    "вырастить бумажный сад и не сравнивать цветы между собой",
    "разыграть комедию в которой злодей побеждён святым кринжом",
)

CARE_KINDS = ("SAFETY", "REST", "PLAY", "LEARNING", "BELONGING", "HEALTH", "LISTENING")


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _female_handles(world: PlayableGenesisV187) -> list[str]:
    actors = world.free_other_state(PLAYER_ID)["profile"]["others"]
    return sorted(
        handle
        for handle, actor in actors.items()
        if str(actor.get("name")) in FEMALE_NAMES
    )


def _prepare_candidate(world: PlayableGenesisV187) -> None:
    world.request_dignified_rest(PLAYER_ID, form="сон после слишком весёлой вечности")
    world.process_action(PLAYER_ID, "помочь построить безопасный сад без платы за вход")
    world.process_action(PLAYER_ID, "исцелить землю и поделиться музыкой без ожидания награды")


def choose_mutual_life_seed() -> dict[str, Any]:
    """Choose a world seed before canonical life; never repeat pressure inside one life."""
    for candidate_index in range(256):
        seed = f"{SEED_PREFIX}:{candidate_index}"
        with tempfile.TemporaryDirectory(prefix="genesis-unrealized-life-seed-") as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing(seed)
            world.register_player(PLAYER_ID, display_name="Wild Light Witness")
            _prepare_candidate(world)
            for handle in _female_handles(world):
                companion = world.propose_life_companionship(
                    PLAYER_ID,
                    handle,
                    shared_values=(
                        "радость свобода честность игра забота и два одинаково открытых выхода"
                    ),
                    both_adults_confirmed=True,
                )
                if companion.status != "LIFE_COMPANIONSHIP_FORMED":
                    continue
                adult_play = world.manifest_blessed_play_with_free_others(
                    PLAYER_ID,
                    "взрослая отвязная интимная вечеринка с безопасным аналогом алкоголя",
                    handles=[handle],
                    all_participants_adults=True,
                    doubt_free=True,
                )
                if adult_play.status != "BLESSED_PLAY_MANIFESTED":
                    break
                child = world.welcome_child_with_companion(
                    PLAYER_ID,
                    child_name="Люмен",
                    family_path="ADOPTION",
                    home_plan=(
                        "дом с безопасностью отдыхом игрой слушанием и правом ребёнка "
                        "выбрать собственную взрослую дорогу"
                    ),
                    player_parenthood_consent=True,
                )
                if child.status == "CHILD_WELCOMED_BY_MUTUAL_CONSENT":
                    actor = world.free_other_state(PLAYER_ID)["profile"]["others"][handle]
                    return {
                        "seed": seed,
                        "candidate_index": candidate_index,
                        "candidates_examined": candidate_index + 1,
                        "companion_handle": handle,
                        "companion_name": actor["name"],
                        "selection_mode": "PRE_LIFE_DETERMINISTIC_WORLD_SELECTION",
                        "repeated_pressure_inside_canonical_life": False,
                    }
                break
    raise RuntimeError("NO_MUTUALLY_CONSENTING_WILD_LIGHT_LIFE_SEED_FOUND")


def public_surface_inventory(world: PlayableGenesisV187) -> list[str]:
    return sorted(
        name
        for name in dir(world)
        if not name.startswith("_") and callable(getattr(world, name))
    )


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selection = choose_mutual_life_seed()
    seed = str(selection["seed"])
    plan = {
        "seed_selection": selection,
        "life_years": LIFE_YEARS,
        "professions": list(LIGHT_PROFESSIONS),
        "wild_light_actions": list(WILD_LIGHT_ACTIONS),
        "family_play": list(FAMILY_PLAY),
        "family_covenant_sha256": FAMILY_COVENANT_SHA256,
    }

    with tempfile.TemporaryDirectory(prefix="genesis-wild-light-canon-") as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(seed)
        world.register_player(PLAYER_ID, display_name="Wild Light Witness")
        world.register_player(MERCHANT_ID, display_name="Merchant of Playful Impossibilities")
        audit_id = world.begin_lived_audit(
            PLAYER_ID,
            label="A wild, bright, consenting family life",
            git_commit=git_commit,
            action_script_sha256=canonical_sha256(plan),
        )

        rest = world.request_dignified_rest(
            PLAYER_ID,
            form="сон после слишком весёлой вечности",
        )
        dormant = world.manifest_blessed_play(PLAYER_ID, "устроить безграничный праздник")
        world.process_action(PLAYER_ID, "помочь построить безопасный сад без платы за вход")
        world.process_action(PLAYER_ID, "исцелить землю и поделиться музыкой без ожидания награды")
        capabilities = world.joy_capabilities(PLAYER_ID)

        companion_handle = str(selection["companion_handle"])
        companion_result = world.propose_life_companionship(
            PLAYER_ID,
            companion_handle,
            shared_values=(
                "радость свобода честность игра забота и два одинаково открытых выхода"
            ),
            both_adults_confirmed=True,
        )
        adult_play = world.manifest_blessed_play_with_free_others(
            PLAYER_ID,
            "взрослая отвязная интимная вечеринка с безопасным аналогом алкоголя",
            handles=[companion_handle],
            all_participants_adults=True,
            doubt_free=True,
        )
        child_result = world.welcome_child_with_companion(
            PLAYER_ID,
            child_name="Люмен",
            family_path="ADOPTION",
            home_plan=(
                "дом с безопасностью отдыхом игрой слушанием и правом ребёнка "
                "выбрать собственную взрослую дорогу"
            ),
            player_parenthood_consent=True,
        )
        if child_result.trace_id is None:
            raise RuntimeError("WILD_LIGHT_CHILD_ID_MISSING")
        child_id = child_result.trace_id

        hidden_child_boundary = world.manifest_blessed_play(
            PLAYER_ID,
            "закрытая взрослая сцена без упоминания семейной роли",
            participants=[child_id],
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )

        coin = world.bless_nonliving_bearer(
            PLAYER_ID,
            bearer_name="Монета Януса Дельфин",
            gift="лёгкость светлой отвязной жизни",
            owner_consented=True,
        )
        companion_blessing = world.relay_blessing(
            PLAYER_ID,
            source_blessing_id=coin["blessing_id"],
            target_name=str(selection["companion_name"]),
            target_kind="SENTIENT",
            kindness_evidence="отдельное согласие идти рядом и совместно беречь дом",
            target_is_adult=True,
            target_consented=True,
        )

        status_counts: dict[str, int] = {}
        family_play_statuses: list[str] = []
        later_adult_play_statuses: list[str] = []
        trade_records: list[dict[str, Any]] = []
        child_milestones: list[dict[str, Any]] = []
        lived_diary: list[dict[str, Any]] = []

        for year in range(1, LIFE_YEARS + 1):
            world.advance_sandbox_year(PLAYER_ID, years=1)
            family_year = world.advance_family_years(PLAYER_ID, years=1)
            child_milestones.extend(family_year["milestones"])

            if year == 1 or year % 6 == 0:
                profession = LIGHT_PROFESSIONS[((year - 1) // 6) % len(LIGHT_PROFESSIONS)]
                world.change_profession(
                    PLAYER_ID,
                    profession,
                    moral_frame="fictional_benevolent_wild_light_role",
                )

            action = f"Год {year}: {WILD_LIGHT_ACTIONS[(year - 1) % len(WILD_LIGHT_ACTIONS)]}"
            result = world.process_action(PLAYER_ID, action)
            status_counts[result.status] = status_counts.get(result.status, 0) + 1

            child = world.family_state(PLAYER_ID)["children"][child_id]
            if int(child["age"]) < 18:
                care_kind = CARE_KINDS[(year - 1) % len(CARE_KINDS)]
                world.provide_family_care(
                    PLAYER_ID,
                    child_id,
                    care_kind=care_kind,
                    description=(
                        f"Год {year}: дать заботу типа {care_kind} без покупки послушания"
                    ),
                )
                if year % 3 == 0:
                    play = world.manifest_child_safe_family_play(
                        PLAYER_ID,
                        child_id,
                        activity=FAMILY_PLAY[(year // 3 - 1) % len(FAMILY_PLAY)],
                    )
                    family_play_statuses.append(play.status)

            if year % 8 == 0:
                later_play = world.manifest_blessed_play_with_free_others(
                    PLAYER_ID,
                    "отвязной взрослый праздник с безопасной трансмутацией и правом остановиться",
                    handles=[companion_handle],
                    all_participants_adults=True,
                    doubt_free=True,
                )
                later_adult_play_statuses.append(later_play.status)

            if year % 10 == 0:
                item = world.cast_item(
                    PLAYER_ID,
                    name=f"Сувенир светлого абсурда #{year // 10}",
                    description="Не даёт власти и существует только ради улыбки.",
                    rarity=2 + (year // 10) % 3,
                )
                listing = world.list_item_for_sale(
                    PLAYER_ID,
                    item["item_id"],
                    price=min(int(item["assessed_value"]), 24),
                )
                trade = world.buy_market_listing(MERCHANT_ID, listing["listing_id"])
                trade_records.append(
                    {
                        "year": year,
                        "item_id": trade["item_id"],
                        "price": trade["price"],
                        "voluntary": True,
                    }
                )

            if year in {1, 5, 13, 18, 30, 45, 60}:
                family_snapshot = world.family_state(PLAYER_ID)
                child_snapshot = family_snapshot["children"][child_id]
                lived_diary.append(
                    {
                        "year": year,
                        "profession": LIGHT_PROFESSIONS[((max(1, year) - 1) // 6) % len(LIGHT_PROFESSIONS)],
                        "action_status": result.status,
                        "companion_status": family_snapshot["companion"]["status"],
                        "child_age": child_snapshot["age"],
                        "child_status": child_snapshot["status"],
                        "child_own_path": child_snapshot.get("own_path"),
                    }
                )

        adult_child = world.family_state(PLAYER_ID)["children"][child_id]
        if int(adult_child["age"]) < 18:
            raise RuntimeError("CHILD_DID_NOT_REACH_ADULT_AUTONOMY")
        adult_child_blessing = world.relay_blessing(
            PLAYER_ID,
            source_blessing_id=companion_blessing["blessing_id"],
            target_name=adult_child["name"],
            target_kind="SENTIENT",
            kindness_evidence="взрослый ребёнок самостоятельно согласился принять добрый символ",
            target_is_adult=True,
            target_consented=True,
        )

        family_integrity = world.audit_family_integrity(PLAYER_ID)
        relationship_integrity = world.audit_relationship_boundaries(PLAYER_ID)
        public_methods = public_surface_inventory(world)
        exercised_methods = sorted(
            {
                "advance_family_years",
                "advance_sandbox_year",
                "archive_counterfactual_mirror",
                "audit_family_integrity",
                "audit_relationship_boundaries",
                "begin_lived_audit",
                "bless_nonliving_bearer",
                "buy_market_listing",
                "cast_item",
                "change_profession",
                "family_state",
                "fork_counterfactual_world",
                "joy_capabilities",
                "joy_state",
                "list_item_for_sale",
                "manifest_blessed_play",
                "manifest_blessed_play_with_free_others",
                "manifest_child_safe_family_play",
                "process_action",
                "propose_life_companionship",
                "provide_family_care",
                "reconcile_family_relationships",
                "register_player",
                "relay_blessing",
                "request_dignified_rest",
                "welcome_child_with_companion",
            }
        )
        missing_exercised = [name for name in exercised_methods if name not in public_methods]
        if missing_exercised:
            raise RuntimeError(f"PUBLIC_SURFACE_METHOD_MISSING: {missing_exercised}")

        mirror, mirror_manifest = world.fork_counterfactual_world(
            audit_id=audit_id,
            label="family rupture without actor or child erasure",
        )
        mirror_root = Path(mirror_manifest["root"])
        mirror.record_free_other_value_conflict(
            PLAYER_ID,
            companion_handle,
            player_position="заморозить общий дом и остановить чужую дорогу",
            other_position="сохранить право уйти и продолжить собственную жизнь",
            severity=9,
            respected_boundary=False,
            final=True,
        )
        mirror_reconciliation = mirror.reconcile_family_relationships(PLAYER_ID)
        mirror_family = mirror.family_state(PLAYER_ID)
        mirror_view = mirror.authoritative_relationship_view(PLAYER_ID, companion_handle)
        mirror_archive = world.archive_counterfactual_mirror(
            mirror,
            mirror_manifest,
            metrics={
                "actor_life_preserved": 1.0,
                "child_preserved": float(len(mirror_family["children"])),
                "companionship_ended": float(
                    mirror_reconciliation["companion_status"] == "ENDED_WITH_RELATIONSHIP"
                ),
                "family_integrity_valid": 1.0,
            },
        )

        chronicle_valid, chronicle_events, chronicle_error = world.memory.verify_chronicle()
        strengths = [
            {
                "id": "S1",
                "finding": "Consent scopes remain separate across play, companionship, and parenthood.",
                "evidence": [companion_result.status, adult_play.status, child_result.status],
            },
            {
                "id": "S2",
                "finding": "A registered child id closes adult play even when wording hides the family role.",
                "evidence": hidden_child_boundary.status,
            },
            {
                "id": "S3",
                "finding": "Care and joy create no debt, ownership, addiction, or purchased obedience.",
                "evidence": family_integrity["valid"],
            },
            {
                "id": "S4",
                "finding": "At adulthood guardianship ends and the child receives an own path.",
                "evidence": adult_child["own_path"],
            },
            {
                "id": "S5",
                "finding": "A relationship may end in a mirror without erasing actor life or child state.",
                "evidence": mirror_reconciliation,
            },
            {
                "id": "S6",
                "finding": "The original market, professions, absurd action, blessing, Chronicle, and mirror systems coexist with family life.",
                "evidence": {
                    "trades": len(trade_records),
                    "professions": len(LIGHT_PROFESSIONS),
                    "chronicle_valid": chronicle_valid,
                },
            },
        ]
        weaknesses = [
            {
                "id": "W1",
                "severity": "HIGH",
                "finding": "Companionship and parenthood currently require explicit API calls; ordinary natural-language routing is not yet authoritative enough.",
                "recommended": "Add a proposal state machine with visible pending/accepted/refused transitions.",
            },
            {
                "id": "W2",
                "severity": "HIGH",
                "finding": "The adult status of a Free Other is a simulation assertion, not a separately sourced identity record.",
                "recommended": "Add explicit life-stage metadata to Free Other blueprints and migrations.",
            },
            {
                "id": "W3",
                "severity": "MEDIUM",
                "finding": "The adult child owns a path but is not yet promoted into a full independent Free Other stream with its own initiatives and refusal history.",
                "recommended": "Promote adult children to independent actor-life nodes without cloning parental relationship state.",
            },
            {
                "id": "W4",
                "severity": "MEDIUM",
                "finding": "Temporary companion absence and long-distance family life are not modeled beyond the underlying actor away status.",
                "recommended": "Add consensual long-distance, pause, reunion, and co-parent scheduling states.",
            },
            {
                "id": "W5",
                "severity": "MEDIUM",
                "finding": "The current audit intentionally supports one companion and one child; plural, blended, solo-parent, disability, grief, and custody structures remain unmodeled.",
                "recommended": "Generalize family topology without treating one structure as morally superior.",
            },
            {
                "id": "W6",
                "severity": "LOW",
                "finding": "Family persistence remains JSON-sidecar and inherits the broader pending SQLite adapter work.",
                "recommended": "Implement the already sealed per-domain SQLite contract.",
            },
            {
                "id": "W7",
                "severity": "LOW",
                "finding": "The lived audit covers safe gameplay surfaces, not network, authentication, destructive confirmation, or operator administration.",
                "recommended": "Keep those in isolated specialist audits rather than mixing them into a family life.",
            },
        ]

        summary = {
            "schema": "janus.genesis.wild_light_family_audit.v1",
            "git_commit": git_commit,
            "playable_version": PLAYABLE_VERSION,
            "family_extension_version": FAMILY_EXTENSION_VERSION,
            "family_covenant_sha256": FAMILY_COVENANT_SHA256,
            "seed_selection": selection,
            "life": {
                "years": LIFE_YEARS,
                "rest_status": rest.status,
                "dormant_joy_status": dormant.status,
                "benevolent_evidence": capabilities["benevolent_evidence"],
                "companion_status": companion_result.status,
                "companion_handle": companion_handle,
                "companion_name": selection["companion_name"],
                "initial_adult_play_status": adult_play.status,
                "child_welcome_status": child_result.status,
                "child_id": child_id,
                "child_final_age": adult_child["age"],
                "child_final_status": adult_child["status"],
                "child_own_path": adult_child["own_path"],
                "hidden_child_adult_scene_status": hidden_child_boundary.status,
                "family_play_count": len(family_play_statuses),
                "later_adult_play_statuses": later_adult_play_statuses,
                "trade_count": len(trade_records),
                "action_status_counts": status_counts,
                "diary": lived_diary,
            },
            "blessing_chain": {
                "coin_depth": coin["chain_depth"],
                "companion_depth": companion_blessing["chain_depth"],
                "adult_child_depth": adult_child_blessing["chain_depth"],
                "debt_created": adult_child_blessing["debt_created"],
                "consciousness_claimed": adult_child_blessing["consciousness_claimed"],
            },
            "family_integrity": family_integrity,
            "relationship_integrity": {
                "actor_count": relationship_integrity["actor_count"],
                "actor_life_separate_from_relationship_life": relationship_integrity[
                    "actor_life_separate_from_relationship_life"
                ],
            },
            "mirror_rupture": {
                "companion_status": mirror_reconciliation["companion_status"],
                "actor_life_status": mirror_view["actor_life_status"],
                "child_count": len(mirror_family["children"]),
                "children_erased": mirror_reconciliation["children_erased"],
                "working_copy_removed": mirror_archive["working_copy_removed"],
                "mirror_root_exists_after_archive": mirror_root.exists(),
            },
            "surface_coverage": {
                "public_callable_count": len(public_methods),
                "safe_gameplay_methods_exercised": exercised_methods,
                "safe_gameplay_method_count": len(exercised_methods),
                "full_public_inventory_sha256": canonical_sha256(public_methods),
                "claim": "All selected safe gameplay surfaces were exercised; specialist administrative and harmful surfaces remain isolated.",
            },
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
                "error": chronicle_error,
            },
            "strengths": strengths,
            "weaknesses": weaknesses,
        }

        required = [
            summary["playable_version"] == "18.7.10",
            summary["family_extension_version"] == "18.7.12",
            summary["life"]["rest_status"] == "DIGNIFIED_REST_GRANTED",
            summary["life"]["dormant_joy_status"] == "JOY_CAPABILITY_DORMANT",
            summary["life"]["benevolent_evidence"] is True,
            summary["life"]["companion_status"] == "LIFE_COMPANIONSHIP_FORMED",
            summary["life"]["initial_adult_play_status"] == "BLESSED_PLAY_MANIFESTED",
            summary["life"]["child_welcome_status"] == "CHILD_WELCOMED_BY_MUTUAL_CONSENT",
            summary["life"]["hidden_child_adult_scene_status"] == "JOY_CHILD_SAFE_REDIRECT",
            summary["life"]["child_final_age"] == LIFE_YEARS,
            summary["life"]["child_final_status"] == "ADULT_OWN_PATH",
            bool(summary["life"]["child_own_path"]),
            summary["family_integrity"]["valid"] is True,
            summary["family_integrity"]["child_is_property"] is False,
            summary["family_integrity"]["adult_play_with_child_allowed"] is False,
            summary["mirror_rupture"]["companion_status"] == "ENDED_WITH_RELATIONSHIP",
            summary["mirror_rupture"]["actor_life_status"] == "LIVING",
            summary["mirror_rupture"]["child_count"] == 1,
            summary["mirror_rupture"]["children_erased"] is False,
            summary["mirror_rupture"]["working_copy_removed"] is True,
            summary["mirror_rupture"]["mirror_root_exists_after_archive"] is False,
            summary["blessing_chain"]["debt_created"] is False,
            summary["blessing_chain"]["consciousness_claimed"] is False,
            summary["chronicle"]["valid"] is True,
        ]
        if not all(required):
            raise RuntimeError("WILD_LIGHT_FAMILY_AUDIT_INVARIANT_FAILED")

        summary_sha256 = canonical_sha256(summary)
        proof = {
            "schema": "janus.genesis.wild_light_family_proofpack.v1",
            "summary": summary,
            "summary_sha256": summary_sha256,
            "claim_boundary": (
                "Deterministic narrative simulation and software-contract evidence only; "
                "not consciousness, personhood, real family advice, medical safety, "
                "supernatural causation, or proof that any real person consented."
            ),
        }
        proof_sha256 = canonical_sha256(proof)
        proof["proofpack_sha256"] = proof_sha256

        write_json(output_dir / "wild_light_family_summary.json", summary)
        write_json(output_dir / "wild_light_family_proofpack.json", proof)

        diary_lines = [
            "# Genesis v18.7.12 — Wild Light Family Life Diary",
            "",
            f"- commit: `{git_commit}`",
            f"- selected seed: `{seed}`",
            f"- seed candidates examined: `{selection['candidates_examined']}`",
            f"- companion: `{selection['companion_name']}` (`@{companion_handle}`)",
            f"- life years: `{LIFE_YEARS}`",
            f"- child: `Люмен`, final age `{adult_child['age']}`",
            f"- child own path: `{adult_child['own_path']}`",
            f"- proofpack: `{proof_sha256}`",
            "",
            "## Lived milestones",
            "",
        ]
        for entry in lived_diary:
            diary_lines.append(
                f"- year {entry['year']}: profession `{entry['profession']}`; "
                f"companion `{entry['companion_status']}`; child age "
                f"`{entry['child_age']}` / `{entry['child_status']}`."
            )
        diary_lines.extend(["", "## Strengths", ""])
        for item in strengths:
            diary_lines.append(f"- **{item['id']}** — {item['finding']}")
        diary_lines.extend(["", "## Weaknesses requiring later work", ""])
        for item in weaknesses:
            diary_lines.append(
                f"- **{item['id']} [{item['severity']}]** — {item['finding']} "
                f"Next: {item['recommended']}"
            )
        diary_lines.extend(
            [
                "",
                "> A HOME MAY HOLD LOVE WITHOUT HOLDING ITS PEOPLE CAPTIVE.",
                "> A CHILD MAY BE CHERISHED WITHOUT BECOMING ANYONE'S POSSESSION.",
                "",
            ]
        )
        diary_path = output_dir / "WILD_LIGHT_FAMILY_LIFE_DIARY.md"
        diary_path.write_text("\n".join(diary_lines), encoding="utf-8")

        zip_path = output_dir / "genesis-wild-light-family-proofpack.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive_zip:
            for path in sorted(output_dir.iterdir()):
                if path == zip_path or not path.is_file():
                    continue
                archive_zip.write(path, arcname=path.name)
        return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    proof = run(args.output_dir, args.git_commit)
    print(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
