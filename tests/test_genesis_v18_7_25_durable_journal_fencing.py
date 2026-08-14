import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_25_durable_journal_fencing import (
    ControlJournalProjection,
    DeadlineBoundedFairQueue,
    DurableHashJournal,
    FenceBusyError,
    JournalIntegrityError,
    JournaledFencedDispatchCoordinator,
    ProviderIdempotencyBinder,
    ProviderIdempotencyContract,
    SQLiteEffectFenceStore,
    StaleFenceTokenError,
)


class DurableHashJournalTests(unittest.TestCase):
    def test_hash_chain_replays_after_new_instance_and_projects_recovery_state(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "janus-control.jsonl"
            journal = DurableHashJournal(path)
            first = journal.append(
                "EFFECT_AUTHORIZATION_CANCELED",
                {
                    "effect_key": "PAYMENT:99",
                    "authorization_id": "AUTH-OLD",
                    "cancellation_id": "CANCEL-99",
                    "state": "RECONCILIATION_REQUIRED",
                },
            )
            second = journal.append(
                "EFFECT_RECONCILED_NO_EFFECT",
                {
                    "effect_key": "PAYMENT:99",
                    "evidence_ref": "PROVIDER-NO-EFFECT-99",
                },
            )
            third = journal.append(
                "EFFECT_RECOVERY_AUTHORIZED",
                {
                    "effect_key": "PAYMENT:99",
                    "prior_authorization_id": "AUTH-OLD",
                    "replacement_authorization_id": "AUTH-NEW",
                },
            )
            self.assertEqual(first.prev_hash, DurableHashJournal.GENESIS_HASH)
            self.assertEqual(second.prev_hash, first.event_hash)
            self.assertEqual(third.prev_hash, second.event_hash)

            after_crash = DurableHashJournal(path)
            replayed = after_crash.replay()
            self.assertEqual(len(replayed), 3)
            self.assertEqual(after_crash.head_hash(), third.event_hash)
            projection = ControlJournalProjection.from_entries(replayed)
            self.assertEqual(projection.effects["PAYMENT:99"]["state"], "RECOVERY_AUTHORIZED")
            self.assertEqual(
                projection.effects["PAYMENT:99"]["replacement_authorization_id"],
                "AUTH-NEW",
            )
            self.assertEqual(projection.last_sequence, 3)

    def test_tamper_is_detected_on_replay(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "janus-control.jsonl"
            journal = DurableHashJournal(path)
            journal.append(
                "SAGA_STATE",
                {"saga_id": "SAGA-X", "state": "IN_PROGRESS"},
            )
            raw = path.read_text(encoding="utf-8")
            path.write_text(raw.replace("IN_PROGRESS", "SETTLED"), encoding="utf-8")
            with self.assertRaises(JournalIntegrityError):
                DurableHashJournal(path).replay()


class SQLiteFenceTests(unittest.TestCase):
    def test_expired_holder_cannot_use_old_generation_after_takeover(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "fences.sqlite3"
            store_a = SQLiteEffectFenceStore(db)
            store_b = SQLiteEffectFenceStore(db)
            token_a = store_a.acquire(
                effect_key="PAYMENT:1",
                holder_id="PROCESS-A",
                now_tick=10,
                lease_ticks=5,
            )
            with self.assertRaises(FenceBusyError):
                store_b.acquire(
                    effect_key="PAYMENT:1",
                    holder_id="PROCESS-B",
                    now_tick=12,
                    lease_ticks=5,
                )

            token_b = store_b.acquire(
                effect_key="PAYMENT:1",
                holder_id="PROCESS-B",
                now_tick=15,
                lease_ticks=5,
            )
            self.assertGreater(token_b.generation, token_a.generation)
            with self.assertRaises(StaleFenceTokenError):
                store_a.validate(token_a, now_tick=15)
            self.assertTrue(store_b.validate(token_b, now_tick=16))


class ProviderIdempotencyTests(unittest.TestCase):
    def test_recovery_authorization_keeps_same_provider_key_for_same_effect(self):
        binder = ProviderIdempotencyBinder()
        contract = ProviderIdempotencyContract(
            provider_id="BANK-X",
            supports_idempotency=True,
            supports_receipt_lookup=True,
        )
        original = binder.bind(
            contract,
            effect_key="PAYMENT:77",
            authorization_id="AUTH-OLD",
        )
        recovery = binder.bind(
            contract,
            effect_key="PAYMENT:77",
            authorization_id="AUTH-NEW",
        )
        self.assertNotEqual(original.authorization_id, recovery.authorization_id)
        self.assertTrue(binder.same_effect_same_key(original, recovery))
        self.assertEqual(
            recovery.retry_policy,
            "RETRY_ONLY_WITH_SAME_PROVIDER_IDEMPOTENCY_KEY",
        )

    def test_non_idempotent_provider_does_not_get_silent_retry_policy(self):
        binder = ProviderIdempotencyBinder()
        lookup_contract = ProviderIdempotencyContract(
            provider_id="MAIL-X",
            supports_idempotency=False,
            supports_receipt_lookup=True,
        )
        lookup = binder.bind(
            lookup_contract,
            effect_key="EMAIL:7",
            authorization_id="AUTH-E7",
        )
        self.assertIsNone(lookup.idempotency_key)
        self.assertEqual(
            lookup.retry_policy,
            "LOOKUP_AUTHORITATIVE_PROVIDER_RECEIPT_BEFORE_RETRY",
        )

        blind_contract = ProviderIdempotencyContract(
            provider_id="LEGACY-X",
            supports_idempotency=False,
            supports_receipt_lookup=False,
        )
        blind = binder.bind(
            blind_contract,
            effect_key="LEGACY:7",
            authorization_id="AUTH-L7",
        )
        self.assertEqual(
            blind.retry_policy,
            "BLOCK_RETRY_UNTIL_EXTERNAL_RECONCILIATION",
        )


class JournaledFencedDispatchTests(unittest.TestCase):
    def test_intent_is_durable_and_fenced_before_external_effect_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            journal_path = Path(td) / "control.jsonl"
            fence_path = Path(td) / "fences.sqlite3"
            journal = DurableHashJournal(journal_path)
            fences = SQLiteEffectFenceStore(fence_path)
            coordinator = JournaledFencedDispatchCoordinator(journal=journal, fences=fences)
            contract = ProviderIdempotencyContract(
                provider_id="BANK-X",
                supports_idempotency=True,
                supports_receipt_lookup=True,
            )

            intent = coordinator.prepare(
                effect_key="PAYMENT:88",
                authorization_id="AUTH-88",
                holder_id="WORKER-A",
                contract=contract,
                now_tick=100,
                lease_ticks=10,
            )
            self.assertTrue(coordinator.validate_before_effect(intent, now_tick=101))
            replayed = DurableHashJournal(journal_path).replay()
            self.assertEqual(replayed[0].event_type, "DISPATCH_INTENT_DURABLE")
            self.assertEqual(replayed[0].event_hash, intent.journal_event_hash)
            self.assertEqual(replayed[1].event_type, "PROVIDER_BINDING")

            competitor = SQLiteEffectFenceStore(fence_path)
            with self.assertRaises(FenceBusyError):
                competitor.acquire(
                    effect_key="PAYMENT:88",
                    holder_id="WORKER-B",
                    now_tick=102,
                    lease_ticks=10,
                )

            coordinator.record_receipt(
                intent,
                receipt_id="BANK-RECEIPT-88",
                provider_status="SETTLED",
                now_tick=103,
            )
            projection = ControlJournalProjection.from_entries(DurableHashJournal(journal_path).replay())
            self.assertEqual(projection.effects["PAYMENT:88"]["state"], "SETTLED")
            token_b = competitor.acquire(
                effect_key="PAYMENT:88",
                holder_id="WORKER-B",
                now_tick=104,
                lease_ticks=10,
            )
            self.assertEqual(token_b.generation, intent.fence.generation + 1)


class DeadlineBoundedFairnessTests(unittest.TestCase):
    def test_overdue_stream_cannot_starve_mandatory_old_ticket_forever(self):
        queue = DeadlineBoundedFairQueue(max_bypass=1, max_deadline_burst=1)
        low = queue.enqueue(
            ticket_id="LOW",
            effect_key="EFFECT:LOW",
            face_id="FACE_LOW",
            routing_priority=0.1,
            risk_level="LOW",
            deadline_tick=None,
        )
        queue.enqueue(
            ticket_id="OVERDUE-1",
            effect_key="EFFECT:H1",
            face_id="FACE_HIGH",
            routing_priority=10.0,
            risk_level="CRITICAL",
            deadline_tick=5,
        )
        first = queue.next_ticket(now_tick=10)
        self.assertEqual(first.ticket_id, "OVERDUE-1")

        queue.enqueue(
            ticket_id="OVERDUE-2",
            effect_key="EFFECT:H2",
            face_id="FACE_HIGH",
            routing_priority=10.0,
            risk_level="CRITICAL",
            deadline_tick=6,
        )
        second = queue.next_ticket(now_tick=10)
        self.assertEqual(second.ticket_id, low.ticket_id)
        self.assertEqual(second.authority_weight, 0)


if __name__ == "__main__":
    unittest.main()
