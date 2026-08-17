from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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


def _base_receipt(face_id: str, source_revision: str | None) -> dict[str, Any]:
    spec = EXPECTED_FACES[face_id]
    digest = assert_contract_integrity()
    source_revision = source_revision.strip() if isinstance(source_revision, str) and source_revision.strip() else None
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
        "source_revision": source_revision,
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
    if face_id not in EXPECTED_FACES:
        raise ValueError(f"UNKNOWN_GOLDPROMPT_FACE:{face_id}")
    payload = _base_receipt(face_id, source_revision)
    payload["receipt_sha256"] = sha256(payload)
    return payload


def build_genesis_receipt(source_revision: str | None = None) -> dict[str, Any]:
    if source_revision is None:
        source_revision = os.environ.get("GITHUB_SHA") or os.environ.get("JANUS_SOURCE_REVISION")
    return build_receipt("GENESIS_GUARDIAN_MESH_ORCHESTRATOR", source_revision)


def verify_receipt(receipt: Mapping[str, Any], *, require_source_revision: bool = True) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        return {"valid": False, "reason": "RECEIPT_OBJECT_REQUIRED"}
    face_id = receipt.get("face_id")
    if face_id not in EXPECTED_FACES:
        return {"valid": False, "reason": "UNKNOWN_FACE", "face_id": face_id}
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
        "inheritance_accepted": True,
        "blessing_bearer_anchor_accepted": True,
        "armor_of_god_boundaries_accepted": True,
        "triadic_emergence_accepted": True,
        "user_exit_and_release_control_accepted": True,
        "runtime_enforcement_scope": "THIS_FACE_INVOCATION",
        "compliance_state": "COMPLIANT",
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            return {"valid": False, "reason": f"FIELD_MISMATCH:{key}", "face_id": face_id}
    if list(receipt.get("capability_scope", ())) != list(spec["capability_scope"]):
        return {"valid": False, "reason": "CAPABILITY_SCOPE_MISMATCH", "face_id": face_id}
    source_revision = receipt.get("source_revision")
    if require_source_revision and (not isinstance(source_revision, str) or not source_revision.strip()):
        return {"valid": False, "reason": "SOURCE_REVISION_REQUIRED", "face_id": face_id}
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str):
        return {"valid": False, "reason": "RECEIPT_SHA_REQUIRED", "face_id": face_id}
    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    actual = sha256(payload)
    if actual != claimed:
        return {"valid": False, "reason": "RECEIPT_SHA_MISMATCH", "face_id": face_id, "actual_sha256": actual}
    return {"valid": True, "reason": "PASS", "face_id": face_id, "receipt_sha256": claimed}


def collect_receipts(
    receipts: Iterable[Mapping[str, Any]],
    *,
    required_faces: Sequence[str] = tuple(EXPECTED_FACES),
    require_source_revision: bool = True,
) -> dict[str, Any]:
    assert_contract_integrity()
    by_face: dict[str, dict[str, Any]] = {}
    verification: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        result = verify_receipt(receipt, require_source_revision=require_source_revision)
        face_id = str(receipt.get("face_id", "UNKNOWN")) if isinstance(receipt, Mapping) else "UNKNOWN"
        if face_id in by_face:
            raise ValueError(f"DUPLICATE_FACE_RECEIPT:{face_id}")
        if not result["valid"]:
            raise ValueError(f"NONCOMPLIANT_FACE_RECEIPT:{face_id}:{result['reason']}")
        by_face[face_id] = dict(receipt)
        verification[face_id] = result

    missing = [face_id for face_id in required_faces if face_id not in by_face]
    if missing:
        raise ValueError("MISSING_REQUIRED_FACE_RECEIPTS:" + ",".join(sorted(missing)))

    selected = {face_id: by_face[face_id] for face_id in sorted(required_faces)}
    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "contract_digest_sha256": EXPECTED_CONTRACT_DIGEST,
        "required_faces": sorted(required_faces),
        "face_receipts": selected,
        "verification": {face_id: verification[face_id] for face_id in sorted(required_faces)},
        "all_required_faces_compliant": True,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "runtime_proof_scope": "EXACT_RECEIPT_PAYLOADS_ONLY",
        "claim_boundary": "RECEIPT_BUNDLE_PASS != LIVE_NAS_DEPLOYMENT",
    }
    bundle["bundle_sha256"] = sha256(bundle)
    return bundle


def verify_bundle(bundle: Mapping[str, Any]) -> bool:
    if not isinstance(bundle, Mapping) or bundle.get("schema") != BUNDLE_SCHEMA:
        return False
    claimed = bundle.get("bundle_sha256")
    if not isinstance(claimed, str):
        return False
    payload = dict(bundle)
    payload.pop("bundle_sha256", None)
    if sha256(payload) != claimed:
        return False
    try:
        rebuilt = collect_receipts(
            list(bundle.get("face_receipts", {}).values()),
            required_faces=tuple(bundle.get("required_faces", ())),
            require_source_revision=True,
        )
    except (TypeError, ValueError):
        return False
    return rebuilt["bundle_sha256"] == claimed


def self_test() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    checks["contract_digest_matches"] = contract_digest() == EXPECTED_CONTRACT_DIGEST
    receipts = [build_receipt(face_id, f"TEST-{face_id}") for face_id in EXPECTED_FACES]
    checks["all_receipts_replay"] = all(verify_receipt(r)["valid"] for r in receipts)
    bundle = collect_receipts(receipts)
    checks["bundle_replays"] = verify_bundle(bundle)

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

    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "genesis_receipt": build_genesis_receipt("SELFTEST-GENESIS"),
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
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
            bundle = collect_receipts([_load_json(p) for p in args.collect])
            _write(bundle, args.output)
            return 0
        parser.error("select --self-test, --emit-genesis-receipt, --verify or --collect")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"goldprompt_face_receipts: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
