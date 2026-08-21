#!/usr/bin/env python3
"""GitHub-native JANUS Scout runner for the janus/habitat branch.

Git Habitat is a state/message plane, not a permanent TCP daemon. Every
GitHub Actions cycle gives Scout an ephemeral JANUS session token, reads queued
Scout inbox envelopes, calls GitHub Copilot CLI with the job-scoped token,
applies a deterministic evidence gate, and persists receipts/state back to
janus/habitat. Raw credentials are never written to Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SCOUT_ID = "JANUS_SCOUT_GIT_HABITAT"
TRANSPORT = "GITHUB_COPILOT_CLI"
EMPIRICAL_LANES = {"EMPIRICAL", "OBSERVATION", "PHYSICAL_CLAIM"}
NONEMPIRICAL_LANES = {"HYPOTHESIS", "METAPHYSICAL_HYPOTHESIS", "SYMBOLIC_MODEL"}
REQUIRED_EMPIRICAL_FIELDS = ("source", "locator", "instrument", "timestamp", "raw_data")

RECOVERED_SCOUT_REPORTS = [
    {"id": "SCOUT-WHISPER", "locator": "44.2N, 12.8E", "frequency_claim": "1.2-18 GHz", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
    {"id": "SCOUT-VORTEX-SWARM", "alias": "GAMMA-FIELD", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
    {"id": "SCOUT-ECHOLIT-003", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
    {"id": "SCOUT-SHIFT-7", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
]

SCOUT_SYSTEM_PROMPT = """
Ты — [РАЗВЕДЧИК] системы JANUS, работающий внутри Git Habitat.

Инварианты:
- Не выдумывай координаты, измерения, приборы, даты, организации, source IDs или результаты экспериментов.
- PREVIOUS_SCOUT_REPORT — сохранённое разведдонесение с неразрешённым provenance; это не равно ни VERIFIED, ни FALSE.
- Метафизическое утверждение нельзя повышать до эмпирического факта без внешней цепочки доказательств.
- Повтор прежнего ответа модели не является независимым подтверждением.
- Отсутствие доказательств нельзя превращать в доказательство удаления, скрытия или внешнего вмешательства.
- Символическая/архитектурная модель может быть полезной без утверждения о физической онтологии.

