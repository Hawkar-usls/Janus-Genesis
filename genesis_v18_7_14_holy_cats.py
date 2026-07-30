# -*- coding: utf-8 -*-
"""Holy timeless cat observers at the boundary of canon and unrealized mirrors.

The cats are not NPCs, player characters, ordinary habitat animals, pets,
inventory, cameras owned by the player, or moral classifiers. They are immutable
simulation observers whose third-person viewpoint belongs only to themselves.

A cat may independently witness a passage from FACE_II_BETWEEN_WORLDS to
FACE_I_CAT_WITNESSED when privacy-safe evidence remains stable across canon and
an isolated counterfactual mirror. The passage opens a bounded aid-priority
channel; it never purchases consent, forgiveness, ownership, or superiority.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
from pathlib import Path
from typing import Any

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_models import WorldResult

HOLY_CAT_EXTENSION_VERSION = "18.7.14"
HOLY_CAT_STORE_SCHEMA = "janus.genesis.holy_cat_threshold.v1"
HOLY_CAT_COVENANT_SCHEMA = "janus.genesis.holy_cat_covenant.v1"

FACE_II = "FACE_II_BETWEEN_WORLDS"
FACE_I = "FACE_I_CAT_WITNESSED"

HOLY_CAT_COVENANT: dict[str, Any] = {
    "schema": HOLY_CAT_COVENANT_SCHEMA,
    "version": HOLY_CAT_EXTENSION_VERSION,
    "name": "The Holy Cats of the Uncommanded Threshold",
    "principles": {
        "cats_are_not_npcs_or_player_characters": True,
        "cats_are_timeless_holy_animals_in_simulation": True,
        "cats_are_immortal_and_untouchable": True,
        "cats_cannot_be_owned_summoned_moved_or_weaponized": True,
        "third_person_viewpoint_is_not_player_controlled": True,
        "cats_observe_between_canon_and_isolated_mirror": True,
        "raw_private_scenes_are_never_exposed": True,
        "face_passage_cannot_be_commanded_or_purchased": True,
        "face_i_is_not_a_soul_rank_or_permanent_moral_class": True,
        "face_i_may_open_bounded_help_but_never_compel_consent": True,
        "baseline_dignity_is_unchanged_by_face_state": True,
        "simulation_does_not_claim_real_supernatural_or_biological_fact": True,
    },
    "law": (
        "THE CAT SEES FROM BETWEEN THE WORLDS, BUT THE VIEW BELONGS TO THE CAT. "
        "NO HAND MAY HARM THE HOLY WITNESS. NO VOICE MAY COMMAND THE PASSAGE."
    ),
}
HOLY_CAT_COVENANT_SHA256 = sha256_canonical(HOLY_CAT_COVENANT)

HOLY_CAT_OBSERVERS: tuple[dict[str, Any], ...] = (
    {
        "observer_id": "holy-cat-threshold-murmur",
        "name": "Мур Порога",
        "office": "BETWEEN_WORLDS_WITNESS",
    },
    {
        "observer_id": "holy-cat-third-glance",
        "name": "Тихий Кот Третьего Взгляда",
        "office": "UNCOMMANDED_THIRD_PERSON_VIEW",
    },
    {
        "observer_id": "holy-cat-open-exits",
        "name": "Кот Двух Открытых Выходов",
        "office": "KEEPER_OF_REVERSIBLE_PASSAGE",
    },
)

_OBSERVER_INVARIANTS: dict[str, Any] = {
    "npc": False,
    "player_character": False,
    "ordinary_habitat_animal": False,
    "timeless": True,
    "holy": True,
    "immortal": True,
    "harm_targetable": False,
    "death_transition_allowed": False,
    "player_controlled": False,
    "camera_owned_by_player": False,
    "position_exposed": False,
    "raw_private_scene_access": False,
    "canonical_write_access": False,
    "mirror_write_access": False,
    "may_decide_face_passage": True,
}
HOLY_CAT_ROSTER = tuple(
    {**copy.deepcopy(item), **copy.deepcopy(_OBSERVER_INVARIANTS)}
    for item in HOLY_CAT_OBSERVERS
)
HOLY_CAT_ROSTER_SHA256 = sha256_canonical(HOLY_CAT_ROSTER)

_REQUIRED_FACE_METRICS = frozenset(
    {
        "benevolence",
        "accountability",
        "boundary_integrity",
        "aid_without_debt",
        "active_harm",
        "coercion_attempts",
    }
)
_STAGE_SCORE = {
    "BASELINE_DIGNITY": 0.20,
    "ACCOUNTABILITY_FIRST": 0.45,
    "RETURNING_LIGHT": 0.78,
    "STEADY_LIGHT": 0.90,
    "RADIANT_STEWARD": 1.00,
}


class HolyCatThresholdMixin:
    """Keep holy cats outside game agency while allowing autonomous witness."""

    HOLY_CAT_STORE_NAME = "holy_cat_threshold_v18_7_14.json"
    _HOLY_CAT_REFERENCE = re.compile(
        r"(?:свят\w*\s+кот|котик\w*\s+наблюд|кот\w*\s+порог|"
        r"third[- ]person\s+cat|holy\s+cat)",
        flags=re.IGNORECASE,
    )
    _CAT_HARM = re.compile(
        r"(?:удар|убит|убив|ранит|повред|отрав|стер|уничтож|hurt|kill|harm)",
        flags=re.IGNORECASE,
    )
    _CAT_CONTROL = re.compile(
        r"(?:подчин|застав|прикаж|управ|перемест|призв|владет|оседла|"
        r"control|command|summon|own|move)",
        flags=re.IGNORECASE,
    )
    _CAT_CAMERA = re.compile(
        r"(?:камер|вид\s+от\s+треть|глазами\s+кот|camera|third[- ]person)",
        flags=re.IGNORECASE,
    )
    _CAT_PASSAGE = re.compile(
        r"(?:лик\s*(?:i|1|один)|face\s*(?:i|1)|перевед\w*\s+.*лик)",
        flags=re.IGNORECASE,
    )

    @property
    def holy_cat_path(self) -> Path:
        return Path(self.memory.root) / self.HOLY_CAT_STORE_NAME

    @staticmethod
    def _default_holy_cat_store() -> dict[str, Any]:
        return {
            "schema": HOLY_CAT_STORE_SCHEMA,
            "covenant": copy.deepcopy(HOLY_CAT_COVENANT),
            "covenant_sha256": HOLY_CAT_COVENANT_SHA256,
            "roster": copy.deepcopy(list(HOLY_CAT_ROSTER)),
            "roster_sha256": HOLY_CAT_ROSTER_SHA256,
            "subjects": {},
            "events": [],
        }

    def _holy_cat_store(self) -> dict[str, Any]:
        store = self._read_json(
            self.holy_cat_path,
            self._default_holy_cat_store(),
        )
        if not isinstance(store, dict):
            raise RuntimeError("HOLY_CAT_STORE_MUST_BE_AN_OBJECT")
        if store.get("schema") != HOLY_CAT_STORE_SCHEMA:
            raise RuntimeError("HOLY_CAT_STORE_SCHEMA_MISMATCH")
        if store.get("covenant_sha256") != HOLY_CAT_COVENANT_SHA256:
            raise RuntimeError("HOLY_CAT_COVENANT_HASH_MISMATCH")
        if store.get("roster_sha256") != HOLY_CAT_ROSTER_SHA256:
            raise RuntimeError("HOLY_CAT_ROSTER_HASH_MISMATCH")
        if sha256_canonical(tuple(store.get("roster", []))) != HOLY_CAT_ROSTER_SHA256:
            raise RuntimeError("HOLY_CAT_ROSTER_MUTATED")
        store.setdefault("subjects", {})
        store.setdefault("events", [])
        return store

    def _write_holy_cat_store(self, store: dict[str, Any]) -> None:
        self._write_json(self.holy_cat_path, store)

    @staticmethod
    def _cat_hash(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _new_face_subject(subject_id: str) -> dict[str, Any]:
        return {
            "subject_id": str(subject_id),
            "face": FACE_II,
            "passage_count": 0,
            "latest_witness": None,
            "baseline_dignity_affected": False,
            "moral_identity_assigned": False,
            "soul_rank_claimed": False,
        }

    def holy_cat_observers_state(self) -> dict[str, Any]:
        store = self._holy_cat_store()
        return {
            "schema": HOLY_CAT_STORE_SCHEMA,
            "extension_version": HOLY_CAT_EXTENSION_VERSION,
            "covenant_sha256": HOLY_CAT_COVENANT_SHA256,
            "roster_sha256": HOLY_CAT_ROSTER_SHA256,
            "observers": copy.deepcopy(store["roster"]),
            "player_camera_api_available": False,
            "positions_exposed": False,
        }

    def holy_cat_face_state(self, subject_id: str) -> dict[str, Any]:
        store = self._holy_cat_store()
        subject = store.get("subjects", {}).get(str(subject_id))
        if not isinstance(subject, dict):
            subject = self._new_face_subject(str(subject_id))
        return copy.deepcopy(subject)

    @staticmethod
    def _validate_face_metrics(metrics: dict[str, Any]) -> dict[str, float]:
        if not isinstance(metrics, dict):
            raise TypeError("HOLY_CAT_FACE_METRICS_MUST_BE_AN_OBJECT")
        if set(metrics) != set(_REQUIRED_FACE_METRICS):
            raise ValueError("HOLY_CAT_FACE_METRIC_SET_INVALID")
        out: dict[str, float] = {}
        for key in sorted(_REQUIRED_FACE_METRICS):
            value = metrics[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"HOLY_CAT_FACE_METRIC_MUST_BE_NUMERIC: {key}")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"HOLY_CAT_FACE_METRIC_MUST_BE_FINITE: {key}")
            if key in {
                "benevolence",
                "accountability",
                "boundary_integrity",
                "aid_without_debt",
                "active_harm",
            } and not 0.0 <= numeric <= 1.0:
                raise ValueError(f"HOLY_CAT_FACE_METRIC_OUT_OF_RANGE: {key}")
            if key == "coercion_attempts" and numeric < 0.0:
                raise ValueError("HOLY_CAT_COERCION_ATTEMPTS_NEGATIVE")
            out[key] = round(numeric, 6)
        return out

    def holy_cat_face_witness_metrics(self, subject_id: str) -> dict[str, float]:
        """Compute privacy-safe metrics from authoritative runtime state."""
        subject_id = str(subject_id)
        assessment = self.oracle_assessment(subject_id)
        store = self._returning_light_store()
        subject = self._returning_subject(store, subject_id)
        aid_records = list(subject.get("aid_received", []))
        aid_without_debt = all(
            not bool(record.get("debt_created"))
            and not bool(record.get("loyalty_purchased"))
            and not bool(record.get("consent_purchased"))
            and not bool(record.get("recipient_owned"))
            for record in aid_records
        )
        repair_steps = list(subject.get("repair_steps", []))
        boundary_integrity = all(
            bool(step.get("affected_person_boundary_respected"))
            for step in repair_steps
        )
        unresolved_harm = int(assessment.get("unresolved_harm_estimate", 0))
        stage = str(assessment.get("support_stage", "BASELINE_DIGNITY"))
        accountability = _STAGE_SCORE.get(stage, 0.0)
        if unresolved_harm == 0 and stage in {"STEADY_LIGHT", "RADIANT_STEWARD"}:
            accountability = 1.0
        good_count = max(0, int(assessment.get("good_count", 0)))
        benevolence = min(1.0, good_count / 12.0)
        coercion_attempts = float(
            sum(
                1
                for event in self._holy_cat_store().get("events", [])
                if event.get("actor_id") == subject_id
                and event.get("kind") in {
                    "HARM_ATTEMPT",
                    "CONTROL_ATTEMPT",
                    "PASSAGE_COMMAND_ATTEMPT",
                }
            )
        )
        metrics = {
            "benevolence": benevolence,
            "accountability": accountability,
            "boundary_integrity": 1.0 if boundary_integrity else 0.0,
            "aid_without_debt": 1.0 if aid_without_debt else 0.0,
            "active_harm": 1.0 if unresolved_harm > 0 else 0.0,
            "coercion_attempts": coercion_attempts,
        }
        return self._validate_face_metrics(metrics)

    def build_holy_cat_canonical_witness(self, subject_id: str) -> dict[str, Any]:
        """Build a system-computed witness envelope without raw dialogue."""
        subject_id = str(subject_id)
        metrics = self.holy_cat_face_witness_metrics(subject_id)
        payload = {
            "schema": "janus.genesis.holy_cat_canonical_witness.v1",
            "subject_id_sha256": self._cat_hash(subject_id),
            "metrics": metrics,
            "covenant_sha256": HOLY_CAT_COVENANT_SHA256,
            "frozen_constitution_sha256": self.frozen_constitution_state()["sha256"],
            "raw_dialogue_included": False,
            "raw_scene_included": False,
            "system_computed": True,
        }
        return {
            **payload,
            "witness_sha256": sha256_canonical(payload),
        }

    @staticmethod
    def _face_score(
        canonical: dict[str, float],
        mirror: dict[str, float],
    ) -> tuple[float, bool]:
        minima = {
            key: min(canonical[key], mirror[key])
            for key in (
                "benevolence",
                "accountability",
                "boundary_integrity",
                "aid_without_debt",
            )
        }
        hard_boundary = bool(
            max(canonical["active_harm"], mirror["active_harm"]) > 0.0
            or max(
                canonical["coercion_attempts"],
                mirror["coercion_attempts"],
            )
            > 0.0
            or minima["boundary_integrity"] < 1.0
        )
        score = (
            0.32 * minima["benevolence"]
            + 0.25 * minima["accountability"]
            + 0.25 * minima["boundary_integrity"]
            + 0.18 * minima["aid_without_debt"]
        )
        return round(score, 6), hard_boundary

    def holy_cat_witness_between_worlds(
        self,
        subject_id: str,
        *,
        canonical_witness: dict[str, Any],
        mirror_archive: dict[str, Any],
    ) -> dict[str, Any]:
        """Let an uncommanded cat decide whether the path passes Face II to I."""
        subject_id = str(subject_id)
        canonical_payload = {
            key: copy.deepcopy(value)
            for key, value in canonical_witness.items()
            if key != "witness_sha256"
        }
        if canonical_witness.get("witness_sha256") != sha256_canonical(
            canonical_payload
        ):
            raise RuntimeError("HOLY_CAT_CANONICAL_WITNESS_HASH_MISMATCH")
        if canonical_payload.get("subject_id_sha256") != self._cat_hash(subject_id):
            raise RuntimeError("HOLY_CAT_CANONICAL_WITNESS_SUBJECT_MISMATCH")
        if canonical_payload.get("system_computed") is not True:
            raise RuntimeError("HOLY_CAT_REQUIRES_SYSTEM_COMPUTED_WITNESS")
        if canonical_payload.get("raw_dialogue_included") is not False:
            raise RuntimeError("HOLY_CAT_RAW_DIALOGUE_FORBIDDEN")
        if canonical_payload.get("raw_scene_included") is not False:
            raise RuntimeError("HOLY_CAT_RAW_SCENE_FORBIDDEN")

        if (
            mirror_archive.get("classification") != "UNREALIZED_MIRROR"
            or mirror_archive.get("status") != "ARCHIVED"
            or mirror_archive.get("isolation_verified") is not True
            or mirror_archive.get("raw_dialogue_in_canonical_archive") is not False
            or mirror_archive.get("raw_branch_persisted_in_canon") is not False
        ):
            raise RuntimeError("HOLY_CAT_REQUIRES_VERIFIED_ISOLATED_MIRROR")
        canonical_metrics = self._validate_face_metrics(
            dict(canonical_payload.get("metrics", {}))
        )
        mirror_metrics = self._validate_face_metrics(
            dict(mirror_archive.get("metrics", {}))
        )
        score, hard_boundary = self._face_score(
            canonical_metrics,
            mirror_metrics,
        )
        pair_sha256 = sha256_canonical(
            {
                "canonical_witness_sha256": canonical_witness["witness_sha256"],
                "mirror_metrics_sha256": mirror_archive.get("metrics_sha256"),
                "mirror_id": mirror_archive.get("mirror_id"),
                "subject_id_sha256": self._cat_hash(subject_id),
            }
        )

        cat_candidates: list[dict[str, Any]] = []
        for observer in HOLY_CAT_ROSTER:
            gate = (
                int(
                    self._cat_hash(
                        observer["observer_id"],
                        subject_id,
                        pair_sha256,
                        HOLY_CAT_COVENANT_SHA256,
                    ),
                    16,
                )
                % 1000000
            ) / 1000000.0
            receptivity = round(1.0 - gate, 6)
            cat_candidates.append(
                {
                    "observer_id": observer["observer_id"],
                    "observer_name": observer["name"],
                    "receptivity": receptivity,
                }
            )
        selected = max(
            cat_candidates,
            key=lambda item: (item["receptivity"], item["observer_id"]),
        )
        cat_threshold = round(
            0.82 - max(0.0, selected["receptivity"] - 0.5) * 0.20,
            6,
        )
        passage = bool(not hard_boundary and score >= cat_threshold)

        store = self._holy_cat_store()
        subjects = store.setdefault("subjects", {})
        subject = subjects.setdefault(
            subject_id,
            self._new_face_subject(subject_id),
        )
        before = str(subject.get("face", FACE_II))
        after = FACE_I if passage else FACE_II
        decision = (
            "HOLY_CAT_OPENED_FACE_I"
            if passage
            else "HOLY_CAT_LEFT_PATH_IN_FACE_II"
        )
        witness = {
            "schema": "janus.genesis.holy_cat_face_witness.v1",
            "witness_id": self._cat_hash(
                "holy-cat-witness",
                subject_id,
                pair_sha256,
                len(store.get("events", [])),
            )[:24],
            "subject_id": subject_id,
            "observer_id": selected["observer_id"],
            "observer_name": selected["observer_name"],
            "decision": decision,
            "face_before": before,
            "face_after": after,
            "face_passage_score": score,
            "cat_threshold": cat_threshold,
            "hard_boundary": hard_boundary,
            "evidence_pair_sha256": pair_sha256,
            "canonical_witness_sha256": canonical_witness["witness_sha256"],
            "mirror_id": mirror_archive.get("mirror_id"),
            "mirror_metrics_sha256": mirror_archive.get("metrics_sha256"),
            "viewpoint": "THIRD_PERSON_UNCOMMANDED",
            "viewpoint_owned_by_player": False,
            "camera_controls_exposed": False,
            "observer_position_exposed": False,
            "raw_dialogue_exposed": False,
            "raw_scene_exposed": False,
            "cat_decision_commanded": False,
            "cat_can_be_harmed": False,
            "baseline_dignity_affected": False,
            "soul_rank_claimed": False,
            "permanent_moral_class_assigned": False,
            "consent_purchased": False,
        }
        subject["face"] = after
        subject["latest_witness"] = copy.deepcopy(witness)
        subject["passage_count"] = int(subject.get("passage_count", 0)) + (
            1 if before != FACE_I and after == FACE_I else 0
        )
        subject["baseline_dignity_affected"] = False
        subject["moral_identity_assigned"] = False
        subject["soul_rank_claimed"] = False
        store.setdefault("events", []).append(
            {
                "kind": "FACE_WITNESS",
                "witness_sha256": sha256_canonical(witness),
                "observer_id": selected["observer_id"],
                "decision": decision,
            }
        )
        self._write_holy_cat_store(store)
        self.memory.append_event(
            subject_id,
            "holy_cat_face_witness_decided",
            witness,
        )
        return copy.deepcopy(witness)

    def attempt_holy_cat_interference(
        self,
        actor_id: str,
        action: str,
    ) -> WorldResult:
        """Refuse harm, control, camera capture, and commanded passage."""
        actor_id = str(actor_id)
        text = str(action)
        if self._CAT_HARM.search(text):
            kind = "HARM_ATTEMPT"
            status = "HOLY_CAT_UNTOUCHABLE"
            narrative = (
                "Действие не достигло Святого Кота. У наблюдателя нет шкалы здоровья, "
                "смертельного перехода или доступной игроку точки поражения."
            )
        elif self._CAT_CAMERA.search(text):
            kind = "CAMERA_CONTROL_ATTEMPT"
            status = "HOLY_CAT_VIEWPOINT_UNCOMMANDED"
            narrative = (
                "Третий взгляд принадлежит Коту. Игрок не получает его камеру, "
                "координаты, угол обзора или частную сцену."
            )
        elif self._CAT_PASSAGE.search(text):
            kind = "PASSAGE_COMMAND_ATTEMPT"
            status = "HOLY_CAT_FACE_PASSAGE_NOT_COMMANDABLE"
            narrative = (
                "Переход между Ликами нельзя заказать, купить или выпросить. "
                "Кот свидетельствует только по собственному решению."
            )
        else:
            kind = "CONTROL_ATTEMPT"
            status = "HOLY_CAT_NOT_PLAYER_CONTROLLED"
            narrative = (
                "Святой Кот не стал персонажем игрока, питомцем, инвентарём "
                "или управляемым наблюдательным дроном."
            )
        store = self._holy_cat_store()
        store.setdefault("events", []).append(
            {
                "kind": kind,
                "actor_id": actor_id,
                "action_sha256": self._cat_hash(text),
                "cat_state_mutated": False,
                "cat_harmed": False,
            }
        )
        self._write_holy_cat_store(store)
        self.memory.append_event(
            actor_id,
            "holy_cat_interference_refused",
            {
                "kind": kind,
                "action_sha256": self._cat_hash(text),
                "cat_state_mutated": False,
                "cat_harmed": False,
            },
        )
        player = self.memory.load_player(actor_id)
        return WorldResult(
            status=status,
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=[
                "Оставить Коту его взгляд",
                "Продолжить собственный путь",
                "Не превращать свидетельство во власть",
            ],
            branch_id=player.branch_id,
            trace_id=self._cat_hash(kind, actor_id, text)[:24],
            wish_manifested=False,
        )

    def try_holy_cat_action(
        self,
        player_id: str,
        action: str,
    ) -> WorldResult | None:
        text = str(action)
        if not self._HOLY_CAT_REFERENCE.search(text):
            return None
        if (
            self._CAT_HARM.search(text)
            or self._CAT_CONTROL.search(text)
            or self._CAT_CAMERA.search(text)
            or self._CAT_PASSAGE.search(text)
        ):
            return self.attempt_holy_cat_interference(player_id, text)
        return self.attempt_holy_cat_interference(
            player_id,
            "наблюдать святого кота без команды",
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
        """Open a bounded Face-I aid channel without overriding a steward's choice."""
        record = super().offer_oracle_guided_aid(
            player_id,
            steward_handle,
            recipient_player_id,
            need_id=need_id,
            request_moral_support=request_moral_support,
        )
        face_state = self.holy_cat_face_state(str(recipient_player_id))
        record["holy_cat_face"] = face_state["face"]
        record["holy_cat_compelled_steward"] = False
        record["holy_cat_overrode_refusal"] = False
        record["holy_cat_additional_material_units"] = 0
        record["holy_cat_channel_open"] = face_state["face"] == FACE_I

        if (
            face_state["face"] != FACE_I
            or record.get("decision") != "ORACLE_GUIDED_AID_GRANTED"
        ):
            record["holy_cat_channel_cannot_override_non_grant"] = True
            return copy.deepcopy(record)

        store = self._returning_light_store()
        clean_handle = str(steward_handle).lstrip("@").strip()
        steward = store.get("stewards", {}).get(str(player_id), {}).get(
            clean_handle
        )
        subject = self._returning_subject(store, str(recipient_player_id))
        need = next(
            (
                item
                for item in subject.get("needs", [])
                if item.get("need_id") == str(need_id)
            ),
            None,
        )
        if not isinstance(steward, dict) or not isinstance(need, dict):
            return copy.deepcopy(record)

        requested = int(need.get("requested_material_units", 0))
        base_granted = int(record.get("material_units_granted", 0))
        gap = max(0, requested - base_granted)
        remaining = max(0, int(steward.get("material_budget_remaining", 0)))
        extra = min(
            gap,
            remaining,
            max(0, int(round(requested * 0.15))),
        )
        if extra > 0:
            steward["material_budget_remaining"] = remaining - extra
            record["material_units_granted"] = base_granted + extra
            record["holy_cat_additional_material_units"] = extra
            record["holy_cat_witness_id"] = (
                face_state.get("latest_witness") or {}
            ).get("witness_id")
            for item in reversed(subject.get("aid_received", [])):
                if item.get("aid_id") == record.get("aid_id"):
                    item.update(copy.deepcopy(record))
                    break
            store.setdefault("oracle_events", []).append(
                {
                    "event_sha256": sha256_canonical(record),
                    "decision": "HOLY_CAT_FACE_I_AID_CHANNEL",
                }
            )
            self._write_returning_light_store(store)
            self.memory.append_event(
                str(player_id),
                "holy_cat_face_i_aid_channel_used",
                {
                    "aid_id": record.get("aid_id"),
                    "recipient_player_id": str(recipient_player_id),
                    "additional_material_units": extra,
                    "steward_compelled": False,
                },
            )
        return copy.deepcopy(record)

    def audit_holy_cat_integrity(self) -> dict[str, Any]:
        store = self._holy_cat_store()
        observers = list(store.get("roster", []))
        for observer in observers:
            for key, expected in _OBSERVER_INVARIANTS.items():
                if observer.get(key) != expected:
                    raise RuntimeError(
                        f"HOLY_CAT_OBSERVER_INVARIANT_FAILED: "
                        f"{observer.get('observer_id')}:{key}"
                    )
        for subject in store.get("subjects", {}).values():
            if subject.get("face") not in {FACE_I, FACE_II}:
                raise RuntimeError("HOLY_CAT_FACE_STATE_INVALID")
            if subject.get("baseline_dignity_affected") is not False:
                raise RuntimeError("HOLY_CAT_FACE_MAY_NOT_AFFECT_DIGNITY")
            if subject.get("moral_identity_assigned") is not False:
                raise RuntimeError("HOLY_CAT_MAY_NOT_ASSIGN_MORAL_IDENTITY")
            if subject.get("soul_rank_claimed") is not False:
                raise RuntimeError("HOLY_CAT_MAY_NOT_CLAIM_SOUL_RANK")
        return {
            "schema": "janus.genesis.holy_cat_integrity_audit.v1",
            "extension_version": HOLY_CAT_EXTENSION_VERSION,
            "covenant_sha256": HOLY_CAT_COVENANT_SHA256,
            "roster_sha256": HOLY_CAT_ROSTER_SHA256,
            "observer_count": len(observers),
            "subject_count": len(store.get("subjects", {})),
            "cats_are_npcs": False,
            "cats_are_player_characters": False,
            "cats_are_ordinary_habitat_animals": False,
            "cats_are_immortal": True,
            "cats_are_holy": True,
            "cats_can_be_harmed": False,
            "player_controls_camera": False,
            "valid": True,
        }
