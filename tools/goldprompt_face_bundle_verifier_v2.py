from __future__ import annotations

import re
from typing import Any, Mapping

import goldprompt_face_receipts_v2 as core

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CHAIN_EVIDENCE_KEYS = frozenset({
    "valid",
    "result_schema",
    "chain_sha256",
    "packet_sha256s",
    "face_receipt_sha256s",
    "verified_raw_packet_binding",
    "end_to_end_receipt_binding_established",
    "origin_authentication_established",
    "live_process_identity_established",
    "authority_delta",
})


def verify_compact_bundle_replay(bundle: Mapping[str, Any]) -> bool:
    """Verify the compact bundle's internal replay contract.

    This deliberately does NOT re-prove raw packet hashes because raw packet
    bodies are not contained in the compact bundle. Use
    verify_bundle_with_raw_evidence for authoritative raw-evidence replay.
    """
    if not core.verify_bundle(bundle):
        return False
    evidence = bundle.get("demihead_chain_evidence")
    receipts = bundle.get("face_receipts")
    if not isinstance(evidence, Mapping) or frozenset(evidence.keys()) != CHAIN_EVIDENCE_KEYS:
        return False
    if not isinstance(receipts, Mapping):
        return False
    if evidence.get("valid") is not True:
        return False
    if evidence.get("result_schema") != core.DEMIHEAD_RESULT_SCHEMA:
        return False
    if evidence.get("verified_raw_packet_binding") is not True:
        return False
    if evidence.get("end_to_end_receipt_binding_established") is not True:
        return False
    if evidence.get("origin_authentication_established") is not False:
        return False
    if evidence.get("live_process_identity_established") is not False:
        return False
    if evidence.get("authority_delta") != 0:
        return False
    if not isinstance(evidence.get("chain_sha256"), str) or SHA256_RE.fullmatch(evidence["chain_sha256"]) is None:
        return False

    packet_hashes = evidence.get("packet_sha256s")
    if not isinstance(packet_hashes, Mapping) or set(packet_hashes) != set(core.CANONICAL_HEMISPHERES):
        return False
    if any(not isinstance(value, str) or SHA256_RE.fullmatch(value) is None for value in packet_hashes.values()):
        return False

    face_hashes = evidence.get("face_receipt_sha256s")
    expected_faces = {"LEFT_HRAIN", "RIGHT_INAIHR", "DEMIHEAD_ARBITER"}
    if not isinstance(face_hashes, Mapping) or set(face_hashes) != expected_faces:
        return False
    for face_id in expected_faces:
        receipt = receipts.get(face_id)
        if not isinstance(receipt, Mapping):
            return False
        if face_hashes.get(face_id) != receipt.get("receipt_sha256"):
            return False
    return True


def verify_bundle_with_raw_evidence(
    bundle: Mapping[str, Any],
    *,
    left_packet: Mapping[str, Any],
    right_packet: Mapping[str, Any],
    demihead_result: Mapping[str, Any],
    expected_revisions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Re-prove the v2 bundle from raw packet bodies and DemiHead result.

    This is the authoritative verifier for the v2 proof class. It does not
    trust compact packet hashes or chain booleans from the bundle.
    """
    if not verify_compact_bundle_replay(bundle):
        raise ValueError("GOLDPROMPT_COMPACT_BUNDLE_REPLAY_INVALID")

    chain = core.verify_demihead_result_with_raw_packets(
        demihead_result,
        left_packet,
        right_packet,
        expected_revisions=expected_revisions,
    )
    if chain != bundle.get("demihead_chain_evidence"):
        raise ValueError("GOLDPROMPT_COMPACT_CHAIN_EVIDENCE_RAW_REPLAY_MISMATCH")

    receipts = bundle["face_receipts"]
    if dict(receipts["LEFT_HRAIN"]) != dict(left_packet["goldprompt_receipt"]):
        raise ValueError("GOLDPROMPT_LEFT_RECEIPT_RAW_PACKET_MISMATCH")
    if dict(receipts["RIGHT_INAIHR"]) != dict(right_packet["goldprompt_receipt"]):
        raise ValueError("GOLDPROMPT_RIGHT_RECEIPT_RAW_PACKET_MISMATCH")
    if dict(receipts["DEMIHEAD_ARBITER"]) != dict(demihead_result["goldprompt_receipt"]):
        raise ValueError("GOLDPROMPT_DEMIHEAD_RECEIPT_RESULT_MISMATCH")

    if expected_revisions is not None:
        if set(expected_revisions) != set(core.CANONICAL_REQUIRED_FACES):
            raise ValueError("EXPECTED_SOURCE_REVISION_FACE_SET_MISMATCH")
        for face_id in core.CANONICAL_REQUIRED_FACES:
            if not core.verify_receipt(receipts[face_id], expected_revisions[face_id]):
                raise ValueError(f"GOLDPROMPT_EXPECTED_REVISION_REPLAY_MISMATCH:{face_id}")

    return {
        "schema": "janus.goldprompt.face_receipt_bundle_raw_replay_certificate.v2",
        "bundle_sha256": bundle["bundle_sha256"],
        "dependency_manifest_digest_sha256": core.EXPECTED_DEPENDENCY_MANIFEST_DIGEST,
        "chain_sha256": chain["chain_sha256"],
        "packet_sha256s": dict(chain["packet_sha256s"]),
        "face_receipt_sha256s": {
            face_id: receipts[face_id]["receipt_sha256"]
            for face_id in core.CANONICAL_REQUIRED_FACES
        },
        "compact_bundle_replay_verified": True,
        "raw_packet_bodies_replayed": True,
        "demihead_result_replayed": True,
        "end_to_end_receipt_binding_established": True,
        "cross_repository_artifact_origin_attestation_established": False,
        "end_to_end_message_authentication_established": False,
        "live_process_identity_established": False,
        "authority_delta": 0,
        "claim_boundaries": [
            "COMPACT_BUNDLE_REPLAY != RAW_EVIDENCE_REPLAY",
            "RAW_EVIDENCE_REPLAY != LIVE_MESSAGE_AUTHENTICATION",
            "END_TO_END_RECEIPT_BINDING != END_TO_END_ORIGIN_AUTHENTICATION",
            "GITHUB_ARTIFACT_ATTESTATION_REQUIRES_SEPARATE_VERIFICATION",
            "AUTHORITY_DELTA = 0",
        ],
    }
