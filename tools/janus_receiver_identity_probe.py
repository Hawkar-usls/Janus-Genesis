#!/usr/bin/env python3
"""Read-only live receiver identity probe for JANUS #164.

The probe never changes the inspected process, files, repository, network, or
container state. It records enough provenance to bind a running receiver to a
content identity and, when possible, to an exact Git blob/commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_link(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


def _cmd(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def git_identity(repo: Path, source: Path | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "git_applicable": False,
        "repository": None,
        "commit": None,
        "blob": None,
        "tracked_path": None,
        "worktree_clean_for_source": None,
    }
    rc, top = _cmd(["git", "rev-parse", "--show-toplevel"], repo)
    if rc != 0 or not top:
        return out
    top_path = Path(top).resolve()
    out["git_applicable"] = True
    out["repository"] = str(top_path)
    rc, commit = _cmd(["git", "rev-parse", "HEAD"], top_path)
    if rc == 0:
        out["commit"] = commit
    if source is None:
        return out
    try:
        rel = source.resolve().relative_to(top_path).as_posix()
    except (OSError, ValueError):
        return out
    rc, tracked = _cmd(["git", "ls-files", "--error-unmatch", "--", rel], top_path)
    if rc != 0 or not tracked:
        return out
    out["tracked_path"] = rel
    rc, blob = _cmd(["git", "rev-parse", f"HEAD:{rel}"], top_path)
    if rc == 0:
        out["blob"] = blob
    rc, diff = _cmd(["git", "diff", "--quiet", "HEAD", "--", rel], top_path)
    out["worktree_clean_for_source"] = rc == 0
    return out


def discover_source_from_pid(pid: int) -> tuple[dict[str, Any], Path | None]:
    proc = Path("/proc") / str(pid)
    if not proc.exists():
        raise FileNotFoundError(f"process {pid} not found under /proc")
    cmdline_raw = b""
    try:
        cmdline_raw = (proc / "cmdline").read_bytes()
    except OSError:
        pass
    args = [x.decode("utf-8", errors="replace") for x in cmdline_raw.split(b"\0") if x]
    cwd = _read_link(proc / "cwd")
    exe = _read_link(proc / "exe")
    source: Path | None = None
    for arg in args[1:]:
        candidate = Path(arg)
        if not candidate.is_absolute() and cwd:
            candidate = Path(cwd) / candidate
        if candidate.suffix == ".py" and candidate.exists():
            source = candidate.resolve()
            break
    if source is None and exe and Path(exe).exists():
        source = Path(exe).resolve()
    identity = {
        "pid": pid,
        "cmdline": args,
        "cwd": cwd,
        "exe": exe,
        "proc_root": _read_link(proc / "root"),
        "cgroup": _read_text(proc / "cgroup"),
    }
    return identity, source


def tcp_listener_probe(host: str, port: int, timeout: float) -> dict[str, Any]:
    result: dict[str, Any] = {"host": host, "port": port, "tcp_connect": False, "error": None}
    try:
        with socket.create_connection((host, port), timeout=timeout):
            result["tcp_connect"] = True
    except OSError as exc:
        result["error"] = exc.__class__.__name__
    return result


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    process_identity: dict[str, Any] | None = None
    source: Path | None = args.source.resolve() if args.source else None
    if args.pid is not None:
        process_identity, discovered = discover_source_from_pid(args.pid)
        if source is None:
            source = discovered
    source_identity: dict[str, Any] = {
        "path": str(source) if source else None,
        "sha256": sha256_file(source) if source and source.is_file() else None,
        "bytes": source.stat().st_size if source and source.is_file() else None,
        "git_applicable": False,
        "repository": None,
        "commit": None,
        "blob": None,
        "tracked_path": None,
        "worktree_clean_for_source": None,
    }
    repo = args.repo.resolve() if args.repo else (source.parent if source else None)
    if repo:
        source_identity.update(git_identity(repo, source))
    network = tcp_listener_probe(args.host, args.port, args.timeout) if args.probe_tcp else None
    return {
        "schema": "janus.receiver.live_source_identity.v1",
        "evidence_kind": "LIVE" if args.live else "LOCAL_PROBE_UNATTESTED",
        "receiver_service": args.receiver_service,
        "process_identity": process_identity,
        "source_identity": source_identity,
        "port_8008_owner": args.port_owner,
        "network_namespace": args.network_namespace,
        "service_owner_reconciled": bool(args.service_owner_reconciled),
        "network_probe": network,
        "read_only": True,
        "source_writeback_observed": False,
        "authority_delta": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pid", type=int)
    p.add_argument("--source", type=Path)
    p.add_argument("--repo", type=Path)
    p.add_argument("--receiver-service", default="janus_nas_brain")
    p.add_argument("--port-owner")
    p.add_argument("--network-namespace")
    p.add_argument("--service-owner-reconciled", action="store_true")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8008)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--probe-tcp", action="store_true")
    p.add_argument("--live", action="store_true", help="Mark evidence as live only when run on the actual receiver host/process.")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.pid is None and args.source is None:
        p.error("one of --pid or --source is required")
    receipt = build_receipt(args)
    text = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
