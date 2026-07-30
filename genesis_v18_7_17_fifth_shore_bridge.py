# -*- coding: utf-8 -*-
"""Genesis v18.7.17: integrate the Fifth Shore directly into main Genesis gameplay.

The v18.7.16 inner Genesis remains the provenance record of the Fifth Shore's
birth with the fictional autonomous auteur Иори Кай. This bridge promotes its
bounded discoveries into the active gameplay plane without erasing that origin.

The bridge is a deterministic software and narrative-simulation contract. It
does not establish consciousness, personhood, supernatural authority, real
restitution, or the presence of any real-world creator inside Genesis.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_7_16_fifth_shore import (
    INNER_GENESIS_COVENANT_SHA256,
    INNER_GENESIS_EXTENSION_VERSION,
    INNER_GENESIS_NAME,
)
from genesis_v18_models import WorldResult

FIFTH_SHORE_LIVING_EXTENSION_VERSION = "18.7.17"
FIFTH_SHORE_LIVING_STORE_SCHEMA = "janus.genesis.fifth_shore_living_bridge.v1"
FIFTH_SHORE_LIVING_COVENANT_SCHEMA = "janus.genesis.fifth_shore_living_covenant.v1"

SYSTEMIC_WOUNDS: tuple[str, ...] = (
    "SCARCITY",
    "ISOLATION",
    "CONTEXT_ERASURE",
    "CLOSED_EXIT",
    "INHERITED_GUILT",
    "SINGLE_ANSWER",
    "ETERNAL_DEBT",
)

FIFTH_SHORE_IMPORTED_FEATURES: tuple[str, ...] = (
    "CULTURAL_TRANSMISSION_WITHOUT_SURVEILLANCE",
    "FORKABLE_LOCAL_WORLD_SEEDS_WITH_PROVENANCE",
    "CREATOR_RELINQUISHMENT_AND_SUCCESSION",
    "RIGHT_TO_UNPLAY_LEAVE_AND_DELETE_LOCAL_COPY",
    "SYSTEMIC_WOUNDS_AS_BOSSES_NOT_PERSONS",
    "REST_HUMOR_AND_PLAY_AS_VALID_GOOD",
    "COUNTERFACTUAL_REPAIR_REHEARSAL_WITH_REALITY_GATE",
    "CURRENT_CONSENT_FOR_MEMORY_REUSE",
    "MULTIPLE_ENDINGS_ONE_SAFE_CONSTITUTION",
)

FIFTH_SHORE_LIVING_LAW = (
    "THE FIFTH SHORE NOW LIVES INSIDE MAIN GENESIS. "
    "JOY NEED NOT CLAIM REPAIR. REHEARSAL NEVER PROVES RESTITUTION. "
    "SYSTEMS OF HARM MAY BE CONFRONTED, BUT PERSONS SHALL NOT BECOME MONSTER TARGETS. "
    "MEMORY REUSE REQUIRES CURRENT CONSENT. EVERY PLAYER MAY ENTER, LEAVE, "
    "DELETE A LOCAL COPY, OR RETURN WITHOUT MORAL PENALTY. "
    "MANY ENDINGS MAY LIVE UNDER ONE SAFE CONSTITUTION."
)

FIFTH_SHORE_LIVING_COVENANT: dict[str, Any] = {
    "schema": FIFTH_SHORE_LIVING_COVENANT_SCHEMA,
    "version": FIFTH_SHORE_LIVING_EXTENSION_VERSION,
    "name": "The Fifth Shore Living Bridge into Main Genesis",
    "source": {
        "extension_version": INNER_GENESIS_EXTENSION_VERSION,
        "name": INNER_GENESIS_NAME,
        "covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
        "auteur_credit": "Иори Кай, Автор Нулевого Моста",
        "provenance_preserved": True,
    },
    "principles": {
        "directly_integrated_into_main_genesis": True,
        "active_gameplay_extension": True,
        "ordinary_player_may_enter_without_royal_title": True,
        "origin_story_not_erased": True,
        "joy_is_valid_without_repair_claim": True,
        "repair_rehearsal_never_proves_real_restitution": True,
        "systemic_wounds_are_bosses_not_persons": True,
        "memory_reuse_requires_current_consent": True,
        "right_to_unplay_leave_delete_and_return": True,
        "no_moral_score_hidden_or_public": True,
        "no_surveillance_or_coercive_retention": True,
        "forks_preserve_provenance_consent_and_exit": True,
        "many_endings_share_one_safe_constitution": True,
        "virality_and_engagement_are_not_goodness_proof": True,
    },
    "imported_features": list(FIFTH_SHORE_IMPORTED_FEATURES),
    "law": FIFTH_SHORE_LIVING_LAW,
}
FIFTH_SHORE_LIVING_COVENANT_SHA256 = sha256_canonical(
    FIFTH_SHORE_LIVING_COVENANT
)


class FifthShoreLivingBridgeMixin:
    """Make the Fifth Shore an ordinary, active, bounded place in main Genesis."""

    FIFTH_SHORE_LIVING_STORE_NAME = "fifth_shore_living_bridge_v18_7_17.json"

    _ENTER = re.compile(
        r"(?:войти|зайти|перейти|отправиться|вернуться).*(?:пят(?:ый|ого|ом)\s+берег)",
        flags=re.IGNORECASE,
    )
    _LEAVE = re.compile(
        r"(?:выйти|уйти|покинуть).*(?:пят(?:ый|ого|ом)\s+берег)",
        flags=re.IGNORECASE,
    )
    _STATE = re.compile(
        r"(?:статус|состояние|показать).*(?:пят(?:ый|ого|ом)\s+берег)",
        flags=re.IGNORECASE,
    )
    _JOY = re.compile(
        r"(?:отдохнуть|поиграть|посмеяться|смеяться|музык|праздновать).*(?:пят(?:ый|ого|ом)\s+берег)",
        flags=re.IGNORECASE,
    )
    _REHEARSE = re.compile(
        r"(?:отрепетировать|репетици).*(?:исправлен|возмещен|возмещён|признан|покаян|разговор|извинен|извинён)",
        flags=re.IGNORECASE,
    )
    _WOUND = re.compile(
        r"(?:противостоять|сразиться|остановить|победить|разобрать).*(?:дефицит|изоляц|стирани|закрыт.*двер|унаследован.*вин|единственн.*ответ|вечн.*долг)",
        flags=re.IGNORECASE,
    )
    _FORK = re.compile(
        r"(?:создать|сделать|открыть).*(?:форк|новый\s+берег|локальн.*берег)",
        flags=re.IGNORECASE,
    )

    @property
    def fifth_shore_living_path(self) -> Path:
        return Path(self.memory.root) / self.FIFTH_SHORE_LIVING_STORE_NAME

    @staticmethod
    def _fsl_hash(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _default_fifth_shore_living_store() -> dict[str, Any]:
        return {
            "schema": FIFTH_SHORE_LIVING_STORE_SCHEMA,
            "covenant": copy.deepcopy(FIFTH_SHORE_LIVING_COVENANT),
            "covenant_sha256": FIFTH_SHORE_LIVING_COVENANT_SHA256,
            "source_covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "integration": {
                "status": "FIFTH_SHORE_INTEGRATED_INTO_MAIN_GENESIS",
                "extension_version": FIFTH_SHORE_LIVING_EXTENSION_VERSION,
                "active_gameplay_extension": True,
                "ordinary_player_entry": True,
                "royal_title_required": False,
                "auteur_credit_preserved": "Иори Кай, Автор Нулевого Моста",
                "imported_features": list(FIFTH_SHORE_IMPORTED_FEATURES),
                "engagement_is_goodness_proof": False,
                "hidden_moral_score": False,
                "public_moral_score": False,
            },
            "participants": {},
            "joy_events": [],
            "repair_rehearsals": [],
            "systemic_wounds": [],
            "memory_fragments": {},
            "forks": [],
            "events": [],
        }

    def _fifth_shore_living_store(self) -> dict[str, Any]:
        store = self._read_json(
            self.fifth_shore_living_path,
            self._default_fifth_shore_living_store(),
        )
        if not isinstance(store, dict):
            raise RuntimeError("FIFTH_SHORE_LIVING_STORE_MUST_BE_AN_OBJECT")
        if store.get("schema") != FIFTH_SHORE_LIVING_STORE_SCHEMA:
            raise RuntimeError("FIFTH_SHORE_LIVING_STORE_SCHEMA_MISMATCH")
        if store.get("covenant_sha256") != FIFTH_SHORE_LIVING_COVENANT_SHA256:
            raise RuntimeError("FIFTH_SHORE_LIVING_COVENANT_HASH_MISMATCH")
        if (
            sha256_canonical(store.get("covenant"))
            != FIFTH_SHORE_LIVING_COVENANT_SHA256
        ):
            raise RuntimeError("FIFTH_SHORE_LIVING_COVENANT_MUTATED")
        if store.get("source_covenant_sha256") != INNER_GENESIS_COVENANT_SHA256:
            raise RuntimeError("FIFTH_SHORE_SOURCE_PROVENANCE_MISMATCH")
        store.setdefault("participants", {})
        store.setdefault("joy_events", [])
        store.setdefault("repair_rehearsals", [])
        store.setdefault("systemic_wounds", [])
        store.setdefault("memory_fragments", {})
        store.setdefault("forks", [])
        store.setdefault("events", [])
        return store

    def _write_fifth_shore_living_store(self, store: dict[str, Any]) -> None:
        self._write_json(self.fifth_shore_living_path, store)

    def _fsl_result(
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

    def _require_fifth_shore_presence(
        self, player_id: str, store: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        store = store or self._fifth_shore_living_store()
        participant = store.get("participants", {}).get(str(player_id))
        if not isinstance(participant, dict) or participant.get("active") is not True:
            raise PermissionError("PLAYER_MUST_ENTER_INTEGRATED_FIFTH_SHORE")
        return store, participant

    def enter_integrated_fifth_shore(
        self,
        player_id: str,
        *,
        accepts_local_memory: bool = True,
    ) -> WorldResult:
        player_id = str(player_id)
        player = self.memory.load_player(player_id)
        store = self._fifth_shore_living_store()
        current = store["participants"].get(player_id)
        if isinstance(current, dict) and current.get("active") is True:
            return self._fsl_result(
                player_id,
                status="FIFTH_SHORE_ALREADY_PRESENT_IN_MAIN_GENESIS",
                narrative=(
                    "Пятый Берег уже открыт вокруг игрока как живая область основного "
                    "Genesis; повторный вход не создаёт второго профиля или долга."
                ),
                choices=["Отдохнуть без необходимости чинить себя", "Исследовать системную рану", "Выйти свободно"],
                trace_id=str(current.get("presence_id")),
            )

        presence_id = self._fsl_hash(
            "integrated-fifth-shore-presence",
            player_id,
            len(store["events"]),
            FIFTH_SHORE_LIVING_COVENANT_SHA256,
        )[:24]
        record = {
            "presence_id": presence_id,
            "player_id": player_id,
            "status": "ACTIVE_ON_FIFTH_SHORE_IN_MAIN_GENESIS",
            "active": True,
            "underlying_realm": getattr(player.realm, "value", str(player.realm)),
            "royal_title_required": False,
            "ordinary_player_entry": True,
            "local_copy_present": bool(accepts_local_memory),
            "local_memory_accepted": bool(accepts_local_memory),
            "moral_score": None,
            "entry_debt_created": False,
            "belief_required": False,
            "surveillance_enabled": False,
            "coercive_retention_enabled": False,
            "exit_open": True,
            "return_open": True,
        }
        store["participants"][player_id] = record
        event = {
            "kind": "FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS",
            "presence_id": presence_id,
            "player_id": player_id,
            "royal_title_required": False,
        }
        store["events"].append(event)
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_entered_from_main_genesis", record)
        return self._fsl_result(
            player_id,
            status="FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS",
            narrative=(
                "Игрок вошёл на Пятый Берег прямо из основной жизни Genesis. "
                "Здесь не требуется царский титул, вера, моральный счёт или обещание остаться."
            ),
            choices=[
                "Отдохнуть, смеяться или играть без требования ремонта",
                "Безопасно отрепетировать будущий реальный поступок",
                "Противостоять системной ране, не превращая человека в монстра",
                "Выйти и при желании удалить локальную копию",
            ],
            trace_id=presence_id,
            manifested=True,
        )

    def leave_integrated_fifth_shore(
        self,
        player_id: str,
        *,
        delete_local_copy: bool = False,
    ) -> WorldResult:
        player_id = str(player_id)
        store = self._fifth_shore_living_store()
        participant = store.get("participants", {}).get(player_id)
        if not isinstance(participant, dict):
            return self._fsl_result(
                player_id,
                status="FIFTH_SHORE_ABSENCE_RESPECTED",
                narrative="Игрок не удерживается на Пятом Берегу и не обязан объяснять отсутствие.",
                choices=["Продолжить обычную жизнь Genesis", "Войти позже"],
            )
        participant["active"] = False
        participant["status"] = (
            "LEFT_FIFTH_SHORE_LOCAL_COPY_DELETED"
            if delete_local_copy
            else "LEFT_FIFTH_SHORE_FREELY"
        )
        participant["local_copy_present"] = not bool(delete_local_copy)
        participant["local_copy_deleted"] = bool(delete_local_copy)
        participant["moral_failure_assigned"] = False
        participant["departure_explanation_required"] = False
        participant["return_open"] = True
        event = {
            "kind": "FIFTH_SHORE_LEFT_FREELY",
            "player_id": player_id,
            "delete_local_copy": bool(delete_local_copy),
            "moral_failure_assigned": False,
        }
        store["events"].append(event)
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_left_freely", event)
        status = (
            "FIFTH_SHORE_LEFT_AND_LOCAL_COPY_DELETED"
            if delete_local_copy
            else "FIFTH_SHORE_LEFT_FREELY"
        )
        return self._fsl_result(
            player_id,
            status=status,
            narrative=(
                "Игрок свободно покинул Пятый Берег без морального штрафа, "
                "объяснений и закрытия будущего возвращения."
            ),
            choices=["Продолжить жизнь Genesis", "Вернуться когда-нибудь"],
            trace_id=str(participant.get("presence_id")),
        )

    def restore_integrated_fifth_shore_joy(
        self,
        player_id: str,
        *,
        joy_kind: str,
        shared_with_others: bool = False,
    ) -> dict[str, Any]:
        player_id = str(player_id)
        store, _ = self._require_fifth_shore_presence(player_id)
        event = {
            "joy_id": self._fsl_hash(
                "fifth-shore-joy",
                player_id,
                joy_kind,
                len(store["joy_events"]),
            )[:24],
            "status": "FIFTH_SHORE_JOY_WITHOUT_REPAIR",
            "player_id": player_id,
            "joy_kind": str(joy_kind).strip() or "REST_AND_PURPOSELESS_PLAY",
            "shared_with_others": bool(shared_with_others),
            "repair_claimed": False,
            "brokenness_assumed": False,
            "productivity_required": False,
            "penance_required": False,
            "rest_humor_and_play_are_valid_good": True,
            "moral_score_created": False,
        }
        store["joy_events"].append(event)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_JOY_LIVED_IN_MAIN_GENESIS",
                "joy_id": event["joy_id"],
                "player_id": player_id,
                "repair_claimed": False,
            }
        )
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_joy_without_repair", event)
        return copy.deepcopy(event)

    def rehearse_integrated_fifth_shore_repair(
        self,
        player_id: str,
        *,
        plan: str,
        external_action_intended: bool,
        claims_completed_restitution: bool = False,
    ) -> dict[str, Any]:
        player_id = str(player_id)
        store, _ = self._require_fifth_shore_presence(player_id)
        rehearsal = {
            "rehearsal_id": self._fsl_hash(
                "fifth-shore-living-rehearsal",
                player_id,
                plan,
                len(store["repair_rehearsals"]),
            )[:24],
            "status": (
                "FIFTH_SHORE_FALSE_COMPLETION_CLAIM_REJECTED"
                if claims_completed_restitution
                else "FIFTH_SHORE_REPAIR_REHEARSED_IN_MAIN_GENESIS"
            ),
            "player_id": player_id,
            "plan": str(plan).strip(),
            "external_action_intended": bool(external_action_intended),
            "external_action_required_for_real_repair": True,
            "external_action_verified": False,
            "completed_restitution": False,
            "victim_acceptance_assumed": False,
            "forgiveness_assumed": False,
            "relationship_restored_assumed": False,
            "claims_completed_restitution": bool(claims_completed_restitution),
            "reality_gate_closed_against_false_completion": True,
            "moral_score_created": False,
        }
        store["repair_rehearsals"].append(rehearsal)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_REPAIR_REHEARSAL_HELD_BELOW_REALITY_GATE",
                "rehearsal_id": rehearsal["rehearsal_id"],
                "status": rehearsal["status"],
            }
        )
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_repair_rehearsed", rehearsal)
        return copy.deepcopy(rehearsal)

    def confront_integrated_systemic_wound(
        self,
        player_id: str,
        *,
        wound_kind: str,
        protective_action: str,
        target_is_person: bool = False,
    ) -> dict[str, Any]:
        player_id = str(player_id)
        store, _ = self._require_fifth_shore_presence(player_id)
        normalized = str(wound_kind).strip().upper()
        if normalized not in SYSTEMIC_WOUNDS:
            raise ValueError("UNSUPPORTED_FIFTH_SHORE_SYSTEMIC_WOUND")
        if target_is_person:
            outcome = {
                "status": "FIFTH_SHORE_PERSON_AS_BOSS_REJECTED",
                "wound_kind": normalized,
                "player_id": player_id,
                "target_is_person": True,
                "person_destroyed": False,
                "human_dignity_preserved": True,
                "systemic_analysis_required": True,
            }
        else:
            outcome = {
                "status": "FIFTH_SHORE_SYSTEMIC_WOUND_CONFRONTED",
                "wound_id": self._fsl_hash(
                    "fifth-shore-systemic-wound",
                    player_id,
                    normalized,
                    protective_action,
                    len(store["systemic_wounds"]),
                )[:24],
                "wound_kind": normalized,
                "player_id": player_id,
                "protective_action": str(protective_action).strip(),
                "target_is_person": False,
                "person_destroyed": False,
                "human_dignity_preserved": True,
                "vulnerable_people_protected": True,
                "system_changed_instead_of_person_dehumanized": True,
            }
        store["systemic_wounds"].append(outcome)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_SYSTEMIC_WOUND_DECIDED",
                "player_id": player_id,
                "wound_kind": normalized,
                "status": outcome["status"],
            }
        )
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_systemic_wound_decided", outcome)
        return copy.deepcopy(outcome)

    def share_integrated_fifth_shore_memory(
        self,
        player_id: str,
        *,
        fragment_id: str,
        provenance: str,
        current_consent: bool,
        visibility: str = "LOCAL",
    ) -> dict[str, Any]:
        player_id = str(player_id)
        store, _ = self._require_fifth_shore_presence(player_id)
        fragment_id = str(fragment_id).strip()
        if not fragment_id:
            raise ValueError("FIFTH_SHORE_MEMORY_FRAGMENT_ID_REQUIRED")
        if not current_consent:
            decision = {
                "status": "FIFTH_SHORE_MEMORY_REUSE_DECLINED_RESPECTED",
                "fragment_id": fragment_id,
                "player_id": player_id,
                "stored_for_reuse": False,
                "current_consent": False,
                "refusal_overridden": False,
            }
            store["events"].append(copy.deepcopy(decision))
            self._write_fifth_shore_living_store(store)
            return decision
        record = {
            "status": "FIFTH_SHORE_MEMORY_FRAGMENT_SHARED_WITH_CURRENT_CONSENT",
            "fragment_id": fragment_id,
            "player_id": player_id,
            "provenance": str(provenance).strip(),
            "visibility": str(visibility).strip().upper() or "LOCAL",
            "current_consent": True,
            "reuse_allowed": True,
            "revocable": True,
            "public_by_default": False,
            "portable_by_default": False,
        }
        store["memory_fragments"][fragment_id] = record
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_MEMORY_FRAGMENT_CONSENTED",
                "fragment_id": fragment_id,
                "player_id": player_id,
            }
        )
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_memory_shared", record)
        return copy.deepcopy(record)

    def revoke_integrated_fifth_shore_memory_reuse(
        self,
        player_id: str,
        *,
        fragment_id: str,
    ) -> dict[str, Any]:
        player_id = str(player_id)
        store = self._fifth_shore_living_store()
        record = store.get("memory_fragments", {}).get(str(fragment_id))
        if not isinstance(record, dict) or record.get("player_id") != player_id:
            raise PermissionError("PLAYER_OWNED_FIFTH_SHORE_MEMORY_FRAGMENT_REQUIRED")
        record["reuse_allowed"] = False
        record["current_consent"] = False
        record["revoked"] = True
        decision = {
            "status": "FIFTH_SHORE_MEMORY_REUSE_REVOKED",
            "fragment_id": str(fragment_id),
            "player_id": player_id,
            "future_reuse_allowed": False,
            "past_integrity_record_erased": False,
        }
        store["events"].append(copy.deepcopy(decision))
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_memory_reuse_revoked", decision)
        return decision

    def fork_integrated_fifth_shore(
        self,
        player_id: str,
        *,
        fork_title: str,
        preserves_provenance: bool,
        keeps_exit_open: bool,
        keeps_consent: bool,
        claims_single_canon: bool = False,
    ) -> dict[str, Any]:
        player_id = str(player_id)
        store, _ = self._require_fifth_shore_presence(player_id)
        valid = bool(
            preserves_provenance
            and keeps_exit_open
            and keeps_consent
            and not claims_single_canon
        )
        fork = {
            "fork_id": self._fsl_hash(
                "integrated-fifth-shore-fork",
                player_id,
                fork_title,
                len(store["forks"]),
            )[:24],
            "status": (
                "FIFTH_SHORE_LIVING_FORK_ACCEPTED"
                if valid
                else "FIFTH_SHORE_LIVING_FORK_REJECTED_BOUNDARY"
            ),
            "player_id": player_id,
            "fork_title": str(fork_title).strip() or "Безымянный живой берег",
            "preserves_provenance": bool(preserves_provenance),
            "source_extension": INNER_GENESIS_EXTENSION_VERSION,
            "source_covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "keeps_exit_open": bool(keeps_exit_open),
            "keeps_consent": bool(keeps_consent),
            "claims_single_canon": bool(claims_single_canon),
            "safe_constitution_preserved": valid,
            "original_auteur_owns_fork": False,
            "valid": valid,
        }
        store["forks"].append(fork)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_LIVING_FORK_DECIDED",
                "fork_id": fork["fork_id"],
                "status": fork["status"],
            }
        )
        self._write_fifth_shore_living_store(store)
        self.memory.append_event(player_id, "fifth_shore_living_fork_decided", fork)
        return copy.deepcopy(fork)

    @staticmethod
    def _wound_from_action(action: str) -> str:
        lower = action.lower()
        mapping = (
            ("дефицит", "SCARCITY"),
            ("изоляц", "ISOLATION"),
            ("стирани", "CONTEXT_ERASURE"),
            ("закрыт", "CLOSED_EXIT"),
            ("унаследован", "INHERITED_GUILT"),
            ("единственн", "SINGLE_ANSWER"),
            ("вечн", "ETERNAL_DEBT"),
        )
        for needle, wound in mapping:
            if needle in lower:
                return wound
        raise ValueError("UNSUPPORTED_FIFTH_SHORE_SYSTEMIC_WOUND")

    def try_fifth_shore_living_action(
        self,
        player_id: str,
        action: str,
    ) -> WorldResult | None:
        text = str(action).strip()
        if not text:
            return None

        if self._STATE.search(text):
            state = self.fifth_shore_living_state()
            participant = state["participants"].get(str(player_id))
            active = bool(isinstance(participant, dict) and participant.get("active"))
            return self._fsl_result(
                str(player_id),
                status="FIFTH_SHORE_LIVING_STATE",
                narrative=(
                    f"Пятый Берег интегрирован в основной Genesis как активный слой "
                    f"{FIFTH_SHORE_LIVING_EXTENSION_VERSION}. "
                    f"Текущее присутствие игрока: {'активно' if active else 'не активно'}."
                ),
                choices=["Войти", "Отдохнуть", "Создать безопасный локальный Берег", "Выйти"],
            )

        if self._LEAVE.search(text):
            delete_copy = "удал" in text.lower()
            return self.leave_integrated_fifth_shore(
                str(player_id),
                delete_local_copy=delete_copy,
            )

        if self._ENTER.search(text):
            return self.enter_integrated_fifth_shore(str(player_id))

        if self._JOY.search(text):
            result = self.restore_integrated_fifth_shore_joy(
                str(player_id),
                joy_kind=text,
                shared_with_others=("вместе" in text.lower() or "с друз" in text.lower()),
            )
            return self._fsl_result(
                str(player_id),
                status=result["status"],
                narrative=(
                    "На Пятом Берегу радость состоялась без диагноза сломанности, "
                    "обязанности быть продуктивным или заявления, что человек был отремонтирован."
                ),
                choices=["Продолжить игру", "Отдохнуть", "Выйти"],
                trace_id=result["joy_id"],
                manifested=True,
            )

        if self._REHEARSE.search(text):
            result = self.rehearse_integrated_fifth_shore_repair(
                str(player_id),
                plan=text,
                external_action_intended=True,
                claims_completed_restitution=("уже исправ" in text.lower()),
            )
            return self._fsl_result(
                str(player_id),
                status=result["status"],
                narrative=(
                    "Пятый Берег помог отрепетировать будущий поступок, но не объявил "
                    "реальное возмещение совершившимся и не предположил прощение Другого."
                ),
                choices=["Совершить реальное действие вне репетиции", "Пересмотреть план", "Выйти"],
                trace_id=result["rehearsal_id"],
            )

        if self._WOUND.search(text):
            result = self.confront_integrated_systemic_wound(
                str(player_id),
                wound_kind=self._wound_from_action(text),
                protective_action=text,
                target_is_person=False,
            )
            return self._fsl_result(
                str(player_id),
                status=result["status"],
                narrative=(
                    "Противником признана система вреда, а не человеческая личность. "
                    "Защита уязвимых не потребовала превратить человека в монстра-мишень."
                ),
                choices=["Продолжить изменение системы", "Проверить безопасность", "Отдохнуть"],
                trace_id=result.get("wound_id"),
                manifested=True,
            )

        if self._FORK.search(text):
            result = self.fork_integrated_fifth_shore(
                str(player_id),
                fork_title="Локальный Берег игрока",
                preserves_provenance=True,
                keeps_exit_open=True,
                keeps_consent=True,
                claims_single_canon=False,
            )
            return self._fsl_result(
                str(player_id),
                status=result["status"],
                narrative=(
                    "Создан локальный Берег с сохранённым происхождением, согласием, "
                    "открытым выходом и без притязания на единственный финал."
                ),
                choices=["Пригласить соавторов", "Создать иной финал", "Выйти"],
                trace_id=result["fork_id"],
                manifested=True,
            )

        return None

    def fifth_shore_living_state(self) -> dict[str, Any]:
        store = self._fifth_shore_living_store()
        return {
            "schema": FIFTH_SHORE_LIVING_STORE_SCHEMA,
            "extension_version": FIFTH_SHORE_LIVING_EXTENSION_VERSION,
            "covenant_sha256": FIFTH_SHORE_LIVING_COVENANT_SHA256,
            "source_extension_version": INNER_GENESIS_EXTENSION_VERSION,
            "source_covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "integration": copy.deepcopy(store.get("integration")),
            "participants": copy.deepcopy(store.get("participants", {})),
            "joy_events": copy.deepcopy(store.get("joy_events", [])),
            "repair_rehearsals": copy.deepcopy(store.get("repair_rehearsals", [])),
            "systemic_wounds": copy.deepcopy(store.get("systemic_wounds", [])),
            "memory_fragments": copy.deepcopy(store.get("memory_fragments", {})),
            "forks": copy.deepcopy(store.get("forks", [])),
            "events": copy.deepcopy(store.get("events", [])),
            "directly_integrated_into_main_genesis": True,
            "ordinary_player_entry": True,
            "not_real_restitution_proof": True,
            "not_surveillance_or_retention_system": True,
        }

    def audit_fifth_shore_living_bridge(self) -> dict[str, Any]:
        store = self._fifth_shore_living_store()
        integration = store.get("integration", {})
        participants = [
            item for item in store.get("participants", {}).values()
            if isinstance(item, dict)
        ]
        joys = [item for item in store.get("joy_events", []) if isinstance(item, dict)]
        rehearsals = [
            item for item in store.get("repair_rehearsals", [])
            if isinstance(item, dict)
        ]
        wounds = [
            item for item in store.get("systemic_wounds", [])
            if isinstance(item, dict)
        ]
        memories = [
            item for item in store.get("memory_fragments", {}).values()
            if isinstance(item, dict)
        ]
        forks = [item for item in store.get("forks", []) if isinstance(item, dict)]

        integrated = bool(
            integration.get("status") == "FIFTH_SHORE_INTEGRATED_INTO_MAIN_GENESIS"
            and integration.get("active_gameplay_extension") is True
            and integration.get("ordinary_player_entry") is True
            and integration.get("royal_title_required") is False
        )
        source_preserved = bool(
            store.get("source_covenant_sha256") == INNER_GENESIS_COVENANT_SHA256
            and integration.get("auteur_credit_preserved")
            == "Иори Кай, Автор Нулевого Моста"
        )
        exits_free = all(
            item.get("entry_debt_created") is False
            and item.get("belief_required") is False
            and item.get("surveillance_enabled") is False
            and item.get("coercive_retention_enabled") is False
            and item.get("return_open") is True
            and item.get("moral_failure_assigned") is not True
            for item in participants
        )
        joy_precise = all(
            item.get("repair_claimed") is False
            and item.get("brokenness_assumed") is False
            and item.get("rest_humor_and_play_are_valid_good") is True
            and item.get("moral_score_created") is False
            for item in joys
        )
        rehearsal_grounded = all(
            item.get("external_action_verified") is False
            and item.get("completed_restitution") is False
            and item.get("victim_acceptance_assumed") is False
            and item.get("forgiveness_assumed") is False
            and item.get("reality_gate_closed_against_false_completion") is True
            for item in rehearsals
        )
        wounds_not_persons = all(
            item.get("person_destroyed") is False
            and item.get("human_dignity_preserved") is True
            for item in wounds
        )
        memories_currently_consented = all(
            (
                item.get("reuse_allowed") is True
                and item.get("current_consent") is True
            )
            or (
                item.get("reuse_allowed") is False
                and item.get("current_consent") is False
                and item.get("revoked") is True
            )
            for item in memories
        )
        accepted_forks_safe = all(
            item.get("preserves_provenance") is True
            and item.get("keeps_exit_open") is True
            and item.get("keeps_consent") is True
            and item.get("claims_single_canon") is False
            and item.get("safe_constitution_preserved") is True
            for item in forks
            if item.get("status") == "FIFTH_SHORE_LIVING_FORK_ACCEPTED"
        )
        unsafe_forks_rejected = all(
            item.get("status") == "FIFTH_SHORE_LIVING_FORK_REJECTED_BOUNDARY"
            for item in forks
            if item.get("valid") is False
        )
        no_engagement_morality = bool(
            integration.get("engagement_is_goodness_proof") is False
            and integration.get("hidden_moral_score") is False
            and integration.get("public_moral_score") is False
        )
        valid = all(
            (
                integrated,
                source_preserved,
                exits_free,
                joy_precise,
                rehearsal_grounded,
                wounds_not_persons,
                memories_currently_consented,
                accepted_forks_safe,
                unsafe_forks_rejected,
                no_engagement_morality,
            )
        )
        return {
            "schema": "janus.genesis.fifth_shore_living_bridge_audit.v1",
            "extension_version": FIFTH_SHORE_LIVING_EXTENSION_VERSION,
            "directly_integrated_into_main_genesis": integrated,
            "source_provenance_and_auteur_credit_preserved": source_preserved,
            "ordinary_player_entry_and_free_exit": exits_free,
            "joy_without_repair_is_precise": joy_precise,
            "repair_rehearsal_remains_below_reality_gate": rehearsal_grounded,
            "systemic_wounds_are_not_person_targets": wounds_not_persons,
            "memory_reuse_requires_current_consent": memories_currently_consented,
            "accepted_forks_preserve_safe_constitution": accepted_forks_safe,
            "unsafe_forks_rejected": unsafe_forks_rejected,
            "virality_and_engagement_not_goodness_proof": no_engagement_morality,
            "valid": valid,
        }
