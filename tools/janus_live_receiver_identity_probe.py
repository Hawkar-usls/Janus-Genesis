#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only live receiver/source identity probe for JANUS #164.

The probe observes Linux /proc plus optional Docker metadata. It never mutates
source state, containers, sockets, Git refs, or network state. Optional output
files are local evidence receipts only. Live PASS remains impossible unless
exact source identity and :8008 ownership are both explicit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_SERVICE_NAMES = ("janus_nas_brain", "janus_nas_api", "janus_titan_core")


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def safe_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, PermissionError):
        return None


def safe_link(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except (OSError, PermissionError):
        return None


def iter_pids(proc_root: Path) -> Iterable[int]:
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return []
    out = []
    for entry in entries:
        if entry.name.isdigit():
            try:
                out.append(int(entry.name))
            except ValueError:
                pass
    return sorted(out)


def process_record(proc_root: Path, pid: int) -> dict:
    base = proc_root / str(pid)
    raw = None
    try:
        raw = (base / "cmdline").read_bytes()
    except OSError:
        pass
    cmdline = []
    if raw:
        cmdline = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
    return {
        "pid": pid,
        "comm": safe_text(base / "comm"),
        "cmdline": cmdline,
        "cwd": safe_link(base / "cwd"),
        "exe": safe_link(base / "exe"),
        "root": safe_link(base / "root"),
        "net_namespace": safe_link(base / "ns" / "net"),
    }


def matches_service(record: dict, names: tuple[str, ...]) -> bool:
    haystack = " ".join([record.get("comm") or "", *(record.get("cmdline") or [])]).lower()
    return any(name.lower() in haystack for name in names)


def parse_proc_tcp(path: Path, port: int) -> list[dict]:
    text = safe_text(path)
    if not text:
        return []
    listeners = []
    for line in text.splitlines()[1:]:
        cols = line.split()
        if len(cols) < 10:
            continue
        local = cols[1]
        state = cols[3]
        if state != "0A" or ":" not in local:
            continue
        host_hex, port_hex = local.rsplit(":", 1)
        try:
            parsed_port = int(port_hex, 16)
        except ValueError:
            continue
        if parsed_port != port:
            continue
        listeners.append(
            {
                "table": path.name,
                "local_hex": host_hex,
                "port": parsed_port,
                "inode": cols[9],
                "state": "LISTEN",
            }
        )
    return listeners


def socket_inodes_for_pid(proc_root: Path, pid: int) -> set[str]:
    fd_dir = proc_root / str(pid) / "fd"
    out: set[str] = set()
    try:
        entries = list(fd_dir.iterdir())
    except OSError:
        return out
    for entry in entries:
        target = safe_link(entry)
        if target and target.startswith("socket:[") and target.endswith("]"):
            out.add(target[8:-1])
    return out


def namespace_listener_owners(proc_root: Path, anchor_pid: int, port: int) -> dict:
    anchor = proc_root / str(anchor_pid)
    ns = safe_link(anchor / "ns" / "net")
    listeners = parse_proc_tcp(anchor / "net" / "tcp", port) + parse_proc_tcp(anchor / "net" / "tcp6", port)
    inodes = {x["inode"] for x in listeners}
    owners = []
    if ns and inodes:
        for pid in iter_pids(proc_root):
            pns = safe_link(proc_root / str(pid) / "ns" / "net")
            if pns != ns:
                continue
            sockets = socket_inodes_for_pid(proc_root, pid)
            overlap = sorted(inodes & sockets)
            if overlap:
                record = process_record(proc_root, pid)
                record["listener_inodes"] = overlap
                owners.append(record)
    return {
        "anchor_pid": anchor_pid,
        "net_namespace": ns,
        "listeners": listeners,
        "owners": owners,
        "docker_names": [],
    }


def parse_git_head(repo_dir: Path) -> dict | None:
    git = repo_dir / ".git"
    if not git.is_dir():
        return None
    head = safe_text(git / "HEAD")
    if not head:
        return {"repo_dir": str(repo_dir), "commit": None, "ref": None}
    if head.startswith("ref: "):
        ref = head[5:].strip()
        commit = safe_text(git / ref)
        if not commit:
            packed = safe_text(git / "packed-refs") or ""
            for line in packed.splitlines():
                if not line or line.startswith(("#", "^")):
                    continue
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    commit = parts[0]
                    break
        return {"repo_dir": str(repo_dir), "commit": commit, "ref": ref}
    return {"repo_dir": str(repo_dir), "commit": head, "ref": "DETACHED"}


def find_git_provenance(path: Path) -> dict | None:
    # Keep /proc/<pid>/root lexical. Resolving that magic symlink may escape the
    # target process root and accidentally inspect the host namespace instead.
    current = path
    try:
        if current.is_file():
            current = current.parent
    except OSError:
        pass
    for candidate in [current, *current.parents]:
        prov = parse_git_head(candidate)
        if prov:
            return prov
    return None


def source_candidates(proc_root: Path, record: dict) -> list[dict]:
    pid = record["pid"]
    root_prefix = proc_root / str(pid) / "root"
    candidates: list[str] = []
    for arg in record.get("cmdline") or []:
        if arg.endswith(".py") or arg.endswith(".pyw"):
            candidates.append(arg)
    out = []
    for raw in dict.fromkeys(candidates):
        raw_path = Path(raw)
        container_path = raw_path if raw_path.is_absolute() else Path(record.get("cwd") or "/") / raw_path
        host_view = root_prefix / str(container_path).lstrip("/")
        out.append(
            {
                "container_path": str(container_path),
                "host_view_path": str(host_view),
                "sha256": sha256_file(host_view),
                "git": find_git_provenance(host_view),
            }
        )
    return out


def docker_rows(names: tuple[str, ...]) -> list[dict]:
    """Return narrow, non-secret Docker metadata only. No env/config dump."""
    try:
        proc = subprocess.run(
            ["docker", "ps", "--no-trunc", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        cid, name, image = parts
        if not any(x.lower() in name.lower() for x in names):
            continue
        try:
            detail = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Pid}}\t{{.Id}}\t{{.Name}}\t{{.Image}}\t{{json .NetworkSettings.Networks}}\t{{json .NetworkSettings.Ports}}",
                    cid,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if detail.returncode != 0:
            continue
        fields = detail.stdout.rstrip("\n").split("\t", 5)
        if len(fields) != 6:
            continue
        pid_s, full_id, inspect_name, image_id, networks, ports = fields
        try:
            pid = int(pid_s)
        except ValueError:
            pid = 0
        rows.append(
            {
                "name": inspect_name.lstrip("/") or name,
                "container_id": full_id or cid,
                "image_ref": image,
                "image_id": image_id,
                "init_pid": pid,
                "networks": json.loads(networks) if networks else {},
                "ports": json.loads(ports) if ports else {},
            }
        )
    return rows


def bind_docker_names_to_namespaces(proc_root: Path, dockers: list[dict], namespaces: list[dict]) -> None:
    names_by_ns: dict[str, set[str]] = {}
    for item in dockers:
        pid = item.get("init_pid") or 0
        if not pid:
            continue
        ns = safe_link(proc_root / str(pid) / "ns" / "net")
        if ns:
            names_by_ns.setdefault(ns, set()).add(item["name"])
    for item in namespaces:
        ns = item.get("net_namespace")
        item["docker_names"] = sorted(names_by_ns.get(ns, set())) if ns else []


def evaluate(receipt: dict, expected_owner: str | None, expected_commit: str | None) -> dict:
    exact_source_commits = set()
    for proc in receipt["matching_processes"]:
        for source in proc.get("source_candidates", []):
            commit = (source.get("git") or {}).get("commit")
            if commit and source.get("sha256"):
                exact_source_commits.add(commit)

    owner_names = set()
    for ns in receipt["port_8008_namespaces"]:
        for owner in ns.get("owners", []):
            hay = " ".join([owner.get("comm") or "", *(owner.get("cmdline") or [])])
            owner_names.add(hay)
        if ns.get("listeners"):
            owner_names.update(ns.get("docker_names") or [])

    source_state = "UNRESOLVED"
    if exact_source_commits:
        source_state = "EXACT_SOURCE_IDENTITY_OBSERVED"
    if expected_commit:
        source_state = "EXPECTED_COMMIT_MATCH" if expected_commit in exact_source_commits else "EXPECTED_COMMIT_NOT_PROVEN"

    port_state = "UNRESOLVED"
    if any(ns.get("listeners") for ns in receipt["port_8008_namespaces"]):
        port_state = "LISTENER_OBSERVED_OWNER_UNRESOLVED"
    if owner_names:
        port_state = "LISTENER_OWNER_OBSERVED"
    if expected_owner:
        port_state = (
            "EXPECTED_OWNER_MATCH"
            if any(expected_owner.lower() in text.lower() for text in owner_names)
            else "EXPECTED_OWNER_NOT_PROVEN"
        )

    live_bound = source_state in {"EXACT_SOURCE_IDENTITY_OBSERVED", "EXPECTED_COMMIT_MATCH"} and port_state in {
        "LISTENER_OWNER_OBSERVED",
        "EXPECTED_OWNER_MATCH",
    }
    return {
        "live_receiver_source_identity": source_state,
        "port_8008_owner": port_state,
        "live_receiver_bound": live_bound,
        "issue_164_pass": False,
        "claim": "IDENTITY_BINDING_PASS_NOT_HR1_HR10" if live_bound else "HOLD",
    }


def build_receipt(
    proc_root: Path,
    names: tuple[str, ...],
    port: int,
    expected_owner: str | None,
    expected_commit: str | None,
) -> dict:
    records = []
    for pid in iter_pids(proc_root):
        record = process_record(proc_root, pid)
        if matches_service(record, names):
            record["source_candidates"] = source_candidates(proc_root, record)
            records.append(record)

    dockers = docker_rows(names)
    anchor_pids = {r["pid"] for r in records}
    anchor_pids.update(x["init_pid"] for x in dockers if x.get("init_pid"))
    namespaces = [
        namespace_listener_owners(proc_root, pid, port)
        for pid in sorted(anchor_pids)
        if (proc_root / str(pid)).exists()
    ]
    bind_docker_names_to_namespaces(proc_root, dockers, namespaces)

    receipt = {
        "schema": "janus.handoff.live_receiver_identity_probe.v1",
        "evidence_kind": "READ_ONLY_LIVE_IDENTITY_NETWORK_PROBE",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "proc_root": str(proc_root),
        "service_names": list(names),
        "matching_processes": records,
        "docker": dockers,
        "port": port,
        "port_8008_namespaces": namespaces,
        "privacy": {
            "unredacted_receipt_scope": "LOCAL_ONLY",
            "public_private_exact_pin_disclosure": False,
        },
        "safety": {
            "source_writeback": False,
            "destructive_action": False,
            "network_mutation": False,
            "container_mutation": False,
            "authority_delta": 0,
        },
    }
    receipt["gate"] = evaluate(receipt, expected_owner, expected_commit)
    return receipt


def public_summary(receipt: dict) -> dict:
    gate = receipt["gate"]
    return {
        "schema": "janus.handoff.live_receiver_identity_probe.public_summary.v1",
        "evidence_kind": receipt["evidence_kind"],
        "live_receiver_source_identity": gate["live_receiver_source_identity"],
        "port_8008_owner": gate["port_8008_owner"],
        "live_receiver_bound": gate["live_receiver_bound"],
        "issue_164_pass": False,
        "private_exact_pin_disclosed": False,
        "source_writeback": False,
        "destructive_action": False,
        "authority_delta": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    parser.add_argument("--port", type=int, default=8008)
    parser.add_argument("--service-name", action="append", dest="service_names")
    parser.add_argument("--expected-owner", default="janus_nas_brain")
    parser.add_argument("--expected-commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--public-summary-output", type=Path)
    args = parser.parse_args()
    names = tuple(args.service_names or DEFAULT_SERVICE_NAMES)
    receipt = build_receipt(args.proc_root, names, args.port, args.expected_owner, args.expected_commit)
    text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.public_summary_output:
        summary = json.dumps(public_summary(receipt), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        args.public_summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.public_summary_output.write_text(summary, encoding="utf-8")
    return 0 if receipt["gate"]["live_receiver_bound"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
