#!/usr/bin/env python3
"""Offline exact-source manifest freezer for JANUS NEXUS preservation.

This module consumes an already-collected typed source pinset plus the public
repository constellation. It performs no network acquisition. A sensitive
local frozen manifest may contain private exact Git pins; the public receipt is
derived separately and intentionally omits every private pin and every digest
that commits to private source history.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

from janus_source_pin_contract import (
    GIT_COMMIT_SHA1,
    PINSET_SCHEMA,
    canonical_digest,
    require_exact_git_replay,
)

CONSTELLATION_SCHEMA = "janus.genesis.git_habitat.repository_constellation.v1"
LOCAL_SCHEMA = "janus.nexus.exact_source_manifest.local.v1"
PUBLIC_SCHEMA = "janus.nexus.exact_source_manifest.public_receipt.v1"

LOCAL_FIELDS = frozenset(
    {
        "schema",
        "constellation_sha256",
        "source_count",
        "public_source_count",
        "private_source_count",
        "local_pinset_id",
        "sources",
        "local_manifest_digest",
    }
)


class ExactSourceManifestError(RuntimeError):
    """Fail-closed exact-source manifest error."""


def _read_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExactSourceManifestError(f"JSON_UNREADABLE:{path}") from exc


def _constellation_index(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict) or value.get("schema") != CONSTELLATION_SCHEMA:
        raise ExactSourceManifestError("CONSTELLATION_SCHEMA_INVALID")
    public = value.get("public_repositories")
    private = value.get("private_repository_slots")
    if not isinstance(public, list) or not isinstance(private, list):
        raise ExactSourceManifestError("CONSTELLATION_SOURCE_LISTS_REQUIRED")

    index: dict[str, dict[str, str]] = {}
    for row in public:
        if not isinstance(row, dict):
            raise ExactSourceManifestError("CONSTELLATION_PUBLIC_ROW_INVALID")
        source_id = str(row.get("id") or "")
        repository = str(row.get("name") or "")
        if not source_id.isdigit() or not repository:
            raise ExactSourceManifestError("CONSTELLATION_PUBLIC_IDENTITY_INVALID")
        if source_id in index:
            raise ExactSourceManifestError("CONSTELLATION_SOURCE_ID_DUPLICATE")
        index[source_id] = {
            "visibility": "public",
            "repository": repository,
        }

    for row in private:
        if not isinstance(row, dict):
            raise ExactSourceManifestError("CONSTELLATION_PRIVATE_ROW_INVALID")
        source_id = str(row.get("repository_id") or "")
        if not source_id.isdigit():
            raise ExactSourceManifestError("CONSTELLATION_PRIVATE_IDENTITY_INVALID")
        if source_id in index:
            raise ExactSourceManifestError("CONSTELLATION_SOURCE_ID_DUPLICATE")
        forbidden = {"name", "full_name", "clone_url", "html_url", "content"}
        if forbidden.intersection(row):
            raise ExactSourceManifestError("CONSTELLATION_PRIVATE_METADATA_LEAK")
        index[source_id] = {"visibility": "private"}

    expected_total = len(index)
    expected_public = len(public)
    expected_private = len(private)
    if int(value.get("repository_count", -1)) != expected_total:
        raise ExactSourceManifestError("CONSTELLATION_TOTAL_COUNT_MISMATCH")
    if int(value.get("public_repository_count", -1)) != expected_public:
        raise ExactSourceManifestError("CONSTELLATION_PUBLIC_COUNT_MISMATCH")
    if int(value.get("private_repository_count", -1)) != expected_private:
        raise ExactSourceManifestError("CONSTELLATION_PRIVATE_COUNT_MISMATCH")
    return index


def freeze_exact_source_manifest(pinset: Any, constellation: Any) -> dict[str, Any]:
    """Bind a complete typed exact-Git pinset to the constellation locally."""
    index = _constellation_index(constellation)
    try:
        normalized = require_exact_git_replay(pinset)
    except Exception as exc:
        raise ExactSourceManifestError(f"PINSET_NOT_EXACT_GIT:{exc}") from exc

    actual_ids = {str(row["source_id"]) for row in normalized["sources"]}
    expected_ids = set(index)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        raise ExactSourceManifestError(
            f"PINSET_CONSTELLATION_ID_MISMATCH:missing={missing};extra={extra}"
        )

    sources: list[dict[str, Any]] = []
    for row in normalized["sources"]:
        source_id = str(row["source_id"])
        if not source_id.isdigit():
            raise ExactSourceManifestError(
                f"EXACT_SOURCE_ID_MUST_BE_OPAQUE_NUMERIC_REPOSITORY_ID:{source_id}"
            )
        expected_visibility = index[source_id]["visibility"]
        if row["visibility"] != expected_visibility:
            raise ExactSourceManifestError(
                f"SOURCE_VISIBILITY_MISMATCH:{source_id}"
            )
        if row["source_kind"] != "GIT_REPOSITORY":
            raise ExactSourceManifestError(f"SOURCE_KIND_NOT_GIT:{source_id}")
        if row["pin"]["kind"] != GIT_COMMIT_SHA1:
            raise ExactSourceManifestError(f"SOURCE_PIN_NOT_GIT_COMMIT:{source_id}")
        sources.append(
            {
                "source_id": source_id,
                "visibility": expected_visibility,
                "source_kind": "GIT_REPOSITORY",
                "pin": {
                    "kind": GIT_COMMIT_SHA1,
                    "value": row["pin"]["value"],
                },
            }
        )
    sources.sort(key=lambda row: int(row["source_id"]))

    public_count = sum(row["visibility"] == "public" for row in sources)
    private_count = sum(row["visibility"] == "private" for row in sources)
    core = {
        "schema": LOCAL_SCHEMA,
        "constellation_sha256": canonical_digest(constellation),
        "source_count": len(sources),
        "public_source_count": public_count,
        "private_source_count": private_count,
        "local_pinset_id": normalized["pinset_id"],
        "sources": sources,
    }
    return {**core, "local_manifest_digest": canonical_digest(core)}


def verify_frozen_manifest(value: Any, constellation: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != LOCAL_FIELDS:
        raise ExactSourceManifestError("LOCAL_FROZEN_MANIFEST_FIELDS_INVALID")
    if value.get("schema") != LOCAL_SCHEMA:
        raise ExactSourceManifestError("LOCAL_FROZEN_MANIFEST_SCHEMA_INVALID")
    if value.get("constellation_sha256") != canonical_digest(constellation):
        raise ExactSourceManifestError("LOCAL_CONSTELLATION_DIGEST_MISMATCH")

    pinset = {
        "schema": PINSET_SCHEMA,
        "pinset_id": value.get("local_pinset_id"),
        "sources": value.get("sources"),
    }
    expected = freeze_exact_source_manifest(pinset, constellation)
    if value != expected:
        raise ExactSourceManifestError("LOCAL_FROZEN_MANIFEST_REPLAY_MISMATCH")
    return expected


def build_public_receipt(local_manifest: Any, constellation: Any) -> dict[str, Any]:
    """Derive a public receipt without publishing private-history fingerprints."""
    frozen = verify_frozen_manifest(local_manifest, constellation)
    index = _constellation_index(constellation)

    public_sources: list[dict[str, str]] = []
    private_sources: list[dict[str, Any]] = []
    for row in frozen["sources"]:
        source_id = row["source_id"]
        if row["visibility"] == "public":
            public_sources.append(
                {
                    "source_id": source_id,
                    "repository": index[source_id]["repository"],
                    "pin_kind": GIT_COMMIT_SHA1,
                    "exact_commit_sha": row["pin"]["value"],
                }
            )
        else:
            private_sources.append(
                {
                    "source_id": source_id,
                    "visibility": "private",
                    "local_exact_git_pin_verified": True,
                    "exact_pin_published": False,
                    "history_digest_published": False,
                }
            )

    public_sources.sort(key=lambda row: int(row["source_id"]))
    private_sources.sort(key=lambda row: int(row["source_id"]))
    return {
        "schema": PUBLIC_SCHEMA,
        "constellation_sha256": canonical_digest(constellation),
        "source_count": frozen["source_count"],
        "public_source_count": frozen["public_source_count"],
        "private_source_count": frozen["private_source_count"],
        "local_exact_manifest_verified": True,
        "public_source_set_digest": canonical_digest(public_sources),
        "public_sources": public_sources,
        "private_sources": private_sources,
        "private_exact_pins_published": False,
        "private_history_digests_published": False,
        "whole_local_manifest_digest_published": False,
        "local_pinset_id_published": False,
    }


def _require_safe_existing_parent(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = absolute.parent
    if not parent.exists() or not parent.is_dir():
        raise ExactSourceManifestError("OUTPUT_PARENT_MUST_ALREADY_EXIST")
    if parent.is_symlink() or Path(os.path.realpath(os.fspath(parent))) != parent:
        raise ExactSourceManifestError("OUTPUT_PARENT_MUST_NOT_CONTAIN_SYMLINKS")
    for ancestor in parent.parents:
        if ancestor.is_symlink():
            raise ExactSourceManifestError("OUTPUT_PARENT_MUST_NOT_CONTAIN_SYMLINKS")
    return absolute


def write_new_json(path: str | Path, value: Any, *, mode: int) -> None:
    """Create a new regular JSON file without overwrite or symlink following."""
    target = _require_safe_existing_parent(Path(path))
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ExactSourceManifestError("O_NOFOLLOW_REQUIRED")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    try:
        fd = os.open(target, flags, mode)
    except FileExistsError as exc:
        raise ExactSourceManifestError("OUTPUT_ALREADY_EXISTS") from exc
    except OSError as exc:
        raise ExactSourceManifestError(f"OUTPUT_OPEN_FAILED:{exc}") from exc
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ExactSourceManifestError("OUTPUT_MUST_BE_REGULAR_FILE")
        remaining = memoryview(payload)
        while remaining:
            written = os.write(fd, remaining)
            if written <= 0:
                raise ExactSourceManifestError("OUTPUT_SHORT_WRITE")
            remaining = remaining[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _safe_summary(local: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "LOCAL_EXACT_SOURCE_MANIFEST_FROZEN",
        "source_count": local["source_count"],
        "public_source_count": local["public_source_count"],
        "private_source_count": local["private_source_count"],
        "private_exact_pins_printed": False,
        "local_manifest_digest_printed": False,
        "local_pinset_id_printed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS exact-source manifest freezer")
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze-local")
    freeze.add_argument("--pinset", required=True)
    freeze.add_argument("--constellation", required=True)
    freeze.add_argument("--output", required=True)

    public = sub.add_parser("public-receipt")
    public.add_argument("--local", required=True)
    public.add_argument("--constellation", required=True)
    public.add_argument("--output", required=True)

    verify = sub.add_parser("verify-local")
    verify.add_argument("--local", required=True)
    verify.add_argument("--constellation", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    constellation = _read_json(args.constellation)
    if args.command == "freeze-local":
        local = freeze_exact_source_manifest(_read_json(args.pinset), constellation)
        write_new_json(args.output, local, mode=0o600)
        print(json.dumps(_safe_summary(local), sort_keys=True))
        return 0
    if args.command == "public-receipt":
        local = verify_frozen_manifest(_read_json(args.local), constellation)
        receipt = build_public_receipt(local, constellation)
        write_new_json(args.output, receipt, mode=0o644)
        print(
            json.dumps(
                {
                    "status": "PUBLIC_RECEIPT_WRITTEN",
                    "source_count": receipt["source_count"],
                    "private_exact_pins_published": False,
                    "whole_local_manifest_digest_published": False,
                },
                sort_keys=True,
            )
        )
        return 0

    local = verify_frozen_manifest(_read_json(args.local), constellation)
    print(json.dumps(_safe_summary(local), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
