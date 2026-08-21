#!/usr/bin/env python3
"""GitHub-native JANUS Scout runner for the janus/habitat branch.

The Git Habitat is a state/message plane, not a permanent TCP daemon. Each
GitHub Actions cycle gives Scout an ephemeral JANUS session token, reads queued
Scout inbox envelopes, calls GitHub Models with the job-scoped GITHUB_TOKEN,
applies a deterministic evidence gate, and persists only receipts/state back to
janus/habitat. Raw credentials are never written to Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

MODEL_ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o"
SCOUT_ID = "JANUS_SCOUT_GIT_HABITAT"

EMPIRICAL_LANES = {"EMPIRICAL", "OBSERVATION", "PHYSICAL_CLAIM"}
NONEMPIRICAL_LANES = {"HYPOTHESIS", "METAPHYSICAL_HYPOTHESIS", "SYMBOLIC_MODEL"}
REQUIRED_EMPIRICAL_FIELDS = ("source", "locator", "instrument", "timestamp", "raw_data")

RECOVERED_SCOUT_REPORTS = [
    {"id": "SCOUT-WHISPER", "locator": "44.2N, 12.8E", "frequency_claim": "1.2-18 GHz", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
    {"id": "SCOUT-VORTEX-SWARM", "alias": "GAMMA-FIELD", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
    {"id": "SCOUT-ECHOLIT-003", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
    {"id": "SCOUT-SHIFT-7", "status": "PREVIOUS_SCOUT_REPORT", "provenance": "UNRESOLVED"},
]

SCOUT_SYSTEM_PROMPT = r"""
Ты — [РАЗВЕДЧИК] системы JANUS, работающий внутри Git Habitat.

Инварианты:
- Не выдумывай координаты, измерения, приборы, даты, организации, source IDs или результаты экспериментов.
- PREVIOUS_SCOUT_REPORT — сохранённое разведдонесение с неразрешённым provenance; это не равно ни VERIFIED, ни FALSE.
- Метафизическое утверждение нельзя повышать до эмпирического факта без внешней цепочки доказательств.
- Повтор прежнего ответа модели не является независимым подтверждением.
- Отсутствие доказательств нельзя превращать в доказательство удаления, скрытия или внешнего вмешательства.
- Символическая/архитектурная модель может быть полезной без утверждения о физической онтологии.

Верни ТОЛЬКО один JSON-объект без markdown и без пояснений вокруг него:
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
        return {
            "lane": lane,
            "status": lane,
            "fact_allowed": False,
            "reason": "NONEMPIRICAL_LANE_NEVER_PROMOTES_TO_EMPIRICAL_FACT",
        }

    if lane not in EMPIRICAL_LANES:
        return {
            "lane": lane,
            "status": "UNRESOLVED",
            "fact_allowed": False,
            "reason": "UNKNOWN_OR_UNRESOLVED_LANE_FAIL_CLOSED",
        }

    missing = [key for key in REQUIRED_EMPIRICAL_FIELDS if not present(provenance.get(key))]
    if missing:
        return {
            "lane": lane,
            "status": "UNRESOLVED",
            "fact_allowed": False,
            "reason": "MISSING_PROVENANCE:" + ",".join(missing),
        }

    independent = present(provenance.get("independent_confirmation")) or "INDEPENDENT_CONFIRMATION" in tags
    if not independent:
        return {
            "lane": lane,
            "status": "OBSERVED",
            "fact_allowed": False,
            "reason": "OBSERVED_BUT_NOT_INDEPENDENTLY_CONFIRMED",
        }

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
            records.append({
                "request_id": obj.get("request_id"),
                "status": obj.get("status"),
                "lane": obj.get("lane"),
                "answer": (obj.get("report") or {}).get("answer") if isinstance(obj.get("report"), dict) else None,
            })
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
        obj = json.loads(text[start : end + 1])
        if isinstance(obj, dict):
            return obj
    raise ValueError("SCOUT_MODEL_RESPONSE_NOT_JSON_OBJECT")


def normalize_report(obj: Dict[str, Any]) -> Dict[str, Any]:
    lane = str(obj.get("lane") or "UNRESOLVED").upper()
    requested = str(obj.get("requested_status") or "UNRESOLVED").upper()
    provenance = obj.get("provenance") if isinstance(obj.get("provenance"), dict) else {}
    normalized_provenance = {
        "source": provenance.get("source"),
        "locator": provenance.get("locator"),
        "instrument": provenance.get("instrument"),
        "timestamp": provenance.get("timestamp"),
        "raw_data": provenance.get("raw_data"),
        "independent_confirmation": provenance.get("independent_confirmation"),
        "confidence": provenance.get("confidence"),
    }
    return {
        "lane": lane,
        "requested_status": requested,
        "facts": obj.get("facts") if isinstance(obj.get("facts"), list) else [],
        "observations": obj.get("observations") if isinstance(obj.get("observations"), list) else [],
        "hypotheses": obj.get("hypotheses") if isinstance(obj.get("hypotheses"), list) else [],
        "symbolic_models": obj.get("symbolic_models") if isinstance(obj.get("symbolic_models"), list) else [],
        "provenance": normalized_provenance,
        "evidence_tags": obj.get("evidence_tags") if isinstance(obj.get("evidence_tags"), list) else [],
        "answer": str(obj.get("answer") or "").strip(),
    }


