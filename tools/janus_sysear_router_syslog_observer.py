#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "janus.sysear.router_syslog_observer.v1"
PUBLIC_SCHEMA = "janus.sysear.router_syslog_public_receipt.v1"
IPV4_RE = re.compile(r"(?<![0-9])(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})(?:\.(?:25[0-5]|2[0-4][0-9]|1?[0-9]{1,2})){3}(?![0-9])")
MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])")
HEX_IPV6_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{0,4}(?![0-9a-f])")


def _create_text(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _run_readonly(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=3, check=False)
    return (result.stdout or "") + "\n" + (result.stderr or "")


def discover_default_gateway() -> str | None:
    system = platform.system().lower()
    candidates: list[list[str]]
    if system == "windows":
        candidates = [["route", "print", "-4"]]
    elif system == "darwin":
        candidates = [["route", "-n", "get", "default"], ["netstat", "-rn", "-f", "inet"]]
    else:
        candidates = [["ip", "route", "show", "default"], ["route", "-n"]]
    for argv in candidates:
        try:
            text = _run_readonly(argv)
        except (OSError, subprocess.SubprocessError):
            continue
        if system == "windows":
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
                    return parts[2]
        elif system == "darwin":
            match = re.search(r"\bgateway:\s*([^\s]+)", text)
            if match:
                return match.group(1)
            for line in text.splitlines():
                parts = line.split()
                if parts and parts[0] == "default" and len(parts) > 1:
                    return parts[1]
        else:
            match = re.search(r"\bdefault\s+via\s+([^\s]+)", text)
            if match:
                return match.group(1)
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "0.0.0.0":
                    return parts[1]
    return None


def classify(message: str) -> str:
    low = message.lower()
    if any(k in low for k in ("drop", "deny", "reject", "blocked", "firewall")):
        return "FIREWALL"
    if any(k in low for k in ("dhcp", "lease", "dnsmasq")):
        return "DHCP"
    if any(k in low for k in ("wlan", "wifi", "wireless", "deauth", "assoc")):
        return "WIFI"
    if any(k in low for k in ("route", "gateway", "wan", "pppoe")):
        return "ROUTING"
    if any(k in low for k in ("dns", "resolver")):
        return "DNS"
    if any(k in low for k in ("login", "auth", "admin")):
        return "AUTH"
    return "SYSTEM"


def contains_deployment_identifier(text: str) -> bool:
    return bool(IPV4_RE.search(text) or MAC_RE.search(text) or HEX_IPV6_RE.search(text))


def doctor(args: argparse.Namespace) -> int:
    gateway = discover_default_gateway()
    bind_ok = False
    error_class = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((args.listen_host, args.listen_port))
        bind_ok = True
    except OSError as exc:
        error_class = exc.__class__.__name__
    finally:
        sock.close()
    receipt = {
        "schema": SCHEMA,
        "mode": "DOCTOR_READ_ONLY",
        "default_gateway_detected": gateway is not None,
        "listen_bind_available": bind_ok,
        "listen_port": args.listen_port,
        "error_class": error_class,
        "router_address_publicly_disclosed": False,
        "outbound_router_probe_performed": False,
        "external_effect_authority": False,
    }
    if args.local_sensitive_output:
        sensitive = dict(receipt)
        sensitive["default_gateway_exact_local_only"] = gateway
        _create_text(args.local_sensitive_output, json.dumps(sensitive, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if bind_ok else 2


def listen(args: argparse.Namespace) -> int:
    expected = args.expected_source or discover_default_gateway()
    if not expected:
        raise SystemExit("NO_EXPECTED_ROUTER_SOURCE: supply --expected-source or make default gateway discoverable")
    raw_path = args.raw_output
    receipt_path = args.local_receipt
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists() or receipt_path.exists():
        raise SystemExit("OUTPUT_EXISTS: create-only retention policy")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.listen_host, args.listen_port))
    sock.settimeout(min(1.0, max(0.05, args.timeout)))
    started = time.time()
    accepted = 0
    rejected = 0
    classes: Counter[str] = Counter()
    sha = hashlib.sha256()
    source_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()

    with raw_path.open("x", encoding="utf-8", newline="\n") as raw:
        try:
            os.chmod(raw_path, 0o600)
        except OSError:
            pass
        while accepted < args.max_events and time.time() - started < args.duration:
            try:
                data, peer = sock.recvfrom(args.max_datagram_bytes)
            except socket.timeout:
                continue
            peer_ip = str(peer[0])
            if peer_ip != expected:
                rejected += 1
                continue
            message = data.decode("utf-8", errors="replace").rstrip("\x00\r\n")
            event_class = classify(message)
            row = {
                "observed_at_unix": round(time.time(), 6),
                "source_ip_local_only": peer_ip,
                "event_class": event_class,
                "message": message,
            }
            line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            raw.write(line)
            sha.update(line.encode("utf-8"))
            classes[event_class] += 1
            accepted += 1
    sock.close()

    receipt = {
        "schema": SCHEMA,
        "mode": "BOUNDED_LIVE_SYSLOG_CAPTURE",
        "status": "PASS_CAPTURED" if accepted else "HOLD_NO_ROUTER_EVENTS_OBSERVED",
        "started_at_unix": round(started, 6),
        "ended_at_unix": round(time.time(), 6),
        "listen_port": args.listen_port,
        "expected_source_exact_local_only": expected,
        "expected_source_sha256": source_hash,
        "accepted_events": accepted,
        "rejected_non_router_source_events": rejected,
        "event_classes": dict(sorted(classes.items())),
        "raw_jsonl_path_local_only": str(raw_path),
        "raw_jsonl_sha256": sha.hexdigest(),
        "transport": "UDP_SYSLOG_UNAUTHENTICATED",
        "transport_authenticated": False,
        "source_ip_filter_applied": True,
        "truth_authority": False,
        "effect_authority": False,
        "raw_publication_allowed": False,
        "claim_ceiling": "PASS_CAPTURED means bounded datagrams from the locally bound router address were observed; it does not authenticate the router, prove human identity, or authorize actions.",
    }
    _create_text(receipt_path, json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "accepted_events": accepted, "rejected_non_router_source_events": rejected}, sort_keys=True))
    return 0 if accepted else 4


