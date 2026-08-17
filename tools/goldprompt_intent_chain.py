from __future__ import annotations

import copy
import json
import re
from typing import Any, Mapping

from goldprompt_intent_guard import sha256_json, verify_intent_anchor

HANDOFF_SCHEMA = "janus.goldprompt.intent_handoff.v1"
PACKET_SCHEMA = "janus.demihead.hemisphere_packet.v3"
DEMIHEAD_RESULT_SCHEMA = "janus.demihead.intent_bound_bicameral_result.v1"
INTENT_CHAIN_SCHEMA = "janus.goldprompt.intent_chain.v1"
CERTIFICATE_SCHEMA = "janus.goldprompt.intent_chain_certificate.v1"
GENESIS_FACE_ID = "GENESIS_GUARDIAN_MESH_ORCHESTRATOR"
CONTEXT_TIERS = {
    0: "CURRENT_EXPLICIT_USER_REQUEST",
    1: "IMMEDIATELY_REQUIRED_RECENT_REFERENTS",
    2: "ACTIVE_PROJECT_CONSTRAINTS_REQUIRED_FOR_CORRECTNESS",
    3: "OLDER_RELEVANT_CONTEXT",
    4: "ASSOCIATIVE_OR_EMERGENT_CONTEXT",
}
HANDOFF_KEYS = {
    "schema", "intent_id", "current_turn_digest", "requested_operation",
    "primary_entities", "must_answer_points", "face_id", "context_tier_used",
    "context_tier_name", "handoff_sha256",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def build_strict_handoff(anchor: Mapping[str, Any], face_id: str, context_tier_used: int = 2) -> dict[str, Any]:
    if not verify_intent_anchor(anchor):
        raise ValueError("INVALID_INTENT_ANCHOR")
    if context_tier_used not in CONTEXT_TIERS:
        raise ValueError("CONTEXT_TIER_INVALID")
    handoff = {
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
    handoff["handoff_sha256"] = sha256_json(handoff)
    return handoff


def verify_strict_handoff(anchor: Mapping[str, Any], handoff: Mapping[str, Any], expected_face_id: str) -> bool:
    if not verify_intent_anchor(anchor) or not isinstance(handoff, Mapping) or set(handoff) != HANDOFF_KEYS:
        return False
    required = {
        "schema": HANDOFF_SCHEMA,
        "intent_id": anchor["intent_id"],
        "current_turn_digest": anchor["current_turn_digest"],
        "requested_operation": anchor["requested_operation"],
        "primary_entities": sorted(anchor["primary_entities"]),
        "must_answer_points": list(anchor["must_answer_points"]),
        "face_id": str(expected_face_id),
    }
    if any(handoff.get(key) != value for key, value in required.items()):
        return False
    tier = handoff.get("context_tier_used")
    if tier not in CONTEXT_TIERS or handoff.get("context_tier_name") != CONTEXT_TIERS[tier]:
        return False
    claimed = handoff.get("handoff_sha256")
    if not isinstance(claimed, str) or HEX64.fullmatch(claimed) is None:
        return False
    payload = dict(handoff)
    payload.pop("handoff_sha256", None)
    return sha256_json(payload) == claimed


def verify_intent_packet(packet: Mapping[str, Any], anchor: Mapping[str, Any], expected_face: str) -> bool:
    if not isinstance(packet, Mapping) or packet.get("schema") != PACKET_SCHEMA or packet.get("hemisphere") != expected_face:
        return False
    if packet.get("intent_anchor") != anchor:
        return False
    handoff = packet.get("intent_handoff")
    if not isinstance(handoff, Mapping) or not verify_strict_handoff(anchor, handoff, expected_face):
        return False
    source = packet.get("source")
    if not isinstance(source, Mapping):
        return False
    return (
        source.get("intent_id") == anchor.get("intent_id")
        and source.get("intent_handoff_sha256") == handoff.get("handoff_sha256")
    )


def _expected_demihead_chain(
    anchor: Mapping[str, Any],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    demihead_handoff: Mapping[str, Any],
) -> dict[str, Any]:
    core = {
        "schema": INTENT_CHAIN_SCHEMA,
        "intent_id": anchor["intent_id"],
        "current_turn_digest": anchor["current_turn_digest"],
        "requested_operation": anchor["requested_operation"],
        "primary_entities": sorted(anchor["primary_entities"]),
        "upstream": {
            "LEFT_HRAIN": {
                "handoff_sha256": left["intent_handoff"]["handoff_sha256"],
                "packet_sha256": sha256_json(left),
            },
            "RIGHT_INAIHR": {
                "handoff_sha256": right["intent_handoff"]["handoff_sha256"],
                "packet_sha256": sha256_json(right),
            },
        },
        "demihead": {
            "face_id": "DEMIHEAD_ARBITER",
            "handoff_sha256": demihead_handoff["handoff_sha256"],
        },
        "binding_scope": "CURRENT_TURN_TO_LEFT_RIGHT_TO_DEMIHEAD_WITHOUT_INTENT_REINTERPRETATION",
        "all_handoffs_same_intent": True,
        "emergent_association_may_replace_intent": False,
        "authority_delta": 0,
    }
    return {**core, "intent_chain_sha256": sha256_json(core)}


def verify_demihead_intent_result(
    result: Mapping[str, Any],
    *,
    anchor: Mapping[str, Any],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    if not verify_intent_anchor(anchor):
        return False
    if not verify_intent_packet(left, anchor, "LEFT_HRAIN") or not verify_intent_packet(right, anchor, "RIGHT_INAIHR"):
        return False
    if not isinstance(result, Mapping) or result.get("schema") != DEMIHEAD_RESULT_SCHEMA or result.get("intent_anchor") != anchor:
        return False
    upstream = result.get("upstream_intent_handoffs")
    if not isinstance(upstream, Mapping):
        return False
    if upstream.get("LEFT_HRAIN") != left.get("intent_handoff") or upstream.get("RIGHT_INAIHR") != right.get("intent_handoff"):
        return False
    own = result.get("demihead_intent_handoff")
    if not isinstance(own, Mapping) or not verify_strict_handoff(anchor, own, "DEMIHEAD_ARBITER"):
        return False
    if result.get("intent_chain") != _expected_demihead_chain(anchor, left, right, own):
        return False
    routing = result.get("routing")
    if not isinstance(routing, Mapping):
        return False
    return (
        routing.get("intent_alignment_required") is True
        and routing.get("intent_split_permitted") is False
        and routing.get("older_context_may_redefine_task") is False
        and routing.get("optional_association_may_replace_primary_path") is False
    )


def build_certificate(
    *,
    anchor: Mapping[str, Any],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    demihead_result: Mapping[str, Any],
) -> dict[str, Any]:
    if not verify_demihead_intent_result(demihead_result, anchor=anchor, left=left, right=right):
        raise ValueError("NONCOMPLIANT_DEMIHEAD_INTENT_CHAIN")
    genesis_handoff = build_strict_handoff(anchor, GENESIS_FACE_ID, 2)
    core = {
        "schema": CERTIFICATE_SCHEMA,
        "intent_id": anchor["intent_id"],
        "current_turn_digest": anchor["current_turn_digest"],
        "requested_operation": anchor["requested_operation"],
        "primary_entities": sorted(anchor["primary_entities"]),
        "node_order": ["CURRENT_USER_TURN", "LEFT_HRAIN", "RIGHT_INAIHR", "DEMIHEAD_ARBITER", GENESIS_FACE_ID],
        "handoff_sha256": {
            "LEFT_HRAIN": left["intent_handoff"]["handoff_sha256"],
            "RIGHT_INAIHR": right["intent_handoff"]["handoff_sha256"],
            "DEMIHEAD_ARBITER": demihead_result["demihead_intent_handoff"]["handoff_sha256"],
            GENESIS_FACE_ID: genesis_handoff["handoff_sha256"],
        },
        "packet_sha256": {
            "LEFT_HRAIN": sha256_json(left),
            "RIGHT_INAIHR": sha256_json(right),
        },
        "demihead_intent_chain_sha256": demihead_result["intent_chain"]["intent_chain_sha256"],
        "genesis_intent_handoff": genesis_handoff,
        "all_nodes_same_intent": True,
        "intent_reinterpretation_permitted": False,
        "emergence_may_replace_primary_intent": False,
        "final_output_alignment_gate_required": True,
        "high_impact_tool_action_on_alignment_failure": "FORBIDDEN",
        "authority_delta": 0,
        "claim_boundaries": [
            "INTENT_CHAIN_PASS != FACTUAL_CORRECTNESS",
            "INTENT_CHAIN_PASS != HUMAN_CONSENT",
            "INTENT_CONTINUITY != LIVE_NAS_ATTESTATION",
        ],
    }
    return {**core, "certificate_sha256": sha256_json(core)}


def verify_certificate(
    certificate: Mapping[str, Any],
    *,
    anchor: Mapping[str, Any],
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    demihead_result: Mapping[str, Any],
) -> bool:
    try:
        expected = build_certificate(anchor=anchor, left=left, right=right, demihead_result=demihead_result)
    except (KeyError, TypeError, ValueError):
        return False
    return dict(certificate) == expected


def load_json(path: str) -> dict[str, Any]:
    value = json.loads(open(path, "r", encoding="utf-8").read())
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value
