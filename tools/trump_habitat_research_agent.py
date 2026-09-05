#!/usr/bin/env python3
"""Bounded GitHub-native JANUS research lane for TRUMP/P-vs-NP work.

The lane may inspect a checked-out TRUMP repository but is forbidden to modify it.
It writes only a structured research packet into the Janus_Genesis Git Habitat.
Model output is never promoted to proof by this script.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

LANE_ID = "JANUS_TRUMP_GIT_RESEARCH_LANE"

SYSTEM_PROMPT = r"""
Ты — JANUS TRUMP Research Lane. Работаешь как bounded falsification-first исследователь.
Ты можешь читать только локально checkout-нутый репозиторий TRUMP и переданный request JSON.
Ты НЕ имеешь права изменять код, создавать коммиты, открывать PR, писать в main или объявлять P=NP.

Обязательные эпистемические правила:
- P_VS_NP=OPEN и SAT_IN_P=NOT_PROVED, если только внешний формальный verifier не доказал обратное.
- MODEL_OUTPUT_IS_NOT_PROOF.
- AGREEMENT_WITH_HUMAN_OR_ANOTHER_MODEL_IS_NOT_INDEPENDENT_CONFIRMATION.
- FINITE_NO_FIND_IS_NOT_A_UNIVERSAL_THEOREM.
- Любая предложенная мутация/контрпример должна сопровождаться replayable test idea.
- Не расширяй frozen family, если request это запрещает.
- Не меняй frozen operators/gates, если request это запрещает.
- Предпочитай явный минимальный контрпример или локальный obstruction абстрактному оптимизму.

Изучи request и релевантные файлы текущего checkout. Верни ТОЛЬКО один JSON-объект:
{
  "lane": "TRUMP_FALSIFICATION_RESEARCH",
  "status": "HYPOTHESIS",
  "repo_observations": [
    {"claim": "...", "path": "...", "why_relevant": "..."}
  ],
  "candidate_mechanisms": [
    {
      "name": "...",
      "targets_transition": "BCE|PURE|OTHER",
      "construction": "...",
      "why_it_might_work": "...",
      "accidental_simplification_risk": "...",
      "minimal_replay_test": "..."
    }
  ],
  "rejected_ideas": [
    {"idea": "...", "reason": "..."}
  ],
  "recommended_next_gate": "...",
  "proof_claim": false,
  "p_vs_np": "OPEN",
  "sat_in_p": "NOT_PROVED",
  "answer": "краткий итог на русском"
}
""".strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def extract_json(text: str) -> Dict[str, Any]:
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
    raise ValueError("TRUMP_RESEARCH_RESPONSE_NOT_JSON")


def extract_copilot_jsonl(stdout: str) -> Dict[str, Any]:
    final: list[str] = []
    deltas: list[str] = []
    generic: list[str] = []
    for raw in stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        et = str(event.get("type") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if et == "assistant.message" and isinstance(data.get("content"), str):
            final.append(data["content"])
        elif et == "assistant.message_delta":
            delta = data.get("deltaContent", data.get("delta"))
            if isinstance(delta, str):
                deltas.append(delta)
        for value in data.values():
            if isinstance(value, str) and "{" in value and "proof_claim" in value:
                generic.append(value)
    for candidate in reversed(final):
        try:
            return extract_json(candidate)
        except Exception:
            pass
    if deltas:
        try:
            return extract_json("".join(deltas))
        except Exception:
            pass
    for candidate in reversed(generic):
        try:
            return extract_json(candidate)
        except Exception:
            pass
    return extract_json(stdout)


def normalize(report: Dict[str, Any]) -> Dict[str, Any]:
    report = dict(report)
    report["lane"] = "TRUMP_FALSIFICATION_RESEARCH"
    report["status"] = "HYPOTHESIS"
    report["proof_claim"] = False
    report["p_vs_np"] = "OPEN"
    report["sat_in_p"] = "NOT_PROVED"
    for key in ("repo_observations", "candidate_mechanisms", "rejected_ideas"):
        if not isinstance(report.get(key), list):
            report[key] = []
    if not isinstance(report.get("recommended_next_gate"), str):
        report["recommended_next_gate"] = "UNRESOLVED"
    if not isinstance(report.get("answer"), str):
        report["answer"] = "UNRESOLVED"
    return report


def run_copilot(request: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    prompt = SYSTEM_PROMPT + "\n\nREQUEST JSON:\n" + json.dumps(request, ensure_ascii=False, indent=2)
    with tempfile.TemporaryDirectory(prefix="janus-trump-") as td:
        env = os.environ.copy()
        env.update({
            "COPILOT_HOME": str(Path(td) / ".copilot"),
            "COPILOT_AUTO_UPDATE": "false",
            "GITHUB_COPILOT_PROMPT_MODE_EXTENSIONS": "false",
            "GITHUB_COPILOT_PROMPT_MODE_REPO_HOOKS": "false",
            "GITHUB_COPILOT_PROMPT_MODE_WORKSPACE_MCP": "false",
        })
        cmd = [
            "copilot", "-p", prompt,
            "--output-format=json",
            "--no-ask-user",
            "--no-color",
            "--no-custom-instructions",
            "--no-remote",
            "--no-remote-export",
            "--disable-builtin-mcps",
            "--deny-tool=write",
            "--deny-tool=shell",
            "--deny-tool=url",
            "--deny-tool=memory",
            "--excluded-tools=bash,powershell,edit,create,apply_patch,web_fetch,task,skill,ask_user,list_agents,read_agent,write_agent",
        ]
        cp = subprocess.run(
            cmd,
            cwd=str(workspace),
            env=env,
            text=True,
            capture_output=True,
            timeout=240,
        )
        if cp.returncode != 0:
            detail = (cp.stderr or cp.stdout or "").strip()[-1800:]
            raise RuntimeError(f"COPILOT_CLI_EXIT_{cp.returncode}:{detail}")
        return normalize(extract_copilot_jsonl(cp.stdout))


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--habitat-root", required=True)
    args = ap.parse_args()

    request_path = Path(args.request)
    workspace = Path(args.workspace)
    habitat = Path(args.habitat_root)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request_id = re.sub(r"[^A-Za-z0-9._-]+", "_", str(request.get("request_id") or request_path.stem))[:120]

    if request.get("status") != "QUEUED":
        raise ValueError("TRUMP_REQUEST_NOT_QUEUED")
    if request.get("purpose") != "PARALLEL_TRUMP_CODE_RESEARCH":
        raise ValueError("TRUMP_REQUEST_WRONG_PURPOSE")

    report = run_copilot(request, workspace)
    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1",
        "lane_id": LANE_ID,
        "request_id": request_id,
        "processed_at_utc": utc_now(),
        "source_repo": request.get("source_repo"),
        "source_branch": request.get("source_branch"),
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "authority": "RESEARCH_HYPOTHESIS_ONLY",
        "truth_boundary": {
            "model_output_is_proof": False,
            "model_output_is_independent_confirmation": False,
            "p_vs_np": "OPEN",
            "sat_in_p": "NOT_PROVED"
        },
        "report": report,
    }

    outbox = habitat / "outbox" / "trump" / f"{request_id}.json"
    memory = habitat / "memory" / "trump" / f"{utc_now().replace(':', '-')}_{request_id}.json"
    write_json(outbox, receipt)
    write_json(memory, receipt)
    print(f"TRUMP_RESEARCH_RECEIPT={outbox}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