def public_receipt(args: argparse.Namespace) -> int:
    local = json.loads(args.local_receipt.read_text(encoding="utf-8"))
    if local.get("schema") != SCHEMA:
        raise SystemExit("LOCAL_RECEIPT_SCHEMA_REJECT")
    allowed = {
        "schema": PUBLIC_SCHEMA,
        "source_class": "NETWORK_EDGE_TELEMETRY",
        "observer": "JANUS_SYSEAR",
        "status": local.get("status"),
        "listen_port": local.get("listen_port"),
        "accepted_events": local.get("accepted_events"),
        "rejected_non_router_source_events": local.get("rejected_non_router_source_events"),
        "event_classes": local.get("event_classes"),
        "raw_jsonl_sha256": local.get("raw_jsonl_sha256"),
        "source_binding": "EXACT_LOCAL_ROUTER_ADDRESS_WITHHELD",
        "transport": "UDP_SYSLOG_UNAUTHENTICATED",
        "transport_authenticated": False,
        "raw_telemetry_public": False,
        "router_identifiers_public": False,
        "truth_authority": False,
        "effect_authority": False,
        "authority_delta": 0,
        "claim_ceiling": "Privacy-safe observation receipt only; raw router telemetry and deployment identifiers remain local.",
    }
    text = json.dumps(allowed, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if contains_deployment_identifier(text):
        raise SystemExit("PUBLIC_RECEIPT_IDENTIFIER_LEAK_REJECT")
    _create_text(args.output, text, mode=0o600)
    print(json.dumps({"status": allowed["status"], "public_receipt": str(args.output)}, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JANUS SysEar bounded router syslog observer")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor")
    d.add_argument("--listen-host", default="0.0.0.0")
    d.add_argument("--listen-port", type=int, default=5514)
    d.add_argument("--local-sensitive-output", type=Path)
    d.set_defaults(func=doctor)

    l = sub.add_parser("listen")
    l.add_argument("--listen-host", default="0.0.0.0")
    l.add_argument("--listen-port", type=int, default=5514)
    l.add_argument("--expected-source")
    l.add_argument("--duration", type=float, default=30.0)
    l.add_argument("--timeout", type=float, default=0.5)
    l.add_argument("--max-events", type=int, default=200)
    l.add_argument("--max-datagram-bytes", type=int, default=8192)
    l.add_argument("--raw-output", type=Path, required=True)
    l.add_argument("--local-receipt", type=Path, required=True)
    l.set_defaults(func=listen)

    r = sub.add_parser("public-receipt")
    r.add_argument("--local-receipt", type=Path, required=True)
    r.add_argument("--output", type=Path, required=True)
    r.set_defaults(func=public_receipt)
    return p


def main() -> int:
    args = parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
