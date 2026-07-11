"""Bidirectional mutation fitness and retrieval-memory scaffolding.

This module does not mutate geometry and does not replace the Physics Judge.
It provides deterministic evidence aggregation for future controlled mutation work.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REQUIRED_SCALES = ("1", "3", "5", "7")
DEFAULT_HARD_GATES = (
    "geometry_contract",
    "physical_residual",
    "equilibrium",
    "protected_geometry",
    "fdm_minimum_feature",
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _validate_unit_interval(name: str, value: float) -> None:
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be within [0, 1], got {value!r}")


def multiscale_agreement(scores: Mapping[str, float]) -> dict[str, Any]:
    """Return a deterministic 1/3/5/7 multiscale agreement score.

    The score rewards both a high mean and low disagreement across scales.
    Missing scales reduce coverage and therefore reduce the final score.
    """

    normalized = {str(key): _clamp01(value) for key, value in scores.items()}
    present = [normalized[scale] for scale in REQUIRED_SCALES if scale in normalized]
    if not present:
        return {
            "required_scales": list(REQUIRED_SCALES),
            "present_scales": [],
            "coverage": 0.0,
            "mean": 0.0,
            "spread": 1.0,
            "agreement": 0.0,
        }

    coverage = len(present) / len(REQUIRED_SCALES)
    mean = sum(present) / len(present)
    spread = max(present) - min(present)
    agreement = _clamp01(mean * (1.0 - spread) * coverage)
    return {
        "required_scales": list(REQUIRED_SCALES),
        "present_scales": [scale for scale in REQUIRED_SCALES if scale in normalized],
        "coverage": coverage,
        "mean": mean,
        "spread": spread,
        "agreement": agreement,
    }


@dataclass(slots=True)
class MutationEvidence:
    """Evidence used to rank an already-gated mutation candidate."""

    forward_score: float
    reverse_score: float
    retrieval_score: float
    printability_score: float
    uncertainty: float = 0.0
    irreversibility: float = 0.0
    phase_sensitivity: float = 0.0
    multiscale_scores: dict[str, float] = field(default_factory=dict)
    hard_gates: dict[str, bool] = field(default_factory=dict)

    def validate(self) -> None:
        for name in (
            "forward_score",
            "reverse_score",
            "retrieval_score",
            "printability_score",
            "uncertainty",
            "irreversibility",
            "phase_sensitivity",
        ):
            _validate_unit_interval(name, getattr(self, name))
        for scale, value in self.multiscale_scores.items():
            _validate_unit_interval(f"multiscale_scores[{scale!r}]", value)


@dataclass(slots=True)
class MutationQuery:
    """Deterministic query used to retrieve comparable prior experiments."""

    baseline_fingerprint: str
    contract_fingerprint: str
    load_fingerprint: str
    mutation_operator: str
    descriptor_tokens: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MutationExperimentRecord:
    """Machine-readable record for one proposed or evaluated mutation."""

    baseline_fingerprint: str
    contract_fingerprint: str
    load_fingerprint: str
    mutation_operator: str
    region_descriptor: str
    evidence: dict[str, Any]
    evaluation: dict[str, Any]
    outcome: str
    descriptor_tokens: list[str] = field(default_factory=list)
    physics_gate: str = "NOT_EVALUATED"
    printability_gate: str = "NOT_EVALUATED"
    phase_state: str = "PHASE_NOT_EVALUATED"
    provenance: dict[str, list[str]] = field(default_factory=dict)
    created_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema: str = "janus-mutation-experiment/1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "MutationExperimentRecord":
        return cls(
            baseline_fingerprint=str(raw["baseline_fingerprint"]),
            contract_fingerprint=str(raw["contract_fingerprint"]),
            load_fingerprint=str(raw["load_fingerprint"]),
            mutation_operator=str(raw["mutation_operator"]),
            region_descriptor=str(raw["region_descriptor"]),
            evidence=dict(raw["evidence"]),
            evaluation=dict(raw["evaluation"]),
            outcome=str(raw["outcome"]),
            descriptor_tokens=list(raw.get("descriptor_tokens", [])),
            physics_gate=str(raw.get("physics_gate", "NOT_EVALUATED")),
            printability_gate=str(raw.get("printability_gate", "NOT_EVALUATED")),
            phase_state=str(raw.get("phase_state", "PHASE_NOT_EVALUATED")),
            provenance={
                str(key): [str(item) for item in value]
                for key, value in dict(raw.get("provenance", {})).items()
            },
            created_at_utc=str(
                raw.get("created_at_utc", datetime.now(timezone.utc).isoformat())
            ),
            schema=str(raw.get("schema", "janus-mutation-experiment/1.0")),
        )


def evaluate_candidate(evidence: MutationEvidence) -> dict[str, Any]:
    """Evaluate a candidate without bypassing hard engineering gates.

    Fitness is a ranking aid only. A failed hard gate always produces
    ``HARD_GATE_REJECTED`` regardless of the numerical score.
    """

    evidence.validate()
    gates = {
        name: bool(evidence.hard_gates.get(name, False))
        for name in DEFAULT_HARD_GATES
    }
    gates.update({str(name): bool(value) for name, value in evidence.hard_gates.items()})
    failed_gates = sorted(name for name, passed in gates.items() if not passed)

    scale_result = multiscale_agreement(evidence.multiscale_scores)
    directional_disagreement = abs(evidence.forward_score - evidence.reverse_score)

    positive = (
        0.28 * evidence.forward_score
        + 0.28 * evidence.reverse_score
        + 0.16 * evidence.retrieval_score
        + 0.14 * scale_result["agreement"]
        + 0.14 * evidence.printability_score
    )
    penalty = (
        0.35 * evidence.uncertainty
        + 0.25 * evidence.irreversibility
        + 0.25 * evidence.phase_sensitivity
        + 0.15 * directional_disagreement
    )
    fitness = _clamp01(positive - penalty)

    if failed_gates:
        verdict = "HARD_GATE_REJECTED"
        eligible_for_ranking = False
        fitness = 0.0
    else:
        eligible_for_ranking = True
        if (
            evidence.forward_score >= 0.65
            and evidence.reverse_score >= 0.65
            and directional_disagreement <= 0.25
            and fitness >= 0.55
        ):
            verdict = "BIDIRECTIONAL_CONFIRMED"
        elif evidence.forward_score >= 0.65 and evidence.reverse_score < 0.65:
            verdict = "FORWARD_ONLY_UNCERTAIN"
        elif evidence.reverse_score >= 0.65 and evidence.forward_score < 0.65:
            verdict = "REVERSE_PRESERVED_NO_GAIN"
        else:
            verdict = "BIDIRECTIONAL_REJECTED"

    return {
        "schema": "janus-bidirectional-fitness/1.0",
        "eligible_for_ranking": eligible_for_ranking,
        "hard_gates": gates,
        "failed_hard_gates": failed_gates,
        "forward_score": evidence.forward_score,
        "reverse_score": evidence.reverse_score,
        "retrieval_score": evidence.retrieval_score,
        "printability_score": evidence.printability_score,
        "multiscale": scale_result,
        "directional_disagreement": directional_disagreement,
        "uncertainty_penalty_inputs": {
            "declared_uncertainty": evidence.uncertainty,
            "irreversibility": evidence.irreversibility,
            "phase_sensitivity": evidence.phase_sensitivity,
            "directional_disagreement": directional_disagreement,
        },
        "positive_score": positive,
        "penalty_score": penalty,
        "fitness": fitness,
        "verdict": verdict,
        "authority": "ranking_only_after_hard_gates",
        "geometry_mutation_executed": False,
    }


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = {str(item) for item in left}
    right_set = {str(item) for item in right}
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


def record_similarity(record: MutationExperimentRecord, query: MutationQuery) -> float:
    """Score deterministic similarity for retrieval-memory ranking."""

    score = 0.0
    score += 0.35 if record.baseline_fingerprint == query.baseline_fingerprint else 0.0
    score += 0.25 if record.contract_fingerprint == query.contract_fingerprint else 0.0
    score += 0.25 if record.load_fingerprint == query.load_fingerprint else 0.0
    score += 0.10 if record.mutation_operator == query.mutation_operator else 0.0
    score += 0.05 * _jaccard(record.descriptor_tokens, query.descriptor_tokens)
    return _clamp01(score)


class MutationMemory:
    """Append-only JSONL memory with deterministic retrieval.

    The atomic rewrite keeps the file valid if the process is interrupted while
    a new record is being committed.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def iter_records(self) -> Iterable[MutationExperimentRecord]:
        if not self.path.exists():
            return []
        records: list[MutationExperimentRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(MutationExperimentRecord.from_dict(json.loads(stripped)))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"Invalid mutation-memory record at line {line_number}: {exc}"
                    ) from exc
        return records

    def append(self, record: MutationExperimentRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        line = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
        payload = existing
        if payload and not payload.endswith("\n"):
            payload += "\n"
        payload += line + "\n"

        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, self.path)

    def retrieve(self, query: MutationQuery, limit: int = 5) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        ranked = [
            {
                "similarity": record_similarity(record, query),
                "record": record.to_dict(),
            }
            for record in self.iter_records()
        ]
        ranked.sort(
            key=lambda item: (
                float(item["similarity"]),
                str(item["record"].get("created_at_utc", "")),
            ),
            reverse=True,
        )
        return ranked[:limit]
