#!/usr/bin/env python3
"""Read-only live receiver identity / QNAP namespace probe for JANUS #164.

The probe never changes the inspected process, files, repository, network,
container configuration, or service lifecycle.  It may execute only read-only
query commands (`git ...`, `docker ps`, `docker inspect`) and read `/proc`.

`--qnap-auto` discovers Docker container PIDs/network namespaces, identifies
which observed namespace is listening on the selected port (8008 by default),
and binds the requested receiver container to a source-content hash when a
Python source argument is visible through `/proc/<pid>/root`.

No `docker exec`, restart, stop, start, kill, cp, update, or config mutation is
performed.  `--live` is an operator assertion that the probe itself is running
on the actual receiver host; the script never infers LIVE from a heartbeat.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any, Iterable

DEFAULT_QNAP_DOCKER = Path("/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker")
READ_ONLY_DOCKER_SUBCOMMANDS = frozenset({"ps", "inspect"})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_link(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


def _cmd(cmd: list[str], cwd: Path | None = None, *, timeout: float = 5.0) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def _docker_query(docker: Path, args: list[str]) -> tuple[int, str]:
    if not args or args[0] not in READ_ONLY_DOCKER_SUBCOMMANDS:
        raise ValueError("NON_READ_ONLY_DOCKER_SUBCOMMAND_REJECTED")
    return _cmd([str(docker), *args], timeout=20.0)


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
    rc, _ = _cmd(["git", "diff", "--quiet", "HEAD", "--", rel], top_path)
    out["worktree_clean_for_source"] = rc == 0
    return out


def _host_view_process_path(proc: Path, cwd: str | None, value: str) -> Path | None:
    """Resolve a process-visible path through /proc/<pid>/root without entering it."""
    candidate = Path(value)
    if candidate.is_absolute():
        host_view = proc / "root" / str(candidate).lstrip("/")
    elif cwd and cwd.startswith("/"):
        host_view = proc / "root" / cwd.lstrip("/") / candidate
    else:
        return None
    try:
        if host_view.is_file():
            return host_view.resolve(strict=True)
    except OSError:
        return None
    return None


def discover_source_from_pid(pid: int) -> tuple[dict[str, Any], Path | None]:
    proc = Path("/proc") / str(pid)
    if not proc.exists():
        raise FileNotFoundError(f"process {pid} not found under /proc")
    cmdline_raw = _read_bytes(proc / "cmdline") or b""
    args = [x.decode("utf-8", errors="replace") for x in cmdline_raw.split(b"\0") if x]
    cwd = _read_link(proc / "cwd")
    exe = _read_link(proc / "exe")
    root = _read_link(proc / "root")
    source: Path | None = None
    source_argument: str | None = None
    for arg in args[1:]:
        if Path(arg).suffix != ".py":
            continue
        resolved = _host_view_process_path(proc, cwd, arg)
        if resolved is not None:
            source = resolved
            source_argument = arg
            break
    if source is None and exe:
        # Executable identity is useful only as a fallback content identity.
        resolved_exe = _host_view_process_path(proc, cwd, exe)
        if resolved_exe is not None:
            source = resolved_exe

    # Never emit the raw argv/cgroup text: service command lines can contain
    # credentials.  Hashing provides continuity evidence without disclosure.
    cgroup_raw = _read_bytes(proc / "cgroup") or b""
    identity = {
        "pid": pid,
        "argv_count": len(args),
        "argv0_basename": Path(args[0]).name if args else None,
        "cmdline_sha256": sha256_bytes(cmdline_raw) if cmdline_raw else None,
        "python_source_argument": source_argument,
        "cwd": cwd,
        "exe_basename": Path(exe).name if exe else None,
        "proc_root": root,
        "cgroup_sha256": sha256_bytes(cgroup_raw) if cgroup_raw else None,
        "raw_cmdline_emitted": False,
        "raw_cgroup_emitted": False,
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


def _parse_proc_net(path: Path, port: int, family: str) -> list[dict[str, Any]]:
    text = _read_text(path)
    if not text:
        return []
    wanted = f"{int(port):04X}"
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        local = parts[1]
        state = parts[3]
        if state != "0A" or ":" not in local:
            continue
        address_hex, port_hex = local.rsplit(":", 1)
        if port_hex.upper() != wanted:
            continue
        rows.append(
            {
                "family": family,
                "local_address_hex": address_hex,
                "port": int(port),
                "socket_inode": parts[9],
            }
        )
    return rows


def listeners_in_pid_namespace(pid: int, port: int) -> list[dict[str, Any]]:
    base = Path("/proc") / str(pid) / "net"
    return _parse_proc_net(base / "tcp", port, "tcp4") + _parse_proc_net(base / "tcp6", port, "tcp6")


def _safe_inspect_container(docker: Path, name: str) -> dict[str, Any] | None:
    rc, raw = _docker_query(docker, ["inspect", name])
    if rc != 0 or not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list) or not value or not isinstance(value[0], dict):
        return None
    row = value[0]
    state = row.get("State") if isinstance(row.get("State"), dict) else {}
    config = row.get("Config") if isinstance(row.get("Config"), dict) else {}
    network = row.get("NetworkSettings") if isinstance(row.get("NetworkSettings"), dict) else {}
    pid = int(state.get("Pid") or 0)
    netns = _read_link(Path("/proc") / str(pid) / "ns" / "net") if pid > 0 else None
    return {
        "name": name,
        "container_id_prefix": str(row.get("Id") or "")[:12] or None,
        "running": bool(state.get("Running")),
        "pid": pid or None,
        "image": str(config.get("Image") or "")[:200] or None,
        "network_namespace": netns,
        "published_ports": sorted(str(key) for key in (network.get("Ports") or {}).keys()),
        "environment_read": False,
    }


def qnap_auto_discovery(docker: Path, receiver_service: str, port: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "docker_path": str(docker),
        "docker_available": docker.is_file(),
        "docker_queries_read_only": True,
        "docker_exec_used": False,
        "service_lifecycle_mutated": False,
        "port": int(port),
        "containers": [],
        "owner_namespaces": [],
        "port_owner_reconciled": False,
        "port_owner_container_candidates": [],
        "receiver_container_found": False,
        "receiver_source_binding": None,
    }
    if not docker.is_file():
        result["hold_reason"] = "QNAP_DOCKER_NOT_FOUND"
        return result

    rc, names_raw = _docker_query(docker, ["ps", "-a", "--format", "{{.Names}}"])
    if rc != 0:
        result["hold_reason"] = "DOCKER_PS_READ_FAILED"
        return result
    names = sorted({line.strip() for line in names_raw.splitlines() if line.strip()})
    containers: list[dict[str, Any]] = []
    for name in names:
        row = _safe_inspect_container(docker, name)
        if row is None:
            continue
        pid = row.get("pid")
        listeners = listeners_in_pid_namespace(int(pid), port) if isinstance(pid, int) and pid > 0 else []
        row["listener_count_on_target_port"] = len(listeners)
        row["target_port_listener_inodes"] = sorted({str(x["socket_inode"]) for x in listeners})
        containers.append(row)
    result["containers"] = containers

    by_netns: dict[str, dict[str, Any]] = {}
    for row in containers:
        netns = row.get("network_namespace")
        if not isinstance(netns, str) or not netns:
            continue
        entry = by_netns.setdefault(netns, {"network_namespace": netns, "containers": [], "listener_inodes": set()})
        entry["containers"].append(str(row["name"]))
        if int(row.get("listener_count_on_target_port") or 0) > 0:
            entry["listener_inodes"].update(str(x) for x in row.get("target_port_listener_inodes") or [])

    owners: list[dict[str, Any]] = []
    for netns, entry in sorted(by_netns.items()):
        inodes = sorted(entry["listener_inodes"])
        if not inodes:
            continue
        owners.append(
            {
                "network_namespace": netns,
                "containers": sorted(set(entry["containers"])),
                "listener_inodes": inodes,
            }
        )
    result["owner_namespaces"] = owners
    result["port_owner_reconciled"] = len(owners) == 1
    if len(owners) == 1:
        result["port_owner_container_candidates"] = owners[0]["containers"]

    receiver = next((row for row in containers if row.get("name") == receiver_service), None)
    result["receiver_container_found"] = receiver is not None
    if receiver is not None:
        pid = receiver.get("pid")
        binding: dict[str, Any] = {
            "container": receiver_service,
            "pid": pid,
            "network_namespace": receiver.get("network_namespace"),
            "running": receiver.get("running"),
            "owns_target_port_namespace": receiver_service in result["port_owner_container_candidates"],
            "process_identity": None,
            "source_identity": None,
        }
        if isinstance(pid, int) and pid > 0:
            try:
                process_identity, source = discover_source_from_pid(pid)
            except (FileNotFoundError, PermissionError, OSError):
                process_identity, source = None, None
            binding["process_identity"] = process_identity
            binding["source_identity"] = {
                "path": str(source) if source else None,
                "sha256": sha256_file(source) if source and source.is_file() else None,
                "bytes": source.stat().st_size if source and source.is_file() else None,
            }
        result["receiver_source_binding"] = binding

    if not owners:
        result["hold_reason"] = "NO_TARGET_PORT_LISTENER_IN_OBSERVED_CONTAINER_NAMESPACES"
    elif len(owners) > 1:
        result["hold_reason"] = "MULTIPLE_TARGET_PORT_OWNER_NAMESPACES"
    elif receiver is None:
        result["hold_reason"] = "RECEIVER_CONTAINER_NOT_FOUND"
    else:
        result["hold_reason"] = None
    return result


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    if args.qnap_auto:
        qnap = qnap_auto_discovery(args.docker, args.receiver_service, args.port)
        binding = qnap.get("receiver_source_binding") or {}
        source_identity = binding.get("source_identity") or {
            "path": None,
            "sha256": None,
            "bytes": None,
        }
        process_identity = binding.get("process_identity")
        owners = qnap.get("owner_namespaces") or []
        owner_label = None
        netns = None
        if len(owners) == 1:
            owner_label = ",".join(owners[0].get("containers") or []) or "UNNAMED_NAMESPACE"
            netns = owners[0].get("network_namespace")
        return {
            "schema": "janus.receiver.live_source_identity.v1_1",
            "evidence_kind": "LIVE" if args.live else "LOCAL_PROBE_UNATTESTED",
            "receiver_service": args.receiver_service,
            "process_identity": process_identity,
            "source_identity": source_identity,
            "port_8008_owner": owner_label,
            "network_namespace": netns,
            "service_owner_reconciled": bool(qnap.get("port_owner_reconciled")),
            "receiver_owns_target_port_namespace": bool(binding.get("owns_target_port_namespace")),
            "qnap_auto_discovery": qnap,
            "network_probe": tcp_listener_probe(args.host, args.port, args.timeout) if args.probe_tcp else None,
            "read_only": True,
            "source_writeback_observed": False,
            "destructive_action_observed": False,
            "authority_delta": 0,
            "claim_ceiling": {
                "nas_available_proves_hr1_hr10": False,
                "heartbeat_proves_service_owner": False,
                "port_namespace_reconciliation_proves_application_semantics": False,
                "live_flag_is_operator_attestation": True,
            },
        }

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
        "schema": "janus.receiver.live_source_identity.v1_1",
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
        "destructive_action_observed": False,
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
    p.add_argument("--qnap-auto", action="store_true", help="Read-only auto-discover QNAP Docker namespaces and target-port ownership.")
    p.add_argument("--docker", type=Path, default=DEFAULT_QNAP_DOCKER)
    p.add_argument("--live", action="store_true", help="Mark evidence as live only when run on the actual receiver host/process.")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if not args.qnap_auto and args.pid is None and args.source is None:
        p.error("one of --pid, --source, or --qnap-auto is required")
    receipt = build_receipt(args)
    text = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
