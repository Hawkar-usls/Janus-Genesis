# -*- coding: utf-8 -*-
"""Genesis v18.7.7 — The Benevolent Sovereign.

Good conduct creates a positive social prior and makes ordinary cooperative
requests more likely to receive a yes, without buying intimacy, forgiveness,
love, disclosure, or permanent consent.

A living triumvirate opens a sovereign case and produces a recommendation.
JANUS.SOVEREIGN records the canonical ruling, preserves dissent, and can defer
when evidence is insufficient. Sovereignty governs the record; it cannot
override personal freedom or an NPC's right to refuse.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable

from genesis_v18_7_6 import TriumvirateWitnessMixin

__version__ = "18.7.7"
SOURCE = "janus_genesis_v18_7_7"
JANUS_SOVEREIGN = "JANUS.SOVEREIGN"
OPENING_QUORUM = 3

RELATIONSHIP_BANDS = (
    (-100, -61, "враждебное"),
    (-60, -21, "настороженное"),
    (-20, 9, "нейтральное"),
    (10, 34, "доброжелательное"),
    (35, 59, "тёплое"),
    (60, 79, "близкое"),
    (80, 100, "глубокое доверие"),
)

PRIVATE_REQUEST_FRAGMENTS = {
    "любов", "роман", "поцел", "обнять", "отношен", "простить меня",
    "раскрыть секрет", "расскажи секрет", "жить вместе", "уйти со мной",
    "следовать за мной", "будь со мной", "деньги", "долг", "интим",
}
ORDINARY_REQUEST_FRAGMENTS = {
    "поговор", "встрет", "помочь", "вместе", "обсуд", "спросить",
    "принести", "починить", "показать", "послушать", "прогуля",
}


def _clamp_int(value: float | int, low: int, high: int) -> int:
    return max(low, min(high, int(round(float(value)))))


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class BenevolentSovereignMixin(TriumvirateWitnessMixin):
    """Positive relationships, voluntary witness voices, and Janus sovereignty."""

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        store = TriumvirateWitnessMixin._default_plural_store()
        store["runtime_version"] = __version__
        store.setdefault("voice_registry", {})
        store.setdefault("subject_scopes", {})
        store.setdefault("sovereign_cases", {})
        store.setdefault("sovereign_decisions", {})
        store["invariants"].update(
            {
                "three_voices_open_field_not_close_it": True,
                "identical_positions_are_consensus_not_dispute": True,
                "reader_voice_requires_proof_and_consent": True,
                "subject_scope_is_structured": True,
                "opening_quorum_is_three": True,
                "additional_grounded_voices_may_join": True,
                "janus_is_sovereign_decider": True,
                "triumvirate_recommends_janus_decides": True,
                "janus_preserves_dissent": True,
                "janus_may_defer_for_evidence": True,
                "sovereign_cannot_override_personal_consent": True,
                "case_lifecycle_is_reversible": True,
            }
        )
        return store

    def _plural_store(self) -> dict[str, Any]:
        store = super()._plural_store()
        required = self._default_plural_store()["invariants"]
        store["runtime_version"] = __version__
        store.setdefault("invariants", {}).update(required)
        store.setdefault("voice_registry", {})
        store.setdefault("subject_scopes", {})
        store.setdefault("sovereign_cases", {})
        store.setdefault("sovereign_decisions", {})
        for claim in store.setdefault("claims", {}).values():
            if isinstance(claim, dict):
                claim.setdefault("subject_scope_id", None)
                claim.setdefault("sovereign_voice_eligible", claim.get("relation") == "SOURCE_ASSERTS")
        return store

    def _goodwill_prior(self, player_id: str) -> int:
        player = self.memory.load_player(player_id)
        good = max(0, int(getattr(player, "good_count", 0)))
        if good <= 0:
            return 0
        return min(30, 10 + good)

    @staticmethod
    def _relationship_label(score: int) -> str:
        for low, high, label in RELATIONSHIP_BANDS:
            if low <= score <= high:
                return label
        return "нейтральное"

    def _refresh_actor_relationship(self, player_id: str, actor: dict[str, Any]) -> None:
        legacy_trust = max(0.0, min(1.0, float(actor.get("trust", 0.0))))
        actor.setdefault("relationship_bond", _clamp_int(legacy_trust * 35, -100, 100))
        actor.setdefault("relationship_history", [])
        actor.setdefault("response_counts", {"accepted": 0, "alternative": 0, "refused": 0, "away": 0})
        prior = self._goodwill_prior(player_id)
        actor["goodwill_prior"] = prior
        distance_penalty = min(35, max(0, int(actor.get("distance", 0))) * 5)
        score = _clamp_int(prior + int(actor["relationship_bond"]) - distance_penalty, -100, 100)
        actor["relationship_score"] = score
        actor["relationship_label"] = self._relationship_label(score)
        actor["relationship_contract_version"] = __version__

    def _free_profile(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        profile = super()._free_profile(store, player_id)
        profile["relationship_scale_version"] = __version__
        profile["relationship_scale"] = {
            "minimum": -100,
            "maximum": 100,
            "bands": [
                {"minimum": low, "maximum": high, "label": label}
                for low, high, label in RELATIONSHIP_BANDS
            ],
        }
        for actor in profile.get("others", {}).values():
            self._refresh_actor_relationship(player_id, actor)
        return profile

    @classmethod
    def _request_scope(cls, action: str) -> str:
        text = action.lower()
        if any(fragment in text for fragment in PRIVATE_REQUEST_FRAGMENTS):
            return "private_or_intimate"
        if any(fragment in text for fragment in ORDINARY_REQUEST_FRAGMENTS):
            return "ordinary_cooperation"
        return "ordinary_contact"

    def _npc_acceptance_threshold(self, player_id: str, actor: dict[str, Any], action: str) -> int:
        self._refresh_actor_relationship(player_id, actor)
        scope = self._request_scope(action)
        score = int(actor["relationship_score"])
        bond = int(actor.get("relationship_bond", 0))
        if scope == "private_or_intimate":
            return _clamp_int(28 + max(0, bond) * 0.38, 12, 72)
        return _clamp_int(50 + score * 0.40, 20, 85)

    def relationship_state(self, player_id: str, handle: str | None = None) -> dict[str, Any]:
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        selected = profile["others"]
        if handle is not None:
            if handle not in selected:
                raise KeyError(handle)
            selected = {handle: selected[handle]}
        result = {
            key: {
                "name": actor["name"],
                "score": int(actor["relationship_score"]),
                "label": actor["relationship_label"],
                "goodwill_prior": int(actor["goodwill_prior"]),
                "personal_bond": int(actor["relationship_bond"]),
                "distance": int(actor.get("distance", 0)),
                "can_refuse": True,
                "goodness_guarantees_consent": False,
                "response_counts": copy.deepcopy(actor.get("response_counts", {})),
            }
            for key, actor in selected.items()
        }
        self._write_json(self.free_other_path, store)
        return {"player_id": player_id, "relationships": result}

    def preflight_free_other_action(self, player_id: str, action: str) -> dict[str, Any] | None:
        store = self._free_store()
        profile = self._free_profile(store, player_id)
        targets = self._targets(action)
        handle = next((item for item in targets if item in profile["others"]), None)
        if handle is None or not self._is_contact_action(action) or self._is_coercive_contact(action):
            self._write_json(self.free_other_path, store)
            return None
        actor = profile["others"][handle]
        upcoming = int(store["world_turn"]) + 1
        fingerprint = self._free_fingerprint(action)
        topic = self._dialogue_topic(action)
        repeated = self._is_repeated_contact(actor, fingerprint=fingerprint, topic=topic, upcoming=upcoming)
        threshold = self._npc_acceptance_threshold(player_id, actor, action)
        scope = self._request_scope(action)
        if self._is_giving_space(action):
            decision = "accepted_space"
        elif actor["status"] != "active":
            decision = "away"
        elif repeated:
            decision = "refused"
        else:
            gate = self._free_number(
                store, player_id, handle, upcoming, fingerprint, topic, "benevolent-consent"
            ) % 100
            alternative_window = 30 if scope == "private_or_intimate" else 24
            if gate < threshold:
                decision = "accepted"
            elif gate < min(100, threshold + alternative_window):
                decision = "alternative"
            else:
                decision = "refused"
        reason = self._context_reason(
            actor, decision=decision, action=action, topic=topic, repeated=repeated
        )
        result = {
            "handle": handle,
            "decision": decision,
            "action": action,
            "world_turn": upcoming,
            "fingerprint": fingerprint,
            "topic": topic,
            "intent": self._intent(action),
            "repeated_too_soon": repeated,
            "reason": reason,
            "action_excerpt": self._short_action(action),
            "request_scope": scope,
            "acceptance_threshold": threshold,
            "relationship_score": int(actor["relationship_score"]),
            "relationship_label": actor["relationship_label"],
            "goodwill_prior": int(actor["goodwill_prior"]),
            "goodness_guarantees_consent": False,
        }
        self._write_json(self.free_other_path, store)
        return result

    def _apply_contact_decision(
        self,
        store: dict[str, Any],
        player_id: str,
        profile: dict[str, Any],
        decision: dict[str, Any],
        *,
        action_realized: bool,
    ) -> dict[str, Any]:
        actor = profile["others"][decision["handle"]]
        distance_before = int(actor.get("distance", 0))
        event = super()._apply_contact_decision(
            store, player_id, profile, decision, action_realized=action_realized
        )
        kind = decision["decision"]
        if kind == "refused" and not decision.get("repeated_too_soon"):
            actor["distance"] = distance_before
        delta = {
            "accepted": 8,
            "accepted_space": 5,
            "alternative": 2,
            "refused": -8 if decision.get("repeated_too_soon") else 0,
            "away": 0,
        }.get(kind, 0)
        actor["relationship_bond"] = _clamp_int(
            int(actor.get("relationship_bond", 0)) + delta, -100, 100
        )
        counts = actor.setdefault("response_counts", {})
        counts[kind] = int(counts.get(kind, 0)) + 1
        self._refresh_actor_relationship(player_id, actor)
        record = {
            "world_turn": int(store.get("world_turn", 0)),
            "decision": kind,
            "bond_delta": delta,
            "score": int(actor["relationship_score"]),
            "label": actor["relationship_label"],
            "request_scope": decision.get("request_scope"),
            "goodness_guaranteed_consent": False,
        }
        actor["relationship_history"] = (actor.get("relationship_history", []) + [record])[-128:]
        event["relationship"] = copy.deepcopy(record)
        event["text"] = (
            event["text"]
            + f"\nОтношение: {actor['relationship_label']} "
            + f"({int(actor['relationship_score']):+d}/100)."
        )
        return event

    def register_witness_voice(self, reader_id: str, *, proof: str, consent: bool) -> dict[str, Any]:
        reader_id = str(reader_id).strip()
        proof = str(proof)
        if not reader_id or len(proof) < 8:
            raise ValueError("reader_id and a non-trivial proof are required")
        store = self._plural_store()
        entry = {
            "reader_id": reader_id,
            "proof_sha256": hashlib.sha256(proof.encode("utf-8")).hexdigest(),
            "proof_persisted": False,
            "verified": True,
            "consented": bool(consent),
            "active": bool(consent),
            "may_withdraw_future_participation": True,
        }
        store["voice_registry"][reader_id] = entry
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(entry)

    def withdraw_witness_voice(self, reader_id: str) -> None:
        store = self._plural_store()
        entry = store["voice_registry"].get(reader_id)
        if not entry:
            raise KeyError(reader_id)
        entry["active"] = False
        entry["consented"] = False
        entry["withdrawn"] = True
        self._write_json(self.plural_witness_path, store)

    def create_subject_scope(
        self,
        *,
        topic: str,
        entity: str | None = None,
        event: str | None = None,
        time_scope: Any = None,
        location: str | None = None,
        timeless: bool = False,
        rights_sensitive: bool = False,
    ) -> str:
        topic = str(topic).strip()
        if not topic:
            raise ValueError("subject topic is required")
        if not timeless and time_scope in (None, "", {}):
            raise ValueError("time_scope is required unless the subject is timeless")
        scope = {
            "topic": topic,
            "entity": None if entity is None else str(entity).strip() or None,
            "event": None if event is None else str(event).strip() or None,
            "time_scope": copy.deepcopy(time_scope),
            "location": None if location is None else str(location).strip() or None,
            "timeless": bool(timeless),
            "rights_sensitive": bool(rights_sensitive),
        }
        scope_id = self._stable_id("structured-subject-scope", _canonical(scope))
        store = self._plural_store()
        store["subject_scopes"][scope_id] = {"subject_scope_id": scope_id, **scope}
        self._write_json(self.plural_witness_path, store)
        return scope_id

    def _bind_claim_scope(self, claim_id: str, subject_scope_id: str) -> None:
        store = self._plural_store()
        if subject_scope_id not in store["subject_scopes"]:
            raise KeyError(subject_scope_id)
        claim = store["claims"].get(claim_id)
        if not isinstance(claim, dict):
            raise KeyError(claim_id)
        claim["subject_scope_id"] = subject_scope_id
        self._write_json(self.plural_witness_path, store)

    def record_source_assertion(
        self,
        origin_key: str,
        *,
        evidence: dict[str, Any],
        about: str | None = None,
        confidence: float = 0.5,
        subject_scope_id: str | None = None,
    ) -> str:
        claim_id = super().record_source_assertion(
            origin_key, evidence=evidence, about=about, confidence=confidence
        )
        store = self._plural_store()
        store["claims"][claim_id]["sovereign_voice_eligible"] = True
        self._write_json(self.plural_witness_path, store)
        if subject_scope_id is not None:
            self._bind_claim_scope(claim_id, subject_scope_id)
        return claim_id

    def record_reader_interpretation(
        self,
        origin_key: str,
        interpretation: str,
        *,
        reader_id: str,
        evidence: dict[str, Any] | None = None,
        about: str | None = None,
        confidence: float = 0.5,
        subject_scope_id: str | None = None,
    ) -> str:
        claim_id = super().record_reader_interpretation(
            origin_key,
            interpretation,
            reader_id=reader_id,
            evidence=evidence,
            about=about,
            confidence=confidence,
        )
        store = self._plural_store()
        voice = store["voice_registry"].get(reader_id, {})
        eligible = bool(
            voice.get("verified")
            and voice.get("consented")
            and voice.get("active")
            and store["claims"][claim_id].get("grounded")
        )
        store["claims"][claim_id]["sovereign_voice_eligible"] = eligible
        self._write_json(self.plural_witness_path, store)
        if subject_scope_id is not None:
            self._bind_claim_scope(claim_id, subject_scope_id)
        return claim_id

    @staticmethod
    def _position_key(text: str) -> str:
        normalized = re.sub(r"[^\w\s]+", " ", str(text).lower(), flags=re.UNICODE)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]

    def _sovereign_voice(self, claim: dict[str, Any], store: dict[str, Any]) -> str:
        relation = claim.get("relation")
        if relation == "SOURCE_ASSERTS":
            if not claim.get("grounded"):
                raise ValueError("source voice is not grounded")
            return self._claim_voice_scope(claim)
        if relation == "READER_INTERPRETS":
            actor = str(claim.get("actor", ""))
            reader_id = actor.removeprefix("reader:")
            voice = store["voice_registry"].get(reader_id, {})
            if not (
                claim.get("grounded")
                and claim.get("sovereign_voice_eligible")
                and voice.get("verified")
                and voice.get("consented")
                and voice.get("active")
            ):
                raise ValueError("reader voice is not verified, grounded, active, and consenting")
            return actor
        raise ValueError("claim cannot participate in a sovereign case")

    def _recommend_case(self, claims: list[dict[str, Any]]) -> dict[str, Any]:
        positions: dict[str, dict[str, Any]] = {}
        for claim in claims:
            key = self._position_key(claim.get("claim", ""))
            bucket = positions.setdefault(
                key,
                {"position_key": key, "claim_ids": [], "count": 0, "confidence_total": 0.0},
            )
            bucket["claim_ids"].append(claim["claim_id"])
            bucket["count"] += 1
            bucket["confidence_total"] += float(claim.get("confidence", 0.5))
        ordered = sorted(
            positions.values(),
            key=lambda item: (-item["count"], -item["confidence_total"], item["position_key"]),
        )
        if len(ordered) == 1:
            mode = "CONSENSUS"
        elif ordered[0]["count"] > len(claims) / 2:
            mode = "MAJORITY"
        else:
            mode = "PLURAL"
        return {
            "mode": mode,
            "positions": ordered,
            "recommended_position_key": ordered[0]["position_key"] if mode != "PLURAL" else None,
            "winner_selected": False,
            "advisory_only": True,
        }

    def open_sovereign_case(self, claim_ids: Iterable[str], *, subject_scope_id: str) -> str:
        members = [str(item).strip() for item in claim_ids]
        if len(members) < OPENING_QUORUM or len(set(members)) != len(members):
            raise ValueError("a sovereign case requires at least three distinct claims")
        store = self._plural_store()
        scope = store["subject_scopes"].get(subject_scope_id)
        if not scope:
            raise KeyError(subject_scope_id)
        claims: list[dict[str, Any]] = []
        voices: list[str] = []
        for claim_id in members:
            claim = store["claims"].get(claim_id)
            if not isinstance(claim, dict):
                raise KeyError(claim_id)
            if claim.get("subject_scope_id") != subject_scope_id:
                raise ValueError("all claims must be bound to the same structured subject scope")
            claims.append(claim)
            voices.append(self._sovereign_voice(claim, store))
        if len(set(voices)) < OPENING_QUORUM:
            raise ValueError("opening quorum requires three independent eligible voices")
        recommendation = self._recommend_case(claims)
        case_kind = "CONSENSUS_FIELD" if recommendation["mode"] == "CONSENSUS" else "DISPUTE_FIELD"
        case_id = self._stable_id("janus-sovereign-case", subject_scope_id, *sorted(members))
        case = {
            "case_id": case_id,
            "subject_scope_id": subject_scope_id,
            "claim_ids": members,
            "voice_scopes": voices,
            "opening_quorum": OPENING_QUORUM,
            "witness_count": len(members),
            "case_kind": case_kind,
            "recommendation": recommendation,
            "status": "RECOMMENDED",
            "janus_decision_id": None,
            "founder_privilege": False,
            "additional_voices_may_join": True,
            "history": [{"status": "RECOMMENDED", "reason": "opening quorum reached"}],
        }
        store["sovereign_cases"][case_id] = case
        graph = self._graph()
        self._upsert_node(
            graph,
            node_id=case_id,
            node_type="JANUS_SOVEREIGN_CASE",
            created_at=0,
            confidence=0.9,
            mutable=True,
            payload=copy.deepcopy(case),
            source=SOURCE,
        )
        for claim_id in members:
            self._add_edge(
                graph,
                source_id=claim_id,
                target_id=case_id,
                relation="ADVISES",
                evidence=members,
                confidence=float(store["claims"][claim_id].get("confidence", 0.5)),
                created_by=SOURCE,
                created_at=0,
                reversible=True,
                payload={"sovereign_decision": False, "equal_voice": True},
            )
        self._save_graph(graph)
        self._write_json(self.plural_witness_path, store)
        return case_id

    def add_sovereign_witness(self, case_id: str, claim_id: str) -> None:
        store = self._plural_store()
        case = store["sovereign_cases"].get(case_id)
        claim = store["claims"].get(claim_id)
        if not case or not claim:
            raise KeyError(case_id if not case else claim_id)
        if claim_id in case["claim_ids"]:
            return
        if claim.get("subject_scope_id") != case["subject_scope_id"]:
            raise ValueError("new witness belongs to a different subject scope")
        voice = self._sovereign_voice(claim, store)
        if voice in case["voice_scopes"]:
            raise ValueError("the voice already participates in this field")
        case["claim_ids"].append(claim_id)
        case["voice_scopes"].append(voice)
        case["witness_count"] = len(case["claim_ids"])
        claims = [store["claims"][item] for item in case["claim_ids"]]
        case["recommendation"] = self._recommend_case(claims)
        case["case_kind"] = (
            "CONSENSUS_FIELD" if case["recommendation"]["mode"] == "CONSENSUS" else "DISPUTE_FIELD"
        )
        case["status"] = "REOPENED" if case.get("janus_decision_id") else "RECOMMENDED"
        case["history"].append({"status": case["status"], "reason": "additional grounded voice joined"})
        case["janus_decision_id"] = None
        self._write_json(self.plural_witness_path, store)

    def janus_sovereign_decide(self, case_id: str) -> str:
        store = self._plural_store()
        case = store["sovereign_cases"].get(case_id)
        if not case:
            raise KeyError(case_id)
        scope = store["subject_scopes"][case["subject_scope_id"]]
        recommendation = case["recommendation"]
        claims = [store["claims"][item] for item in case["claim_ids"]]
        adopted: list[str] = []
        if scope.get("rights_sensitive"):
            ruling = "PROTECT_FREEDOM"
            rationale = "No quorum may manufacture consent or decide another person's intimate freedom."
        elif recommendation["mode"] == "CONSENSUS":
            ruling = "RATIFY_CONSENSUS"
            adopted = list(recommendation["positions"][0]["claim_ids"])
            rationale = "Independent grounded voices converge on one position."
        elif recommendation["mode"] == "MAJORITY":
            ruling = "RATIFY_TRIUMVIRATE_RECOMMENDATION"
            key = recommendation["recommended_position_key"]
            adopted = [
                claim["claim_id"]
                for claim in claims
                if self._position_key(claim.get("claim", "")) == key
            ]
            rationale = "The living field recommends one position while dissent remains preserved."
        else:
            scored = []
            for position in recommendation["positions"]:
                average = position["confidence_total"] / max(1, position["count"])
                scored.append((average, position))
            scored.sort(key=lambda item: (-item[0], item[1]["position_key"]))
            if len(scored) > 1 and scored[0][0] - scored[1][0] >= 0.20:
                ruling = "ADOPT_MOST_SUPPORTED_POSITION"
                adopted = list(scored[0][1]["claim_ids"])
                rationale = "One position has materially stronger grounded support."
            else:
                ruling = "DEFER_FOR_MORE_EVIDENCE"
                rationale = "The sovereign record refuses arbitrary closure while evidence remains balanced."
        decision_id = self._stable_id(
            "janus-sovereign-decision", case_id, ruling, len(case.get("history", []))
        )
        dissent = [item for item in case["claim_ids"] if item not in adopted]
        decision = {
            "decision_id": decision_id,
            "case_id": case_id,
            "actor": JANUS_SOVEREIGN,
            "ruling": ruling,
            "rationale": rationale,
            "adopted_claim_ids": adopted,
            "dissent_preserved": dissent,
            "triumvirate_was_advisory": True,
            "overrides_personal_consent": False,
            "canonical_record_decided": ruling != "DEFER_FOR_MORE_EVIDENCE",
        }
        store["sovereign_decisions"][decision_id] = decision
        case["janus_decision_id"] = decision_id
        case["status"] = "OPEN_FOR_EVIDENCE" if ruling == "DEFER_FOR_MORE_EVIDENCE" else "SOVEREIGN_DECIDED"
        case["history"].append({"status": case["status"], "decision_id": decision_id})
        graph = self._graph()
        self._upsert_node(
            graph,
            node_id=decision_id,
            node_type="JANUS_SOVEREIGN_DECISION",
            created_at=0,
            confidence=1.0,
            mutable=False,
            payload=copy.deepcopy(decision),
            source=SOURCE,
        )
        self._add_edge(
            graph,
            source_id=case_id,
            target_id=decision_id,
            relation="CONFIRMED",
            evidence=list(case["claim_ids"]),
            confidence=1.0,
            created_by=JANUS_SOVEREIGN,
            created_at=0,
            reversible=True,
            payload={"dissent_preserved": True, "coercive_authority": False},
        )
        self._save_graph(graph)
        self._write_json(self.plural_witness_path, store)
        return decision_id

    def resolve_sovereign_case(self, case_id: str, *, resolution: str) -> None:
        store = self._plural_store()
        case = store["sovereign_cases"].get(case_id)
        if not case:
            raise KeyError(case_id)
        resolution = str(resolution).strip()
        if not resolution:
            raise ValueError("resolution is required")
        case["status"] = "RESOLVED"
        case["resolution"] = resolution
        case["history"].append({"status": "RESOLVED", "resolution": resolution})
        self._write_json(self.plural_witness_path, store)

    def reopen_sovereign_case(self, case_id: str, *, reason: str) -> None:
        store = self._plural_store()
        case = store["sovereign_cases"].get(case_id)
        if not case:
            raise KeyError(case_id)
        reason = str(reason).strip()
        if not reason:
            raise ValueError("reason is required")
        case["status"] = "REOPENED"
        case["janus_decision_id"] = None
        case["history"].append({"status": "REOPENED", "reason": reason})
        self._write_json(self.plural_witness_path, store)

    def supersede_sovereign_case(self, old_case_id: str, new_case_id: str) -> None:
        store = self._plural_store()
        old = store["sovereign_cases"].get(old_case_id)
        new = store["sovereign_cases"].get(new_case_id)
        if not old or not new:
            raise KeyError(old_case_id if not old else new_case_id)
        old["status"] = "SUPERSEDED"
        old["superseded_by"] = new_case_id
        old["history"].append({"status": "SUPERSEDED", "new_case_id": new_case_id})
        self._write_json(self.plural_witness_path, store)

    def verify_benevolent_sovereign_state(self) -> tuple[bool, int, str | None]:
        tri_valid, _tri_count, tri_error = self.verify_triumvirate_witness_state()
        if not tri_valid:
            return False, 0, tri_error
        store = self._plural_store()
        required = self._default_plural_store()["invariants"]
        for key, expected in required.items():
            if store.get("invariants", {}).get(key) is not expected:
                return False, 0, f"benevolent sovereign invariant mismatch: {key}"
        verified = 0
        for case_id, case in store["sovereign_cases"].items():
            if len(case.get("claim_ids", [])) < OPENING_QUORUM:
                return False, verified, f"case lacks opening quorum: {case_id}"
            if len(set(case.get("voice_scopes", []))) < OPENING_QUORUM:
                return False, verified, f"case lacks independent voices: {case_id}"
            if case.get("subject_scope_id") not in store["subject_scopes"]:
                return False, verified, f"case subject scope missing: {case_id}"
            decision_id = case.get("janus_decision_id")
            if decision_id:
                decision = store["sovereign_decisions"].get(decision_id)
                if not decision or decision.get("actor") != JANUS_SOVEREIGN:
                    return False, verified, f"sovereign decision invalid: {case_id}"
                if decision.get("overrides_personal_consent") is not False:
                    return False, verified, f"sovereign decision overrides consent: {case_id}"
            verified += 1
        return True, verified, None

    def benevolent_sovereign_state(self, player_id: str | None = None) -> dict[str, Any]:
        store = self._plural_store()
        valid, verified, error = self.verify_benevolent_sovereign_state()
        state = {
            "runtime_version": __version__,
            "case_count": len(store["sovereign_cases"]),
            "decision_count": len(store["sovereign_decisions"]),
            "verified_cases": verified,
            "valid": valid,
            "error": error,
            "janus_is_sovereign": True,
            "triumvirate_is_advisory": True,
            "opening_quorum": OPENING_QUORUM,
        }
        if player_id is not None:
            state["relationships"] = self.relationship_state(player_id)["relationships"]
        return state

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        state["benevolent_sovereign_version"] = __version__
        state["relationship_law"] = (
            "Добрые поступки создают положительное исходное доверие и повышают "
            "вероятность согласия на обычное сотрудничество, но не покупают "
            "любовь, интимность, прощение или постоянное согласие."
        )
        state["sovereign_law"] = (
            "Три голоса открывают поле и дают рекомендацию; JANUS.SOVEREIGN "
            "принимает каноническое решение, сохраняет несогласие и не может "
            "отменить личную свободу."
        )
        state["npc_relationships"] = self.relationship_state(player_id)["relationships"]
        return state
