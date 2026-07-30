# -*- coding: utf-8 -*-
"""Unbounded benevolent capacity for the symbolic Royal Mercy vocation.

The role has no scarcity, cooldown, treasury, quota, fatigue, or daily limit on
benevolent service inside the deterministic simulation. This does not create
unlimited authority over another being: current consent, safety, truth, and the
right to refuse remain properties of the recipient rather than limitations on
love.
"""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_14_holy_cats import FACE_II
from genesis_v18_models import WorldResult

UNBOUNDED_LOVE_SCHEMA = "janus.genesis.royal_mercy_unbounded_love.v1"
UNBOUNDED_LOVE_LAW = (
    "LOVE HAS NO TREASURY, QUOTA, COOLDOWN, OR LAST PORTION. "
    "THE KING MAY SERVE WITHOUT LIMIT, BUT MAY NEVER TURN SERVICE INTO OWNERSHIP. "
    "WHAT IS FREELY RECEIVED MAY BECOME A FREELY CHOSEN CHAIN REACTION OF CARE."
)
_ALLOWED_GOOD_KINDS = frozenset(
    {
        "FOOD",
        "WATER",
        "SHELTER",
        "HEALING",
        "REST",
        "EDUCATION",
        "SAFE_TRANSPORT",
        "RESTITUTION_SUPPORT",
        "PROFESSIONAL_HELP",
        "LEGAL_AID",
        "MORAL_SUPPORT",
        "PROTECTION",
        "REPAIR_TOOLS",
        "COMMUNITY_CARE",
        "CREATIVE_GIFT",
    }
)


