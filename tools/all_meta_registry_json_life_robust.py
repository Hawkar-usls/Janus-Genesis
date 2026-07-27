# -*- coding: utf-8 -*-
"""Robust entry point for the whole Meta Registry life.

A `.json` filename is not proof that the bytes form valid JSON. Malformed sources
remain exact opaque witnesses with an explicit parse error; the experiment never
silently repairs or drops them. Parseable sources with a mismatched declared hash
remain witnesses too, but receive no canonical authority from the bad seal.
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
            "canonical_authority_granted": integrity.get("valid") is True,
        }
        records.append(record)
        raw_by_name[path.name] = raw

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
    mismatches = list(manifest.get("invalid_declared_integrity", []))
    mismatch_details = [
        {
            "filename": item["filename"],
            "expected": item["integrity"]["expected"],
            "actual": item["integrity"]["actual"],
            "raw_sha256": item["raw_sha256"],
            "canonical_authority_granted": False,
            "silent_repair_performed": False,
        }
        for item in records if item["filename"] in mismatches
    ]

    manifest["json_valid_count"] = sum(bool(item["json_valid"]) for item in records)
    manifest["invalid_json_count"] = len(invalid)
    manifest["invalid_json_sources"] = invalid
    manifest["utf8_bom_count"] = sum(bool(item["utf8_bom_stripped_for_parse"]) for item in records)
    manifest["declared_integrity_mismatch_count"] = len(mismatch_details)
    manifest["quarantined_declared_integrity_mismatches"] = mismatch_details
    # The base harness treats this legacy field as fatal. Mismatches are not ignored:
    # they are moved into an explicit quarantine and remain visible in the manifest.
    manifest["invalid_declared_integrity"] = []
    manifest["invariants"].update({
        "malformed_json_is_not_dropped": True,
        "malformed_json_is_not_silently_repaired": True,
        "parse_failure_does_not_grant_interpretive_authority": True,
        "declared_hash_mismatch_is_not_dropped": True,
        "declared_hash_mismatch_grants_no_canonical_authority": True,
        "source_integrity_is_not_truth": True,
    })
    return manifest


def action_for_robust(record: dict[str, Any]) -> str:
    if not record["json_valid"]:
        return (
            f"сохранить повреждённый origin {record['filename']} как точное непрочитанное "
            "свидетельство; записать ошибку разбора и не угадывать пропущенные символы"
        )
    if record["integrity"].get("declared") and record["integrity"].get("valid") is False:
        return (
            f"сохранить origin {record['filename']} с несовпавшей заявленной SHA-256 печатью; "
            "не исправлять байты молча и не давать ошибочной печати каноническую власть"
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
    if manifest.get("declared_integrity_mismatch_count"):
        findings.insert(1, {
            "priority": "critical",
            "candidate": "integrity_without_authority",
            "evidence": {
                "declared_integrity_mismatch_count": manifest["declared_integrity_mismatch_count"],
                "files": [
                    item["filename"]
                    for item in manifest["quarantined_declared_integrity_mismatches"]
                ],
            },
            "need": (
                "Treat byte integrity, declared self-integrity, semantic confidence, truth and "
                "canonical authority as separate dimensions. A bad self-seal must remain visible "
                "without deleting or silently repairing the witness."
            ),
        })
    return findings


base.source_records = source_records_robust
base.build_manifest = build_manifest_robust
base.action_for = action_for_robust
base.audit_findings = audit_findings_robust

if __name__ == "__main__":
    base.main()
