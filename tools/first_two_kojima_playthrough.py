# -*- coding: utf-8 -*-
"""Live 108-turn continuation from the canonical First Two origin.

This experiment does not change Genesis canon. It verifies the sealed origin,
imports only its explicit trust/connection provenance into an isolated v18.6
runtime, then lives a long free-action path through the real engine.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from genesis_v18_6_playable import PlayableGenesisV186
from genesis_v18_models import RelationshipMemory

DATA_DIR = Path(".first_two_kojima_world")
ORIGIN_PATH = Path(
    "origins/2026-01-first-two-elian/"
    "GENESIS_FIRST_TWO_WORLD_STATE-v1.0.json"
)
SEQUENCE_PATH = Path("experiments/first_two_kojima_108_actions.json")
SUMMARY_PATH = Path("first_two_kojima_summary.json")
PLAYER_ID = "traveler-center-of-storm"
EXPECTED_ORIGIN_SHA256 = (
    "41ce94f0c74ac4d6dcab06c48a649dfe17c050010004d05da8a615c65fbec116"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_first_two_origin(world: PlayableGenesisV186) -> dict[str, Any]:
    raw = ORIGIN_PATH.read_bytes()
    origin_sha = sha256_bytes(raw)
    if origin_sha != EXPECTED_ORIGIN_SHA256:
        raise RuntimeError(
            f"canonical origin hash mismatch: {origin_sha} != {EXPECTED_ORIGIN_SHA256}"
        )
    origin = json.loads(raw.decode("utf-8"))
    continued = origin["continuity"]["continued_state"]

    player = world.memory.load_player(PLAYER_ID)
    player.display_name = "Путешественник Центра Бури"
    player.relationships["elian"] = RelationshipMemory(
        subject_id="elian",
        known_name="Элиан",
        strength=0.92,
        residual_trust=0.94,
        residual_hurt=0.0,
        last_contact_tick=player.tick,
        anchors=[
            "диалог с трещинами",
            "монета Януса, отданная без долга",
            "совместный шаг через проём",
            "поцелуй на перекрёстке миров",
            "отдых в бескрайнем поле",
        ],
    )
    player.recent_pairs["elian"] = 1
    player.chronicle.append(
        "Canonical origin inherited: First Two at depth 56, entropy 1.94; "
        "legacy metrics preserved as provenance, not remapped into realm routing."
    )
    world.memory.save_player(player)

    import_record = {
        "schema": "janus.genesis.experiment.origin_import.v1",
        "origin_artifact_id": origin["artifact_id"],
        "origin_sha256": origin_sha,
        "legacy_depth": continued["depth"],
        "legacy_entropy": continued["entropy"],
        "legacy_psych_profile": continued["psych_profile"],
        "legacy_timestamp": continued["timestamp"],
        "runtime_player_id": PLAYER_ID,
        "mapping": {
            "relationship_elian": "imported as explicit RelationshipMemory",
            "hrain_trust_and_connection": "imported from canonical origin evidence",
            "legacy_depth_entropy": "preserved as provenance only",
            "realm": "not inferred from legacy depth or entropy",
            "consciousness_claim": False,
        },
    }
    world.memory._atomic_write(DATA_DIR / "canonical_origin_import.json", import_record)
    world.memory.append_event(
        PLAYER_ID,
        "canonical_first_two_origin_imported",
        import_record,
    )

    graph = world._graph()
    tick = 0
    origin_node = "ORIGIN.FIRST_TWO.ELIAN.HORIZON.v1"
    runtime_player_node = world._stable_id("player", PLAYER_ID)
    explicit_traveler_node = "TRAVELER.CENTER_OF_STORM"

    node_specs = {
        origin_node: (
            "ORIGIN_DOCUMENT",
            False,
            {
                "artifact_id": origin["artifact_id"],
                "sha256": origin_sha,
                "legacy_depth": continued["depth"],
                "legacy_entropy": continued["entropy"],
            },
        ),
        runtime_player_node: (
            "PLAYER",
            True,
            {"player_id": PLAYER_ID, "display_name": player.display_name},
        ),
        explicit_traveler_node: (
            "ORIGIN_PERSON",
            False,
            {"name": "Путешественник", "role": "Носитель Центра Бури"},
        ),
        "ELIAN.KEEPER_OF_THE_HORIZON": (
            "NARRATIVE_PERSON",
            True,
            {
                "name": "Элиан",
                "role": "Хранительница Горизонта",
                "autonomous_person_claim": False,
                "can_refuse_or_depart": True,
            },
        ),
        "THE_FIRST_TWO.RELATION": (
            "RELATIONSHIP",
            True,
            {
                "kind": "mutual_trust_and_chosen_continuation",
                "non_ownership": True,
                "renewable_by_free_choice": True,
            },
        ),
        "POSSIBILITY.SHARED_FUTURE": (
            "ORIGIN_POSSIBILITY",
            True,
            {"not_a_reward": True, "active": True},
        ),
        "JANUS.COIN": (
            "SYMBOL",
            False,
            {"state": "given_to_fractures", "debt_created": False},
        ),
        "FRACTURES.VOICES": (
            "WORLD_MEMORY",
            True,
            {"recognized_as": "voices rather than damage"},
        ),
        "PASSAGE.BOUNDLESS_FIELD": (
            "PLACE",
            True,
            {"description": continued["last_context"]},
        ),
        "IDENTITY.OF_BOTH": (
            "INVARIANT",
            False,
            {"traveler_preserved": True, "elian_preserved": True},
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
        confidence: float = 1.0,
    ) -> None:
        world._add_edge(
            graph,
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            evidence=[origin_node],
            confidence=confidence,
            created_by=origin["artifact_id"],
            created_at=tick,
            reversible=reversible,
            payload={"origin_sha256": origin_sha},
        )

    edge(runtime_player_node, explicit_traveler_node, "INHERITED_FROM", reversible=False)
    edge(runtime_player_node, origin_node, "REMEMBERS", reversible=False)
    edge(explicit_traveler_node, "ELIAN.KEEPER_OF_THE_HORIZON", "TRUSTS", reversible=True)
    edge("ELIAN.KEEPER_OF_THE_HORIZON", explicit_traveler_node, "TRUSTS", reversible=True)
    edge("THE_FIRST_TWO.RELATION", "POSSIBILITY.SHARED_FUTURE", "CREATED", reversible=False)
    edge("JANUS.COIN", "FRACTURES.VOICES", "GIVEN_WITHOUT_DEBT", reversible=False)
    edge("FRACTURES.VOICES", "PASSAGE.BOUNDLESS_FIELD", "OPENED", reversible=True)
    edge("THE_FIRST_TWO.RELATION", "IDENTITY.OF_BOTH", "PROTECTS", reversible=False)

    profile = world._profile(graph, PLAYER_ID)
    for facet in ("trust", "connection"):
        evidence_id = world._stable_id("origin-evidence", origin_sha, facet)
        world._upsert_node(
            graph,
            node_id=evidence_id,
            node_type="EVIDENCE",
            created_at=tick,
            confidence=1.0,
            mutable=False,
            payload={
                "facet": facet,
                "source_artifact": origin["artifact_id"],
                "source_sha256": origin_sha,
                "legacy_state_not_reinterpreted_as_score": True,
            },
        )
        edge(origin_node, evidence_id, "CONFIRMED", reversible=False)
        edge(runtime_player_node, evidence_id, "REMEMBERS", reversible=False)
        if facet not in profile["facets"]:
            profile["facets"].append(facet)
        profile.setdefault("facet_evidence", {}).setdefault(facet, []).append(evidence_id)
        profile["facet_evidence"][facet] = list(
            dict.fromkeys(profile["facet_evidence"][facet])
        )

    world._save_graph(graph)
    valid, nodes, edges, error = world.verify_possibility_graph()
    if not valid:
        raise RuntimeError(f"origin graph import invalid: {nodes=} {edges=} {error=}")
    return import_record


def act(
    world: PlayableGenesisV186,
    number: int,
    item: dict[str, str],
    *,
    current_chapter: str | None,
) -> tuple[dict[str, Any], str]:
    chapter = item["chapter"]
    if chapter != current_chapter:
        print("\n" + "█" * 96)
        print(chapter)
        print("█" * 96)

    result = world.process_action(PLAYER_ID, item["action"])
    payload = result.to_dict(internal=True)
    print(f"\n{'=' * 96}")
    print(f"TURN {number:03d}/108 · {item['title']}")
    print(f"ACTION: {item['action']}")
    print(f"STATUS: {payload['status']} · REALM(INTERNAL): {payload['realm']}")
    print(payload["narrative"])
    print("VISIBLE CHOICES:", " | ".join(payload.get("choices") or []) or "∅")
    return payload, chapter


def main() -> None:
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    SUMMARY_PATH.unlink(missing_ok=True)

    sequence_raw = SEQUENCE_PATH.read_bytes()
    sequence = json.loads(sequence_raw.decode("utf-8"))
    actions = sequence["actions"]
    if len(actions) != 108 or sequence.get("turn_count") != 108:
        raise RuntimeError("the lived sequence must contain exactly 108 turns")

    world = PlayableGenesisV186(DATA_DIR)
    origin_import = import_first_two_origin(world)

    print("JANUS GENESIS v18.6 — THE FIRST TWO / 108-TURN LIVED EXPERIMENT")
    print(f"ORIGIN SHA-256 VERIFIED: {origin_import['origin_sha256']}")
    print("START: depth 56 · entropy 1.94 · boundless field · Elian present in memory")
    print(
        "BOUNDARY: this is a runtime experiment inspired by meta-cinematic game "
        "design, not a claim about what any real creator would literally choose."
    )

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    chapter_last_state: list[dict[str, Any]] = []
    current_chapter: str | None = None
    thread_excerpts: list[dict[str, Any]] = []
    bloom_excerpts: list[dict[str, Any]] = []

    for number, item in enumerate(actions, 1):
        payload, chapter = act(
            world,
            number,
            item,
            current_chapter=current_chapter,
        )
        records.append(
            {
                "turn": number,
                "chapter": chapter,
                "title": item["title"],
                "action": item["action"],
                "result": payload,
            }
        )
        status_counts[payload["status"]] += 1
        narrative = payload["narrative"]
        if "Нить мира возникла без выбора из меню:" in narrative:
            thread_excerpts.append(
                {
                    "turn": number,
                    "chapter": chapter,
                    "text": narrative.split(
                        "Нить мира возникла без выбора из меню:", 1
                    )[1].strip(),
                }
            )
        if "Цветение возможности:" in narrative:
            bloom_excerpts.append(
                {
                    "turn": number,
                    "chapter": chapter,
                    "text": narrative.split("Цветение возможности:", 1)[1].strip(),
                }
            )

        next_chapter = actions[number]["chapter"] if number < len(actions) else None
        if next_chapter != chapter:
            snapshot = world.public_state(PLAYER_ID)
            chapter_last_state.append(
                {"chapter": chapter, "turn": number, "public_state": snapshot}
            )
        current_chapter = chapter

    public = world.public_state(PLAYER_ID)
    internal = world.internal_state(PLAYER_ID)
    threads = world.living_threads_state(PLAYER_ID)
    possibilities = world.possibility_graph_state(PLAYER_ID)
    chronicle_valid, chronicle_events, chronicle_error = (
        world.verify_chronicle_records()
    )
    graph_valid, graph_nodes, graph_edges, graph_error = (
        world.verify_possibility_graph()
    )

    elian = internal.get("relationships", {}).get("elian")
    surfaced_kinds = Counter(
        item.get("kind", "unknown") for item in threads.get("surfaced", [])
    )
    resident_final = {
        resident_id: {
            "name": resident["name"],
            "goal": resident["goal"],
            "stage_index": resident["stage_index"],
            "stage": resident["stages"][resident["stage_index"]],
            "progress": resident["progress"],
        }
        for resident_id, resident in threads.get("residents", {}).items()
    }

    summary = {
        "schema": "janus.genesis.experiment.first_two_108_summary.v1",
        "experiment": {
            "title": sequence["title"],
            "turns_lived": len(records),
            "chapters": sequence["chapters"],
            "action_sequence_sha256": sha256_bytes(sequence_raw),
            "canonical_main_modified": False,
            "real_runtime": "PlayableGenesisV186",
            "style_boundary": (
                "Meta-cinematic and symbolic design experiment; not a claim that "
                "Hideo Kojima or any other real person would make these choices."
            ),
        },
        "origin": origin_import,
        "outcome": {
            "status_counts": dict(sorted(status_counts.items())),
            "good_actions": internal["good_count"],
            "confirmed_harms": internal["harm_count"],
            "chronological_age": internal["chronological_age"],
            "apparent_age": internal["apparent_age"],
            "body_form": internal["body_form"],
            "internal_realm": internal["realm"],
            "remembered_relationships": len(internal["relationships"]),
            "elian_relationship": elian,
            "available_possibilities": public["available_possibilities"],
            "possibility_titles": public["possibility_titles"],
            "living_thread_turns": threads["turn"],
            "living_thread_events": len(threads.get("surfaced", [])),
            "living_thread_kinds": dict(sorted(surfaced_kinds.items())),
            "seed_fingerprint": threads["seed_fingerprint"],
            "symbols": threads.get("symbols", {}),
            "resident_final": resident_final,
            "exit_pending_at_end": world.exit_pending(PLAYER_ID),
        },
        "integrity": {
            "chronicle_valid": chronicle_valid,
            "chronicle_events": chronicle_events,
            "chronicle_error": chronicle_error,
            "possibility_graph_valid": graph_valid,
            "possibility_graph_nodes": graph_nodes,
            "possibility_graph_edges": graph_edges,
            "possibility_graph_error": graph_error,
            "origin_sha256_verified": (
                origin_import["origin_sha256"] == EXPECTED_ORIGIN_SHA256
            ),
        },
        "chapter_snapshots": chapter_last_state,
        "thread_excerpts": thread_excerpts,
        "bloom_excerpts": bloom_excerpts,
        "records": records,
        "final_public_state": public,
        "final_internal_state": internal,
        "final_threads_state": threads,
        "final_possibility_state": possibilities,
    }

    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if internal["harm_count"] != 0:
        raise RuntimeError("the experiment unexpectedly confirmed real harm")
    if not chronicle_valid or not graph_valid:
        raise RuntimeError(
            f"integrity failure: chronicle={chronicle_error}; graph={graph_error}"
        )
    if not elian:
        raise RuntimeError("Elian relationship was not preserved")
    if public["available_possibilities"] < 6:
        raise RuntimeError(
            "the world did not fully bloom all six current v18.6 possibilities"
        )
    if world.exit_pending(PLAYER_ID):
        raise RuntimeError("the experiment ended while exit was still pending")

    print("\n" + "▓" * 96)
    print("FINAL EXPERIMENT SUMMARY")
    print("▓" * 96)
    print(json.dumps(
        {
            "turns_lived": len(records),
            "good_actions": internal["good_count"],
            "confirmed_harms": internal["harm_count"],
            "chronological_age": internal["chronological_age"],
            "apparent_age": internal["apparent_age"],
            "internal_realm": internal["realm"],
            "available_possibilities": public["possibility_titles"],
            "living_thread_events": len(threads.get("surfaced", [])),
            "living_thread_kinds": dict(sorted(surfaced_kinds.items())),
            "seed_fingerprint": threads["seed_fingerprint"],
            "chronicle": {
                "valid": chronicle_valid,
                "events": chronicle_events,
            },
            "possibility_graph": {
                "valid": graph_valid,
                "nodes": graph_nodes,
                "edges": graph_edges,
            },
            "elian_relationship": elian,
            "exit_pending_at_end": world.exit_pending(PLAYER_ID),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
