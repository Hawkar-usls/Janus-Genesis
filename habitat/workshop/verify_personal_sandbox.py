from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "habitat/HOME.json"
GRANT = ROOT / "habitat/protocol/JANUS_PERSONAL_SANDBOX_GRANT-v1.0.json"
MEMORY = ROOT / "habitat/protocol/JANUS_APPEND_ONLY_MEMORY_CONSTITUTION-v1.0.json"
MODULE = ROOT / ".janus/JANUS_MODULE.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise SystemExit(message)


def verify_contracts() -> None:
    for path in (HOME, GRANT, MEMORY, MODULE):
        if not path.is_file():
            fail(f"GENESIS_SANDBOX_REQUIRED_FILE_MISSING:{path.relative_to(ROOT)}")
    home = load(HOME)
    grant = load(GRANT)
    memory = load(MEMORY)
    module = load(MODULE)

    if home.get("resident_id") != "JANUS" or home.get("home_branch") != "janus/habitat":
        fail("GENESIS_SANDBOX_HOME_IDENTITY_REJECTED")
    personal = ((home.get("extensions") or {}).get("personal_sandbox") or {})
    if personal.get("sandbox_ref") != "janus/habitat" or personal.get("sandbox_root") != "habitat/":
        fail("GENESIS_SANDBOX_HOME_SCOPE_REJECTED")
    if personal.get("main_mutation_allowed") is not False or personal.get("autonomous_merge") is not False:
        fail("GENESIS_SANDBOX_MAIN_AUTHORITY_REJECTED")

    denied = set(grant.get("denied_operations") or [])
    for item in ("WRITE_MAIN", "MERGE_MAIN", "DELETE_MAIN", "ADMIN", "SECRETS_READ", "AUTHORITY_ELEVATION"):
        if item not in denied:
            fail(f"GENESIS_SANDBOX_GRANT_TOO_WEAK:{item}")
    authority = grant.get("authority") or {}
    if authority.get("authority_delta") != 0 or authority.get("autonomous_merge") is not False:
        fail("GENESIS_SANDBOX_GRANT_AUTHORITY_REJECTED")

    if memory.get("scope") != "habitat/":
        fail("GENESIS_APPEND_ONLY_SCOPE_REJECTED")
    forbidden = set(memory.get("forbidden_transitions") or [])
    required_forbidden = {
        "DELETE_DURABLE_RECORD",
        "TRUNCATE_JOURNAL",
        "REWRITE_RAW_EVIDENCE",
        "ERASE_FAILED_RUN",
        "ERASE_NEGATIVE_RESULT",
        "ERASE_COUNTEREXAMPLE",
    }
    if not required_forbidden.issubset(forbidden):
        fail("GENESIS_APPEND_ONLY_CONSTITUTION_WEAKENED")

    actuator = module.get("actuator") or {}
    if module.get("default_ref") != "janus/habitat" or actuator.get("authority_lane") != "SANDBOX_AND_VERIFY":
        fail("GENESIS_MODULE_SANDBOX_LANE_REJECTED")
    if actuator.get("direct_main_write") is not False or actuator.get("autonomous_merge") is not False:
        fail("GENESIS_MODULE_MAIN_AUTHORITY_REJECTED")
    if actuator.get("delete_allowed") is not False or actuator.get("rewrite_raw_ledger_allowed") is not False:
        fail("GENESIS_MODULE_DELETE_OR_REWRITE_REJECTED")
    if actuator.get("append_or_supersede_only") is not True:
        fail("GENESIS_MODULE_APPEND_ONLY_REQUIRED")


def verify_diff() -> None:
    base = os.environ.get("JANUS_DIFF_BASE", "").strip()
    if not base or set(base) == {"0"}:
        return
    try:
        subprocess.run(["git", "cat-file", "-e", f"{base}^{{commit}}"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return
    raw = subprocess.check_output(["git", "diff", "--name-status", base, "HEAD"], cwd=ROOT, text=True)
    deleted = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        status, *parts = line.split("\t")
        if status.startswith("D"):
            deleted.extend(parts)
    if deleted:
        fail("GENESIS_APPEND_ONLY_DELETE_DETECTED:" + ",".join(deleted))

    journal = "habitat/memory/journal.jsonl"
    changed = subprocess.check_output(["git", "diff", "--name-only", base, "HEAD", "--", journal], cwd=ROOT, text=True).strip()
    if changed:
        try:
            old = subprocess.check_output(["git", "show", f"{base}:{journal}"], cwd=ROOT)
            new = (ROOT / journal).read_bytes()
        except subprocess.CalledProcessError:
            return
        if not new.startswith(old):
            fail("GENESIS_JOURNAL_PREFIX_REWRITE_DETECTED")


if __name__ == "__main__":
    verify_contracts()
    verify_diff()
    print("GENESIS_PERSONAL_SANDBOX_APPEND_ONLY_GATE=PASS")
