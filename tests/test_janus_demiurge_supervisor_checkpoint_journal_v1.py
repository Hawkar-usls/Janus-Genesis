#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ast
import copy
import tempfile
import unittest
from pathlib import Path

from tools.janus_demiurge_supervisor_checkpoint_journal import (
    CHECKPOINT_SCHEMA,
    PINNED_SUPERVISOR_HEAD,
    JanusDemiurgeSupervisorCheckpointJournal,
    SupervisorCheckpointJournalError,
    canonical_sha256,
)
from tools.janus_hippocampus_hdd_buffer import JanusHippocampusBufferedJournal


BOUNDS = {
    "alpha": (0.01, 0.5),
    "gamma": (0.8, 0.999),
    "epsilon": (0.01, 0.9),
}


def score(config, target, weights):
    total = 0.0
    norm = 0.0
    for key, (low, high) in BOUNDS.items():
        delta = (config[key] - target[key]) / (high - low)
        total += weights[key] * delta * delta
        norm += weights[key]
    return -float(total / norm)


def make_checkpoint(
    *,
    objective_id="objective-checkpoint",
    resume_config=None,
    target_config=None,
    weights=None,
    next_window_index=2,
    generation_window=3,
    total_adoptions=2,
    state="BUDGET_EXHAUSTED",
    parent=None,
):
    target = target_config or {"alpha": 0.31, "gamma": 0.975, "epsilon": 0.12}
    config = resume_config or {"alpha": 0.18, "gamma": 0.94, "epsilon": 0.30}
    weights = weights or {"alpha": 1.0, "gamma": 1.0, "epsilon": 1.0}
    if state == "WAIT_FIXED_POINT":
        config = dict(target)
    checkpoint = {
        "schema": CHECKPOINT_SCHEMA,
        "objective_id": objective_id,
        "resume_config": dict(config),
        "resume_score": score(config, target, weights),
        "next_window_index": next_window_index,
        "root_seed": 37037,
        "target_config": dict(target),
        "weights": dict(weights),
        "generation_window": generation_window,
        "candidate_count": 8,
        "patience_windows": 4,
        "min_window_improvement": 0.0,
        "total_generations": next_window_index * generation_window,
        "total_adoptions": total_adoptions,
        "state": state,
        "parent_checkpoint_receipt_sha256": parent,
    }
    checkpoint["receipt_sha256"] = canonical_sha256(checkpoint)
    return checkpoint


class DemiurgeSupervisorCheckpointJournalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "hippocampus.db"
        self.journal = JanusHippocampusBufferedJournal(
            self.db,
            batch_size=100,
            flush_interval_seconds=60,
            synchronous="FULL",
        )
        await self.journal.start()
        self.store = JanusDemiurgeSupervisorCheckpointJournal(self.journal)

    async def asyncTearDown(self):
        if not getattr(self.journal, "_closed", False):
            await self.journal.close()
        self.tmp.cleanup()

    async def test_persist_crosses_force_save_and_hdd_verification(self):
        checkpoint = make_checkpoint()
        result = await self.store.persist_checkpoint(
            checkpoint,
            source_head=PINNED_SUPERVISOR_HEAD,
        )
        self.assertEqual(result["state"], "PERSISTED")
        self.assertTrue(result["sqlite_transaction_committed"])
        self.assertEqual(result["journal_synchronous"], "FULL")
        self.assertTrue(result["process_restart_recovery_after_commit"])
        self.assertFalse(result["backup_claimed"])
        self.assertFalse(result["replication_claimed"])
        self.assertFalse(result["power_loss_proof_claimed"])
        stats = await self.journal.stats()
        self.assertEqual(stats["buffered_records"], 0)

    async def test_idempotent_replay_does_not_duplicate_checkpoint(self):
        checkpoint = make_checkpoint()
        first = await self.store.persist_checkpoint(
            checkpoint, source_head=PINNED_SUPERVISOR_HEAD
        )
        second = await self.store.persist_checkpoint(
            checkpoint, source_head=PINNED_SUPERVISOR_HEAD
        )
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(second["state"], "IDEMPOTENT_PERSISTED_REPLAY")
        hits = await self.journal.recall(first["idempotency_key"], limit=10)
        exact = [row for row in hits if row["origin"] == "HDD"]
        self.assertEqual(len(exact), 1)

    async def test_process_restart_recovers_exact_checkpoint(self):
        checkpoint = make_checkpoint()
        await self.store.persist_checkpoint(
            checkpoint, source_head=PINNED_SUPERVISOR_HEAD
        )
        await self.journal.close()

        self.journal = JanusHippocampusBufferedJournal(
            self.db,
            batch_size=100,
            flush_interval_seconds=60,
            synchronous="FULL",
        )
        await self.journal.start()
        restarted = JanusDemiurgeSupervisorCheckpointJournal(self.journal)
        recovered = await restarted.recover_latest(
            objective_id=checkpoint["objective_id"],
            source_head=PINNED_SUPERVISOR_HEAD,
        )
        self.assertEqual(recovered["state"], "RECOVERED")
        self.assertEqual(recovered["checkpoint"], checkpoint)
        self.assertTrue(recovered["ancestry_complete_within_bounded_recall"])
        self.assertFalse(recovered["authorized"])
        self.assertFalse(recovered["execute"])

    async def test_checkpoint_chain_recovers_latest_and_complete_ancestry(self):
        first = make_checkpoint(next_window_index=2, generation_window=3)
        second = make_checkpoint(
            resume_config={"alpha": 0.21, "gamma": 0.95, "epsilon": 0.25},
            next_window_index=4,
            generation_window=3,
            total_adoptions=5,
            parent=first["receipt_sha256"],
        )
        await self.store.persist_checkpoint(first, source_head=PINNED_SUPERVISOR_HEAD)
        await self.store.persist_checkpoint(second, source_head=PINNED_SUPERVISOR_HEAD)
        recovered = await self.store.recover_latest(
            objective_id=first["objective_id"],
            source_head=PINNED_SUPERVISOR_HEAD,
        )
        self.assertEqual(recovered["checkpoint"], second)
        self.assertTrue(recovered["ancestry_complete_within_bounded_recall"])

    async def test_conflicting_same_window_index_fails_hold_reconcile(self):
        first = make_checkpoint(next_window_index=2, generation_window=3)
        conflict = make_checkpoint(
            resume_config={"alpha": 0.22, "gamma": 0.95, "epsilon": 0.24},
            next_window_index=2,
            generation_window=3,
            total_adoptions=3,
        )
        await self.store.persist_checkpoint(first, source_head=PINNED_SUPERVISOR_HEAD)
        await self.store.persist_checkpoint(conflict, source_head=PINNED_SUPERVISOR_HEAD)
        with self.assertRaisesRegex(SupervisorCheckpointJournalError, "HOLD_RECONCILE"):
            await self.store.recover_latest(
                objective_id=first["objective_id"],
                source_head=PINNED_SUPERVISOR_HEAD,
            )

    async def test_wrong_source_head_fails_before_write(self):
        with self.assertRaises(SupervisorCheckpointJournalError):
            await self.store.persist_checkpoint(
                make_checkpoint(), source_head="0" * 40
            )
        stats = await self.journal.stats()
        self.assertEqual(stats["buffered_records"], 0)

    async def test_tampered_checkpoint_fails_before_write(self):
        checkpoint = make_checkpoint()
        checkpoint["resume_config"]["alpha"] = 0.49
        with self.assertRaises(SupervisorCheckpointJournalError):
            await self.store.persist_checkpoint(
                checkpoint, source_head=PINNED_SUPERVISOR_HEAD
            )
        stats = await self.journal.stats()
        self.assertEqual(stats["buffered_records"], 0)

    async def test_rehashed_but_inconsistent_generation_count_rejected(self):
        checkpoint = make_checkpoint()
        checkpoint["total_generations"] += 1
        unsigned = dict(checkpoint)
        unsigned.pop("receipt_sha256")
        checkpoint["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaisesRegex(SupervisorCheckpointJournalError, "total_generations"):
            await self.store.persist_checkpoint(
                checkpoint, source_head=PINNED_SUPERVISOR_HEAD
            )

    async def test_fixed_point_checkpoint_requires_zero_score(self):
        checkpoint = make_checkpoint(state="WAIT_FIXED_POINT", next_window_index=1)
        # Correct fixed-point fixture is admitted.
        admitted = await self.store.persist_checkpoint(
            checkpoint, source_head=PINNED_SUPERVISOR_HEAD
        )
        self.assertEqual(admitted["state"], "PERSISTED")

        forged = copy.deepcopy(checkpoint)
        forged["resume_config"]["alpha"] = 0.30
        forged["resume_score"] = score(
            forged["resume_config"], forged["target_config"], forged["weights"]
        )
        unsigned = dict(forged)
        unsigned.pop("receipt_sha256")
        forged["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaisesRegex(SupervisorCheckpointJournalError, "WAIT_FIXED_POINT"):
            await self.store.persist_checkpoint(
                forged, source_head=PINNED_SUPERVISOR_HEAD
            )

    async def test_not_found_is_authority_neutral(self):
        result = await self.store.recover_latest(
            objective_id="objective-missing",
            source_head=PINNED_SUPERVISOR_HEAD,
        )
        self.assertEqual(result["state"], "NOT_FOUND")
        self.assertIsNone(result["checkpoint"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["execute"])

    def test_adapter_has_no_network_process_or_cortex_import(self):
        path = Path(__file__).resolve().parents[1] / "tools" / "janus_demiurge_supervisor_checkpoint_journal.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_roots = {
            "aiohttp", "httpx", "requests", "socket", "subprocess", "urllib",
            "shutil", "ftplib", "paramiko"
        }
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint(forbidden_roots), imports)
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("janus_storj_neighbor_cortex_memory", source)


if __name__ == "__main__":
    unittest.main()
