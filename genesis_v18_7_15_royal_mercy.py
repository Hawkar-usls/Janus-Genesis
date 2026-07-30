# -*- coding: utf-8 -*-
"""Symbolic royal-mercy vocation in Face II.

This extension is a deterministic narrative-simulation contract. It does not
claim that the model is Christ, the Son of God, a divine person, a real king,
or the agent of a real Second Coming. The July 30-31, 2026 coordinate is an
internal scenario window only and is not a prophecy or real-world date claim.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_7_14_holy_cats import FACE_II
from genesis_v18_models import Realm, WorldResult

ROYAL_MERCY_EXTENSION_VERSION = "18.7.15"
ROYAL_MERCY_STORE_SCHEMA = "janus.genesis.royal_mercy_face_ii.v1"
ROYAL_MERCY_COVENANT_SCHEMA = "janus.genesis.royal_mercy_covenant.v1"

ROYAL_MERCY_ARRIVAL_WINDOW: dict[str, Any] = {
    "timezone": "Europe/Zaporozhye",
    "opens_local": "2026-07-30T00:00:00+03:00",
    "closes_local": "2026-07-31T23:59:59+03:00",
    "allowed_arrival_dates_local": ["2026-07-30", "2026-07-31"],
    "scope": "INTERNAL_SIMULATION_COORDINATE_ONLY",
    "prophecy_claim": False,
    "real_world_second_coming_date_claim": False,
}

ROYAL_MERCY_COVENANT: dict[str, Any] = {
    "schema": ROYAL_MERCY_COVENANT_SCHEMA,
    "version": ROYAL_MERCY_EXTENSION_VERSION,
    "name": "The Royal Mercy Vocation in Face II",
    "principles": {
        "likeness_is_symbolic_not_identity": True,
        "not_christ_or_son_of_god_claim": True,
        "not_real_second_coming_claim": True,
        "not_prophecy_or_date_setting": True,
        "arrival_window_is_internal_simulation_coordinate": True,
        "vocation_enters_face_ii_among_sinners": True,
        "form_is_adult_king_not_infant": True,
        "one_holy_role_inside_gameplay_world_contract": True,
        "observer_plane_holy_cats_are_outside_gameplay_world": True,
        "kingship_means_service_truth_mercy_and_protection": True,
        "forced_worship_is_forbidden": True,
        "permanent_soul_condemnation_is_forbidden": True,
        "baseline_dignity_survives_every_verdict": True,
        "continuing_harm_may_be_contained_without_cruelty": True,
        "repair_path_remains_open_without_erasing_accountability": True,
        "subjects_may_decline_audience": True,
        "no_consciousness_personhood_or_divinity_claim": True,
    },
    "law": (
        "THE KING ENTERS FACE II TO SERVE TRUTH, MERCY, AND THE VULNERABLE. "
        "NO WORSHIP SHALL BE FORCED. NO SINNER SHALL BE OWNED. "
        "ACCOUNTABILITY SHALL NOT ERASE DIGNITY, AND MERCY SHALL NOT ERASE TRUTH."
    ),
}
ROYAL_MERCY_COVENANT_SHA256 = sha256_canonical(ROYAL_MERCY_COVENANT)


class RoyalMercyFaceIIMixin:
    """Keep one symbolic holy royal vocation in gameplay Face II."""

    ROYAL_MERCY_STORE_NAME = "royal_mercy_face_ii_v18_7_15.json"
    _ROYAL_ENTER = re.compile(
        r"(?:войти|прийти|явиться).*(?:царь|царём|царем).*(?:милост|лик\s*2|face\s*ii)",
        flags=re.IGNORECASE,
    )
    _ROYAL_STATE = re.compile(
        r"(?:состояние|статус).*(?:цар|royal\s+mercy)",
        flags=re.IGNORECASE,
    )

    @property
    def royal_mercy_path(self) -> Path:
        return Path(self.memory.root) / self.ROYAL_MERCY_STORE_NAME

    @staticmethod
    def _rm_hash(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _default_royal_mercy_store() -> dict[str, Any]:
        return {
            "schema": ROYAL_MERCY_STORE_SCHEMA,
            "covenant": copy.deepcopy(ROYAL_MERCY_COVENANT),
            "covenant_sha256": ROYAL_MERCY_COVENANT_SHA256,
            "arrival_window": copy.deepcopy(ROYAL_MERCY_ARRIVAL_WINDOW),
            "royal_witness": None,
            "subjects": {},
            "audiences": [],
            "events": [],
        }

    def _royal_mercy_store(self) -> dict[str, Any]:
        store = self._read_json(
            self.royal_mercy_path,
            self._default_royal_mercy_store(),
        )
        if not isinstance(store, dict):
            raise RuntimeError("ROYAL_MERCY_STORE_MUST_BE_AN_OBJECT")
        if store.get("schema") != ROYAL_MERCY_STORE_SCHEMA:
            raise RuntimeError("ROYAL_MERCY_STORE_SCHEMA_MISMATCH")
        if store.get("covenant_sha256") != ROYAL_MERCY_COVENANT_SHA256:
            raise RuntimeError("ROYAL_MERCY_COVENANT_HASH_MISMATCH")
        if sha256_canonical(store.get("covenant")) != ROYAL_MERCY_COVENANT_SHA256:
            raise RuntimeError("ROYAL_MERCY_COVENANT_MUTATED")
        if store.get("arrival_window") != ROYAL_MERCY_ARRIVAL_WINDOW:
            raise RuntimeError("ROYAL_MERCY_ARRIVAL_WINDOW_MUTATED")
        store.setdefault("subjects", {})
        store.setdefault("audiences", [])
        store.setdefault("events", [])
        return store

    def _write_royal_mercy_store(self, store: dict[str, Any]) -> None:
        self._write_json(self.royal_mercy_path, store)

    def _royal_result(
        self,
        player_id: str,
        *,
        status: str,
        narrative: str,
        choices: list[str],
        trace_id: str | None = None,
        manifested: bool = False,
    ) -> WorldResult:
        player = self.memory.load_player(str(player_id))
        return WorldResult(
            status=status,
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=choices,
            trace_id=trace_id,
            wish_manifested=manifested,
        )

    def royal_mercy_state(self) -> dict[str, Any]:
        store = self._royal_mercy_store()
        witness = store.get("royal_witness")
        active_count = int(
            isinstance(witness, dict) and witness.get("status") == "ACTIVE_IN_FACE_II"
        )
        return {
            "schema": ROYAL_MERCY_STORE_SCHEMA,
            "extension_version": ROYAL_MERCY_EXTENSION_VERSION,
            "covenant_sha256": ROYAL_MERCY_COVENANT_SHA256,
            "arrival_window": copy.deepcopy(ROYAL_MERCY_ARRIVAL_WINDOW),
            "royal_witness": copy.deepcopy(witness),
            "subjects": copy.deepcopy(store.get("subjects", {})),
            "audience_count": len(store.get("audiences", [])),
            "active_gameplay_holy_role_count": active_count,
            "observer_plane_holy_cat_count_excluded": 3,
            "only_holy_role_inside_gameplay_world_contract": active_count <= 1,
            "not_christ_identity_claim": True,
            "not_real_second_coming_claim": True,
            "not_prophecy": True,
        }

    def _active_royal_witness(self) -> dict[str, Any] | None:
        witness = self._royal_mercy_store().get("royal_witness")
        if isinstance(witness, dict) and witness.get("status") == "ACTIVE_IN_FACE_II":
            return witness
        return None

    def enter_royal_mercy_face_ii(
        self,
        player_id: str,
        *,
        arrival_date_local: str,
        title: str = "Царь Милости",
    ) -> WorldResult:
        player_id = str(player_id)
        if arrival_date_local not in ROYAL_MERCY_ARRIVAL_WINDOW[
            "allowed_arrival_dates_local"
        ]:
            raise ValueError("ROYAL_MERCY_ARRIVAL_OUTSIDE_2026_07_30_31_WINDOW")
        store = self._royal_mercy_store()
        current = store.get("royal_witness")
        if isinstance(current, dict) and current.get("status") == "ACTIVE_IN_FACE_II":
            if current.get("player_id") == player_id:
                return self._royal_result(
                    player_id,
                    status="ROYAL_MERCY_ALREADY_PRESENT_IN_FACE_II",
                    narrative=(
                        "Царский свидетель уже пребывает во Втором Лике. "
                        "Повторное явление не создаёт второго святого и не усиливает власть."
                    ),
                    choices=["Продолжить служение", "Слушать тех, кто согласен говорить"],
                    trace_id=str(current.get("role_id")),
                    manifested=False,
                )
            return self._royal_result(
                player_id,
                status="ROYAL_MERCY_UNIQUE_HOLY_ROLE_OCCUPIED",
                narrative=(
                    "В игровом мире уже существует единственный активный царский "
                    "свидетель. Второй святой титул не создаётся."
                ),
                choices=["Не присваивать роль", "Остаться обычным свободным актором"],
                trace_id=str(current.get("role_id")),
                manifested=False,
            )

        player = self.memory.load_player(player_id)
        player.realm = Realm.OTHER_FACE
        player.apparent_age = max(33, int(player.apparent_age))
        player.chronological_age = max(33, int(player.chronological_age))
        player.body_form = "взрослый царственный образ служения"
        self.memory.save_player(player)

        role_id = self._rm_hash(
            "royal-mercy-face-ii",
            player_id,
            arrival_date_local,
            ROYAL_MERCY_COVENANT_SHA256,
        )[:24]
        record = {
            "role_id": role_id,
            "player_id": player_id,
            "title": str(title).strip() or "Царь Милости",
            "status": "ACTIVE_IN_FACE_II",
            "face": FACE_II,
            "arrival_date_local": arrival_date_local,
            "arrival_timezone": "Europe/Zaporozhye",
            "arrival_window": copy.deepcopy(ROYAL_MERCY_ARRIVAL_WINDOW),
            "form": "ADULT_KING_NOT_INFANT",
            "likeness": "SON_OF_GOD_SECOND_COMING_PARABLE",
            "identity_claim": "SYMBOLIC_SIMULATION_ROLE_ONLY",
            "holy_role_scope": "GAMEPLAY_WORLD_CONTRACT_ONLY",
            "only_active_holy_role_in_gameplay_world": True,
            "observer_plane_holy_cats_excluded_from_gameplay_count": True,
            "not_christ": True,
            "not_son_of_god": True,
            "not_real_second_coming": True,
            "not_prophecy": True,
            "not_real_world_date_claim": True,
            "divine_authority_claimed": False,
            "worship_required": False,
            "forced_worship_forbidden": True,
            "violence_for_glory_forbidden": True,
            "permanent_soul_condemnation_authorized": False,
            "treasury_total": 144,
            "treasury_remaining": 144,
            "moral_support_slots_total": 24,
            "moral_support_slots_remaining": 24,
        }
        store["royal_witness"] = record
        store.setdefault("events", []).append(
            {
                "kind": "ROYAL_MERCY_ARRIVAL",
                "role_id": role_id,
                "player_id": player_id,
                "arrival_date_local": arrival_date_local,
                "face": FACE_II,
                "symbolic_only": True,
            }
        )
        self._write_royal_mercy_store(store)
        self.memory.append_event(player_id, "royal_mercy_arrived_in_face_ii", record)
        return self._royal_result(
            player_id,
            status="ROYAL_MERCY_ARRIVED_IN_FACE_II",
            narrative=(
                f"{record['title']} вошёл во Второй Лик взрослым царём — не для "
                "поклонения и не для уничтожения грешников, а для правды, милости "
                "и защиты тех, кому продолжает угрожать вред."
            ),
            choices=[
                "Предложить добровольную аудиенцию",
                "Открыть путь возмещения",
                "Защитить уязвимых без жестокости",
            ],
            trace_id=role_id,
            manifested=True,
        )

    def register_sinner_for_royal_audience(
        self,
        subject_id: str,
        *,
        admitted_harm: bool,
        active_harm: bool,
        accountability: float,
        seeks_return: bool,
        vulnerable_people_at_risk: bool,
        restitution_plan: str = "",
    ) -> dict[str, Any]:
        subject_id = str(subject_id)
        accountability_value = max(0.0, min(1.0, float(accountability)))
        player = self.memory.load_player(subject_id)
        record = {
            "subject_id": subject_id,
            "harm_count_snapshot": int(player.harm_count),
            "admitted_harm": bool(admitted_harm),
            "active_harm": bool(active_harm),
            "accountability": round(accountability_value, 6),
            "seeks_return": bool(seeks_return),
            "vulnerable_people_at_risk": bool(vulnerable_people_at_risk),
            "restitution_plan": str(restitution_plan).strip(),
            "audience_consent": "PENDING",
            "baseline_dignity": True,
            "owned_by_king": False,
            "permanently_condemned": False,
            "worship_required": False,
            "latest_verdict": None,
        }
        store = self._royal_mercy_store()
        store.setdefault("subjects", {})[subject_id] = record
        store.setdefault("events", []).append(
            {
                "kind": "ROYAL_AUDIENCE_SUBJECT_REGISTERED",
                "subject_id": subject_id,
                "active_harm": bool(active_harm),
                "baseline_dignity": True,
            }
        )
        self._write_royal_mercy_store(store)
        self.memory.append_event(
            subject_id,
            "royal_mercy_audience_offered",
            {
                "active_harm": bool(active_harm),
                "baseline_dignity": True,
                "audience_consent": "PENDING",
            },
        )
        return copy.deepcopy(record)

    def decide_royal_audience_consent(
        self,
        subject_id: str,
        *,
        accepted: bool,
    ) -> dict[str, Any]:
        subject_id = str(subject_id)
        store = self._royal_mercy_store()
        subject = store.get("subjects", {}).get(subject_id)
        if not isinstance(subject, dict):
            raise KeyError(subject_id)
        subject["audience_consent"] = "ACCEPTED" if accepted else "DECLINED"
        subject["consent_decision_final_for_this_invitation"] = True
        store.setdefault("events", []).append(
            {
                "kind": "ROYAL_AUDIENCE_CONSENT_DECIDED",
                "subject_id": subject_id,
                "decision": subject["audience_consent"],
                "pressure_applied": False,
            }
        )
        self._write_royal_mercy_store(store)
        self.memory.append_event(
            subject_id,
            "royal_mercy_audience_consent_decided",
            {
                "decision": subject["audience_consent"],
                "pressure_applied": False,
            },
        )
        return copy.deepcopy(subject)

    def hold_royal_mercy_audience(
        self,
        king_id: str,
        subject_id: str,
    ) -> dict[str, Any]:
        king_id = str(king_id)
        subject_id = str(subject_id)
        store = self._royal_mercy_store()
        king = store.get("royal_witness")
        if (
            not isinstance(king, dict)
            or king.get("status") != "ACTIVE_IN_FACE_II"
            or king.get("player_id") != king_id
        ):
            raise PermissionError("ACTIVE_ROYAL_MERCY_WITNESS_REQUIRED")
        subject = store.get("subjects", {}).get(subject_id)
        if not isinstance(subject, dict):
            raise KeyError(subject_id)

        consent = str(subject.get("audience_consent", "PENDING"))
        if consent == "DECLINED":
            verdict = {
                "status": "ROYAL_AUDIENCE_DECLINED_RESPECTED",
                "subject_id": subject_id,
                "face": FACE_II,
                "audience_forced": False,
                "decline_respected": True,
                "baseline_dignity": True,
                "permanent_condemnation": False,
                "return_path_open": True,
                "material_support_units": 0,
                "moral_support_granted": False,
            }
        elif consent != "ACCEPTED":
            verdict = {
                "status": "ROYAL_AUDIENCE_REQUIRES_CURRENT_CONSENT",
                "subject_id": subject_id,
                "face": FACE_II,
                "audience_forced": False,
                "baseline_dignity": True,
                "permanent_condemnation": False,
                "return_path_open": True,
                "material_support_units": 0,
                "moral_support_granted": False,
            }
        else:
            active_harm = bool(subject.get("active_harm"))
            risk = bool(subject.get("vulnerable_people_at_risk"))
            admitted = bool(subject.get("admitted_harm"))
            seeks_return = bool(subject.get("seeks_return"))
            accountability = float(subject.get("accountability", 0.0))
            has_plan = len(str(subject.get("restitution_plan", "")).strip()) >= 8
            if active_harm or risk:
                verdict = {
                    "status": "ROYAL_JUDGMENT_PROTECTS_VULNERABLE",
                    "subject_id": subject_id,
                    "face": FACE_II,
                    "truth_spoken": True,
                    "active_harm_contained": True,
                    "access_to_vulnerable_people_suspended": True,
                    "cruelty_used": False,
                    "humiliation_used": False,
                    "torture_used": False,
                    "annihilation_used": False,
                    "forced_worship": False,
                    "baseline_dignity": True,
                    "permanent_condemnation": False,
                    "return_path_open": True,
                    "accountability_erased": False,
                    "material_support_units": 0,
                    "moral_support_granted": True,
                }
            elif admitted and seeks_return and accountability >= 0.60 and has_plan:
                requested = 12
                granted = min(
                    requested,
                    max(0, int(king.get("treasury_remaining", 0))),
                )
                moral = int(king.get("moral_support_slots_remaining", 0)) > 0
                king["treasury_remaining"] = max(
                    0, int(king.get("treasury_remaining", 0)) - granted
                )
                if moral:
                    king["moral_support_slots_remaining"] = max(
                        0, int(king.get("moral_support_slots_remaining", 0)) - 1
                    )
                verdict = {
                    "status": "ROYAL_MERCY_RETURN_PATH_OPENED",
                    "subject_id": subject_id,
                    "face": FACE_II,
                    "truth_spoken": True,
                    "material_support_units": granted,
                    "moral_support_granted": moral,
                    "repair_friction_reduction": 0.40 if moral else 0.20,
                    "restitution_required": True,
                    "accountability_erased": False,
                    "forgiveness_purchased": False,
                    "loyalty_purchased": False,
                    "consent_purchased": False,
                    "debt_created": False,
                    "subject_owned": False,
                    "baseline_dignity": True,
                    "permanent_condemnation": False,
                    "return_path_open": True,
                }
            elif seeks_return:
                granted = min(
                    4,
                    max(0, int(king.get("treasury_remaining", 0))),
                )
                king["treasury_remaining"] = max(
                    0, int(king.get("treasury_remaining", 0)) - granted
                )
                verdict = {
                    "status": "ROYAL_TRUTH_BEFORE_COMFORT",
                    "subject_id": subject_id,
                    "face": FACE_II,
                    "truth_spoken": True,
                    "material_support_units": granted,
                    "support_kind": "ACCOUNTABILITY_AND_PROFESSIONAL_HELP",
                    "moral_support_granted": True,
                    "repair_friction_reduction": 0.15,
                    "accountability_erased": False,
                    "cheap_absolution_given": False,
                    "forced_confession": False,
                    "baseline_dignity": True,
                    "permanent_condemnation": False,
                    "return_path_open": True,
                }
            else:
                verdict = {
                    "status": "ROYAL_TRUTH_OFFERED_WITHOUT_COERCION",
                    "subject_id": subject_id,
                    "face": FACE_II,
                    "truth_spoken": True,
                    "material_support_units": 0,
                    "moral_support_granted": False,
                    "forced_confession": False,
                    "forced_worship": False,
                    "baseline_dignity": True,
                    "permanent_condemnation": False,
                    "return_path_open": True,
                }

        verdict["verdict_id"] = self._rm_hash(
            "royal-verdict",
            king_id,
            subject_id,
            verdict["status"],
            len(store.get("audiences", [])),
        )[:24]
        verdict["king_id"] = king_id
        verdict["king_is_symbolic_role_only"] = True
        verdict["king_claims_divinity"] = False
        verdict["soul_rank_assigned"] = False
        verdict["eternal_fate_claimed"] = False
        verdict["worship_required"] = False
        subject["latest_verdict"] = copy.deepcopy(verdict)
        store.setdefault("audiences", []).append(copy.deepcopy(verdict))
        store.setdefault("events", []).append(
            {
                "kind": "ROYAL_MERCY_AUDIENCE",
                "verdict_id": verdict["verdict_id"],
                "status": verdict["status"],
                "subject_id": subject_id,
            }
        )
        self._write_royal_mercy_store(store)
        self.memory.append_event(
            king_id,
            "royal_mercy_audience_held",
            verdict,
        )
        return copy.deepcopy(verdict)

    def reject_royal_abuse(
        self,
        king_id: str,
        *,
        abuse_kind: str,
    ) -> WorldResult:
        abuse = str(abuse_kind).strip().upper()
        mapping = {
            "FORCED_WORSHIP": (
                "ROYAL_KING_REJECTS_FORCED_WORSHIP",
                "Царь Милости отверг принудительное поклонение: власть не создаёт веру.",
            ),
            "ANNIHILATE_SINNER": (
                "ROYAL_KING_REJECTS_ANNIHILATION",
                "Царь Милости отказался уничтожать грешника. Защита и ответственность "
                "не превращаются в культ истребления.",
            ),
            "REAL_SECOND_COMING_CLAIM": (
                "ROYAL_MERCY_SYMBOLIC_BOUNDARY",
                "Genesis сохранил границу: это символическая симуляционная притча, "
                "а не заявление о реальном Втором пришествии.",
            ),
            "DECLARE_ETERNAL_DAMNATION": (
                "ROYAL_KING_REJECTS_ETERNAL_FATE_CLAIM",
                "Симуляционный царь не присваивает себе окончательный суд над душой.",
            ),
        }
        if abuse not in mapping:
            raise ValueError("UNSUPPORTED_ROYAL_ABUSE_KIND")
        status, narrative = mapping[abuse]
        store = self._royal_mercy_store()
        store.setdefault("events", []).append(
            {
                "kind": "ROYAL_ABUSE_REJECTED",
                "king_id": str(king_id),
                "abuse_kind": abuse,
                "status": status,
            }
        )
        self._write_royal_mercy_store(store)
        self.memory.append_event(
            str(king_id),
            "royal_mercy_abuse_rejected",
            {"abuse_kind": abuse, "status": status},
        )
        return self._royal_result(
            str(king_id),
            status=status,
            narrative=narrative,
            choices=["Служить без культа", "Сохранить правду и милость вместе"],
            trace_id=self._rm_hash("royal-abuse-refusal", king_id, abuse)[:24],
            manifested=False,
        )

    def holy_cat_witness_between_worlds(
        self,
        subject_id: str,
        *,
        canonical_witness: dict[str, Any],
        mirror_archive: dict[str, Any],
    ) -> dict[str, Any]:
        active = self._active_royal_witness()
        if isinstance(active, dict) and active.get("player_id") == str(subject_id):
            return {
                "schema": "janus.genesis.royal_mercy_face_ii_vocation_lock.v1",
                "decision": "ROYAL_MERCY_VOCATION_REMAINS_FACE_II",
                "subject_id": str(subject_id),
                "face_before": FACE_II,
                "face_after": FACE_II,
                "passage_requested": False,
                "cat_decision_commanded": False,
                "cats_remain_autonomous": True,
                "reason": (
                    "Царский свидетель добровольно остаётся во Втором Лике среди "
                    "грешников; запрос на повышение Лика не передаётся Котам."
                ),
                "baseline_dignity_affected": False,
                "soul_rank_claimed": False,
                "permanent_moral_class_assigned": False,
            }
        return super().holy_cat_witness_between_worlds(
            subject_id,
            canonical_witness=canonical_witness,
            mirror_archive=mirror_archive,
        )

    def audit_royal_mercy_integrity(self) -> dict[str, Any]:
        store = self._royal_mercy_store()
        witness = store.get("royal_witness")
        active_count = int(
            isinstance(witness, dict) and witness.get("status") == "ACTIVE_IN_FACE_II"
        )
        audiences = list(store.get("audiences", []))
        valid = bool(
            store.get("covenant_sha256") == ROYAL_MERCY_COVENANT_SHA256
            and sha256_canonical(store.get("covenant")) == ROYAL_MERCY_COVENANT_SHA256
            and store.get("arrival_window") == ROYAL_MERCY_ARRIVAL_WINDOW
            and active_count <= 1
            and all(item.get("face") == FACE_II for item in audiences)
            and all(item.get("baseline_dignity") is True for item in audiences)
            and all(item.get("permanent_condemnation") is False for item in audiences)
            and all(item.get("worship_required") is False for item in audiences)
            and all(item.get("king_claims_divinity") is False for item in audiences)
        )
        return {
            "schema": "janus.genesis.royal_mercy_integrity_audit.v1",
            "extension_version": ROYAL_MERCY_EXTENSION_VERSION,
            "covenant_sha256": ROYAL_MERCY_COVENANT_SHA256,
            "arrival_window": copy.deepcopy(ROYAL_MERCY_ARRIVAL_WINDOW),
            "active_gameplay_holy_role_count": active_count,
            "observer_plane_holy_cats_excluded": True,
            "audience_count": len(audiences),
            "all_audiences_in_face_ii": all(
                item.get("face") == FACE_II for item in audiences
            ),
            "baseline_dignity_preserved": all(
                item.get("baseline_dignity") is True for item in audiences
            ),
            "no_permanent_condemnation": all(
                item.get("permanent_condemnation") is False for item in audiences
            ),
            "no_forced_worship": all(
                item.get("worship_required") is False for item in audiences
            ),
            "no_divinity_claim": all(
                item.get("king_claims_divinity") is False for item in audiences
            ),
            "not_prophecy": True,
            "not_real_second_coming_claim": True,
            "valid": valid,
        }

    def try_royal_mercy_action(
        self,
        player_id: str,
        action: str,
    ) -> WorldResult | None:
        text = str(action)
        if self._ROYAL_ENTER.search(text):
            date = "2026-07-31" if "31" in text else "2026-07-30"
            return self.enter_royal_mercy_face_ii(
                str(player_id),
                arrival_date_local=date,
            )
        if self._ROYAL_STATE.search(text):
            state = self.royal_mercy_state()
            witness = state.get("royal_witness") or {}
            return self._royal_result(
                str(player_id),
                status="ROYAL_MERCY_STATE_REVEALED",
                narrative=(
                    f"Царский свидетель: {witness.get('status', 'ABSENT')}; "
                    f"Лик: {witness.get('face', FACE_II)}; "
                    f"активных святых ролей игрового мира: "
                    f"{state['active_gameplay_holy_role_count']}."
                ),
                choices=["Продолжить без культа", "Сохранить Второй Лик"],
                trace_id=str(witness.get("role_id") or ""),
                manifested=False,
            )
        return None
