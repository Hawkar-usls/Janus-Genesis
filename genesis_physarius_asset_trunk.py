# -*- coding: utf-8 -*-
"""PHYSARIUS_ASSET_TRUNK_V1 control-plane primitives for JANUS Genesis.

The trunk transports queries, pointers, rights attestations and provenance only.
Bulk asset bytes remain on the provider/CDN data plane and are never accepted as
SLIME payloads. Discovery does not grant reuse authority: rights are evaluated
per item and unknown or unsupported rights fail closed.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

SCHEMA = "janus.physarius.asset_exchange.v1"
VERSION = "1.0.0"
MAX_CONTROL_PACKET_BYTES = 64 * 1024

MESSAGE_CLASSES = frozenset(
    {
        "ASSET_QUERY",
        "ASSET_CANDIDATE",
        "ASSET_POINTER",
        "LICENSE_ATTESTATION",
        "PROVENANCE_POINTER",
        "DERIVATION_REQUEST",
        "DERIVATION_RECEIPT",
        "CACHE_POINTER",
    }
)

FORBIDDEN_BINARY_KEYS = frozenset(
    {
        "base64",
        "binary",
        "blob",
        "bytes",
        "data_uri",
        "file_bytes",
        "raw_bytes",
    }
)

PROVENANCE_REQUIRED = frozenset(
    {
        "provider_id",
        "source_asset_id",
        "source_url",
        "retrieved_at",
        "rights_expression",
        "rights_source_url",
        "source_sha256",
    }
)

_CONTROL = {
    "read_only_transfer": True,
    "binary_payload_allowed": False,
    "direct_source_mutation": False,
    "authority_delta": 0,
    "scientific_claim_promotion": False,
    "proof_authority": False,
}


class AssetTrunkViolation(ValueError):
    """Raised when an asset control packet violates the frozen trunk laws."""


def _stable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _stable(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_stable(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _stable(value),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _walk_forbidden_binary(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}"
            if key_text in FORBIDDEN_BINARY_KEYS:
                raise AssetTrunkViolation(
                    f"Binary-like field is forbidden on SLIME control plane: {child_path}"
                )
            _walk_forbidden_binary(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk_forbidden_binary(child, f"{path}[{index}]")
    elif isinstance(value, (bytes, bytearray, memoryview)):
        raise AssetTrunkViolation(f"Binary value is forbidden on SLIME control plane: {path}")


def _validate_control(control: Mapping[str, Any]) -> None:
    if dict(control) != _CONTROL:
        raise AssetTrunkViolation("Unsafe or non-canonical asset trunk control envelope")


def _validate_packet_size(packet: Mapping[str, Any]) -> None:
    if len(canonical_bytes(packet)) > MAX_CONTROL_PACKET_BYTES:
        raise AssetTrunkViolation("Asset control packet exceeds 64 KiB control-plane ceiling")


def build_exchange(
    message_class: str,
    payload: Mapping[str, Any] | None = None,
    *,
    source: str = "JANUS_GENESIS",
    target: str = "GENESIS_OPEN_ASSET_FEDERATION",
    previous_exchange_sha256: str | None = None,
    exchange_id: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic, hash-bound SLIME control-plane exchange."""
    if message_class not in MESSAGE_CLASSES:
        raise AssetTrunkViolation(f"Unsupported asset message class: {message_class}")

    clean_payload = dict(payload or {})
    _walk_forbidden_binary(clean_payload)
    identity_material = {"message_class": message_class, "payload": clean_payload}

    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "version": VERSION,
        "exchange_id": exchange_id or f"asset-{sha256_hex(identity_material)[:24]}",
        "source": source,
        "target": target,
        "message_class": message_class,
        "payload": clean_payload,
        "previous_exchange_sha256": previous_exchange_sha256,
        "control": dict(_CONTROL),
    }
    packet["exchange_sha256"] = sha256_hex(packet)
    _validate_packet_size(packet)
    return packet


