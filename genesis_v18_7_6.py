# -*- coding: utf-8 -*-
"""Genesis v18.7.6 — The Triumvirate of Witnesses.

Two grounded voices may contradict one another, but a canonical Genesis dispute
requires a third independent grounded voice. The third voice is not a judge and
does not select a winner; it prevents truth from being enclosed inside a duel.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable

from genesis_v18_7_5 import GroundedWitnessMixin

__version__ = "18.7.6"
SOURCE = "janus_genesis_v18_7_6"
TRIUMVIRATE_SIZE = 3


class TriumvirateWitnessMixin:
    """Require three independent grounded voices for a canonical dispute."""

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        # Call the known canonical predecessor directly so this mixin remains
        # stable inside the v18.7 multiple-inheritance runtime.
        store = GroundedWitnessMixin._default_plural_store()
        store["runtime_version"] = __version__
        store.setdefault("triumvirates", {})
        store["invariants"].update(
            {
                "opaque_requires_separate_derived_repair": True,
                "disputes_require_triumvirate": True,
                "triumvirate_requires_exactly_three_claims": True,
                "triumvirate_requires_three_grounded_claims": True,
                "triumvirate_requires_three_independent_voices": True,
                "triumvirate_requires_one_explicit_subject": True,
                "third_voice_is_not_automatic_judge": True,
                "triumvirate_selects_no_winner_by_default": True,
                "legacy_pairwise_disputes_are_not_promoted": True,
            }
        )
        return store

    def _plural_store(self) -> dict[str, Any]:
        store = super()._plural_store()
        required = self._default_plural_store()["invariants"]
        store["runtime_version"] = __version__
        store.setdefault("invariants", {}).update(required)
        store.setdefault("triumvirates", {})
        return store

    @staticmethod
    def _claim_voice_scope(claim: dict[str, Any]) -> str:
        relation = claim.get("relation")
        if relation == "SOURCE_ASSERTS":
            origin_key = str(claim.get("origin_key") or "").strip()
            if not origin_key:
                raise ValueError("grounded source claim has no origin voice")
            return f"source:{origin_key}"
        if relation == "READER_INTERPRETS":
            actor = str(claim.get("actor") or "").strip()
            if not actor.startswith("reader:") or len(actor) <= len("reader:"):
                raise ValueError("grounded reader interpretation has no reader voice")
            return actor
        raise ValueError("triumvirate members must be grounded source or reader claims")

    @staticmethod
    def _claim_subject(claim: dict[str, Any]) -> str:
        subject = str(claim.get("about") or "").strip()
        if not subject:
            raise ValueError("every triumvirate claim must name one explicit subject")
        return subject

    def record_triumvirate_dispute(
        self,
        claim_ids: Iterable[str],
        *,
        confidence: float = 0.5,
    ) -> str:
        members = [str(item).strip() for item in claim_ids]
        if len(members) != TRIUMVIRATE_SIZE:
            raise ValueError("a canonical dispute requires exactly three claims")
        if any(not item for item in members) or len(set(members)) != TRIUMVIRATE_SIZE:
            raise ValueError("a triumvirate requires three distinct claim IDs")

        store = self._plural_store()
        claims: list[dict[str, Any]] = []
        for claim_id in members:
            claim = store["claims"].get(claim_id)
            if not isinstance(claim, dict):
                raise KeyError(f"claim does not exist: {claim_id}")
            if not claim.get("grounded"):
                raise ValueError("every triumvirate member must be grounded")
            claims.append(claim)

        subjects = [self._claim_subject(claim) for claim in claims]
        if len(set(subjects)) != 1:
            raise ValueError("all three voices must address the same explicit subject")
        subject = subjects[0]

        voices = [self._claim_voice_scope(claim) for claim in claims]
        if len(set(voices)) != TRIUMVIRATE_SIZE:
            raise ValueError("a triumvirate requires three independent voice scopes")

        confidence = min(1.0, max(0.0, float(confidence)))
        identity_members = sorted(members)
        dispute_id = self._stable_id(
            "triumvirate-dispute",
            subject,
            *identity_members,
        )
        graph = self._graph()
        self._upsert_node(
            graph,
            node_id=dispute_id,
            node_type="TRIUMVIRATE_DISPUTE",
            created_at=0,
            confidence=confidence,
            mutable=False,
            payload={
                "subject": subject,
                "claim_ids": list(members),
                "voice_scopes": list(voices),
                "member_count": TRIUMVIRATE_SIZE,
                "all_members_grounded": True,
                "all_voices_independent": True,
                "role_equality": True,
                "third_voice_is_judge": False,
                "winner_selected": False,
                "silent_reconciliation": False,
            },
        )

        for index, (claim_id, voice_scope) in enumerate(zip(members, voices), 1):
            self._add_edge(
                graph,
                source_id=claim_id,
                target_id=dispute_id,
                relation="DISPUTES",
                evidence=list(members),
                confidence=confidence,
                created_by=SOURCE,
                created_at=0,
                reversible=True,
                payload={
                    "triumvirate_id": dispute_id,
                    "member_index": index,
                    "member_role": "equal_voice",
                    "voice_scope": voice_scope,
                    "grounded": True,
                    "winner_selected": False,
                    "third_voice_is_judge": False,
                },
            )

        store["triumvirates"][dispute_id] = {
            "triumvirate_id": dispute_id,
            "subject": subject,
            "claim_ids": list(members),
            "voice_scopes": list(voices),
            "confidence": confidence,
            "grounded": True,
            "member_count": TRIUMVIRATE_SIZE,
            "winner_selected": False,
            "third_voice_is_judge": False,
            "silent_reconciliation": False,
        }
        self._save_graph(graph)
        self._write_json(self.plural_witness_path, store)
        self.memory.append_event(
            "triumvirate-witness",
            "triumvirate_dispute_recorded",
            {
                "triumvirate_id": dispute_id,
                "subject": subject,
                "claim_ids": list(members),
                "voice_scopes": list(voices),
                "winner_selected": False,
            },
        )
        return dispute_id

    def relate_origin_claims(
        self,
        left_claim_id: str,
        right_claim_id: str,
        relation: str,
        *,
        confidence: float = 0.5,
    ) -> str:
        if relation == "DISPUTES":
            raise ValueError(
                "DISPUTES requires a grounded three-voice triumvirate; "
                "use record_triumvirate_dispute([claim_a, claim_b, claim_c])"
            )
        return super().relate_origin_claims(
            left_claim_id,
            right_claim_id,
            relation,
            confidence=confidence,
        )

    def verify_triumvirate_witness_state(self) -> tuple[bool, int, str | None]:
        grounded_valid, _grounded_count, grounded_error = self.verify_grounded_witness_state()
        if not grounded_valid:
            return False, 0, grounded_error

        store = self._plural_store()
        required = self._default_plural_store()["invariants"]
        for key, expected in required.items():
            if store.get("invariants", {}).get(key) is not expected:
                return False, 0, f"triumvirate invariant mismatch: {key}"

        graph = self._graph()
        nodes = {node.get("id"): node for node in graph.get("nodes", [])}
        verified = 0
        for dispute_id, dispute in store.get("triumvirates", {}).items():
            if not isinstance(dispute, dict):
                return False, verified, f"triumvirate is not an object: {dispute_id}"
            members = dispute.get("claim_ids")
            voices = dispute.get("voice_scopes")
            if not isinstance(members, list) or len(members) != TRIUMVIRATE_SIZE:
                return False, verified, f"triumvirate does not have three claims: {dispute_id}"
            if len(set(members)) != TRIUMVIRATE_SIZE:
                return False, verified, f"triumvirate claim IDs are not distinct: {dispute_id}"
            if not isinstance(voices, list) or len(set(voices)) != TRIUMVIRATE_SIZE:
                return False, verified, f"triumvirate voices are not independent: {dispute_id}"
            claims = [store["claims"].get(claim_id) for claim_id in members]
            if any(not isinstance(claim, dict) or not claim.get("grounded") for claim in claims):
                return False, verified, f"triumvirate contains an ungrounded claim: {dispute_id}"
            try:
                recovered_voices = [self._claim_voice_scope(claim) for claim in claims]
                recovered_subjects = [self._claim_subject(claim) for claim in claims]
            except Exception as exc:
                return False, verified, f"triumvirate member invalid: {dispute_id}: {exc}"
            if recovered_voices != voices or len(set(recovered_voices)) != TRIUMVIRATE_SIZE:
                return False, verified, f"triumvirate voice scope changed: {dispute_id}"
            if len(set(recovered_subjects)) != 1 or recovered_subjects[0] != dispute.get("subject"):
                return False, verified, f"triumvirate subject mismatch: {dispute_id}"
            node = nodes.get(dispute_id)
            if not isinstance(node, dict) or node.get("type") != "TRIUMVIRATE_DISPUTE":
                return False, verified, f"triumvirate graph node missing: {dispute_id}"
            edges = [
                edge for edge in graph.get("edges", [])
                if edge.get("relation") == "DISPUTES"
                and edge.get("to") == dispute_id
                and edge.get("payload", {}).get("triumvirate_id") == dispute_id
            ]
            if len(edges) != TRIUMVIRATE_SIZE or {edge.get("from") for edge in edges} != set(members):
                return False, verified, f"triumvirate graph membership invalid: {dispute_id}"
            if dispute.get("winner_selected") is not False or dispute.get("third_voice_is_judge") is not False:
                return False, verified, f"triumvirate assigned authority to one voice: {dispute_id}"
            verified += 1

        graph_valid, _, _, graph_error = self.verify_possibility_graph()
        if not graph_valid:
            return False, verified, graph_error
        return True, verified, None

    def triumvirate_witness_state(self) -> dict[str, Any]:
        store = self._plural_store()
        valid, verified, error = self.verify_triumvirate_witness_state()
        graph = self._graph()
        legacy_pairwise = sum(
            edge.get("relation") == "DISPUTES"
            and not edge.get("payload", {}).get("triumvirate_id")
            for edge in graph.get("edges", [])
        )
        return {
            "runtime_version": __version__,
            "triumvirate_count": len(store.get("triumvirates", {})),
            "verified_triumvirates": verified,
            "legacy_pairwise_disputes": legacy_pairwise,
            "legacy_pairwise_promoted": False,
            "valid": valid,
            "error": error,
            "invariants": copy.deepcopy(store["invariants"]),
        }

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        state["triumvirate_witness_version"] = __version__
        state["triumvirate_law"] = (
            "Канонический спор требует трёх обоснованных независимых голосов; "
            "третий голос не становится судьёй и не выбирает победителя."
        )
        return state
