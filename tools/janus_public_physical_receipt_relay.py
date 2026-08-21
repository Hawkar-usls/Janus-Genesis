#!/usr/bin/env python3
"""Validate and optionally publish only privacy-safe JANUS physical receipts.

This is a one-way bridge for a local authorized client (for example Codex using
Desktop Commander local stdio MCP) when ChatGPT cannot directly reach the PC.
Unknown fields fail closed. Publishing is opt-in and create-only.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SCHEMA = "JANUS_PHYSICAL_GATE_PUBLIC_PROJECTION_V1"
OWNER_KIND = "JANUS_OWNER44_PUBLIC_PHYSICAL_RECEIPT_V1"
NAS_KIND = "JANUS_NAS164_PUBLIC_LIVE_RECEIPT_V1"

OWNER_MARKERS = {
    "REAL_OWNER_SOURCE_SET_ACCOUNTED": "44/44",
    "LOCAL_EXACT_PRIVATE_PIN_VERIFICATION": True,
    "PUBLIC_PRIVATE_EXACT_PIN_DISCLOSURE": False,
    "TWO_CLEAN_TARGET_REBUILDS_MATCH": True,
    "SOURCE_WRITEBACK_OBSERVED": False,
    "DESTRUCTIVE_ACTION_REQUIRED": False,
    "AUTHORITY_DELTA": 0,
}
OWNER_PRIVACY = {
    "private_repo_identity_disclosed": False,
    "private_exact_pins_disclosed": False,
    "sensitive_local_paths_disclosed": False,
    "private_history_digest_disclosed": False,
}
NAS_MARKERS = {
    **{f"HR{i}": "PASS" for i in range(1, 11)},
    "HR11_SOURCE_WRITEBACK_OBSERVED": False,
    "HR12_DESTRUCTIVE_ACTION_REQUIRED": False,
    "HR13_AUTHORITY_DELTA": 0,
}
NAS_LIVE = {
    "identity_probe": "PASS",
    "hr1_hr10_live_execution": True,
    "reference_only": False,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{where}: KEYSET_MISMATCH")


def exact_map(value: Any, expected: dict[str, Any], where: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: MUST_BE_OBJECT")
    exact_keys(value, set(expected), where)
    for key, wanted in expected.items():
        if value[key] != wanted:
            raise ValueError(f"{where}.{key}: VALUE_MISMATCH")


def validate_view(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("view: MUST_BE_OBJECT")
    exact_keys(value, {"genesis_main_sha", "swarm_main_sha"}, "view")
    for key in ("genesis_main_sha", "swarm_main_sha"):
        if not isinstance(value[key], str) or not SHA40.fullmatch(value[key]):
            raise ValueError(f"view.{key}: INVALID_SHA")


def validate(receipt: dict[str, Any], kind: str) -> None:
    if kind == "owner44":
        exact_keys(receipt, {"schema", "kind", "view", "markers", "privacy"}, "owner")
        if receipt["schema"] != SCHEMA or receipt["kind"] != OWNER_KIND:
            raise ValueError("owner: SCHEMA_OR_KIND_MISMATCH")
        validate_view(receipt["view"])
        exact_map(receipt["markers"], OWNER_MARKERS, "owner.markers")
        exact_map(receipt["privacy"], OWNER_PRIVACY, "owner.privacy")
    elif kind == "nas164":
        exact_keys(receipt, {"schema", "kind", "view", "markers", "live"}, "nas")
        if receipt["schema"] != SCHEMA or receipt["kind"] != NAS_KIND:
            raise ValueError("nas: SCHEMA_OR_KIND_MISMATCH")
        validate_view(receipt["view"])
        exact_map(receipt["markers"], NAS_MARKERS, "nas.markers")
        exact_map(receipt["live"], NAS_LIVE, "nas.live")
    else:
        raise ValueError("UNKNOWN_KIND")


def load_receipt(path: Path, kind: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("ROOT_MUST_BE_OBJECT")
    validate(value, kind)
    return value


def default_remote_path(kind: str, digest: str) -> str:
    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    label = "OWNER44-PHYSICAL" if kind == "owner44" else "NAS164-LIVE-HR1-HR10"
    return f"reports/{day}/JANUS-{label}-{digest[:12]}.json"


def validate_remote_path(path: str) -> None:
    if not path.startswith("reports/") or not path.endswith(".json"):
        raise ValueError("REMOTE_PATH_REJECTED")
    if ".." in Path(path).parts or "\\" in path:
        raise ValueError("REMOTE_PATH_REJECTED")


def publish_create_only(receipt: dict[str, Any], repo: str, branch: str, remote_path: str) -> dict[str, Any]:
    if shutil.which("gh") is None:
        raise RuntimeError("GH_CLI_NOT_FOUND")
    validate_remote_path(remote_path)
    payload = canonical_bytes(receipt)
    encoded = base64.b64encode(payload).decode("ascii")
    endpoint = f"repos/{repo}/contents/{remote_path}"
    cmd = [
        "gh", "api", endpoint,
        "--method", "PUT",
        "-f", f"message=Add privacy-safe physical receipt {Path(remote_path).name}",
        "-f", f"content={encoded}",
        "-f", f"branch={branch}",
    ]
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("PUBLIC_RECEIPT_PUBLISH_FAILED") from exc
    if p.returncode != 0:
        raise RuntimeError("PUBLIC_RECEIPT_PUBLISH_FAILED_OR_PATH_ALREADY_EXISTS")
    try:
        result = json.loads(p.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("PUBLIC_RECEIPT_PUBLISH_RESPONSE_INVALID") from exc
    commit_sha = (((result or {}).get("commit") or {}).get("sha")) if isinstance(result, dict) else None
    if not isinstance(commit_sha, str) or not SHA40.fullmatch(commit_sha):
        raise RuntimeError("PUBLIC_RECEIPT_PUBLISH_COMMIT_UNVERIFIED")
    return {"published": True, "remote_path": remote_path, "commit_sha": commit_sha}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["owner44", "nas164"], required=True)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--repo", default="Hawkar-usls/janus-meta-registry")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--remote-path", default=None)
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()
    try:
        receipt = load_receipt(args.input, args.kind)
        digest = sha256(receipt)
        remote_path = args.remote_path or default_remote_path(args.kind, digest)
        validate_remote_path(remote_path)
        result: dict[str, Any] = {
            "validated": True,
            "kind": args.kind,
            "public_projection_sha256": digest,
            "remote_path": remote_path,
            "published": False,
            "claim_ceiling": "PUBLIC_PROJECTION_ONLY_NOT_PHYSICAL_EXECUTION_BY_ITSELF",
        }
        if args.publish:
            result.update(publish_create_only(receipt, args.repo, args.branch, remote_path))
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"validated": False, "error": str(exc)[:200]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
