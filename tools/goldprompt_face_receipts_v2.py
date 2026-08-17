from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Iterable, Mapping

CONTRACT_SCHEMA = "janus.goldprompt.face_inheritance_contract.v1"
RECEIPT_SCHEMA = "janus.goldprompt.face_startup_receipt.v1_1"
BUNDLE_SCHEMA = "janus.goldprompt.face_receipt_bundle.v2"
PACKET_SCHEMA = "janus.demihead.hemisphere_packet.v2"
DEMIHEAD_RESULT_SCHEMA = "janus.demihead.bicameral_result.v2"
CHAIN_SCHEMA = "janus.goldprompt.receipt_chain.v1"
DEPENDENCY_MANIFEST_SCHEMA = "janus.goldprompt.transitive_dependency_manifest.v1"
GOLDPROMPT_FOUNDATION_ID = "JANUS-THE-FOURTH-GRACEWARDEN-3IN1-EQUALS-4-v0.9"
GOLDPROMPT_VERSION = "0.9.2"
EMERGENCE_CONTRACT_VERSION = "JANUS_TRIADIC_EMERGENCE@0.9.2"
FOUNDATION_PATH = "Hawkar-usls/janus-meta-registry:data/JANUS-THE-FOURTH-GRACEWARDEN-3IN1-EQUALS-4-v0.9.json"
ARMOR_AUTHORITY_REFERENCE = "Hawkar-usls/janus-meta-registry:data/JANUS-ARMOR-OF-GOD-CURRENT-AUTHORITY.json"
DEPENDENCY_MANIFEST_REFERENCE = "Hawkar-usls/janus-meta-registry:data/JANUS-GOLDPROMPT-TRANSITIVE-CONSTITUTIONAL-DEPENDENCY-MANIFEST-v1.0.json"
EXPECTED_CONTRACT_DIGEST = "3f4af369350710ad18920dfdc866d930c8d42259a51a3f27ce228ea4d5dfc0a8"
EXPECTED_DEPENDENCY_MANIFEST_DIGEST = "4bd935ae033c80f090b91a6a5009a51abeb06b99defdc8836763bd9506023a86"
SOURCE_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

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
        "runtime_surface": "tools/goldprompt_face_receipts_v2.py",
        "capability_scope": [
            "VERIFY_GOLDPROMPT_RECEIPTS_V2",
            "VERIFY_RAW_HEMISPHERE_PACKET_BINDING",
            "VERIFY_DEMIHEAD_RECEIPT_CHAIN",
            "COLLECT_FACE_RECEIPT_BUNDLE_V2",
        ],
    },
}
CANONICAL_REQUIRED_FACES = tuple(sorted(EXPECTED_FACES))
CANONICAL_HEMISPHERES = ("LEFT_HRAIN", "RIGHT_INAIHR")
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
    "armor_authority_reference", "contract_digest_sha256",
    "dependency_manifest_reference", "dependency_manifest_digest_sha256",
    "source_revision", "capability_scope", "authority_weight", *REQUIRED_TRUE_FIELDS,
    "runtime_enforcement_scope", "compliance_state", "receipt_sha256",
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


