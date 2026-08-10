# -*- coding: utf-8 -*-
"""Hardened canonical entrypoint for the Round-2.1 capability admission gate.

This wrapper verifies that provenance declared in the admission config matches
bytes actually consumed by the run before delegating inference to the Round-2.1
runner.  It also emits the observed Git-blob identities into the final receipt.

The historical runner remains a reusable implementation module; this wrapper is
the canonical CI entrypoint for admission evidence.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

from tools import run_top100_round2_1_capability_admission as gate


PROVENANCE_STATUS = "VERIFIED_AGAINST_ACTUAL_CONSUMED_BYTES"


def git_blob_sha1_bytes(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def git_blob_sha1(path: Path) -> str:
    return git_blob_sha1_bytes(path.read_bytes())


def validate_provenance(
    config: dict[str, Any],
    critical: dict[str, Any],
    *,
    config_path: Path,
    critical_path: Path,
    pack_path: Path,
) -> dict[str, Any]:
    observed_pack_blob = git_blob_sha1(pack_path)
    observed_critical_blob = git_blob_sha1(critical_path)

    declared_pack_path = str(config.get("round1_pack") or "")
    declared_critical_path = str(config.get("critical_reference") or "")
    if declared_pack_path != pack_path.as_posix():
        raise ValueError(
            f"config round1_pack path mismatch: {declared_pack_path!r} != {pack_path.as_posix()!r}"
        )
    if declared_critical_path != critical_path.as_posix():
        raise ValueError(
            f"config critical_reference path mismatch: {declared_critical_path!r} != {critical_path.as_posix()!r}"
        )

    declared_pack_blob = str(config.get("round1_pack_git_blob_sha1") or "")
    declared_critical_blob = str(config.get("critical_reference_git_blob_sha1") or "")
    if declared_pack_blob != observed_pack_blob:
        raise ValueError(
            f"config round1 pack blob mismatch: {declared_pack_blob} != {observed_pack_blob}"
        )
    if declared_critical_blob != observed_critical_blob:
        raise ValueError(
            f"config critical reference blob mismatch: {declared_critical_blob} != {observed_critical_blob}"
        )

    source = critical.get("source")
    if not isinstance(source, dict):
        raise ValueError("critical reference source must be an object")
    source_pack_path = str(source.get("round1_pack_path") or "")
    source_pack_blob = str(source.get("round1_pack_git_blob_sha1") or "")
    if source_pack_path != declared_pack_path:
        raise ValueError(
            f"critical source round1 pack path mismatch: {source_pack_path!r} != {declared_pack_path!r}"
        )
    if source_pack_blob != observed_pack_blob:
        raise ValueError(
            f"critical source round1 pack blob mismatch: {source_pack_blob} != {observed_pack_blob}"
        )

    declared_critical_set_hash = str(config.get("critical_set_canonical_sha256") or "")
    source_critical_set_hash = str(critical.get("critical_set_canonical_sha256") or "")
    if declared_critical_set_hash != source_critical_set_hash:
        raise ValueError(
            "config and critical reference disagree on critical_set_canonical_sha256"
        )

    return {
        "status": PROVENANCE_STATUS,
        "config_path": config_path.as_posix(),
        "critical_reference_path": critical_path.as_posix(),
        "round1_pack_path": pack_path.as_posix(),
        "observed_critical_reference_git_blob_sha1": observed_critical_blob,
        "observed_round1_pack_git_blob_sha1": observed_pack_blob,
        "config_declared_critical_reference_git_blob_sha1": declared_critical_blob,
        "config_declared_round1_pack_git_blob_sha1": declared_pack_blob,
        "critical_source_round1_pack_git_blob_sha1": source_pack_blob,
        "critical_set_canonical_sha256": source_critical_set_hash,
        "receipt_fields_derived_from_verified_declarations": True,
    }


def _paths_from_argv(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--critical-reference", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    known, rest = parser.parse_known_args(argv)
    return known, rest


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    paths, _ = _paths_from_argv(raw_argv)
    config = json.loads(paths.config.read_text(encoding="utf-8"))
    critical = json.loads(paths.critical_reference.read_text(encoding="utf-8"))
    provenance = validate_provenance(
        config,
        critical,
        config_path=paths.config,
        critical_path=paths.critical_reference,
        pack_path=paths.pack,
    )

    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        rc = gate.main(raw_argv)
    if rc != 0:
        return rc
    report = json.loads(capture.getvalue())
    report["provenance_verification"] = provenance
    pretty = "--pretty" in raw_argv
    print(json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=pretty,
        indent=2 if pretty else None,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
