# -*- coding: utf-8 -*-
"""Scope audit for JANUS Git Habitat repository constellation v18.7.59."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "protocol" / "JANUS_GENESIS_GIT_HABITAT_REPOSITORY_CONSTELLATION-v1.0.json"
TOOL = ROOT / "tools" / "genesis_git_habitat_repository_constellation.py"
SOURCE_LINK = ROOT / ".janus" / "HABITAT_LINK.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tool = TOOL.read_text(encoding="utf-8")
    source_link = json.loads(SOURCE_LINK.read_text(encoding="utf-8"))
    public = manifest.get("public_repositories", [])
    private = manifest.get("private_repository_slots", [])
    private_forbidden = {"name", "full_name", "clone_url", "html_url", "content", "description"}
    checks = {
        "complete_snapshot_count_44": manifest.get("repository_count") == 44,
        "public_count_41": manifest.get("public_repository_count") == 41 and len(public) == 41,
        "private_count_3": manifest.get("private_repository_count") == 3 and len(private) == 3,
        "all_ids_unique": len({
            *[str(row.get("id")) for row in public],
            *[str(row.get("repository_id")) for row in private],
        }) == 44,
        "private_names_absent_from_public_manifest_rows": all(
            not private_forbidden.intersection(row) for row in private if isinstance(row, dict)
        ),
        "private_resolution_requires_authentication": all(
            row.get("resolution") == "AUTHENTICATED_RESOLUTION_REQUIRED" for row in private
        ),
        "write_back_default_deny_manifest": manifest.get("source_repository_link_contract", {}).get("write_back_default") == "DENY",
        "materializer_has_no_network_client": all(
            marker not in tool for marker in ("urllib.request", "requests.", "http.client", "socket.")
        ),
        "materializer_has_no_git_writeback": all(
            marker not in tool for marker in ("git push", "create_pull_request", "create_issue", "workflow_dispatch")
        ),
        "source_link_denies_writeback": source_link.get("write_back_default") == "DENY",
        "source_link_requires_human_writeback_authorization": source_link.get("write_back_requires_explicit_human_authorization") is True,
        "source_link_grants_no_command_authority": source_link.get("habitat_command_authority_granted") is False,
        "source_link_grants_no_private_public_mirror": source_link.get("private_content_may_be_mirrored_to_public_habitat") is False,
    }
    ok = all(checks.values())
    report = {
        "schema": "janus.genesis.git_habitat.repository_constellation_audit.v18_7_59",
        "runtime_version": "18.7.59",
        "checks": checks,
        "scope_pass": ok,
        "repository_count": 44,
        "public_repository_count": 41,
        "private_repository_count": 3,
        "canonical_laws": [
            "REPOSITORY_LINK != COMMAND_AUTHORITY",
            "READ_OR_INDEX != WRITE_BACK_PERMISSION",
            "PRIVATE_REPOSITORY_NAME != PUBLIC_CONSTELLATION_METADATA",
            "WRITE_BACK_DEFAULT = DENY",
            "SOURCE_HISTORY_REMAINS_AUTHORITATIVE",
            "REPOSITORY_CHANGE != AUTOMATIC_WORLD_EFFECT"
        ],
        "repository_wide_source_marker_presence_proven_by_this_audit": False,
        "source_marker_rollout_requires_separate_cross_repository_verification": True,
        "claim_ceiling": "This source audit verifies the central 44-node constellation contract, private-name non-disclosure, and default-deny write-back semantics. It does not by itself prove that every source repository already contains the reciprocal .janus/HABITAT_LINK.json marker; that is a separate cross-repository rollout check."
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
