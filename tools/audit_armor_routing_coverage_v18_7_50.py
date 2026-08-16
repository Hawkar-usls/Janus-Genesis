# -*- coding: utf-8 -*-
"""Static JANUS Armor routing inventory for v18.7.50.

The audit intentionally distinguishes:

* canonical external-egress coverage;
* hardened default Third Wish factory admission;
* armored-compatible historical brokers;
* historical/legacy direct adapters;
* local Genesis state-mutation surfaces;
* repository-wide unbypassability (not established).

It does not turn source inspection into a security certification.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _has(path: str, *markers: str) -> bool:
    text = _text(path)
    return all(marker in text for marker in markers)


def main() -> int:
    canonical_checks = {
        "canonical_launcher_exists": (ROOT / "play_genesis_armored.py").is_file(),
        "canonical_launcher_binds_armored_ai": _has(
            "play_genesis_armored.py", "ArmoredGenesisAIBridge", "_build_ai_bridge"
        ),
        "canonical_launcher_binds_armored_network": _has(
            "play_genesis_armored.py", "ArmoredDurableGenesisNetworkClient", "_build_network_client"
        ),
        "router_uses_v18_7_49_gate": _has(
            "genesis_v18_7_50_armor_routing.py", "HardenedFundamentumArmorOfGodGate"
        ),
        "router_gates_ai_before_provider": _has(
            "genesis_v18_7_50_armor_routing.py", "self.armor_router.authorize", "return super().propose_action"
        ),
        "router_gates_network_before_sync": _has(
            "genesis_v18_7_50_armor_routing.py", "EXPLICIT_USER_NETWORK_SYNC", "return super().sync"
        ),
        "hardened_capability_factory_exists": _has(
            "genesis_v18_7_50_armored_capability_factory.py",
            "build_hardened_armored_fabric",
            "HardenedTruthGuardArmoredThirdWishCapabilityFabric",
        ),
        "plain_fabric_fails_production_factory_admission": _has(
            "genesis_v18_7_50_armored_capability_factory.py",
            "V18_7_50_PRODUCTION_BROKER_REQUIRES_HARDENED_ARMOR_FABRIC",
        ),
    }

    third_wish_brokers = {}
    for path in (
        "tools/genesis_third_wish_host_broker.py",
        "tools/genesis_third_wish_memory_swarm_broker.py",
        "tools/genesis_third_wish_sensor_model_schedule_broker.py",
        "tools/genesis_third_wish_identity_effects_broker.py",
        "tools/genesis_third_wish_active_network_broker.py",
        "tools/genesis_third_wish_github_broker.py",
        "tools/genesis_third_wish_github_high_impact_broker.py",
    ):
        if not (ROOT / path).is_file():
            third_wish_brokers[path] = "MISSING"
            continue
        text = _text(path)
        third_wish_brokers[path] = (
            "ARMORED_SUBCLASS_COMPATIBLE_USE_V18_7_50_FACTORY_FOR_NEW_WIRING"
            if "register_handler" in text and "ThirdWishCapabilityFabric" in text
            else "REVIEW_REQUIRED"
        )

    legacy_external_adapters = {
        "play_genesis.py": (
            "LEGACY_UNARMORED_ENTRY"
            if _has("play_genesis.py", "network.sync()", "GenesisAIBridge")
            else "CHANGED_REVIEW_REQUIRED"
        ),
        "genesis_v18_7_ai.py": (
            "LEGACY_DIRECT_PROVIDER_EGRESS"
            if _has("genesis_v18_7_ai.py", "urllib.request.urlopen")
            else "CHANGED_REVIEW_REQUIRED"
        ),
        "genesis_v18_7_38_durable_network_outbox.py": (
            "LEGACY_DIRECT_NETWORK_ADAPTER"
            if _has("genesis_v18_7_38_durable_network_outbox.py", "class DurableGenesisNetworkClient")
            else "CHANGED_REVIEW_REQUIRED"
        ),
    }

    local_mutation_surfaces = {
        "tools/genesis_api_server.py": (
            "UNARMORED_LOCAL_STATE_MUTATION_SURFACE"
            if _has("tools/genesis_api_server.py", "self.server.world.process_action")
            else "REVIEW_REQUIRED"
        ),
        "tools/genesis_ai_gateway.py": "GENESIS_AI_LINK_LOCAL_MUTATION_SURFACE",
        "tools/genesis_hosted_gateway.py": "HOSTED_GENESIS_LOCAL_MUTATION_SURFACE",
    }

    canonical_covered = all(canonical_checks.values())
    repository_wide_complete = False
    report = {
        "schema": "janus.genesis.armor.routing_coverage_audit.v1",
        "runtime_version": "18.7.50",
        "canonical_entry": "play_genesis_armored.py",
        "canonical_external_egress_armor_covered": canonical_covered,
        "new_third_wish_production_factory_hardened": canonical_checks[
            "hardened_capability_factory_exists"
        ] and canonical_checks["plain_fabric_fails_production_factory_admission"],
        "canonical_checks": canonical_checks,
        "third_wish_brokers": third_wish_brokers,
        "legacy_external_adapters": legacy_external_adapters,
        "local_mutation_surfaces": local_mutation_surfaces,
        "repository_wide_complete_routing_coverage_proven": repository_wide_complete,
        "tamper_proof": False,
        "claim_ceiling": (
            "The preferred v18.7.50 CLI routes optional AI-provider egress and "
            "legacy Genesis Network sync through the hardened v18.7.49 Armor gate, "
            "and new Third Wish production wiring has a fail-closed hardened factory. "
            "Historical adapters and additional local mutation surfaces remain "
            "separately callable, so repository-wide unbypassability is not established."
        ),
        "next_gate": "MIGRATE_OR_DISABLE_LEGACY_DIRECT_EFFECT_AND_LOCAL_MUTATION_ENTRYPOINTS",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if canonical_covered else 1


if __name__ == "__main__":
    raise SystemExit(main())
