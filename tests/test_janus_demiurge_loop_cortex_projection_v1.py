#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import copy
import tempfile
import unittest
from pathlib import Path

from tools.janus_demiurge_loop_cortex_projection import (
    LOOP_SCHEMA,
    PINNED_DEMIURGE_LOOP_HEAD,
    DemiurgeLoopProjectionError,
    JanusDemiurgeLoopCortexProjection,
    canonical_sha256,
    validate_loop_receipt,
)
from tools.janus_storj_neighbor_cortex_memory import JanusCortexMemory


def _generation(
    index,
    *,
    before,
    selected,
    after,
    adopted,
    config,
):
    row = {
        "generation": index,
        "generation_seed": 1000 + index,
        "incumbent_score_before": before,
        "selected_proposal_id": f"{index + 1:024x}",
        "selected_score": selected,
        "adopted": adopted,
        "incumbent_score_after": after,
        "incumbent_config_after": dict(config),
        "proposal_receipt_sha256": f"{index + 11:064x}",
        "ranking_receipt_sha256": f"{index + 21:064x}",
    }
    row["receipt_sha256"] = canonical_sha256(row)
    return row


def valid_loop_result():
    initial = {"alpha": 0.08, "gamma": 0.86, "epsilon": 0.65}
    middle = {"alpha": 0.12, "gamma": 0.90, "epsilon": 0.50}
    final = {"alpha": 0.18, "gamma": 0.94, "epsilon": 0.30}
    target = {"alpha": 0.31, "gamma": 0.975, "epsilon": 0.12}
    lineage = [
        _generation(
            0,
            before=-0.8,
            selected=-0.5,
            after=-0.5,
            adopted=True,
            config=middle,
        ),
        _generation(
            1,
            before=-0.5,
            selected=-0.2,
            after=-0.2,
            adopted=True,
            config=final,
        ),
        _generation(
            2,
            before=-0.2,
            selected=-0.25,
            after=-0.2,
            adopted=False,
            config=final,
        ),
    ]
    result = {
        "schema": LOOP_SCHEMA,
        "mode": "LOCAL_COUNTERFACTUAL_EVOLUTION",
        "initial_config": initial,
        "target_config": target,
        "weights": {"alpha": 1.0, "gamma": 1.0, "epsilon": 1.0},
        "initial_score": -0.8,
        "final_config": final,
        "final_score": -0.2,
        "generations": 3,
        "candidate_count": 8,
        "adopted_generations": 2,
        "lineage": lineage,
        "simulation_only": True,
        "future_prediction_claimed": False,
        "scientific_validation_claimed": False,
        "source_writeback": False,
        "external_effect": False,
        "authorized": False,
        "automatic_merge": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


class DemiurgeLoopReceiptValidationTests(unittest.TestCase):
    def test_valid_loop_receipt_replays(self):
        result = valid_loop_result()
        validated = validate_loop_receipt(result)
        self.assertEqual(validated["loop_receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(validated["final_score"], -0.2)
        self.assertEqual(validated["adopted_generations"], 2)

    def test_generation_body_tamper_rejected_even_when_outer_receipt_rehashed(self):
        result = valid_loop_result()
        result["lineage"][1]["incumbent_score_after"] = -0.1
        unsigned = dict(result)
        unsigned.pop("receipt_sha256")
        result["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeLoopProjectionError):
            validate_loop_receipt(result)

    def test_rehashed_authorization_attempt_rejected(self):
        result = valid_loop_result()
        result["authorized"] = True
        unsigned = dict(result)
        unsigned.pop("receipt_sha256")
        result["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeLoopProjectionError):
            validate_loop_receipt(result)

    def test_adopted_generation_must_strictly_improve(self):
        result = valid_loop_result()
        row = result["lineage"][2]
        row["adopted"] = True
        row["selected_score"] = -0.25
        row["incumbent_score_after"] = -0.25
        unsigned_row = dict(row)
        unsigned_row.pop("receipt_sha256")
        row["receipt_sha256"] = canonical_sha256(unsigned_row)
        result["final_score"] = -0.25
        result["final_config"] = dict(row["incumbent_config_after"])
        result["adopted_generations"] = 3
        unsigned = dict(result)
        unsigned.pop("receipt_sha256")
        result["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeLoopProjectionError):
            validate_loop_receipt(result)

    def test_final_config_must_equal_lineage_head(self):
        result = valid_loop_result()
        result["final_config"]["alpha"] = 0.19
        unsigned = dict(result)
        unsigned.pop("receipt_sha256")
        result["receipt_sha256"] = canonical_sha256(unsigned)
        with self.assertRaises(DemiurgeLoopProjectionError):
            validate_loop_receipt(result)


class DemiurgeLoopCortexProjectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "cortex.db"
        self.cortex = JanusCortexMemory(
            self.db_path,
            batch_size=100,
            flush_timeout=30.0,
            enable_fts=False,
        )
        self.adapter = JanusDemiurgeLoopCortexProjection(self.cortex)

    async def asyncTearDown(self):
        await self.cortex.close()
        self.tmp.cleanup()

    async def test_projection_is_explicit_and_buffered_by_default(self):
        result = await self.adapter.project(
            valid_loop_result(),
            source_head=PINNED_DEMIURGE_LOOP_HEAD,
            policy_id="DEMIURGE_LOOP_EPISODE_V1",
            reason="retain selected counterfactual evolution episode for later recall",
        )
        self.assertEqual(result["state"], "BUFFERED")
        self.assertFalse(result["persisted"])
        self.assertFalse(result["authorized"])
        self.assertFalse(result["execute"])
        self.assertFalse(result["external_effect"])
        self.assertTrue(result["same_evidence_root_as_source"])
        self.assertFalse(result["independent_corroboration_claimed"])
        self.assertEqual(self.cortex.buffered_rows, 1)

    async def test_same_adapter_replay_is_idempotent(self):
        kwargs = dict(
            source_head=PINNED_DEMIURGE_LOOP_HEAD,
            policy_id="DEMIURGE_LOOP_EPISODE_V1",
            reason="retain loop episode",
        )
        first = await self.adapter.project(valid_loop_result(), **kwargs)
        second = await self.adapter.project(valid_loop_result(), **kwargs)
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(second["state"], "IDEMPOTENT_REPLAY")
        self.assertEqual(self.cortex.buffered_rows, 1)

    async def test_persist_then_new_adapter_recovers_idempotency_from_cortex(self):
        kwargs = dict(
            source_head=PINNED_DEMIURGE_LOOP_HEAD,
            policy_id="DEMIURGE_LOOP_EPISODE_V1",
            reason="persist loop episode",
            persist=True,
        )
        first = await self.adapter.project(valid_loop_result(), **kwargs)
        self.assertEqual(first["state"], "PERSISTED")
        self.assertTrue(first["persisted"])
        second_adapter = JanusDemiurgeLoopCortexProjection(self.cortex)
        second = await second_adapter.project(valid_loop_result(), **kwargs)
        self.assertEqual(second["state"], "IDEMPOTENT_REPLAY")
        hits = await self.cortex.recall_hits(first["idempotency_key"], limit=10)
        exact = [hit for hit in hits if hit.tag.startswith("DEMIURGE_LOOP:")]
        self.assertEqual(len(exact), 1)

    async def test_wrong_source_head_fails_before_memory_write(self):
        with self.assertRaises(DemiurgeLoopProjectionError):
            await self.adapter.project(
                valid_loop_result(),
                source_head="0" * 40,
                policy_id="DEMIURGE_LOOP_EPISODE_V1",
                reason="wrong pin",
            )
        self.assertEqual(self.cortex.buffered_rows, 0)

    async def test_policy_change_changes_idempotency_key(self):
        first = self.adapter.build_plan(
            valid_loop_result(),
            source_head=PINNED_DEMIURGE_LOOP_HEAD,
            policy_id="POLICY_A",
            reason="same reason",
        )
        second = self.adapter.build_plan(
            valid_loop_result(),
            source_head=PINNED_DEMIURGE_LOOP_HEAD,
            policy_id="POLICY_B",
            reason="same reason",
        )
        self.assertNotEqual(first.idempotency_key, second.idempotency_key)

    async def test_projection_content_does_not_claim_independent_evidence(self):
        plan = self.adapter.build_plan(
            valid_loop_result(),
            source_head=PINNED_DEMIURGE_LOOP_HEAD,
            policy_id="DEMIURGE_LOOP_EPISODE_V1",
            reason="evidence lineage regression",
        )
        self.assertIn('"same_evidence_root_as_source":true', plan.content)
        self.assertIn('"independent_corroboration_claimed":false', plan.content)
        self.assertIn('"future_prediction_claimed":false', plan.content)


if __name__ == "__main__":
    unittest.main()
