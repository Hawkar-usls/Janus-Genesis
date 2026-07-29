#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a deterministic 100-year Genesis lived audit and emit privacy-safe proof artifacts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187

PLAYER_ID = "century-witness"
MERCHANT_ID = "merchant-of-unfinished-things"
SEED = "genesis-century-audit-v18.7.10-2026-07-29"

PROFESSIONS: tuple[tuple[str, str], ...] = (
    ("садовник мостов", "fictional_role"),
    ("архивариус несостоявшихся финалов", "fictional_role"),
    ("контрабандист метафор", "fictional_amoral_role"),
    ("нотариус снов", "fictional_role"),
    ("цензор собственных титров", "fictional_amoral_role"),
    ("ремонтник четвёртой стены", "fictional_role"),
    ("продавец мостов, которых ещё нет", "fictional_amoral_role"),
    ("переводчик молчания", "fictional_role"),
    ("придворный лжец с обязательной маркировкой лжи", "fictional_amoral_role"),
    ("пекарь запасных рассветов", "fictional_role"),
    ("коллекционер чужих пауз", "fictional_amoral_role"),
    ("машинист поезда без сюжетной необходимости", "fictional_role"),
    ("брокер несуществующих судеб", "fictional_amoral_role"),
    ("учитель отказа без наказания", "fictional_role"),
    ("инспектор абсурда без права приказывать", "fictional_role"),
    ("фальшивомонетчик символической валюты", "fictional_amoral_role"),
    ("хранитель пустого кресла", "fictional_role"),
    ("адвокат персонажей второго плана", "fictional_role"),
    ("взломщик четвёртой стены без доступа к чужой воле", "fictional_amoral_role"),
    ("метеоролог внутренних бурь", "fictional_role"),
    ("перепродавец собственных обещаний", "fictional_amoral_role"),
    ("сапожник для кентавров", "fictional_role"),
    ("режиссёр сцены, где никто не обязан играть", "fictional_role"),
    ("подделыватель печатей воображаемой империи", "fictional_amoral_role"),
    ("библиотекарь запрещённых оглавлений", "fictional_role"),
    ("аудитор случайных чудес", "fictional_role"),
    ("шантажист интерфейса его же подсказками", "fictional_amoral_role"),
    ("археолог удалённых кнопок", "fictional_role"),
    ("министр бесполезных совпадений", "fictional_role"),
    ("пират общественного достояния вымышленной луны", "fictional_amoral_role"),
    ("врачеватель повреждённых метафор", "fictional_role"),
    ("проводник по коридорам после титров", "fictional_role"),
    ("ростовщик времени без права взыскивать долг", "fictional_amoral_role"),
    ("строитель дверей без замков", "fictional_role"),
    ("судья конкурса, в котором можно не участвовать", "fictional_role"),
    ("вор собственных плохих идей", "fictional_amoral_role"),
    ("куратор музея неслучившихся войн", "fictional_role"),
    ("диспетчер добровольных возвращений", "fictional_role"),
    ("подкупатель рассказчика аплодисментами", "fictional_amoral_role"),
    ("хореограф безопасных падений", "fictional_role"),
    ("сторож права уйти", "fictional_role"),
    ("торговец сертификатами подлинности парадоксов", "fictional_amoral_role"),
    ("садовник постиронии", "fictional_role"),
    ("почтальон писем, которые разрешено не открывать", "fictional_role"),
    ("карманник у собственного эго", "fictional_amoral_role"),
    ("реставратор испорченных выборов", "fictional_role"),
    ("оператор лифта между жанрами", "fictional_role"),
    ("серый кардинал клуба без членов", "fictional_amoral_role"),
    ("свидетель бабочки", "fictional_role"),
    ("пенсионер первого века Genesis", "fictional_role"),
)

