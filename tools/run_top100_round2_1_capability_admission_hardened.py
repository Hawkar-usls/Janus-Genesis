# -*- coding: utf-8 -*-
"""Hardened canonical entrypoint for the Round-2.1 capability admission gate.

The canonical entrypoint reads config, critical reference, and frozen pack into
one byte snapshot, verifies provenance against those exact bytes, parses that
same snapshot, and passes the parsed objects directly to the admission engine.
No second file read is delegated to the historical CLI entrypoint.
"""
from __future__ import annotations

import argparse
import hashlib
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


def _repo_relative(path: Path) -> str:
    """Represent a consumed path in repository-relative POSIX form when possible."""
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def validate_provenance(
    config: dict[str, Any],
    critical: dict[str, Any],
    *,
    config_path: Path,
    critical_path: Path,
    pack_path: Path,
    config_bytes: bytes | None = None,
    critical_bytes: bytes | None = None,
    pack_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Validate declarations against the exact byte snapshot used by execution.

    Callers that already hold a snapshot pass the byte buffers explicitly. The
    optional fallback reads are retained only for focused unit-level validation.
    """
    if config_bytes is None:
        config_bytes = config_path.read_bytes()
    if critical_bytes is None:
        critical_bytes = critical_path.read_bytes()
    if pack_bytes is None:
        pack_bytes = pack_path.read_bytes()

    observed_config_blob = git_blob_sha1_bytes(config_bytes)
    observed_pack_blob = git_blob_sha1_bytes(pack_bytes)
    observed_critical_blob = git_blob_sha1_bytes(critical_bytes)
    observed_pack_path = _repo_relative(pack_path)
    observed_critical_path = _repo_relative(critical_path)

    declared_pack_path = str(config.get("round1_pack") or "")
    declared_critical_path = str(config.get("critical_reference") or "")
    if declared_pack_path != observed_pack_path:
        raise ValueError(
            f"config round1_pack path mismatch: {declared_pack_path!r} != {observed_pack_path!r}"
        )
    if declared_critical_path != observed_critical_path:
        raise ValueError(
            f"config critical_reference path mismatch: {declared_critical_path!r} != {observed_critical_path!r}"
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
        "config_path": _repo_relative(config_path),
        "critical_reference_path": observed_critical_path,
        "round1_pack_path": observed_pack_path,
        "observed_config_git_blob_sha1": observed_config_blob,
        "observed_critical_reference_git_blob_sha1": observed_critical_blob,
        "observed_round1_pack_git_blob_sha1": observed_pack_blob,
        "config_declared_critical_reference_git_blob_sha1": declared_critical_blob,
        "config_declared_round1_pack_git_blob_sha1": declared_pack_blob,
        "critical_source_round1_pack_git_blob_sha1": source_pack_blob,
        "critical_set_canonical_sha256": source_critical_set_hash,
        "receipt_fields_derived_from_verified_declarations": True,
        "single_snapshot_consumption": True,
        "verified_bytes_are_execution_bytes": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--critical-reference", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--docker-image", default="python:3.11-alpine")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)

    # One read per consumed input. The exact same byte buffers are used both for
    # provenance identities and for the parsed objects handed to gate.execute().
    config_bytes = args.config.read_bytes()
    critical_bytes = args.critical_reference.read_bytes()
    pack_bytes = args.pack.read_bytes()

    config = json.loads(config_bytes.decode("utf-8"))
    critical = json.loads(critical_bytes.decode("utf-8"))
    pack = json.loads(pack_bytes.decode("utf-8"))

    provenance = validate_provenance(
        config,
        critical,
        config_path=args.config,
        critical_path=args.critical_reference,
        pack_path=args.pack,
        config_bytes=config_bytes,
        critical_bytes=critical_bytes,
        pack_bytes=pack_bytes,
    )

    report = gate.execute(
        config,
        critical,
        pack,
        endpoint=args.endpoint,
        docker_image=args.docker_image,
        timeout=args.timeout,
    )
    report["provenance_verification"] = provenance
    print(json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=args.pretty,
        indent=2 if args.pretty else None,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
