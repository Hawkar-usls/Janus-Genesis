from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    ORIGIN_HUMAN,
    ROLE_HUMAN_THROUGH_AI,
)
from genesis_v18_7_25_durable_journal_fencing import (
    DurableHashJournal,
    ProviderEffectBinding,
    SQLiteEffectFenceStore,
)
from genesis_v18_7_26_controlled_ai_link import (
    ControlMode,
    CrashInjector,
    CrashPoint,
    InjectedCrash,
    RuntimeControlAdapter,
    RuntimeFenceUnavailable,
    RuntimeOutcomeUndetermined,
)
from genesis_v18_7_27_session_review_reconciliation import (
    FaceReviewCandidate,
    IndependentReviewUnavailable,
    LineageIndependentReviewPlanner,
    LockedControlledGenesisAILinkGateway,
    ProviderLookupContractError,
    ProviderLookupObservation,
    ProviderLookupOutcome,
    ProviderLookupReconciler,
)
from genesis_v18_7_playable import PlayableGenesisV187


class ManualClock:
    def __init__(self, value=100):
        self.value = int(value)

    def __call__(self):
        return self.value

    def advance(self, delta):
        self.value += int(delta)


class SessionAtomicityTests(unittest.TestCase):
    @staticmethod
    def _adapter(world, root: Path, holder: str):
        return RuntimeControlAdapter(
            world,
            journal=DurableHashJournal(root / "runtime-control.jsonl"),
            fences=SQLiteEffectFenceStore(root / "runtime-fences.sqlite3"),
            mode=ControlMode.ENFORCED,
            holder_id=holder,
            lease_ticks=1_000_000,
        )

    def test_two_gateway_instances_serialize_one_session_into_unique_sequences(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            gateway_a = LockedControlledGenesisAILinkGateway(
                world,
                root,
                adapter=self._adapter(world, root, "worker-a"),
            )
            session = gateway_a.register_session(
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode=MODE_AUTHORITATIVE,
                display_name="Mira",
                provider="test-provider",
                model="test-model",
                actor_id="mira",
            )
            gateway_b = LockedControlledGenesisAILinkGateway(
                world,
                root,
                adapter=self._adapter(world, root, "worker-b"),
            )
            start = threading.Barrier(2)

            def run(gateway, action):
                start.wait()
                return gateway.process_turn(
                    session["session_id"],
                    action,
                    origin=ORIGIN_HUMAN,
                    human_confirmed=True,
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(gateway_a.process_turn, session["session_id"], "создать тихий сад", origin=ORIGIN_HUMAN, human_confirmed=True),
                    pool.submit(gateway_b.process_turn, session["session_id"], "создать музыку", origin=ORIGIN_HUMAN, human_confirmed=True),
                ]
                turns = [future.result(timeout=10) for future in futures]

            self.assertEqual(sorted(turn["sequence"] for turn in turns), [1, 2])
            state = gateway_a.session_state(session["session_id"])
            self.assertEqual([turn["sequence"] for turn in state["turns"]], [1, 2])
            self.assertEqual(state["next_sequence"], 3)


class LineageIndependentReviewTests(unittest.TestCase):
    def test_cloned_face_ids_count_as_one_independent_lineage(self):
        planner = LineageIndependentReviewPlanner()
        candidates = [
            FaceReviewCandidate("FACE_B1", "LINEAGE_B", routing_priority=5.0),
            FaceReviewCandidate("FACE_B2", "LINEAGE_B", routing_priority=4.0),
        ]
        with self.assertRaises(IndependentReviewUnavailable):
            planner.plan(
                origin_lineage_root="LINEAGE_A",
                candidates=candidates,
                required_reviews=2,
            )

    def test_origin_lineage_is_excluded_and_novel_counterevidence_gets_review_access(self):
        planner = LineageIndependentReviewPlanner()
        candidates = [
            FaceReviewCandidate("FACE_A_FORK", "LINEAGE_A", routing_priority=100.0),
            FaceReviewCandidate("FACE_B", "LINEAGE_B", routing_priority=9.0),
            FaceReviewCandidate("FACE_C", "LINEAGE_C", routing_priority=8.0),
            FaceReviewCandidate(
                "FACE_D_LOW",
                "LINEAGE_D",
                routing_priority=0.1,
                novel_counterevidence=True,
            ),
        ]
        assignments = planner.plan(
            origin_lineage_root="LINEAGE_A",
            candidates=candidates,
            required_reviews=2,
        )
        self.assertEqual(len(assignments), 2)
        self.assertNotIn("LINEAGE_A", {a.lineage_root for a in assignments})
        self.assertIn("LINEAGE_D", {a.lineage_root for a in assignments})
        self.assertEqual(len({a.lineage_root for a in assignments}), 2)
        self.assertTrue(all(a.authority_weight == 0 for a in assignments))
        self.assertTrue(all(not a.world_authority_granted for a in assignments))
        self.assertIn("COUNTEREXAMPLE_CHALLENGE", {a.role for a in assignments})


class FakeProviderLookup:
    def __init__(self, observation):
        self.provider_id = observation.provider_id
        self.observation = observation

    def lookup(self, binding):
        return self.observation


class ProviderLookupReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.binding = ProviderEffectBinding(
            provider_id="BANK-X",
            effect_key="PAYMENT:200",
            authorization_id="AUTH-200",
            idempotency_key="janus-payment-200",
            retry_policy="RETRY_ONLY_WITH_SAME_PROVIDER_IDEMPOTENCY_KEY",
        )
        self.reconciler = ProviderLookupReconciler()

    def test_authoritative_no_effect_lookup_can_open_retry_policy(self):
        observation = ProviderLookupObservation(
            provider_id="BANK-X",
            effect_key="PAYMENT:200",
            idempotency_key="janus-payment-200",
            outcome=ProviderLookupOutcome.NO_EFFECT,
            evidence_ref="BANK-X-LOOKUP-NO-EFFECT-200",
            authoritative_under_adapter_contract=True,
        )
        decision = self.reconciler.reconcile(
            binding=self.binding,
            adapter=FakeProviderLookup(observation),
        )
        self.assertEqual(decision.state, "NO_EFFECT_BY_PROVIDER_LOOKUP")
        self.assertTrue(decision.safe_automatic_retry)

    def test_settled_lookup_requires_receipt_and_never_opens_retry(self):
        observation = ProviderLookupObservation(
            provider_id="BANK-X",
            effect_key="PAYMENT:200",
            idempotency_key="janus-payment-200",
            outcome=ProviderLookupOutcome.SETTLED,
            evidence_ref="BANK-X-LOOKUP-200",
            receipt_id="BANK-X-RECEIPT-200",
            authoritative_under_adapter_contract=True,
        )
        decision = self.reconciler.reconcile(
            binding=self.binding,
            adapter=FakeProviderLookup(observation),
        )
        self.assertEqual(decision.state, "SETTLED_BY_PROVIDER_LOOKUP")
        self.assertEqual(decision.receipt_id, "BANK-X-RECEIPT-200")
        self.assertFalse(decision.safe_automatic_retry)

    def test_non_authoritative_or_mismatched_lookup_cannot_clear_uncertainty(self):
        weak = ProviderLookupObservation(
            provider_id="BANK-X",
            effect_key="PAYMENT:200",
            idempotency_key="janus-payment-200",
            outcome=ProviderLookupOutcome.NO_EFFECT,
            evidence_ref="UNVERIFIED-SCREENSHOT",
            authoritative_under_adapter_contract=False,
        )
        weak_decision = self.reconciler.reconcile(
            binding=self.binding,
            adapter=FakeProviderLookup(weak),
        )
        self.assertFalse(weak_decision.safe_automatic_retry)
        self.assertTrue(weak_decision.state.startswith("UNDETERMINED"))

        mismatch = ProviderLookupObservation(
            provider_id="BANK-X",
            effect_key="PAYMENT:OTHER",
            idempotency_key="janus-payment-200",
            outcome=ProviderLookupOutcome.NO_EFFECT,
            evidence_ref="BANK-X-MISMATCH",
            authoritative_under_adapter_contract=True,
        )
        with self.assertRaises(ProviderLookupContractError):
            self.reconciler.reconcile(
                binding=self.binding,
                adapter=FakeProviderLookup(mismatch),
            )


class FullCrashBoundaryMatrixTests(unittest.TestCase):
    def _adapter(self, world, root, clock, point=None):
        injector = CrashInjector(point) if point is not None else CrashInjector()
        return RuntimeControlAdapter(
            world,
            journal=DurableHashJournal(root / "runtime-control.jsonl"),
            fences=SQLiteEffectFenceStore(root / "runtime-fences.sqlite3"),
            mode=ControlMode.ENFORCED,
            crash_injector=injector,
            holder_id="matrix-worker",
            now_tick=clock,
            lease_ticks=10,
        )

    def _fresh(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        world = PlayableGenesisV187(root)
        clock = ManualClock(100)
        return td, root, world, clock

    def test_before_fence_crash_leaves_no_effect_and_retry_can_execute(self):
        td, root, world, clock = self._fresh()
        with td:
            adapter = self._adapter(world, root, clock, CrashPoint.BEFORE_FENCE)
            before = world.memory.load_player("mira").tick
            with self.assertRaises(InjectedCrash):
                adapter.execute(actor_id="mira", action="создать сад", request_id="REQ-1")
            self.assertEqual(world.memory.load_player("mira").tick, before)
            self.assertEqual(len(adapter.journal.replay()), 0)
            result = self._adapter(world, root, clock).execute(
                actor_id="mira", action="создать сад", request_id="REQ-1"
            )
            self.assertIsNotNone(result)
            self.assertGreater(world.memory.load_player("mira").tick, before)

    def test_after_fence_before_intent_requires_fence_expiry_but_has_no_world_uncertainty(self):
        td, root, world, clock = self._fresh()
        with td:
            adapter = self._adapter(world, root, clock, CrashPoint.AFTER_FENCE_BEFORE_INTENT)
            before = world.memory.load_player("mira").tick
            with self.assertRaises(InjectedCrash):
                adapter.execute(actor_id="mira", action="создать сад", request_id="REQ-2")
            self.assertEqual(world.memory.load_player("mira").tick, before)
            self.assertEqual(len(adapter.journal.replay()), 0)
            retry = self._adapter(world, root, clock)
            with self.assertRaises(RuntimeFenceUnavailable):
                retry.execute(actor_id="mira", action="создать сад", request_id="REQ-2")
            clock.advance(11)
            retry.execute(actor_id="mira", action="создать сад", request_id="REQ-2")
            self.assertGreater(world.memory.load_player("mira").tick, before)

    def test_after_durable_intent_before_call_can_retry_after_fence_expiry(self):
        td, root, world, clock = self._fresh()
        with td:
            adapter = self._adapter(world, root, clock, CrashPoint.AFTER_DURABLE_INTENT)
            before = world.memory.load_player("mira").tick
            with self.assertRaises(InjectedCrash):
                adapter.execute(actor_id="mira", action="создать сад", request_id="REQ-3")
            self.assertEqual(world.memory.load_player("mira").tick, before)
            self.assertEqual([e.event_type for e in adapter.journal.replay()], ["RUNTIME_EFFECT_INTENT_DURABLE"])
            clock.advance(11)
            self._adapter(world, root, clock).execute(
                actor_id="mira", action="создать сад", request_id="REQ-3"
            )
            self.assertGreater(world.memory.load_player("mira").tick, before)

    def test_after_call_entering_before_world_is_conservatively_undetermined(self):
        td, root, world, clock = self._fresh()
        with td:
            adapter = self._adapter(world, root, clock, CrashPoint.AFTER_CALL_ENTERING_BEFORE_WORLD)
            before = world.memory.load_player("mira").tick
            with self.assertRaises(InjectedCrash):
                adapter.execute(actor_id="mira", action="создать сад", request_id="REQ-4")
            self.assertEqual(world.memory.load_player("mira").tick, before)
            with self.assertRaises(RuntimeOutcomeUndetermined):
                self._adapter(world, root, clock).execute(
                    actor_id="mira", action="создать сад", request_id="REQ-4"
                )
            self.assertEqual(world.memory.load_player("mira").tick, before)

    def test_after_world_before_receipt_is_undetermined_and_never_auto_reexecutes(self):
        td, root, world, clock = self._fresh()
        with td:
            adapter = self._adapter(world, root, clock, CrashPoint.AFTER_WORLD_BEFORE_RECEIPT)
            before = world.memory.load_player("mira").tick
            with self.assertRaises(InjectedCrash):
                adapter.execute(actor_id="mira", action="создать сад", request_id="REQ-5")
            after = world.memory.load_player("mira").tick
            self.assertGreater(after, before)
            with self.assertRaises(RuntimeOutcomeUndetermined):
                self._adapter(world, root, clock).execute(
                    actor_id="mira", action="создать сад", request_id="REQ-5"
                )
            self.assertEqual(world.memory.load_player("mira").tick, after)

    def test_after_receipt_before_release_replays_receipt_without_second_world_call(self):
        td, root, world, clock = self._fresh()
        with td:
            adapter = self._adapter(world, root, clock, CrashPoint.AFTER_RECEIPT_BEFORE_RELEASE)
            before = world.memory.load_player("mira").tick
            with self.assertRaises(InjectedCrash):
                adapter.execute(actor_id="mira", action="создать сад", request_id="REQ-6")
            after = world.memory.load_player("mira").tick
            self.assertGreater(after, before)
            result = self._adapter(world, root, clock).execute(
                actor_id="mira", action="создать сад", request_id="REQ-6"
            )
            self.assertIsNotNone(result)
            self.assertEqual(world.memory.load_player("mira").tick, after)


if __name__ == "__main__":
    unittest.main()
