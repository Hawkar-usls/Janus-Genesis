# -*- coding: utf-8 -*-
"""Scope-limited audit for JANUS v18.7.55 legacy direct-egress hardening.

This audit proves only the selected historical Genesis Network adapter has a
source-level default-deny admission fence and the canonical Armor wrapper uses a
transient post-PASS admission. It deliberately keeps the old root Gemini
narrator and genesis_v18_7_ai.py visible as remaining direct-egress debt.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def has(path: str, *markers: str) -> bool:
    value = text(path)
    return all(marker in value for marker in markers)


def main() -> int:
    checks = {
        "legacy_network_default_deny_marker": has(
            "genesis_v18_7_network.py",
            "LEGACY_DIRECT_NETWORK_EGRESS_DEFAULT_DENY",
            'LEGACY_DIRECT_EGRESS_ENV = "JANUS_LEGACY_DIRECT_EGRESS"',
        ),
        "legacy_network_opt_in_exact_one": has(
            "genesis_v18_7_network.py",
            'os.environ.get(LEGACY_DIRECT_EGRESS_ENV) == "1"',
        ),
        "legacy_network_local_queue_preserved": has(
            "genesis_v18_7_network.py",
            "def queue_public_event",
            "legacy_direct_remote_egress_default_deny",
        ),
        "canonical_wrapper_sets_transient_admission_after_authorize": has(
            "genesis_v18_7_50_armor_routing.py",
            "self.armor_router.authorize",
            "self._armor_egress_admitted = True",
            "return super().sync",
        ),
        "canonical_wrapper_restores_admission_in_finally": has(
            "genesis_v18_7_50_armor_routing.py",
            "finally:",
            "self._armor_egress_admitted = previous",
        ),
    }
    network_scope_pass = all(checks.values())
    report = {
        "schema": "janus.genesis.legacy_direct_egress_audit.v18_7_55",
        "runtime_version": "18.7.55",
        "scope": "LEGACY_GENESIS_NETWORK_DIRECT_EGRESS_DEFAULT_DENY",
        "checks": checks,
        "network_scope_pass": network_scope_pass,
        "remaining_direct_egress_debt": {
            "genesis_v18_7_ai.py": "LEGACY_DIRECT_PROVIDER_EGRESS_NOT_DEFAULT_DENIED_BY_THIS_GATE",
            "janus_genesis.py": "LEGACY_ROOT_GEMINI_NARRATOR_EGRESS_NOT_YET_MIGRATED",
        },
        "legacy_compatibility_opt_in_exists": True,
        "legacy_compatibility_opt_in_is_armor_equivalent": False,
        "repository_wide_complete_routing_coverage_proven": False,
        "os_level_tamper_proof": False,
        "claim_ceiling": (
            "v18.7.55 makes the selected historical Genesis Network remote boundary "
            "default-deny and lets the canonical Armor wrapper open only a transient "
            "post-PASS admission. It does not close the historical AI provider or root "
            "Gemini narrator, does not remove an explicit legacy compatibility opt-in, "
            "and does not establish repository-wide unbypassability."
        ),
        "next_gate": "LEGACY_ROOT_GEMINI_DEFAULT_DENY_THEN_PROVIDER_EGRESS_ADMISSION_REFACTOR",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if network_scope_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
