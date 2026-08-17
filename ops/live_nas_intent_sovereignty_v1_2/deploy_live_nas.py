#!/usr/bin/env python3
"""Atomic QNAP deployment for JANUS Intent Sovereignty v1.2.

Touches only the intent live-module file and `janus_titan_core`. It never reads
runtime bot configuration, tokens, or databases. A failed health/self-test
attempt restores the previous module and restarts only Titan.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, Optional

CAPSULE_ID = "JANUS-LIVE-NAS-INTENT-SOVEREIGNTY-v1.2"
MODULE_NAME = "janus_intent_sovereignty_v1_2.py"
TARGET_REL = Path("services/modules_live") / MODULE_NAME
DEFAULT_ROOT = Path("/share/CACHEDEV1_DATA/Janus")
DEFAULT_DOCKER = Path("/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker")
TARGET_CONTAINER = "janus_titan_core"
CANONICAL_REGISTRY_COMMIT = "481beaa0802d3691c15a86359ea6dc9c9ff3e6df"
GENESIS_E2E_COMMIT = "e56cc76fa300b90562b6adb95571a73fceb68cbe"
GITHUB_E2E_CERTIFICATE_SHA256 = "b518b38a46950e994768000236b13bff34b727069373e2356b056b7271312c7c"
PROTECTED_NAMES = {
    "storagenode", "janus_radio", "janus_bot_hub", "janus_nas_brain",
    "janus_ollama_bridge", "janus-ollama", "janus_bloodrayne",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run_cmd(argv, *, timeout=120, check=True) -> subprocess.CompletedProcess:
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError("command failed rc={0}: {1}: {2}".format(proc.returncode, " ".join(map(str, argv)), proc.stderr.strip()[:1000]))
    return proc


def docker_ps(docker: Path) -> Dict[str, str]:
    proc = run_cmd([str(docker), "ps", "-a", "--format", "{{.ID}}|{{.Names}}"], timeout=60)
    out: Dict[str, str] = {}
    for line in proc.stdout.splitlines():
        parts = line.strip().split("|", 1)
        if len(parts) == 2:
            out[parts[1]] = parts[0]
    return out


def docker_inspect(docker: Path, name: str) -> dict:
    proc = run_cmd([str(docker), "inspect", name], timeout=60)
    value = json.loads(proc.stdout)
    if not isinstance(value, list) or not value:
        raise RuntimeError("docker inspect returned no object for {0}".format(name))
    return value[0]


def http_ok(url: str, timeout=4.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= int(response.status) < 500
    except Exception:
        return False


def wait_health(urls, attempts=18, delay=3.0) -> Optional[str]:
    for _ in range(attempts):
        for url in urls:
            if http_ok(url):
                return url
        time.sleep(delay)
    return None


def wait_boot_receipt(path: Path, expected_sha: str, attempts=20, delay=2.0) -> dict:
    last_error = "boot receipt not present"
    for _ in range(attempts):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("module_sha256") != expected_sha:
                last_error = "boot receipt module SHA mismatch"
            elif value.get("status") != "LIVE_NAS_CORE_GUARD_ACTIVE":
                last_error = "boot receipt status not active"
            elif value.get("self_test", {}).get("status") != "PASS":
                last_error = "boot receipt self-test not PASS"
            elif value.get("live_nas_core_guard_enforced") is not True:
                last_error = "boot receipt guard flag not true"
            else:
                return value
        except Exception as exc:
            last_error = "{0}:{1}".format(exc.__class__.__name__, str(exc)[:160])
        time.sleep(delay)
    raise RuntimeError(last_error)


def atomic_install(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".new")
    shutil.copy2(str(source), str(temp))
    os.replace(str(temp), str(target))


def restore_target(target: Path, backup: Optional[Path]) -> None:
    if backup is not None and backup.exists():
        atomic_install(backup, target)
    else:
        try:
            target.unlink()
        except FileNotFoundError:
            pass


def protected_snapshot(ps: Dict[str, str]) -> Dict[str, str]:
    return {name: cid for name, cid in ps.items() if name in PROTECTED_NAMES}


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy JANUS Intent Sovereignty v1.2 to QNAP Titan live-module boundary.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--docker", type=Path, default=DEFAULT_DOCKER)
    parser.add_argument("--module", type=Path, default=Path(__file__).with_name(MODULE_NAME))
    parser.add_argument("--no-restart", action="store_true", help="Install only; do not certify live enforcement.")
    args = parser.parse_args()

    root = args.root.resolve()
    docker = args.docker
    module = args.module.resolve()
    target = root / TARGET_REL
    runtime = root / "runtime"
    boot_receipt_path = runtime / "intent_sovereignty_v1_2_boot.json"
    certificate_path = runtime / "JANUS-LIVE-NAS-INTENT-SOVEREIGNTY-v1.2-certificate.json"
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = root / "_backups" / "intent_sovereignty_v1_2" / timestamp
    backup_path: Optional[Path] = None

    state = {
        "schema": "janus.live_nas.intent_sovereignty.deployment_receipt.v1",
        "capsule_id": CAPSULE_ID,
        "started_at": utc_now(),
        "root": str(root),
        "target": str(target),
        "target_container": TARGET_CONTAINER,
        "status": "STARTED",
        "authority_delta": 0,
    }

    try:
        if not root.is_dir():
            raise RuntimeError("JANUS_ROOT_NOT_FOUND")
        if not docker.is_file():
            raise RuntimeError("QNAP_DOCKER_NOT_FOUND")
        if not module.is_file():
            raise RuntimeError("CAPSULE_MODULE_NOT_FOUND")
        py_compile.compile(str(module), doraise=True)
        module_sha = sha256_file(module)
        state["module_sha256"] = module_sha

        before = docker_ps(docker)
        if TARGET_CONTAINER not in before:
            raise RuntimeError("JANUS_TITAN_CORE_CONTAINER_NOT_FOUND")
        protected_before = protected_snapshot(before)
        state["protected_containers_before"] = protected_before

        if target.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / MODULE_NAME
            shutil.copy2(str(target), str(backup_path))
            state["backup"] = str(backup_path)
            state["previous_module_sha256"] = sha256_file(target)
        else:
            state["backup"] = None
            state["previous_module_sha256"] = None

        try:
            boot_receipt_path.unlink()
        except FileNotFoundError:
            pass
        atomic_install(module, target)
        installed_sha = sha256_file(target)
        if installed_sha != module_sha:
            raise RuntimeError("ATOMIC_INSTALL_SHA_MISMATCH")
        state["installed_module_sha256"] = installed_sha

        if args.no_restart:
            state["status"] = "STAGED_NOT_LIVE"
            state["live_nas_core_guard_enforced"] = False
            print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
            return 0

        run_cmd([str(docker), "restart", TARGET_CONTAINER], timeout=120)
        health_url = wait_health(["http://127.0.0.1:5000/ping", "http://127.0.0.1:5000/api/status"])
        if not health_url:
            raise RuntimeError("TITAN_HEALTH_NOT_RECOVERED")
        state["health_url"] = health_url

        boot = wait_boot_receipt(boot_receipt_path, module_sha)
        boot_sha = sha256_file(boot_receipt_path)
        state["boot_receipt_sha256"] = boot_sha
        logs = run_cmd([str(docker), "logs", "--since", "5m", "--tail", "300", TARGET_CONTAINER], timeout=60, check=False)
        log_text = (logs.stdout or "") + "\n" + (logs.stderr or "")
        marker_seen = "LIVE MODULE ONLINE: janus_intent_sovereignty_v1_2" in log_text
        state["loader_marker_seen"] = marker_seen

        after = docker_ps(docker)
        protected_after = protected_snapshot(after)
        state["protected_containers_after"] = protected_after
        state["protected_containers_unchanged"] = protected_before == protected_after
        if protected_before != protected_after:
            raise RuntimeError("PROTECTED_CONTAINER_ID_CHANGED_DURING_DEPLOY")

        inspect = docker_inspect(docker, TARGET_CONTAINER)
        certificate_core = {
            "schema": "janus.live_nas.intent_sovereignty.runtime_certificate.v1",
            "artifact_id": "JANUS-LIVE-NAS-INTENT-SOVEREIGNTY-v1.2-certificate",
            "issued_at": utc_now(),
            "status": "LIVE_NAS_CORE_GUARD_ACTIVE",
            "scope": "JANUS_TITAN_CORE_PROCESS_INPUT_FINAL_OUTPUT_GUARD",
            "canonical_guard": "JANUS-GOLDPROMPT-INTENT-CONTINUITY-AND-CONTEXT-BLEED-GUARD-v1.2",
            "canonical_registry_commit": CANONICAL_REGISTRY_COMMIT,
            "genesis_e2e_commit": GENESIS_E2E_COMMIT,
            "github_e2e_certificate_sha256": GITHUB_E2E_CERTIFICATE_SHA256,
            "module_path": str(target),
            "module_sha256": module_sha,
            "boot_receipt_sha256": boot_sha,
            "boot_self_test": boot.get("self_test"),
            "routes_covered": ["/api/janus/action", "/api/hrain/sync"],
            "target_container": TARGET_CONTAINER,
            "target_container_id": str(inspect.get("Id", ""))[:64],
            "target_image": str(inspect.get("Config", {}).get("Image", ""))[:200],
            "health_url": health_url,
            "loader_marker_seen": marker_seen,
            "protected_containers_unchanged": True,
            "live_nas_core_guard_enforced": True,
            "full_bound_face_transport_proven": False,
            "live_nas_runtime_enforced": False,
            "reason_full_gate_remains_open": "This certificate proves the live Titan process_input guard, not physical HRaiN/iNaiHR/DemiHead/Genesis packet-v3 transport on NAS.",
            "database_mutated_by_deploy": False,
            "runtime_config_read_by_deploy": False,
            "secrets_read_by_deploy": False,
            "containers_restarted_by_deploy": [TARGET_CONTAINER],
            "authority_delta": 0,
            "claim_boundaries": [
                "LIVE_NAS_CORE_GUARD_ACTIVE != FULL_BOUND_FACE_NAS_TRANSPORT_PROOF",
                "INTENT_ALIGNMENT != FACTUAL_CORRECTNESS",
                "INTENT_CONTINUITY != HUMAN_CONSENT",
            ],
        }
        certificate = dict(certificate_core)
        certificate["certificate_sha256"] = canonical_sha256(certificate_core)
        runtime.mkdir(parents=True, exist_ok=True)
        temp_cert = certificate_path.with_suffix(certificate_path.suffix + ".tmp")
        temp_cert.write_text(json.dumps(certificate, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(str(temp_cert), str(certificate_path))
        state.update({
            "status": "LIVE_NAS_CORE_GUARD_ACTIVE", "finished_at": utc_now(),
            "certificate_path": str(certificate_path), "certificate_sha256": certificate["certificate_sha256"],
            "live_nas_core_guard_enforced": True, "full_bound_face_transport_proven": False,
        })
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        state["status"] = "FAILED_ROLLBACK_ATTEMPTED"
        state["error"] = "{0}:{1}".format(exc.__class__.__name__, str(exc))
        try:
            restore_target(target, backup_path)
            if docker.is_file():
                run_cmd([str(docker), "restart", TARGET_CONTAINER], timeout=120, check=False)
            state["rollback"] = "ATTEMPTED"
        except Exception as rollback_exc:
            state["rollback"] = "FAILED:{0}:{1}".format(rollback_exc.__class__.__name__, str(rollback_exc))
        state["finished_at"] = utc_now()
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
