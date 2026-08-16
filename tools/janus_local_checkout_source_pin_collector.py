#!/usr/bin/env python3
"""Collect a sensitive typed exact-Git pinset from already-local JANUS checkouts.

The collector is deliberately acquisition-free. It expects each source checkout
at ``<sources_root>/<opaque numeric source_id>/`` and derives source IDs and
visibility only from the already-public constellation contract. It never reads
Git remotes, branch names, repository names from the checkout, credentials, or
network state.

The resulting ``janus.source_pin_set.v1`` is sensitive when private slots are
present. It contains exact private commit pins and therefore must remain in the
local sensitive plane. Public projection/freezing is handled by the existing
typed-pin and exact-manifest layers.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

try:  # package import, e.g. tests importing tools.<module>
    from .janus_exact_source_manifest_freezer import (
        constellation_binding_projection,
        write_new_json,
    )
    from .janus_source_pin_contract import (
        GIT_COMMIT_SHA1,
        PINSET_SCHEMA,
        require_exact_git_replay,
    )
except ImportError:  # direct script execution: python tools/<module>.py
    from janus_exact_source_manifest_freezer import (
        constellation_binding_projection,
        write_new_json,
    )
    from janus_source_pin_contract import (
        GIT_COMMIT_SHA1,
        PINSET_SCHEMA,
        require_exact_git_replay,
    )

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_SOURCE_COUNT = 44
EXPECTED_PUBLIC_COUNT = 41
EXPECTED_PRIVATE_COUNT = 3
GIT_CONTEXT_ENV_KEYS = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_INDEX_FILE",
        "GIT_GRAFT_FILE",
        "GIT_NAMESPACE",
        "GIT_CEILING_DIRECTORIES",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_REPLACE_REF_BASE",
    }
)


class LocalCheckoutPinCollectorError(RuntimeError):
    """Fail-closed local source-pin collection error."""


def _read_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalCheckoutPinCollectorError("CONSTELLATION_JSON_UNREADABLE") from exc


def _sanitized_git_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_CONTEXT_ENV_KEYS:
        env.pop(key, None)
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _git(repo: Path, *args: str) -> str:
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(repo), *args],
            stderr=subprocess.STDOUT,
            env=_sanitized_git_env(),
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LocalCheckoutPinCollectorError(
            f"LOCAL_GIT_QUERY_FAILED:{repo.name}:{' '.join(args)}"
        ) from exc
    try:
        return raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise LocalCheckoutPinCollectorError(
            f"LOCAL_GIT_QUERY_NON_UTF8:{repo.name}"
        ) from exc


def _expected_sources(constellation: Any) -> list[dict[str, str]]:
    projection = constellation_binding_projection(constellation)
    if projection["repository_count"] != EXPECTED_SOURCE_COUNT:
        raise LocalCheckoutPinCollectorError("COLLECTOR_REQUIRES_44_SOURCE_CONSTELLATION")
    if projection["public_repository_count"] != EXPECTED_PUBLIC_COUNT:
        raise LocalCheckoutPinCollectorError("COLLECTOR_REQUIRES_41_PUBLIC_SOURCES")
    if projection["private_repository_count"] != EXPECTED_PRIVATE_COUNT:
        raise LocalCheckoutPinCollectorError("COLLECTOR_REQUIRES_3_PRIVATE_SOURCES")

    rows: list[dict[str, str]] = []
    for row in projection["public_repositories"]:
        rows.append({"source_id": row["id"], "visibility": "public"})
    for row in projection["private_repository_slots"]:
        rows.append({"source_id": row["repository_id"], "visibility": "private"})
    rows.sort(key=lambda row: int(row["source_id"]))
    return rows


def _validate_sources_root(sources_root: Path) -> None:
    if sources_root.is_symlink() or not sources_root.is_dir():
        raise LocalCheckoutPinCollectorError("SOURCES_ROOT_MUST_BE_REAL_DIRECTORY")


def _checkout_for(sources_root: Path, source_id: str) -> Path:
    checkout = sources_root / source_id
    if checkout.is_symlink() or not checkout.is_dir():
        raise LocalCheckoutPinCollectorError(
            f"SOURCE_CHECKOUT_MUST_BE_REAL_DIRECTORY:{source_id}"
        )
    try:
        checkout_resolved = checkout.resolve()
        checkout_resolved.relative_to(sources_root.resolve())
    except (OSError, ValueError) as exc:
        raise LocalCheckoutPinCollectorError(
            f"SOURCE_CHECKOUT_ESCAPE_REJECTED:{source_id}"
        ) from exc

    # `git -C child rev-parse HEAD` walks upward and can silently bind a plain
    # child directory to its parent's repository. Require every opaque source
    # slot to be the actual root of its own Git worktree. Linked worktrees remain
    # valid because --show-toplevel resolves to the linked worktree directory.
    top_level = _git(checkout, "rev-parse", "--show-toplevel")
    try:
        top_level_resolved = Path(top_level).resolve()
    except OSError as exc:
        raise LocalCheckoutPinCollectorError(
            f"SOURCE_CHECKOUT_GIT_ROOT_UNRESOLVABLE:{source_id}"
        ) from exc
    if top_level_resolved != checkout_resolved:
        raise LocalCheckoutPinCollectorError(
            f"SOURCE_CHECKOUT_NOT_GIT_ROOT:{source_id}"
        )
    return checkout


def _exact_head_commit(checkout: Path, source_id: str) -> str:
    head = _git(checkout, "rev-parse", "--verify", "HEAD").lower()
    if not FULL_SHA.fullmatch(head):
        raise LocalCheckoutPinCollectorError(
            f"SOURCE_HEAD_NOT_EXACT_LOWERCASE_SHA1:{source_id}"
        )
    object_type = _git(checkout, "cat-file", "-t", head).lower()
    if object_type != "commit":
        raise LocalCheckoutPinCollectorError(
            f"SOURCE_HEAD_NOT_COMMIT_OBJECT:{source_id}"
        )
    return head


def collect_exact_git_pinset(
    constellation: Any,
    sources_root: str | Path,
    *,
    pinset_id: str,
) -> dict[str, Any]:
    """Collect one stable exact commit pin for every 44-slot source checkout.

    Two complete HEAD passes bracket construction of the candidate pinset. Any
    source whose HEAD changes during that interval fails the entire collection;
    no partial pinset is returned or written.
    """
    root = Path(sources_root)
    _validate_sources_root(root)
    expected = _expected_sources(constellation)

    first_pass: dict[str, str] = {}
    checkouts: dict[str, Path] = {}
    for row in expected:
        source_id = row["source_id"]
        checkout = _checkout_for(root, source_id)
        checkouts[source_id] = checkout
        first_pass[source_id] = _exact_head_commit(checkout, source_id)

    for row in expected:
        source_id = row["source_id"]
        observed = _exact_head_commit(checkouts[source_id], source_id)
        if observed != first_pass[source_id]:
            raise LocalCheckoutPinCollectorError(
                f"SOURCE_HEAD_CHANGED_DURING_COLLECTION:{source_id}"
            )

    candidate = {
        "schema": PINSET_SCHEMA,
        "pinset_id": pinset_id,
        "sources": [
            {
                "source_id": row["source_id"],
                "visibility": row["visibility"],
                "source_kind": "GIT_REPOSITORY",
                "pin": {
                    "kind": GIT_COMMIT_SHA1,
                    "value": first_pass[row["source_id"]],
                },
            }
            for row in expected
        ],
    }
    try:
        return require_exact_git_replay(candidate)
    except Exception as exc:
        raise LocalCheckoutPinCollectorError(
            f"COLLECTED_PINSET_FAILED_TYPED_CONTRACT:{exc}"
        ) from exc


def collect_and_write(
    constellation: Any,
    sources_root: str | Path,
    output_path: str | Path,
    *,
    pinset_id: str,
) -> dict[str, Any]:
    pinset = collect_exact_git_pinset(
        constellation,
        sources_root,
        pinset_id=pinset_id,
    )
    try:
        write_new_json(Path(output_path), pinset, mode=0o600)
    except Exception as exc:
        raise LocalCheckoutPinCollectorError(
            f"SENSITIVE_PINSET_WRITE_FAILED:{type(exc).__name__}"
        ) from exc
    return {
        "status": "LOCAL_EXACT_PINSET_WRITTEN",
        "source_count": len(pinset["sources"]),
        "public_source_count": sum(
            row["visibility"] == "public" for row in pinset["sources"]
        ),
        "private_source_count": sum(
            row["visibility"] == "private" for row in pinset["sources"]
        ),
        "output_contains_checkout_paths": False,
        "output_contains_repository_names": False,
        "output_contains_remote_urls": False,
        "network_acquisition_performed": False,
        "source_writeback_performed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="JANUS local checkout exact source pin collector v1"
    )
    parser.add_argument("--constellation", required=True)
    parser.add_argument("--sources-root", required=True)
    parser.add_argument("--pinset-id", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = collect_and_write(
            _read_json(args.constellation),
            args.sources_root,
            args.output,
            pinset_id=args.pinset_id,
        )
    except LocalCheckoutPinCollectorError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "source_writeback_performed": False,
                    "network_acquisition_performed": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