def accept_exchange(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Verify an incoming asset exchange before it can enter Genesis context."""
    if packet.get("schema") != SCHEMA:
        raise AssetTrunkViolation("Unsupported asset exchange schema")
    if packet.get("version") != VERSION:
        raise AssetTrunkViolation("Unsupported asset exchange version")
    if packet.get("message_class") not in MESSAGE_CLASSES:
        raise AssetTrunkViolation("Unsupported asset message class")

    control = packet.get("control")
    if not isinstance(control, Mapping):
        raise AssetTrunkViolation("Missing asset trunk control envelope")
    _validate_control(control)

    payload = packet.get("payload")
    if not isinstance(payload, Mapping):
        raise AssetTrunkViolation("Asset exchange payload must be an object")
    _walk_forbidden_binary(payload)
    _validate_packet_size(packet)

    received_hash = packet.get("exchange_sha256")
    if not isinstance(received_hash, str):
        raise AssetTrunkViolation("Missing exchange SHA-256")
    unsigned = dict(packet)
    unsigned.pop("exchange_sha256", None)
    if received_hash != sha256_hex(unsigned):
        raise AssetTrunkViolation("Asset exchange SHA-256 mismatch")

    return dict(packet)


def normalize_rights(rights_expression: str | None) -> str:
    if not rights_expression:
        return "UNKNOWN"
    normalized = rights_expression.strip().upper().replace("_", "-").replace(" ", "-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    aliases = {
        "PUBLIC-DOMAIN": "PUBLIC_DOMAIN",
        "PUBLICDOMAIN": "PUBLIC_DOMAIN",
        "PD": "PUBLIC_DOMAIN",
        "CC-0": "CC0",
        "CREATIVE-COMMONS-ZERO": "CC0",
        "ALL-RIGHTS-RESERVED": "ALL_RIGHTS_RESERVED",
    }
    return aliases.get(normalized, normalized)


def rights_decision(rights_expression: str | None) -> dict[str, Any]:
    """Return a fail-closed derivative-use decision without pretending to be legal advice."""
    rights = normalize_rights(rights_expression)
    if rights in {"CC0", "PUBLIC_DOMAIN"}:
        return {"decision": "AUTO_DERIVATION_ALLOWED", "rights": rights}
    if rights in {"CC-BY", "CC-BY-SA"}:
        return {
            "decision": "CONDITIONAL_DERIVATION_ALLOWED",
            "rights": rights,
            "obligations": ["ATTRIBUTION"] + (["SHARE_ALIKE"] if rights == "CC-BY-SA" else []),
        }
    if rights in {
        "UNKNOWN",
        "ALL_RIGHTS_RESERVED",
        "CC-BY-ND",
        "CC-BY-NC",
        "CC-BY-NC-SA",
        "CC-BY-NC-ND",
    }:
        return {"decision": "BLOCKED_PENDING_EXPLICIT_CLEARANCE", "rights": rights}
    return {"decision": "REQUIRE_POLICY_ADAPTER", "rights": rights}


def validate_provenance(provenance: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(PROVENANCE_REQUIRED - set(provenance))
    if missing:
        raise AssetTrunkViolation(f"Incomplete provenance: missing {', '.join(missing)}")
    digest = provenance.get("source_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise AssetTrunkViolation("source_sha256 must be a 64-character SHA-256 hex digest")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise AssetTrunkViolation("source_sha256 is not hexadecimal") from exc

    decision = rights_decision(provenance.get("rights_expression"))
    if decision["decision"] not in {
        "AUTO_DERIVATION_ALLOWED",
        "CONDITIONAL_DERIVATION_ALLOWED",
    }:
        raise AssetTrunkViolation("Provenance rights fail closed")
    return dict(provenance)


def relevant_sources(
    registry: Mapping[str, Any],
    required_classes: Iterable[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return every relevant enabled adapter; never collapse the federation to one winner."""
    wanted = set(required_classes or ())
    selected: list[dict[str, Any]] = []
    for source in registry.get("sources", []):
        if not isinstance(source, Mapping):
            continue
        status = str(source.get("status", ""))
        if not status.startswith("ENABLED"):
            continue
        classes = set(source.get("classes", []))
        if wanted and not (wanted & classes):
            continue
        selected.append(dict(source))
    return tuple(selected)


LAWS = (
    "SLIME_CONTROL_PLANE_NE_BINARY_DATA_PLANE",
    "DISCOVERY_NE_LICENSE_CLEARANCE",
    "UNKNOWN_RIGHTS_FAIL_CLOSED",
    "PROVENANCE_SURVIVES_DERIVATION",
    "FEDERATION_NE_WINNER_TAKE_ALL",
)
