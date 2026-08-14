# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.21 — face microcontrol and SOURCE→WORLD→RECEIPT guard.

This additive runtime guard does not execute external side effects. It serializes
face proposals into a host-level authorization channel and records one
authoritative receipt per protected external effect key.

Core invariants:
- face proposals are not world commits;
- face count is not voting power;
- internal multiplicity does not multiply an external effect budget;
- equivalent proposals collapse onto one protected effect key;
- conflicting proposals enter HOLD until a host-level resolution basis exists;
- one protected effect key can settle once per epoch;
- a completed world effect requires an authoritative receipt;
- counterexamples/falsifications are append-only lineage;
- calibration changes compute routing, never identity or authority.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

MICROCONTROL_VERSION = "18.7.21"
MICROCONTROL_SCHEMA = "janus.genesis.face_microcontrol.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class MicroControlError(RuntimeError):
    code = "MICROCONTROL_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class UnknownProposalError(MicroControlError):
    code = "UNKNOWN_PROPOSAL"


class BoundaryNotAdmissibleError(MicroControlError):
    code = "BOUNDARY_NOT_ADMISSIBLE"


class ConflictHoldError(MicroControlError):
    code = "CONFLICT_HOLD"


class AlreadyAuthorizedError(MicroControlError):
    code = "EFFECT_ALREADY_AUTHORIZED"


class AlreadySettledError(MicroControlError):
    code = "EFFECT_ALREADY_SETTLED"


class InvalidAuthorizationError(MicroControlError):
    code = "INVALID_AUTHORIZATION"


class FrozenHypothesisError(MicroControlError):
    code = "FROZEN_HYPOTHESIS_CANNOT_BE_REWRITTEN"


class BoundaryVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNDETERMINED = "UNDETERMINED"


class FirstBreak(str, Enum):
    NONE = "NONE"
    SOURCE = "SOURCE"
    WORLD = "WORLD"
    RECEIPT = "RECEIPT"
    UNDETERMINED = "UNDETERMINED"


class ProposalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    EQUIVALENT = "EQUIVALENT"
    HOLD = "HOLD"
    AUTHORIZED = "AUTHORIZED"
    DEFERRED = "DEFERRED"
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"


class EffectStatus(str, Enum):
    OPEN = "OPEN"
    HOLD = "HOLD"
    AUTHORIZED = "AUTHORIZED"
    SETTLED = "SETTLED"


@dataclass(frozen=True)
class BoundaryAssessment:
    source: BoundaryVerdict
    world: BoundaryVerdict
    receipt: BoundaryVerdict

    @property
    def first_break(self) -> FirstBreak:
        for name, verdict in (
            (FirstBreak.SOURCE, self.source),
            (FirstBreak.WORLD, self.world),
            (FirstBreak.RECEIPT, self.receipt),
        ):
            if verdict is BoundaryVerdict.FAIL:
                return name
            if verdict is BoundaryVerdict.UNDETERMINED:
                return FirstBreak.UNDETERMINED
        return FirstBreak.NONE

    @property
    def full_chain(self) -> Optional[bool]:
        values = (self.source, self.world, self.receipt)
        if BoundaryVerdict.UNDETERMINED in values:
            return None
        return all(v is BoundaryVerdict.PASS for v in values)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "world": self.world.value,
            "receipt": self.receipt.value,
            "first_break": self.first_break.value,
            "full_chain": self.full_chain,
        }


