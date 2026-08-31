# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import unittest
from pathlib import Path

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


class GenesisPhysariusAssetTrunkTests(unittest.TestCase):
    def test_control_packet_roundtrip_is_hash_bound(self):
        packet = build_exchange(
            "ASSET_QUERY",
            {"query": "weathered limestone", "desired_maps": ["albedo", "normal"]},
            exchange_id="asset-test-1",
        )
        self.assertEqual(accept_exchange(packet), packet)

    def test_tampered_packet_is_rejected(self):
        packet = build_exchange("ASSET_POINTER", {"source_url": "https://example.invalid/a"})
        packet["payload"]["source_url"] = "https://example.invalid/b"
        with self.assertRaisesRegex(AssetTrunkViolation, "SHA-256 mismatch"):
            accept_exchange(packet)

    def test_binary_blob_cannot_ride_slime(self):
        with self.assertRaisesRegex(AssetTrunkViolation, "Binary-like field"):
            build_exchange("ASSET_CANDIDATE", {"blob": "AAECAwQ="})

    def test_unknown_and_non_derivative_rights_fail_closed(self):
        self.assertEqual(rights_decision(None)["decision"], "BLOCKED_PENDING_EXPLICIT_CLEARANCE")
        self.assertEqual(rights_decision("CC-BY-ND")["decision"], "BLOCKED_PENDING_EXPLICIT_CLEARANCE")
        self.assertEqual(rights_decision("CC-BY-NC-SA")["decision"], "BLOCKED_PENDING_EXPLICIT_CLEARANCE")

    def test_cc0_and_public_domain_can_enter_auto_derivation_lane(self):
        self.assertEqual(rights_decision("CC0")["decision"], "AUTO_DERIVATION_ALLOWED")
        self.assertEqual(rights_decision("public domain")["decision"], "AUTO_DERIVATION_ALLOWED")

    def test_cc_by_sa_preserves_share_alike_obligation(self):
        decision = rights_decision("CC-BY-SA")
        self.assertEqual(decision["decision"], "CONDITIONAL_DERIVATION_ALLOWED")
        self.assertIn("ATTRIBUTION", decision["obligations"])
        self.assertIn("SHARE_ALIKE", decision["obligations"])

    def test_provenance_requires_hash_and_rights(self):
        provenance = _valid_provenance()
        self.assertEqual(validate_provenance(provenance)["provider_id"], "poly_haven")

        broken = dict(provenance)
        broken.pop("rights_source_url")
        with self.assertRaisesRegex(AssetTrunkViolation, "Incomplete provenance"):
            validate_provenance(broken)

    def test_provenance_with_unknown_policy_adapter_cannot_enter_derivation_lane(self):
        provenance = _valid_provenance()
        provenance["rights_expression"] = "CUSTOM-UNVERIFIED-LICENSE"
        with self.assertRaisesRegex(AssetTrunkViolation, "rights fail closed"):
            validate_provenance(provenance)

    def test_federation_returns_all_relevant_enabled_sources_not_one_winner(self):
        registry = _registry()
        museums = relevant_sources(registry, ["MUSEUM_OPEN_ACCESS_API"])
        ids = {source["provider_id"] for source in museums}
        self.assertIn("smithsonian_open_access", ids)
        self.assertIn("met_open_access", ids)
        self.assertIn("rijksmuseum", ids)
        self.assertGreaterEqual(len(ids), 3)

    def test_no_provider_count_ceiling_is_encoded(self):
        registry = _registry()
        self.assertEqual(registry["discovery_scope"], "OPEN_ENDED")
        self.assertEqual(registry["federation_policy"], "ALL_RELEVANT_SOURCES_NOT_ONE_PREFERRED_SOURCE")


if __name__ == "__main__":
    unittest.main()
