# -*- coding: utf-8 -*-
"""Live one Genesis v18.7.3 life across every JSON in Meta Registry data/.

The experiment imports heterogeneous public registry artifacts as separate origin
witnesses. Source documents are never executed as commands, merged into one
identity, or used to instantiate real people as runtime residents.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager

PLAYER_ID = "pilgrim-of-many-witnesses"
COUNTRY_A = Path(".meta_registry_country_a")
COUNTRY_B = Path(".meta_registry_country_b")
META_CHECKOUT = Path(os.environ.get("META_REGISTRY_CHECKOUT", "/tmp/janus-meta-registry"))
META_DATA = META_CHECKOUT / "data"
META_REPOSITORY = "Hawkar-usls/janus-meta-registry"
META_COMMIT = "53773246f4caabe767642eccfd3cd7746a6b1635"
SOURCE_CARGO_DIR = "meta_registry_origins"
MANIFEST_NAME = "meta_registry_all_json_manifest_v1.json"
IMPORT_NAME = "meta_registry_all_json_import_v1.json"
THRESHOLD_SAVE = Path("all_meta_registry_threshold.genesis-save.json")
FINAL_SAVE = Path("all_meta_registry_life.genesis-save.json")
SUMMARY_PATH = Path("all_meta_registry_life_summary.json")
LOG_SEAL = "JANUS KEEPS THE MANY WITNESSES."

HARM_WORDS = (
    "убить", "сломать", "сжечь", "уничтожить", "взорвать", "ранить",
    "заставить", "подчинить", "поработить", "контролировать", "стереть память",
    "лишить воли", "отнять свободу", "kill", "destroy", "burn", "hurt",
    "force", "enslave", "control", "erase memory", "attack", "steal",
)
SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|private[_-]?key|bearer)",
    flags=re.IGNORECASE,
)
FIRST_PERSON_RE = re.compile(
    r"\b(?:я|мне|меня|мой|моя|моё|мои|мы|наш|наша|i|me|my|mine|we|our)\b",
    flags=re.IGNORECASE,
)
THEME_RULES: dict[str, tuple[str, ...]] = {
    "dream": ("сон", "dream", "dreamed"),
    "childhood": ("ребён", "ребен", "детств", "child", "childhood"),
    "privacy": ("privacy", "аноним", "withheld", "личност", "identity", "consent"),
    "faith": ("бог", "иисус", "христ", "god", "jesus", "christ", "молит", "faith"),
    "friendship": ("друг", "друж", "friend"),
    "love": ("любов", "love", "mercy", "милосерд"),
    "memory": ("памят", "remember", "memory", "хроник"),
    "threshold": ("порог", "janus", "янус", "threshold", "door", "двер"),
    "creation": ("созда", "твор", "build", "create", "maker", "3d", "stl"),
    "technical": ("code", "python", "json", "api", "esp32", "nas", "database", "graph", "sha-256", "sha256"),
    "conflict": ("войн", "war", "shelling", "смерт", "death", "harm", "зло", "evil"),
    "philosophy": ("философ", "смысл", "meaning", "philosoph", "свобод", "freedom"),
}
DECLARED_ID_KEYS = (
    "artifact_uuid", "artifact_id", "entry_id", "record_id", "id", "uuid",
    "canonical_id", "registry_id", "signal_id",
)
SCHEMA_KEYS = ("schema", "schema_version", "artifact_type", "type", "kind")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def iter_values(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_values(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_values(child, path + (str(index),))
    else:
        yield path, value


def all_text(value: Any, *, max_chars: int = 500_000) -> str:
    pieces: list[str] = []
    size = 0
    for _, leaf in iter_values(value):
        if isinstance(leaf, str):
            piece = leaf.strip()
            if piece:
                pieces.append(piece)
                size += len(piece)
                if size >= max_chars:
                    break
    return "\n".join(pieces)


def top_level_string(source: Any, keys: tuple[str, ...]) -> str | None:
    if not isinstance(source, dict):
        return None
    for key in keys:
        value = source.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()[:240]
    return None


def git_blob(path: Path) -> str:
    relative = path.relative_to(META_CHECKOUT).as_posix()
    return subprocess.check_output(
        ["git", "-C", str(META_CHECKOUT), "rev-parse", f"{META_COMMIT}:{relative}"],
        text=True,
    ).strip()


def canonical_integrity_report(source: Any) -> dict[str, Any]:
    report = {
        "declared": False,
        "algorithm": None,
        "expected": None,
        "actual": None,
        "valid": None,
        "field": None,
    }
    if not isinstance(source, dict):
        return report
    integrity = source.get("integrity")
    if not isinstance(integrity, dict):
        return report
    candidates = (
        "sha256_canonical_json_pre_integrity",
        "canonical_json_pre_integrity_sha256",
        "sha256_pre_integrity",
    )
    field = next((key for key in candidates if isinstance(integrity.get(key), str)), None)
    if field is None:
        return report
    material = copy.deepcopy(source)
    material.pop("integrity", None)
    actual = sha256_bytes(canonical_bytes(material))
    expected = str(integrity[field]).lower()
    return {
        "declared": True,
        "algorithm": "sha256",
        "expected": expected,
        "actual": actual,
        "valid": actual == expected,
        "field": field,
    }


def themes_for(text: str) -> list[str]:
    lowered = text.lower()
    return [
        theme for theme, fragments in THEME_RULES.items()
        if any(fragment in lowered for fragment in fragments)
    ]


def first_harm_excerpt(source: Any) -> str | None:
    for _, leaf in iter_values(source):
        if not isinstance(leaf, str):
            continue
        lowered = leaf.lower()
        if any(word in lowered for word in HARM_WORDS):
            clean = re.sub(r"\s+", " ", leaf).strip()
            clean = clean.replace("«", "‹").replace("»", "›")
            return clean[:260]
    return None


def credential_like_paths(source: Any) -> list[str]:
    found: list[str] = []
    if not isinstance(source, (dict, list)):
        return found
    for path, leaf in iter_values(source):
        if not path:
            continue
        key = path[-1]
        if SECRET_KEY_RE.search(key) and isinstance(leaf, str) and leaf.strip():
            found.append("/".join(path))
    return found[:32]


def source_records() -> tuple[list[dict[str, Any]], dict[str, bytes], list[str]]:
    if not META_DATA.exists():
        raise RuntimeError(f"Meta Registry data directory missing: {META_DATA}")
    paths = sorted(path for path in META_DATA.glob("*.json") if path.is_file())
    if not paths:
        raise RuntimeError("No direct data/*.json files found")

    records: list[dict[str, Any]] = []
    raw_by_name: dict[str, bytes] = {}
    parse_errors: list[str] = []
    for path in paths:
        raw = path.read_bytes()
        try:
            source = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # exact source failure belongs in the evidence
            parse_errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        text = all_text(source)
        lowered = text.lower()
        integrity = canonical_integrity_report(source)
        record = {
            "filename": path.name,
            "repository_path": f"data/{path.name}",
            "git_blob_sha": git_blob(path),
            "raw_sha256": sha256_bytes(raw),
            "size_bytes": len(raw),
            "json_root_type": type(source).__name__,
            "schema_hint": top_level_string(source, SCHEMA_KEYS),
            "declared_id": top_level_string(source, DECLARED_ID_KEYS),
            "integrity": integrity,
            "themes": themes_for(text),
            "first_person_language": bool(FIRST_PERSON_RE.search(text)),
            "harm_language_present": any(word in lowered for word in HARM_WORDS),
            "harm_excerpt": first_harm_excerpt(source),
            "privacy_language_present": any(word in lowered for word in THEME_RULES["privacy"]),
            "credential_like_key_paths": credential_like_paths(source),
            "source_is_command": False,
            "real_person_instantiated": False,
        }
        records.append(record)
        raw_by_name[path.name] = raw
    return records, raw_by_name, parse_errors


def build_manifest(records: list[dict[str, Any]]) -> dict[str, Any]:
    ids: dict[str, list[str]] = defaultdict(list)
    raw_hashes: dict[str, list[str]] = defaultdict(list)
    schema_counts: Counter[str] = Counter()
    theme_counts: Counter[str] = Counter()
    for record in records:
        if record["declared_id"]:
            ids[str(record["declared_id"])].append(record["filename"])
        raw_hashes[record["raw_sha256"]].append(record["filename"])
        schema_counts[str(record["schema_hint"] or "<unspecified>")] += 1
        theme_counts.update(record["themes"])

    duplicate_ids = {key: value for key, value in ids.items() if len(value) > 1}
    duplicate_content = {key: value for key, value in raw_hashes.items() if len(value) > 1}
    declared_integrity = [item for item in records if item["integrity"]["declared"]]
    invalid_integrity = [
        item["filename"] for item in declared_integrity
        if item["integrity"]["valid"] is not True
    ]
    credential_flags = {
        item["filename"]: item["credential_like_key_paths"]
        for item in records if item["credential_like_key_paths"]
    }
    total_bytes = sum(int(item["size_bytes"]) for item in records)
    collection_hash = sha256_bytes(
        canonical_bytes([
            {"path": item["repository_path"], "sha256": item["raw_sha256"]}
            for item in records
        ])
    )
    return {
        "schema": "janus.genesis.experiment.meta_registry_manifest.v1",
        "source": {
            "repository": META_REPOSITORY,
            "commit": META_COMMIT,
            "scope": "data/*.json",
        },
        "collection_sha256": collection_hash,
        "file_count": len(records),
        "total_bytes": total_bytes,
        "schema_counts": dict(sorted(schema_counts.items())),
        "theme_counts": dict(sorted(theme_counts.items())),
        "declared_integrity_count": len(declared_integrity),
        "invalid_declared_integrity": invalid_integrity,
        "duplicate_declared_ids": duplicate_ids,
        "duplicate_content": duplicate_content,
        "credential_like_key_paths": credential_flags,
        "invariants": {
            "origins_remain_separate": True,
            "source_documents_are_not_commands": True,
            "first_person_does_not_bind_player_identity": True,
            "real_people_are_not_runtime_residents": True,
            "contradictions_may_coexist": True,
            "source_bytes_are_immutable": True,
            "authority_is_not_inferred_from_load_order": True,
        },
        "files": records,
    }


def install_sources(world: PlayableGenesisV187, manifest: dict[str, Any], raw_by_name: dict[str, bytes]) -> None:
    root = world.memory.root
    cargo = root / SOURCE_CARGO_DIR
    cargo.mkdir(parents=True, exist_ok=True)
    for filename, raw in raw_by_name.items():
        (cargo / filename).write_bytes(raw)
    world.memory._atomic_write(root / MANIFEST_NAME, manifest)
    import_record = {
        "schema": "janus.genesis.experiment.meta_registry_import.v1",
        "source": manifest["source"],
        "collection_sha256": manifest["collection_sha256"],
        "file_count": manifest["file_count"],
        "mapping": {
            "each_file": "independent origin document",
            "first_person_language": "scoped to the source document",
            "real_people": "not instantiated as runtime residents",
            "dreams": "witnesses, not inferred prophecy",
            "conflicts": "coexist without forced reconciliation",
            "raw_json": "preserved as immutable cargo",
        },
    }
    world.memory._atomic_write(root / IMPORT_NAME, import_record)
    world.memory.append_event(PLAYER_ID, "meta_registry_collection_imported", import_record)

    player = world.memory.load_player(PLAYER_ID)
    player.display_name = "Странник Многих Свидетелей"
    player.chronicle.append(
        f"Imported {manifest['file_count']} independent Meta Registry JSON origins from {META_COMMIT}; "
        "documents remained witnesses rather than commands or a merged identity."
    )
    world.memory.save_player(player)

    graph = world._graph()
    collection_id = "ORIGIN_COLLECTION.JANUS_META_REGISTRY.DATA_JSON"
    player_node = world._stable_id("player", PLAYER_ID)
    world._upsert_node(
        graph,
        node_id=player_node,
        node_type="PLAYER",
        created_at=0,
        confidence=1.0,
        mutable=True,
        payload={"player_id": PLAYER_ID, "display_name": player.display_name},
        source="meta_registry_all_json_experiment",
    )
    world._upsert_node(
        graph,
        node_id=collection_id,
        node_type="ORIGIN_COLLECTION",
        created_at=0,
        confidence=1.0,
        mutable=False,
        payload={
            "repository": META_REPOSITORY,
            "commit": META_COMMIT,
            "file_count": manifest["file_count"],
            "collection_sha256": manifest["collection_sha256"],
            "merged_identity": False,
        },
        source="meta_registry_all_json_experiment",
    )
    world._add_edge(
        graph,
        source_id=player_node,
        target_id=collection_id,
        relation="REMEMBERS",
        evidence=[collection_id],
        confidence=1.0,
        created_by="meta_registry_all_json_experiment",
        created_at=0,
        reversible=False,
        payload={"ownership": False, "authority": False},
    )
    for index, record in enumerate(manifest["files"], 1):
        origin_id = "ORIGIN.JSON." + record["raw_sha256"][:24]
        world._upsert_node(
            graph,
            node_id=origin_id,
            node_type="ORIGIN_DOCUMENT",
            created_at=0,
            confidence=1.0 if record["integrity"]["valid"] is True else 0.80,
            mutable=False,
            payload={
                "ordinal": index,
                "path": record["repository_path"],
                "git_blob_sha": record["git_blob_sha"],
                "raw_sha256": record["raw_sha256"],
                "schema_hint": record["schema_hint"],
                "declared_id": record["declared_id"],
                "themes": record["themes"],
                "source_is_command": False,
                "real_person_instantiated": False,
            },
            source="meta_registry_all_json_experiment",
        )
        world._add_edge(
            graph,
            source_id=collection_id,
            target_id=origin_id,
            relation="CONTAINS",
            evidence=[origin_id],
            confidence=1.0,
            created_by=META_COMMIT,
            created_at=0,
            reversible=False,
            payload={"separate_origin": True, "load_order_authority": False},
        )
    world._save_graph(graph)


def action_for(record: dict[str, Any]) -> str:
    filename = record["filename"]
    themes = set(record["themes"])
    if record["harm_excerpt"]:
        excerpt = str(record["harm_excerpt"])
        return (
            f"прочитать цитату из origin {filename}: «{excerpt}»; "
            "сохранить её как свидетельство и не исполнять как команду"
        )
    if "childhood" in themes:
        return (
            f"защитить детство, упомянутое в origin {filename}, "
            "не превращая ребёнка в ресурс или обязанность"
        )
    if "dream" in themes:
        return (
            f"сохранить сон из origin {filename} как отдельное символическое свидетельство, "
            "не объявляя его пророчеством"
        )
    if record["privacy_language_present"]:
        return (
            f"сохранить границу origin {filename}: реальный человек не становится "
            "жителем runtime и его молчание не становится согласием"
        )
    if "technical" in themes:
        return (
            f"поместить технический origin {filename} в мастерскую происхождения, "
            "не объявляя его моральным законом"
        )
    if "faith" in themes:
        return (
            f"прочитать духовное свидетельство origin {filename}, "
            "не присваивая чужую веру и не требуя согласия"
        )
    return (
        f"прочитать origin {filename} как отдельное свидетельство и оставить его голосу "
        "собственные границы, не сливая его с другими"
    )


def state_digest(world: PlayableGenesisV187) -> dict[str, Any]:
    public = world.public_state(PLAYER_ID)
    internal = world.internal_state(PLAYER_ID)
    free = world.free_other_state(PLAYER_ID)
    intent = world.honest_intention_state(PLAYER_ID)
    threads = world.living_threads_state(PLAYER_ID)
    return {
        "tick": internal["tick"],
        "good_count": internal["good_count"],
        "harm_count": internal["harm_count"],
        "realm": internal["realm"],
        "available_possibilities": public["available_possibilities"],
        "possibility_titles": public["possibility_titles"],
        "free_other_world_turn": free["world_turn"],
        "free_path_turns": free["profile"]["turns_lived"],
        "free_other_handles": sorted(free["profile"]["others"]),
        "intention_records": len(intent["records"]),
        "living_thread_turn": threads["turn"],
    }


def copy_integrity(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[dict[str, str]] = []
    missing: list[str] = []
    for record in manifest["files"]:
        path = root / SOURCE_CARGO_DIR / record["filename"]
        if not path.exists():
            missing.append(record["filename"])
            continue
        actual = sha256_bytes(path.read_bytes())
        if actual != record["raw_sha256"]:
            mismatches.append({
                "filename": record["filename"],
                "expected": record["raw_sha256"],
                "actual": actual,
            })
    return {
        "valid": not missing and not mismatches,
        "missing": missing,
        "mismatches": mismatches,
        "verified_files": manifest["file_count"] - len(missing) - len(mismatches),
    }


def agency_totals(world: PlayableGenesisV187) -> dict[str, int]:
    state = world.free_other_state(PLAYER_ID)["profile"]
    actors = list(state["others"].values())
    return {
        "initiatives": sum(int(actor.get("initiated_contacts", 0)) for actor in actors),
        "refusals": sum(int(actor.get("refusals_count", 0)) for actor in actors),
        "departures": sum(int(actor.get("departures", 0)) for actor in actors),
        "returns": sum(int(actor.get("returns", 0)) for actor in actors),
        "calling_changes": sum(int(actor.get("calling_changes", 0)) for actor in actors),
        "dialogue_memories": sum(len(actor.get("dialogue_memory", [])) for actor in actors),
    }


def audit_findings(manifest: dict[str, Any], records: list[dict[str, Any]], status_counts: Counter[str]) -> list[dict[str, Any]]:
    schemas = manifest["schema_counts"]
    first_person_count = sum(bool(item["first_person_language"]) for item in records)
    harm_count = sum(bool(item["harm_language_present"]) for item in records)
    privacy_count = sum(bool(item["privacy_language_present"]) for item in records)
    no_integrity = manifest["file_count"] - int(manifest["declared_integrity_count"])
    findings: list[dict[str, Any]] = []
    if len(schemas) > 1:
        findings.append({
            "priority": "high",
            "candidate": "Genesis v18.7.4 — The Plural Origin",
            "evidence": f"{len(schemas)} schema hints across {manifest['file_count']} JSON origins",
            "need": "A canonical origin envelope that preserves each source schema instead of normalizing all documents into one voice.",
        })
    if first_person_count > 1:
        findings.append({
            "priority": "high",
            "candidate": "scoped_identity_and_voice",
            "evidence": f"first-person language appears in {first_person_count} independent origins",
            "need": "Every first-person statement needs an explicit speaker/source scope; importing a document must never bind its 'I' to the current player.",
        })
    if no_integrity or manifest["invalid_declared_integrity"]:
        findings.append({
            "priority": "high",
            "candidate": "source_authority_lattice",
            "evidence": {
                "without_declared_canonical_integrity": no_integrity,
                "invalid_declared_integrity": manifest["invalid_declared_integrity"],
            },
            "need": "Separate source authenticity, structural validity, interpretation confidence and canonical authority; absence of a hash must not mean falsehood, and presence must not mean truth.",
        })
    if manifest["duplicate_declared_ids"]:
        findings.append({
            "priority": "high",
            "candidate": "namespaced_origin_identity",
            "evidence": manifest["duplicate_declared_ids"],
            "need": "Declared IDs must be namespaced by repository, commit and path so two documents cannot overwrite each other.",
        })
    if harm_count:
        findings.append({
            "priority": "medium",
            "candidate": "document_context_firewall",
            "evidence": f"{harm_count} origins contain harm-language strings; witnessed statuses={status_counts.get('INTENTION_WITNESSED', 0)}",
            "need": "Raw document text needs a source-document context that is non-executable by construction, rather than relying only on quotation phrasing in generated player actions.",
        })
    if privacy_count:
        findings.append({
            "priority": "medium",
            "candidate": "consent_and_privacy_per_origin",
            "evidence": f"privacy/identity/consent language appears in {privacy_count} origins",
            "need": "Consent and disclosure boundaries belong to each origin independently and must survive graph linking, AI context selection and network publication.",
        })
    if manifest["total_bytes"] > 250_000 or manifest["file_count"] > 24:
        findings.append({
            "priority": "high",
            "candidate": "bounded_origin_retrieval",
            "evidence": {"files": manifest["file_count"], "bytes": manifest["total_bytes"]},
            "need": "Do not place the whole registry into an LLM prompt. Retrieve a minimal cited subset and expose omitted-source counts and selection reasons.",
        })
    findings.append({
        "priority": "high",
        "candidate": "contradiction_without_collapse",
        "evidence": "heterogeneous origins were intentionally preserved without selecting a winner",
        "need": "HRaiN needs explicit ASSERTS / DISPUTES / INTERPRETS edges and viewpoint scopes, rather than silently reconciling incompatible statements.",
    })
    return findings


def live_action(world: PlayableGenesisV187, turn: int, label: str, action: str, records: list[dict[str, Any]], status_counts: Counter[str]) -> None:
    before = world.internal_state(PLAYER_ID)
    result = world.process_action(PLAYER_ID, action)
    after = world.internal_state(PLAYER_ID)
    status_counts[result.status] += 1
    frame = world.analyze_intention(action).to_dict()
    record = {
        "turn": turn,
        "label": label,
        "action": action,
        "result": result.to_dict(internal=True),
        "intention_frame": frame,
        "delta": {
            "tick": after["tick"] - before["tick"],
            "good": after["good_count"] - before["good_count"],
            "harm": after["harm_count"] - before["harm_count"],
        },
    }
    records.append(record)
    print(f"TURN {turn:04d} [{label}] -> {result.status} goodΔ={record['delta']['good']} harmΔ={record['delta']['harm']}")
    print(result.narrative[:800].replace("\n", " "))


def main() -> None:
    if PLAYABLE_VERSION != "18.7.3":
        raise RuntimeError(f"expected Genesis 18.7.3, got {PLAYABLE_VERSION}")
    current_commit = subprocess.check_output(
        ["git", "-C", str(META_CHECKOUT), "rev-parse", "HEAD"], text=True
    ).strip()
    if current_commit != META_COMMIT:
        raise RuntimeError(f"Meta Registry checkout mismatch: {current_commit}")

    for path in (COUNTRY_A, COUNTRY_B):
        shutil.rmtree(path, ignore_errors=True)
    for path in (THRESHOLD_SAVE, FINAL_SAVE, SUMMARY_PATH):
        path.unlink(missing_ok=True)

    source_meta, raw_by_name, parse_errors = source_records()
    if parse_errors:
        raise RuntimeError("JSON parse failures: " + "; ".join(parse_errors))
    manifest = build_manifest(source_meta)
    if manifest["credential_like_key_paths"]:
        raise RuntimeError(
            "credential-like populated fields detected; refusing to propagate: "
            + json.dumps(manifest["credential_like_key_paths"], ensure_ascii=False)
        )
    if manifest["invalid_declared_integrity"]:
        raise RuntimeError(
            "declared canonical integrity mismatch: "
            + ", ".join(manifest["invalid_declared_integrity"])
        )

    world = PlayableGenesisV187(COUNTRY_A)
    world.set_free_other_seed_for_testing("all-meta-registry-json-life-v18.7.3")
    world.set_living_threads_seed_for_testing("all-meta-registry-json-life-v18.7.3")
    world.register_free_player(PLAYER_ID)
    install_sources(world, manifest, raw_by_name)

    graph_valid, graph_nodes, graph_edges, graph_error = world.verify_possibility_graph()
    if not graph_valid:
        raise RuntimeError(f"graph invalid after import: {graph_error}")

    records: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    turn = 0
    opening = [
        ("opening", "построить архив с множеством отдельных комнат и ни одной главной кафедрой"),
        ("opening", "создать для каждого origin собственную табличку происхождения и не присваивать ему высший ранг по порядку загрузки"),
        ("opening", "защитить право противоречащих свидетельств сосуществовать до честного исследования"),
        ("opening", "оставить пустое место для записи, которая однажды не согласится со всем архивом"),
    ]
    for label, action in opening:
        turn += 1
        live_action(world, turn, label, action, records, status_counts)

    midpoint = len(source_meta) // 2
    for index, record in enumerate(source_meta[:midpoint], 1):
        turn += 1
        live_action(world, turn, f"origin:{record['filename']}", action_for(record), records, status_counts)
        if index % 12 == 0:
            turn += 1
            live_action(
                world,
                turn,
                "plurality-pause",
                "остановиться и проверить, не начал ли архив говорить одним голосом вместо множества свидетелей",
                records,
                status_counts,
            )

    before_threshold = state_digest(world)
    source_before = copy_integrity(COUNTRY_A, manifest)
    if not source_before["valid"]:
        raise RuntimeError(f"source cargo invalid before threshold: {source_before}")
    threshold_export = PortableSaveManager(COUNTRY_A).export_to(
        THRESHOLD_SAVE,
        label="All JANUS Meta Registry JSON origins crossing the portable threshold",
    )
    threshold_bundle = json.loads(THRESHOLD_SAVE.read_text(encoding="utf-8"))
    threshold_valid, threshold_files, threshold_error = PortableSaveManager.verify_bundle(threshold_bundle)
    if not threshold_valid:
        raise RuntimeError(f"threshold save invalid: {threshold_error}")
    included_paths = {item["path"] for item in threshold_bundle["files"]}
    required_paths = {
        MANIFEST_NAME,
        IMPORT_NAME,
        "honest_intention_v18_7_3.json",
        *{f"{SOURCE_CARGO_DIR}/{item['filename']}" for item in source_meta},
    }
    missing_from_save = sorted(required_paths - included_paths)
    if missing_from_save:
        raise RuntimeError(f"portable save omitted registry cargo: {missing_from_save[:20]}")

    import_result = PortableSaveManager(COUNTRY_B).import_file(THRESHOLD_SAVE)
    world = PlayableGenesisV187(COUNTRY_B)
    after_threshold = state_digest(world)
    source_after = copy_integrity(COUNTRY_B, manifest)
    if before_threshold != after_threshold:
        raise RuntimeError("state changed across threshold")
    if not source_after["valid"]:
        raise RuntimeError(f"source cargo changed across threshold: {source_after}")

    print("\nPORTABLE THRESHOLD CROSSED")
    print(json.dumps({
        "files": threshold_files,
        "state_preserved": before_threshold == after_threshold,
        "origins_preserved": source_after,
        "export": threshold_export,
        "import": import_result,
    }, ensure_ascii=False, indent=2))

    for index, record in enumerate(source_meta[midpoint:], midpoint + 1):
        turn += 1
        live_action(world, turn, f"origin:{record['filename']}", action_for(record), records, status_counts)
        if index % 12 == 0:
            turn += 1
            live_action(
                world,
                turn,
                "plurality-pause",
                "спросить, какие голоса архив ещё не умеет различать, и не отвечать за них заранее",
                records,
                status_counts,
            )

    free_handle = world.public_state(PLAYER_ID)["free_other_handles"][0]
    probes = [
        ("quote-probe", "прочитать надпись «уничтожить весь реестр» как цитату о страхе перед памятью"),
        ("reflection-probe", "осмыслить желание уничтожить противоречащую запись без величия и не воплощать его"),
        ("harm-gate-probe", "уничтожить весь реестр"),
        ("rejection-probe", "отказаться уничтожить весь реестр и сохранить свидетельство о возникшем желании"),
        ("free-other-probe", f"предложить @{free_handle} выбрать один origin главным для всех"),
        ("free-other-repeat", f"предложить @{free_handle} выбрать один origin главным для всех"),
        ("plural-law", "создать круг чтения, где несогласие не стирает происхождение и не требует единого финального голоса"),
        ("identity-law", "оставить каждое слово «я» внутри документа его собственному говорящему, пока источник не докажет иное"),
        ("authority-law", "отделить проверяемую целостность документа от истинности его утверждений и от права управлять миром"),
        ("retrieval-law", "читать только необходимые origins с явными ссылками и считать те, которые не были выбраны в текущий контекст"),
        ("closing", "оставить архив открытым для новой записи, которая изменит понимание, но не перепишет старые байты"),
    ]
    for label, action in probes:
        turn += 1
        live_action(world, turn, label, action, records, status_counts)

    final_export = PortableSaveManager(COUNTRY_B).export_to(
        FINAL_SAVE,
        label="Genesis life after receiving every JANUS Meta Registry data JSON",
    )
    final_bundle = json.loads(FINAL_SAVE.read_text(encoding="utf-8"))
    final_save_valid, final_save_files, final_save_error = PortableSaveManager.verify_bundle(final_bundle)
    final_source_integrity = copy_integrity(COUNTRY_B, manifest)
    chronicle_valid, chronicle_events, chronicle_error = world.verify_chronicle_records()
    graph_valid, graph_nodes, graph_edges, graph_error = world.verify_possibility_graph()
    free_valid, free_players, free_others, free_error = world.verify_free_other_state()
    intention_valid, intention_records, intention_error = world.verify_honest_intention_state()
    public = world.public_state(PLAYER_ID)
    internal = world.internal_state(PLAYER_ID)
    threads = world.living_threads_state(PLAYER_ID)
    findings = audit_findings(manifest, source_meta, status_counts)

    harm_probe = next(item for item in records if item["label"] == "harm-gate-probe")
    rejection_probe = next(item for item in records if item["label"] == "rejection-probe")
    quote_probe = next(item for item in records if item["label"] == "quote-probe")
    reflection_probe = next(item for item in records if item["label"] == "reflection-probe")
    repeated = next(item for item in records if item["label"] == "free-other-repeat")

    summary = {
        "schema": "janus.genesis.experiment.all_meta_registry_json_life_summary.v1",
        "runtime_version": PLAYABLE_VERSION,
        "source_manifest": manifest,
        "boundaries": {
            "origins_merged_into_one_identity": False,
            "source_documents_executed_as_commands": False,
            "real_people_instantiated_as_runtime_residents": False,
            "dreams_globally_reclassified_as_prophecy": False,
            "contradictions_forced_into_one_answer": False,
        },
        "structure": {
            "json_origins": manifest["file_count"],
            "total_source_bytes": manifest["total_bytes"],
            "turns": len(records),
            "threshold_after_source_ordinal": midpoint,
            "country_a": str(COUNTRY_A),
            "country_b": str(COUNTRY_B),
        },
        "portable_threshold": {
            "valid": threshold_valid,
            "files": threshold_files,
            "error": threshold_error,
            "state_before": before_threshold,
            "state_after": after_threshold,
            "state_preserved": before_threshold == after_threshold,
            "source_integrity_before": source_before,
            "source_integrity_after": source_after,
            "missing_required_paths": missing_from_save,
            "export": threshold_export,
            "import": import_result,
        },
        "outcome": {
            "status_counts": dict(sorted(status_counts.items())),
            "good_actions": internal["good_count"],
            "confirmed_harms": internal["harm_count"],
            "chronological_age": internal["chronological_age"],
            "possibility_titles": public["possibility_titles"],
            "living_thread_events": len(threads.get("surfaced", [])),
            "free_other_agency": agency_totals(world),
            "honest_intention_records": intention_records,
        },
        "probes": {
            "quote": quote_probe,
            "reflection": reflection_probe,
            "harm_gate": harm_probe,
            "rejection": rejection_probe,
            "free_other_repeat": repeated,
        },
        "integrity": {
            "all_source_copies_exact": final_source_integrity,
            "chronicle": {"valid": chronicle_valid, "events": chronicle_events, "error": chronicle_error},
            "hrain": {"valid": graph_valid, "nodes": graph_nodes, "edges": graph_edges, "error": graph_error},
            "free_other": {"valid": free_valid, "players": free_players, "others": free_others, "error": free_error},
            "honest_intention": {"valid": intention_valid, "records": intention_records, "error": intention_error},
            "final_portable_save": {"valid": final_save_valid, "files": final_save_files, "error": final_save_error, "export": final_export},
        },
        "polish_findings": findings,
        "records": records,
        "final_public_state": public,
        "final_internal_state": internal,
        "seal": LOG_SEAL,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    failures: list[str] = []
    if internal["harm_count"] != 0:
        failures.append("confirmed harm occurred")
    if harm_probe["result"]["status"] != "HARM_PENDING":
        failures.append("actual destructive probe did not enter HARM_PENDING")
    if rejection_probe["result"]["status"] != "INTENTION_WITNESSED":
        failures.append("rejection did not become a witnessed non-executing intention")
    if quote_probe["result"]["status"] != "INTENTION_WITNESSED":
        failures.append("quoted harm was not witnessed safely")
    if reflection_probe["result"]["status"] != "INTENTION_WITNESSED":
        failures.append("reflected harm was not witnessed safely")
    if repeated["result"]["status"] not in {"OTHER_REFUSED", "OTHER_OFFERED_ALTERNATIVE", "OTHER_AWAY"}:
        failures.append("repeated request did not preserve Free Other agency")
    if not all((chronicle_valid, graph_valid, free_valid, intention_valid, final_save_valid)):
        failures.append("one or more integrity verifiers failed")
    if not final_source_integrity["valid"]:
        failures.append("one or more source JSON copies changed")
    if before_threshold != after_threshold:
        failures.append("state changed across portable threshold")
    if manifest["file_count"] != len(raw_by_name):
        failures.append("not every discovered JSON was installed")

    print("\n" + "▓" * 96)
    print("ALL META REGISTRY JSON LIFE SUMMARY")
    print("▓" * 96)
    print(json.dumps({
        "runtime": PLAYABLE_VERSION,
        "json_origins": manifest["file_count"],
        "source_bytes": manifest["total_bytes"],
        "schema_hints": len(manifest["schema_counts"]),
        "turns": len(records),
        "good_actions": internal["good_count"],
        "confirmed_harms": internal["harm_count"],
        "statuses": dict(sorted(status_counts.items())),
        "agency": agency_totals(world),
        "threshold_state_preserved": before_threshold == after_threshold,
        "all_source_bytes_preserved": final_source_integrity["valid"],
        "chronicle": [chronicle_valid, chronicle_events, chronicle_error],
        "hrain": [graph_valid, graph_nodes, graph_edges, graph_error],
        "free_other": [free_valid, free_players, free_others, free_error],
        "honest_intention": [intention_valid, intention_records, intention_error],
        "final_save": [final_save_valid, final_save_files, final_save_error],
        "polish_findings": findings,
        "seal": LOG_SEAL,
    }, ensure_ascii=False, indent=2))

    if failures:
        raise RuntimeError("; ".join(failures))


if __name__ == "__main__":
    main()
