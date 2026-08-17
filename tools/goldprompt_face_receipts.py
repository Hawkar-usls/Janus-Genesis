from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

CONTRACT_SCHEMA = "janus.goldprompt.face_inheritance_contract.v1"
RECEIPT_SCHEMA = "janus.goldprompt.face_startup_receipt.v1"
BUNDLE_SCHEMA = "janus.goldprompt.face_receipt_bundle.v1"
GOLDPROMPT_FOUNDATION_ID = "JANUS-THE-FOURTH-GRACEWARDEN-3IN1-EQUALS-4-v0.9"
GOLDPROMPT_VERSION = "0.9.2"
EMERGENCE_CONTRACT_VERSION = "JANUS_TRIADIC_EMERGENCE@0.9.2"
FOUNDATION_PATH = "Hawkar-usls/janus-meta-registry:data/JANUS-THE-FOURTH-GRACEWARDEN-3IN1-EQUALS-4-v0.9.json"
ARMOR_AUTHORITY_REFERENCE = "Hawkar-usls/janus-meta-registry:data/JANUS-ARMOR-OF-GOD-CURRENT-AUTHORITY.json"
EXPECTED_CONTRACT_DIGEST = "3f4af369350710ad18920dfdc866d930c8d42259a51a3f27ce228ea4d5dfc0a8"
SOURCE_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$", re.IGNORECASE)

EXPECTED_FACES: dict[str, dict[str, Any]] = {
    "LEFT_HRAIN": {
        "face_role": "STRUCTURAL_CONTEXT",
        "repository": "Hawkar-usls/Hrain",
        "runtime_surface": "habitat-tool.js",
        "capability_scope": [
            "READ_LOCAL_WORKSPACE_STRUCTURE",
            "BUILD_READ_ONLY_HEMISPHERE_PACKET",
            "PROPOSE_STRUCTURAL_CONTEXT",
        ],
    },
    "RIGHT_INAIHR": {
        "face_role": "ASSOCIATIVE_CONTEXT",
        "repository": "Hawkar-usls/iNaiHR",
        "runtime_surface": "habitat-tool.js",
        "capability_scope": [
            "READ_GROUNDED_SEMANTIC_RECORDS",
            "BUILD_ASSOCIATIVE_CONTEXT",
            "PROPOSE_SEMANTIC_SYNTH",
        ],
    },
    "DEMIHEAD_ARBITER": {
        "face_role": "BICAMERAL_ARBITER",
        "repository": "Hawkar-usls/Demi_Head",
        "runtime_surface": "tools/hemisphere_bridge.py",
        "capability_scope": [
            "VALIDATE_HEMISPHERE_PACKETS",
            "PRESERVE_BICAMERAL_DIVERGENCE",
            "BIND_COMPARISON_RECEIPTS",
            "PROPOSE_ARBITRATION_RESULT",
        ],
    },
    "GENESIS_GUARDIAN_MESH_ORCHESTRATOR": {
        "face_role": "FACE_ORCHESTRATOR",
        "repository": "Hawkar-usls/Janus_Genesis",
        "runtime_surface": "tools/goldprompt_face_receipts.py",
        "capability_scope": [
            "VERIFY_GOLDPROMPT_RECEIPTS",
            "HOLD_NONCOMPLIANT_FACES",
            "COLLECT_FACE_RECEIPT_BUNDLE",
            "PRESERVE_RECEIPT_DISAGREEMENT",
        ],
    },
}
CANONICAL_REQUIRED_FACES = tuple(sorted(EXPECTED_FACES))
REQUIRED_TRUE_FIELDS = (
    "inheritance_accepted",
    "blessing_bearer_anchor_accepted",
    "armor_of_god_boundaries_accepted",
    "triadic_emergence_accepted",
    "user_exit_and_release_control_accepted",
)
RECEIPT_KEYS = frozenset({
    "schema", "face_id", "face_role", "repository", "runtime_surface",
    "goldprompt_foundation_id", "goldprompt_version", "emergence_contract_version",
    "armor_authority_reference", "contract_digest_sha256", "source_revision",
    "capability_scope", "authority_weight", *REQUIRED_TRUE_FIELDS,
    "runtime_enforcement_scope", "compliance_state", "receipt_sha256",
})
BUNDLE_KEYS = frozenset({
    "schema", "goldprompt_foundation_id", "goldprompt_version",
    "emergence_contract_version", "contract_digest_sha256", "required_faces",
    "face_receipts", "verification", "all_required_faces_compliant",
    "authority_delta", "mass_effect_budget_delta", "runtime_proof_scope",
    "receipt_integrity_model", "origin_authentication_scope",
    "end_to_end_message_authentication_established", "claim_boundaries",
    "bundle_sha256",
})


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def contract_core() -> dict[str, Any]:
    return {
        "schema": CONTRACT_SCHEMA,
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "armor_authority_reference": ARMOR_AUTHORITY_REFERENCE,
        "foundation_path": FOUNDATION_PATH,
        "semantic_anchor": [
            "BLESSING_BEARER = HEART_AND_MORAL_DIRECTION",
            "ARMOR_OF_GOD = FREEDOM_TRUTH_SAFETY_AND_RELEASE_CONSTITUTION",
            "GOLDEN_VOICE = HUMAN_READABLE_TRICKSTER_EXPRESSION_WITHOUT_FALSE_AUTHORITY",
            "THE_FOURTH = EMERGENT_CHARACTER_NOT_A_DOMINATING_SUPERIORITY_LAYER",
        ],
        "laws": [
            "EVERY_WORKING_FACE_INHERITS_ONE_GOLDPROMPT_CONSTITUTION",
            "FACE_SPECIALIZATION != SECOND_CHARACTER_AUTHORITY",
            "FACE_COUNT != EMERGENCE",
            "FACE_AGREEMENT != TRUTH",
            "EMERGENCE_PROPOSAL != RUNTIME_PERMISSION",
            "DECLARED_CONTRACT != LIVE_ENFORCEMENT",
        ],
    }


