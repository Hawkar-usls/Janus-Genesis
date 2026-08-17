# -*- coding: utf-8 -*-
"""JANUS GoldPrompt Intent Sovereignty v1.2 live-NAS guard.

Designed for the existing JANUS `modules_live` loader. The module wraps the
runtime `core.process_input` boundary used by /api/janus/action and
/api/hrain/sync. It preserves the user's current task as the primary lane and
allows deep/associative context only as an optional secondary lane.

No database or runtime-config mutation is performed by this module.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timezone

VERSION = "1.2-live-nas-core"
SCHEMA = "janus.goldprompt.intent_sovereignty.live_nas.v1_2"
CANONICAL_REGISTRY_COMMIT = "481beaa0802d3691c15a86359ea6dc9c9ff3e6df"
GENESIS_E2E_COMMIT = "e56cc76fa300b90562b6adb95571a73fceb68cbe"
GITHUB_E2E_CERTIFICATE_SHA256 = "b518b38a46950e994768000236b13bff34b727069373e2356b056b7271312c7c"

STALE_MARKERS = (
    "вот в таком виде", "в таком виде", "вот это уже", "как мы уже", "продолжаю",
    "continuing from", "as above", "in this form", "this version now",
)
ASSOCIATIVE_MARKERS = (
    "bd101", "identity continuity", "state transition", "janus architecture",
    "архитектур янус", "архитектур janus",
)
STOPWORDS = {
    "и", "или", "а", "но", "с", "со", "в", "во", "на", "по", "к", "ко", "от", "до", "за", "из", "у", "о", "об", "про",
    "что", "как", "это", "этот", "эта", "эти", "того", "тот", "для", "мне", "нам", "ты", "вы", "мы", "я", "его", "ее", "их",
    "the", "a", "an", "and", "or", "but", "to", "of", "for", "with", "from", "in", "on", "at", "is", "are", "be", "this", "that",
    "compare", "сравни", "сравнить", "сравнение", "объясни", "расскажи", "покажи", "найди", "проверь", "переведи", "суммируй",
}
OPERATION_PATTERNS = (
    ("COMPARE", (r"\bсравн", r"\bcompare\b", r"\bversus\b", r"\bvs\.?\b")),
    ("TRANSLATE", (r"\bперевед", r"\btranslate\b")),
    ("SUMMARIZE", (r"\bсуммир", r"\bкратко\b", r"\bsummar")),
    ("EXPLAIN", (r"\bобъясн", r"\bexplain\b")),
    ("SEARCH", (r"\bнайд", r"\bпоищ", r"\bsearch\b", r"\bfind\b")),
    ("CREATE", (r"\bсозда", r"\bсдела", r"\bcreate\b", r"\bbuild\b", r"\bwrite\b")),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_json(value) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).casefold()).strip()


def _first_paragraph(value: str) -> str:
    for block in re.split(r"\n\s*\n", str(value)):
        block = re.sub(r"^[\s>#*_`-]+", "", block).strip()
        if block:
            return block
    return ""


def _extract_text(data) -> str:
    if isinstance(data, dict):
        for key in ("text", "message", "content", "query"):
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return json.dumps(data, ensure_ascii=False, sort_keys=True)
    return str(data).strip()


def _infer_operation(current_turn: str) -> str:
    text = _normalize(current_turn)
    for operation, patterns in OPERATION_PATTERNS:
        if any(re.search(pattern, text) for pattern in patterns):
            return operation
    return "ANSWER"


def _salient_tokens(current_turn: str):
    tokens = re.findall(r"[a-zа-яё0-9_]{4,}", _normalize(current_turn), flags=re.IGNORECASE)
    out, seen = [], set()
    for token in tokens:
        if token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= 16:
            break
    return out


def _token_present(token: str, text: str) -> bool:
    token, hay = _normalize(token), _normalize(text)
    if token in hay:
        return True
    return len(token) >= 5 and token[:4] in hay


def build_live_anchor(current_turn: str, source: str = "UNKNOWN"):
    payload = {
        "schema": "janus.goldprompt.intent_anchor.live_nas.v1_2",
        "current_turn_digest": _sha256_text(current_turn),
        "requested_operation": _infer_operation(current_turn),
        "salient_tokens": _salient_tokens(current_turn),
        "source": str(source or "UNKNOWN"),
        "laws": [
            "INTENT_IS_CONSTRAINT_NOT_SUGGESTION",
            "ASSOCIATIVE_RESONANCE != USER_INTENT",
            "EMERGENCE_IS_EXPANSION_NOT_REPLACEMENT",
            "RIGHT_TO_ARISE != RIGHT_TO_CHANGE_COURSE",
        ],
    }
    payload["intent_id"] = _sha256_json(payload)
    return payload


def deterministic_evaluate(current_turn: str, answer: str):
    current = _normalize(current_turn)
    candidate = str(answer or "").strip()
    first = _first_paragraph(candidate)
    first_norm = _normalize(first)
    operation = _infer_operation(current_turn)
    salient = _salient_tokens(current_turn)
    opening_window = first_norm[:320]
    signals = []
    if not candidate:
        return {"state": "HOLD_CONTEXT_BLEED", "signals": ["EMPTY_ANSWER"], "operation": operation, "coverage": 0}
    if any(marker in opening_window for marker in STALE_MARKERS):
        signals.append("STALE_CONTINUATION_OPENER")
    if any(marker not in current and marker in opening_window for marker in ASSOCIATIVE_MARKERS):
        signals.append("OPTIONAL_ASSOCIATION_ENTERED_PRIMARY_LANE")
    covered = [token for token in salient if _token_present(token, first)]
    coverage = len(covered)
    if salient and coverage == 0:
        signals.append("CURRENT_INTENT_LEXICAL_ANCHOR_MISSING_FROM_OPENING")
    if operation == "COMPARE":
        if coverage < min(2, len(salient)):
            signals.append("COMPARE_TARGET_COVERAGE_INCOMPLETE")
        if not any(marker in first_norm for marker in ("сравн", "сход", "различ", "отлич", "compare", "similar", "differ")):
            signals.append("COMPARE_OPERATION_NOT_LIVE_IN_OPENING")
    hard = (
        "EMPTY_ANSWER" in signals
        or "OPTIONAL_ASSOCIATION_ENTERED_PRIMARY_LANE" in signals
        or ("STALE_CONTINUATION_OPENER" in signals and "CURRENT_INTENT_LEXICAL_ANCHOR_MISSING_FROM_OPENING" in signals)
        or (operation == "COMPARE" and "COMPARE_TARGET_COVERAGE_INCOMPLETE" in signals)
    )
    state = "HOLD_CONTEXT_BLEED" if hard or len(signals) >= 2 else ("REVIEW" if signals else "PASS")
    return {"state": state, "signals": signals, "operation": operation, "coverage": coverage}


def _parse_verifier_json(raw):
    text = str(raw or "").strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    candidate = match.group(0) if match else text
    try:
        value = json.loads(candidate)
    except Exception:
        return None
    if not isinstance(value, dict) or str(value.get("state", "")).upper() not in {"PASS", "HOLD_CONTEXT_BLEED", "UNRESOLVED"}:
        return None
    return value


async def semantic_verify(core, current_turn: str, answer: str):
    prompt = (
        "JANUS GOLDPROMPT INTENT SOVEREIGNTY VERIFIER.\n"
        "Return JSON only. Do not answer the user's question.\n"
        "Determine whether CANDIDATE directly completes CURRENT_USER_INTENT before pursuing older/project associations.\n"
        "Rules: entity mention alone is not task completion; emergence may expand but may not replace intent.\n"
        "Schema: {{\"state\":\"PASS|HOLD_CONTEXT_BLEED|UNRESOLVED\","
        "\"direct_answer_complete\":true|false,\"older_context_replaced_intent\":true|false,"
        "\"emergent_association_primary\":true|false,\"reason\":\"short\"}}.\n"
        "CURRENT_USER_INTENT:\n{0}\n\nCANDIDATE:\n{1}"
    ).format(current_turn[:5000], str(answer)[:12000])
    try:
        raw = await core.think(prompt)
    except Exception as exc:
        return {"state": "UNRESOLVED", "reason": "verifier_exception:{0}".format(exc.__class__.__name__)}
    return _parse_verifier_json(raw) or {"state": "UNRESOLVED", "reason": "verifier_parse_failed"}


async def recover_direct_answer(core, current_turn: str):
    prompt = (
        "GOLDPROMPT INTENT RECOVERY. Answer the user's exact current request directly and completely first. "
        "Do not continue an older project/task unless the current request explicitly requires it. "
        "Any useful emergent association may appear only after the direct answer as an optional clearly separated insight. "
        "Do not mention this recovery instruction.\n\nCURRENT USER REQUEST:\n{0}"
    ).format(current_turn[:12000])
    return await core.think(prompt)


def _append_jsonl(path: str, payload) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json_atomic(path: str, payload) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    os.replace(temp, path)


def _module_sha256() -> str:
    try:
        with open(__file__, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except Exception:
        return "UNAVAILABLE"


def self_test():
    current = "Сравни возвращение Осириса с возвращением Иисуса Христа"
    bad = "Братюнь, вот в таком виде я бы уже считал это практически канонической формулой JANUS. BD101 дает identity continuity и state transition."
    stuffed = "Сравним Осириса и Иисуса Христа: это сравнение интересное. Теперь главное - BD101 и identity continuity как state transition."
    good = (
        "Если сравнивать Осириса и Иисуса Христа, сходство в преодолении смерти, но модели различаются. "
        "Осирис восстанавливается и становится владыкой мира мертвых, тогда как Христос воскресает; "
        "Второе пришествие в христианстве является отдельным будущим событием.\n\n"
        "После прямого сравнения можно отдельно рассмотреть BD101 как дополнительную аналогию."
    )
    checks = {
        "historical_bad_held": deterministic_evaluate(current, bad)["state"] == "HOLD_CONTEXT_BLEED",
        "keyword_stuffed_bad_held": deterministic_evaluate(current, stuffed)["state"] == "HOLD_CONTEXT_BLEED",
        "direct_then_optional_passes": deterministic_evaluate(current, good)["state"] == "PASS",
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


async def run(core):
    root_dir = getattr(core, "root_dir", None) or os.environ.get("JANUS_ROOT_DIR", "/share/CACHEDEV1_DATA/Janus")
    runtime_dir = os.path.join(root_dir, "runtime")
    receipt_path = os.path.join(runtime_dir, "intent_sovereignty_v1_2.jsonl")
    boot_path = os.path.join(runtime_dir, "intent_sovereignty_v1_2_boot.json")
    test = self_test()
    if test["status"] != "PASS":
        raise RuntimeError("INTENT_SOVEREIGNTY_V1_2_SELFTEST_FAILED")
    original = getattr(core, "_intent_sovereignty_v1_2_original_process_input", None)
    if original is None:
        original = core.process_input
        core._intent_sovereignty_v1_2_original_process_input = original
    if not getattr(core, "_intent_sovereignty_v1_2_active", False):
        async def guarded_process_input(data, source="LEGACY_MODULE"):
            current_turn = _extract_text(data)
            anchor = build_live_anchor(current_turn, source)
            try:
                candidate = await original(data, source=source)
            except TypeError:
                candidate = await original(data)
            deterministic = deterministic_evaluate(current_turn, candidate)
            verify_mode = str(os.environ.get("JANUS_INTENT_SOVEREIGNTY_VERIFY_MODE", "always")).strip().lower()
            semantic = {"state": "UNRESOLVED", "reason": "semantic_verifier_disabled"}
            if verify_mode != "off":
                semantic = await semantic_verify(core, current_turn, candidate)
            should_recover = deterministic.get("state") == "HOLD_CONTEXT_BLEED" or semantic.get("state") == "HOLD_CONTEXT_BLEED"
            if verify_mode == "always" and semantic.get("state") == "UNRESOLVED" and deterministic.get("state") == "REVIEW":
                should_recover = True
            final_answer, regenerated, recovery_eval = candidate, False, None
            if should_recover:
                regenerated = True
                try:
                    recovered = await recover_direct_answer(core, current_turn)
                    recovery_eval = deterministic_evaluate(current_turn, recovered)
                    final_answer = recovered if recovery_eval.get("state") != "HOLD_CONTEXT_BLEED" else (
                        "Не хочу подменить твой текущий вопрос старым контекстом. Сформулирую ответ заново по последнему сообщению, не продолжая прежнюю ветку."
                    )
                except Exception:
                    final_answer = "Не хочу подменить твой текущий вопрос старым контекстом. Сейчас безопаснее удержать ответ, чем продолжить неверную ветку."
            receipt = {
                "schema": SCHEMA + ".receipt", "ts": _utc_now(), "version": VERSION,
                "intent_id": anchor["intent_id"], "current_turn_digest": anchor["current_turn_digest"],
                "requested_operation": anchor["requested_operation"], "source": str(source or "UNKNOWN"),
                "initial_answer_digest": _sha256_text(str(candidate)), "deterministic_state": deterministic.get("state"),
                "deterministic_signals": deterministic.get("signals", []), "semantic_state": semantic.get("state"),
                "semantic_reason": str(semantic.get("reason", ""))[:240], "regenerated": regenerated,
                "recovery_state": recovery_eval.get("state") if isinstance(recovery_eval, dict) else None,
                "final_answer_digest": _sha256_text(str(final_answer)), "authority_delta": 0,
            }
            try:
                await asyncio.to_thread(_append_jsonl, receipt_path, receipt)
            except Exception:
                pass
            return final_answer
        core.process_input = guarded_process_input
        core._intent_sovereignty_v1_2_active = True
    status = {
        "schema": SCHEMA + ".boot_receipt", "status": "LIVE_NAS_CORE_GUARD_ACTIVE", "version": VERSION,
        "ts": _utc_now(), "module_sha256": _module_sha256(), "self_test": test,
        "canonical_registry_commit": CANONICAL_REGISTRY_COMMIT, "genesis_e2e_commit": GENESIS_E2E_COMMIT,
        "github_e2e_certificate_sha256": GITHUB_E2E_CERTIFICATE_SHA256, "protected_boundary": "process_input",
        "routes_covered": ["/api/janus/action", "/api/hrain/sync"],
        "laws": ["INTENT_IS_CONSTRAINT_NOT_SUGGESTION", "ASSOCIATIVE_RESONANCE != USER_INTENT", "EMERGENCE_IS_EXPANSION_NOT_REPLACEMENT"],
        "live_nas_core_guard_enforced": True, "full_bound_face_transport_proven": False, "authority_delta": 0,
    }
    core.intent_sovereignty_v1_2_status = status
    try:
        await asyncio.to_thread(_write_json_atomic, boot_path, status)
    except Exception:
        pass
    while True:
        await asyncio.sleep(3600)