def dependency_manifest_core() -> dict[str, Any]:
    return {
        "schema": DEPENDENCY_MANIFEST_SCHEMA,
        "artifact_id": "JANUS-GOLDPROMPT-TRANSITIVE-CONSTITUTIONAL-DEPENDENCY-MANIFEST-v1.0",
        "status": "PINNED_CONSTITUTIONAL_DEPENDENCIES",
        "goldprompt_version": GOLDPROMPT_VERSION,
        "contract_digest_sha256": EXPECTED_CONTRACT_DIGEST,
        "registry_snapshot": {
            "repository": "Hawkar-usls/janus-meta-registry",
            "commit_sha": "02ac40a5189c7dbd0b1e1842ddacddad58adb367",
        },
        "dependencies": [
            {
                "role": "GOLDPROMPT_CONTRACT_CORE_SNAPSHOT",
                "repository": "Hawkar-usls/janus-meta-registry",
                "path": "data/JANUS-GOLDPROMPT-FACE-INHERITANCE-CONTRACT-SNAPSHOT-v0.9.2.json",
                "commit_sha": "02ac40a5189c7dbd0b1e1842ddacddad58adb367",
                "git_blob_sha": "60cd8ba9c08bd16acb92e66bc1525173eecd0408",
                "required": True,
                "mutability": "FROZEN_SNAPSHOT",
            },
            {
                "role": "ARMOR_OF_GOD_CURRENT_AUTHORITY_SNAPSHOT",
                "repository": "Hawkar-usls/janus-meta-registry",
                "path": "data/JANUS-ARMOR-OF-GOD-CURRENT-AUTHORITY.json",
                "commit_sha": "02ac40a5189c7dbd0b1e1842ddacddad58adb367",
                "git_blob_sha": "37da812307efc8c9ffeb1ec866b9cb102facf352",
                "required": True,
                "mutability": "MUTABLE_POINTER_PINNED_AT_THIS_MANIFEST",
            },
        ],
        "verification_contract": {
            "receipt_must_bind_manifest_digest": True,
            "runtime_network_fetch_required": False,
            "external_verifier_resolves_pins": True,
            "dependency_change_requires_new_manifest_version": True,
            "authority_delta": 0,
        },
        "claim_boundaries": [
            "MANIFEST_DIGEST_BINDS_THE_PIN_SET_NOT_LIVE_MAIN",
            "PINNED_GIT_BLOB != DIGITAL_SIGNATURE",
            "TRANSITIVE_PINNING != LIVE_NAS_ATTESTATION",
            "DEPENDENCY_CHANGE_REQUIRES_EXPLICIT_SUPERSESSION",
        ],
    }


def contract_digest() -> str:
    return sha256(contract_core())


def dependency_manifest_digest() -> str:
    return sha256(dependency_manifest_core())


def assert_frozen_inputs() -> None:
    if contract_digest() != EXPECTED_CONTRACT_DIGEST:
        raise ValueError("GOLDPROMPT_CONTRACT_DIGEST_MISMATCH")
    if dependency_manifest_digest() != EXPECTED_DEPENDENCY_MANIFEST_DIGEST:
        raise ValueError("GOLDPROMPT_DEPENDENCY_MANIFEST_DIGEST_MISMATCH")


