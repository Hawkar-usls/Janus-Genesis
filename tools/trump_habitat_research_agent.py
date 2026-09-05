#!/usr/bin/env python3
"""Bounded GitHub-native JANUS research lane for TRUMP/P-vs-NP work.

The lane may inspect a checked-out TRUMP repository but is forbidden to modify it.
It writes only a structured research packet into the Janus_Genesis Git Habitat.
Copilot is optional: quota/provider failures fall back to a deterministic,
replayable R50G24 mutation search over the frozen 30-skeleton family.
No output from this lane is promoted to proof.
"""

from __future__ import annotations

import argparse
import importlib
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

LANE_ID = "JANUS_TRUMP_GIT_RESEARCH_LANE"
MAX_DETERMINISTIC_TRIALS = 4000
MAX_STRONG_CANDIDATES = 8
MAX_NEAR_MISSES = 12

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
            detail = (cp.stderr or cp.stdout or "").strip()[-2400:]
            raise RuntimeError(f"COPILOT_CLI_EXIT_{cp.returncode}:{detail}")
        return normalize(extract_copilot_jsonl(cp.stdout))


def formula_variables(formula) -> list[int]:
    return sorted({abs(int(lit)) for clause in formula for lit in clause})


def is_bipolar_formula(formula) -> bool:
    signs: dict[int, set[int]] = {}
    for clause in formula:
        for raw in clause:
            lit = int(raw)
            signs.setdefault(abs(lit), set()).add(1 if lit > 0 else -1)
    return bool(signs) and all(s == {-1, 1} for s in signs.values())


def clause_json(clause) -> list[int]:
    return [int(x) for x in clause]