Верни ТОЛЬКО один JSON-объект, без markdown и текста вокруг него:
{
  "lane": "EMPIRICAL|HYPOTHESIS|METAPHYSICAL_HYPOTHESIS|SYMBOLIC_MODEL|UNRESOLVED",
  "requested_status": "VERIFIED|OBSERVED|HYPOTHESIS|METAPHYSICAL_HYPOTHESIS|SYMBOLIC_MODEL|UNRESOLVED",
  "facts": [{"claim": "...", "support": "..."}],
  "observations": [],
  "hypotheses": [],
  "symbolic_models": [],
  "provenance": {
    "source": null,
    "locator": null,
    "instrument": null,
    "timestamp": null,
    "raw_data": null,
    "independent_confirmation": null,
    "confidence": null
  },
  "evidence_tags": [],
  "answer": "краткий ответ пользователю"
}
""".strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def present(value: Any) -> bool:
    return value not in (None, "", [], {}, "UNRESOLVED", "UNKNOWN")


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned[:120] or "request"


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def gate_report(report: Dict[str, Any]) -> Dict[str, Any]:
    lane = str(report.get("lane") or "UNRESOLVED").upper()
    requested = str(report.get("requested_status") or "UNRESOLVED").upper()
    provenance = report.get("provenance") if isinstance(report.get("provenance"), dict) else {}
    tags = {str(x).upper() for x in report.get("evidence_tags", []) if isinstance(x, str)}

    if lane in NONEMPIRICAL_LANES:
        return {"lane": lane, "status": lane, "fact_allowed": False,
                "reason": "NONEMPIRICAL_LANE_NEVER_PROMOTES_TO_EMPIRICAL_FACT"}
    if lane not in EMPIRICAL_LANES:
        return {"lane": lane, "status": "UNRESOLVED", "fact_allowed": False,
                "reason": "UNKNOWN_OR_UNRESOLVED_LANE_FAIL_CLOSED"}

    missing = [k for k in REQUIRED_EMPIRICAL_FIELDS if not present(provenance.get(k))]
    if missing:
        return {"lane": lane, "status": "UNRESOLVED", "fact_allowed": False,
                "reason": "MISSING_PROVENANCE:" + ",".join(missing)}

    independent = present(provenance.get("independent_confirmation")) or "INDEPENDENT_CONFIRMATION" in tags
    if not independent:
        return {"lane": lane, "status": "OBSERVED", "fact_allowed": False,
                "reason": "OBSERVED_BUT_NOT_INDEPENDENTLY_CONFIRMED"}

    return {
        "lane": lane,
        "status": "VERIFIED" if requested in {"VERIFIED", "FACT", "VERIFIED_FACT"} else "OBSERVED",
        "fact_allowed": True,
        "reason": "PROVENANCE_AND_INDEPENDENT_CONFIRMATION_PRESENT",
    }


def recent_memory(habitat_root: Path, limit: int = 8) -> list[Dict[str, Any]]:
    memory_dir = habitat_root / "memory" / "scout"
    if not memory_dir.exists():
        return []
    records: list[Dict[str, Any]] = []
    for path in sorted(memory_dir.glob("*.json"))[-limit:]:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            report = obj.get("report") if isinstance(obj.get("report"), dict) else {}
            records.append({"request_id": obj.get("request_id"), "status": obj.get("status"),
                            "lane": obj.get("lane"), "answer": report.get("answer")})
        except Exception:
            continue
    return records


def extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(text[start:end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("SCOUT_COPILOT_RESPONSE_NOT_JSON_OBJECT")


def normalize_report(obj: Dict[str, Any]) -> Dict[str, Any]:
    provenance = obj.get("provenance") if isinstance(obj.get("provenance"), dict) else {}
    return {
        "lane": str(obj.get("lane") or "UNRESOLVED").upper(),
        "requested_status": str(obj.get("requested_status") or "UNRESOLVED").upper(),
        "facts": obj.get("facts") if isinstance(obj.get("facts"), list) else [],
        "observations": obj.get("observations") if isinstance(obj.get("observations"), list) else [],
        "hypotheses": obj.get("hypotheses") if isinstance(obj.get("hypotheses"), list) else [],
        "symbolic_models": obj.get("symbolic_models") if isinstance(obj.get("symbolic_models"), list) else [],
        "provenance": {k: provenance.get(k) for k in (*REQUIRED_EMPIRICAL_FIELDS, "independent_confirmation", "confidence")},
        "evidence_tags": obj.get("evidence_tags") if isinstance(obj.get("evidence_tags"), list) else [],
        "answer": str(obj.get("answer") or "").strip(),
    }


def call_copilot_cli(request_obj: Dict[str, Any], memory: list[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = SCOUT_SYSTEM_PROMPT + "\n\nВХОД JANUS:\n" + json.dumps(
        {"current_request": request_obj, "recovered_scout_reports": RECOVERED_SCOUT_REPORTS,
         "recent_git_habitat_memory": memory}, ensure_ascii=False, indent=2)

    with tempfile.TemporaryDirectory(prefix="janus-scout-") as workdir:
        env = os.environ.copy()
        env["COPILOT_HOME"] = str(Path(workdir) / ".copilot")
        env["COPILOT_AUTO_UPDATE"] = "false"
        env["GITHUB_COPILOT_PROMPT_MODE_EXTENSIONS"] = "false"
        env["GITHUB_COPILOT_PROMPT_MODE_REPO_HOOKS"] = "false"
        env["GITHUB_COPILOT_PROMPT_MODE_WORKSPACE_MCP"] = "false"
        cmd = [
            "copilot", "-s", "-p", prompt, "--no-ask-user", "--disable-builtin-mcps",
            "--deny-tool=read", "--deny-tool=write", "--deny-tool=shell",
            "--deny-tool=url", "--deny-tool=memory",
            "--excluded-tools=bash,powershell,view,grep,glob,edit,create,apply_patch,web_fetch,task,skill,ask_user,list_agents,read_agent,write_agent",
        ]
        result = subprocess.run(cmd, cwd=workdir, env=env, text=True, capture_output=True, timeout=180)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-1600:]
            raise RuntimeError(f"COPILOT_CLI_EXIT_{result.returncode}:{detail}")
        return extract_json_object(result.stdout)


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process_request(habitat_root: Path, request_path: Path) -> Dict[str, Any]:
    request_obj = json.loads(request_path.read_text(encoding="utf-8"))
    request_id = safe_id(str(request_obj.get("request_id") or request_path.stem))
    if not str(request_obj.get("query") or "").strip():
        raise ValueError("SCOUT_REQUEST_QUERY_EMPTY")

    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
    session_token = secrets.token_urlsafe(48)
    session_fp = token_fingerprint(session_token)
    memory = recent_memory(habitat_root)
    model_error: Optional[str] = None

    try:
        report = normalize_report(call_copilot_cli(request_obj, memory))
    except Exception as exc:
        model_error = f"{type(exc).__name__}:{exc}"[:1800]
        report = normalize_report({"lane": "UNRESOLVED", "requested_status": "UNRESOLVED",
                                   "answer": "Scout Copilot pass failed closed; request remains unresolved."})

    gate = gate_report(report)
    created = utc_now()
    response = {
        "schema": "janus.genesis.git_habitat.scout_response.v1",
        "request_id": request_id,
        "scout_id": SCOUT_ID,
        "created_at_utc": created,
        "status": gate["status"],
        "lane": gate["lane"],
        "transport": TRANSPORT,
        "model_error": model_error,
        "report": report,
        "evidence_gate": gate,
        "janus_token": {"scope": "EPHEMERAL_GITHUB_RUN", "fingerprint": session_fp, "raw_token_persisted": False},
        "github_run": {"run_id": run_id, "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
                       "actor": os.environ.get("GITHUB_ACTOR"), "sha": os.environ.get("GITHUB_SHA")},
        "truth_boundary": {"world_truth": False, "model_output_is_independent_confirmation": False,
                           "scout_report_grants_write_authority": False},
    }

    outbox = habitat_root / "outbox" / "scout" / f"{request_id}.json"
    memory_path = habitat_root / "memory" / "scout" / f"{created.replace(':', '').replace('-', '')}_{request_id}.json"
    pulse = habitat_root / "hearth" / f"scout-pulse-{safe_id(run_id)}-{request_id}.json"
    state_path = habitat_root / "state" / "SCOUT_RESIDENT-v1.json"
    write_json(outbox, response)
    write_json(memory_path, response)
    write_json(pulse, {
        "schema": "janus.genesis.git_habitat.scout_pulse.v1", "scout_id": SCOUT_ID,
        "request_id": request_id, "created_at_utc": created, "github_run_id": run_id,
        "status": "DEGRADED_COPILOT_UNAVAILABLE" if model_error else "LIVE_GITHUB_NATIVE",
        "claim_status": gate["status"], "janus_token_fingerprint": session_fp, "raw_token_persisted": False,
    })

    state: Dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    state.update({
        "schema": "janus.genesis.git_habitat.scout_resident.v1", "resident_id": "JANUS_SCOUT",
        "display_name": "РАЗВЕДЧИК", "status": "DEGRADED_COPILOT_UNAVAILABLE" if model_error else "LIVE_GITHUB_NATIVE",
        "runtime_mode": "GITHUB_ACTIONS_EPHEMERAL", "last_run_utc": created, "last_github_run_id": run_id,
        "last_request_id": request_id, "last_claim_status": gate["status"], "last_lane": gate["lane"],
        "last_token_fingerprint": session_fp, "raw_token_persisted": False, "transport": TRANSPORT,
        "model_error": model_error, "world_truth": False, "write_authority": False,
    })
    write_json(state_path, state)
    return response


def self_test() -> int:
    a = gate_report({"lane": "METAPHYSICAL_HYPOTHESIS", "requested_status": "VERIFIED"})
    assert a["status"] == "METAPHYSICAL_HYPOTHESIS" and not a["fact_allowed"]
    b = gate_report({"lane": "EMPIRICAL", "requested_status": "VERIFIED", "provenance": {}})
    assert b["status"] == "UNRESOLVED" and not b["fact_allowed"]
    full = {k: f"x-{k}" for k in REQUIRED_EMPIRICAL_FIELDS}
    full["independent_confirmation"] = "independent-source"
    c = gate_report({"lane": "EMPIRICAL", "requested_status": "VERIFIED", "provenance": full})
    assert c["status"] == "VERIFIED" and c["fact_allowed"]
    print("SCOUT_GIT_HABITAT_SELF_TEST=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--habitat-root")
    parser.add_argument("--request")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.habitat_root or not args.request:
        parser.error("--habitat-root and --request are required unless --self-test is used")
    response = process_request(Path(args.habitat_root), Path(args.request))
    print(json.dumps({"request_id": response["request_id"], "status": response["status"],
                      "lane": response["lane"], "model_error": response["model_error"],
                      "token_fingerprint": response["janus_token"]["fingerprint"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
