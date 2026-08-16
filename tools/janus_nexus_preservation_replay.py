# -*- coding: utf-8 -*-
"""Privacy-safe JANUS NEXUS preservation replay v1.

The local replay verifies a complete 44-slot constellation against exact pinned
Git objects through the Nexus materializer. A separate public projection omits
private repository names, exact private commit pins, private tree/file digests,
and whole-Nexus/manifest digests that would fingerprint private material.

A public receipt therefore records that private slots were verified locally but
does *not* pretend to provide public cryptographic proof of their exact pins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.janus_nexus_materializer import (  # noqa: E402
    NexusMaterializer,
    NexusMaterializerError,
    validate_manifest as validate_nexus_manifest,
)

CONSTELLATION_SCHEMA = "janus.genesis.git_habitat.repository_constellation.v1"
PUBLIC_RECEIPT_SCHEMA = "janus.nexus.preservation_public_receipt.v1"
EXPECTED_OWNER = "Hawkar-usls"
EXPECTED_TOTAL = 44
EXPECTED_PUBLIC = 41
EXPECTED_PRIVATE = 3


class PreservationReplayError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreservationReplayError(f"PRESERVATION_JSON_UNREADABLE:{target}") from exc
    if not isinstance(value, dict):
        raise PreservationReplayError(f"PRESERVATION_JSON_OBJECT_REQUIRED:{target}")
    return value


def _write_json(path: str | Path, value: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.parent.is_symlink():
        raise PreservationReplayError("PRESERVATION_OUTPUT_SYMLINK_REJECTED")
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def validate_constellation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != CONSTELLATION_SCHEMA:
        raise PreservationReplayError("PRESERVATION_CONSTELLATION_SCHEMA_INVALID")
    if value.get("inventory_owner") != EXPECTED_OWNER:
        raise PreservationReplayError("PRESERVATION_CONSTELLATION_OWNER_MISMATCH")
    public = value.get("public_repositories")
    private = value.get("private_repository_slots")
    if not isinstance(public, list) or not isinstance(private, list):
        raise PreservationReplayError("PRESERVATION_CONSTELLATION_LISTS_REQUIRED")
    if (
        len(public) != EXPECTED_PUBLIC
        or len(private) != EXPECTED_PRIVATE
        or len(public) + len(private) != EXPECTED_TOTAL
        or value.get("repository_count") != EXPECTED_TOTAL
        or value.get("public_repository_count") != EXPECTED_PUBLIC
        or value.get("private_repository_count") != EXPECTED_PRIVATE
    ):
        raise PreservationReplayError("PRESERVATION_CONSTELLATION_44_SLOT_CONTRACT_INVALID")

    seen: set[str] = set()
    for row in public:
        if not isinstance(row, dict):
            raise PreservationReplayError("PRESERVATION_PUBLIC_ROW_INVALID")
        repo_id = str(row.get("id") or "")
        name = str(row.get("name") or "")
        branch = str(row.get("default_branch") or "")
        if not repo_id.isdigit() or not name or not branch or repo_id in seen:
            raise PreservationReplayError("PRESERVATION_PUBLIC_IDENTITY_INVALID")
        seen.add(repo_id)
    for row in private:
        if not isinstance(row, dict):
            raise PreservationReplayError("PRESERVATION_PRIVATE_SLOT_INVALID")
        repo_id = str(row.get("repository_id") or "")
        if not repo_id.isdigit() or repo_id in seen:
            raise PreservationReplayError("PRESERVATION_PRIVATE_SLOT_ID_INVALID")
        forbidden = {
            "name",
            "full_name",
            "repository",
            "clone_url",
            "html_url",
            "sha",
            "tree_sha256",
            "content",
        }
        if forbidden.intersection(row):
            raise PreservationReplayError("PRESERVATION_PRIVATE_CONSTELLATION_METADATA_LEAK")
        seen.add(repo_id)
    return value


def validate_inventory_binding(
    constellation: dict[str, Any],
    nexus_manifest: dict[str, Any],
) -> dict[str, Any]:
    constellation = validate_constellation(constellation)
    nexus_manifest = validate_nexus_manifest(nexus_manifest)

    expected_ids = [
        str(row["id"]) for row in constellation["public_repositories"]
    ] + [
        str(row["repository_id"])
        for row in constellation["private_repository_slots"]
    ]
    actual_ids = [str(row["repository_id"]) for row in nexus_manifest["sources"]]
    if actual_ids != expected_ids:
        raise PreservationReplayError("PRESERVATION_SOURCE_SET_OR_ORDER_MISMATCH")

    sources = {str(row["repository_id"]): row for row in nexus_manifest["sources"]}
    for row in constellation["public_repositories"]:
        repo_id = str(row["id"])
        source = sources[repo_id]
        if (
            source.get("visibility") != "public"
            or source.get("repository") != f"{EXPECTED_OWNER}/{row['name']}"
            or source.get("branch") != row["default_branch"]
        ):
            raise PreservationReplayError(
                f"PRESERVATION_PUBLIC_BINDING_MISMATCH:{repo_id}"
            )
    for row in constellation["private_repository_slots"]:
        repo_id = str(row["repository_id"])
        source = sources[repo_id]
        if source.get("visibility") != "private":
            raise PreservationReplayError(
                f"PRESERVATION_PRIVATE_BINDING_MISMATCH:{repo_id}"
            )
        forbidden = {"repository", "name", "full_name", "clone_url", "html_url"}
        if forbidden.intersection(source):
            raise PreservationReplayError(
                f"PRESERVATION_PRIVATE_MANIFEST_METADATA_LEAK:{repo_id}"
            )
    return nexus_manifest


class PreservationReplay:
    def __init__(
        self,
        constellation: dict[str, Any],
        nexus_manifest: dict[str, Any],
        sources_root: str | Path,
        nexus_root: str | Path,
    ) -> None:
        self.constellation = validate_constellation(constellation)
        self.nexus_manifest = validate_inventory_binding(
            self.constellation, nexus_manifest
        )
        self.sources_root = Path(sources_root)
        self.nexus_root = Path(nexus_root)

    def _local_replay(self) -> tuple[dict[str, Any], dict[str, Any]]:
        materializer = NexusMaterializer(
            self.nexus_manifest,
            self.sources_root,
            self.nexus_root,
        )
        try:
            verification = materializer.verify()
        except NexusMaterializerError as exc:
            raise PreservationReplayError(
                f"PRESERVATION_LOCAL_REPLAY_ERROR:{exc}"
            ) from exc
        if not verification.get("ok"):
            errors = verification.get("errors") or []
            raise PreservationReplayError(
                "PRESERVATION_LOCAL_REPLAY_FAILED:" + ",".join(map(str, errors))
            )
        nexus_receipt = _read_json(self.nexus_root / "NEXUS_ID.json")
        rows = nexus_receipt.get("sources")
        if not isinstance(rows, list) or len(rows) != EXPECTED_TOTAL:
            raise PreservationReplayError("PRESERVATION_NEXUS_SOURCE_RECEIPTS_INVALID")
        return verification, nexus_receipt

    def public_receipt(self) -> dict[str, Any]:
        _verification, nexus_receipt = self._local_replay()
        by_id = {
            str(row.get("repository_id") or ""): row
            for row in nexus_receipt["sources"]
            if isinstance(row, dict)
        }

        public_sources: list[dict[str, Any]] = []
        for inventory_row in self.constellation["public_repositories"]:
            repo_id = str(inventory_row["id"])
            row = by_id.get(repo_id)
            if row is None:
                raise PreservationReplayError(
                    f"PRESERVATION_PUBLIC_RECEIPT_MISSING:{repo_id}"
                )
            public_sources.append(
                {
                    "repository_id": repo_id,
                    "repository": f"{EXPECTED_OWNER}/{inventory_row['name']}",
                    "branch": inventory_row["default_branch"],
                    "sha": row.get("sha"),
                    "tree_sha256": row.get("tree_sha256"),
                    "tracked_file_count": row.get("tracked_file_count"),
                    "local_exact_pin_verified": True,
                }
            )

        private_slots: list[dict[str, Any]] = []
        for inventory_row in self.constellation["private_repository_slots"]:
            repo_id = str(inventory_row["repository_id"])
            if repo_id not in by_id:
                raise PreservationReplayError(
                    f"PRESERVATION_PRIVATE_RECEIPT_MISSING:{repo_id}"
                )
            private_slots.append(
                {
                    "repository_id": repo_id,
                    "visibility": "private",
                    "local_exact_pin_verified": True,
                    "repository_name_persisted_public": False,
                    "exact_pin_persisted_public": False,
                    "tree_digest_persisted_public": False,
                    "file_digests_persisted_public": False,
                    "private_content_persisted_public": False,
                }
            )

        receipt: dict[str, Any] = {
            "schema": PUBLIC_RECEIPT_SCHEMA,
            "inventory_owner": EXPECTED_OWNER,
            "constellation_manifest_sha256": _sha256_json(self.constellation),
            "repository_count": EXPECTED_TOTAL,
            "public_repository_count": EXPECTED_PUBLIC,
            "private_repository_count": EXPECTED_PRIVATE,
            "public_sources": public_sources,
            "private_repository_slots": private_slots,
            "local_exact_replay_passed": True,
            "source_history_merged": False,
            "source_history_remains_authoritative": True,
            "source_writeback_performed": False,
            "source_code_executed": False,
            "destructive_source_effect_performed": False,
            "nexus_manifest_digest_persisted_public": False,
            "whole_nexus_digest_persisted_public": False,
            "private_exact_pin_public_proof_claimed": False,
            "empirical_owner_wide_replay_promoted": False,
            "public_projection_only": True,
            "authority_delta": 0,
            "mass_effect_budget_delta": 0,
        }
        receipt["public_receipt_digest"] = _sha256_json(receipt)
        self.validate_public_receipt_privacy(receipt)
        return receipt

    @staticmethod
    def validate_public_receipt_privacy(receipt: dict[str, Any]) -> None:
        if receipt.get("schema") != PUBLIC_RECEIPT_SCHEMA:
            raise PreservationReplayError("PRESERVATION_PUBLIC_RECEIPT_SCHEMA_INVALID")
        private_rows = receipt.get("private_repository_slots")
        if not isinstance(private_rows, list) or len(private_rows) != EXPECTED_PRIVATE:
            raise PreservationReplayError("PRESERVATION_PUBLIC_PRIVATE_SLOT_COUNT_INVALID")
        forbidden = {
            "repository",
            "name",
            "full_name",
            "clone_url",
            "html_url",
            "sha",
            "tree_sha256",
            "files",
            "file_digests",
            "content",
        }
        for row in private_rows:
            if not isinstance(row, dict) or forbidden.intersection(row):
                raise PreservationReplayError("PRESERVATION_PUBLIC_PRIVATE_METADATA_LEAK")
            if row.get("exact_pin_persisted_public") is not False:
                raise PreservationReplayError("PRESERVATION_PUBLIC_PRIVATE_PIN_POLICY_INVALID")
            if row.get("tree_digest_persisted_public") is not False:
                raise PreservationReplayError("PRESERVATION_PUBLIC_PRIVATE_TREE_POLICY_INVALID")
            if row.get("file_digests_persisted_public") is not False:
                raise PreservationReplayError("PRESERVATION_PUBLIC_PRIVATE_FILE_POLICY_INVALID")
        for forbidden_top in ("nexus_digest", "manifest_sha256", "nexus_manifest_sha256"):
            if forbidden_top in receipt:
                raise PreservationReplayError(
                    f"PRESERVATION_PUBLIC_PRIVATE_FINGERPRINT_LEAK:{forbidden_top}"
                )
        if receipt.get("whole_nexus_digest_persisted_public") is not False:
            raise PreservationReplayError("PRESERVATION_PUBLIC_WHOLE_NEXUS_POLICY_INVALID")
        if receipt.get("nexus_manifest_digest_persisted_public") is not False:
            raise PreservationReplayError("PRESERVATION_PUBLIC_MANIFEST_POLICY_INVALID")
        if receipt.get("private_exact_pin_public_proof_claimed") is not False:
            raise PreservationReplayError("PRESERVATION_PUBLIC_PRIVATE_PROOF_OVERCLAIM")

    def write_public_receipt(self, path: str | Path) -> dict[str, Any]:
        receipt = self.public_receipt()
        _write_json(path, receipt)
        return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="JANUS NEXUS privacy-safe preservation replay v1"
    )
    parser.add_argument("--constellation", required=True)
    parser.add_argument("--nexus-manifest", required=True)
    parser.add_argument("--sources-root", required=True)
    parser.add_argument("--nexus-root", required=True)
    parser.add_argument("--public-receipt", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    replay = PreservationReplay(
        _read_json(args.constellation),
        _read_json(args.nexus_manifest),
        args.sources_root,
        args.nexus_root,
    )
    receipt = replay.write_public_receipt(args.public_receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
