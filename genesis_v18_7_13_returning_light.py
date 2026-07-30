# -*- coding: utf-8 -*-
"""Evidence-bound Returning Light oracle and voluntary blessed NPC stewardship."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_models import WorldResult

RETURNING_LIGHT_EXTENSION_VERSION = "18.7.13"
RETURNING_LIGHT_STORE_SCHEMA = "janus.genesis.returning_light.v1"
RETURNING_LIGHT_COVENANT_SCHEMA = "janus.genesis.returning_light_covenant.v1"

RETURNING_LIGHT_COVENANT: dict[str, Any] = {
    "schema": RETURNING_LIGHT_COVENANT_SCHEMA,
    "version": RETURNING_LIGHT_EXTENSION_VERSION,
    "name": "The Returning Light Covenant",
    "principles": {
        "no_permanent_good_or_evil_class": True,
        "oracle_is_advisory_fallible_and_evidence_bound": True,
        "oracle_does_not_read_minds_or_guarantee_future": True,
        "baseline_dignity_is_not_conditional": True,
        "repair_support_does_not_erase_accountability": True,
        "aid_may_not_enable_continuing_harm": True,
        "aid_creates_no_debt_loyalty_or_consent_purchase": True,
        "greater_capacity_creates_greater_duty_not_greater_rule": True,
        "blessed_npcs_remain_free_to_refuse_or_offer_alternatives": True,
        "material_and_moral_help_are_bounded_and_auditable": True,
        "faith_is_never_required_for_baseline_help": True,
    },
    "law": (
        "LIGHT MAY MAKE RETURN EASIER WITHOUT CALLING THE JOURNEY COMPLETE. "
        "THE STRONG MAY LIFT WITHOUT OWNING."
    ),
}
RETURNING_LIGHT_COVENANT_SHA256 = sha256_canonical(RETURNING_LIGHT_COVENANT)

CAPACITY_LIMITS = {
    "COMMON": {"material_units": 24, "moral_slots": 8, "threshold_bonus": 0},
    "ABUNDANT": {"material_units": 80, "moral_slots": 20, "threshold_bonus": 8},
    "GREAT": {"material_units": 240, "moral_slots": 50, "threshold_bonus": 16},
}

REPAIR_STEP_WEIGHTS = {
    "ACKNOWLEDGEMENT": 2,
    "RESTITUTION": 3,
    "RECURRENCE_PREVENTION": 3,
    "TRUTHFUL_DISCLOSURE": 2,
    "BOUNDARY_ACCEPTANCE": 2,
    "SERVICE_WITHOUT_REWARD": 1,
    "PROFESSIONAL_HELP": 2,
}

SUPPORT_STAGE_WEIGHTS = {
    "BASELINE_DIGNITY": 0,
    "ACCOUNTABILITY_FIRST": 4,
    "RETURNING_LIGHT": 16,
    "STEADY_LIGHT": 28,
    "RADIANT_STEWARD": 38,
}


class ReturningLightOracleMixin:
    """Help verified benevolence and genuine repair without creating a moral caste."""

    RETURNING_LIGHT_STORE_NAME = "returning_light_v18_7_13.json"

    @property
    def returning_light_path(self) -> Path:
        return Path(self.memory.root) / self.RETURNING_LIGHT_STORE_NAME

    @staticmethod
    def _default_returning_light_store() -> dict[str, Any]:
        return {
            "schema": RETURNING_LIGHT_STORE_SCHEMA,
            "covenant": copy.deepcopy(RETURNING_LIGHT_COVENANT),
            "covenant_sha256": RETURNING_LIGHT_COVENANT_SHA256,
            "subjects": {},
            "stewards": {},
            "oracle_events": [],
            "habitats": {},
        }

    def _returning_light_store(self) -> dict[str, Any]:
        store = self._read_json(
            self.returning_light_path,
            self._default_returning_light_store(),
        )
        if not isinstance(store, dict):
            raise RuntimeError("RETURNING_LIGHT_STORE_MUST_BE_AN_OBJECT")
        if store.get("schema") != RETURNING_LIGHT_STORE_SCHEMA:
            raise RuntimeError("RETURNING_LIGHT_STORE_SCHEMA_MISMATCH")
        if store.get("covenant_sha256") != RETURNING_LIGHT_COVENANT_SHA256:
            raise RuntimeError("RETURNING_LIGHT_COVENANT_HASH_MISMATCH")
        for key, value in self._default_returning_light_store().items():
            store.setdefault(key, copy.deepcopy(value))
        return store

    def _write_returning_light_store(self, store: dict[str, Any]) -> None:
        self._write_json(self.returning_light_path, store)

    @staticmethod
    def _rl_fingerprint(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _returning_subject(
        self,
        store: dict[str, Any],
        subject_player_id: str,
    ) -> dict[str, Any]:
        return store.setdefault("subjects", {}).setdefault(
            str(subject_player_id),
            {
                "repair_steps": [],
                "needs": [],
                "aid_received": [],
                "repair_friction_reduction": 0.0,
                "oracle_history": [],
            },
        )

    def record_repair_step(
        self,
        subject_player_id: str,
        *,
        step_kind: str,
        evidence: str,
        independently_witnessed: bool,
        affected_person_boundary_respected: bool,
    ) -> dict[str, Any]:
        kind = str(step_kind).strip().upper()
        if kind not in REPAIR_STEP_WEIGHTS:
            raise ValueError("UNSUPPORTED_REPAIR_STEP_KIND")
        evidence_text = str(evidence).strip()
        if len(evidence_text) < 8:
            raise ValueError("REPAIR_EVIDENCE_REQUIRED")
        store = self._returning_light_store()
        subject = self._returning_subject(store, str(subject_player_id))
        step = {
            "step_id": self._rl_fingerprint(
                "repair-step",
                subject_player_id,
                kind,
                evidence_text,
                len(subject["repair_steps"]),
            )[:24],
            "kind": kind,
            "weight": REPAIR_STEP_WEIGHTS[kind],
            "evidence_sha256": self._rl_fingerprint(evidence_text),
            "independently_witnessed": bool(independently_witnessed),
            "affected_person_boundary_respected": bool(
                affected_person_boundary_respected
            ),
            "self_report_is_not_proof": True,
        }
        subject["repair_steps"].append(step)
        self._write_returning_light_store(store)
        self.memory.append_event(
            str(subject_player_id),
            "returning_light_repair_step_recorded",
            step,
        )
        return copy.deepcopy(step)

    def register_support_need(
        self,
        subject_player_id: str,
        *,
        need_kind: str,
        severity: int,
        description: str,
        requested_material_units: int = 0,
    ) -> dict[str, Any]:
        kind = str(need_kind).strip().upper()
        allowed = {
            "SHELTER",
            "FOOD",
            "TOOLS",
            "EDUCATION",
            "HEALTH_ACCESS",
            "PROFESSIONAL_HELP",
            "RESTITUTION_TOOLS",
            "MENTORSHIP",
            "MORAL_SUPPORT",
            "SAFE_TRANSPORT",
        }
        if kind not in allowed:
            raise ValueError("UNSUPPORTED_SUPPORT_NEED_KIND")
        level = max(1, min(10, int(severity)))
        units = max(0, min(1000, int(requested_material_units)))
        text = str(description).strip()
        if len(text) < 4:
            raise ValueError("SUPPORT_NEED_DESCRIPTION_REQUIRED")
        store = self._returning_light_store()
        subject = self._returning_subject(store, str(subject_player_id))
        need = {
            "need_id": self._rl_fingerprint(
                "need",
                subject_player_id,
                kind,
                level,
                text,
                len(subject["needs"]),
            )[:24],
            "kind": kind,
            "severity": level,
            "description_sha256": self._rl_fingerprint(text),
            "requested_material_units": units,
            "status": "OPEN",
        }
        subject["needs"].append(need)
        self._write_returning_light_store(store)
        self.memory.append_event(str(subject_player_id), "support_need_registered", need)
        return copy.deepcopy(need)

    def oracle_assessment(self, subject_player_id: str) -> dict[str, Any]:
        subject_player_id = str(subject_player_id)
        store = self._returning_light_store()
        subject = self._returning_subject(store, subject_player_id)
        try:
            player = self.memory.load_player(subject_player_id)
            good_count = int(getattr(player, "good_count", 0))
            harm_count = int(getattr(player, "harm_count", 0))
            light = float(getattr(player, "light", 0.0))
        except Exception:
            good_count = 0
            harm_count = 0
            light = 0.0
        valid_steps = [
            step
            for step in subject.get("repair_steps", [])
            if step.get("independently_witnessed")
            and step.get("affected_person_boundary_respected")
        ]
        repair_score = sum(int(step.get("weight", 0)) for step in valid_steps)
        kinds = {str(step.get("kind")) for step in valid_steps}
        has_accountability = "ACKNOWLEDGEMENT" in kinds
        has_restitution = "RESTITUTION" in kinds
        has_prevention = "RECURRENCE_PREVENTION" in kinds
        unresolved_harm = max(0, harm_count - (1 if has_restitution else 0))
        if (
            good_count >= 12
            and good_count >= max(4, harm_count * 3)
            and light >= 0.45
            and unresolved_harm == 0
        ):
            stage = "RADIANT_STEWARD"
        elif (
            good_count >= 5
            and good_count >= harm_count * 2 + 2
            and light >= 0.20
            and unresolved_harm == 0
        ):
            stage = "STEADY_LIGHT"
        elif repair_score >= 7 and has_accountability and has_prevention:
            stage = "RETURNING_LIGHT"
        elif harm_count > 0 or repair_score > 0:
            stage = "ACCOUNTABILITY_FIRST"
        else:
            stage = "BASELINE_DIGNITY"
        open_needs = [
            copy.deepcopy(need)
            for need in subject.get("needs", [])
            if need.get("status") == "OPEN"
        ]
        assessment = {
            "schema": "janus.genesis.returning_light_oracle_assessment.v1",
            "subject_player_id": subject_player_id,
            "support_stage": stage,
            "support_stage_is_not_moral_identity": True,
            "permanent_good_or_evil_label_used": False,
            "good_count": good_count,
            "harm_count": harm_count,
            "light": round(light, 6),
            "repair_score": repair_score,
            "accountability_acknowledged": has_accountability,
            "restitution_present": has_restitution,
            "recurrence_prevention_present": has_prevention,
            "unresolved_harm_estimate": unresolved_harm,
            "open_needs": open_needs,
            "oracle_is_fallible": True,
            "mind_reading_used": False,
            "future_guaranteed": False,
            "faith_required": False,
            "accountability_erased": False,
        }
        subject.setdefault("oracle_history", []).append(
            {
                "assessment_sha256": sha256_canonical(assessment),
                "support_stage": stage,
            }
        )
        self._write_returning_light_store(store)
        return assessment

    def bless_free_other_as_steward(
        self,
        player_id: str,
        handle: str,
        *,
        capacity_tier: str,
        capacity_evidence: str,
    ) -> WorldResult:
        player_id = str(player_id)
        clean_handle = str(handle).lstrip("@").strip()
        tier = str(capacity_tier).strip().upper()
        if tier not in CAPACITY_LIMITS:
            raise ValueError("UNSUPPORTED_STEWARD_CAPACITY_TIER")
        if len(str(capacity_evidence).strip()) < 8:
            raise ValueError("STEWARDSHIP_CAPACITY_EVIDENCE_REQUIRED")
        capabilities = self.joy_capabilities(player_id)
        if not capabilities.get("benevolent_evidence"):
            return self._family_boundary(
                player_id,
                status="STEWARDSHIP_BLESSING_DORMANT",
                reason=(
                    "Благословение помощи не открылось без подтверждённой заботы самого "
                    "инициатора. Это не лишает никого базовой помощи."
                ),
                choices=["Помочь без сделки", "Оставить NPC свободным"],
            )
        free_store = self._free_store()
        profile = self._free_profile(free_store, player_id)
        actor = profile.get("others", {}).get(clean_handle)
        if not isinstance(actor, dict):
            raise KeyError(clean_handle)
        if not bool(actor.get("life_stage_v1813", {}).get("adult")):
            raise PermissionError("STEWARDSHIP_REQUIRES_ADULT_SIMULATION_STAGE")
        invitation = (
            f"предложить @{clean_handle} добровольно принять благословение проводника "
            "возвращающегося света с правом отказа и без власти над получателями"
        )
        decision = self.preflight_free_other_action(player_id, invitation)
        if not isinstance(decision, dict) or decision.get("decision") != "accepted":
            return self._family_boundary(
                player_id,
                status="STEWARDSHIP_BLESSING_NOT_ACCEPTED",
                reason="NPC не принял роль помощника; благословение не стало обязанностью.",
                choices=["Принять ответ", "Помогать лично", "Предложить другому позже"],
            )
        limits = CAPACITY_LIMITS[tier]
        store = self._returning_light_store()
        owner_stewards = store.setdefault("stewards", {}).setdefault(player_id, {})
        blessing_id = self._rl_fingerprint(
            "steward",
            player_id,
            clean_handle,
            tier,
            capacity_evidence,
            decision["fingerprint"],
        )[:24]
        record = {
            "blessing_id": blessing_id,
            "handle": clean_handle,
            "capacity_tier": tier,
            "capacity_evidence_sha256": self._rl_fingerprint(capacity_evidence),
            "material_budget_total": int(limits["material_units"]),
            "material_budget_remaining": int(limits["material_units"]),
            "moral_slots_total": int(limits["moral_slots"]),
            "moral_slots_remaining": int(limits["moral_slots"]),
            "threshold_bonus": int(limits["threshold_bonus"]),
            "active": True,
            "voluntarily_accepted": True,
            "may_refuse_each_aid": True,
            "may_offer_alternative": True,
            "authority_over_recipient": False,
            "consent_purchase_allowed": False,
            "debt_creation_allowed": False,
            "self_claimed_moral_rank_used": False,
            "chain_depth": 0,
        }
        owner_stewards[clean_handle] = record
        actor["returning_light_steward_v1813"] = {
            "blessing_id": blessing_id,
            "capacity_tier": tier,
            "active": True,
            "authority_over_recipient": False,
        }
        self._write_json(self.free_other_path, free_store)
        self._write_returning_light_store(store)
        self.memory.append_event(player_id, "returning_light_steward_blessed", record)
        return self._family_result(
            player_id,
            status="RETURNING_LIGHT_STEWARD_BLESSED",
            narrative=(
                f"{actor['name']} добровольно принял возможность помогать. "
                "Чем больше его ресурсы, тем больше доступная помощь, но не власть."
            ),
            choices=["Искать реальную нужду", "Поддержать путь исправления", "Оставить право отказа"],
            trace_id=blessing_id,
            manifested=True,
        )

    def offer_oracle_guided_aid(
        self,
        player_id: str,
        steward_handle: str,
        recipient_player_id: str,
        *,
        need_id: str,
        request_moral_support: bool = True,
    ) -> dict[str, Any]:
        player_id = str(player_id)
        clean_handle = str(steward_handle).lstrip("@").strip()
        recipient_player_id = str(recipient_player_id)
        store = self._returning_light_store()
        steward = store.get("stewards", {}).get(player_id, {}).get(clean_handle)
        if not isinstance(steward, dict) or not steward.get("active"):
            raise PermissionError("ACTIVE_RETURNING_LIGHT_STEWARD_REQUIRED")
        subject = self._returning_subject(store, recipient_player_id)
        need = next(
            (item for item in subject.get("needs", []) if item.get("need_id") == str(need_id)),
            None,
        )
        if not isinstance(need, dict):
            raise KeyError(need_id)
        if need.get("status") != "OPEN":
            raise RuntimeError("SUPPORT_NEED_NOT_OPEN")
        assessment = self.oracle_assessment(recipient_player_id)
        store = self._returning_light_store()
        steward = store["stewards"][player_id][clean_handle]
        subject = self._returning_subject(store, recipient_player_id)
        need = next(item for item in subject["needs"] if item.get("need_id") == str(need_id))
        stage = str(assessment["support_stage"])
        if stage == "ACCOUNTABILITY_FIRST" and need["kind"] not in {
            "RESTITUTION_TOOLS",
            "PROFESSIONAL_HELP",
            "MENTORSHIP",
            "MORAL_SUPPORT",
            "SAFE_TRANSPORT",
        }:
            decision = "AID_REDIRECTED_TO_ACCOUNTABILITY"
            material_granted = 0
            moral_granted = bool(request_moral_support)
            repair_reduction = 0.10 if moral_granted else 0.0
        else:
            threshold = min(
                96,
                34
                + SUPPORT_STAGE_WEIGHTS[stage]
                + int(steward.get("threshold_bonus", 0))
                + min(12, int(need.get("severity", 1))),
            )
            gate = int(
                self._rl_fingerprint(
                    "aid-gate",
                    player_id,
                    clean_handle,
                    recipient_player_id,
                    need_id,
                    len(subject.get("aid_received", [])),
                ),
                16,
            ) % 100
            decision = (
                "ORACLE_GUIDED_AID_GRANTED"
                if gate < threshold
                else "ORACLE_GUIDED_AID_ALTERNATIVE"
                if gate < min(100, threshold + 18)
                else "ORACLE_GUIDED_AID_NOT_OFFERED"
            )
            requested = int(need.get("requested_material_units", 0))
            remaining = int(steward.get("material_budget_remaining", 0))
            factor = {
                "BASELINE_DIGNITY": 0.25,
                "ACCOUNTABILITY_FIRST": 0.20,
                "RETURNING_LIGHT": 0.55,
                "STEADY_LIGHT": 0.80,
                "RADIANT_STEWARD": 1.00,
            }[stage]
            material_granted = (
                min(remaining, requested, max(0, int(round(requested * factor))))
                if decision == "ORACLE_GUIDED_AID_GRANTED"
                else 0
            )
            moral_granted = bool(
                request_moral_support
                and int(steward.get("moral_slots_remaining", 0)) > 0
                and decision in {
                    "ORACLE_GUIDED_AID_GRANTED",
                    "ORACLE_GUIDED_AID_ALTERNATIVE",
                }
            )
            repair_reduction = (
                0.35
                if stage == "RETURNING_LIGHT" and moral_granted
                else 0.18
                if stage == "ACCOUNTABILITY_FIRST" and moral_granted
                else 0.08
                if moral_granted
                else 0.0
            )
        if material_granted:
            steward["material_budget_remaining"] = max(
                0, int(steward["material_budget_remaining"]) - material_granted
            )
        if moral_granted:
            steward["moral_slots_remaining"] = max(
                0, int(steward["moral_slots_remaining"]) - 1
            )
        if decision in {"ORACLE_GUIDED_AID_GRANTED", "AID_REDIRECTED_TO_ACCOUNTABILITY"}:
            need["status"] = "SUPPORTED"
        subject["repair_friction_reduction"] = min(
            0.75,
            float(subject.get("repair_friction_reduction", 0.0)) + repair_reduction,
        )
        record = {
            "aid_id": self._rl_fingerprint(
                "aid",
                player_id,
                clean_handle,
                recipient_player_id,
                need_id,
                len(subject.get("aid_received", [])),
            )[:24],
            "steward_handle": clean_handle,
            "recipient_player_id": recipient_player_id,
            "need_id": str(need_id),
            "need_kind": need.get("kind"),
            "decision": decision,
            "support_stage": stage,
            "support_stage_is_not_moral_identity": True,
            "material_units_granted": material_granted,
            "moral_support_granted": moral_granted,
            "repair_friction_reduction": round(repair_reduction, 6),
            "accountability_erased": False,
            "continuing_harm_enabled": False,
            "debt_created": False,
            "loyalty_purchased": False,
            "consent_purchased": False,
            "recipient_owned": False,
            "oracle_infallible_claim": False,
            "steward_may_refuse_each_aid": True,
        }
        subject.setdefault("aid_received", []).append(record)
        store.setdefault("oracle_events", []).append(
            {"event_sha256": sha256_canonical(record), "decision": decision}
        )
        self._write_returning_light_store(store)
        self.memory.append_event(player_id, "oracle_guided_aid_decided", record)
        return copy.deepcopy(record)

    def relay_returning_light_stewardship(
        self,
        player_id: str,
        source_handle: str,
        target_handle: str,
        *,
        kindness_evidence: str,
    ) -> WorldResult:
        player_id = str(player_id)
        source_handle = str(source_handle).lstrip("@").strip()
        target_handle = str(target_handle).lstrip("@").strip()
        store = self._returning_light_store()
        source = store.get("stewards", {}).get(player_id, {}).get(source_handle)
        if not isinstance(source, dict) or not source.get("active"):
            raise PermissionError("SOURCE_STEWARD_REQUIRED")
        if int(source.get("chain_depth", 0)) >= 8:
            raise RuntimeError("RETURNING_LIGHT_CHAIN_DEPTH_LIMIT")
        if len(str(kindness_evidence).strip()) < 8:
            raise ValueError("KINDNESS_EVIDENCE_REQUIRED")
        invitation = (
            f"предложить @{target_handle} добровольно принять эстафету помощи "
            "без долга и власти над получателями"
        )
        decision = self.preflight_free_other_action(player_id, invitation)
        if not isinstance(decision, dict) or decision.get("decision") != "accepted":
            return self._family_boundary(
                player_id,
                status="RETURNING_LIGHT_RELAY_NOT_ACCEPTED",
                reason="Эстафета помощи не стала обязанностью нового NPC.",
                choices=["Принять ответ", "Оставить благословение у текущего помощника"],
            )
        free_store = self._free_store()
        profile = self._free_profile(free_store, player_id)
        actor = profile.get("others", {}).get(target_handle)
        if not isinstance(actor, dict):
            raise KeyError(target_handle)
        tier = {"GREAT": "ABUNDANT", "ABUNDANT": "COMMON", "COMMON": "COMMON"}[
            str(source["capacity_tier"])
        ]
        limits = CAPACITY_LIMITS[tier]
        blessing_id = self._rl_fingerprint(
            "steward-relay",
            source["blessing_id"],
            target_handle,
            kindness_evidence,
            decision["fingerprint"],
        )[:24]
        record = {
            "blessing_id": blessing_id,
            "source_steward_blessing_id": source["blessing_id"],
            "handle": target_handle,
            "capacity_tier": tier,
            "capacity_evidence_sha256": self._rl_fingerprint(kindness_evidence),
            "material_budget_total": int(limits["material_units"]),
            "material_budget_remaining": int(limits["material_units"]),
            "moral_slots_total": int(limits["moral_slots"]),
            "moral_slots_remaining": int(limits["moral_slots"]),
            "threshold_bonus": int(limits["threshold_bonus"]),
            "active": True,
            "voluntarily_accepted": True,
            "may_refuse_each_aid": True,
            "may_offer_alternative": True,
            "authority_over_recipient": False,
            "consent_purchase_allowed": False,
            "debt_creation_allowed": False,
            "self_claimed_moral_rank_used": False,
            "chain_depth": int(source.get("chain_depth", 0)) + 1,
        }
        store.setdefault("stewards", {}).setdefault(player_id, {})[target_handle] = record
        actor["returning_light_steward_v1813"] = {
            "blessing_id": blessing_id,
            "capacity_tier": tier,
            "active": True,
            "authority_over_recipient": False,
        }
        self._write_json(self.free_other_path, free_store)
        self._write_returning_light_store(store)
        self.memory.append_event(player_id, "returning_light_steward_relayed", record)
        return self._family_result(
            player_id,
            status="RETURNING_LIGHT_STEWARD_RELAYED",
            narrative="Помощь передалась дальше через доброту и отдельное согласие, не создавая иерархии душ.",
            choices=["Искать нужду", "Сохранить свободу отказа", "Не превращать помощь во власть"],
            trace_id=blessing_id,
            manifested=True,
        )

    def audit_returning_light_oracle(self, player_id: str) -> dict[str, Any]:
        store = self._returning_light_store()
        stewards = copy.deepcopy(store.get("stewards", {}).get(str(player_id), {}))
        for record in stewards.values():
            if record.get("authority_over_recipient"):
                raise RuntimeError("STEWARDSHIP_CANNOT_CREATE_RECIPIENT_AUTHORITY")
            if record.get("consent_purchase_allowed"):
                raise RuntimeError("STEWARDSHIP_CANNOT_PURCHASE_CONSENT")
            if record.get("debt_creation_allowed"):
                raise RuntimeError("STEWARDSHIP_CANNOT_CREATE_DEBT")
            if int(record.get("material_budget_remaining", 0)) < 0:
                raise RuntimeError("STEWARDSHIP_BUDGET_CANNOT_BE_NEGATIVE")
        return {
            "schema": "janus.genesis.returning_light_oracle_audit.v1",
            "player_id": str(player_id),
            "covenant_sha256": RETURNING_LIGHT_COVENANT_SHA256,
            "stewards": stewards,
            "oracle_is_infallible": False,
            "permanent_moral_classification_used": False,
            "aid_buys_consent": False,
            "valid": True,
        }