def deterministic_r50g24(request: Dict[str, Any], workspace: Path, provider_error: str) -> Dict[str, Any]:
    """Replay the frozen R50G23 machinery and search minimal additive mutations.

    This is intentionally narrow. It does not search arbitrary CNF space and does
    not alter R47J. For each of the frozen 30 skeletons it extracts R50G23's own
    first-transition debt, then tests one added binary clause containing the
    required counter-polarity literal. If no strong survivor is found, it spends
    the remaining bounded budget on ternary clauses. A strong candidate must keep
    the same-pivot R47J macro replay valid and leave a nonempty bipolar stalled
    R33 residual rather than merely moving BCE/PURE elsewhere.
    """
    exp = workspace / "experiments"
    if not exp.is_dir():
        raise RuntimeError(f"TRUMP_EXPERIMENTS_MISSING:{exp}")
    for p in (str(workspace), str(exp)):
        if p not in sys.path:
            sys.path.insert(0, p)

    r50g23 = importlib.import_module(
        "janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt"
    )
    r33 = r50g23.r33
    r47j = r50g23.r47j
    pivot = int(r50g23.PIVOT)
    skeletons = r50g23.clean_skeletons_from_frozen_r50g22()
    if len(skeletons) != 30:
        raise AssertionError(("R50G24_FROZEN_SKELETON_COUNT_DRIFT", len(skeletons)))

    strong: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    rejected_counts: dict[str, int] = {
        "r47j_candidate_missing": 0,
        "r47j_replay_fail": 0,
        "same_first_transition": 0,
        "solved_or_empty_after_r33": 0,
        "nonbipolar_residual": 0,
    }
    trials = 0

    def evaluate(item: Dict[str, Any], base_audit: Dict[str, Any], added_clause: tuple[int, ...]) -> None:
        nonlocal trials
        if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
            return
        source = r50g23.canon(item["source"])
        if tuple(added_clause) in source:
            return
        trials += 1
        mutated = r50g23.canon(list(source) + [tuple(added_clause)])
        candidate = r47j.macro_candidate_fixpoint(mutated, pivot)
        if candidate is None:
            rejected_counts["r47j_candidate_missing"] += 1
            return
        replay = r47j.independent_fixpoint_macro_replay(mutated, candidate)
        if not replay.get("pass"):
            rejected_counts["r47j_replay_fail"] += 1
            return

        forced = r50g23.canon(candidate["DP"]["transformed"])
        reduced = r33.simplify(forced)
        final_formula = r50g23.canon(reduced["final_formula"])
        history = reduced.get("history", [])
        labels = ["R33:" + str(rec.get("rule")) for rec in history]
        first_label = labels[0] if labels else str(reduced.get("terminal"))
        base_first = str(base_audit["transition_labels"][0])
        first_changed = first_label != base_first
        stalled_nonempty = reduced.get("terminal") == "STALLED_STACK_LEAN_CORE" and bool(final_formula)
        bipolar = is_bipolar_formula(final_formula) if final_formula else False

        row = {
            "spec": item["spec"],
            "source_hash": item["source_hash"],
            "base_first_transition": base_first,
            "base_debt": base_audit["first_transition_direct_blocking_debt"],
            "added_clause": clause_json(added_clause),
            "mutated_source_CLV": list(r33.measure(mutated)),
            "forced_DP_CLV": list(r33.measure(forced)),
            "R33_terminal": reduced.get("terminal"),
            "R33_transition_labels": labels,
            "R33_final_CLV": list(r33.measure(final_formula)),
            "first_transition_changed": first_changed,
            "nonempty_stalled_residual": stalled_nonempty,
            "bipolar_residual": bipolar,
            "r47j_replay_pass": True,
        }
        if stalled_nonempty and bipolar:
            row["classification"] = "STRONG_NONEMPTY_BIPOLAR_RESIDUAL_CANDIDATE"
            strong.append(row)
            return
        if not first_changed:
            rejected_counts["same_first_transition"] += 1
        elif not final_formula or reduced.get("terminal") != "STALLED_STACK_LEAN_CORE":
            rejected_counts["solved_or_empty_after_r33"] += 1
        elif not bipolar:
            rejected_counts["nonbipolar_residual"] += 1
        if first_changed and len(near) < MAX_NEAR_MISSES:
            row["classification"] = "FIRST_TRANSITION_BROKEN_BUT_STRONG_GATE_NOT_MET"
            near.append(row)

    audits: list[tuple[Dict[str, Any], Dict[str, Any], int, list[int]]] = []
    for item in skeletons:
        audit = r50g23.audit_one_skeleton(item)
        debt = audit["first_transition_direct_blocking_debt"]
        req = debt.get("required_literal")
        if req is None:
            continue
        required_literal = int(req)
        vars_ = [v for v in formula_variables(item["source"]) if v != abs(required_literal)]
        audits.append((item, audit, required_literal, vars_))

    # Minimal additive debt first: exactly one binary clause containing the
    # required opposite-polarity literal and one already-existing variable.
    for item, audit, req, vars_ in audits:
        for v in vars_:
            for partner in (v, -v):
                evaluate(item, audit, tuple(sorted((req, partner))))
                if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                    break
            if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                break
        if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
            break

    # Only if the one-clause/binary debt did not produce a survivor, spend the
    # remaining budget on one ternary clause. This still does not expand the
    # frozen skeleton family; it is a controlled mutation of each frozen source.
    if not strong and trials < MAX_DETERMINISTIC_TRIALS:
        for item, audit, req, vars_ in audits:
            for a, b in itertools.combinations(vars_, 2):
                for sa in (a, -a):
                    for sb in (b, -b):
                        clause = tuple(sorted((req, sa, sb)))
                        if any(-x in clause for x in clause):
                            continue
                        evaluate(item, audit, clause)
                        if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                            break
                    if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                        break
                if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                    break
            if trials >= MAX_DETERMINISTIC_TRIALS or len(strong) >= MAX_STRONG_CANDIDATES:
                break

    mechanisms = []
    for idx, row in enumerate(strong[:5], 1):
        debt = row["base_debt"]
        mechanisms.append({
            "name": f"R50G24_DETERMINISTIC_SURVIVOR_{idx}",
            "targets_transition": "BCE" if "BLOCK" in str(debt.get("debt_class", "")) else "PURE",
            "construction": f"Add exactly one clause {row['added_clause']} to frozen skeleton {row['spec']} before the same-pivot R47J replay.",
            "why_it_might_work": "Direct replay changed the collapse path and left R33 at a nonempty bipolar stalled residual while R47J independent replay still passed.",
            "accidental_simplification_risk": "Candidate status only: full R50G24 preregistered replay and downstream RUP/restart analysis are still required.",
            "minimal_replay_test": "Rebuild the named frozen skeleton, add only the recorded clause, run R47J pivot 1, replay the macro independently, then run R33 and assert STALLED_STACK_LEAN_CORE, nonempty final CNF, and both polarities for every residual variable.",
            "receipt": row,
        })

    if strong:
        recommended = "R50G24_REPLAY_AND_PREREGISTER_DETERMINISTIC_NONEMPTY_BIPOLAR_SURVIVOR"
        answer = (
            f"Детерминированный fallback проверил {trials} минимальных controlled mutations и нашёл "
            f"{len(strong)} кандидатов, где same-pivot R47J replay проходит, а R33 оставляет непустое "
            "биполярное stalled-ядро. Это кандидаты для независимого R50G24 replay, не доказательство P=NP."
        )
    else:
        recommended = "R50G24_PAIRWISE_COUNTERPOLARITY_CLOSURE_AFTER_SINGLE_CLAUSE_NEGATIVE"
        answer = (
            f"Детерминированный fallback проверил {trials} одно-клаузных controlled mutations и сильного "
            "непустого биполярного residual core не нашёл. Следующий честный debt — парное counterpolarity "
            "closure без расширения frozen 30. Это конечный отрицательный результат, не универсальная теорема."
        )

    return normalize({
        "engine": "DETERMINISTIC_R50G24_MUTATION_LAB",
        "provider_fallback_reason": provider_error[-1200:],
        "repo_observations": [
            {
                "claim": "Frozen R50G23 skeleton population replayed through repository code.",
                "path": "experiments/janus_trump_r50g23_direct5_skeleton_r47j_collapse_cascade_anti_collapse_debt.py",
                "why_relevant": "The fallback imports the canonical frozen selector, R47J replay, R33 simplifier and first-transition debt extractor rather than reimplementing their semantics."
            },
            {
                "claim": f"Bounded mutation trials executed: {trials}; strong candidates: {len(strong)}.",
                "path": "runtime-only",
                "why_relevant": "Every tested mutation is an additive change to one of the same frozen 30 sources; no new family member generator is introduced."
            }
        ],
        "candidate_mechanisms": mechanisms,
        "near_misses": near,
        "rejected_summary": rejected_counts,
        "rejected_ideas": [
            {
                "idea": "Treat Copilot quota failure as research failure.",
                "reason": "Provider availability is orthogonal to the replayable SAT experiment; deterministic fallback preserves the research lane."
            },
            {
                "idea": "Count a first-transition change alone as PASS.",
                "reason": "A mutation can merely move BCE/PURE or solve by another local rule; strong status additionally requires a nonempty bipolar STALLED_STACK_LEAN_CORE after R33."
            }
        ],
        "deterministic_trial_count": trials,
        "strong_candidate_count": len(strong),
        "strong_candidates": strong,
        "recommended_next_gate": recommended,
        "answer": answer,
    })


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

    provider_error = ""
    engine = "COPILOT_READ_ONLY"
    try:
        report = run_copilot(request, workspace)
    except Exception as exc:
        provider_error = f"{type(exc).__name__}:{exc}"
        print("TRUMP_COPILOT_UNAVAILABLE_FALLING_BACK_DETERMINISTIC")
        print(provider_error[-1200:])
        report = deterministic_r50g24(request, workspace, provider_error)
        engine = "DETERMINISTIC_R50G24_MUTATION_LAB"

    receipt = {
        "schema": "janus.genesis.trump_research_receipt.v1_1",
        "lane_id": LANE_ID,
        "request_id": request_id,
        "processed_at_utc": utc_now(),
        "source_repo": request.get("source_repo"),
        "source_branch": request.get("source_branch"),
        "source_commit": os.environ.get("TRUMP_SOURCE_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "engine": engine,
        "provider_error_observed": bool(provider_error),
        "authority": "RESEARCH_HYPOTHESIS_ONLY",
        "truth_boundary": {
            "model_output_is_proof": False,
            "model_output_is_independent_confirmation": False,
            "deterministic_finite_search_is_universal_proof": False,
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
