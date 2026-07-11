from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

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
