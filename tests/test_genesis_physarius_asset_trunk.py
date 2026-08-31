# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import pytest

from genesis_physarius_asset_trunk import (
    AssetTrunkViolation,
    accept_exchange,
    build_exchange,
    relevant_sources,
    rights_decision,
    validate_provenance,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "asset_sources" / "ASSET_SOURCE_REGISTRY_V1.json"


def _registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_control_packet_roundtrip_is_hash_bound():
    packet = build_exchange(
        "ASSET_QUERY",
        {"query": "weathered limestone", "desired_maps": ["albedo", "normal"]},
        exchange_id="asset-test-1",
    )
    assert accept_exchange(packet) == packet


def test_tampered_packet_is_rejected():
    packet = build_exchange("ASSET_POINTER", {"source_url": "https://example.invalid/a"})
    packet["payload"]["source_url"] = "https://example.invalid/b"
    with pytest.raises(AssetTrunkViolation, match="SHA-256 mismatch"):
        accept_exchange(packet)


def test_binary_blob_cannot_ride_slime():
    with pytest.raises(AssetTrunkViolation, match="Binary-like field"):
        build_exchange("ASSET_CANDIDATE", {"blob": "AAECAwQ="})


def test_unknown_and_non_derivative_rights_fail_closed():
    assert rights_decision(None)["decision"] == "BLOCKED_PENDING_EXPLICIT_CLEARANCE"
    assert rights_decision("CC-BY-ND")["decision"] == "BLOCKED_PENDING_EXPLICIT_CLEARANCE"
    assert rights_decision("CC-BY-NC-SA")["decision"] == "BLOCKED_PENDING_EXPLICIT_CLEARANCE"


def test_cc0_and_public_domain_can_enter_auto_derivation_lane():
    assert rights_decision("CC0")["decision"] == "AUTO_DERIVATION_ALLOWED"
    assert rights_decision("public domain")["decision"] == "AUTO_DERIVATION_ALLOWED"


def test_cc_by_sa_preserves_share_alike_obligation():
    decision = rights_decision("CC-BY-SA")
    assert decision["decision"] == "CONDITIONAL_DERIVATION_ALLOWED"
    assert "ATTRIBUTION" in decision["obligations"]
    assert "SHARE_ALIKE" in decision["obligations"]


def _valid_provenance():
    return {
        "provider_id": "poly_haven",
        "source_asset_id": "stone-test",
        "source_url": "https://example.invalid/source",
        "retrieved_at": "2026-08-31T00:00:00Z",
        "rights_expression": "CC0",
        "rights_source_url": "https://polyhaven.com/license",
        "source_sha256": "a" * 64,
    }


def test_provenance_requires_hash_and_rights():
    provenance = _valid_provenance()
    assert validate_provenance(provenance)["provider_id"] == "poly_haven"

    broken = dict(provenance)
    broken.pop("rights_source_url")
    with pytest.raises(AssetTrunkViolation, match="Incomplete provenance"):
        validate_provenance(broken)


def test_provenance_with_unknown_policy_adapter_cannot_enter_derivation_lane():
    provenance = _valid_provenance()
    provenance["rights_expression"] = "CUSTOM-UNVERIFIED-LICENSE"
    with pytest.raises(AssetTrunkViolation, match="rights fail closed"):
        validate_provenance(provenance)


def test_federation_returns_all_relevant_enabled_sources_not_one_winner():
    registry = _registry()
    museums = relevant_sources(registry, ["MUSEUM_OPEN_ACCESS_API"])
    ids = {source["provider_id"] for source in museums}
    assert "smithsonian_open_access" in ids
    assert "met_open_access" in ids
    assert "rijksmuseum" in ids
    assert len(ids) >= 3


def test_no_provider_count_ceiling_is_encoded():
    registry = _registry()
    assert registry["discovery_scope"] == "OPEN_ENDED"
    assert registry["federation_policy"] == "ALL_RELEVANT_SOURCES_NOT_ONE_PREFERRED_SOURCE"
