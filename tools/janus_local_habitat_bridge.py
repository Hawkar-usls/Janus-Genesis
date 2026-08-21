#!/usr/bin/env python3
"""JANUS local Habitat bridge for Codex/Desktop Commander/Ollama.

This helper deliberately does not provide arbitrary remote execution. It creates
and verifies a local append-only Habitat journal, exposes a privacy-safe doctor,
can opt-in to registering Desktop Commander as a *local stdio MCP* in Codex,
and can probe only loopback Ollama.

Authority boundaries:
  SOURCE_WRITEBACK_DEFAULT=DENY
  DESTRUCTIVE_ACTION=FORBIDDEN
  AUTHORITY_DELTA=0

The script never scans Git repositories, never reads Git remotes, never acquires
source repositories, and never publishes local/private identities or exact pins.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA = "JANUS_LOCAL_HABITAT_V1"
IDENTITY_SCHEMA = "JANUS_LOCAL_HABITAT_IDENTITY_V1"
RESIDENT_ID = "JANUS"
GENESIS_EXPECTED = "227d42d6848790031916cac53d39961a19c35d08"
SWARM_EXPECTED = "b0bb07418cb1c0e1bc2da8ae443977825c0b19d1"
SOURCE_WRITEBACK_DEFAULT = "DENY"
DESTRUCTIVE_ACTION = "FORBIDDEN"
AUTHORITY_DELTA = 0


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def habitat_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    env = os.environ.get("JANUS_HABITAT_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".janus" / "habitat"


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def atomic_create_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(str(path))
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        raise FileExistsError(str(tmp))
    data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def identity_payload() -> dict[str, Any]:
    return {
        "schema": IDENTITY_SCHEMA,
        "resident_id": RESIDENT_ID,
        "source_writeback_default": SOURCE_WRITEBACK_DEFAULT,
        "destructive_action": DESTRUCTIVE_ACTION,
        "authority_delta": AUTHORITY_DELTA,
    }


def init_habitat(root: Path) -> dict[str, Any]:
    ensure_private_dir(root)
    for name in ("state", "receipts", "memory"):
        ensure_private_dir(root / name)
    identity = root / "identity.json"
    created = False
    expected = identity_payload()
    if not identity.exists():
        atomic_create_json(identity, expected)
        created = True
    else:
        current = json.loads(identity.read_text(encoding="utf-8"))
        if current != expected:
            raise RuntimeError("IDENTITY_MISMATCH_FAIL_CLOSED")
    journal = root / "journal.jsonl"
    if not journal.exists():
        fd = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    return {"schema": SCHEMA, "resident_id": RESIDENT_ID, "identity_created": created, "journal_chain_ok": verify_journal(journal)["ok"]}


def read_entries(journal: Path) -> list[dict[str, Any]]:
    if not journal.exists():
        return []
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(journal.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"JOURNAL_JSON_INVALID_LINE_{index}") from exc
        if not isinstance(row, dict):
            raise RuntimeError(f"JOURNAL_ENTRY_NOT_OBJECT_LINE_{index}")
        rows.append(row)
    return rows


def verify_journal(journal: Path) -> dict[str, Any]:
    rows = read_entries(journal)
    prev = "0" * 64
    for idx, row in enumerate(rows, start=1):
        body = {k: v for k, v in row.items() if k != "entry_hash"}
        expected = sha256_value(body)
        if row.get("seq") != idx:
            return {"ok": False, "reason": "SEQ_MISMATCH", "index": idx}
        if row.get("prev_hash") != prev:
            return {"ok": False, "reason": "PREV_HASH_MISMATCH", "index": idx}
        if row.get("entry_hash") != expected:
            return {"ok": False, "reason": "ENTRY_HASH_MISMATCH", "index": idx}
        prev = expected
    return {"ok": True, "entries": len(rows), "head": prev}


def append_event(root: Path, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    init_habitat(root)
    journal = root / "journal.jsonl"
    check = verify_journal(journal)
    if not check["ok"]:
        raise RuntimeError("JOURNAL_CHAIN_INVALID_FAIL_CLOSED")
    body = {
        "schema": SCHEMA,
        "seq": int(check.get("entries", 0)) + 1,
        "prev_hash": check.get("head", "0" * 64),
        "timestamp": utc_now(),
        "resident_id": RESIDENT_ID,
        "event_type": event_type,
        "payload": payload,
        "authority_delta": AUTHORITY_DELTA,
    }
    row = dict(body)
    row["entry_hash"] = sha256_value(body)
    line = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    with journal.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    return {"seq": row["seq"], "entry_hash": row["entry_hash"], "journal_chain_ok": verify_journal(journal)["ok"]}


def command_version(name: str, args: list[str]) -> dict[str, Any]:
    if shutil.which(name) is None:
        return {"available": False}
    try:
        p = subprocess.run([name, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5, check=False)
        first = (p.stdout or "").strip().splitlines()
        text = first[0][:160] if first else None
        return {"available": p.returncode == 0, "version": text}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}


def require_loopback_url(raw: str) -> str:
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("OLLAMA_URL_SCHEME_REJECTED")
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("OLLAMA_NON_LOOPBACK_REJECTED")
    return raw.rstrip("/")


def ollama_health(url: str, timeout: float = 2.0) -> dict[str, Any]:
    base = require_loopback_url(url)
    req = urllib.request.Request(base + "/api/tags", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read(2_000_000).decode("utf-8"))
        models = payload.get("models") if isinstance(payload, dict) else None
        names = []
        if isinstance(models, list):
            for row in models[:50]:
                if isinstance(row, dict) and isinstance(row.get("name"), str):
                    names.append(row["name"][:120])
        return {"reachable": True, "model_count": len(names), "models": names}
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return {"reachable": False, "model_count": 0, "models": []}


def doctor(ollama_url: str) -> dict[str, Any]:
    return {
        "schema": "JANUS_LOCAL_BRIDGE_DOCTOR_V1",
        "python": {"available": True, "version": sys.version.split()[0]},
        "git": command_version("git", ["--version"]),
        "node": command_version("node", ["--version"]),
        "npx": command_version("npx", ["--version"]),
        "codex": command_version("codex", ["--version"]),
        "ollama": ollama_health(ollama_url),
        "remote_desktop_required": False,
        "local_codex_stdio_mcp_supported": True,
        "genesis_expected": GENESIS_EXPECTED,
        "swarm_expected": SWARM_EXPECTED,
        "source_writeback_default": SOURCE_WRITEBACK_DEFAULT,
        "destructive_action": DESTRUCTIVE_ACTION,
        "authority_delta": AUTHORITY_DELTA,
    }


def install_codex_desktop_commander(apply: bool) -> dict[str, Any]:
    command = ["codex", "mcp", "add", "desktop-commander", "--", "npx", "-y", "@wonderwhy-er/desktop-commander@latest"]
    if not apply:
        return {"applied": False, "command": " ".join(command), "reason": "EXPLICIT_APPLY_REQUIRED"}
    if shutil.which("codex") is None:
        raise RuntimeError("CODEX_CLI_NOT_FOUND")
    try:
        p = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("CODEX_MCP_INSTALL_FAILED") from exc
    if p.returncode != 0:
        raise RuntimeError("CODEX_MCP_INSTALL_FAILED")
    return {"applied": True, "connector": "desktop-commander", "transport": "local_stdio", "remote_pairing_required": False}


def print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    d = sub.add_parser("doctor")
    del d
    a = sub.add_parser("append")
    a.add_argument("--event-type", required=True)
    a.add_argument("--payload-json", default="{}")
    c = sub.add_parser("codex-mcp")
    c.add_argument("--apply", action="store_true")
    sub.add_parser("ollama-health")
    args = ap.parse_args()
    root = habitat_root(args.root)

    try:
        if args.cmd == "init":
            result = init_habitat(root)
        elif args.cmd == "status":
            init_habitat(root)
            result = {"schema": SCHEMA, "resident_id": RESIDENT_ID, "journal": verify_journal(root / "journal.jsonl"), "authority_delta": AUTHORITY_DELTA}
        elif args.cmd == "doctor":
            result = doctor(args.ollama_url)
        elif args.cmd == "append":
            payload = json.loads(args.payload_json)
            if not isinstance(payload, dict):
                raise ValueError("PAYLOAD_MUST_BE_OBJECT")
            result = append_event(root, args.event_type, payload)
        elif args.cmd == "codex-mcp":
            result = install_codex_desktop_commander(args.apply)
        elif args.cmd == "ollama-health":
            result = ollama_health(args.ollama_url)
        else:
            raise RuntimeError("UNKNOWN_COMMAND")
    except Exception as exc:
        print_json({"ok": False, "error": str(exc)[:200]})
        return 2
    print_json({"ok": True, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
