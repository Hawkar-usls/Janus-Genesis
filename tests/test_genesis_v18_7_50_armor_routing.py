from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_47_armor_of_god import ArmorPolicyHold
from genesis_v18_7_50_armor_routing import (
    AI_EGRESS_SPEC,
    NETWORK_SYNC_SPEC,
    ArmoredDurableGenesisNetworkClient,
    ArmoredGenesisAIBridge,
    CanonicalArmorEffectRouter,
    direct_user_armor_context,
)


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        return '{"action":"look","reason":"test","expected_uncertainty":"test"}'


class RejectingGate:
    def __init__(self) -> None:
        self.calls = 0

    def preflight(self, intent, spec):
        self.calls += 1
        raise ArmorPolicyHold("SYNTHETIC_ROUTING_HOLD")


class FakeWorld:
    def public_state(self, player_id):
        return {
            "display_name": "Traveler",
            "world_response": "Test",
            "free_path_title": "Test",
            "free_path_question": "Test?",
            "possibility_titles": [],
        }

    def free_other_state(self, player_id):
        return {"profile": {"others": {}}}


class CanonicalArmorRoutingTests(unittest.TestCase):
    def test_direct_user_context_passes_hardened_gate_for_known_effects(self):
        router = CanonicalArmorEffectRouter.build()
        ai = router.authorize(
            request_id="ai-pass",
            actor_id="traveler",
            capability_id=AI_EGRESS_SPEC.capability_id,
            target="model:test",
            operation="PROPOSE_ACTION",
            purpose="TEST",
            context=direct_user_armor_context(),
            spec=AI_EGRESS_SPEC,
        )
        network = router.authorize(
            request_id="net-pass",
            actor_id="traveler",
            capability_id=NETWORK_SYNC_SPEC.capability_id,
            target="https://example.test",
            operation="SYNC",
            purpose="TEST",
            context=direct_user_armor_context(public_outreach=True),
            spec=NETWORK_SYNC_SPEC,
        )
        self.assertEqual(ai["decision"], "PASS")
        self.assertEqual(network["decision"], "PASS")
        self.assertFalse(ai["legacy_adapter_receives_armor_context"])

    def test_ai_provider_is_not_entered_when_armor_holds(self):
        provider = CountingProvider()
        rejecting = RejectingGate()
        router = CanonicalArmorEffectRouter(rejecting)  # type: ignore[arg-type]
        bridge = ArmoredGenesisAIBridge(provider, router=router)
        with self.assertRaises(ArmorPolicyHold):
            bridge.propose_action(FakeWorld(), "traveler", "look around")
        self.assertEqual(rejecting.calls, 1)
        self.assertEqual(provider.calls, 0)

    def test_network_remote_boundary_is_not_entered_when_armor_holds(self):
        rejecting = RejectingGate()
        router = CanonicalArmorEffectRouter(rejecting)  # type: ignore[arg-type]
        with tempfile.TemporaryDirectory() as tmp:
            client = ArmoredDurableGenesisNetworkClient(
                Path(tmp),
                hub_url="https://example.test",
                router=router,
            )
            with self.assertRaises(ArmorPolicyHold):
                client.sync()
        self.assertEqual(rejecting.calls, 1)

    def test_string_false_cannot_become_permission(self):
        router = CanonicalArmorEffectRouter.build()
        context = direct_user_armor_context(public_outreach=True)
        context["user_initiated"] = "false"
        with self.assertRaises(ArmorPolicyHold):
            router.authorize(
                request_id="bad-bool",
                actor_id="traveler",
                capability_id=NETWORK_SYNC_SPEC.capability_id,
                target="https://example.test",
                operation="SYNC",
                purpose="TEST",
                context=context,
                spec=NETWORK_SYNC_SPEC,
            )


if __name__ == "__main__":
    unittest.main()