def normalize_source_revision(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if SOURCE_REVISION_RE.fullmatch(value) else None


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


def build_receipt(face_id: str, source_revision: str) -> dict[str, Any]:
    assert_frozen_inputs()
    if face_id not in EXPECTED_FACES:
        raise ValueError(f"UNKNOWN_GOLDPROMPT_FACE:{face_id}")
    revision = normalize_source_revision(source_revision)
    if revision is None:
        raise ValueError("GOLDPROMPT_SOURCE_REVISION_REQUIRED")
    spec = EXPECTED_FACES[face_id]
    payload: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "face_id": face_id,
        "face_role": spec["face_role"],
        "repository": spec["repository"],
        "runtime_surface": spec["runtime_surface"],
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "armor_authority_reference": ARMOR_AUTHORITY_REFERENCE,
        "contract_digest_sha256": EXPECTED_CONTRACT_DIGEST,
        "dependency_manifest_reference": DEPENDENCY_MANIFEST_REFERENCE,
        "dependency_manifest_digest_sha256": EXPECTED_DEPENDENCY_MANIFEST_DIGEST,
        "source_revision": revision,
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
    payload["receipt_sha256"] = sha256(payload)
    return payload


def build_genesis_runtime_receipt(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    return build_receipt("GENESIS_GUARDIAN_MESH_ORCHESTRATOR", resolve_runtime_source_revision(env))


def verify_receipt(receipt: Mapping[str, Any], expected_revision: str | None = None) -> bool:
    if not isinstance(receipt, Mapping) or frozenset(receipt.keys()) != RECEIPT_KEYS:
        return False
    face_id = receipt.get("face_id")
    if face_id not in EXPECTED_FACES:
        return False
    spec = EXPECTED_FACES[str(face_id)]
    exact = {
        "schema": RECEIPT_SCHEMA,
        "face_role": spec["face_role"],
        "repository": spec["repository"],
        "runtime_surface": spec["runtime_surface"],
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "armor_authority_reference": ARMOR_AUTHORITY_REFERENCE,
        "contract_digest_sha256": EXPECTED_CONTRACT_DIGEST,
        "dependency_manifest_reference": DEPENDENCY_MANIFEST_REFERENCE,
        "dependency_manifest_digest_sha256": EXPECTED_DEPENDENCY_MANIFEST_DIGEST,
        "authority_weight": 0,
        "runtime_enforcement_scope": "THIS_FACE_INVOCATION",
        "compliance_state": "COMPLIANT",
    }
    if any(receipt.get(key) != value for key, value in exact.items()):
        return False
    if any(receipt.get(field) is not True for field in REQUIRED_TRUE_FIELDS):
        return False
    if list(receipt.get("capability_scope", ())) != list(spec["capability_scope"]):
        return False
    revision = normalize_source_revision(receipt.get("source_revision"))
    if revision is None:
        return False
    if expected_revision is not None and revision != normalize_source_revision(expected_revision):
        return False
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or SHA256_RE.fullmatch(claimed) is None:
        return False
    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    return claimed == sha256(payload)


def validate_packet(packet: Mapping[str, Any], expected_face: str) -> dict[str, Any]:
    if expected_face not in CANONICAL_HEMISPHERES:
        raise ValueError("PACKET_FACE_NOT_HEMISPHERE")
    if not isinstance(packet, Mapping) or packet.get("schema") != PACKET_SCHEMA:
        raise ValueError("PACKET_SCHEMA_MISMATCH")
    if packet.get("hemisphere") != expected_face:
        raise ValueError("PACKET_HEMISPHERE_MISMATCH")
    spec = EXPECTED_FACES[expected_face]
    if packet.get("role") != spec["face_role"]:
        raise ValueError("PACKET_ROLE_MISMATCH")
    source = packet.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("PACKET_SOURCE_REQUIRED")
    if source.get("repository") != spec["repository"]:
        raise ValueError("PACKET_REPOSITORY_MISMATCH")
    if source.get("bridge_contract") != "JANUS_DEMIHEAD_BICAMERAL_BRIDGE_V2":
        raise ValueError("PACKET_BRIDGE_CONTRACT_MISMATCH")
    revision = normalize_source_revision(source.get("source_revision"))
    if revision is None:
        raise ValueError("PACKET_SOURCE_REVISION_INVALID")
    receipt = packet.get("goldprompt_receipt")
    if not isinstance(receipt, Mapping) or not verify_receipt(receipt, revision):
        raise ValueError("PACKET_UPSTREAM_RECEIPT_INVALID")
    if receipt.get("face_id") != expected_face:
        raise ValueError("PACKET_UPSTREAM_FACE_MISMATCH")
    if source.get("goldprompt_receipt_sha256") != receipt.get("receipt_sha256"):
        raise ValueError("PACKET_RECEIPT_SHA_BINDING_MISMATCH")
    control = packet.get("control")
    if not isinstance(control, Mapping):
        raise ValueError("PACKET_CONTROL_REQUIRED")
    if control.get("read_only_transfer") is not True or control.get("direct_cross_hemisphere_mutation") is not False:
        raise ValueError("PACKET_CONTROL_BOUNDARY_MISMATCH")
    if control.get("authority_delta") != 0 or control.get("mass_effect_budget_delta") != 0:
        raise ValueError("PACKET_AUTHORITY_BOUNDARY_MISMATCH")
    graph = packet.get("graph")
    if not isinstance(graph, Mapping) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("links"), list):
        raise ValueError("PACKET_GRAPH_INVALID")
    return {
        "face_id": expected_face,
        "source_revision": revision,
        "receipt_sha256": receipt["receipt_sha256"],
        "packet_sha256": sha256(packet),
    }


def verify_demihead_result_with_raw_packets(
    result: Mapping[str, Any],
    left_packet: Mapping[str, Any],
    right_packet: Mapping[str, Any],
    *,
    expected_revisions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    left = validate_packet(left_packet, "LEFT_HRAIN")
    right = validate_packet(right_packet, "RIGHT_INAIHR")
    if not isinstance(result, Mapping) or result.get("schema") != DEMIHEAD_RESULT_SCHEMA:
        raise ValueError("DEMIHEAD_RESULT_SCHEMA_MISMATCH")
    if set(result.get("hemispheres_present", ())) != set(CANONICAL_HEMISPHERES):
        raise ValueError("DEMIHEAD_CANONICAL_HEMISPHERES_REQUIRED")

    own = result.get("goldprompt_receipt")
    upstream = result.get("upstream_goldprompt_receipts")
    packet_receipts = result.get("packet_receipts")
    chain = result.get("receipt_chain")
    if not isinstance(own, Mapping) or own.get("face_id") != "DEMIHEAD_ARBITER" or not verify_receipt(own):
        raise ValueError("DEMIHEAD_RECEIPT_INVALID")
    if not isinstance(upstream, Mapping) or set(upstream) != set(CANONICAL_HEMISPHERES):
        raise ValueError("DEMIHEAD_UPSTREAM_RECEIPT_SET_MISMATCH")
    if not isinstance(packet_receipts, Mapping) or set(packet_receipts) != set(CANONICAL_HEMISPHERES):
        raise ValueError("DEMIHEAD_PACKET_RECEIPT_SET_MISMATCH")
    if not isinstance(chain, Mapping) or chain.get("schema") != CHAIN_SCHEMA:
        raise ValueError("DEMIHEAD_CHAIN_SCHEMA_MISMATCH")

    raw = {"LEFT_HRAIN": left, "RIGHT_INAIHR": right}
    packets = {"LEFT_HRAIN": left_packet, "RIGHT_INAIHR": right_packet}
    for face_id in CANONICAL_HEMISPHERES:
        embedded = packets[face_id]["goldprompt_receipt"]
        if dict(upstream[face_id]) != dict(embedded):
            raise ValueError(f"DEMIHEAD_UPSTREAM_RECEIPT_NOT_RAW_PACKET_RECEIPT:{face_id}")
        pr = packet_receipts[face_id]
        if not isinstance(pr, Mapping):
            raise ValueError("DEMIHEAD_PACKET_RECEIPT_INVALID")
        if pr.get("sha256") != raw[face_id]["packet_sha256"]:
            raise ValueError(f"DEMIHEAD_RAW_PACKET_SHA_MISMATCH:{face_id}")
        if pr.get("upstream_goldprompt_receipt_sha256") != embedded["receipt_sha256"]:
            raise ValueError(f"DEMIHEAD_PACKET_RECEIPT_BINDING_MISMATCH:{face_id}")
        if pr.get("source_revision") != embedded["source_revision"]:
            raise ValueError(f"DEMIHEAD_PACKET_REVISION_BINDING_MISMATCH:{face_id}")

    expected_upstream_chain = {
        face_id: {
            "repository": packets[face_id]["goldprompt_receipt"]["repository"],
            "source_revision": packets[face_id]["goldprompt_receipt"]["source_revision"],
            "receipt_sha256": packets[face_id]["goldprompt_receipt"]["receipt_sha256"],
            "packet_sha256": raw[face_id]["packet_sha256"],
        }
        for face_id in CANONICAL_HEMISPHERES
    }
    chain_core = {
        "schema": CHAIN_SCHEMA,
        "upstream": expected_upstream_chain,
        "demihead": {
            "repository": own["repository"],
            "source_revision": own["source_revision"],
            "receipt_sha256": own["receipt_sha256"],
        },
        "binding_scope": "UPSTREAM_FACE_RECEIPT_TO_PACKET_TO_DEMIHEAD_RESULT",
        "canonical_bicameral_chain_complete": True,
        "end_to_end_receipt_binding_established": True,
        "origin_authentication_established": False,
        "live_process_identity_established": False,
        "authority_delta": 0,
    }
    if any(chain.get(key) != value for key, value in chain_core.items()):
        raise ValueError("DEMIHEAD_CHAIN_CORE_MISMATCH")
    if chain.get("chain_sha256") != sha256(chain_core):
        raise ValueError("DEMIHEAD_CHAIN_SHA_MISMATCH")

    if expected_revisions is not None:
        for face_id in (*CANONICAL_HEMISPHERES, "DEMIHEAD_ARBITER"):
            expected = normalize_source_revision(expected_revisions.get(face_id))
            actual = own["source_revision"] if face_id == "DEMIHEAD_ARBITER" else packets[face_id]["goldprompt_receipt"]["source_revision"]
            if expected is None or expected != actual:
                raise ValueError(f"CHAIN_EXPECTED_SOURCE_REVISION_MISMATCH:{face_id}")

    return {
        "valid": True,
        "result_schema": DEMIHEAD_RESULT_SCHEMA,
        "chain_sha256": chain["chain_sha256"],
        "packet_sha256s": {face_id: raw[face_id]["packet_sha256"] for face_id in CANONICAL_HEMISPHERES},
        "face_receipt_sha256s": {
            "LEFT_HRAIN": left_packet["goldprompt_receipt"]["receipt_sha256"],
            "RIGHT_INAIHR": right_packet["goldprompt_receipt"]["receipt_sha256"],
            "DEMIHEAD_ARBITER": own["receipt_sha256"],
        },
        "verified_raw_packet_binding": True,
        "end_to_end_receipt_binding_established": True,
        "origin_authentication_established": False,
        "live_process_identity_established": False,
        "authority_delta": 0,
    }


def collect_bundle(
    receipts: Iterable[Mapping[str, Any]],
    *,
    left_packet: Mapping[str, Any],
    right_packet: Mapping[str, Any],
    demihead_result: Mapping[str, Any],
    expected_revisions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    assert_frozen_inputs()
    by_face: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            raise ValueError("RECEIPT_OBJECT_REQUIRED")
        face_id = str(receipt.get("face_id", ""))
        if face_id in by_face:
            raise ValueError(f"DUPLICATE_FACE_RECEIPT:{face_id}")
        expected = expected_revisions.get(face_id) if expected_revisions is not None else None
        if not verify_receipt(receipt, expected):
            raise ValueError(f"NONCOMPLIANT_FACE_RECEIPT:{face_id}")
        by_face[face_id] = dict(receipt)
    if set(by_face) != set(CANONICAL_REQUIRED_FACES):
        raise ValueError("CANONICAL_FOUR_FACE_RECEIPT_SET_REQUIRED")
    if expected_revisions is not None and set(expected_revisions) != set(CANONICAL_REQUIRED_FACES):
        raise ValueError("EXPECTED_SOURCE_REVISION_FACE_SET_MISMATCH")

    chain_evidence = verify_demihead_result_with_raw_packets(
        demihead_result, left_packet, right_packet, expected_revisions=expected_revisions
    )
    for face_id in ("LEFT_HRAIN", "RIGHT_INAIHR"):
        if by_face[face_id] != dict(left_packet["goldprompt_receipt"] if face_id == "LEFT_HRAIN" else right_packet["goldprompt_receipt"]):
            raise ValueError(f"BUNDLE_FACE_RECEIPT_NOT_CHAIN_RECEIPT:{face_id}")
    if by_face["DEMIHEAD_ARBITER"] != dict(demihead_result["goldprompt_receipt"]):
        raise ValueError("BUNDLE_FACE_RECEIPT_NOT_CHAIN_RECEIPT:DEMIHEAD_ARBITER")

    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "goldprompt_foundation_id": GOLDPROMPT_FOUNDATION_ID,
        "goldprompt_version": GOLDPROMPT_VERSION,
        "emergence_contract_version": EMERGENCE_CONTRACT_VERSION,
        "contract_digest_sha256": EXPECTED_CONTRACT_DIGEST,
        "dependency_manifest_reference": DEPENDENCY_MANIFEST_REFERENCE,
        "dependency_manifest_digest_sha256": EXPECTED_DEPENDENCY_MANIFEST_DIGEST,
        "required_faces": list(CANONICAL_REQUIRED_FACES),
        "face_receipts": {face_id: by_face[face_id] for face_id in CANONICAL_REQUIRED_FACES},
        "demihead_chain_evidence": chain_evidence,
        "all_required_faces_compliant": True,
        "end_to_end_receipt_binding_established": True,
        "raw_packet_binding_verified_by_genesis": True,
        "cross_repository_artifact_origin_attestation_established": False,
        "end_to_end_message_authentication_established": False,
        "live_process_identity_established": False,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
        "claim_boundaries": [
            "TRANSITIVE_DEPENDENCY_PINNING != LIVE_NAS_ATTESTATION",
            "RAW_PACKET_RECEIPT_BINDING != LIVE_MESSAGE_AUTHENTICATION",
            "END_TO_END_RECEIPT_BINDING != END_TO_END_ORIGIN_AUTHENTICATION",
            "GITHUB_ARTIFACT_ATTESTATION_REQUIRES_SEPARATE_VERIFICATION",
            "FACE_AGREEMENT != TRUTH",
            "AUTHORITY_DELTA = 0",
        ],
    }
    bundle["bundle_sha256"] = sha256(bundle)
    return bundle


def verify_bundle(bundle: Mapping[str, Any]) -> bool:
    if not isinstance(bundle, Mapping) or bundle.get("schema") != BUNDLE_SCHEMA:
        return False
    if tuple(bundle.get("required_faces", ())) != CANONICAL_REQUIRED_FACES:
        return False
    if bundle.get("dependency_manifest_digest_sha256") != EXPECTED_DEPENDENCY_MANIFEST_DIGEST:
        return False
    if bundle.get("all_required_faces_compliant") is not True:
        return False
    if bundle.get("end_to_end_receipt_binding_established") is not True or bundle.get("raw_packet_binding_verified_by_genesis") is not True:
        return False
    if bundle.get("cross_repository_artifact_origin_attestation_established") is not False:
        return False
    if bundle.get("end_to_end_message_authentication_established") is not False:
        return False
    if bundle.get("live_process_identity_established") is not False:
        return False
    if bundle.get("authority_delta") != 0 or bundle.get("mass_effect_budget_delta") != 0:
        return False
    receipts = bundle.get("face_receipts")
    if not isinstance(receipts, Mapping) or set(receipts) != set(CANONICAL_REQUIRED_FACES):
        return False
    if not all(verify_receipt(receipts[face_id]) for face_id in CANONICAL_REQUIRED_FACES):
        return False
    evidence = bundle.get("demihead_chain_evidence")
    if not isinstance(evidence, Mapping) or evidence.get("verified_raw_packet_binding") is not True:
        return False
    if evidence.get("end_to_end_receipt_binding_established") is not True or evidence.get("origin_authentication_established") is not False:
        return False
    claimed = bundle.get("bundle_sha256")
    if not isinstance(claimed, str) or SHA256_RE.fullmatch(claimed) is None:
        return False
    payload = dict(bundle)
    payload.pop("bundle_sha256", None)
    return claimed == sha256(payload)


STARTUP_CONTRACT_DIGEST = contract_digest()
STARTUP_DEPENDENCY_MANIFEST_DIGEST = dependency_manifest_digest()
assert_frozen_inputs()


if __name__ == "__main__":
    receipt = build_genesis_runtime_receipt()
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