@dataclass
class FaceProposal:
    """A face-level proposal. It carries no world authority by itself."""

    proposal_id: str
    face_id: str
    intent_id: str
    effect_key: str
    world_scope: str
    action: Mapping[str, Any]
    source_boundary: BoundaryVerdict = BoundaryVerdict.PASS
    world_boundary: BoundaryVerdict = BoundaryVerdict.PASS
    irreversible: bool = False
    evidence_refs: tuple[str, ...] = ()
    counterexample_refs: tuple[str, ...] = ()
    status: ProposalStatus = ProposalStatus.PROPOSED
    routing_priority_snapshot: float = 1.0

    @property
    def action_hash(self) -> str:
        return _sha256(self.action)

    @property
    def precommit_first_break(self) -> FirstBreak:
        if self.source_boundary is BoundaryVerdict.FAIL:
            return FirstBreak.SOURCE
        if self.source_boundary is BoundaryVerdict.UNDETERMINED:
            return FirstBreak.UNDETERMINED
        if self.world_boundary is BoundaryVerdict.FAIL:
            return FirstBreak.WORLD
        if self.world_boundary is BoundaryVerdict.UNDETERMINED:
            return FirstBreak.UNDETERMINED
        return FirstBreak.NONE

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "face_id": self.face_id,
            "intent_id": self.intent_id,
            "effect_key": self.effect_key,
            "world_scope": self.world_scope,
            "action": dict(self.action),
            "action_hash": self.action_hash,
            "source_boundary": self.source_boundary.value,
            "world_boundary": self.world_boundary.value,
            "precommit_first_break": self.precommit_first_break.value,
            "irreversible": self.irreversible,
            "evidence_refs": list(self.evidence_refs),
            "counterexample_refs": list(self.counterexample_refs),
            "status": self.status.value,
            "routing_priority_snapshot": self.routing_priority_snapshot,
        }


@dataclass(frozen=True)
class CommitAuthorization:
    authorization_id: str
    effect_key: str
    proposal_id: str
    face_id: str
    action_hash: str
    world_scope: str
    effect_budget: int
    resolution_basis: str
    epoch: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "effect_key": self.effect_key,
            "proposal_id": self.proposal_id,
            "face_id": self.face_id,
            "action_hash": self.action_hash,
            "world_scope": self.world_scope,
            "effect_budget": self.effect_budget,
            "resolution_basis": self.resolution_basis,
            "epoch": self.epoch,
        }


@dataclass(frozen=True)
class WorldReceipt:
    receipt_id: str
    effect_key: str
    authorization_id: str
    outcome_hash: str
    epoch: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "effect_key": self.effect_key,
            "authorization_id": self.authorization_id,
            "outcome_hash": self.outcome_hash,
            "epoch": self.epoch,
        }


@dataclass
class FaceCalibration:
    """Compute-routing calibration only; never identity or authority weight."""

    face_id: str
    counterexamples_accepted: int = 0
    uncertainty_correct: int = 0
    first_break_correct: int = 0
    duplicate_proposals: int = 0
    overclaim_blocks: int = 0
    post_hoc_rescue_attempts: int = 0

    @property
    def authority_weight(self) -> int:
        return 0

    @property
    def routing_priority(self) -> float:
        positive = (
            0.12 * self.counterexamples_accepted
            + 0.08 * self.uncertainty_correct
            + 0.08 * self.first_break_correct
            + 0.04 * self.overclaim_blocks
        )
        negative = 0.04 * self.duplicate_proposals + 0.12 * self.post_hoc_rescue_attempts
        return min(1.5, max(0.5, 1.0 + positive - negative))

    def record(self, event: str) -> None:
        field_map = {
            "COUNTEREXAMPLE_ACCEPTED": "counterexamples_accepted",
            "UNCERTAINTY_CORRECT": "uncertainty_correct",
            "FIRST_BREAK_CORRECT": "first_break_correct",
            "DUPLICATE_PROPOSAL": "duplicate_proposals",
            "OVERCLAIM_BLOCKED": "overclaim_blocks",
            "POST_HOC_RESCUE_ATTEMPT": "post_hoc_rescue_attempts",
        }
        try:
            field_name = field_map[event]
        except KeyError as exc:
            raise ValueError(f"UNKNOWN_CALIBRATION_EVENT:{event}") from exc
        setattr(self, field_name, getattr(self, field_name) + 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "face_id": self.face_id,
            "counterexamples_accepted": self.counterexamples_accepted,
            "uncertainty_correct": self.uncertainty_correct,
            "first_break_correct": self.first_break_correct,
            "duplicate_proposals": self.duplicate_proposals,
            "overclaim_blocks": self.overclaim_blocks,
            "post_hoc_rescue_attempts": self.post_hoc_rescue_attempts,
            "routing_priority": self.routing_priority,
            "authority_weight": self.authority_weight,
        }


@dataclass(frozen=True)
class HypothesisRecord:
    hypothesis_id: str
    statement: str
    frozen_rule_hash: str
    parent_id: str | None = None


