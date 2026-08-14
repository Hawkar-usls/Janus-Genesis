from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    ORIGIN_HUMAN,
    ROLE_HUMAN_THROUGH_AI,
    GenesisAILinkGateway,
)
from genesis_v18_7_25_durable_journal_fencing import (
    DurableHashJournal,
    ProviderEffectBinding,
    SQLiteEffectFenceStore,
)
from genesis_v18_7_26_controlled_ai_link import (
    ControlMode,
    ControlledGenesisAILinkGateway,
    CrashInjector,
    CrashPoint,
    HMACProviderReceiptVerifier,
    InjectedCrash,
    ProviderReceiptClaim,
    ProviderReceiptVerificationError,
    RuntimeControlAdapter,
    RuntimeOutcomeUndetermined,
    RuntimeRequestConflict,
)
from genesis_v18_7_playable import PlayableGenesisV187


class ControlledAILinkTests(unittest.TestCase):
    def _control(self, world, root: Path, *, mode=ControlMode.SHADOW, crash=None, holder="worker-a"):
        return RuntimeControlAdapter(
            world,
            journal=DurableHashJournal(root / "runtime-control.jsonl"),
            fences=SQLiteEffectFenceStore(root / "runtime-fences.sqlite3"),
            mode=mode,
            crash_injector=crash,
            holder_id=holder,
            lease_ticks=1_000_000,
        )

    @staticmethod
    def _register(gateway):
        return gateway.register_session(
            role=ROLE_HUMAN_THROUGH_AI,
            execution_mode=MODE_AUTHORITATIVE,
            display_name="Mira",
            provider="test-provider",
            model="test-model",
            actor_id="mira",
        )

    def test_shadow_mode_preserves_existing_authoritative_result_and_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base_dir = root / "base"
            shadow_dir = root / "shadow"
            base_world = PlayableGenesisV187(base_dir)
            shadow_world = PlayableGenesisV187(shadow_dir)
            base_gateway = GenesisAILinkGateway(base_world, base_dir)
            shadow_adapter = self._control(shadow_world, shadow_dir, mode=ControlMode.SHADOW)
            shadow_gateway = ControlledGenesisAILinkGateway(
                shadow_world,
                shadow_dir,
                adapter=shadow_adapter,
            )
            base_session = self._register(base_gateway)
            shadow_session = self._register(shadow_gateway)
            action = "построить мост и оставить право не переходить"

            base_turn = base_gateway.process_turn(
                base_session["session_id"],
                action,
                origin=ORIGIN_HUMAN,
                human_confirmed=True,
            )
            shadow_turn = shadow_gateway.process_turn(
                shadow_session["session_id"],
                action,
                origin=ORIGIN_HUMAN,
                human_confirmed=True,
            )
            self.assertEqual(
                shadow_turn["result"]["runtime_result"],
                base_turn["result"]["runtime_result"],
            )
            self.assertEqual(shadow_world.public_state("mira"), base_world.public_state("mira"))
            events = shadow_adapter.journal.replay()
            self.assertEqual([e.event_type for e in events], ["SHADOW_RUNTIME_PRE", "SHADOW_RUNTIME_POST"])

    def test_crash_after_world_before_receipt_blocks_automatic_second_world_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            crash = CrashInjector(CrashPoint.AFTER_WORLD_BEFORE_RECEIPT)
            adapter = self._control(world, root, mode=ControlMode.ENFORCED, crash=crash)
            gateway = ControlledGenesisAILinkGateway(world, root, adapter=adapter)
            session = self._register(gateway)
            action = "создать тихий сад"
            tick_before = world.memory.load_player("mira").tick

            with self.assertRaises(InjectedCrash) as caught:
                gateway.process_turn(
                    session["session_id"],
                    action,
                    origin=ORIGIN_HUMAN,
                    human_confirmed=True,
                )
            self.assertEqual(caught.exception.point, CrashPoint.AFTER_WORLD_BEFORE_RECEIPT.value)
            tick_after_first = world.memory.load_player("mira").tick
            self.assertGreater(tick_after_first, tick_before)
            self.assertEqual(gateway.session_state(session["session_id"])["turns"], [])

            with self.assertRaises(RuntimeOutcomeUndetermined):
                gateway.process_turn(
                    session["session_id"],
                    action,
                    origin=ORIGIN_HUMAN,
                    human_confirmed=True,
                )
            self.assertEqual(world.memory.load_player("mira").tick, tick_after_first)
            self.assertEqual(gateway.session_state(session["session_id"])["turns"], [])

    def test_crash_after_runtime_receipt_replays_cached_result_without_second_world_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            crash = CrashInjector(CrashPoint.AFTER_RECEIPT_BEFORE_RELEASE)
            adapter = self._control(world, root, mode=ControlMode.ENFORCED, crash=crash)
            gateway = ControlledGenesisAILinkGateway(world, root, adapter=adapter)
            session = self._register(gateway)
            action = "создать музыку и не требовать слушателя"

            with self.assertRaises(InjectedCrash):
                gateway.process_turn(
                    session["session_id"],
                    action,
                    origin=ORIGIN_HUMAN,
                    human_confirmed=True,
                )
            tick_after_first = world.memory.load_player("mira").tick
            self.assertEqual(gateway.session_state(session["session_id"])["turns"], [])

            retried = gateway.process_turn(
                session["session_id"],
                action,
                origin=ORIGIN_HUMAN,
                human_confirmed=True,
            )
            self.assertTrue(retried["result"]["canonical_runtime_outcome_recorded"])
            self.assertEqual(world.memory.load_player("mira").tick, tick_after_first)
            state = gateway.session_state(session["session_id"])
            self.assertEqual(len(state["turns"]), 1)
            self.assertEqual(state["next_sequence"], 2)

    def test_same_ai_link_sequence_cannot_be_redefined_to_a_different_action(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            crash = CrashInjector(CrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD)
            adapter = self._control(world, root, mode=ControlMode.ENFORCED, crash=crash)
            request_id = "AI_LINK:fixed-sequence-1"
            with self.assertRaises(InjectedCrash):
                adapter.execute(
                    actor_id="mira",
                    action="создать тихий сад",
                    request_id=request_id,
                )
            with self.assertRaises(RuntimeRequestConflict):
                adapter.execute(
                    actor_id="mira",
                    action="построить мост",
                    request_id=request_id,
                )

    def test_successful_enforced_gateway_keeps_v18_7_19_authority_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = self._control(world, root, mode=ControlMode.ENFORCED)
            gateway = ControlledGenesisAILinkGateway(world, root, adapter=adapter)
            session = self._register(gateway)
            action = "построить мост и оставить право не переходить"
            turn = gateway.process_turn(
                session["session_id"],
                action,
                origin=ORIGIN_HUMAN,
                human_confirmed=True,
            )
            self.assertTrue(turn["result"]["authoritative_runtime"])
            self.assertTrue(turn["result"]["canonical_runtime_outcome_recorded"])
            self.assertFalse(turn["result"]["canonical_state_change_claimed"])
            sequence = turn["sequence"]
            request_id = gateway.runtime_request_id(session["session_id"], sequence)
            effect = adapter.effect_state(actor_id="mira", action=action, request_id=request_id)
            self.assertEqual(effect["state"], "SETTLED")


class ProviderReceiptVerifierTests(unittest.TestCase):
    def setUp(self):
        self.binding = ProviderEffectBinding(
            provider_id="BANK-TEST",
            effect_key="PAYMENT:55",
            authorization_id="AUTH-55",
            idempotency_key="janus-key-55",
            retry_policy="RETRY_ONLY_WITH_SAME_PROVIDER_IDEMPOTENCY_KEY",
        )
        self.verifier = HMACProviderReceiptVerifier(
            provider_id="BANK-TEST",
            secret=b"unit-test-provider-secret",
        )

    def test_reference_signed_receipt_binds_provider_effect_authorization_and_key(self):
        claim = self.verifier.sign_claim(
            effect_key=self.binding.effect_key,
            authorization_id=self.binding.authorization_id,
            idempotency_key=self.binding.idempotency_key,
            receipt_id="BANK-RECEIPT-55",
            status="SETTLED",
            payload={"amount_minor": 5500, "currency": "UAH"},
        )
        self.assertTrue(self.verifier.verify(claim, binding=self.binding))

    def test_tampered_effect_or_signature_is_rejected(self):
        claim = self.verifier.sign_claim(
            effect_key=self.binding.effect_key,
            authorization_id=self.binding.authorization_id,
            idempotency_key=self.binding.idempotency_key,
            receipt_id="BANK-RECEIPT-55",
            status="SETTLED",
            payload={"amount_minor": 5500},
        )
        wrong_effect = ProviderReceiptClaim(
            provider_id=claim.provider_id,
            effect_key="PAYMENT:OTHER",
            authorization_id=claim.authorization_id,
            idempotency_key=claim.idempotency_key,
            receipt_id=claim.receipt_id,
            status=claim.status,
            payload_sha256=claim.payload_sha256,
            signature_hex=claim.signature_hex,
        )
        with self.assertRaises(ProviderReceiptVerificationError):
            self.verifier.verify(wrong_effect, binding=self.binding)

        bad_signature = ProviderReceiptClaim(
            provider_id=claim.provider_id,
            effect_key=claim.effect_key,
            authorization_id=claim.authorization_id,
            idempotency_key=claim.idempotency_key,
            receipt_id=claim.receipt_id,
            status=claim.status,
            payload_sha256=claim.payload_sha256,
            signature_hex="00" * 32,
        )
        with self.assertRaises(ProviderReceiptVerificationError):
            self.verifier.verify(bad_signature, binding=self.binding)


if __name__ == "__main__":
    unittest.main()
