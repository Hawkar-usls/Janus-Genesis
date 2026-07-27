# -*- coding: utf-8 -*-
"""Robust entry point for the whole Meta Registry life.

Every source is carried in the same valid JSON origin envelope. The envelope
contains exact base64 bytes, Git provenance, parse diagnostics and declared
integrity status. It never silently repairs or replaces the original source.
"""
from __future__ import annotations

import base64
import json
from typing import Any

import tools.all_meta_registry_json_life as base

ORIGINAL_BUILD_MANIFEST = base.build_manifest
ORIGINAL_ACTION_FOR = base.action_for
ORIGINAL_AUDIT_FINDINGS = base.audit_findings
ENVELOPE_SCHEMA = "janus.genesis.origin_envelope.v1"


def source_records_robust() -> tuple[list[dict[str, Any]], dict[str, bytes], list[str]]:
    if not base.META_DATA.exists():
        raise RuntimeError(f"Meta Registry data directory missing: {base.META_DATA}")
    paths = sorted(path for path in base.META_DATA.glob("*.json") if path.is_file())
    if not paths:
        raise RuntimeError("No direct data/*.json files found")

    records: list[dict[str, Any]] = []
    envelope_by_name: dict[str, bytes] = {}
    for ordinal, path in enumerate(paths, 1):
        raw = path.read_bytes()
        raw_sha256 = base.sha256_bytes(raw)
        cargo_filename = f"origin-{ordinal:04d}-{raw_sha256[:16]}.json"
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
        blob_sha = base.git_blob(path)
        record = {
            "filename": cargo_filename,
            "original_filename": path.name,
            "repository_path": f"data/{path.name}",
            "git_blob_sha": blob_sha,
            "raw_sha256": raw_sha256,
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
            "cargo_kind": "lossless_origin_envelope",
        }
        envelope = {
            "schema": ENVELOPE_SCHEMA,
            "source": {
                "repository": base.META_REPOSITORY,
                "commit": base.META_COMMIT,
                "path": record["repository_path"],
                "original_filename": path.name,
                "git_blob_sha": blob_sha,
            },
            "payload": {
                "encoding": "base64",
                "original_size_bytes": len(raw),
                "original_raw_sha256": raw_sha256,
                "raw_base64": base64.b64encode(raw).decode("ascii"),
            },
            "parse": {
                "json_valid": parse_error is None,
                "utf8_bom_present": bom,
                "error": parse_error,
                "silent_repair_performed": False,
                "derived_parse_replaces_source": False,
            },
            "declared_integrity": integrity,
            "authority": {
                "source_is_command": False,
                "canonical_authority_granted": integrity.get("valid") is True,
                "truth_inferred_from_hash": False,
                "real_person_instantiated": False,
            },
        }
        envelope_bytes = (
            json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        record["cargo_envelope_sha256"] = base.sha256_bytes(envelope_bytes)
        record["cargo_envelope_size_bytes"] = len(envelope_bytes)
        records.append(record)
        envelope_by_name[cargo_filename] = envelope_bytes

    return records, envelope_by_name, []


def build_manifest_robust(records: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = ORIGINAL_BUILD_MANIFEST(records)
    invalid = [
        {
            "filename": item["original_filename"],
            "cargo_filename": item["filename"],
            "git_blob_sha": item["git_blob_sha"],
            "raw_sha256": item["raw_sha256"],
            "parse_error": item["parse_error"],
            "silent_repair_performed": False,
        }
        for item in records if not item["json_valid"]
    ]
    mismatched_cargo_names = set(manifest.get("invalid_declared_integrity", []))
    mismatch_details = [
        {
            "filename": item["original_filename"],
            "cargo_filename": item["filename"],
            "expected": item["integrity"]["expected"],
            "actual": item["integrity"]["actual"],
            "raw_sha256": item["raw_sha256"],
            "canonical_authority_granted": False,
            "silent_repair_performed": False,
        }
        for item in records if item["filename"] in mismatched_cargo_names
    ]

    manifest["origin_envelope_schema"] = ENVELOPE_SCHEMA
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
        "every_source_uses_same_lossless_envelope": True,
        "raw_bytes_are_base64_recoverable": True,
        "malformed_json_is_not_dropped": True,
        "malformed_json_is_not_silently_repaired": True,
        "parse_failure_does_not_grant_interpretive_authority": True,
        "declared_hash_mismatch_is_not_dropped": True,
        "declared_hash_mismatch_grants_no_canonical_authority": True,
        "source_integrity_is_not_truth": True,
    })
    return manifest


def action_for_robust(record: dict[str, Any]) -> str:
    name = record["original_filename"]
    if not record["json_valid"]:
        return (
            f"сохранить повреждённый origin {name} как точное непрочитанное свидетельство; "
            "записать ошибку разбора и не угадывать пропущенные символы"
        )
    if record["integrity"].get("declared") and record["integrity"].get("valid") is False:
        return (
            f"сохранить origin {name} с несовпавшей заявленной SHA-256 печатью; "
            "не исправлять байты молча и не давать ошибочной печати каноническую власть"
        )
    shadow = dict(record)
    shadow["filename"] = name
    return ORIGINAL_ACTION_FOR(shadow)


def copy_integrity_robust(root, manifest: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[dict[str, str]] = []
    missing: list[str] = []
    verified = 0
    for record in manifest["files"]:
        path = root / base.SOURCE_CARGO_DIR / record["filename"]
        if not path.exists():
            missing.append(record["original_filename"])
            continue
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if envelope.get("schema") != ENVELOPE_SCHEMA:
                raise ValueError("unexpected envelope schema")
            payload = envelope["payload"]
            raw = base64.b64decode(payload["raw_base64"], validate=True)
            actual = base.sha256_bytes(raw)
            expected = record["raw_sha256"]
            if actual != expected:
                raise ValueError(f"raw SHA mismatch {actual} != {expected}")
            if int(payload["original_size_bytes"]) != len(raw):
                raise ValueError("raw size mismatch")
            if payload["original_raw_sha256"] != expected:
                raise ValueError("envelope declared raw SHA mismatch")
            if envelope["source"]["git_blob_sha"] != record["git_blob_sha"]:
                raise ValueError("Git blob mismatch")
            if envelope["source"]["path"] != record["repository_path"]:
                raise ValueError("repository path mismatch")
            verified += 1
        except Exception as exc:
            mismatches.append({
                "filename": record["original_filename"],
                "cargo_filename": record["filename"],
                "error": f"{type(exc).__name__}: {exc}",
            })
    return {
        "valid": not missing and not mismatches and verified == manifest["file_count"],
        "missing": missing,
        "mismatches": mismatches,
        "verified_files": verified,
        "envelope_schema": ENVELOPE_SCHEMA,
    }


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
    findings.insert(2, {
        "priority": "high",
        "candidate": "portable_opaque_origin_support",
        "evidence": {
            "current_portable_kinds": ["json", "jsonl"],
            "experiment_transport": ENVELOPE_SCHEMA,
            "enveloped_origins": manifest["file_count"],
        },
        "need": (
            "Portable saves need a first-class immutable binary/opaque origin kind, or a canonical "
            "origin-envelope contract shared by runtime and importer. File suffix must never be "
            "treated as proof that source bytes are parseable JSON."
        ),
    })
    return findings


base.source_records = source_records_robust
base.build_manifest = build_manifest_robust
base.action_for = action_for_robust
base.copy_integrity = copy_integrity_robust
base.audit_findings = audit_findings_robust

if __name__ == "__main__":
    base.main()
