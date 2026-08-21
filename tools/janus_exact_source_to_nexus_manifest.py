#!/usr/bin/env python3
"""Adapt a verified local exact-source manifest into a local Nexus manifest.

This bridge is deliberately local-only. The input exact-source manifest contains
private exact Git pins and the output Nexus manifest also contains those private
pins, so neither artifact belongs in the public evidence plane.

For public sources, repository identity and default-branch provenance come from
the already-public authenticated constellation. For private sources, no branch
or repository identity is disclosed or queried: the required Nexus ``branch``
field receives the explicit non-authoritative sentinel ``PINNED_COMMIT_ONLY``.
Replay authority is the exact commit SHA, not that sentinel.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from janus_exact_source_manifest_freezer import (
    ExactSourceManifestError,
    verify_frozen_manifest,
    write_new_json,
)

NEXUS_SCHEMA = "janus.nexus.manifest.v1"
PRIVATE_BRANCH_SENTINEL = "PINNED_COMMIT_ONLY"
EXPECTED_OWNER = "Hawkar-usls"
EXPECTED_TOTAL = 44
EXPECTED_PUBLIC = 41
EXPECTED_PRIVATE = 3
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
SAFE_BRANCH = re.compile(r"^(?!.*\.\.)[A-Za-z0-9._/+-]{1,240}$")


class ExactSourceToNexusManifestError(RuntimeError):
    """Fail-closed bridge error."""


def _read_json(path: str | Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExactSourceToNexusManifestError(f"{label}_JSON_UNREADABLE") from exc
    if not isinstance(value, dict):
        raise ExactSourceToNexusManifestError(f"{label}_JSON_OBJECT_REQUIRED")
    return value


def _source_index(local_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = local_manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != EXPECTED_TOTAL:
        raise ExactSourceToNexusManifestError("LOCAL_EXACT_MANIFEST_REQUIRES_44_SOURCES")
    index: dict[str, dict[str, Any]] = {}
    for row in sources:
        if not isinstance(row, dict):
            raise ExactSourceToNexusManifestError("LOCAL_EXACT_SOURCE_ROW_INVALID")
        source_id = str(row.get("source_id") or "")
        if not source_id.isdigit() or source_id in index:
            raise ExactSourceToNexusManifestError("LOCAL_EXACT_SOURCE_ID_INVALID")
        pin = row.get("pin")
        if (
            not isinstance(pin, dict)
            or pin.get("kind") != "GIT_COMMIT_SHA1"
            or not FULL_SHA.fullmatch(str(pin.get("value") or ""))
        ):
            raise ExactSourceToNexusManifestError(
                f"LOCAL_EXACT_SOURCE_PIN_INVALID:{source_id}"
            )
        index[source_id] = row
    return index


def adapt_exact_source_manifest(
    local_manifest: dict[str, Any],
    constellation: dict[str, Any],
    *,
    artifact_id: str,
) -> dict[str, Any]:
    """Return one sensitive local Nexus manifest bound to exact commit pins."""
    if not isinstance(artifact_id, str) or not 1 <= len(artifact_id) <= 200:
        raise ExactSourceToNexusManifestError("ARTIFACT_ID_INVALID")

    try:
        frozen = verify_frozen_manifest(local_manifest, constellation)
    except ExactSourceManifestError as exc:
        raise ExactSourceToNexusManifestError(
            f"LOCAL_EXACT_MANIFEST_VERIFY_FAILED:{exc}"
        ) from exc

    public = constellation.get("public_repositories")
    private = constellation.get("private_repository_slots")
    if (
        not isinstance(public, list)
        or not isinstance(private, list)
        or len(public) != EXPECTED_PUBLIC
        or len(private) != EXPECTED_PRIVATE
        or len(public) + len(private) != EXPECTED_TOTAL
    ):
        raise ExactSourceToNexusManifestError("CONSTELLATION_44_SLOT_CONTRACT_INVALID")

    index = _source_index(frozen)
    rows: list[dict[str, Any]] = []

    for inventory_row in public:
        if not isinstance(inventory_row, dict):
            raise ExactSourceToNexusManifestError("PUBLIC_CONSTELLATION_ROW_INVALID")
        source_id = str(inventory_row.get("id") or "")
        name = str(inventory_row.get("name") or "")
        branch = str(inventory_row.get("default_branch") or "")
        if not source_id.isdigit() or not name or not SAFE_BRANCH.fullmatch(branch):
            raise ExactSourceToNexusManifestError(
                f"PUBLIC_CONSTELLATION_IDENTITY_INVALID:{source_id}"
            )
        source = index.get(source_id)
        if source is None or source.get("visibility") != "public":
            raise ExactSourceToNexusManifestError(
                f"PUBLIC_SOURCE_BINDING_MISMATCH:{source_id}"
            )
        rows.append(
            {
                "repository_id": source_id,
                "visibility": "public",
                "repository": f"{EXPECTED_OWNER}/{name}",
                "branch": branch,
                "sha": source["pin"]["value"],
            }
        )

    for inventory_row in private:
        if not isinstance(inventory_row, dict):
            raise ExactSourceToNexusManifestError("PRIVATE_CONSTELLATION_ROW_INVALID")
        source_id = str(inventory_row.get("repository_id") or "")
        if (
            not source_id.isdigit()
            or inventory_row.get("visibility") != "private"
            or inventory_row.get("resolution") != "AUTHENTICATED_RESOLUTION_REQUIRED"
        ):
            raise ExactSourceToNexusManifestError(
                f"PRIVATE_CONSTELLATION_IDENTITY_INVALID:{source_id}"
            )
        source = index.get(source_id)
        if source is None or source.get("visibility") != "private":
            raise ExactSourceToNexusManifestError(
                f"PRIVATE_SOURCE_BINDING_MISMATCH:{source_id}"
            )
        rows.append(
            {
                "repository_id": source_id,
                "visibility": "private",
                "branch": PRIVATE_BRANCH_SENTINEL,
                "sha": source["pin"]["value"],
            }
        )

    if len(rows) != EXPECTED_TOTAL or len({row["repository_id"] for row in rows}) != EXPECTED_TOTAL:
        raise ExactSourceToNexusManifestError("NEXUS_SOURCE_ACCOUNTING_INVALID")

    candidate = {
        "schema": NEXUS_SCHEMA,
        "artifact_id": artifact_id,
        "write_back_default": "DENY",
        "source_code_execution": False,
        "sources": rows,
    }
    validate_adapted_manifest(candidate)
    return candidate


def validate_adapted_manifest(value: Any) -> dict[str, Any]:
    """Validate the bridge-owned subset before handing it to the materializer."""
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "artifact_id",
        "write_back_default",
        "source_code_execution",
        "sources",
    }:
        raise ExactSourceToNexusManifestError("NEXUS_MANIFEST_FIELDS_INVALID")
    if value.get("schema") != NEXUS_SCHEMA:
        raise ExactSourceToNexusManifestError("NEXUS_MANIFEST_SCHEMA_INVALID")
    if value.get("write_back_default") != "DENY" or value.get("source_code_execution") is not False:
        raise ExactSourceToNexusManifestError("NEXUS_MANIFEST_AUTHORITY_BOUNDARY_INVALID")
    sources = value.get("sources")
    if not isinstance(sources, list) or len(sources) != EXPECTED_TOTAL:
        raise ExactSourceToNexusManifestError("NEXUS_MANIFEST_REQUIRES_44_SOURCES")

    public_count = 0
    private_count = 0
    seen: set[str] = set()
    for row in sources:
        if not isinstance(row, dict):
            raise ExactSourceToNexusManifestError("NEXUS_SOURCE_ROW_INVALID")
        source_id = str(row.get("repository_id") or "")
        if not source_id.isdigit() or source_id in seen:
            raise ExactSourceToNexusManifestError("NEXUS_SOURCE_ID_INVALID")
        seen.add(source_id)
        if not FULL_SHA.fullmatch(str(row.get("sha") or "")):
            raise ExactSourceToNexusManifestError(f"NEXUS_SOURCE_SHA_INVALID:{source_id}")
        visibility = row.get("visibility")
        if visibility == "public":
            public_count += 1
            if set(row) != {"repository_id", "visibility", "repository", "branch", "sha"}:
                raise ExactSourceToNexusManifestError(
                    f"NEXUS_PUBLIC_SOURCE_FIELDS_INVALID:{source_id}"
                )
            if not str(row.get("repository") or "").startswith(f"{EXPECTED_OWNER}/"):
                raise ExactSourceToNexusManifestError(
                    f"NEXUS_PUBLIC_REPOSITORY_INVALID:{source_id}"
                )
            if not SAFE_BRANCH.fullmatch(str(row.get("branch") or "")):
                raise ExactSourceToNexusManifestError(
                    f"NEXUS_PUBLIC_BRANCH_INVALID:{source_id}"
                )
        elif visibility == "private":
            private_count += 1
            if set(row) != {"repository_id", "visibility", "branch", "sha"}:
                raise ExactSourceToNexusManifestError(
                    f"NEXUS_PRIVATE_SOURCE_FIELDS_INVALID:{source_id}"
                )
            if row.get("branch") != PRIVATE_BRANCH_SENTINEL:
                raise ExactSourceToNexusManifestError(
                    f"NEXUS_PRIVATE_BRANCH_SENTINEL_INVALID:{source_id}"
                )
        else:
            raise ExactSourceToNexusManifestError(
                f"NEXUS_SOURCE_VISIBILITY_INVALID:{source_id}"
            )

    if public_count != EXPECTED_PUBLIC or private_count != EXPECTED_PRIVATE:
        raise ExactSourceToNexusManifestError("NEXUS_VISIBILITY_ACCOUNTING_INVALID")
    return value


def adapt_and_write(
    local_manifest: dict[str, Any],
    constellation: dict[str, Any],
    output_path: str | Path,
    *,
    artifact_id: str,
) -> dict[str, Any]:
    candidate = adapt_exact_source_manifest(
        local_manifest,
        constellation,
        artifact_id=artifact_id,
    )
    try:
        write_new_json(Path(output_path), candidate, mode=0o600)
    except Exception as exc:
        raise ExactSourceToNexusManifestError(
            f"SENSITIVE_NEXUS_MANIFEST_WRITE_FAILED:{type(exc).__name__}"
        ) from exc
    return {
        "status": "LOCAL_SENSITIVE_NEXUS_MANIFEST_WRITTEN",
        "source_count": EXPECTED_TOTAL,
        "public_source_count": EXPECTED_PUBLIC,
        "private_source_count": EXPECTED_PRIVATE,
        "private_branch_field_is_non_authoritative_sentinel": True,
        "private_branch_sentinel": PRIVATE_BRANCH_SENTINEL,
        "private_repository_identity_published": False,
        "private_exact_pin_printed": False,
        "network_acquisition_performed": False,
        "source_writeback_performed": False,
        "source_code_execution_performed": False,
        "authority_delta": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="JANUS exact-source to local Nexus manifest adapter v1"
    )
    parser.add_argument("--local-exact-manifest", required=True)
    parser.add_argument("--constellation", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = adapt_and_write(
            _read_json(args.local_exact_manifest, label="LOCAL_EXACT_MANIFEST"),
            _read_json(args.constellation, label="CONSTELLATION"),
            args.output,
            artifact_id=args.artifact_id,
        )
    except ExactSourceToNexusManifestError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "private_exact_pin_printed": False,
                    "network_acquisition_performed": False,
                    "source_writeback_performed": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
