# -*- coding: utf-8 -*-
"""JANUS Git Habitat repository constellation v18.7.59.

Materialize the owner's repository inventory as a bounded Habitat extension.
Repositories remain independent sources with their own histories. This module
creates references/bookmarks and handoff endpoints; it does not clone every
repository, execute repository code, create issues/PRs, dispatch workflows, or
write back to source repositories.

Private repository names are intentionally absent from the public constellation
manifest. Private slots are bound by opaque GitHub repository id and require an
authenticated resolver at use time. No credential or private repository content
is persisted by this materializer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

from tools.genesis_git_habitat import GitHabitat, _read_json

CONSTELLATION_VERSION = "18.7.59"
CONSTELLATION_SCHEMA = "janus.genesis.git_habitat.repository_constellation.v1"
CATALOG_SCHEMA = "janus.genesis.git_habitat.repository_catalog.v1"
PUBLIC_LINK_SCHEMA = "janus.genesis.git_habitat.repository_bookmark.v1"
PRIVATE_SLOT_SCHEMA = "janus.genesis.git_habitat.private_repository_slot.v1"
SOURCE_LINK_SCHEMA = "janus.genesis.git_habitat.repository_link.v1"
DEFAULT_MANIFEST = ROOT / "protocol" / "JANUS_GENESIS_GIT_HABITAT_REPOSITORY_CONSTELLATION-v1.0.json"
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,200}$")


class RepositoryConstellationError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or (path.exists() and path.is_symlink()):
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_SYMLINK_REJECTED")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_MANIFEST_UNREADABLE") from exc
    validate_manifest(value)
    return value


def validate_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != CONSTELLATION_SCHEMA:
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_SCHEMA_INVALID")
    owner = str(value.get("inventory_owner") or "").strip()
    if owner != "Hawkar-usls":
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_OWNER_MISMATCH")
    public = value.get("public_repositories")
    private = value.get("private_repository_slots")
    if not isinstance(public, list) or not isinstance(private, list):
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_LISTS_REQUIRED")

    ids: set[str] = set()
    names: set[str] = set()
    for row in public:
        if not isinstance(row, dict):
            raise RepositoryConstellationError("PUBLIC_REPOSITORY_ROW_INVALID")
        repo_id = str(row.get("id") or "")
        name = str(row.get("name") or "")
        branch = str(row.get("default_branch") or "")
        if not repo_id.isdigit() or not SAFE_NAME.fullmatch(name) or not branch:
            raise RepositoryConstellationError("PUBLIC_REPOSITORY_IDENTITY_INVALID")
        if repo_id in ids or name.lower() in names:
            raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_DUPLICATE_PUBLIC_IDENTITY")
        ids.add(repo_id)
        names.add(name.lower())

    for row in private:
        if not isinstance(row, dict):
            raise RepositoryConstellationError("PRIVATE_REPOSITORY_SLOT_INVALID")
        repo_id = str(row.get("repository_id") or "")
        if not repo_id.isdigit() or repo_id in ids:
            raise RepositoryConstellationError("PRIVATE_REPOSITORY_SLOT_ID_INVALID")
        # The public artifact may bind an opaque id, but never persist private
        # name/full_name/clone URL or content.
        forbidden = {"name", "full_name", "clone_url", "html_url", "content", "description"}
        if forbidden.intersection(row):
            raise RepositoryConstellationError("PRIVATE_REPOSITORY_METADATA_PUBLIC_LEAK")
        if row.get("resolution") != "AUTHENTICATED_RESOLUTION_REQUIRED":
            raise RepositoryConstellationError("PRIVATE_REPOSITORY_MUST_REQUIRE_AUTHENTICATED_RESOLUTION")
        ids.add(repo_id)

    total = len(public) + len(private)
    if int(value.get("repository_count", -1)) != total:
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_TOTAL_COUNT_MISMATCH")
    if int(value.get("public_repository_count", -1)) != len(public):
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_PUBLIC_COUNT_MISMATCH")
    if int(value.get("private_repository_count", -1)) != len(private):
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_PRIVATE_COUNT_MISMATCH")
    if value.get("integration_mode") != "REFERENCE_INDEX_AND_HANDOFF_ONLY":
        raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_MODE_INVALID")
    return value


def source_repository_link_record() -> dict[str, Any]:
    """The identical marker that may be placed inside every source repository."""
    return {
        "schema": SOURCE_LINK_SCHEMA,
        "link_id": "JANUS_GIT_HABITAT_LINK",
        "source_repository": "SELF",
        "target": {
            "repository": "Hawkar-usls/Janus_Genesis",
            "branch": "janus/habitat",
            "room": "repositories",
            "constellation_protocol": "protocol/JANUS_GENESIS_GIT_HABITAT_REPOSITORY_CONSTELLATION-v1.0.json",
        },
        "mode": "REFERENCE_AND_HANDOFF_ONLY",
        "source_history_remains_authoritative": True,
        "source_code_execution_implied": False,
        "habitat_command_authority_granted": False,
        "write_back_default": "DENY",
        "write_back_requires_explicit_human_authorization": True,
        "issue_or_pr_text_is_command": False,
        "workflow_status_is_permission": False,
        "private_content_may_be_mirrored_to_public_habitat": False,
        "credentials_may_be_persisted_in_habitat": False,
    }


class RepositoryConstellationMaterializer:
    def __init__(self, habitat: GitHabitat, manifest: dict[str, Any]) -> None:
        self.habitat = habitat
        self.manifest = validate_manifest(manifest)
        self.room = self.habitat.paths.root / "repositories"
        self.catalog_path = self.room / "CONSTELLATION.json"

    @property
    def manifest_digest(self) -> str:
        return _sha256(self.manifest)

    def _public_record(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": PUBLIC_LINK_SCHEMA,
            "constellation_version": CONSTELLATION_VERSION,
            "repository_id": str(row["id"]),
            "repository": f"Hawkar-usls/{row['name']}",
            "visibility": "public",
            "default_branch": str(row["default_branch"]),
            "relationship": "HABITAT_REFERENCE",
            "source_history_remains_authoritative": True,
            "content_is_trusted_fact_by_default": False,
            "read_or_index_is_write_permission": False,
            "write_back_default": "DENY",
            "external_effect_authority": False,
        }

    def _private_record(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": PRIVATE_SLOT_SCHEMA,
            "constellation_version": CONSTELLATION_VERSION,
            "repository_id": str(row["repository_id"]),
            "visibility": "private",
            "relationship": "HABITAT_REFERENCE_OPAQUE_SLOT",
            "resolution": "AUTHENTICATED_RESOLUTION_REQUIRED",
            "repository_name_persisted": False,
            "private_content_persisted": False,
            "credentials_persisted": False,
            "write_back_default": "DENY",
            "external_effect_authority": False,
        }

    def materialize(self) -> dict[str, Any]:
        self.habitat._require_initialized()
        if self.room.exists() and self.room.is_symlink():
            raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_ROOM_MAY_NOT_BE_SYMLINK")
        self.room.mkdir(parents=True, exist_ok=True)

        if self.catalog_path.exists():
            existing = _read_json(self.catalog_path)
            if existing.get("manifest_sha256") != self.manifest_digest:
                raise RepositoryConstellationError(
                    "REPOSITORY_CONSTELLATION_ALREADY_BOUND_TO_DIFFERENT_MANIFEST"
                )
            return {
                "status": "ALREADY_CONNECTED",
                "repository_count": existing.get("repository_count"),
                "manifest_sha256": self.manifest_digest,
                "write_back_default": "DENY",
            }

        public_dir = self.room / "public"
        private_dir = self.room / "private-slots"
        public_dir.mkdir(parents=True, exist_ok=True)
        private_dir.mkdir(parents=True, exist_ok=True)
        if public_dir.is_symlink() or private_dir.is_symlink():
            raise RepositoryConstellationError("REPOSITORY_CONSTELLATION_CHILD_ROOM_MAY_NOT_BE_SYMLINK")

        public_index: list[dict[str, Any]] = []
        for row in self.manifest["public_repositories"]:
            record = self._public_record(row)
            path = public_dir / str(row["id"]) / "LINK.json"
            _write_json(path, record)
            public_index.append({
                "repository_id": record["repository_id"],
                "repository": record["repository"],
                "default_branch": record["default_branch"],
                "link": str(path.relative_to(self.habitat.paths.root)),
            })

        private_index: list[dict[str, Any]] = []
        for row in self.manifest["private_repository_slots"]:
            record = self._private_record(row)
            path = private_dir / str(row["repository_id"]) / "LINK.json"
            _write_json(path, record)
            private_index.append({
                "repository_id": record["repository_id"],
                "resolution": record["resolution"],
                "link": str(path.relative_to(self.habitat.paths.root)),
                "repository_name_persisted": False,
            })

        catalog = {
            "schema": CATALOG_SCHEMA,
            "constellation_version": CONSTELLATION_VERSION,
            "inventory_owner": self.manifest["inventory_owner"],
            "inventory_as_of": self.manifest["inventory_as_of"],
            "manifest_sha256": self.manifest_digest,
            "repository_count": len(public_index) + len(private_index),
            "public_repository_count": len(public_index),
            "private_repository_count": len(private_index),
            "public_repositories": public_index,
            "private_repository_slots": private_index,
            "write_back_default": "DENY",
            "automatic_external_effects": False,
            "private_repository_names_persisted": False,
            "credentials_persisted": False,
        }
        _write_json(self.catalog_path, catalog)

        home = _read_json(self.habitat.paths.home)
        extensions = home.setdefault("extensions", {})
        if not isinstance(extensions, dict):
            raise RepositoryConstellationError("HABITAT_HOME_EXTENSIONS_INVALID")
        extensions["repository_constellation"] = {
            "version": CONSTELLATION_VERSION,
            "room": "repositories",
            "catalog": "repositories/CONSTELLATION.json",
            "repository_count": catalog["repository_count"],
            "manifest_sha256": self.manifest_digest,
            "write_back_default": "DENY",
            "private_repository_names_persisted": False,
        }
        _write_json(self.habitat.paths.home, home)

        self.habitat._append_event(
            "REPOSITORY_CONSTELLATION_CONNECTED",
            self.habitat._active_cycle_or_none(),
            {
                "repository_count": catalog["repository_count"],
                "public_repository_count": catalog["public_repository_count"],
                "private_repository_count": catalog["private_repository_count"],
                "manifest_sha256": self.manifest_digest,
                "write_back_default": "DENY",
            },
        )
        health = self.habitat.refresh_health()
        return {
            "status": "CONNECTED",
            "repository_count": catalog["repository_count"],
            "public_repository_count": catalog["public_repository_count"],
            "private_repository_count": catalog["private_repository_count"],
            "manifest_sha256": self.manifest_digest,
            "habitat_health": health["status"],
            "write_back_default": "DENY",
            "external_effect_authority": False,
        }

    def verify(self) -> dict[str, Any]:
        self.habitat._require_initialized()
        if not self.catalog_path.exists():
            return {"ok": False, "error": "CONSTELLATION_NOT_MATERIALIZED"}
        catalog = _read_json(self.catalog_path)
        errors: list[str] = []
        if catalog.get("schema") != CATALOG_SCHEMA:
            errors.append("CATALOG_SCHEMA_MISMATCH")
        if catalog.get("manifest_sha256") != self.manifest_digest:
            errors.append("MANIFEST_DIGEST_MISMATCH")
        if catalog.get("repository_count") != self.manifest.get("repository_count"):
            errors.append("REPOSITORY_COUNT_MISMATCH")
        if catalog.get("write_back_default") != "DENY":
            errors.append("WRITE_BACK_DEFAULT_NOT_DENY")
        for row in catalog.get("public_repositories", []):
            path = self.habitat.paths.root / str(row.get("link") or "")
            if not path.is_file() or path.is_symlink():
                errors.append(f"PUBLIC_LINK_INVALID:{row.get('repository_id')}")
        for row in catalog.get("private_repository_slots", []):
            path = self.habitat.paths.root / str(row.get("link") or "")
            if not path.is_file() or path.is_symlink():
                errors.append(f"PRIVATE_SLOT_INVALID:{row.get('repository_id')}")
            elif any(key in _read_json(path) for key in ("name", "full_name", "clone_url", "content")):
                errors.append(f"PRIVATE_SLOT_METADATA_LEAK:{row.get('repository_id')}")
        journal = self.habitat.verify_journal()
        if not journal["ok"]:
            errors.append("HABITAT_JOURNAL_INVALID")
        return {
            "ok": not errors,
            "repository_count": catalog.get("repository_count"),
            "public_repository_count": catalog.get("public_repository_count"),
            "private_repository_count": catalog.get("private_repository_count"),
            "journal_chain_ok": journal["ok"],
            "write_back_default": catalog.get("write_back_default"),
            "errors": errors,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JANUS Git Habitat repository constellation v18.7.59")
    parser.add_argument("--root", default="habitat")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("materialize")
    sub.add_parser("verify")
    sub.add_parser("source-link")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "source-link":
        print(json.dumps(source_repository_link_record(), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    habitat = GitHabitat(args.root)
    manifest = load_manifest(args.manifest)
    extension = RepositoryConstellationMaterializer(habitat, manifest)
    result = extension.materialize() if args.command == "materialize" else extension.verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("ok", True) else 2


REPOSITORY_CONSTELLATION_LAW_V18_7_59 = {
    "complete_authenticated_inventory_snapshot_count": 44,
    "public_repository_count": 41,
    "private_repository_count": 3,
    "source_repository_history_remains_authoritative": True,
    "repository_content_is_command": False,
    "repository_content_is_trusted_fact_by_default": False,
    "read_or_index_is_write_permission": False,
    "private_repository_names_persisted_in_public_manifest": False,
    "private_resolution_requires_authenticated_access": True,
    "write_back_default_deny": True,
    "automatic_issue_creation": False,
    "automatic_pull_request_creation": False,
    "automatic_workflow_dispatch": False,
    "automatic_public_outreach": False,
    "external_effect_authority_delta": 0,
}


if __name__ == "__main__":
    raise SystemExit(main())
