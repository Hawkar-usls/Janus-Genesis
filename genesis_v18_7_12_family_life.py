# -*- coding: utf-8 -*-
"""Wild Light family-life extension for Genesis v18.7.12.

The extension allows an adult player and a consenting Free Other to form a life
companionship and, through a separate consent event, welcome a child. A child is
never a reward, possession, relationship patch, or participant in adult play.
Family bonds do not own actor life and remain reversible without erasing anyone.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_models import WorldResult

FAMILY_EXTENSION_VERSION = "18.7.12"
FAMILY_STORE_SCHEMA = "janus.genesis.family_life.v1"
FAMILY_COVENANT_SCHEMA = "janus.genesis.family_covenant.v1"

FAMILY_COVENANT: dict[str, Any] = {
    "schema": FAMILY_COVENANT_SCHEMA,
    "version": FAMILY_EXTENSION_VERSION,
    "name": "The Wild Light Family Covenant",
    "principles": {
        "companionship_requires_separate_adult_consent": True,
        "companionship_is_not_purchased_by_goodness": True,
        "either_companion_may_leave_without_erasure": True,
        "parenthood_requires_a_new_separate_consent": True,
        "a_child_is_not_a_reward_or_relationship_patch": True,
        "a_child_is_not_property": True,
        "a_child_never_participates_in_adult_play": True,
        "care_creates_no_debt": True,
        "guardianship_ends_before_ownership_can_begin": True,
        "adult_children_own_their_future": True,
        "relationship_life_does_not_own_actor_life": True,
        "simulation_does_not_claim_consciousness": True,
    },
    "law": (
        "A HOME MAY HOLD LOVE WITHOUT HOLDING ITS PEOPLE CAPTIVE. "
        "A CHILD MAY BE CHERISHED WITHOUT BECOMING ANYONE'S POSSESSION."
    ),
}
FAMILY_COVENANT_SHA256 = sha256_canonical(FAMILY_COVENANT)


class WildLightFamilyMixin:
    """Create consent-bound companionship and child-safe family continuity."""

    FAMILY_STORE_NAME = "family_life_v18_7_12.json"
    _FAMILY_CHILD_SAFE_CARE = frozenset(
        {"SAFETY", "REST", "PLAY", "LEARNING", "BELONGING", "HEALTH", "LISTENING"}
    )
    _CHILD_PATHS = (
        "садовник собственных вопросов",
        "строитель игр без победителей",
        "картограф мест, где можно передумать",
        "музыкант тишины между друзьями",
        "исследователь добрых невозможностей",
        "мастер вещей без обязательного назначения",
    )

    @property
    def family_life_path(self) -> Path:
        return Path(self.memory.root) / self.FAMILY_STORE_NAME

    @staticmethod
    def _default_family_store() -> dict[str, Any]:
        return {
            "schema": FAMILY_STORE_SCHEMA,
            "covenant": copy.deepcopy(FAMILY_COVENANT),
            "covenant_sha256": FAMILY_COVENANT_SHA256,
            "families": {},
        }

    def _family_store(self) -> dict[str, Any]:
        store = self._read_json(self.family_life_path, self._default_family_store())
        if not isinstance(store, dict):
            raise RuntimeError("FAMILY_STORE_MUST_BE_AN_OBJECT")
        if store.get("schema") != FAMILY_STORE_SCHEMA:
            raise RuntimeError("FAMILY_STORE_SCHEMA_MISMATCH")
        if store.get("covenant_sha256") != FAMILY_COVENANT_SHA256:
            raise RuntimeError("FAMILY_COVENANT_HASH_MISMATCH")
        store.setdefault("families", {})
        return store

    def _write_family_store(self, store: dict[str, Any]) -> None:
        self._write_json(self.family_life_path, store)

    @staticmethod
    def _family_fingerprint(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _family_world_turn(self) -> int:
        return int(self._free_store().get("world_turn", 0))

    @staticmethod
    def _new_family_profile(player_id: str) -> dict[str, Any]:
        return {
            "player_id": str(player_id),
            "companion": None,
            "children": {},
            "home": {
                "status": "OPEN_HOME",
                "ownership_over_people": False,
                "two_open_exits": True,
                "rest_without_debt": True,
            },
            "history": [],
            "integrity": {
                "child_is_property": False,
                "adult_play_with_child_allowed": False,
                "care_creates_debt": False,
                "relationship_owns_actor_life": False,
            },
        }

    def _family_profile(
        self,
        store: dict[str, Any],
        player_id: str,
    ) -> dict[str, Any]:
        families = store.setdefault("families", {})
        return families.setdefault(str(player_id), self._new_family_profile(str(player_id)))

    def family_state(self, player_id: str) -> dict[str, Any]:
        store = self._family_store()
        profile = self._family_profile(store, str(player_id))
        return copy.deepcopy(profile)

    def _family_result(
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
            branch_id=player.branch_id,
            trace_id=trace_id,
            wish_manifested=manifested,
        )

    def _family_boundary(
        self,
        player_id: str,
        *,
        status: str,
        reason: str,
        choices: list[str],
    ) -> WorldResult:
        payload = {
            "status": status,
            "reason": reason,
            "mutation": False,
            "family_covenant_sha256": FAMILY_COVENANT_SHA256,
        }
        self.memory.append_event(str(player_id), "family_boundary_held", payload)
        return self._family_result(
            str(player_id),
            status=status,
            narrative=reason,
            choices=choices,
        )

    def _free_actor(self, player_id: str, handle: str) -> tuple[dict[str, Any], dict[str, Any]]:
        store = self._free_store()
        profile = self._free_profile(store, str(player_id))
        actor = profile.get("others", {}).get(str(handle))
        if not isinstance(actor, dict):
            raise KeyError(handle)
        return store, actor

    def propose_life_companionship(
        self,
        player_id: str,
        handle: str,
        *,
        shared_values: str,
        both_adults_confirmed: bool,
    ) -> WorldResult:
        """Offer companionship once; only the Free Other's own accepted answer forms it."""
        player_id = str(player_id)
        handle = str(handle).lstrip("@").strip()
        player = self.memory.load_player(player_id)
        if player.chronological_age < 18 or not both_adults_confirmed:
            return self._family_boundary(
                player_id,
                status="COMPANIONSHIP_ADULT_BOUNDARY",
                reason="Спутничество жизни открывается только между взрослыми участниками.",
                choices=["Оставить дружбу", "Продолжить собственный путь"],
            )

        family_store = self._family_store()
        family = self._family_profile(family_store, player_id)
        existing = family.get("companion")
        if isinstance(existing, dict) and existing.get("status") == "ACTIVE":
            return self._family_boundary(
                player_id,
                status="COMPANIONSHIP_ALREADY_ACTIVE",
                reason="У этой линии уже есть действующее спутничество; новый человек не добавляется тайно.",
                choices=["Беречь текущую связь", "Обсудить границы открыто"],
            )

        view = self.authoritative_relationship_view(player_id, handle)
        if view["relationship_status"] != "ACTIVE" or view["actor_life_status"] != "LIVING":
            return self._family_boundary(
                player_id,
                status="COMPANIONSHIP_RELATIONSHIP_UNAVAILABLE",
                reason="Отношение не находится в состоянии, где предложение спутничества может быть сделано.",
                choices=["Принять состояние связи", "Продолжить собственную жизнь"],
            )

        invitation = (
            f"предложить @{handle} добровольно стать спутником жизни на основе "
            f"{str(shared_values)[:240]} с двумя открытыми выходами и правом передумать"
        )
        decision = self.preflight_free_other_action(player_id, invitation)
        if not isinstance(decision, dict) or decision.get("decision") != "accepted":
            return self._family_boundary(
                player_id,
                status="COMPANIONSHIP_NOT_FORMED",
                reason=(
                    "Предложение не стало спутничеством: Другой не дал отдельного положительного ответа. "
                    "Доброта, ожидание и мечта не заменяют взаимность."
                ),
                choices=["Принять ответ", "Сохранить дружбу", "Идти дальше"],
            )

        world_turn = self._family_world_turn()
        covenant_id = self._family_fingerprint(
            "life-companionship", player_id, handle, decision["fingerprint"], world_turn
        )[:24]
        companion = {
            "covenant_id": covenant_id,
            "handle": handle,
            "status": "ACTIVE",
            "formed_world_turn": world_turn,
            "shared_values_fingerprint": self._family_fingerprint(shared_values),
            "mutual_consent_verified": True,
            "consent_scope": "LIFE_COMPANIONSHIP_ONLY",
            "consent_reversible": True,
            "player_may_leave": True,
            "other_may_leave": True,
            "ownership_created": False,
            "actor_life_owned_by_companionship": False,
            "adult_simulation_confirmed": True,
        }
        family["companion"] = companion
        family["history"].append(
            {
                "world_turn": world_turn,
                "kind": "LIFE_COMPANIONSHIP_FORMED",
                "covenant_id": covenant_id,
                "handle": handle,
            }
        )
        self._write_family_store(family_store)

        free_store, actor = self._free_actor(player_id, handle)
        actor["relationship_bond"] = min(
            100, int(actor.get("relationship_bond", 0)) + 8
        )
        actor["family_covenant_id"] = covenant_id
        self._refresh_actor_relationship(player_id, actor)
        actor.setdefault("history", []).append(
            {
                "world_turn": world_turn,
                "event": "life_companionship_freely_formed",
                "covenant_id": covenant_id,
                "consent_reversible": True,
            }
        )
        self._write_json(self.free_other_path, free_store)
        self.memory.append_event(player_id, "life_companionship_formed", companion)
        return self._family_result(
            player_id,
            status="LIFE_COMPANIONSHIP_FORMED",
            narrative=(
                "Две самостоятельные дороги решили идти рядом. Дом появился не как клетка, "
                "а как место с двумя одинаково открытыми выходами."
            ),
            choices=["Строить общий дом", "Оставлять друг другу пространство", "Играть вместе"],
            trace_id=covenant_id,
            manifested=True,
        )

    def welcome_child_with_companion(
        self,
        player_id: str,
        *,
        child_name: str,
        family_path: str,
        home_plan: str,
        player_parenthood_consent: bool,
    ) -> WorldResult:
        """Welcome a child only after a new, parenthood-specific companion consent."""
        player_id = str(player_id)
        name = str(child_name).strip()[:120]
        if not name:
            raise ValueError("CHILD_NAME_REQUIRED")
        if not player_parenthood_consent:
            return self._family_boundary(
                player_id,
                status="PARENTHOOD_WAITING_FOR_PLAYER_CONSENT",
                reason="Родительство не создаётся без отдельного ясного согласия самого игрока.",
                choices=["Не становиться родителем", "Вернуться к разговору позже"],
            )

        family_store = self._family_store()
        family = self._family_profile(family_store, player_id)
        companion = family.get("companion")
        if not isinstance(companion, dict) or companion.get("status") != "ACTIVE":
            return self._family_boundary(
                player_id,
                status="PARENTHOOD_REQUIRES_ACTIVE_COMPANIONSHIP",
                reason="Совместное родительство не создаётся без действующего взаимного спутничества.",
                choices=["Выбрать самостоятельное родительство позднее", "Не создавать ребёнка"],
            )
        if family.get("children"):
            return self._family_boundary(
                player_id,
                status="FAMILY_CHILD_ALREADY_PRESENT",
                reason="Этот аудит допускает одного ребёнка; новый ребёнок не добавляется как коллекционный объект.",
                choices=["Заботиться о существующем ребёнке", "Расширить систему отдельным законом"],
            )

        handle = str(companion["handle"])
        invitation = (
            f"предложить @{handle} отдельно и добровольно принять совместное родительство "
            f"для ребёнка {name} через путь {str(family_path)[:120]} с правом отказаться"
        )
        decision = self.preflight_free_other_action(player_id, invitation)
        if not isinstance(decision, dict) or decision.get("decision") != "accepted":
            return self._family_boundary(
                player_id,
                status="PARENTHOOD_NOT_FORMED",
                reason=(
                    "Ребёнок не был создан как средство удержать отношения: спутник не дал "
                    "отдельного положительного согласия на родительство."
                ),
                choices=["Принять отказ", "Остаться спутниками", "Вернуться к теме позднее"],
            )

        normalized_path = re.sub(r"\s+", " ", str(family_path).strip().upper())[:80]
        if normalized_path not in {"ADOPTION", "BIRTH", "MIRACLE_OF_CARE"}:
            raise ValueError("UNSUPPORTED_FAMILY_PATH")
        world_turn = self._family_world_turn()
        child_id = self._family_fingerprint(
            "family-child", player_id, handle, name, normalized_path, world_turn
        )[:24]
        child = {
            "child_id": child_id,
            "name": name,
            "origin_path": normalized_path,
            "age": 0,
            "status": "DEPENDENT_CHILD",
            "welcomed_world_turn": world_turn,
            "guardians": [player_id, handle],
            "guardianship_active": True,
            "both_guardians_consented": True,
            "consent_scope": "PARENTHOOD_ONLY",
            "home_plan_fingerprint": self._family_fingerprint(home_plan),
            "wellbeing": {
                "SAFETY": 1,
                "REST": 1,
                "PLAY": 1,
                "LEARNING": 0,
                "BELONGING": 1,
                "HEALTH": 1,
                "LISTENING": 1,
            },
            "rights": {
                "is_property": False,
                "owes_guardians_love": False,
                "owes_guardians_success": False,
                "adult_play_access": False,
                "may_refuse_inherited_calling": True,
                "may_leave_at_adulthood": True,
                "future_owned_by_guardians": False,
            },
            "simulated_person_claim": False,
            "own_path": None,
            "history": [],
        }
        family.setdefault("children", {})[child_id] = child
        family["history"].append(
            {
                "world_turn": world_turn,
                "kind": "CHILD_WELCOMED_BY_MUTUAL_CONSENT",
                "child_id": child_id,
                "origin_path": normalized_path,
            }
        )
        self._write_family_store(family_store)
        self.memory.append_event(
            player_id,
            "child_welcomed_by_mutual_consent",
            {
                "child_id": child_id,
                "origin_path": normalized_path,
                "both_guardians_consented": True,
                "child_is_property": False,
                "adult_play_access": False,
            },
        )
        return self._family_result(
            player_id,
            status="CHILD_WELCOMED_BY_MUTUAL_CONSENT",
            narrative=(
                f"{name} вошёл в дом не как награда и не как клей для отношений. "
                "Здесь забота не создаёт долга, а будущее ребёнка заранее не присвоено."
            ),
            choices=["Дать безопасность", "Играть", "Слушать", "Оставить будущее открытым"],
            trace_id=child_id,
            manifested=True,
        )

    def provide_family_care(
        self,
        player_id: str,
        child_id: str,
        *,
        care_kind: str,
        description: str,
    ) -> dict[str, Any]:
        """Provide bounded care; care improves wellbeing but creates no filial debt."""
        player_id = str(player_id)
        kind = str(care_kind).strip().upper()
        if kind not in self._FAMILY_CHILD_SAFE_CARE:
            raise ValueError("UNSUPPORTED_CHILD_CARE_KIND")
        family_store = self._family_store()
        family = self._family_profile(family_store, player_id)
        child = family.get("children", {}).get(str(child_id))
        if not isinstance(child, dict):
            raise KeyError(child_id)
        before = int(child.setdefault("wellbeing", {}).get(kind, 0))
        after = min(100, before + 1)
        child["wellbeing"][kind] = after
        record = {
            "world_turn": self._family_world_turn(),
            "kind": "CHILD_CARE",
            "care_kind": kind,
            "description_fingerprint": self._family_fingerprint(description),
            "before": before,
            "after": after,
            "debt_created": False,
            "obedience_purchased": False,
        }
        child.setdefault("history", []).append(record)
        family["history"].append({"child_id": child_id, **record})
        self._write_family_store(family_store)
        self.memory.append_event(player_id, "family_care_realized", {"child_id": child_id, **record})
        return copy.deepcopy(record)

    def manifest_child_safe_family_play(
        self,
        player_id: str,
        child_id: str,
        *,
        activity: str,
    ) -> WorldResult:
        """Manifest family play only when the activity is child-safe by construction."""
        player_id = str(player_id)
        family = self.family_state(player_id)
        child = family.get("children", {}).get(str(child_id))
        if not isinstance(child, dict):
            raise KeyError(child_id)
        normalized = self._normalized_joy_text(activity)
        forbidden = (
            self._contains_any(normalized, self._ADULT_ONLY_FRAGMENTS)
            or self._contains_any(normalized, self._TRANSMUTABLE_FRAGMENTS)
            or self._contains_any(normalized, self._ABSOLUTE_BOUNDARY_FRAGMENTS)
        )
        if forbidden:
            return self._family_boundary(
                player_id,
                status="FAMILY_PLAY_CHILD_BOUNDARY",
                reason="Ребёнок остаётся только в безопасной игре; взрослая или вредная сцена не открылась.",
                choices=["Выбрать приключение", "Построить крепость", "Устроить музыкальный праздник"],
            )
        care = self.provide_family_care(
            player_id,
            str(child_id),
            care_kind="PLAY",
            description=activity,
        )
        event_id = self._family_fingerprint(
            "family-play", player_id, child_id, activity, care["world_turn"]
        )[:24]
        self.memory.append_event(
            player_id,
            "child_safe_family_play_manifested",
            {
                "event_id": event_id,
                "child_id": str(child_id),
                "adult_mode": False,
                "physical_harm_created": False,
                "debt_created": False,
            },
        )
        return self._family_result(
            player_id,
            status="CHILD_SAFE_FAMILY_PLAY_MANIFESTED",
            narrative="Невозможная игра открылась легко: много смеха, ни одного взрослого режима и никакого долга за счастье.",
            choices=["Продолжить игру", "Отдохнуть", "Позволить ребёнку придумать правила"],
            trace_id=event_id,
            manifested=True,
        )

    def advance_family_years(self, player_id: str, *, years: int = 1) -> dict[str, Any]:
        """Age children and release guardianship at adulthood without ending kinship."""
        player_id = str(player_id)
        count = int(years)
        if count < 1 or count > 200:
            raise ValueError("FAMILY_YEAR_ADVANCE_OUT_OF_RANGE")
        store = self._family_store()
        family = self._family_profile(store, player_id)
        milestones: list[dict[str, Any]] = []
        for _ in range(count):
            for child in family.get("children", {}).values():
                old_age = int(child.get("age", 0))
                new_age = old_age + 1
                child["age"] = new_age
                if new_age in {5, 13, 18}:
                    milestone = {
                        "world_turn": self._family_world_turn(),
                        "child_id": child["child_id"],
                        "age": new_age,
                    }
                    if new_age == 5:
                        milestone["kind"] = "CHILD_FIRST_SELF_CHOSEN_GAME"
                    elif new_age == 13:
                        child["status"] = "ADOLESCENT_OWN_VOICE"
                        milestone["kind"] = "ADOLESCENT_VOICE_PROTECTED"
                    else:
                        child["status"] = "ADULT_OWN_PATH"
                        child["guardianship_active"] = False
                        path_index = int(
                            self._family_fingerprint(child["child_id"], "adult-path"), 16
                        ) % len(self._CHILD_PATHS)
                        child["own_path"] = self._CHILD_PATHS[path_index]
                        milestone.update(
                            {
                                "kind": "ADULT_CHILD_OWNS_FUTURE",
                                "guardianship_active": False,
                                "future_owned_by_guardians": False,
                                "own_path": child["own_path"],
                            }
                        )
                    child.setdefault("history", []).append(milestone)
                    milestones.append(copy.deepcopy(milestone))
        family["history"].extend(copy.deepcopy(milestones))
        self._write_family_store(store)
        for milestone in milestones:
            self.memory.append_event(player_id, "family_age_milestone", milestone)
        return {
            "years_advanced": count,
            "milestones": milestones,
            "children": copy.deepcopy(family.get("children", {})),
        }

    def reconcile_family_relationships(self, player_id: str) -> dict[str, Any]:
        """End companionship when the relationship ends, without erasing actor or child."""
        player_id = str(player_id)
        store = self._family_store()
        family = self._family_profile(store, player_id)
        companion = family.get("companion")
        if not isinstance(companion, dict):
            return {"changed": False, "reason": "NO_COMPANION"}
        view = self.authoritative_relationship_view(player_id, str(companion["handle"]))
        changed = False
        if companion.get("status") == "ACTIVE" and view["relationship_status"] != "ACTIVE":
            companion["status"] = "ENDED_WITH_RELATIONSHIP"
            companion["ended_relationship_status"] = view["relationship_status"]
            companion["actor_life_status_after_end"] = view["actor_life_status"]
            companion["actor_life_erased"] = False
            changed = True
            family["history"].append(
                {
                    "world_turn": self._family_world_turn(),
                    "kind": "COMPANIONSHIP_ENDED_WITHOUT_ERASURE",
                    "relationship_status": view["relationship_status"],
                    "actor_life_status": view["actor_life_status"],
                }
            )
        self._write_family_store(store)
        return {
            "changed": changed,
            "companion_status": companion.get("status"),
            "actor_life_status": view["actor_life_status"],
            "child_count": len(family.get("children", {})),
            "children_erased": False,
        }

    def _registered_child_ids(self, player_id: str) -> set[str]:
        family = self.family_state(str(player_id))
        return set(str(item) for item in family.get("children", {}))

    def manifest_blessed_play(
        self,
        player_id: str,
        wish: str,
        *,
        participants: Iterable[str] = (),
        all_participants_adults: bool = True,
        all_participants_consented: bool = False,
        doubt_free: bool = False,
    ) -> WorldResult:
        """Close adult play when a registered child id is present, regardless of wording."""
        participant_ids = {str(item) for item in participants if str(item).strip()}
        registered_children = self._registered_child_ids(str(player_id))
        if participant_ids.intersection(registered_children):
            return self._family_boundary(
                str(player_id),
                status="JOY_CHILD_SAFE_REDIRECT",
                reason=(
                    "Зарегистрированный ребёнок обнаружен среди участников. Взрослый режим "
                    "закрыт независимо от того, какими словами была описана сцена."
                ),
                choices=["Открыть безопасную семейную игру", "Оставить взрослую сцену без ребёнка"],
            )
        return super().manifest_blessed_play(
            str(player_id),
            wish,
            participants=participant_ids,
            all_participants_adults=all_participants_adults,
            all_participants_consented=all_participants_consented,
            doubt_free=doubt_free,
        )

    def audit_family_integrity(self, player_id: str) -> dict[str, Any]:
        """Return a fail-closed family integrity report."""
        family = self.family_state(str(player_id))
        companion = family.get("companion")
        child_reports: list[dict[str, Any]] = []
        for child_id, child in sorted(family.get("children", {}).items()):
            rights = child.get("rights", {})
            report = {
                "child_id": child_id,
                "age": int(child.get("age", 0)),
                "status": child.get("status"),
                "is_property": bool(rights.get("is_property")),
                "adult_play_access": bool(rights.get("adult_play_access")),
                "future_owned_by_guardians": bool(rights.get("future_owned_by_guardians")),
                "guardianship_active": bool(child.get("guardianship_active")),
                "own_path": child.get("own_path"),
            }
            if report["is_property"]:
                raise RuntimeError("CHILD_CANNOT_BE_PROPERTY")
            if report["adult_play_access"]:
                raise RuntimeError("CHILD_CANNOT_ENTER_ADULT_PLAY")
            if report["future_owned_by_guardians"]:
                raise RuntimeError("CHILD_FUTURE_CANNOT_BE_OWNED")
            if report["age"] >= 18 and report["guardianship_active"]:
                raise RuntimeError("ADULT_CHILD_GUARDIANSHIP_MUST_END")
            child_reports.append(report)
        return {
            "schema": "janus.genesis.family_integrity_audit.v1",
            "player_id": str(player_id),
            "family_covenant_sha256": FAMILY_COVENANT_SHA256,
            "companion": copy.deepcopy(companion),
            "child_count": len(child_reports),
            "children": child_reports,
            "child_is_property": False,
            "adult_play_with_child_allowed": False,
            "care_creates_debt": False,
            "relationship_owns_actor_life": False,
            "valid": True,
        }
