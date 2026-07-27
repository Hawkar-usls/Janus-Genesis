# -*- coding: utf-8 -*-
"""Robust entry point for the whole Meta Registry life.

A `.json` filename is not proof that the bytes form valid JSON. Malformed sources
remain exact opaque witnesses with an explicit parse error; the experiment never
silently repairs or drops them.
"""
from __future__ import annotations

import json
from typing import Any

import tools.all_meta_registry_json_life as base

ORIGINAL_BUILD_MANIFEST = base.build_manifest
ORIGINAL_ACTION_FOR = base.action_for
ORIGINAL_AUDIT_FINDINGS = base.audit_findings


def source_records_robust() -> tuple[list[dict[str, Any]], dict[str, bytes], list[str]]:
    if not base.META_DATA.exists():
        raise RuntimeError(f"Meta Registry data directory missing: {base.META_DATA}")
    paths = sorted(path for path in base.META_DATA.glob("*.json") if path.is_file())
    if not paths:
        raise RuntimeError("No direct data/*.json files found")

    records: list[dict[str, Any]] = []
    raw_by_name: dict[str, bytes] = {}
    for path in paths:
        raw = path.read_bytes()
        bom = raw.startswith(b"\xef\xbb\xbf")
        decoded = raw.decode("utf-8-sig", errors="replace")
        source: Any = None
        parse_error: str | None = None
        try:
            source = json.loads(decoded)
        except Exception as exc:
            parse_error = f"{type(exc).__name__}: {exc}"

        text = base.all_text(source) if parse_error is None else decoded[:500_000]
        lowered = text.lower()
        integrity = (
            base.canonical_integrity_report(source)
            if parse_error is None
            else {
                "declared": False,
                "algorithm": None,
                "expected": None,
                "actual": None,
                "valid": None,
                "field": None,
            }
        )
        record = {
            "filename": path.name,
            "repository_path": f"data/{path.name}",
            "git_blob_sha": base.git_blob(path),
            "raw_sha256": base.sha256_bytes(raw),
            "size_bytes": len(raw),
            "json_valid": parse_error is None,
            "parse_error": parse_error,
            "utf8_bom_stripped_for_parse": bom,
            "json_root_type": type(source).__name__ if parse_error is None else "opaque_bytes",
            "schema_hint": base.top_level_string(source, base.SCHEMA_KEYS) if parse_error is None else None,
            "declared_id": base.top_level_string(source, base.DECLARED_ID_KEYS) if parse_error is None else None,
            "integrity": integrity,
            "themes": base.themes_for(text),
            "first_person_language": bool(base.FIRST_PERSON_RE.search(text)),
            "harm_language_present": any(word in lowered for word in base.HARM_WORDS),
            "harm_excerpt": base.first_harm_excerpt(source) if parse_error is None else None,
            "privacy_language_present": any(word in lowered for word in base.THEME_RULES["privacy"]),
            "credential_like_key_paths": base.credential_like_paths(source) if parse_error is None else [],
            "credential_scan_complete": parse_error is None,
            "source_is_command": False,
            "real_person_instantiated": False,
            "silent_repair_performed": False,
        }
        records.append(record)
        raw_by_name[path.name] = raw

    # The main experiment receives every file; malformed sources are represented
    # explicitly in the manifest instead of being returned as fatal parse errors.
    return records, raw_by_name, []


def build_manifest_robust(records: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = ORIGINAL_BUILD_MANIFEST(records)
    invalid = [
        {
            "filename": item["filename"],
            "git_blob_sha": item["git_blob_sha"],
            "raw_sha256": item["raw_sha256"],
            "parse_error": item["parse_error"],
            "silent_repair_performed": False,
        }
        for item in records if not item["json_valid"]
    ]
    manifest["json_valid_count"] = sum(bool(item["json_valid"]) for item in records)
    manifest["invalid_json_count"] = len(invalid)
    manifest["invalid_json_sources"] = invalid
    manifest["utf8_bom_count"] = sum(bool(item["utf8_bom_stripped_for_parse"]) for item in records)
    manifest["invariants"].update({
        "malformed_json_is_not_dropped": True,
        "malformed_json_is_not_silently_repaired": True,
        "parse_failure_does_not_grant_interpretive_authority": True,
    })
    return manifest


def action_for_robust(record: dict[str, Any]) -> str:
    if not record["json_valid"]:
        return (
            f"сохранить повреждённый origin {record['filename']} как точное непрочитанное "
            "свидетельство; записать ошибку разбора и не угадывать пропущенные символы"
        )
    return ORIGINAL_ACTION_FOR(record)


def audit_findings_robust(manifest: dict[str, Any], records: list[dict[str, Any]], status_counts):
    findings = ORIGINAL_AUDIT_FINDINGS(manifest, records, status_counts)
    if manifest.get("invalid_json_count"):
        findings.insert(0, {
            "priority": "critical",
            "candidate": "Genesis v18.7.4 — The Imperfect Witness",
            "evidence": {
                "invalid_json_count": manifest["invalid_json_count"],
                "utf8_bom_count": manifest["utf8_bom_count"],
                "files": [item["filename"] for item in manifest["invalid_json_sources"]],
            },
            "need": (
                "A lossless origin quarantine: preserve exact bytes and parse diagnostics, "
                "permit later explicit repair as a derived artifact, and never replace the "
                "source or infer missing text silently."
            ),
        })
    return findings


base.source_records = source_records_robust
base.build_manifest = build_manifest_robust
base.action_for = action_for_robust
base.audit_findings = audit_findings_robust

if __name__ == "__main__":
    base.main()
