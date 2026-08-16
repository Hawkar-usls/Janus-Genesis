# -*- coding: utf-8 -*-
"""JANUS NEXUS materializer v1.

Build a disposable, reproducible multi-repository work body from *already local*
Git checkouts pinned to exact commit SHAs. The materializer never clones,
fetches, executes source code, writes to source repositories, or infers authority
from repository content.

Acquisition is deliberately out of scope. An operator/worker may prepare local
checkouts through a separately authorized path, then this module verifies each
checkout HEAD and copies only Git-tracked regular files into the Nexus body.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "janus.nexus.manifest.v1"
RECEIPT_SCHEMA = "janus.nexus.materialization_receipt.v1"
SOURCE_RECEIPT_SCHEMA = "janus.nexus.source_receipt.v1"
SAFE_ID = re.compile(r"^[0-9]{1,32}$")
SAFE_BRANCH = re.compile(r"^[A-Za-z0-9._/+-]{1,240}$")
SAFE_PUBLIC_REPO = re.compile(r"^Hawkar-usls/[A-Za-z0-9._-]{1,200}$")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class NexusMaterializerError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical(value))


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NexusMaterializerError(f"JSON_UNREADABLE:{path}") from exc
    if not isinstance(value, dict):
        raise NexusMaterializerError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or (path.exists() and path.is_symlink()):
        raise NexusMaterializerError("NEXUS_OUTPUT_SYMLINK_REJECTED")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def validate_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != MANIFEST_SCHEMA:
        raise NexusMaterializerError("NEXUS_MANIFEST_SCHEMA_INVALID")
    if value.get("write_back_default") != "DENY":
        raise NexusMaterializerError("NEXUS_WRITE_BACK_MUST_DEFAULT_DENY")
    if value.get("source_code_execution") is not False:
        raise NexusMaterializerError("NEXUS_SOURCE_EXECUTION_MUST_BE_FALSE")
    sources = value.get("sources")
    if not isinstance(sources, list) or not sources:
        raise NexusMaterializerError("NEXUS_MANIFEST_SOURCES_REQUIRED")

    seen_ids: set[str] = set()
    for row in sources:
        if not isinstance(row, dict):
            raise NexusMaterializerError("NEXUS_SOURCE_ROW_INVALID")
        repo_id = str(row.get("repository_id") or "")
        visibility = row.get("visibility")
        branch = str(row.get("branch") or "")
        sha = str(row.get("sha") or "")
        if not SAFE_ID.fullmatch(repo_id) or repo_id in seen_ids:
            raise NexusMaterializerError("NEXUS_SOURCE_REPOSITORY_ID_INVALID")
        if visibility not in {"public", "private"}:
            raise NexusMaterializerError("NEXUS_SOURCE_VISIBILITY_INVALID")
        if not SAFE_BRANCH.fullmatch(branch) or ".." in branch:
            raise NexusMaterializerError("NEXUS_SOURCE_BRANCH_INVALID")
        if not FULL_SHA.fullmatch(sha):
            raise NexusMaterializerError("NEXUS_SOURCE_SHA_INVALID")
        if visibility == "public":
            if not SAFE_PUBLIC_REPO.fullmatch(str(row.get("repository") or "")):
                raise NexusMaterializerError("NEXUS_PUBLIC_REPOSITORY_INVALID")
        else:
            forbidden = {"repository", "name", "full_name", "clone_url", "html_url"}
            if forbidden.intersection(row):
                raise NexusMaterializerError("NEXUS_PRIVATE_REPOSITORY_METADATA_LEAK")
        seen_ids.add(repo_id)
    return value


def load_manifest(path: str | Path) -> dict[str, Any]:
    return validate_manifest(_read_json(Path(path)))


def _git(repo: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise NexusMaterializerError(
            f"NEXUS_GIT_QUERY_FAILED:{repo}:{' '.join(args)}"
        ) from exc


def _checked_relative_path(raw: str) -> Path:
    candidate = Path(raw)
    if not raw or candidate.is_absolute() or ".." in candidate.parts:
        raise NexusMaterializerError("NEXUS_TRACKED_PATH_INVALID")
    if any(part in {"", ".", ".git"} for part in candidate.parts):
        raise NexusMaterializerError("NEXUS_TRACKED_PATH_INVALID")
    return candidate


def _tracked_files(repo: Path) -> list[Path]:
    raw = _git(repo, "ls-files", "-z")
    paths: list[Path] = []
    for item in raw.decode("utf-8", errors="strict").split("\0"):
        if not item:
            continue
        rel = _checked_relative_path(item)
        source = repo / rel
        if source.is_symlink():
            raise NexusMaterializerError(f"NEXUS_SOURCE_SYMLINK_REJECTED:{rel.as_posix()}")
        if not source.is_file():
            raise NexusMaterializerError(f"NEXUS_TRACKED_FILE_INVALID:{rel.as_posix()}")
        paths.append(rel)
    return sorted(paths, key=lambda p: p.as_posix())


def _file_record(path: Path, rel: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": rel.as_posix(),
        "bytes": len(raw),
        "sha256": _sha256_bytes(raw),
    }


def _safe_destination(root: Path, rel: Path) -> Path:
    root_resolved = root.resolve()
    candidate = root / rel
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if candidate.parent.is_symlink() or candidate.is_symlink():
        raise NexusMaterializerError("NEXUS_OUTPUT_SYMLINK_REJECTED")
    parent_resolved = candidate.parent.resolve()
    try:
        parent_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise NexusMaterializerError("NEXUS_OUTPUT_ESCAPE_REJECTED") from exc
    return candidate


class NexusMaterializer:
    def __init__(self, manifest: dict[str, Any], sources_root: str | Path, output_root: str | Path) -> None:
        self.manifest = validate_manifest(manifest)
        self.sources_root = Path(sources_root)
        self.output_root = Path(output_root)
        self.receipt_path = self.output_root / "NEXUS_ID.json"

    @property
    def manifest_sha256(self) -> str:
        return _sha256_json(self.manifest)

    def _source_checkout(self, row: dict[str, Any]) -> Path:
        return self.sources_root / str(row["repository_id"])

    def _verify_checkout_pin(self, row: dict[str, Any], checkout: Path) -> None:
        if not checkout.is_dir() or checkout.is_symlink():
            raise NexusMaterializerError(
                f"NEXUS_SOURCE_CHECKOUT_INVALID:{row['repository_id']}"
            )
        head = _git(checkout, "rev-parse", "HEAD").decode("ascii").strip().lower()
        if head != row["sha"]:
            raise NexusMaterializerError(
                f"NEXUS_SOURCE_SHA_MISMATCH:{row['repository_id']}:{head}"
            )
        tracked_dirty = _git(
            checkout,
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
        )
        if tracked_dirty:
            raise NexusMaterializerError(
                f"NEXUS_SOURCE_TRACKED_WORKTREE_DIRTY:{row['repository_id']}"
            )

    def _body_dir(self, row: dict[str, Any]) -> Path:
        prefix = "public" if row["visibility"] == "public" else "private"
        return self.output_root / "faces" / f"{prefix}-{row['repository_id']}"

    def _source_receipt(self, row: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
        receipt: dict[str, Any] = {
            "schema": SOURCE_RECEIPT_SCHEMA,
            "repository_id": str(row["repository_id"]),
            "visibility": row["visibility"],
            "branch": row["branch"],
            "sha": row["sha"],
            "tracked_file_count": len(files),
            "tree_sha256": _sha256_json(files),
            "files": files,
            "source_history_remains_authoritative": True,
            "source_code_executed": False,
            "write_back_performed": False,
        }
        if row["visibility"] == "public":
            receipt["repository"] = row["repository"]
        return receipt

    def _existing_receipt(self) -> dict[str, Any] | None:
        if not self.receipt_path.exists():
            return None
        return _read_json(self.receipt_path)

    def materialize(self) -> dict[str, Any]:
        existing = self._existing_receipt()
        if existing is not None:
            if existing.get("manifest_sha256") != self.manifest_sha256:
                raise NexusMaterializerError("NEXUS_ALREADY_BOUND_TO_DIFFERENT_MANIFEST")
            verified = self.verify()
            if not verified["ok"]:
                raise NexusMaterializerError("NEXUS_EXISTING_BODY_FAILED_VERIFY")
            return {
                "status": "ALREADY_MATERIALIZED",
                "manifest_sha256": self.manifest_sha256,
                "nexus_digest": existing.get("nexus_digest"),
                "source_count": existing.get("source_count"),
            }

        if self.output_root.exists() and any(self.output_root.iterdir()):
            raise NexusMaterializerError("NEXUS_OUTPUT_NOT_EMPTY")
        self.output_root.mkdir(parents=True, exist_ok=True)

        source_receipts: list[dict[str, Any]] = []
        for row in self.manifest["sources"]:
            checkout = self._source_checkout(row)
            self._verify_checkout_pin(row, checkout)
            tracked = _tracked_files(checkout)
            body_dir = self._body_dir(row)
            body_dir.mkdir(parents=True, exist_ok=False)
            files: list[dict[str, Any]] = []
            for rel in tracked:
                source_path = checkout / rel
                destination = _safe_destination(body_dir, rel)
                shutil.copyfile(source_path, destination)
                files.append(_file_record(destination, rel))
            source_receipt = self._source_receipt(row, files)
            _write_json(body_dir / "SOURCE.json", source_receipt)
            source_receipts.append(source_receipt)

        identity_basis = {
            "schema": RECEIPT_SCHEMA,
            "manifest_sha256": self.manifest_sha256,
            "sources": [
                {
                    "repository_id": r["repository_id"],
                    "sha": r["sha"],
                    "tree_sha256": r["tree_sha256"],
                }
                for r in source_receipts
            ],
        }
        nexus_digest = _sha256_json(identity_basis)
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "manifest_sha256": self.manifest_sha256,
            "nexus_digest": nexus_digest,
            "source_count": len(source_receipts),
            "sources": source_receipts,
            "source_history_merged": False,
            "source_history_remains_authoritative": True,
            "source_code_executed": False,
            "network_access_performed": False,
            "source_write_back_performed": False,
            "write_back_default": "DENY",
            "destructive_action_performed": False,
        }
        _write_json(self.receipt_path, receipt)
        return {
            "status": "MATERIALIZED",
            "manifest_sha256": self.manifest_sha256,
            "nexus_digest": nexus_digest,
            "source_count": len(source_receipts),
            "source_write_back_performed": False,
            "source_code_executed": False,
        }

    def verify(self) -> dict[str, Any]:
        if not self.receipt_path.is_file() or self.receipt_path.is_symlink():
            return {"ok": False, "errors": ["NEXUS_RECEIPT_MISSING"]}
        receipt = _read_json(self.receipt_path)
        errors: list[str] = []
        if receipt.get("schema") != RECEIPT_SCHEMA:
            errors.append("NEXUS_RECEIPT_SCHEMA_INVALID")
        if receipt.get("manifest_sha256") != self.manifest_sha256:
            errors.append("NEXUS_MANIFEST_DIGEST_MISMATCH")
        if receipt.get("write_back_default") != "DENY":
            errors.append("NEXUS_WRITE_BACK_DEFAULT_CHANGED")
        if receipt.get("source_write_back_performed") is not False:
            errors.append("NEXUS_SOURCE_WRITE_BACK_CLAIM_INVALID")
        if receipt.get("source_code_executed") is not False:
            errors.append("NEXUS_SOURCE_EXECUTION_CLAIM_INVALID")

        basis_sources: list[dict[str, Any]] = []
        source_rows = receipt.get("sources")
        if not isinstance(source_rows, list):
            source_rows = []
            errors.append("NEXUS_SOURCE_RECEIPTS_INVALID")
        for row in source_rows:
            repo_id = str(row.get("repository_id") or "")
            visibility = row.get("visibility")
            prefix = "public" if visibility == "public" else "private"
            body_dir = self.output_root / "faces" / f"{prefix}-{repo_id}"
            if body_dir.is_symlink() or not body_dir.is_dir():
                errors.append(f"NEXUS_BODY_DIR_INVALID:{repo_id}")
                continue
            file_rows = row.get("files")
            if not isinstance(file_rows, list):
                errors.append(f"NEXUS_FILE_RECEIPTS_INVALID:{repo_id}")
                continue
            recomputed: list[dict[str, Any]] = []
            for item in file_rows:
                try:
                    rel = _checked_relative_path(str(item.get("path") or ""))
                except NexusMaterializerError:
                    errors.append(f"NEXUS_RECEIPT_PATH_INVALID:{repo_id}")
                    continue
                path = body_dir / rel
                if path.is_symlink() or not path.is_file():
                    errors.append(f"NEXUS_BODY_FILE_MISSING:{repo_id}:{rel.as_posix()}")
                    continue
                recomputed.append(_file_record(path, rel))
            if recomputed != file_rows:
                errors.append(f"NEXUS_BODY_FILE_DIGEST_MISMATCH:{repo_id}")
            tree_sha = _sha256_json(recomputed)
            if tree_sha != row.get("tree_sha256"):
                errors.append(f"NEXUS_TREE_DIGEST_MISMATCH:{repo_id}")
            source_json = body_dir / "SOURCE.json"
            if not source_json.is_file() or source_json.is_symlink():
                errors.append(f"NEXUS_SOURCE_RECEIPT_MISSING:{repo_id}")
            elif visibility == "private":
                private_receipt = _read_json(source_json)
                if any(k in private_receipt for k in ("repository", "name", "full_name", "clone_url", "html_url")):
                    errors.append(f"NEXUS_PRIVATE_METADATA_LEAK:{repo_id}")
            basis_sources.append(
                {
                    "repository_id": repo_id,
                    "sha": row.get("sha"),
                    "tree_sha256": row.get("tree_sha256"),
                }
            )

        basis = {
            "schema": RECEIPT_SCHEMA,
            "manifest_sha256": self.manifest_sha256,
            "sources": basis_sources,
        }
        if _sha256_json(basis) != receipt.get("nexus_digest"):
            errors.append("NEXUS_IDENTITY_DIGEST_MISMATCH")
        return {
            "ok": not errors,
            "source_count": len(source_rows),
            "manifest_sha256": self.manifest_sha256,
            "nexus_digest": receipt.get("nexus_digest"),
            "errors": errors,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS NEXUS offline exact-SHA materializer v1")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--sources-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("command", choices=("materialize", "verify"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    materializer = NexusMaterializer(
        load_manifest(args.manifest), args.sources_root, args.output_root
    )
    result = materializer.materialize() if args.command == "materialize" else materializer.verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
