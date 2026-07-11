from __future__ import annotations

import os
import time
from dataclasses import asdict
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import pytest

from janus_genesis.bidirectional_fitness import (
    MutationEvidence,
    MutationExperimentRecord,
    MutationMemory,
    MutationQuery,
    evaluate_candidate,
    multiscale_agreement,
)


def passing_gates() -> dict[str, bool]:
    return {
        "geometry_contract": True,
        "physical_residual": True,
        "equilibrium": True,
        "protected_geometry": True,
        "fdm_minimum_feature": True,
    }


def test_hard_gate_always_rejects_candidate() -> None:
    gates = passing_gates()
    gates["geometry_contract"] = False
    result = evaluate_candidate(
        MutationEvidence(
            forward_score=0.95,
            reverse_score=0.95,
            retrieval_score=0.90,
            printability_score=0.90,
            multiscale_scores={"1": 0.9, "3": 0.9, "5": 0.9, "7": 0.9},
            hard_gates=gates,
        )
    )
    assert result["verdict"] == "HARD_GATE_REJECTED"
    assert result["fitness"] == 0.0
    assert "geometry_contract" in result["failed_hard_gates"]


def test_bidirectional_candidate_is_confirmed_after_gates() -> None:
    result = evaluate_candidate(
        MutationEvidence(
            forward_score=0.82,
            reverse_score=0.79,
            retrieval_score=0.75,
            printability_score=0.88,
            uncertainty=0.05,
            irreversibility=0.02,
            phase_sensitivity=0.06,
            multiscale_scores={"1": 0.83, "3": 0.80, "5": 0.78, "7": 0.76},
            hard_gates=passing_gates(),
        )
    )
    assert result["eligible_for_ranking"] is True
    assert result["verdict"] == "BIDIRECTIONAL_CONFIRMED"
    assert result["geometry_mutation_executed"] is False


def test_directional_disagreement_is_visible() -> None:
    result = evaluate_candidate(
        MutationEvidence(
            forward_score=0.90,
            reverse_score=0.30,
            retrieval_score=0.70,
            printability_score=0.80,
            multiscale_scores={"1": 0.9, "3": 0.8, "5": 0.7, "7": 0.6},
            hard_gates=passing_gates(),
        )
    )
    assert result["verdict"] == "FORWARD_ONLY_UNCERTAIN"
    assert result["directional_disagreement"] == pytest.approx(0.6)


def test_multiscale_missing_levels_reduce_coverage() -> None:
    result = multiscale_agreement({"1": 0.9, "3": 0.9})
    assert result["coverage"] == 0.5
    assert result["agreement"] < 0.5


def make_record(operator: str, baseline: str, tokens: list[str]) -> MutationExperimentRecord:
    evidence = MutationEvidence(
        forward_score=0.75,
        reverse_score=0.78,
        retrieval_score=0.70,
        printability_score=0.80,
        multiscale_scores={"1": 0.8, "3": 0.8, "5": 0.75, "7": 0.7},
        hard_gates=passing_gates(),
    )
    return MutationExperimentRecord(
        baseline_fingerprint=baseline,
        contract_fingerprint="contract-a",
        load_fingerprint="load-a",
        mutation_operator=operator,
        region_descriptor="hook-adjacent mutable shell",
        descriptor_tokens=tokens,
        evidence={"input": asdict(evidence)},
        evaluation=evaluate_candidate(evidence),
        outcome="VALID",
    )


def _concurrent_append_worker(
    path_text: str,
    worker_id: int,
    records_per_worker: int,
    start_event: Any,
) -> None:
    if not start_event.wait(timeout=10.0):
        raise RuntimeError("concurrent append test did not receive the start signal")
    memory = MutationMemory(Path(path_text), lock_timeout_seconds=20.0)
    for record_index in range(records_per_worker):
        baseline = f"worker-{worker_id}-record-{record_index}"
        memory.append(make_record("stress_aligned_rib", baseline, ["hook", "shell"]))


def test_jsonl_memory_serializes_concurrent_process_appends(tmp_path: Path) -> None:
    path = tmp_path / "memory" / "mutation_experiments.jsonl"
    context = get_context("spawn")
    start_event = context.Event()
    worker_count = 4
    records_per_worker = 6
    workers = [
        context.Process(
            target=_concurrent_append_worker,
            args=(str(path), worker_id, records_per_worker, start_event),
        )
        for worker_id in range(worker_count)
    ]

    for worker in workers:
        worker.start()
    start_event.set()
    for worker in workers:
        worker.join(timeout=30.0)
        assert worker.is_alive() is False
        assert worker.exitcode == 0

    memory = MutationMemory(path)
    records = list(memory.iter_records())
    expected = {
        f"worker-{worker_id}-record-{record_index}"
        for worker_id in range(worker_count)
        for record_index in range(records_per_worker)
    }
    assert len(records) == worker_count * records_per_worker
    assert {record.baseline_fingerprint for record in records} == expected
    assert memory.lock_path.exists() is False
    assert list(path.parent.glob(f".{path.name}.*.tmp")) == []


def test_jsonl_memory_recovers_abandoned_stale_lock(tmp_path: Path) -> None:
    path = tmp_path / "memory" / "mutation_experiments.jsonl"
    memory = MutationMemory(
        path,
        lock_timeout_seconds=1.0,
        stale_lock_seconds=0.05,
        lock_poll_seconds=0.005,
    )
    memory.lock_path.parent.mkdir(parents=True, exist_ok=True)
    memory.lock_path.write_text('{"pid": -1, "token": "abandoned"}', encoding="utf-8")
    old_timestamp = time.time() - 1.0
    os.utime(memory.lock_path, (old_timestamp, old_timestamp))

    memory.append(make_record("stress_aligned_rib", "baseline-stale", ["hook"]))

    records = list(memory.iter_records())
    assert len(records) == 1
    assert records[0].baseline_fingerprint == "baseline-stale"
    assert memory.lock_path.exists() is False


def test_jsonl_memory_roundtrip_and_retrieval(tmp_path: Path) -> None:
    memory = MutationMemory(tmp_path / "memory" / "mutation_experiments.jsonl")
    memory.append(make_record("stress_aligned_rib", "baseline-a", ["hook", "shell"]))
    memory.append(make_record("local_thinning", "baseline-b", ["window", "shell"]))

    results = memory.retrieve(
        MutationQuery(
            baseline_fingerprint="baseline-a",
            contract_fingerprint="contract-a",
            load_fingerprint="load-a",
            mutation_operator="stress_aligned_rib",
            descriptor_tokens=["hook", "shell"],
        )
    )
    assert len(results) == 2
    assert results[0]["record"]["mutation_operator"] == "stress_aligned_rib"
    assert results[0]["similarity"] == 1.0