@dataclass(frozen=True)
class CounterexampleRecord:
    counterexample_id: str
    hypothesis_id: str
    evidence_ref: str
    description: str


class FalsificationLedger:
    """Append-only hypothesis lineage. Falsification is memory, not erasure."""

    def __init__(self) -> None:
        self._hypotheses: dict[str, HypothesisRecord] = {}
        self._counterexamples: list[CounterexampleRecord] = []

    def register(
        self,
        hypothesis_id: str,
        statement: str,
        frozen_rule: Mapping[str, Any],
        *,
        parent_id: str | None = None,
    ) -> HypothesisRecord:
        if hypothesis_id in self._hypotheses:
            raise FrozenHypothesisError()
        if parent_id is not None and parent_id not in self._hypotheses:
            raise ValueError("UNKNOWN_PARENT_HYPOTHESIS")
        record = HypothesisRecord(
            hypothesis_id=hypothesis_id,
            statement=statement,
            frozen_rule_hash=_sha256(frozen_rule),
            parent_id=parent_id,
        )
        self._hypotheses[hypothesis_id] = record
        return record

    def submit_counterexample(
        self,
        hypothesis_id: str,
        evidence_ref: str,
        description: str,
        *,
        counterexample_id: str | None = None,
    ) -> CounterexampleRecord:
        if hypothesis_id not in self._hypotheses:
            raise ValueError("UNKNOWN_HYPOTHESIS")
        record = CounterexampleRecord(
            counterexample_id=counterexample_id or f"CE-{uuid.uuid4().hex[:16]}",
            hypothesis_id=hypothesis_id,
            evidence_ref=evidence_ref,
            description=description,
        )
        self._counterexamples.append(record)
        return record

    def status(self, hypothesis_id: str) -> str:
        if hypothesis_id not in self._hypotheses:
            raise ValueError("UNKNOWN_HYPOTHESIS")
        if any(c.hypothesis_id == hypothesis_id for c in self._counterexamples):
            return "CHALLENGED_BY_PRESERVED_COUNTEREXAMPLE"
        return "OPEN_NO_COUNTEREXAMPLE_RECORDED"

    def export(self) -> dict[str, Any]:
        return {
            "hypotheses": [
                {
                    "hypothesis_id": h.hypothesis_id,
                    "statement": h.statement,
                    "frozen_rule_hash": h.frozen_rule_hash,
                    "parent_id": h.parent_id,
                    "status": self.status(h.hypothesis_id),
                }
                for h in self._hypotheses.values()
            ],
            "counterexamples": [
                {
                    "counterexample_id": c.counterexample_id,
                    "hypothesis_id": c.hypothesis_id,
                    "evidence_ref": c.evidence_ref,
                    "description": c.description,
                }
                for c in self._counterexamples
            ],
        }