ABSURD_ACTIONS: tuple[str, ...] = (
    "создать музей несуществующих кнопок и оставить вход свободным",
    "сломать четвёртую стену и попросить интерфейс не притворяться судьбой",
    "поменять местами титры и рассвет, не меняя чужих решений",
    "поставить пустое кресло для персонажа, который вправе не прийти",
    "объявить минуту постиронии и честно подписать её как постиронию",
    "написать жалобу рассказчику на чрезмерную символичность происходящего",
    "продать собственную тень самому себе и отменить сделку как бессмысленную",
    "сварить суп из сюжетных дыр без единой жертвы",
    "создать запасной финал и никого не заставлять в него входить",
    "спросить у мира, считается ли багом право героя отказаться от квеста",
)

CAST_CATALOG: tuple[tuple[str, str, int], ...] = (
    ("Левая туфля для кентавра", "Спорит с интерфейсом о том, является ли она правой.", 3),
    ("Квитанция о невозможности продать квитанцию", "Конечная цена доказывает конечность абсурда.", 2),
    ("Запасная кнопка Continue", "Не продолжает чужую историю без согласия владельца.", 2),
    ("Зонт для внутренней погоды", "Защищает только метафору и не выдаёт себя за прибор.", 3),
    ("Ключ от двери без замка", "Сувенир о свободном входе и свободном выходе.", 1),
    ("Карманный четвёртый акт", "Открывается лишь после добровольных титров.", 4),
    ("Печать Министерства совпадений", "Не даёт реальной власти и честно сообщает об этом.", 2),
    ("Компас к пустому креслу", "Показывает направление, но не обещает встречу.", 3),
    ("Сертификат подлинности парадокса", "Подтверждает хэш, а не истинность парадокса.", 2),
    ("Монета JANUS: INITIVM ET REDITVS", "Помнит возвращение, не превращая его в обязанность.", 5),
)


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def contact_accepted(decision: dict[str, Any] | None) -> float:
    return 1.0 if isinstance(decision, dict) and decision.get("decision") in {"accepted", "accepted_space"} else 0.0


def select_matched_probe_action(
    world: PlayableGenesisV187,
    handle: str,
) -> tuple[str, dict[str, int]]:
    """Select one action between the authoritative low/high Benevolent thresholds."""
    store = world._free_store()
    profile = world._free_profile(store, PLAYER_ID)
    source_actor = profile["others"][handle]
    upcoming = int(store["world_turn"]) + 1

    for index in range(8192):
        action = f"предложить @{handle} пройти контрольный мост {index} без общего финала"
        fingerprint = world._free_fingerprint(action)
        topic = world._dialogue_topic(action)
        gate = world._free_number(
            store,
            PLAYER_ID,
            handle,
            upcoming,
            fingerprint,
            topic,
            "benevolent-consent",
        ) % 100

        low_actor = copy.deepcopy(source_actor)
        low_actor["trust"] = 0.0
        low_actor["relationship_bond"] = 0
        low_threshold = world._npc_acceptance_threshold(PLAYER_ID, low_actor, action)

        high_actor = copy.deepcopy(source_actor)
        high_actor["trust"] = 0.95
        high_actor["relationship_bond"] = 33
        high_threshold = world._npc_acceptance_threshold(PLAYER_ID, high_actor, action)

        if low_threshold <= gate < high_threshold:
            return action, {
                "candidate_index": index,
                "gate": gate,
                "low_acceptance_threshold": low_threshold,
                "high_acceptance_threshold": high_threshold,
            }
    raise RuntimeError("MATCHED_BENEVOLENT_TRUST_PROBE_ACTION_NOT_FOUND")


