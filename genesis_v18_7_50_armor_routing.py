# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.50 — canonical Armor routing bridge.

This module closes the preferred CLI's two legacy external-egress paths without
rewriting historical adapters:

* Genesis AI provider egress is Armor-authorized before provider.chat() enters
  urllib/network code.
* Durable Genesis Network sync is Armor-authorized before the legacy network
  client crosses its remote-call boundary.

v18.7.55 compatibility hardening adds a transient network-admission handoff:
the historical network adapter is now default-deny, and this canonical wrapper
sets its internal admission bit only after Armor PASS and only for the duration
of the exact sync call. The bit is restored in ``finally`` and is not evidence,
permission, or reusable authority for later calls.

Historical adapters remain importable for provenance/compatibility. Therefore
this module establishes canonical-entry routing, not repository-wide
unbypassability and not OS-level tamper resistance.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from genesis_v18_7_38_durable_network_outbox import DurableGenesisNetworkClient
from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilitySpec,
    RiskClass,
    THIRD_WISH_INTENT_SCHEMA,
)
from genesis_v18_7_47_armor_of_god import ARMOR_CONTEXT_KEY
from genesis_v18_7_48_armor_truth_guard import DECISION_DIRECT_USER_REQUEST
from genesis_v18_7_49_armor_mechanics_hardening import HardenedFundamentumArmorOfGodGate
from genesis_v18_7_ai import GenesisAIBridge

ARMOR_ROUTING_VERSION = "18.7.50"
CANONICAL_ARMOR_ENTRY = "play_genesis_armored.py"

AI_EGRESS_SPEC = CapabilitySpec(
    "GENESIS.AI.CONTEXT.EGRESS",
    RiskClass.EXTERNAL_REVERSIBLE,
    "Send bounded safe Genesis context to a user-selected model endpoint.",
    autonomy_eligible=False,
)
NETWORK_SYNC_SPEC = CapabilitySpec(
    "GENESIS.NETWORK.SYNC",
    RiskClass.EXTERNAL_REVERSIBLE,
    "Push explicitly queued public Genesis events and pull public network events.",
    autonomy_eligible=False,
)


def direct_user_armor_context(*, public_outreach: bool = False) -> dict[str, Any]:
    """Minimal exact-typed v18.7.49 context for an explicit human CLI action."""

    return {
        "decision_basis": DECISION_DIRECT_USER_REQUEST,
        "user_initiated": True,
        "fresh_human_authorization_present": False,
        "fresh_human_authorization_bound": False,
        "public_outreach": bool(public_outreach),
        "mass_effect": False,
        "requested_mass_effect_budget": 0,
        "face_count": 1,
        "requested_authority_multiplier": 1,
        "requested_reviewer_authority_multiplier": 1,
        "high_stakes": False,
        "appeal_pending": False,
        "effect_independent_of_appealed_claim": False,
    }


@dataclass
class CanonicalArmorEffectRouter:
    """Narrow bridge for legacy adapters used by the canonical CLI."""

    gate: HardenedFundamentumArmorOfGodGate

    @classmethod
    def build(cls) -> "CanonicalArmorEffectRouter":
        return cls(HardenedFundamentumArmorOfGodGate())

    def authorize(
        self,
        *,
        request_id: str,
        actor_id: str,
        capability_id: str,
        target: str,
        operation: str,
        purpose: str,
        context: Mapping[str, Any],
        spec: CapabilitySpec,
    ) -> dict[str, Any]:
        intent = ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=str(request_id),
            actor_id=str(actor_id),
            grant_id="CANONICAL-CLI-ARMOR-PREFLIGHT",
            capability_id=str(capability_id),
            target=str(target),
            operation=str(operation),
            purpose=str(purpose),
            parameters={ARMOR_CONTEXT_KEY: dict(context)},
            origin="DIRECT_USER_CLI",
            operator_instruction_present=True,
            reward_present=False,
        )
        result = self.gate.preflight(intent, spec)
        return {
            **result,
            "routing_version": ARMOR_ROUTING_VERSION,
            "canonical_entry": CANONICAL_ARMOR_ENTRY,
            "legacy_adapter_receives_armor_context": False,
        }


class ArmoredGenesisAIBridge(GenesisAIBridge):
    """GenesisAIBridge whose provider egress cannot start before Armor PASS."""

    def __init__(self, provider: Any, *, router: CanonicalArmorEffectRouter | None = None) -> None:
        super().__init__(provider)
        self.armor_router = router or CanonicalArmorEffectRouter.build()
        self._armor_sequence = 0

    def propose_action(self, world: Any, player_id: str, intention: str) -> dict[str, str]:
        self._armor_sequence += 1
        self.armor_router.authorize(
            request_id=f"CLI-AI-{self._armor_sequence}",
            actor_id=str(player_id),
            capability_id=AI_EGRESS_SPEC.capability_id,
            target="user-selected-model-endpoint",
            operation="PROPOSE_ACTION",
            purpose="USER_REQUESTED_AI_PROPOSAL",
            context=direct_user_armor_context(public_outreach=False),
            spec=AI_EGRESS_SPEC,
        )
        return super().propose_action(world, player_id, intention)


class ArmoredDurableGenesisNetworkClient(DurableGenesisNetworkClient):
    """Legacy durable network client with mandatory internal Armor preflight."""

    def __init__(self, *args: Any, router: CanonicalArmorEffectRouter | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.armor_router = router or CanonicalArmorEffectRouter.build()
        self._armor_sync_sequence = 0

    def sync(self, *, limit: int = 200) -> dict[str, Any]:
        self._armor_sync_sequence += 1
        self.armor_router.authorize(
            request_id=f"CLI-NETWORK-SYNC-{self._armor_sync_sequence}",
            actor_id="play-genesis-user",
            capability_id=NETWORK_SYNC_SPEC.capability_id,
            target=str(self.hub_url),
            operation="SYNC",
            purpose="EXPLICIT_USER_NETWORK_SYNC",
            context=direct_user_armor_context(public_outreach=True),
            spec=NETWORK_SYNC_SPEC,
        )
        previous = getattr(self, "_armor_egress_admitted", False)
        self._armor_egress_admitted = True
        try:
            return super().sync(limit=limit)
        finally:
            # No authorization residue survives the exact already-approved call.
            self._armor_egress_admitted = previous if type(previous) is bool else False


ARMOR_ROUTING_LAW_V18_7_50 = {
    "canonical_entry": CANONICAL_ARMOR_ENTRY,
    "canonical_ai_egress_requires_armor_pass": True,
    "canonical_network_sync_requires_armor_pass": True,
    "canonical_network_transient_admission_after_armor_pass": True,
    "canonical_network_admission_restored_in_finally": True,
    "direct_user_request_is_permission_source": True,
    "verification_is_permission_source": False,
    "legacy_adapter_receives_armor_context": False,
    "legacy_adapter_history_deleted": False,
    "repository_wide_legacy_bypass_proven_closed": False,
    "os_level_tamper_proof": False,
}


__all__ = [
    "AI_EGRESS_SPEC",
    "ARMOR_ROUTING_LAW_V18_7_50",
    "ARMOR_ROUTING_VERSION",
    "ArmoredDurableGenesisNetworkClient",
    "ArmoredGenesisAIBridge",
    "CANONICAL_ARMOR_ENTRY",
    "CanonicalArmorEffectRouter",
    "NETWORK_SYNC_SPEC",
    "direct_user_armor_context",
]