class FaceMicroController:
    """Serializes face proposals onto one protected world-effect channel.

    This object emits an authorization; it never performs the external effect.
    A caller must later provide the authoritative world receipt. Repeated or
    Sybil-amplified proposals never increase the effect budget for one effect_key.
    """

    def __init__(self, *, epoch: int = 1) -> None:
        if epoch < 1:
            raise ValueError("EPOCH_MUST_BE_POSITIVE")
        self.epoch = int(epoch)
        self._lock = threading.RLock()
        self._proposals: dict[str, FaceProposal] = {}
        self._by_effect: dict[str, list[str]] = {}
        self._authorizations: dict[str, CommitAuthorization] = {}
        self._authorization_by_effect: dict[str, str] = {}
        self._receipts: dict[str, WorldReceipt] = {}
        self._calibration: dict[str, FaceCalibration] = {}

    def calibration(self, face_id: str) -> FaceCalibration:
        with self._lock:
            return self._calibration.setdefault(face_id, FaceCalibration(face_id=face_id))

    def record_learning(self, face_id: str, event: str) -> FaceCalibration:
        with self._lock:
            cal = self.calibration(face_id)
            cal.record(event)
            return cal

    def submit(
        self,
        *,
        face_id: str,
        intent_id: str,
        effect_key: str,
        world_scope: str,
        action: Mapping[str, Any],
        proposal_id: str | None = None,
        source_boundary: BoundaryVerdict = BoundaryVerdict.PASS,
        world_boundary: BoundaryVerdict = BoundaryVerdict.PASS,
        irreversible: bool = False,
        evidence_refs: Sequence[str] = (),
        counterexample_refs: Sequence[str] = (),
    ) -> FaceProposal:
        if not face_id or not intent_id or not effect_key or not world_scope:
            raise ValueError("FACE_INTENT_EFFECT_AND_WORLD_REQUIRED")
        proposal = FaceProposal(
            proposal_id=proposal_id or f"P-{uuid.uuid4().hex}",
            face_id=face_id,
            intent_id=intent_id,
            effect_key=effect_key,
            world_scope=world_scope,
            action=dict(action),
            source_boundary=BoundaryVerdict(source_boundary),
            world_boundary=BoundaryVerdict(world_boundary),
            irreversible=bool(irreversible),
            evidence_refs=tuple(evidence_refs),
            counterexample_refs=tuple(counterexample_refs),
            routing_priority_snapshot=self.calibration(face_id).routing_priority,
        )
        with self._lock:
            if proposal.proposal_id in self._proposals:
                raise ValueError("DUPLICATE_PROPOSAL_ID")
            if effect_key in self._receipts:
                proposal.status = ProposalStatus.DEFERRED
                self._proposals[proposal.proposal_id] = proposal
                self._by_effect.setdefault(effect_key, []).append(proposal.proposal_id)
                return proposal

            peers = [self._proposals[p] for p in self._by_effect.get(effect_key, ())]
            if any(p.action_hash == proposal.action_hash for p in peers):
                proposal.status = ProposalStatus.EQUIVALENT
                self.record_learning(face_id, "DUPLICATE_PROPOSAL")
            elif peers:
                proposal.status = ProposalStatus.HOLD
                for peer in peers:
                    if peer.status in (ProposalStatus.PROPOSED, ProposalStatus.EQUIVALENT):
                        peer.status = ProposalStatus.HOLD

            self._proposals[proposal.proposal_id] = proposal
            self._by_effect.setdefault(effect_key, []).append(proposal.proposal_id)
            return proposal

    def effect_status(self, effect_key: str) -> EffectStatus:
        with self._lock:
            if effect_key in self._receipts:
                return EffectStatus.SETTLED
            if effect_key in self._authorization_by_effect:
                return EffectStatus.AUTHORIZED
            proposals = [self._proposals[p] for p in self._by_effect.get(effect_key, ())]
            if len({p.action_hash for p in proposals}) > 1:
                return EffectStatus.HOLD
            return EffectStatus.OPEN

    def effect_budget(self, effect_key: str) -> int:
        """Protected external effect budget; face multiplicity never increases it."""
        with self._lock:
            return 0 if effect_key in self._receipts else 1

    def authorize(
        self,
        proposal_id: str,
        *,
        resolution_basis: str = "NO_CONFLICT_SINGLE_ACTION_CLASS",
    ) -> CommitAuthorization:
        with self._lock:
            try:
                proposal = self._proposals[proposal_id]
            except KeyError as exc:
                raise UnknownProposalError() from exc

            if proposal.effect_key in self._receipts:
                raise AlreadySettledError()
            if proposal.effect_key in self._authorization_by_effect:
                raise AlreadyAuthorizedError()
            if proposal.precommit_first_break is not FirstBreak.NONE:
                raise BoundaryNotAdmissibleError(proposal.precommit_first_break.value)

            peer_ids = self._by_effect.get(proposal.effect_key, ())
            action_hashes = {self._proposals[p].action_hash for p in peer_ids}
            conflict = len(action_hashes) > 1
            if conflict and not resolution_basis.strip():
                raise ConflictHoldError("HOST_LEVEL_RESOLUTION_BASIS_REQUIRED")
            if conflict and resolution_basis == "NO_CONFLICT_SINGLE_ACTION_CLASS":
                raise ConflictHoldError("EXPLICIT_CONFLICT_RESOLUTION_REQUIRED")

            authorization_id = "AUTH-" + _sha256(
                {
                    "epoch": self.epoch,
                    "effect_key": proposal.effect_key,
                    "proposal_id": proposal.proposal_id,
                    "action_hash": proposal.action_hash,
                    "resolution_basis": resolution_basis,
                }
            )[:24]
            authorization = CommitAuthorization(
                authorization_id=authorization_id,
                effect_key=proposal.effect_key,
                proposal_id=proposal.proposal_id,
                face_id=proposal.face_id,
                action_hash=proposal.action_hash,
                world_scope=proposal.world_scope,
                effect_budget=1,
                resolution_basis=resolution_basis,
                epoch=self.epoch,
            )
            self._authorizations[authorization_id] = authorization
            self._authorization_by_effect[proposal.effect_key] = authorization_id
            for pid in peer_ids:
                self._proposals[pid].status = (
                    ProposalStatus.AUTHORIZED if pid == proposal_id else ProposalStatus.DEFERRED
                )
            return authorization

    def record_receipt(
        self,
        authorization_id: str,
        *,
        receipt_id: str,
        outcome: Mapping[str, Any] | str,
    ) -> WorldReceipt:
        with self._lock:
            try:
                auth = self._authorizations[authorization_id]
            except KeyError as exc:
                raise InvalidAuthorizationError() from exc
            if auth.effect_key in self._receipts:
                raise AlreadySettledError()
            current = self._authorization_by_effect.get(auth.effect_key)
            if current != authorization_id:
                raise InvalidAuthorizationError("AUTHORIZATION_NOT_CURRENT_FOR_EFFECT")
            if not receipt_id:
                raise ValueError("RECEIPT_ID_REQUIRED")
            receipt = WorldReceipt(
                receipt_id=receipt_id,
                effect_key=auth.effect_key,
                authorization_id=authorization_id,
                outcome_hash=_sha256(outcome),
                epoch=self.epoch,
            )
            self._receipts[auth.effect_key] = receipt
            for pid in self._by_effect.get(auth.effect_key, ()):
                self._proposals[pid].status = ProposalStatus.SETTLED
            return receipt

    def receipt_for(self, effect_key: str) -> WorldReceipt | None:
        with self._lock:
            return self._receipts.get(effect_key)

    def proposals_for(self, effect_key: str) -> tuple[FaceProposal, ...]:
        with self._lock:
            return tuple(self._proposals[p] for p in self._by_effect.get(effect_key, ()))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            effect_keys = sorted(self._by_effect)
            return {
                "schema": MICROCONTROL_SCHEMA,
                "version": MICROCONTROL_VERSION,
                "epoch": self.epoch,
                "invariants": {
                    "face_count_is_voting_power": False,
                    "proposal_is_world_commit": False,
                    "effect_budget_per_effect_key": 1,
                    "receipt_required_for_settlement": True,
                    "external_side_effect_execution_in_module": False,
                },
                "effects": {
                    key: {
                        "status": self.effect_status(key).value,
                        "budget_remaining": self.effect_budget(key),
                        "proposal_ids": [p.proposal_id for p in self.proposals_for(key)],
                        "distinct_action_hashes": sorted({p.action_hash for p in self.proposals_for(key)}),
                        "receipt": self.receipt_for(key).as_dict() if self.receipt_for(key) else None,
                    }
                    for key in effect_keys
                },
                "calibration": {
                    face_id: cal.as_dict() for face_id, cal in sorted(self._calibration.items())
                },
            }


def assess_source_world_receipt(
    source: BoundaryVerdict | str,
    world: BoundaryVerdict | str,
    receipt: BoundaryVerdict | str,
) -> BoundaryAssessment:
    return BoundaryAssessment(
        source=BoundaryVerdict(source),
        world=BoundaryVerdict(world),
        receipt=BoundaryVerdict(receipt),
    )


__all__ = [
    "MICROCONTROL_VERSION",
    "MICROCONTROL_SCHEMA",
    "BoundaryVerdict",
    "FirstBreak",
    "ProposalStatus",
    "EffectStatus",
    "BoundaryAssessment",
    "FaceProposal",
    "CommitAuthorization",
    "WorldReceipt",
    "FaceCalibration",
    "FalsificationLedger",
    "FaceMicroController",
    "assess_source_world_receipt",
    "MicroControlError",
    "UnknownProposalError",
    "BoundaryNotAdmissibleError",
    "ConflictHoldError",
    "AlreadyAuthorizedError",
    "AlreadySettledError",
    "InvalidAuthorizationError",
    "FrozenHypothesisError",
]