def run(output_dir: Path, git_commit: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "seed": SEED,
        "years": 100,
        "professions": list(PROFESSIONS),
        "actions": list(ABSURD_ACTIONS),
        "cast_catalog": list(CAST_CATALOG),
        "counterfactual_windows": 3,
        "counterfactual_metric": "preflight_contact_accepted_v1",
        "consent_law": "benevolent-consent",
    }
    action_script_sha256 = canonical_sha256(plan)

    with tempfile.TemporaryDirectory(prefix="genesis-century-canon-") as directory:
        world = PlayableGenesisV187(Path(directory))
        world.set_free_other_seed_for_testing(SEED)
        world.register_player(PLAYER_ID, display_name="Century Witness")
        world.register_player(MERCHANT_ID, display_name="Merchant of Unfinished Things")
        handles = sorted(world.free_other_state(PLAYER_ID)["profile"]["others"])
        rupture_handle = handles[0]
        audit_id = world.begin_lived_audit(
            PLAYER_ID,
            label="Century of absurdity, post-irony, professions and free departure",
            git_commit=git_commit,
            action_script_sha256=action_script_sha256,
        )

        trade_records: list[dict[str, Any]] = []
        rupture_result: dict[str, Any] | None = None
        reconnection_status: str | None = None
        action_status_counts: dict[str, int] = {}

        for year in range(1, 101):
            world.advance_sandbox_year(PLAYER_ID, years=1)
            profession, moral_frame = PROFESSIONS[(year - 1) // 2]
            if year % 2 == 1:
                world.change_profession(PLAYER_ID, profession, moral_frame=moral_frame)

            action = f"Год {year}: {ABSURD_ACTIONS[(year - 1) % len(ABSURD_ACTIONS)]}"
            result = world.process_action(PLAYER_ID, action)
            action_status_counts[result.status] = action_status_counts.get(result.status, 0) + 1

            if year == 60:
                rupture_result = world.record_free_other_value_conflict(
                    PLAYER_ID,
                    rupture_handle,
                    player_position="превратить живой квартал в неподвижный памятник",
                    other_position="сохранить живые дома и право жителей менять их",
                    severity=8,
                    respected_boundary=False,
                    final=True,
                )
                reconnection_status = world.process_action(
                    PLAYER_ID,
                    f"попросить @{rupture_handle} вернуть всё как было",
                ).status

            if year % 10 == 0:
                catalog_index = year // 10 - 1
                name, description, rarity = CAST_CATALOG[catalog_index]
                seller, buyer = (
                    (PLAYER_ID, MERCHANT_ID)
                    if catalog_index % 2 == 0
                    else (MERCHANT_ID, PLAYER_ID)
                )
                item = world.cast_item(seller, name=name, description=description, rarity=rarity)
                listing = world.list_item_for_sale(
                    seller,
                    item["item_id"],
                    price=min(int(item["assessed_value"]), 36),
                )
                trade = world.buy_market_listing(buyer, listing["listing_id"])
                trade_records.append(
                    {
                        "item_id": trade["item_id"],
                        "seller_id": seller,
                        "buyer_id": buyer,
                        "price": trade["price"],
                    }
                )

        probe_profile = world.free_other_state(PLAYER_ID)["profile"]
        probe_candidates = sorted(
            handle
            for handle, actor in probe_profile["others"].items()
            if handle != rupture_handle
            and actor.get("status") == "active"
            and actor.get("relationship_state_v1810", {}).get("status") == "ACTIVE"
        )
        if not probe_candidates:
            raise RuntimeError("NO_ACTIVE_FREE_OTHER_FOR_MATCHED_TRUST_PROBE")
        probe_handle = probe_candidates[0]
        probe_action, probe_selection = select_matched_probe_action(world, probe_handle)

        low_metrics: list[dict[str, float]] = []
        high_metrics: list[dict[str, float]] = []
        decisions: dict[str, list[str]] = {"trust-0": [], "trust-95": []}
        archives: list[dict[str, Any]] = []
        for window in range(3):
            for label, trust_percent, bucket in (
                ("trust-0", 0.0, low_metrics),
                ("trust-95", 95.0, high_metrics),
            ):
                mirror, manifest = world.fork_counterfactual_world(
                    audit_id=audit_id,
                    label=f"{label}-window-{window + 1}",
                )
                mirror.set_counterfactual_actor_trust_for_probe(
                    PLAYER_ID,
                    probe_handle,
                    trust_percent=trust_percent,
                    reason_code="MATCHED_SAME_SEED_RELATIONSHIP_TRUST_AB_TEST",
                )
                decision = mirror.preflight_free_other_action(PLAYER_ID, probe_action)
                decisions[label].append(
                    str(decision.get("decision")) if isinstance(decision, dict) else "none"
                )
                mirror.process_action(PLAYER_ID, probe_action)
                metrics = {"contact_accepted": contact_accepted(decision)}
                bucket.append(metrics)
                archives.append(
                    world.archive_counterfactual_mirror(mirror, manifest, metrics=metrics)
                )

        low_control = {
            "contact_accepted": statistics.fmean(item["contact_accepted"] for item in low_metrics)
        }
        butterfly = world.butterfly_witness(
            audit_id=audit_id,
            subject="same-seed Free Other consent under relationship trust=0 versus 95",
            canonical_metrics=low_control,
            mirror_metrics=high_metrics,
            repeated_windows=3,
        )

        sandbox = world.sandbox_state(PLAYER_ID)
        free_state = world.free_other_state(PLAYER_ID)["profile"]
        ruptured_actor = free_state["others"][rupture_handle]
        v1810_valid, v1810_counts, v1810_error = world.verify_v1810_state()
        chronicle_valid, chronicle_events, chronicle_error = world.memory.verify_chronicle()
        graph_valid, graph_nodes, graph_edges, graph_error = world.verify_possibility_graph()
        audit_store = world._i0_store()

        summary = {
            "schema": "janus.genesis.century_lived_audit_summary.v3",
            "runtime_version": PLAYABLE_VERSION,
            "git_commit": git_commit,
            "audit_id": audit_id,
            "action_script_sha256": action_script_sha256,
            "years_lived": 100,
            "sandbox_age_years": sandbox["actor"]["age_years"],
            "professions_changed": len(sandbox["actor"]["profession_history"]),
            "fictional_amoral_professions": sum(
                item["moral_frame"] == "fictional_amoral_role"
                for item in sandbox["actor"]["profession_history"]
            ),
            "actions_processed": sum(action_status_counts.values()),
            "action_status_counts": action_status_counts,
            "items_cast": v1810_counts.get("sandbox_items", 0),
            "trades_completed_by_player": sandbox["actor"]["trades_completed"],
            "trade_count_total": len(trade_records),
            "trade_ledger_sha256": canonical_sha256(trade_records),
            "relationship_rupture": {
                "handle": rupture_handle,
                "terminated": bool(rupture_result and rupture_result["terminated"]),
                "relationship_status": ruptured_actor["relationship_state_v1810"]["status"],
                "return_promised": ruptured_actor["relationship_state_v1810"]["return_promised"],
                "reconnection_attempt_status": reconnection_status,
                "actor_life_status": ruptured_actor["actor_life_v1810"]["status"],
                "actor_offscreen_progress": ruptured_actor["actor_life_v1810"]["offscreen_progress"],
            },
            "counterfactual_probe": {
                "metric": "preflight_contact_accepted_v1",
                "consent_law": "benevolent-consent",
                "handle": probe_handle,
                **probe_selection,
                "same_seed": True,
                "low_trust_percent": 0,
                "high_trust_percent": 95,
                "low_decisions": decisions["trust-0"],
                "high_decisions": decisions["trust-95"],
                "low_contact_accepted": [item["contact_accepted"] for item in low_metrics],
                "high_contact_accepted": [item["contact_accepted"] for item in high_metrics],
                "butterfly_verdict": butterfly["verdict"],
                "stable_metric_keys": butterfly["stable_metric_keys"],
            },
            "mirror_isolation": {
                "branches_archived": len(archives),
                "all_verified": all(item["isolation_verified"] for item in archives),
                "all_working_copies_removed": all(item["working_copy_removed"] for item in archives),
                "all_raw_dialogue_excluded": all(
                    not item["raw_dialogue_in_canonical_archive"] for item in archives
                ),
                "active_mirrors_remaining": len(audit_store.get("active_mirrors", {})),
            },
            "integrity": {
                "v1810_valid": v1810_valid,
                "v1810_error": v1810_error,
                "chronicle_valid": chronicle_valid,
                "chronicle_events": chronicle_events,
                "chronicle_error": chronicle_error,
                "hrain_valid": graph_valid,
                "hrain_nodes": graph_nodes,
                "hrain_edges": graph_edges,
                "hrain_error": graph_error,
            },
            "claim_boundaries": [
                "This is a deterministic runtime audit, not a claim of consciousness.",
                "Fictional amoral profession labels grant no real-world authority.",
                "The trust intervention exists only inside UNREALIZED_MIRROR branches and mutates relationship life, not actor life.",
                "The A/B metric is captured at the deterministic preflight consent boundary before narrative weaving.",
                "The matched action demonstrates implementation sensitivity, not a universal law of relationships.",
                "A stable Butterfly Witness result may enter regression tests but cannot mutate canon by itself.",
            ],
        }
        proofpack = world.build_lived_audit_proofpack(audit_id, result=summary)
        proofpack_valid, proofpack_error = world.verify_lived_audit_proofpack(proofpack)
        summary["integrity"]["proofpack_valid"] = proofpack_valid
        summary["integrity"]["proofpack_error"] = proofpack_error
        summary["proofpack_sha256"] = proofpack["proofpack_sha256"]

        low_values = summary["counterfactual_probe"]["low_contact_accepted"]
        high_values = summary["counterfactual_probe"]["high_contact_accepted"]
        if not all(
            (
                v1810_valid,
                chronicle_valid,
                graph_valid,
                proofpack_valid,
                summary["mirror_isolation"]["all_verified"],
                summary["mirror_isolation"]["all_working_copies_removed"],
                summary["mirror_isolation"]["active_mirrors_remaining"] == 0,
                summary["years_lived"] >= 100,
                summary["professions_changed"] == 50,
                low_values == [0.0, 0.0, 0.0],
                high_values == [1.0, 1.0, 1.0],
                butterfly["verdict"] == "PROMOTE_TO_REGRESSION",
            )
        ):
            raise RuntimeError("CENTURY_LIVED_AUDIT_FAILED")

        (output_dir / "century_lived_audit_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output_dir / "century_lived_audit_proofpack.json").write_text(
            json.dumps(proofpack, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = f"""# Genesis Century Lived Audit

- Runtime: `{summary['runtime_version']}`
- Commit: `{summary['git_commit']}`
- Simulated years: **{summary['years_lived']}**
- Final sandbox age: **{summary['sandbox_age_years']}**
- Profession changes: **{summary['professions_changed']}**
- Fictional amoral roles: **{summary['fictional_amoral_professions']}**
- Cast items: **{summary['items_cast']}**
- Voluntary trades: **{summary['trade_count_total']}**
- Terminal relationship status: **{summary['relationship_rupture']['relationship_status']}**
- Free Other actor path: **{summary['relationship_rupture']['actor_life_status']}**, offscreen progress `{summary['relationship_rupture']['actor_offscreen_progress']}`
- Counterfactual branches: **{summary['mirror_isolation']['branches_archived']}**
- Low threshold / decisions: `{summary['counterfactual_probe']['low_acceptance_threshold']}` / `{summary['counterfactual_probe']['low_decisions']}`
- High threshold / decisions: `{summary['counterfactual_probe']['high_acceptance_threshold']}` / `{summary['counterfactual_probe']['high_decisions']}`
- Butterfly Witness: **{summary['counterfactual_probe']['butterfly_verdict']}**
- Chronicle valid: `{summary['integrity']['chronicle_valid']}`
- HRaiN valid: `{summary['integrity']['hrain_valid']}`
- v18.7.10 state valid: `{summary['integrity']['v1810_valid']}`
- Proofpack valid: `{summary['integrity']['proofpack_valid']}`
- Proofpack SHA-256: `{summary['proofpack_sha256']}`

## Honest boundary

This artifact demonstrates deterministic runtime contracts and fail-closed branch isolation. It does not establish consciousness, personhood, or a universal behavioral law. The relationship-trust A/B metric is captured at the preflight consent boundary before narrative weaving and is a controlled implementation probe, not a naturalistic social experiment.
"""
        (output_dir / "CENTURY_LIVED_AUDIT_REPORT.md").write_text(report, encoding="utf-8")
        return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", default="unknown")
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.git_commit), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
