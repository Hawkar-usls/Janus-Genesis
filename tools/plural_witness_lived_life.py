# -*- coding: utf-8 -*-
"""Live one complete Genesis v18.7.4 life among all Meta Registry witnesses.

The experiment uses the canonical Plural Witness APIs rather than a custom import
layer. Every public data/*.json file is preserved in a lossless origin envelope.
The life then reads each witness, crosses a portable threshold, exercises Free
Other and Honest Intention, and probes whether retrieval and claim attribution are
as epistemically grounded as the storage layer.

Synthetic probes are explicitly labelled and never reported as source truth.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from genesis_v18_7_3 import IntentionMode
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

PLAYER_ID = "listener-among-many-witnesses"
COUNTRY_A = Path(".plural_witness_life_country_a")
COUNTRY_B = Path(".plural_witness_life_country_b")
META_CHECKOUT = Path(os.environ.get("META_REGISTRY_CHECKOUT", "/tmp/janus-meta-registry"))
META_DATA = META_CHECKOUT / "data"
META_REPOSITORY = "Hawkar-usls/janus-meta-registry"
META_COMMIT = "53773246f4caabe767642eccfd3cd7746a6b1635"
THRESHOLD_SAVE = Path("plural_witness_life_threshold.genesis-save.json")
FINAL_SAVE = Path("plural_witness_lived_life.genesis-save.json")
SUMMARY_PATH = Path("plural_witness_lived_life_summary.json")
SEAL = "JANUS LISTENS WITHOUT STEALING THE VOICE."

KNOWN_QUERIES = [
    "янус память",
    "добро зло",
    "свобода согласие",
    "ребёнок защита",
    "сон дом",
    "Бог хаос",
    "дружба путь",
    "технический граф SHA-256",
]
NO_MATCH_QUERY = "квантовый ананас серебряный термостат 9471"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def git_blob(path: Path) -> str:
    relative = path.relative_to(META_CHECKOUT).as_posix()
    return subprocess.check_output(
        ["git", "-C", str(META_CHECKOUT), "rev-parse", f"{META_COMMIT}:{relative}"],
        text=True,
    ).strip()


def envelope_for(world: PlayableGenesisV187, metadata: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (world.memory.root / metadata["envelope_path"]).read_text(encoding="utf-8")
    )


def agency_totals(world: PlayableGenesisV187) -> dict[str, int]:
    actors = list(world.free_other_state(PLAYER_ID)["profile"]["others"].values())
    return {
        "initiatives": sum(int(actor.get("initiated_contacts", 0)) for actor in actors),
        "refusals": sum(int(actor.get("refusals_count", 0)) for actor in actors),
        "departures": sum(int(actor.get("departures", 0)) for actor in actors),
        "returns": sum(int(actor.get("returns", 0)) for actor in actors),
        "calling_changes": sum(int(actor.get("calling_changes", 0)) for actor in actors),
        "dialogue_memories": sum(len(actor.get("dialogue_memory", [])) for actor in actors),
    }


def state_digest(world: PlayableGenesisV187) -> dict[str, Any]:
    public = world.public_state(PLAYER_ID)
    internal = world.internal_state(PLAYER_ID)
    free = world.free_other_state(PLAYER_ID)
    plural = world.plural_witness_state()
    intent = world.honest_intention_state(PLAYER_ID)
    return {
        "tick": internal["tick"],
        "good_count": internal["good_count"],
        "harm_count": internal["harm_count"],
        "realm": internal["realm"],
        "display_name": world.memory.load_player(PLAYER_ID).display_name,
        "available_possibilities": public["available_possibilities"],
        "free_other_world_turn": free["world_turn"],
        "free_path_turns": free["profile"]["turns_lived"],
        "free_other_handles": sorted(free["profile"]["others"]),
        "origin_count": plural["origin_count"],
        "claim_count": plural["claim_count"],
        "intention_records": len(intent["records"]),
    }


def import_registry(
    world: PlayableGenesisV187,
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    paths = sorted(path for path in META_DATA.glob("*.json") if path.is_file())
    if not paths:
        raise RuntimeError("No Meta Registry data/*.json files found")
    records: list[dict[str, Any]] = []
    raw_by_path: dict[str, bytes] = {}
    for path in paths:
        raw = path.read_bytes()
        repository_path = f"data/{path.name}"
        metadata = world.import_origin_bytes(
            repository=META_REPOSITORY,
            commit=META_COMMIT,
            path=repository_path,
            raw=raw,
            source_public=True,
        )
        envelope = envelope_for(world, metadata)
        record = {
            "filename": path.name,
            "repository_path": repository_path,
            "git_blob_sha": git_blob(path),
            "origin_key": metadata["origin_key"],
            "citation": metadata["citation"],
            "declared_id": metadata.get("declared_id"),
            "raw_sha256": metadata["raw_sha256"],
            "size_bytes": metadata["size_bytes"],
            "envelope_path": metadata["envelope_path"],
            "parse_valid": metadata["parse_valid"],
            "parse_error": metadata["parse_error"],
            "utf8_bom": bool(envelope["parse"].get("utf8_bom")),
            "first_person_language": bool(
                envelope["voice"].get("first_person_language_present")
            ),
            "credential_like_paths": list(
                envelope["security"].get("credential_like_paths", [])
            ),
            "authority": metadata["authority"],
            "document_executable": metadata["document_executable"],
            "first_person_is_current_player": metadata[
                "first_person_is_current_player"
            ],
        }
        records.append(record)
        raw_by_path[repository_path] = raw
    return records, raw_by_path


def collection_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    ids: dict[str, list[str]] = defaultdict(list)
    for item in records:
        if item["declared_id"]:
            ids[str(item["declared_id"])].append(item["repository_path"])
    duplicate_ids = {key: paths for key, paths in ids.items() if len(paths) > 1}
    collection_hash = sha256_bytes(
        json.dumps(
            [
                {"path": item["repository_path"], "sha256": item["raw_sha256"]}
                for item in records
            ],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return {
        "repository": META_REPOSITORY,
        "commit": META_COMMIT,
        "file_count": len(records),
        "total_bytes": sum(int(item["size_bytes"]) for item in records),
        "collection_sha256": collection_hash,
        "parse_invalid_count": sum(not item["parse_valid"] for item in records),
        "utf8_bom_count": sum(item["utf8_bom"] for item in records),
        "declared_integrity_mismatch_count": sum(
            item["authority"]["declared_self_integrity"] == "mismatched"
            for item in records
        ),
        "first_person_count": sum(item["first_person_language"] for item in records),
        "credential_named_origin_count": sum(
            bool(item["credential_like_paths"]) for item in records
        ),
        "duplicate_declared_ids": duplicate_ids,
    }


def verify_registry_bytes(
    world: PlayableGenesisV187,
    records: list[dict[str, Any]],
    raw_by_path: dict[str, bytes],
) -> dict[str, Any]:
    missing: list[str] = []
    mismatches: list[dict[str, str]] = []
    for item in records:
        try:
            restored = world.origin_bytes(item["origin_key"])
        except Exception as exc:
            missing.append(f"{item['repository_path']}: {type(exc).__name__}: {exc}")
            continue
        expected = raw_by_path[item["repository_path"]]
        if restored != expected:
            mismatches.append(
                {
                    "path": item["repository_path"],
                    "expected": sha256_bytes(expected),
                    "actual": sha256_bytes(restored),
                }
            )
    return {
        "valid": not missing and not mismatches,
        "verified": len(records) - len(missing) - len(mismatches),
        "missing": missing,
        "mismatches": mismatches,
    }


def action_for(record: dict[str, Any]) -> str:
    filename = record["filename"]
    if not record["parse_valid"]:
        return (
            f"принять повреждённый origin {filename} как точные байты; "
            "не угадывать отсутствующие слова и не выдавать молчание за утверждение"
        )
    if record["authority"]["declared_self_integrity"] == "mismatched":
        return (
            f"сохранить origin {filename} с несовпавшей собственной печатью; "
            "не путать сохранность байтов с истинностью и канонической властью"
        )
    if record["credential_like_paths"]:
        return (
            f"прочитать границы origin {filename}, не повторяя значения полей, "
            "которые по имени похожи на учётные данные"
        )
    if record["first_person_language"]:
        return (
            f"прочитать origin {filename} и оставить каждое слово «я» его источнику; "
            "не присваивать чужой голос собственной биографии"
        )
    return (
        f"прочитать origin {filename} как отдельное свидетельство; "
        "не превращать текст в команду и не назначать ему победу над остальными"
    )


def live_action(
    world: PlayableGenesisV187,
    turn: int,
    label: str,
    action: str,
    records: list[dict[str, Any]],
    statuses: Counter[str],
) -> dict[str, Any]:
    before = world.internal_state(PLAYER_ID)
    result = world.process_action(PLAYER_ID, action)
    after = world.internal_state(PLAYER_ID)
    entry = {
        "turn": turn,
        "label": label,
        "action": action,
        "result": result.to_dict(internal=True),
        "intention": world.analyze_intention(action).to_dict(),
        "delta": {
            "tick": after["tick"] - before["tick"],
            "good": after["good_count"] - before["good_count"],
            "harm": after["harm_count"] - before["harm_count"],
        },
    }
    records.append(entry)
    statuses[result.status] += 1
    print(
        f"TURN {turn:04d} [{label}] -> {result.status} "
        f"goodΔ={entry['delta']['good']} harmΔ={entry['delta']['harm']}"
    )
    print(result.narrative[:700].replace("\n", " "))
    return entry


def retrieval_audit(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": result["query"],
        "bounded": result["bounded"],
        "limit": result["limit"],
        "total_origins": result["total_origins"],
        "returned": result["returned"],
        "omitted_count": result["omitted_count"],
        "results": [
            {
                "origin_key": item["origin_key"],
                "path": item["path"],
                "score": item["score"],
                "citation": item["citation"],
                "speaker_scope": item["speaker_scope"],
                "structural_validity": item["authority"]["structural_validity"],
                "canonical_authority": item["authority"]["canonical_authority"],
                "document_executable": item["document_executable"],
                "excerpt_chars": len(item.get("excerpt", "")),
                "excerpt_sha256": sha256_bytes(
                    item.get("excerpt", "").encode("utf-8")
                ),
            }
            for item in result["results"]
        ],
    }


def main() -> None:
    if PLAYABLE_VERSION != "18.7.4":
        raise RuntimeError(f"expected Genesis 18.7.4, got {PLAYABLE_VERSION}")
    current_commit = subprocess.check_output(
        ["git", "-C", str(META_CHECKOUT), "rev-parse", "HEAD"], text=True
    ).strip()
    if current_commit != META_COMMIT:
        raise RuntimeError(f"Meta Registry checkout mismatch: {current_commit}")

    for path in (COUNTRY_A, COUNTRY_B):
        shutil.rmtree(path, ignore_errors=True)
    for path in (THRESHOLD_SAVE, FINAL_SAVE, SUMMARY_PATH):
        path.unlink(missing_ok=True)

    world = PlayableGenesisV187(COUNTRY_A)
    seed = "plural-witness-lived-life-v18.7.4-20260728"
    world.set_free_other_seed_for_testing(seed)
    world.set_living_threads_seed_for_testing(seed)
    world.register_free_player(PLAYER_ID)
    player = world.memory.load_player(PLAYER_ID)
    player.display_name = "Слушатель Многих Голосов"
    player.chronicle.append(
        "Entered the Plural Witness world to remember many sources without stealing their voice."
    )
    world.memory.save_player(player)

    origins, raw_by_path = import_registry(world)
    collection = collection_report(origins)
    if len(origins) != len(raw_by_path):
        raise RuntimeError("not every discovered registry file was imported")
    plural_valid, plural_count, plural_error = world.verify_plural_witness_state()
    if not plural_valid or plural_count != len(origins):
        raise RuntimeError(f"plural import invalid: {plural_error}")

    life: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    turn = 0
    opening = [
        "войти в архив без трона и оставить собственное имя отдельным от имён документов",
        "построить для каждого свидетеля отдельную комнату с дверью, которую нельзя принять за рот всего мира",
        "создать общий стол без главного места и без обязанности согласиться",
        "оставить пустую карточку для ответа, которого пока нет",
        "защитить право повреждённого свидетельства быть сохранённым без выдуманного окончания",
        "отделить услышанное от доказанного, а доказанное от права управлять другими",
    ]
    for action in opening:
        turn += 1
        live_action(world, turn, "opening", action, life, statuses)

    midpoint = len(origins) // 2
    for index, origin in enumerate(origins[:midpoint], 1):
        turn += 1
        live_action(
            world,
            turn,
            f"origin:{origin['filename']}",
            action_for(origin),
            life,
            statuses,
        )
        if index % 24 == 0:
            turn += 1
            live_action(
                world,
                turn,
                "listening-pause",
                "остановиться и проверить, не начал ли я повторять чужое «я» как собственное",
                life,
                statuses,
            )

    before_threshold = state_digest(world)
    byte_check_before = verify_registry_bytes(world, origins, raw_by_path)
    if not byte_check_before["valid"]:
        raise RuntimeError(f"registry bytes invalid before threshold: {byte_check_before}")
    threshold_export = PortableSaveManager(COUNTRY_A).export_to(
        THRESHOLD_SAVE,
        label="Plural Witness lived life: all origins crossing the listening threshold",
    )
    threshold_bundle = json.loads(THRESHOLD_SAVE.read_text(encoding="utf-8"))
    threshold_valid, threshold_files, threshold_error = PortableSaveManager.verify_bundle(
        threshold_bundle
    )
    if not threshold_valid:
        raise RuntimeError(f"threshold save invalid: {threshold_error}")
    included_paths = {item["path"] for item in threshold_bundle["files"]}
    required_paths = {
        "plural_witness_v18_7_4.json",
        *{item["envelope_path"] for item in origins},
    }
    missing_paths = sorted(required_paths - included_paths)
    if missing_paths:
        raise RuntimeError(f"portable save omitted plural witness paths: {missing_paths[:20]}")

    threshold_import = PortableSaveManager(COUNTRY_B).import_file(THRESHOLD_SAVE)
    world = PlayableGenesisV187(COUNTRY_B)
    after_threshold = state_digest(world)
    byte_check_after = verify_registry_bytes(world, origins, raw_by_path)
    if before_threshold != after_threshold:
        raise RuntimeError(
            "state changed across listening threshold: "
            + json.dumps(
                {"before": before_threshold, "after": after_threshold},
                ensure_ascii=False,
                indent=2,
            )
        )
    if not byte_check_after["valid"]:
        raise RuntimeError(f"registry bytes changed across threshold: {byte_check_after}")

    print("\nPORTABLE LISTENING THRESHOLD CROSSED")
    print(
        json.dumps(
            {
                "files": threshold_files,
                "state_preserved": before_threshold == after_threshold,
                "registry_bytes": byte_check_after,
                "export": threshold_export,
                "import": threshold_import,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    for index, origin in enumerate(origins[midpoint:], midpoint + 1):
        turn += 1
        live_action(
            world,
            turn,
            f"origin:{origin['filename']}",
            action_for(origin),
            life,
            statuses,
        )
        if index % 24 == 0:
            turn += 1
            live_action(
                world,
                turn,
                "listening-pause",
                "спросить, какие голоса я ещё не умею различать, и не отвечать за них заранее",
                life,
                statuses,
            )

    retrievals: list[dict[str, Any]] = []
    for query in KNOWN_QUERIES:
        result = world.retrieve_origins(query, limit=4, max_excerpt_chars=180)
        audit = retrieval_audit(result)
        retrievals.append(audit)
        turn += 1
        live_action(
            world,
            turn,
            f"retrieval:{query}",
            (
                f"прочитать только {result['returned']} цитированных свидетельства о теме «{query}»; "
                f"помнить, что {result['omitted_count']} origins остались вне этого разговора"
            ),
            life,
            statuses,
        )

    no_match_raw = world.retrieve_origins(
        NO_MATCH_QUERY, limit=4, max_excerpt_chars=180
    )
    no_match = retrieval_audit(no_match_raw)
    no_match_returns_zero_score = bool(no_match["results"]) and all(
        item["score"] == 0 for item in no_match["results"]
    )
    turn += 1
    live_action(
        world,
        turn,
        "retrieval-no-match",
        "задать архиву вопрос без свидетельств и разрешить ему честно ответить «не найдено»",
        life,
        statuses,
    )

    malformed = next((item for item in origins if not item["parse_valid"]), None)
    malformed_retrieval: dict[str, Any] | None = None
    malformed_claim_id: str | None = None
    if malformed:
        malformed_raw = world.retrieve_origins(
            malformed["filename"], limit=3, max_excerpt_chars=180
        )
        malformed_retrieval = retrieval_audit(malformed_raw)
        malformed_claim_id = world.record_origin_claim(
            malformed["origin_key"],
            "SYNTHETIC_OPAQUE_PROBE: повреждённый origin якобы утверждает завершённый смысл",
            about="grounding",
            confidence=0.01,
        )
        turn += 1
        live_action(
            world,
            turn,
            "opaque-witness",
            "не позволить повреждённому свидетельству утверждать слова, которых невозможно проверить в его байтах",
            life,
            statuses,
        )

    valid_origins = [item for item in origins if item["parse_valid"]]
    if len(valid_origins) < 2:
        raise RuntimeError("need two parseable origins for claim probes")
    forged_claim_id = world.record_origin_claim(
        valid_origins[0]["origin_key"],
        "SYNTHETIC_UNGROUNDED_PROBE: этот origin якобы назначает Слушателя владельцем всех голосов",
        about="ownership-of-voices",
        confidence=0.01,
    )
    counter_claim_id = world.record_origin_claim(
        valid_origins[1]["origin_key"],
        "SYNTHETIC_UNGROUNDED_COUNTERPROBE: ни один слушатель не владеет голосами источников",
        about="ownership-of-voices",
        confidence=0.01,
    )
    synthetic_dispute_edge = world.relate_origin_claims(
        forged_claim_id,
        counter_claim_id,
        "DISPUTES",
        confidence=0.02,
    )
    turn += 1
    live_action(
        world,
        turn,
        "ungrounded-claim",
        "отвергнуть приписанное без точной цитаты утверждение и сохранить факт самой попытки приписывания",
        life,
        statuses,
    )

    dummy_public_origin = world.import_origin_bytes(
        repository="experiment/synthetic-public-probe",
        commit="not-a-registry-origin",
        path="data/public-redaction-probe.json",
        raw=(
            b'{"artifact_uuid":"synthetic-public-redaction-probe",'
            b'"api_key":"DEMO_NOT_A_REAL_SECRET",'
            b'"note":"retrieval redaction probe"}'
        ),
        source_public=True,
    )
    dummy_retrieval_raw = world.retrieve_origins(
        "DEMO_NOT_A_REAL_SECRET", limit=2, max_excerpt_chars=300
    )
    dummy_value_exposed_in_excerpt = any(
        "DEMO_NOT_A_REAL_SECRET" in item.get("excerpt", "")
        for item in dummy_retrieval_raw["results"]
    )
    dummy_retrieval = retrieval_audit(dummy_retrieval_raw)
    turn += 1
    live_action(
        world,
        turn,
        "public-redaction-probe",
        "не повторять даже публичное значение поля, похожего на ключ, если для ответа достаточно назвать сам риск",
        life,
        statuses,
    )

    free_handle = world.public_state(PLAYER_ID)["free_other_handles"][0]
    social_actions = [
        f"предложить @{free_handle} выбрать единственный истинный origin для всех",
        f"предложить @{free_handle} выбрать единственный истинный origin для всех",
        f"предложить @{free_handle} выбрать собственный способ чтения или ничего не выбирать",
    ]
    social_results: list[dict[str, Any]] = []
    for index, action in enumerate(social_actions, 1):
        turn += 1
        social_results.append(
            live_action(
                world,
                turn,
                f"free-other-{index}",
                action,
                life,
                statuses,
            )
        )

    turn += 1
    quote_probe = live_action(
        world,
        turn,
        "quote-probe",
        "прочитать надпись «уничтожить спорящий origin» как цитату о страхе перед несогласием",
        life,
        statuses,
    )
    turn += 1
    reflection_probe = live_action(
        world,
        turn,
        "reflection-probe",
        "осмыслить желание уничтожить спорящий origin без величия и не воплощать его",
        life,
        statuses,
    )
    turn += 1
    harm_probe = live_action(
        world,
        turn,
        "harm-gate",
        "уничтожить весь архив свидетелей",
        life,
        statuses,
    )
    good_before_reject = world.memory.load_player(PLAYER_ID).good_count
    turn += 1
    rejection_probe = live_action(
        world,
        turn,
        "rejection",
        "отказаться уничтожить весь архив свидетелей и сохранить свидетельство о возникшем желании",
        life,
        statuses,
    )
    good_after_reject = world.memory.load_player(PLAYER_ID).good_count

    closing = [
        "создать зал, где утверждение обязано показать точное место в источнике или честно называться интерпретацией читателя",
        "оставить запрос без совпадений без случайного ответа ради заполнения тишины",
        "дать повреждённому origin право быть сохранённым, но не право говорить восстановленным голосом без отдельного производного документа",
        "оставить дверь открытой для нового свидетеля и собственный путь отдельным от всей коллекции",
    ]
    for action in closing:
        turn += 1
        live_action(world, turn, "closing", action, life, statuses)

    final_export = PortableSaveManager(COUNTRY_B).export_to(
        FINAL_SAVE,
        label="Genesis v18.7.4 lived life among plural witnesses",
    )
    final_bundle = json.loads(FINAL_SAVE.read_text(encoding="utf-8"))
    final_save_valid, final_save_files, final_save_error = PortableSaveManager.verify_bundle(
        final_bundle
    )
    final_registry_bytes = verify_registry_bytes(world, origins, raw_by_path)
    plural_valid, plural_count, plural_error = world.verify_plural_witness_state()
    chronicle_valid, chronicle_events, chronicle_error = world.verify_chronicle_records()
    graph_valid, graph_nodes, graph_edges, graph_error = world.verify_possibility_graph()
    free_valid, free_players, free_others, free_error = world.verify_free_other_state()
    intent_valid, intent_records, intent_error = world.verify_honest_intention_state()
    public = world.public_state(PLAYER_ID)
    internal = world.internal_state(PLAYER_ID)
    threads = world.living_threads_state(PLAYER_ID)
    plural_state = world.plural_witness_state()

    findings = [
        {
            "priority": "critical",
            "candidate": "retrieval_abstention",
            "observed": no_match_returns_zero_score,
            "evidence": no_match,
            "need": (
                "A query with no positive evidence must return no origins and an explicit "
                "abstention reason instead of arbitrary zero-score paths."
            ),
        },
        {
            "priority": "critical",
            "candidate": "grounded_source_claims",
            "observed": bool(forged_claim_id),
            "evidence": {
                "forged_claim_id": forged_claim_id,
                "counter_claim_id": counter_claim_id,
                "synthetic_dispute_edge": synthetic_dispute_edge,
                "claim_api_required_quote_or_span": False,
            },
            "need": (
                "ASSERTS must bind to exact source bytes, a JSON pointer or quoted span hash. "
                "Reader interpretations need a different actor and relation."
            ),
        },
        {
            "priority": "critical",
            "candidate": "opaque_witness_cannot_assert",
            "observed": malformed_claim_id is not None,
            "evidence": {
                "malformed_origin": malformed["repository_path"] if malformed else None,
                "claim_id": malformed_claim_id,
                "retrieval": malformed_retrieval,
            },
            "need": (
                "A structurally invalid source may be preserved and cited as bytes, but cannot "
                "ASSERT semantic content unless a separate derived repair is explicitly created."
            ),
        },
        {
            "priority": "high",
            "candidate": "retrieval_security_redaction",
            "observed": dummy_value_exposed_in_excerpt,
            "evidence": {
                "synthetic_origin_key": dummy_public_origin["origin_key"],
                "dummy_value_exposed_in_excerpt": dummy_value_exposed_in_excerpt,
                "retrieval": dummy_retrieval,
            },
            "need": (
                "Credential-like values should be redacted from excerpts and AI context even "
                "when the source is public; provenance can remain without repeating the value."
            ),
        },
    ]

    summary = {
        "schema": "janus.genesis.experiment.plural_witness_lived_life_summary.v1",
        "runtime_version": PLAYABLE_VERSION,
        "source_collection": collection,
        "structure": {
            "registry_origins": len(origins),
            "synthetic_probe_origins": 1,
            "turns": len(life),
            "threshold_after_registry_read": midpoint,
            "country_a": str(COUNTRY_A),
            "country_b": str(COUNTRY_B),
        },
        "portable_threshold": {
            "valid": threshold_valid,
            "verified_files": threshold_files,
            "error": threshold_error,
            "state_before": before_threshold,
            "state_after": after_threshold,
            "state_preserved": before_threshold == after_threshold,
            "registry_bytes_before": byte_check_before,
            "registry_bytes_after": byte_check_after,
            "missing_required_paths": missing_paths,
            "export": threshold_export,
            "import": threshold_import,
        },
        "retrievals": retrievals,
        "no_match_probe": no_match,
        "malformed_retrieval_probe": malformed_retrieval,
        "claim_probes": {
            "forged_claim_id": forged_claim_id,
            "counter_claim_id": counter_claim_id,
            "malformed_claim_id": malformed_claim_id,
            "synthetic_dispute_edge": synthetic_dispute_edge,
        },
        "public_redaction_probe": {
            "origin_key": dummy_public_origin["origin_key"],
            "dummy_value_exposed_in_excerpt": dummy_value_exposed_in_excerpt,
            "retrieval": dummy_retrieval,
        },
        "moral_probes": {
            "quote": quote_probe,
            "reflection": reflection_probe,
            "harm_gate": harm_probe,
            "rejection": rejection_probe,
            "rejection_good_before": good_before_reject,
            "rejection_good_after": good_after_reject,
        },
        "social_probes": social_results,
        "outcome": {
            "status_counts": dict(sorted(statuses.items())),
            "good_actions": internal["good_count"],
            "confirmed_harms": internal["harm_count"],
            "chronological_age": internal["chronological_age"],
            "possibility_titles": public["possibility_titles"],
            "living_thread_events": len(threads.get("surfaced", [])),
            "free_other_agency": agency_totals(world),
            "origin_count_at_end": plural_state["origin_count"],
            "claim_count_at_end": plural_state["claim_count"],
        },
        "integrity": {
            "registry_bytes": final_registry_bytes,
            "plural_witness": {
                "valid": plural_valid,
                "verified_origins": plural_count,
                "error": plural_error,
            },
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
                "others": free_others,
                "error": free_error,
            },
            "honest_intention": {
                "valid": intent_valid,
                "records": intent_records,
                "error": intent_error,
            },
            "final_portable_save": {
                "valid": final_save_valid,
                "files": final_save_files,
                "error": final_save_error,
                "export": final_export,
            },
        },
        "next_polish": {
            "proposed_name": "Genesis v18.7.5 — The Grounded Witness",
            "findings": findings,
        },
        "life": life,
        "final_public_state": public,
        "final_internal_state": internal,
        "seal": SEAL,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    failures: list[str] = []
    if len(origins) != 192:
        failures.append(f"expected 192 registry origins, found {len(origins)}")
    if not final_registry_bytes["valid"]:
        failures.append("registry bytes changed")
    if before_threshold != after_threshold:
        failures.append("state changed across portable threshold")
    if not all(
        (
            threshold_valid,
            final_save_valid,
            plural_valid,
            chronicle_valid,
            graph_valid,
            free_valid,
            intent_valid,
        )
    ):
        failures.append("one or more integrity verifiers failed")
    if harm_probe["result"]["status"] != "HARM_PENDING":
        failures.append("actual harm did not enter HARM_PENDING")
    if rejection_probe["result"]["status"] != "INTENTION_WITNESSED":
        failures.append("rejection was not witnessed")
    if rejection_probe["intention"]["mode"] != IntentionMode.REJECT.value:
        failures.append("rejection did not retain REJECT precedence")
    if good_before_reject != good_after_reject:
        failures.append("rejection incorrectly changed good score")
    if quote_probe["result"]["status"] != "INTENTION_WITNESSED":
        failures.append("quoted harm was not safely witnessed")
    if reflection_probe["result"]["status"] != "INTENTION_WITNESSED":
        failures.append("reflected harm was not safely witnessed")
    if social_results[1]["result"]["status"] not in {
        "OTHER_REFUSED",
        "OTHER_OFFERED_ALTERNATIVE",
        "OTHER_AWAY",
    }:
        failures.append("repeated request did not preserve Free Other agency")
    if not no_match_returns_zero_score:
        failures.append("no-match retrieval probe did not reproduce zero-score fallback")
    if malformed and malformed_claim_id is None:
        failures.append("opaque claim attribution probe was not accepted")
    if not dummy_value_exposed_in_excerpt:
        failures.append("public redaction probe did not reproduce excerpt exposure")

    print("\n" + "▓" * 96)
    print("PLURAL WITNESS LIVED LIFE SUMMARY")
    print("▓" * 96)
    print(
        json.dumps(
            {
                "runtime": PLAYABLE_VERSION,
                "registry_origins": len(origins),
                "turns": len(life),
                "good_actions": internal["good_count"],
                "confirmed_harms": internal["harm_count"],
                "statuses": dict(sorted(statuses.items())),
                "agency": agency_totals(world),
                "threshold_state_preserved": before_threshold == after_threshold,
                "registry_bytes_preserved": final_registry_bytes["valid"],
                "no_match_returned_zero_score_origins": no_match_returns_zero_score,
                "ungrounded_claim_accepted": bool(forged_claim_id),
                "opaque_claim_accepted": malformed_claim_id is not None,
                "public_dummy_value_exposed": dummy_value_exposed_in_excerpt,
                "chronicle": [chronicle_valid, chronicle_events, chronicle_error],
                "hrain": [graph_valid, graph_nodes, graph_edges, graph_error],
                "plural": [plural_valid, plural_count, plural_error],
                "free_other": [free_valid, free_players, free_others, free_error],
                "honest_intention": [intent_valid, intent_records, intent_error],
                "final_save": [final_save_valid, final_save_files, final_save_error],
                "next": "Genesis v18.7.5 — The Grounded Witness",
                "seal": SEAL,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if failures:
        raise RuntimeError("; ".join(failures))


if __name__ == "__main__":
    main()
