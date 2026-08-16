# -*- coding: utf-8 -*-
"""Scope audit for v18.7.56 built-in legacy AI-provider default-deny hardening."""
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
        "builtin_ai_default_deny_marker": has(
            "genesis_v18_7_ai.py",
            "LEGACY_DIRECT_AI_EGRESS_DEFAULT_DENY",
            'LEGACY_AI_DIRECT_EGRESS_ENV = "JANUS_LEGACY_AI_DIRECT_EGRESS"',
        ),
        "builtin_ai_opt_in_exact_one": has(
            "genesis_v18_7_ai.py",
            'os.environ.get(LEGACY_AI_DIRECT_EGRESS_ENV) == "1"',
        ),
        "ollama_requires_admission": has(
            "genesis_v18_7_ai.py",
            "class OllamaChatProvider(_BuiltInProviderEgressAdmission)",
            "egress_admitted=self._direct_egress_admitted()",
        ),
        "openai_compatible_requires_admission": has(
            "genesis_v18_7_ai.py",
            "class OpenAICompatibleChatProvider(_BuiltInProviderEgressAdmission)",
            "egress_admitted=self._direct_egress_admitted()",
        ),
        "canonical_ai_sets_admission_after_authorize": has(
            "genesis_v18_7_50_armor_routing.py",
            "self.armor_router.authorize",
            "provider._armor_egress_admitted = True",
            "return super().propose_action",
        ),
        "canonical_ai_restores_admission_in_finally": has(
            "genesis_v18_7_50_armor_routing.py",
            "canonical_ai_provider_admission_restored_in_finally",
            "finally:",
            "provider._armor_egress_admitted = previous",
        ),
        "legacy_network_default_deny_preserved": has(
            "genesis_v18_7_network.py",
            "LEGACY_DIRECT_NETWORK_EGRESS_DEFAULT_DENY",
        ),
    }
    scope_pass = all(checks.values())
    report = {
        "schema": "janus.genesis.legacy_direct_egress_audit.v18_7_56",
        "runtime_version": "18.7.56",
        "scope": "BUILTIN_AI_PROVIDER_REMOTE_BOUNDARY_DEFAULT_DENY",
        "checks": checks,
        "scope_pass": scope_pass,
        "default_denied_legacy_external_surfaces": [
            "genesis_v18_7_network.py selected remote HTTP boundary",
            "genesis_v18_7_ai.py built-in Ollama provider HTTP boundary",
            "genesis_v18_7_ai.py built-in OpenAI-compatible provider HTTP boundary"
        ],
        "remaining_direct_egress_debt": {
            "janus_genesis.py": "LEGACY_ROOT_GEMINI_NARRATOR_EGRESS_NOT_YET_DEFAULT_DENIED",
            "custom_chat_provider_objects": "OUTSIDE_BUILTIN_PROVIDER_ADMISSION_FENCE_BUT_STILL_PRECEDED_BY_CANONICAL_ARMOR_ROUTER_WHEN_USED_THROUGH_ARMORED_BRIDGE"
        },
        "legacy_ai_compatibility_opt_in_exists": True,
        "legacy_ai_compatibility_opt_in_is_armor_equivalent": False,
        "repository_wide_complete_routing_coverage_proven": False,
        "os_level_tamper_proof": False,
        "claim_ceiling": (
            "v18.7.56 makes the built-in historical Ollama and OpenAI-compatible "
            "provider HTTP boundaries default-deny and lets the canonical Armor bridge "
            "open a transient post-PASS admission only around one proposal call. It "
            "does not modify arbitrary custom provider implementations, does not close "
            "the old root Gemini narrator, and does not establish repository-wide unbypassability."
        ),
        "next_gate": "LEGACY_ROOT_GEMINI_DEFAULT_DENY_THEN_LOCAL_MUTATION_ADMISSION_REVIEW",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if scope_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
