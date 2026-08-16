#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import copy
import tempfile
import unittest
from pathlib import Path

from tools.janus_demiurge_boot_controller import (
    DEFAULT_CHECKPOINT_POLICY,
    OBJECTIVE_SOURCE,
    SUPERVISOR_RESULT_SCHEMA,
    DemiurgeBootControllerError,
    canonical_sha256,
)
from tools.janus_demiurge_boot_controller_v1_1 import (
    CONTROLLER_SCHEMA_V11,
    JanusDemiurgeBootControllerV11,
)
from tools.janus_demiurge_supervisor_checkpoint_journal import (
    CHECKPOINT_SCHEMA,
    PINNED_SUPERVISOR_HEAD,
    JanusDemiurgeSupervisorCheckpointJournal,
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


class ScriptedSupervisor:
    """Local dependency-injection fixture; never used as implementation proof."""

    def __init__(self, *, terminal_window=4, tamper_authorized=False):
        self.terminal_window = terminal_window
        self.tamper_authorized = tamper_authorized
        self.run_calls = 0
        self.resume_calls = 0

    def _checkpoint(
        self,
        *,
        objective_id,
        config,
        target,
        weights,
        root_seed,
        generation_window,
        candidate_count,
        patience_windows,
        min_window_improvement,
        next_window_index,
        parent,
        state,
    ):
        checkpoint = {
            "schema": CHECKPOINT_SCHEMA,
            "objective_id": objective_id,
            "resume_config": dict(config),
            "resume_score": score(config, target, weights),
            "next_window_index": next_window_index,
            "root_seed": root_seed,
            "target_config": dict(target),
            "weights": dict(weights),
            "generation_window": generation_window,
            "candidate_count": candidate_count,
            "patience_windows": patience_windows,
            "min_window_improvement": min_window_improvement,
            "total_generations": next_window_index * generation_window,
            "total_adoptions": 0,
            "state": state,
            "parent_checkpoint_receipt_sha256": parent,
        }
        checkpoint["receipt_sha256"] = canonical_sha256(checkpoint)
        return checkpoint

    def _result(self, *, checkpoint, initial_config, window_offset, windows_executed):
        result = {
            "schema": SUPERVISOR_RESULT_SCHEMA,
            "state": checkpoint["state"],
            "objective_present": True,
            "objective_id": checkpoint["objective_id"],
            "self_generated_objective": False,
            "initial_config": dict(initial_config),
            "final_config": dict(checkpoint["resume_config"]),
            "initial_score": score(
                initial_config, checkpoint["target_config"], checkpoint["weights"]
            ),
            "final_score": checkpoint["resume_score"],
            "weights": dict(checkpoint["weights"]),
            "generation_window": checkpoint["generation_window"],
            "window_offset": window_offset,
            "windows_executed": windows_executed,
            "segment_generations": windows_executed * checkpoint["generation_window"],
            "segment_adoptions": 0,
            "cumulative_generations": checkpoint["total_generations"],
            "cumulative_adoptions": checkpoint["total_adoptions"],
            "candidate_count": checkpoint["candidate_count"],
            "patience_windows": checkpoint["patience_windows"],
            "min_window_improvement": checkpoint["min_window_improvement"],
            "windows": [],
            "checkpoint": checkpoint,
            "work_performed": True,
            "simulation_only": True,
            "authorized": self.tamper_authorized,
            "external_effect": False,
            "source_writeback": False,
            "automatic_merge": False,
        }
        result["receipt_sha256"] = canonical_sha256(result)
        return result

    def run_objective(
        self,
        *,
        objective_id,
        base_config,
        target_config,
        root_seed,
        generation_window,
        max_windows,
        candidate_count,
        patience_windows,
        min_window_improvement,
        weights,
    ):
        self.run_calls += 1
        next_index = max_windows
        state = (
            "WAIT_PLATEAU"
            if next_index >= self.terminal_window
            else "BUDGET_EXHAUSTED"
        )
        checkpoint = self._checkpoint(
            objective_id=objective_id,
            config=base_config,
            target=target_config,
            weights=weights,
            root_seed=root_seed,
            generation_window=generation_window,
            candidate_count=candidate_count,
            patience_windows=patience_windows,
            min_window_improvement=min_window_improvement,
            next_window_index=next_index,
            parent=None,
            state=state,
        )
        return self._result(
            checkpoint=checkpoint,
            initial_config=base_config,
            window_offset=0,
            windows_executed=max_windows,
        )

    def resume_from_checkpoint(self, checkpoint, *, additional_windows):
        self.resume_calls += 1
        next_index = checkpoint["next_window_index"] + additional_windows
        state = (
            "WAIT_PLATEAU"
            if next_index >= self.terminal_window
            else "BUDGET_EXHAUSTED"
        )
        next_checkpoint = self._checkpoint(
            objective_id=checkpoint["objective_id"],
            config=checkpoint["resume_config"],
            target=checkpoint["target_config"],
            weights=checkpoint["weights"],
            root_seed=checkpoint["root_seed"],
            generation_window=checkpoint["generation_window"],
            candidate_count=checkpoint["candidate_count"],
            patience_windows=checkpoint["patience_windows"],
            min_window_improvement=checkpoint["min_window_improvement"],
            next_window_index=next_index,
            parent=checkpoint["receipt_sha256"],
            state=state,
        )
        return self._result(
            checkpoint=next_checkpoint,
            initial_config=checkpoint["resume_config"],
            window_offset=checkpoint["next_window_index"],
            windows_executed=additional_windows,
        )


class DemiurgeBootControllerV11Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "hippocampus.db"
        await self._open_runtime(ScriptedSupervisor())
        self.base = {"alpha": 0.08, "gamma": 0.86, "epsilon": 0.65}
        self.target = {"alpha": 0.31, "gamma": 0.975, "epsilon": 0.12}
        self.objective_id = "boot-objective-001"

    async def asyncTearDown(self):
        if not getattr(self.journal, "_closed", False):
            await self.journal.close()
        self.tmp.cleanup()

    async def _open_runtime(self, supervisor):
        self.journal = JanusHippocampusBufferedJournal(
            self.db,
            batch_size=100,
            flush_interval_seconds=60,
            synchronous="FULL",
        )
        await self.journal.start()
        self.supervisor = supervisor
        self.checkpoints = JanusDemiurgeSupervisorCheckpointJournal(self.journal)
        self.controller = JanusDemiurgeBootControllerV11(
            journal=self.journal,
            checkpoint_store=self.checkpoints,
            supervisor=supervisor,
            supervisor_source_head=PINNED_SUPERVISOR_HEAD,
        )

    async def _register(self, **overrides):
        data = dict(
            objective_id=self.objective_id,
            base_config=self.base,
            target_config=self.target,
            root_seed=37037,
            generation_window=3,
            segment_windows=2,
            candidate_count=8,
            patience_windows=4,
            min_window_improvement=0.0,
            weights={"alpha": 1.0, "gamma": 1.0, "epsilon": 1.0},
        )
        data.update(overrides)
        return await self.controller.register_objective(**data)

    async def _restart(self, supervisor):
        await self.journal.close()
        await self._open_runtime(supervisor)

    async def test_register_persists_objective_before_any_supervisor_work(self):
        result = await self._register()
        self.assertEqual(result["state"], "PERSISTED")
        self.assertTrue(result["sqlite_transaction_committed"])
        self.assertEqual(self.supervisor.run_calls, 0)
        self.assertEqual(self.supervisor.resume_calls, 0)
        hits = await self.journal.recall(self.objective_id, limit=10)
        self.assertEqual(len([h for h in hits if h["origin"] == "HDD"]), 1)

    async def test_restart_before_first_checkpoint_starts_from_durable_objective(self):
        await self._register()
        restarted_supervisor = ScriptedSupervisor(terminal_window=2)
        await self._restart(restarted_supervisor)
        result = await self.controller.run_registered_objective(
            self.objective_id, max_segments=4
        )
        self.assertEqual(result["state"], "WAIT_PLATEAU")
        self.assertEqual(restarted_supervisor.run_calls, 1)
        self.assertEqual(restarted_supervisor.resume_calls, 0)
        self.assertTrue(result["local_supervisor_execution_performed"])
        self.assertFalse(result["recovered_checkpoint"])

    async def test_controller_runs_multiple_segments_without_manual_continue(self):
        await self._register()
        self.supervisor.terminal_window = 4
        result = await self.controller.run_registered_objective(
            self.objective_id, max_segments=4
        )
        self.assertEqual(result["schema"], CONTROLLER_SCHEMA_V11)
        self.assertEqual(result["state"], "WAIT_PLATEAU")
        self.assertEqual(result["segments_executed"], 2)
        self.assertEqual(self.supervisor.run_calls, 1)
        self.assertEqual(self.supervisor.resume_calls, 1)
        self.assertFalse(result["manual_continue_between_segments_required"])
        self.assertFalse(result["self_generated_objective"])
        self.assertFalse(result["autonomous_external_action"])

    async def test_restart_from_budget_checkpoint_resumes_not_restarts(self):
        await self._register()
        self.supervisor.terminal_window = 4
        first = await self.controller.run_registered_objective(
            self.objective_id, max_segments=1
        )
        self.assertEqual(first["state"], "CONTROLLER_BUDGET_EXHAUSTED")
        self.assertEqual(first["checkpoint"]["state"], "BUDGET_EXHAUSTED")

        restarted_supervisor = ScriptedSupervisor(terminal_window=4)
        await self._restart(restarted_supervisor)
        second = await self.controller.run_registered_objective(
            self.objective_id, max_segments=2
        )
        self.assertEqual(second["state"], "WAIT_PLATEAU")
        self.assertEqual(restarted_supervisor.run_calls, 0)
        self.assertEqual(restarted_supervisor.resume_calls, 1)
        self.assertTrue(second["recovered_checkpoint"])

    async def test_restart_after_wait_does_no_new_work(self):
        await self._register()
        self.supervisor.terminal_window = 2
        terminal = await self.controller.run_registered_objective(
            self.objective_id, max_segments=4
        )
        self.assertEqual(terminal["state"], "WAIT_PLATEAU")

        restarted_supervisor = ScriptedSupervisor(terminal_window=999)
        await self._restart(restarted_supervisor)
        replay = await self.controller.run_registered_objective(
            self.objective_id, max_segments=4
        )
        self.assertEqual(replay["state"], "WAIT_PLATEAU")
        self.assertEqual(replay["segments_executed"], 0)
        self.assertFalse(replay["local_supervisor_execution_performed"])
        self.assertEqual(restarted_supervisor.run_calls, 0)
        self.assertEqual(restarted_supervisor.resume_calls, 0)

    async def test_missing_objective_waits_without_supervisor_execution(self):
        result = await self.controller.run_registered_objective(
            "missing-objective", max_segments=4
        )
        self.assertEqual(result["state"], "WAIT_NO_DURABLE_OBJECTIVE")
        self.assertEqual(result["segments_executed"], 0)
        self.assertFalse(result["local_supervisor_execution_performed"])
        self.assertEqual(self.supervisor.run_calls, 0)
        self.assertEqual(self.supervisor.resume_calls, 0)

    async def test_concurrent_conflicting_registration_is_serialized_hold(self):
        async def register(target_alpha):
            target = dict(self.target)
            target["alpha"] = target_alpha
            return await self._register(target_config=target)

        results = await asyncio.gather(
            register(0.30), register(0.32), return_exceptions=True
        )
        errors = [x for x in results if isinstance(x, Exception)]
        successes = [x for x in results if isinstance(x, dict)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], DemiurgeBootControllerError)
        self.assertIn("HOLD_RECONCILE", str(errors[0]))
        hits = await self.journal.recall(self.objective_id, limit=10)
        durable = [h for h in hits if h["origin"] == "HDD" and h["source"] == OBJECTIVE_SOURCE]
        self.assertEqual(len(durable), 1)

    async def test_concurrent_identical_registration_is_idempotent(self):
        results = await asyncio.gather(self._register(), self._register())
        self.assertEqual(
            {row["state"] for row in results},
            {"PERSISTED", "IDEMPOTENT_PERSISTED_REPLAY"},
        )
        hits = await self.journal.recall(self.objective_id, limit=10)
        durable = [h for h in hits if h["origin"] == "HDD" and h["source"] == OBJECTIVE_SOURCE]
        self.assertEqual(len(durable), 1)

    async def test_tampered_supervisor_authorization_fails_before_checkpoint_write(self):
        await self._register()
        bad = ScriptedSupervisor(terminal_window=2, tamper_authorized=True)
        self.controller.supervisor = bad
        with self.assertRaisesRegex(DemiurgeBootControllerError, "authorized"):
            await self.controller.run_registered_objective(
                self.objective_id, max_segments=1
            )
        recovered = await self.checkpoints.recover_latest(
            objective_id=self.objective_id,
            source_head=PINNED_SUPERVISOR_HEAD,
            policy_id=DEFAULT_CHECKPOINT_POLICY,
        )
        self.assertEqual(recovered["state"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