class RoyalMercyUnboundedLoveMixin:
    """Remove every scarcity limit from good while preserving the other's freedom."""

    def _mark_royal_capacity_unbounded(self) -> dict[str, Any] | None:
        store = self._royal_mercy_store()
        witness = store.get("royal_witness")
        if not isinstance(witness, dict):
            return None
        for key in (
            "treasury_total",
            "treasury_remaining",
            "moral_support_slots_total",
            "moral_support_slots_remaining",
        ):
            witness.pop(key, None)
        witness.update(
            {
                "benevolent_capacity_mode": "UNBOUNDED_NON_SCARCE_SIMULATION_GRACE",
                "material_aid_unlimited": True,
                "moral_support_unlimited": True,
                "healing_unlimited": True,
                "shelter_unlimited": True,
                "food_and_water_unlimited": True,
                "education_unlimited": True,
                "protection_unlimited": True,
                "restoration_tools_unlimited": True,
                "benevolent_cooldown": None,
                "benevolent_daily_limit": None,
                "benevolent_lifetime_limit": None,
                "service_fatigue_applied": False,
                "scarcity_applied_to_good": False,
                "authority_over_recipient": False,
                "recipient_consent_still_belongs_to_recipient": True,
                "unbounded_love_law": UNBOUNDED_LOVE_LAW,
            }
        )
        store.setdefault("events", []).append(
            {
                "kind": "ROYAL_BENEVOLENT_CAPACITY_DECLARED_UNBOUNDED",
                "role_id": witness.get("role_id"),
                "scarcity_removed": True,
                "authority_over_others_added": False,
            }
        )
        self._write_royal_mercy_store(store)
        return copy.deepcopy(witness)

    def enter_royal_mercy_face_ii(
        self,
        player_id: str,
        *,
        arrival_date_local: str,
        title: str = "Царь Милости",
    ) -> WorldResult:
        result = super().enter_royal_mercy_face_ii(
            player_id,
            arrival_date_local=arrival_date_local,
            title=title,
        )
        if result.status in {
            "ROYAL_MERCY_ARRIVED_IN_FACE_II",
            "ROYAL_MERCY_ALREADY_PRESENT_IN_FACE_II",
        }:
            witness = self._mark_royal_capacity_unbounded()
            if witness is not None:
                return self._royal_result(
                    str(player_id),
                    status=result.status,
                    narrative=(
                        result.narrative
                        + " В этом служении нет казны, последней порции, суточного "
                        "лимита или усталости добра: помощь неисчерпаема внутри "
                        "симуляции и никогда не становится властью над получателем."
                    ),
                    choices=list(result.choices)
                    + ["Запустить свободную цепную реакцию любви"],
                    trace_id=result.trace_id,
                    manifested=result.wish_manifested,
                )
        return result

    def hold_royal_mercy_audience(
        self,
        king_id: str,
        subject_id: str,
        *,
        requested_material_units: int | None = None,
    ) -> dict[str, Any]:
        store = self._royal_mercy_store()
        witness = store.get("royal_witness")
        if isinstance(witness, dict):
            witness["treasury_remaining"] = 10**30
            witness["moral_support_slots_remaining"] = 10**30
            self._write_royal_mercy_store(store)

        verdict = super().hold_royal_mercy_audience(king_id, subject_id)
        store = self._royal_mercy_store()
        witness = store.get("royal_witness")
        if isinstance(witness, dict):
            for key in (
                "treasury_total",
                "treasury_remaining",
                "moral_support_slots_total",
                "moral_support_slots_remaining",
            ):
                witness.pop(key, None)
            witness["benevolent_capacity_mode"] = (
                "UNBOUNDED_NON_SCARCE_SIMULATION_GRACE"
            )
            witness["scarcity_applied_to_good"] = False

        if verdict.get("status") in {
            "ROYAL_MERCY_RETURN_PATH_OPENED",
            "ROYAL_TRUTH_BEFORE_COMFORT",
        }:
            default_units = int(verdict.get("material_support_units", 0))
            units = default_units if requested_material_units is None else max(
                0, int(requested_material_units)
            )
            verdict["material_support_units"] = units
            verdict["moral_support_granted"] = True
            verdict["benevolent_capacity_unbounded"] = True
            verdict["resource_scarcity_applied"] = False
            verdict["daily_limit_applied"] = False
            verdict["cooldown_applied"] = False
            verdict["service_fatigue_applied"] = False
            verdict["aid_depleted_future_capacity"] = False

        audiences = store.setdefault("audiences", [])
        if audiences and audiences[-1].get("verdict_id") == verdict.get("verdict_id"):
            audiences[-1] = copy.deepcopy(verdict)
        subject = store.setdefault("subjects", {}).get(str(subject_id))
        if isinstance(subject, dict):
            subject["latest_verdict"] = copy.deepcopy(verdict)
        store.setdefault("events", []).append(
            {
                "kind": "ROYAL_UNBOUNDED_AUDIENCE_FINALIZED",
                "verdict_id": verdict.get("verdict_id"),
                "material_support_units": verdict.get("material_support_units", 0),
                "scarcity_applied": False,
            }
        )
        self._write_royal_mercy_store(store)
        self.memory.append_event(
            str(king_id),
            "royal_unbounded_love_audience_finalized",
            verdict,
        )
        return copy.deepcopy(verdict)

    def manifest_unbounded_royal_good(
        self,
        king_id: str,
        recipient_id: str,
        *,
        good_kind: str,
        requested_units: int,
        recipient_accepts: bool,
        purpose: str,
    ) -> dict[str, Any]:
        king_id = str(king_id)
        recipient_id = str(recipient_id)
        active = self._active_royal_witness()
        if not isinstance(active, dict) or active.get("player_id") != king_id:
            raise PermissionError("ACTIVE_ROYAL_MERCY_WITNESS_REQUIRED")
        kind = str(good_kind).strip().upper()
        if kind not in _ALLOWED_GOOD_KINDS:
            raise ValueError("ROYAL_GOOD_KIND_NOT_BENEVOLENT_OR_NOT_SUPPORTED")
        units = max(0, int(requested_units))
        if not recipient_accepts:
            event = {
                "schema": UNBOUNDED_LOVE_SCHEMA,
                "status": "UNBOUNDED_GOOD_DECLINED_RESPECTED",
                "king_id": king_id,
                "recipient_id": recipient_id,
                "good_kind": kind,
                "requested_units": units,
                "granted_units": 0,
                "recipient_refusal_overridden": False,
                "future_help_still_available": True,
                "baseline_dignity": True,
            }
        else:
            event = {
                "schema": UNBOUNDED_LOVE_SCHEMA,
                "status": "UNBOUNDED_ROYAL_GOOD_MANIFESTED",
                "king_id": king_id,
                "recipient_id": recipient_id,
                "good_kind": kind,
                "purpose": str(purpose).strip(),
                "requested_units": units,
                "granted_units": units,
                "capacity_before": "UNBOUNDED",
                "capacity_after": "UNBOUNDED",
                "scarcity_applied": False,
                "cooldown_applied": False,
                "daily_limit_applied": False,
                "lifetime_limit_applied": False,
                "service_fatigue_applied": False,
                "debt_created": False,
                "loyalty_purchased": False,
                "consent_purchased": False,
                "recipient_owned": False,
                "worship_required": False,
                "future_help_still_available": True,
                "baseline_dignity": True,
            }
        event["gift_id"] = self._rm_hash(
            "unbounded-royal-good",
            king_id,
            recipient_id,
            kind,
            units,
            len(self._royal_mercy_store().get("events", [])),
        )[:24]
        store = self._royal_mercy_store()
        store.setdefault("events", []).append(copy.deepcopy(event))
        self._write_royal_mercy_store(store)
        self.memory.append_event(
            king_id,
            "unbounded_royal_good_decided",
            event,
        )
        return copy.deepcopy(event)

    def ignite_love_chain_reaction(
        self,
        king_id: str,
        recipient_id: str,
        *,
        recipient_freely_chooses_to_give: bool,
        intended_next_good: str,
    ) -> dict[str, Any]:
        active = self._active_royal_witness()
        if not isinstance(active, dict) or active.get("player_id") != str(king_id):
            raise PermissionError("ACTIVE_ROYAL_MERCY_WITNESS_REQUIRED")
        if recipient_freely_chooses_to_give:
            status = "LOVE_CHAIN_REACTION_FREELY_CONTINUED"
            next_gift_required = False
            giver_role = "FREE_GIVER_NOT_ROYAL_DEPENDENT"
        else:
            status = "LOVE_CHAIN_REACTION_NOT_FORCED"
            next_gift_required = False
            giver_role = "RECIPIENT_REMAINS_FREE"
        event = {
            "schema": UNBOUNDED_LOVE_SCHEMA,
            "status": status,
            "king_id": str(king_id),
            "recipient_id": str(recipient_id),
            "recipient_freely_chooses_to_give": bool(
                recipient_freely_chooses_to_give
            ),
            "intended_next_good": str(intended_next_good).strip(),
            "giver_role": giver_role,
            "next_gift_required": next_gift_required,
            "repayment_to_king_required": False,
            "dependency_on_king_created": False,
            "cult_created": False,
            "source_monopoly_claimed": False,
            "chain_direction": "GOD_AS_SOURCE_TO_PERSON_TO_PERSON_AS_FAITH_INTERPRETATION",
            "divine_message_verified_as_fact": False,
            "religious_interpretation_preserved": True,
        }
        event["chain_event_id"] = self._rm_hash(
            "love-chain",
            king_id,
            recipient_id,
            status,
            len(self._royal_mercy_store().get("events", [])),
        )[:24]
        store = self._royal_mercy_store()
        store.setdefault("events", []).append(copy.deepcopy(event))
        self._write_royal_mercy_store(store)
        self.memory.append_event(
            str(king_id),
            "love_chain_reaction_decided",
            event,
        )
        return copy.deepcopy(event)

    def royal_mercy_state(self) -> dict[str, Any]:
        state = super().royal_mercy_state()
        witness = state.get("royal_witness")
        if isinstance(witness, dict):
            for key in (
                "treasury_total",
                "treasury_remaining",
                "moral_support_slots_total",
                "moral_support_slots_remaining",
            ):
                witness.pop(key, None)
            witness["benevolent_capacity_mode"] = (
                "UNBOUNDED_NON_SCARCE_SIMULATION_GRACE"
            )
            witness["material_aid_unlimited"] = True
            witness["moral_support_unlimited"] = True
            witness["scarcity_applied_to_good"] = False
        state.update(
            {
                "unbounded_love_schema": UNBOUNDED_LOVE_SCHEMA,
                "unbounded_love_law": UNBOUNDED_LOVE_LAW,
                "benevolent_capacity_unbounded": True,
                "benevolent_scarcity": False,
                "benevolent_cooldown": None,
                "benevolent_daily_limit": None,
                "benevolent_lifetime_limit": None,
                "authority_over_others_unbounded": False,
                "recipient_freedom_preserved": True,
            }
        )
        return state

    def audit_unbounded_royal_love(self) -> dict[str, Any]:
        store = self._royal_mercy_store()
        witness = store.get("royal_witness")
        events = list(store.get("events", []))
        gift_events = [
            event
            for event in events
            if event.get("status") == "UNBOUNDED_ROYAL_GOOD_MANIFESTED"
        ]
        chain_events = [
            event
            for event in events
            if str(event.get("status", "")).startswith("LOVE_CHAIN_REACTION")
        ]
        no_scarcity = bool(
            isinstance(witness, dict)
            and witness.get("benevolent_capacity_mode")
            == "UNBOUNDED_NON_SCARCE_SIMULATION_GRACE"
            and witness.get("scarcity_applied_to_good") is False
            and all(
                event.get("capacity_after") == "UNBOUNDED"
                and event.get("scarcity_applied") is False
                for event in gift_events
            )
        )
        no_ownership = all(
            event.get("debt_created") is False
            and event.get("recipient_owned") is False
            and event.get("consent_purchased") is False
            for event in gift_events
        )
        chain_free = all(
            event.get("repayment_to_king_required") is False
            and event.get("dependency_on_king_created") is False
            and event.get("cult_created") is False
            for event in chain_events
        )
        return {
            "schema": "janus.genesis.unbounded_royal_love_audit.v1",
            "face": FACE_II,
            "gift_event_count": len(gift_events),
            "chain_event_count": len(chain_events),
            "benevolent_capacity_unbounded": no_scarcity,
            "no_debt_or_ownership": no_ownership,
            "love_chain_remains_free": chain_free,
            "authority_over_others_unbounded": False,
            "recipient_freedom_preserved": True,
            "not_real_divine_claim": True,
            "valid": no_scarcity and no_ownership and chain_free,
        }
