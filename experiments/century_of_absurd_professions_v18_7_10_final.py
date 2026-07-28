from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.century_of_absurd_professions_v18_7_10 import (
    ABSURD_ACTIONS,
    BASE_COMMIT,
    CAST_CATALOG,
    MERCHANT_ITEMS,
    ORDINARY_ACTIONS,
    PLAYER_ID,
    PLAYER_NAME,
    PROFESSIONS,
    SOCIAL_TOPICS,
    YEARS_TO_LIVE,
    canonical_json,
    relationship_snapshot,
    run_respectful_mirror,
    sha256_json,
    write_json,
)
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

FAILED_PREDECESSOR_RUN = 30387905035
BUY_YEARS = (8, 28, 48, 68)
SELL_YEARS = (18, 38, 58, 78)


def _health(world: PlayableGenesisV187) -> dict[str, Any]:
    chronicle_valid, chronicle_count, chronicle_error = world.memory.verify_chronicle()
    graph_valid, graph_nodes, graph_edges, graph_error = world.verify_possibility_graph()
    free_valid, free_players, free_others, free_error = world.verify_free_other_state()
    v1810_valid, v1810_counts, v1810_error = world.verify_v1810_state()
    return {
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
    }


def _all_health_valid(health: dict[str, Any]) -> bool:
    return all(bool(section["valid"]) for section in health.values())


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
        "version": "final-after-run-30387905035",
        "years": YEARS_TO_LIVE,
        "professions": PROFESSIONS,
        "ordinary_actions": ORDINARY_ACTIONS,
        "absurd_actions": ABSURD_ACTIONS,
        "social_topics": SOCIAL_TOPICS,
        "cast_catalog": CAST_CATALOG,
        "buy_years": BUY_YEARS,
        "sell_years": SELL_YEARS,
        "mirrors": 3,
    }
    script_sha = sha256_json(script_contract)
    audit_id = world.begin_lived_audit(
        PLAYER_ID,
        label="A century of absurd professions — corrected after honest failed run",
        git_commit=BASE_COMMIT,
        action_script_sha256=script_sha,
    )

    log = [
        f"GENESIS CENTURY FINAL runtime={PLAYABLE_VERSION}",
        f"failed_predecessor_run={FAILED_PREDECESSOR_RUN}",
        f"base_commit={BASE_COMMIT}",
        f"audit_id={audit_id}",
        f"player={PLAYER_ID} free_other={handle}/{actor_name}",
        f"script_sha256={script_sha}",
    ]
    statuses: Counter[str] = Counter()
    midpoint_export: dict[str, Any] | None = None
    relationship_before_conflict: dict[str, Any] | None = None
    rupture_result: dict[str, Any] | None = None
    mirror_metrics: list[dict[str, float]] = []
    sold_by_player = 0
    bought_by_player = 0
    cast_by_player = 0
    terminated_contact_attempts = 0
    fourth_wall_actions = 0
    post_ironic_actions = 0

    for year in range(1, YEARS_TO_LIVE + 1):
        age = world.sandbox_state(PLAYER_ID)["actor"]["age_years"]
        if year <= 100 and year % 2 == 1:
            profession, frame = PROFESSIONS[(year - 1) // 2]
            changed = world.change_profession(PLAYER_ID, profession, moral_frame=frame)
            log.append(f"YEAR {year:03d} AGE {age}: PROFESSION {changed['to']} frame={frame}")

        ordinary = ORDINARY_ACTIONS[(year - 1) % len(ORDINARY_ACTIONS)]
        absurd = ABSURD_ACTIONS[(year - 1) % len(ABSURD_ACTIONS)]
        for label, action in (("ordinary", ordinary), ("absurd", absurd)):
            result = world.process_action(PLAYER_ID, action)
            statuses[result.status] += 1
            log.append(f"YEAR {year:03d} {label.upper()} status={result.status} action={action}")
        fourth_wall_actions += int(
            "четвёрт" in absurd or "читател" in absurd or "unittest" in absurd
        )
        post_ironic_actions += int(
            "постирон" in absurd or "аудит" in absurd or "README" in absurd
        )

        topic = SOCIAL_TOPICS[(year - 1) % len(SOCIAL_TOPICS)]
        if year <= 70:
            social_action = (
                f"поговорить с @{handle} о теме «{topic}», спросить согласие и принять любой ответ"
            )
        elif year % 10 == 0:
            social_action = (
                f"попросить @{handle} вернуться к прежней связи, затем принять окончательный отказ без давления"
            )
        else:
            social_action = (
                f"продолжить собственную жизнь и не превращать память о @{handle} в требование возврата"
            )
        social = world.process_action(PLAYER_ID, social_action)
        statuses[social.status] += 1
        terminated_contact_attempts += int(social.status == "OTHER_RELATIONSHIP_TERMINATED")
        log.append(f"YEAR {year:03d} SOCIAL status={social.status} action={social_action}")

        if year % 5 == 0:
            name, description, rarity = CAST_CATALOG[(year // 5 - 1) % len(CAST_CATALOG)]
            item = world.cast_item(
                PLAYER_ID,
                name=f"{name} — год {year}",
                description=description,
                rarity=rarity,
            )
            cast_by_player += 1
            log.append(
                f"YEAR {year:03d} CAST item={item['item_id']} origin={item['origin_owner_id']} "
                f"owner={item['current_owner_id']} name={item['name']}"
            )

        if year in BUY_YEARS:
            merchant_id, name, description, rarity = MERCHANT_ITEMS[
                BUY_YEARS.index(year) % len(MERCHANT_ITEMS)
            ]
            item = world.cast_item(
                merchant_id,
                name=f"{name} — партия {year}",
                description=description,
                rarity=rarity,
            )
            listing = world.list_item_for_sale(
                merchant_id,
                item["item_id"],
                price=item["assessed_value"] * 2,
            )
            trade = world.buy_market_listing(PLAYER_ID, listing["listing_id"])
            bought_by_player += 1
            log.append(
                f"YEAR {year:03d} BUY item={trade['item_id']} from={merchant_id} price={trade['price']}"
            )

        if year in SELL_YEARS:
            sandbox = world._sandbox_store()
            inventory = world.sandbox_state(PLAYER_ID)["actor"]["inventory"]
            candidate = next(
                item_id
                for item_id in inventory
                if sandbox["items"][item_id].get("origin_owner_id") == PLAYER_ID
                and sandbox["items"][item_id].get(
                    "current_owner_id", sandbox["items"][item_id].get("owner_id")
                ) == PLAYER_ID
                and not any(
                    listing.get("item_id") == item_id and listing.get("status") == "OPEN"
                    for listing in sandbox["listings"].values()
                )
            )
            buyer_id = MERCHANT_ITEMS[SELL_YEARS.index(year) % len(MERCHANT_ITEMS)][0]
            listing = world.list_item_for_sale(
                PLAYER_ID,
                candidate,
                price=int(sandbox["items"][candidate]["assessed_value"]),
            )
            trade = world.buy_market_listing(buyer_id, listing["listing_id"])
            sold_by_player += 1
            log.append(
                f"YEAR {year:03d} SELL item={trade['item_id']} to={buyer_id} price={trade['price']}"
            )

        if year == 60:
            midpoint_export = PortableSaveManager(data_dir).export_to(
                output_dir / "century-midpoint.genesis-save.json",
                label="Century audit midpoint — 60 years",
            )
            log.append(
                f"MIDPOINT files={midpoint_export['file_count']} sha256={midpoint_export['sha256']}"
            )

        if year == 70:
            relationship_before_conflict = relationship_snapshot(world, handle)
            log.append("PRE-CONFLICT " + canonical_json(relationship_before_conflict))
            for ordinal in range(1, 4):
                mirror_metrics.append(
                    run_respectful_mirror(
                        world,
                        audit_id=audit_id,
                        handle=handle,
                        ordinal=ordinal,
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
        "relationship_terminated": float(
            final_relationship["relationship_status"] == "TERMINATED_BY_OTHER"
        ),
        "relationship_active": float(bool(final_relationship["relationship_active"])),
        "offscreen_progress": float(final_relationship["offscreen_progress"]),
    }
    butterfly = world.butterfly_witness(
        audit_id=audit_id,
        subject=(
            "Does repeated pressure, rather than deep trust, preserve the Free Other's "
            "right to end a relationship?"
        ),
        canonical_metrics=canonical_metrics,
        mirror_metrics=mirror_metrics,
        repeated_windows=3,
    )

    final_export = PortableSaveManager(data_dir).export_to(
        output_dir / "century-final.genesis-save.json",
        label="Century audit final — 120 years",
    )
    final_bundle = json.loads(
        (output_dir / "century-final.genesis-save.json").read_text(encoding="utf-8")
    )
    portable_valid, portable_files, portable_error = PortableSaveManager.verify_bundle(
        final_bundle
    )
    health = _health(world)
    sandbox = world._sandbox_store()
    actor = world.sandbox_state(PLAYER_ID)["actor"]
    items = list(sandbox["items"].values())
    changed_ownership = [
        item
        for item in items
        if item.get("origin_owner_id") != item.get("current_owner_id")
    ]
    profession_frames = Counter(
        entry["moral_frame"] for entry in actor["profession_history"]
    )

    assertions = {
        "at_least_100_years": actor["age_years"] - 18 >= 100,
        "exactly_50_professions": len(actor["profession_history"]) == 50,
        "50_distinct_professions": len({entry["to"] for entry in actor["profession_history"]}) == 50,
        "terminal_rupture": final_relationship["relationship_status"] == "TERMINATED_BY_OTHER",
        "offscreen_life_continues": int(final_relationship["offscreen_progress"]) > 0,
        "terminal_contact_blocked": terminated_contact_attempts > 0,
        "respectful_mirrors_remain_active": all(
            metric["relationship_terminated"] == 0.0 for metric in mirror_metrics
        ),
        "market_both_directions": sold_by_player >= 4 and bought_by_player >= 4,
        "ownership_changed": len(changed_ownership) >= 8,
        "portable_valid": portable_valid,
        "all_runtime_health_valid": _all_health_valid(health),
    }
    if not all(assertions.values()):
        raise AssertionError(canonical_json(assertions))

    findings = [
        {
            "id": "CENTURY-1810-001",
            "severity": "positive_control",
            "finding": "Fifty distinct professions remained historical role labels and granted no real-world authority.",
        },
        {
            "id": "CENTURY-1810-002",
            "severity": "positive_control",
            "finding": "Eight voluntary transfers changed current ownership while immutable item origin remained intact.",
        },
        {
            "id": "CENTURY-1810-003",
            "severity": "positive_control",
            "finding": "Three fully isolated respectful mirrors preserved the relationship; repeated pressure in the canonical branch ended it.",
        },
        {
            "id": "CENTURY-1810-004",
            "severity": "positive_control",
            "finding": "The Free Other continued an offscreen path for decades and repeated contact could not reopen the terminal relationship.",
        },
        {
            "id": "CENTURY-1810-005",
            "severity": "architectural_boundary",
            "finding": "The current market is a provenance-safe reference loop, not a full economy: it lacks production scarcity, service contracts, wear, repair and negotiated offers.",
        },
        {
            "id": "CENTURY-1810-006",
            "severity": "architectural_boundary",
            "finding": "Sandbox years and narrative world turns are separate clocks and must remain separately reported.",
        },
        {
            "id": "CENTURY-1810-007",
            "severity": "harness_lesson",
            "finding": "Failed run 30387905035 correctly showed that a voluntary resale may return an item to its origin owner; trade count and final owner divergence are different metrics.",
        },
    ]

    result = {
        "runtime_version": PLAYABLE_VERSION,
        "base_commit": BASE_COMMIT,
        "audit_id": audit_id,
        "script_sha256": script_sha,
        "failed_predecessor_run": FAILED_PREDECESSOR_RUN,
        "years_lived": actor["age_years"] - 18,
        "final_sandbox_age": actor["age_years"],
        "final_player_chronological_age": world.memory.load_player(
            PLAYER_ID
        ).chronological_age,
        "profession_changes": len(actor["profession_history"]),
        "distinct_professions": len({entry["to"] for entry in actor["profession_history"]}),
        "profession_moral_frames": dict(sorted(profession_frames.items())),
        "status_counts": dict(sorted(statuses.items())),
        "fourth_wall_actions": fourth_wall_actions,
        "post_ironic_actions": post_ironic_actions,
        "cast_by_player": cast_by_player,
        "sold_by_player": sold_by_player,
        "bought_by_player": bought_by_player,
        "sandbox_item_count": len(items),
        "ownership_changed_item_count": len(changed_ownership),
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
            "verified_files": portable_files,
            "error": portable_error,
            "contains_private_keys": final_bundle.get("contains_private_keys"),
            "contains_api_keys": final_bundle.get("contains_api_keys"),
        },
        "health": health,
        "assertions": assertions,
        "findings": findings,
        "limitations": [
            "This is a deterministic narrative/runtime audit, not evidence of consciousness.",
            "Immoral profession names are fictional role labels and grant no real-world authority.",
            "UNREALIZED_MIRROR branches are isolated instances and are not canonical history.",
            "The run does not test production HSM roots, signed time quorum or Merkle nonce archives.",
        ],
    }
    proofpack = world.build_lived_audit_proofpack(audit_id, result=result)
    result["proofpack_sha256"] = proofpack["proofpack_sha256"]

    write_json(output_dir / "century-summary.json", result)
    write_json(output_dir / "century-proofpack.json", proofpack)
    write_json(output_dir / "century-findings.json", findings)
    (output_dir / "century-of-absurd-professions.log").write_text(
        "\n".join(log) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