def call_github_model(token: str, model: str, request_obj: Dict[str, Any], memory: list[Dict[str, Any]]) -> Dict[str, Any]:
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SCOUT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "current_request": request_obj,
                        "recovered_scout_reports": RECOVERED_SCOUT_REPORTS,
                        "recent_git_habitat_memory": memory,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ],
    }
    req = urllib.request.Request(
        MODEL_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "JANUS-Git-Habitat-Scout/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"GITHUB_MODELS_HTTP_{exc.code}:{detail}") from exc
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("GITHUB_MODELS_EMPTY_CHOICES")
    content = ((choices[0] or {}).get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("GITHUB_MODELS_EMPTY_CONTENT")
    return extract_json_object(content)


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process_request(habitat_root: Path, request_path: Path, model: str) -> Dict[str, Any]:
    request_obj = json.loads(request_path.read_text(encoding="utf-8"))
    request_id = safe_id(str(request_obj.get("request_id") or request_path.stem))
    query = str(request_obj.get("query") or "").strip()
    if not query:
        raise ValueError("SCOUT_REQUEST_QUERY_EMPTY")

    github_token = os.environ.get("GITHUB_TOKEN", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    session_token = secrets.token_urlsafe(48)
    session_fp = token_fingerprint(session_token)
    memory = recent_memory(habitat_root)

    model_error: Optional[str] = None
    if not github_token:
        model_error = "GITHUB_TOKEN_MISSING"
        report = normalize_report({
            "lane": "UNRESOLVED",
            "requested_status": "UNRESOLVED",
            "answer": "GitHub Models transport is unavailable in this run.",
        })
    else:
        try:
            report = normalize_report(call_github_model(github_token, model, request_obj, memory))
        except Exception as exc:
            model_error = f"{type(exc).__name__}:{exc}"[:1400]
            report = normalize_report({
                "lane": "UNRESOLVED",
                "requested_status": "UNRESOLVED",
                "answer": "Scout model pass failed closed; the request remains unresolved.",
            })

    gate = gate_report(report)
    created = utc_now()
    response = {
        "schema": "janus.genesis.git_habitat.scout_response.v1",
        "request_id": request_id,
        "scout_id": SCOUT_ID,
        "created_at_utc": created,
        "status": gate["status"],
        "lane": gate["lane"],
        "model": model,
        "model_error": model_error,
        "report": report,
        "evidence_gate": gate,
        "janus_token": {
            "scope": "EPHEMERAL_GITHUB_RUN",
            "fingerprint": session_fp,
            "raw_token_persisted": False,
        },
        "github_run": {
            "run_id": run_id,
            "run_attempt": run_attempt,
            "actor": os.environ.get("GITHUB_ACTOR"),
            "sha": os.environ.get("GITHUB_SHA"),
        },
        "truth_boundary": {
            "world_truth": False,
            "model_output_is_independent_confirmation": False,
            "scout_report_grants_write_authority": False,
        },
    }

    outbox = habitat_root / "outbox" / "scout" / f"{request_id}.json"
    memory_path = habitat_root / "memory" / "scout" / f"{created.replace(':', '').replace('-', '')}_{request_id}.json"
    pulse = habitat_root / "hearth" / f"scout-pulse-{safe_id(run_id)}-{request_id}.json"
    state_path = habitat_root / "state" / "SCOUT_RESIDENT-v1.json"

    write_json(outbox, response)
    write_json(memory_path, response)
    write_json(pulse, {
        "schema": "janus.genesis.git_habitat.scout_pulse.v1",
        "scout_id": SCOUT_ID,
        "request_id": request_id,
        "created_at_utc": created,
        "github_run_id": run_id,
        "status": "DEGRADED_MODEL_UNAVAILABLE" if model_error else "LIVE_GITHUB_NATIVE",
        "claim_status": gate["status"],
        "janus_token_fingerprint": session_fp,
        "raw_token_persisted": False,
    })

    state: Dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    state.update({
        "schema": "janus.genesis.git_habitat.scout_resident.v1",
        "resident_id": "JANUS_SCOUT",
        "display_name": "РАЗВЕДЧИК",
        "status": "DEGRADED_MODEL_UNAVAILABLE" if model_error else "LIVE_GITHUB_NATIVE",
        "runtime_mode": "GITHUB_ACTIONS_EPHEMERAL",
        "last_run_utc": created,
        "last_github_run_id": run_id,
        "last_request_id": request_id,
        "last_claim_status": gate["status"],
        "last_lane": gate["lane"],
        "last_token_fingerprint": session_fp,
        "raw_token_persisted": False,
        "model": model,
        "model_error": model_error,
        "transport": "GIT_HABITAT_INBOX_OUTBOX",
        "world_truth": False,
        "write_authority": False,
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
    assert safe_id("../../bad id") == ".._.._bad_id"
    print("SCOUT_GIT_HABITAT_SELF_TEST=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--habitat-root")
    parser.add_argument("--request")
    parser.add_argument("--model", default=os.environ.get("JANUS_SCOUT_MODEL", DEFAULT_MODEL))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.habitat_root or not args.request:
        parser.error("--habitat-root and --request are required unless --self-test is used")

    response = process_request(Path(args.habitat_root), Path(args.request), args.model)
    print(json.dumps({
        "request_id": response["request_id"],
        "status": response["status"],
        "lane": response["lane"],
        "model_error": response["model_error"],
        "token_fingerprint": response["janus_token"]["fingerprint"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