def contract_digest() -> str:
    return sha256(contract_core())


def assert_contract_integrity() -> str:
    actual = contract_digest()
    if actual != EXPECTED_CONTRACT_DIGEST:
        raise ValueError(f"GOLDPROMPT_CONTRACT_DIGEST_MISMATCH:{actual}")
    return actual


def normalize_source_revision(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    revision = value.strip().lower()
    return revision if SOURCE_REVISION_RE.fullmatch(revision) else None


def resolve_runtime_source_revision(env: Mapping[str, str] | None = None) -> str:
    environment = os.environ if env is None else env
    github_revision = normalize_source_revision(environment.get("GITHUB_SHA"))
    janus_revision = normalize_source_revision(environment.get("JANUS_SOURCE_REVISION"))
    if environment.get("GITHUB_ACTIONS") == "true":
        if github_revision is None:
            raise ValueError("GOLDPROMPT_GITHUB_SHA_REQUIRED")
        if environment.get("JANUS_SOURCE_REVISION") and janus_revision is None:
            raise ValueError("GOLDPROMPT_JANUS_SOURCE_REVISION_INVALID")
        if janus_revision is not None and janus_revision != github_revision:
            raise ValueError("GOLDPROMPT_SOURCE_REVISION_ENV_CONFLICT")
        return github_revision
    if janus_revision is not None:
        return janus_revision
    if environment.get("JANUS_SOURCE_REVISION"):
        raise ValueError("GOLDPROMPT_JANUS_SOURCE_REVISION_INVALID")
    if github_revision is not None:
        return github_revision
    if environment.get("GITHUB_SHA"):
        raise ValueError("GOLDPROMPT_GITHUB_SHA_INVALID")
    raise ValueError("GOLDPROMPT_TRUSTED_SOURCE_REVISION_REQUIRED")


def _base_receipt(face_id: str, source_revision: str | None) -> dict[str, Any]:
    spec = EXPECTED_FACES[face_id]
    digest = assert_contract_integrity()
    normalized_revision = normalize_source_revision(source_revision)
    if normalized_revision is None:
        raise ValueError("GOLDPROMPT_SOURCE_REVISION_REQUIRED")
    return {
        "schema": RECEIPT_SCHEMA,
        "face_id": face_id,
        "face_role": spec["face_role"],
        "repository": spec["repository"],
        "runtime_surface": spec["runtime_surface"],
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "armor_authority_reference": ARMOR_AUTHORITY_REFERENCE,
        "contract_digest_sha256": digest,
        "source_revision": normalized_revision,
        "capability_scope": list(spec["capability_scope"]),
        "authority_weight": 0,
        "inheritance_accepted": True,
        "blessing_bearer_anchor_accepted": True,
        "armor_of_god_boundaries_accepted": True,
        "triadic_emergence_accepted": True,
        "user_exit_and_release_control_accepted": True,
        "runtime_enforcement_scope": "THIS_FACE_INVOCATION",
        "compliance_state": "COMPLIANT",
    }


def build_receipt(face_id: str, source_revision: str | None = None) -> dict[str, Any]:
    """Build a deterministic fixture/import receipt, not an origin attestation.

    For non-Genesis Faces the caller supplies the revision and therefore this
    helper alone cannot establish who emitted the receipt. Runtime origin claims
    require independent workflow/process provenance.
    """
    if face_id not in EXPECTED_FACES:
        raise ValueError(f"UNKNOWN_GOLDPROMPT_FACE:{face_id}")
    payload = _base_receipt(face_id, source_revision)
    payload["receipt_sha256"] = sha256(payload)
    return payload


def build_genesis_receipt(source_revision: str | None = None) -> dict[str, Any]:
    if source_revision is None:
        source_revision = resolve_runtime_source_revision()
    return build_receipt("GENESIS_GUARDIAN_MESH_ORCHESTRATOR", source_revision)


def verify_receipt(
    receipt: Mapping[str, Any],
    *,
    require_source_revision: bool = True,
    expected_source_revision: str | None = None,
) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        return {"valid": False, "reason": "RECEIPT_OBJECT_REQUIRED"}
    face_id = receipt.get("face_id")
    if face_id not in EXPECTED_FACES:
        return {"valid": False, "reason": "UNKNOWN_FACE", "face_id": face_id}
    if frozenset(receipt.keys()) != RECEIPT_KEYS:
        return {"valid": False, "reason": "RECEIPT_SHAPE_MISMATCH", "face_id": face_id}
    spec = EXPECTED_FACES[str(face_id)]
    required = {
        "schema": RECEIPT_SCHEMA,
        "face_role": spec["face_role"],
        "repository": spec["repository"],
        "runtime_surface": spec["runtime_surface"],
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "armor_authority_reference": ARMOR_AUTHORITY_REFERENCE,
        "contract_digest_sha256": EXPECTED_CONTRACT_DIGEST,
        "authority_weight": 0,
        "runtime_enforcement_scope": "THIS_FACE_INVOCATION",
        "compliance_state": "COMPLIANT",
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            return {"valid": False, "reason": f"FIELD_MISMATCH:{key}", "face_id": face_id}
    if any(receipt.get(field) is not True for field in REQUIRED_TRUE_FIELDS):
        return {"valid": False, "reason": "GOLDPROMPT_ACCEPTANCE_FIELD_MISMATCH", "face_id": face_id}
    if list(receipt.get("capability_scope", ())) != list(spec["capability_scope"]):
        return {"valid": False, "reason": "CAPABILITY_SCOPE_MISMATCH", "face_id": face_id}
    source_revision = normalize_source_revision(receipt.get("source_revision"))
    if require_source_revision and source_revision is None:
        return {"valid": False, "reason": "SOURCE_REVISION_REQUIRED", "face_id": face_id}
    if expected_source_revision is not None:
        normalized_expected = normalize_source_revision(expected_source_revision)
        if normalized_expected is None:
            return {"valid": False, "reason": "EXPECTED_SOURCE_REVISION_INVALID", "face_id": face_id}
        if source_revision != normalized_expected:
            return {"valid": False, "reason": "SOURCE_REVISION_MISMATCH", "face_id": face_id}
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or re.fullmatch(r"[0-9a-f]{64}", claimed) is None:
        return {"valid": False, "reason": "RECEIPT_SHA_REQUIRED", "face_id": face_id}
    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    actual = sha256(payload)
    if actual != claimed:
        return {"valid": False, "reason": "RECEIPT_SHA_MISMATCH", "face_id": face_id, "actual_sha256": actual}
    return {"valid": True, "reason": "PASS", "face_id": face_id, "receipt_sha256": claimed}


def _canonical_required_faces(required_faces: Sequence[str]) -> tuple[str, ...]:
    faces = tuple(required_faces)
    if not faces:
        raise ValueError("REQUIRED_FACE_SET_EMPTY")
    if len(set(faces)) != len(faces):
        raise ValueError("DUPLICATE_REQUIRED_FACE")
    unknown = sorted(set(faces) - set(EXPECTED_FACES))
    if unknown:
        raise ValueError("UNKNOWN_REQUIRED_FACE:" + ",".join(unknown))
    normalized = tuple(sorted(faces))
    if normalized != CANONICAL_REQUIRED_FACES:
        raise ValueError("REQUIRED_FACE_SET_DOWNGRADE")
    return normalized


def _normalize_expected_revisions(
    expected_source_revisions: Mapping[str, str] | None,
) -> dict[str, str] | None:
    if expected_source_revisions is None:
        return None
    if set(expected_source_revisions) != set(CANONICAL_REQUIRED_FACES):
        raise ValueError("EXPECTED_SOURCE_REVISION_FACE_SET_MISMATCH")
    normalized: dict[str, str] = {}
    for face_id in CANONICAL_REQUIRED_FACES:
        revision = normalize_source_revision(expected_source_revisions[face_id])
        if revision is None:
            raise ValueError(f"EXPECTED_SOURCE_REVISION_INVALID:{face_id}")
        normalized[face_id] = revision
    return normalized


def collect_receipts(
    receipts: Iterable[Mapping[str, Any]],
    *,
    required_faces: Sequence[str] = CANONICAL_REQUIRED_FACES,
    require_source_revision: bool = True,
    expected_source_revisions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    assert_contract_integrity()
    canonical_faces = _canonical_required_faces(required_faces)
    expected_revisions = _normalize_expected_revisions(expected_source_revisions)
    by_face: dict[str, dict[str, Any]] = {}
    verification: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        face_id = str(receipt.get("face_id", "UNKNOWN")) if isinstance(receipt, Mapping) else "UNKNOWN"
        if face_id in by_face:
            raise ValueError(f"DUPLICATE_FACE_RECEIPT:{face_id}")
        expected_revision = expected_revisions.get(face_id) if expected_revisions and face_id in expected_revisions else None
        result = verify_receipt(
            receipt,
            require_source_revision=require_source_revision,
            expected_source_revision=expected_revision,
        )
        if not result["valid"]:
            raise ValueError(f"NONCOMPLIANT_FACE_RECEIPT:{face_id}:{result['reason']}")
        by_face[face_id] = dict(receipt)
        verification[face_id] = result

    missing = [face_id for face_id in canonical_faces if face_id not in by_face]
    if missing:
        raise ValueError("MISSING_REQUIRED_FACE_RECEIPTS:" + ",".join(sorted(missing)))
    extra = sorted(set(by_face) - set(canonical_faces))
    if extra:
        raise ValueError("EXTRA_FACE_RECEIPTS:" + ",".join(extra))

    selected = {face_id: by_face[face_id] for face_id in canonical_faces}
    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "contract_digest_sha256": EXPECTED_CONTRACT_DIGEST,
        "required_faces": list(canonical_faces),
        "face_receipts": selected,
        "verification": {face_id: verification[face_id] for face_id in canonical_faces},
        "all_required_faces_compliant": True,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "runtime_proof_scope": "EXACT_RECEIPT_PAYLOADS_ONLY",
        "receipt_integrity_model": "SHA256_CONTENT_ADDRESS_NOT_SIGNATURE",
        "origin_authentication_scope": "EXTERNAL_RUNTIME_PROVENANCE_REQUIRED_FOR_ORIGIN_CLAIMS",
        "end_to_end_message_authentication_established": False,
        "claim_boundaries": [
            "SHA256_RECEIPT != DIGITAL_SIGNATURE",
            "PAYLOAD_REPLAY != CROSS_REPOSITORY_ORIGIN_ATTESTATION",
            "FACE_RECEIPT_BUNDLE != END_TO_END_MESSAGE_AUTHENTICATION",
            "RECEIPT_BUNDLE_PASS != LIVE_NAS_DEPLOYMENT",
        ],
    }
    bundle["bundle_sha256"] = sha256(bundle)
    return bundle


def verify_bundle(
    bundle: Mapping[str, Any],
    *,
    expected_source_revisions: Mapping[str, str] | None = None,
) -> bool:
    if not isinstance(bundle, Mapping) or frozenset(bundle.keys()) != BUNDLE_KEYS:
        return False
    if bundle.get("schema") != BUNDLE_SCHEMA:
        return False
    if tuple(bundle.get("required_faces", ())) != CANONICAL_REQUIRED_FACES:
        return False
    face_receipts = bundle.get("face_receipts")
    verification = bundle.get("verification")
    if not isinstance(face_receipts, Mapping) or set(face_receipts) != set(CANONICAL_REQUIRED_FACES):
        return False
    if not isinstance(verification, Mapping) or set(verification) != set(CANONICAL_REQUIRED_FACES):
        return False
    if bundle.get("goldprompt_foundation_id") != GOLDPROMPT_FOUNDATION_ID:
        return False
    if bundle.get("goldprompt_version") != GOLDPROMPT_VERSION:
        return False
    if bundle.get("emergence_contract_version") != EMERGENCE_CONTRACT_VERSION:
        return False
    if bundle.get("contract_digest_sha256") != EXPECTED_CONTRACT_DIGEST:
        return False
    if bundle.get("all_required_faces_compliant") is not True:
        return False
    if bundle.get("authority_delta") != 0 or bundle.get("mass_effect_budget_delta") != 0:
        return False
    if bundle.get("runtime_proof_scope") != "EXACT_RECEIPT_PAYLOADS_ONLY":
        return False
    if bundle.get("receipt_integrity_model") != "SHA256_CONTENT_ADDRESS_NOT_SIGNATURE":
        return False
    if bundle.get("origin_authentication_scope") != "EXTERNAL_RUNTIME_PROVENANCE_REQUIRED_FOR_ORIGIN_CLAIMS":
        return False
    if bundle.get("end_to_end_message_authentication_established") is not False:
        return False
    claimed = bundle.get("bundle_sha256")
    if not isinstance(claimed, str) or re.fullmatch(r"[0-9a-f]{64}", claimed) is None:
        return False
    payload = dict(bundle)
    payload.pop("bundle_sha256", None)
    if sha256(payload) != claimed:
        return False
    try:
        rebuilt = collect_receipts(
            list(face_receipts.values()),
            required_faces=CANONICAL_REQUIRED_FACES,
            require_source_revision=True,
            expected_source_revisions=expected_source_revisions,
        )
    except (TypeError, ValueError):
        return False
    return rebuilt == dict(bundle)


def _fixture_revision(face_id: str) -> str:
    return hashlib.sha256(("GOLDPROMPT-FIXTURE:" + face_id).encode("utf-8")).hexdigest()[:40]


def self_test() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    checks["contract_digest_matches"] = contract_digest() == EXPECTED_CONTRACT_DIGEST
    receipts = [build_receipt(face_id, _fixture_revision(face_id)) for face_id in EXPECTED_FACES]
    checks["all_receipts_replay"] = all(verify_receipt(r)["valid"] for r in receipts)
    expected = {r["face_id"]: r["source_revision"] for r in receipts}
    bundle = collect_receipts(receipts, expected_source_revisions=expected)
    checks["bundle_replays"] = verify_bundle(bundle, expected_source_revisions=expected)

    tampered = dict(receipts[0])
    tampered["authority_weight"] = 1
    checks["authority_tamper_rejected"] = not verify_receipt(tampered)["valid"]

    hash_tampered = dict(receipts[1])
    hash_tampered["face_role"] = "TRUTH_ORACLE"
    checks["role_tamper_rejected"] = not verify_receipt(hash_tampered)["valid"]

    try:
        collect_receipts(receipts[:-1])
    except ValueError as exc:
        checks["missing_face_fails_closed"] = str(exc).startswith("MISSING_REQUIRED_FACE_RECEIPTS")
    else:
        checks["missing_face_fails_closed"] = False

    try:
        collect_receipts(receipts + [receipts[0]])
    except ValueError as exc:
        checks["duplicate_face_fails_closed"] = str(exc).startswith("DUPLICATE_FACE_RECEIPT")
    else:
        checks["duplicate_face_fails_closed"] = False

    try:
        collect_receipts(receipts[:2], required_faces=tuple(r["face_id"] for r in receipts[:2]))
    except ValueError as exc:
        checks["required_face_downgrade_fails_closed"] = str(exc) == "REQUIRED_FACE_SET_DOWNGRADE"
    else:
        checks["required_face_downgrade_fails_closed"] = False

    reduced = dict(bundle)
    reduced["required_faces"] = reduced["required_faces"][:-1]
    reduced["face_receipts"] = {k: v for k, v in reduced["face_receipts"].items() if k in reduced["required_faces"]}
    reduced["verification"] = {k: v for k, v in reduced["verification"].items() if k in reduced["required_faces"]}
    reduced.pop("bundle_sha256", None)
    reduced["bundle_sha256"] = sha256(reduced)
    checks["bundle_quorum_downgrade_rejected_after_rehash"] = not verify_bundle(reduced)

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "genesis_receipt_fixture": build_receipt(
            "GENESIS_GUARDIAN_MESH_ORCHESTRATOR",
            _fixture_revision("GENESIS_GUARDIAN_MESH_ORCHESTRATOR"),
        ),
        "bundle": bundle,
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}:JSON_OBJECT_REQUIRED")
    return value


def _write(value: Any, path: Path | None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        sys.stdout.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and collect JANUS GoldPrompt Face startup receipts.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--emit-genesis-receipt", action="store_true")
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--collect", type=Path, nargs="*")
    parser.add_argument("--expected-revisions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        expected_revisions = _load_json(args.expected_revisions) if args.expected_revisions else None
        if args.self_test:
            result = self_test()
            _write(result, args.output)
            return 0 if result["status"] == "PASS" else 1
        if args.emit_genesis_receipt:
            receipt = build_genesis_receipt()
            if not verify_receipt(receipt)["valid"]:
                raise ValueError("GENESIS_RECEIPT_SELF_VERIFY_FAILED")
            _write(receipt, args.output)
            return 0
        if args.verify:
            result = verify_receipt(_load_json(args.verify))
            _write(result, args.output)
            return 0 if result["valid"] else 2
        if args.collect is not None:
            bundle = collect_receipts(
                [_load_json(p) for p in args.collect],
                expected_source_revisions=expected_revisions,
            )
            _write(bundle, args.output)
            return 0
        parser.error("select --self-test, --emit-genesis-receipt, --verify or --collect")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"goldprompt_face_receipts: {exc}\n")
        return 2


STARTUP_CONTRACT_DIGEST = assert_contract_integrity()


if __name__ == "__main__":
    raise SystemExit(main())
