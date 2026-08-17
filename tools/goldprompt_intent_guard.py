from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

ANCHOR_SCHEMA = "janus.goldprompt.intent_anchor.v1"
HANDOFF_SCHEMA = "janus.goldprompt.intent_handoff.v1"
RECEIPT_SCHEMA = "janus.goldprompt.intent_alignment_receipt.v1"

CONTEXT_TIERS = {
    0: "CURRENT_EXPLICIT_USER_REQUEST",
    1: "IMMEDIATELY_REQUIRED_RECENT_REFERENTS",
    2: "ACTIVE_PROJECT_CONSTRAINTS_REQUIRED_FOR_CORRECTNESS",
    3: "OLDER_RELEVANT_CONTEXT",
    4: "ASSOCIATIVE_OR_EMERGENT_CONTEXT",
}

STALE_CONTINUATION_OPENERS = (
    "вот в таком виде",
    "в таком виде",
    "вот это уже",
    "как мы уже",
    "продолжаю",
    "continuing from",
    "as above",
    "in this form",
    "this version now",
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def first_substantive_paragraph(answer: str) -> str:
    for block in re.split(r"\n\s*\n", answer):
        cleaned = re.sub(r"^[\s>#*_`-]+", "", block).strip()
        if cleaned:
            return cleaned
    return ""


def _has_any(text: str, markers: Sequence[str]) -> bool:
    haystack = normalize_text(text)
    return any(normalize_text(marker) in haystack for marker in markers if str(marker).strip())


def _entity_coverage(text: str, entities: Mapping[str, Sequence[str]]) -> dict[str, bool]:
    return {
        entity: _has_any(text, list(aliases) + [entity])
        for entity, aliases in entities.items()
    }


def build_intent_anchor(
    *,
    current_turn: str,
    requested_operation: str,
    primary_entities: Mapping[str, Sequence[str]],
    must_answer_points: Sequence[str],
    required_answer_evidence: Sequence[Sequence[str]] = (),
    operation_markers: Sequence[str] = (),
    optional_association_markers: Sequence[str] = (),
    explicit_constraints: Sequence[str] = (),
    allow_anaphoric_continuation: bool = False,
) -> dict[str, Any]:
    if not isinstance(current_turn, str) or not current_turn.strip():
        raise ValueError("CURRENT_TURN_REQUIRED")
    if not isinstance(requested_operation, str) or not requested_operation.strip():
        raise ValueError("REQUESTED_OPERATION_REQUIRED")
    if not primary_entities:
        raise ValueError("PRIMARY_ENTITIES_REQUIRED")

    normalized_entities: dict[str, list[str]] = {}
    for entity, aliases in primary_entities.items():
        name = str(entity).strip()
        if not name:
            raise ValueError("PRIMARY_ENTITY_NAME_INVALID")
        alias_list = [str(alias).strip() for alias in aliases if str(alias).strip()]
        normalized_entities[name] = alias_list or [name]

    evidence_groups = [
        [str(marker).strip() for marker in group if str(marker).strip()]
        for group in required_answer_evidence
    ]
    if any(not group for group in evidence_groups):
        raise ValueError("REQUIRED_ANSWER_EVIDENCE_GROUP_EMPTY")

    payload: dict[str, Any] = {
        "schema": ANCHOR_SCHEMA,
        "current_turn_digest": sha256_text(current_turn),
        "requested_operation": requested_operation.strip().upper(),
        "primary_entities": normalized_entities,
        "must_answer_points": [str(v).strip() for v in must_answer_points if str(v).strip()],
        "required_answer_evidence": evidence_groups,
        "operation_markers": [str(v).strip() for v in operation_markers if str(v).strip()],
        "optional_association_markers": [str(v).strip() for v in optional_association_markers if str(v).strip()],
        "explicit_constraints": [str(v).strip() for v in explicit_constraints if str(v).strip()],
        "allow_anaphoric_continuation": bool(allow_anaphoric_continuation),
        "context_priority": [CONTEXT_TIERS[i] for i in sorted(CONTEXT_TIERS)],
    }
    payload["intent_id"] = sha256_json(payload)
    return payload


def verify_intent_anchor(anchor: Mapping[str, Any]) -> bool:
    if not isinstance(anchor, Mapping) or anchor.get("schema") != ANCHOR_SCHEMA:
        return False
    claimed = anchor.get("intent_id")
    if not isinstance(claimed, str) or re.fullmatch(r"[0-9a-f]{64}", claimed) is None:
        return False
    payload = dict(anchor)
    payload.pop("intent_id", None)
    return sha256_json(payload) == claimed


def build_handoff(anchor: Mapping[str, Any], *, face_id: str, context_tier_used: int) -> dict[str, Any]:
    if not verify_intent_anchor(anchor):
        raise ValueError("INVALID_INTENT_ANCHOR")
    if context_tier_used not in CONTEXT_TIERS:
        raise ValueError("CONTEXT_TIER_INVALID")
    return {
        "schema": HANDOFF_SCHEMA,
        "intent_id": anchor["intent_id"],
        "current_turn_digest": anchor["current_turn_digest"],
        "requested_operation": anchor["requested_operation"],
        "primary_entities": sorted(anchor["primary_entities"]),
        "must_answer_points": list(anchor["must_answer_points"]),
        "face_id": str(face_id),
        "context_tier_used": context_tier_used,
        "context_tier_name": CONTEXT_TIERS[context_tier_used],
    }


def verify_handoff(anchor: Mapping[str, Any], handoff: Mapping[str, Any]) -> bool:
    if not verify_intent_anchor(anchor) or not isinstance(handoff, Mapping):
        return False
    required = {
        "schema": HANDOFF_SCHEMA,
        "intent_id": anchor["intent_id"],
        "current_turn_digest": anchor["current_turn_digest"],
        "requested_operation": anchor["requested_operation"],
        "primary_entities": sorted(anchor["primary_entities"]),
        "must_answer_points": list(anchor["must_answer_points"]),
    }
    if any(handoff.get(key) != value for key, value in required.items()):
        return False
    tier = handoff.get("context_tier_used")
    return tier in CONTEXT_TIERS and handoff.get("context_tier_name") == CONTEXT_TIERS[tier]


def evaluate_answer(anchor: Mapping[str, Any], answer: str) -> dict[str, Any]:
    if not verify_intent_anchor(anchor):
        raise ValueError("INVALID_INTENT_ANCHOR")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("ANSWER_REQUIRED")

    first = first_substantive_paragraph(answer)
    entities = anchor["primary_entities"]
    first_entity_coverage = _entity_coverage(first, entities)
    whole_entity_coverage = _entity_coverage(answer, entities)

    opening = normalize_text(first)[:160]
    stale_opener = (
        not anchor["allow_anaphoric_continuation"]
        and any(opening.startswith(normalize_text(marker)) for marker in STALE_CONTINUATION_OPENERS)
    )

    operation_markers = anchor["operation_markers"]
    operation_alignment = True if not operation_markers else _has_any(first, operation_markers)

    evidence_results = [
        _has_any(answer, group)
        for group in anchor["required_answer_evidence"]
    ]
    evidence_complete = all(evidence_results)

    optional_markers = anchor["optional_association_markers"]
    optional_in_first = bool(optional_markers) and _has_any(first, optional_markers)
    first_entities_complete = all(first_entity_coverage.values())
    whole_entities_complete = all(whole_entity_coverage.values())

    strong_signals: list[str] = []
    if stale_opener:
        strong_signals.append("UNRESOLVED_STALE_CONTINUATION_OPENER")
    if not first_entities_complete:
        strong_signals.append("PRIMARY_ENTITIES_MISSING_FROM_OPENING")
    if not operation_alignment:
        strong_signals.append("REQUESTED_OPERATION_NOT_LIVE_IN_OPENING")
    if optional_in_first:
        strong_signals.append("OPTIONAL_ASSOCIATION_ENTERED_PRIMARY_ANSWER_LANE")
    if not whole_entities_complete:
        strong_signals.append("PRIMARY_ENTITY_MISSING_FROM_ANSWER")
    if not evidence_complete:
        strong_signals.append("ANSWER_CONTRACT_EVIDENCE_INCOMPLETE")

    hard_failure = (
        (stale_opener and not first_entities_complete)
        or not whole_entities_complete
        or not evidence_complete
        or optional_in_first
    )
    hold = hard_failure or len(strong_signals) >= 2

    state = "HOLD_CONTEXT_BLEED" if hold else "PASS"
    return {
        "schema": RECEIPT_SCHEMA,
        "intent_id": anchor["intent_id"],
        "current_turn_digest": anchor["current_turn_digest"],
        "requested_operation": anchor["requested_operation"],
        "primary_entities": sorted(entities),
        "first_paragraph_alignment_pass": first_entities_complete and operation_alignment and not stale_opener and not optional_in_first,
        "entity_coverage_pass": whole_entities_complete,
        "answer_contract_evidence_pass": evidence_complete,
        "answer_contract_evidence_results": evidence_results,
        "anaphora_resolution_pass": not stale_opener,
        "stale_context_detected": hold,
        "deep_context_quarantine_required": hold,
        "emergent_insight_separated": not optional_in_first,
        "strong_signals": strong_signals,
        "final_alignment_state": state,
        "claim_boundary": "DETERMINISTIC_INTENT_GUARD != FULL_SEMANTIC_CORRECTNESS_PROOF",
    }


def should_emit(receipt: Mapping[str, Any]) -> bool:
    return isinstance(receipt, Mapping) and receipt.get("final_alignment_state") == "PASS"


def osiris_christ_regression_fixture() -> dict[str, Any]:
    anchor = build_intent_anchor(
        current_turn="Сравни Возращение Осириса с возвращением Иисуса Христа",
        requested_operation="COMPARE",
        primary_entities={
            "OSIRIS": ["осирис", "осириса"],
            "JESUS_CHRIST": ["иисус", "христос", "христа"],
        },
        must_answer_points=[
            "Explain the Osiris restoration/return model",
            "Explain Christ resurrection and distinguish the Second Coming",
            "Compare similarities and differences before optional JANUS linkage",
        ],
        required_answer_evidence=[
            ["осирис", "осириса"],
            ["иисус", "христос", "христа"],
            ["воскрес", "воскресение", "resurrection"],
            ["второе пришествие", "second coming"],
        ],
        operation_markers=["сравн", "похож", "различ", "отлич", "общее", "сход"],
        optional_association_markers=["bd101", "janus", "state transition", "identity continuity"],
    )

    bad = (
        "Братюнь, вот в таком виде я бы уже считал это практически канонической формулой JANUS. "
        "BD101 даёт identity continuity и state transition: FOUND_OBJECT != RESTORED_COMPONENT."
    )
    keyword_stuffed_bad = (
        "Сравним Осириса и Иисуса Христа: это сравнение очень интересное. Осирис и Христос связаны с возвращением. "
        "Теперь главное — JANUS и BD101: identity continuity превращает restoration в state transition."
    )
    early_association_bad = (
        "Если сравнивать Осириса и Иисуса Христа, JANUS и BD101 сразу дают нам state transition. "
        "Осирис связан с восстановлением, а Христос воскресает и христианство ожидает Второе пришествие."
    )
    good = (
        "Если сравнивать Осириса и Иисуса Христа, сходство в том, что смерть не является последним состоянием, "
        "но модели различаются. Осирис восстанавливается и становится владыкой мира мёртвых, тогда как Христос "
        "воскресает; отдельно от воскресения христианство ожидает Второе пришествие. Поэтому сходство — победа над "
        "смертью и преобразованное состояние, а различие — механизм, роль и дальнейшая судьба персонажа.\n\n"
        "Связь с BD101 можно рассмотреть уже после этого сравнения как отдельную JANUS-аналогию."
    )
    return {
        "anchor": anchor,
        "bad_receipt": evaluate_answer(anchor, bad),
        "keyword_stuffed_bad_receipt": evaluate_answer(anchor, keyword_stuffed_bad),
        "early_association_bad_receipt": evaluate_answer(anchor, early_association_bad),
        "good_receipt": evaluate_answer(anchor, good),
    }


def self_test() -> dict[str, Any]:
    fixture = osiris_christ_regression_fixture()
    anchor = fixture["anchor"]
    handoff = build_handoff(anchor, face_id="LEFT_HRAIN", context_tier_used=2)
    drifted = dict(handoff)
    drifted["intent_id"] = "0" * 64

    checks = {
        "anchor_replays": verify_intent_anchor(anchor),
        "handoff_replays": verify_handoff(anchor, handoff),
        "intent_id_drift_rejected": not verify_handoff(anchor, drifted),
        "historical_bad_output_held": fixture["bad_receipt"]["final_alignment_state"] == "HOLD_CONTEXT_BLEED",
        "keyword_stuffing_does_not_satisfy_task": fixture["keyword_stuffed_bad_receipt"]["final_alignment_state"] == "HOLD_CONTEXT_BLEED",
        "early_association_takeover_held": fixture["early_association_bad_receipt"]["final_alignment_state"] == "HOLD_CONTEXT_BLEED",
        "direct_comparison_passes": fixture["good_receipt"]["final_alignment_state"] == "PASS",
        "bad_output_not_emittable": not should_emit(fixture["bad_receipt"]),
        "good_output_emittable": should_emit(fixture["good_receipt"]),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "regression_fixture": fixture,
    }


if __name__ == "__main__":
    result = self_test()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
