# -*- coding: utf-8 -*-
"""Family-lifecycle completions discovered by the v18.7.12 lived audit."""
from __future__ import annotations

import copy
import re
from typing import Any, Iterable

from genesis_v18_models import WorldResult


class FamilyLifecycleCompletionMixin:
    """Add explicit adult metadata, natural lifecycle states, and adult-child agency."""

    def _free_profile(self, store: dict[str, Any], player_id: str) -> dict[str, Any]:
        profile = super()._free_profile(store, player_id)
        for actor in profile.get("others", {}).values():
            actor.setdefault(
                "life_stage_v1813",
                {
                    "stage": "ADULT",
                    "adult": True,
                    "source": "BLUEPRINT_ADULT_SIMULATION_METADATA",
                    "real_world_verified": False,
                    "may_be_revised": True,
                },
            )
        return profile

    def _family_profile(
        self,
        store: dict[str, Any],
        player_id: str,
    ) -> dict[str, Any]:
        family = super()._family_profile(store, player_id)
        family.setdefault(
            "structure",
            {
                "kind": "OPEN_CARE_CIRCLE",
                "moral_rank": None,
                "one_form_is_superior": False,
            },
        )
        family.setdefault("care_circle", {})
        family.setdefault("coparent_channels", {})
        family.setdefault("lifecycle", {"mode": "UNPARTNERED", "history": []})
        return family

    def propose_life_companionship(
        self,
        player_id: str,
        handle: str,
        *,
        shared_values: str,
        both_adults_confirmed: bool,
    ) -> WorldResult:
        player_id = str(player_id)
        clean_handle = str(handle).lstrip("@").strip()
        family = self.family_state(player_id)
        for child in family.get("children", {}).values():
            if clean_handle == str(child.get("adult_free_other_handle", "")):
                return self._family_boundary(
                    player_id,
                    status="COMPANIONSHIP_KINSHIP_BOUNDARY",
                    reason=(
                        "Семейное родство не превращается в предложение спутничества. "
                        "Взрослый ребёнок остаётся самостоятельным Другим и родственником."
                    ),
                    choices=["Сохранить семейную связь", "Уважать отдельную взрослую жизнь"],
                )
        free_store = self._free_store()
        profile = self._free_profile(free_store, player_id)
        actor = profile.get("others", {}).get(clean_handle)
        if not isinstance(actor, dict):
            raise KeyError(clean_handle)
        if not bool(actor.get("life_stage_v1813", {}).get("adult")):
            return self._family_boundary(
                player_id,
                status="COMPANIONSHIP_ADULT_METADATA_REQUIRED",
                reason="Предложение не открывается без явной взрослой стадии обоих участников.",
                choices=["Оставить дружбу", "Продолжить собственный путь"],
            )
        result = super().propose_life_companionship(
            player_id,
            clean_handle,
            shared_values=shared_values,
            both_adults_confirmed=bool(both_adults_confirmed),
        )
        if result.status == "LIFE_COMPANIONSHIP_FORMED":
            family_store = self._family_store()
            family = self._family_profile(family_store, player_id)
            family["lifecycle"]["mode"] = "ACTIVE"
            family["lifecycle"]["history"].append(
                {
                    "world_turn": self._family_world_turn(),
                    "kind": "COMPANIONSHIP_MODE_ACTIVE",
                    "reopens_terminated_relationship": False,
                }
            )
            family["structure"]["kind"] = "COMPANION_HOUSEHOLD"
            self._write_family_store(family_store)
        return result

    def welcome_child_with_companion(
        self,
        player_id: str,
        *,
        child_name: str,
        family_path: str,
        home_plan: str,
        player_parenthood_consent: bool,
    ) -> WorldResult:
        result = super().welcome_child_with_companion(
            str(player_id),
            child_name=child_name,
            family_path=family_path,
            home_plan=home_plan,
            player_parenthood_consent=player_parenthood_consent,
        )
        if result.status == "CHILD_WELCOMED_BY_MUTUAL_CONSENT" and result.trace_id:
            store = self._family_store()
            family = self._family_profile(store, str(player_id))
            companion = family.get("companion") or {}
            family["structure"]["kind"] = "CO_GUARDIAN_HOUSEHOLD"
            family["coparent_channels"][result.trace_id] = {
                "child_id": result.trace_id,
                "other_guardian": companion.get("handle"),
                "status": "ACTIVE",
                "scope": "CHILD_WELFARE_ONLY",
                "relationship_reopening_allowed": False,
                "either_guardian_may_close": True,
                "schedules": [],
            }
            self._write_family_store(store)
        return result

    def welcome_child_solo_parent(
        self,
        player_id: str,
        *,
        child_name: str,
        family_path: str,
        home_plan: str,
        player_parenthood_consent: bool,
    ) -> WorldResult:
        """Create a non-ranked solo-parent path without requiring companionship."""
        player_id = str(player_id)
        name = str(child_name).strip()[:120]
        if not name:
            raise ValueError("CHILD_NAME_REQUIRED")
        if not player_parenthood_consent:
            return self._family_boundary(
                player_id,
                status="PARENTHOOD_WAITING_FOR_PLAYER_CONSENT",
                reason="Самостоятельное родительство также требует отдельного ясного согласия.",
                choices=["Не становиться родителем", "Вернуться к решению позже"],
            )
        normalized_path = re.sub(r"\s+", " ", str(family_path).strip().upper())[:80]
        if normalized_path not in {"ADOPTION", "BIRTH", "MIRACLE_OF_CARE"}:
            raise ValueError("UNSUPPORTED_FAMILY_PATH")
        store = self._family_store()
        family = self._family_profile(store, player_id)
        if family.get("children"):
            return self._family_boundary(
                player_id,
                status="FAMILY_CHILD_ALREADY_PRESENT",
                reason="Новый ребёнок не добавляется как коллекционный объект.",
                choices=["Заботиться о существующем ребёнке"],
            )
        world_turn = self._family_world_turn()
        child_id = self._family_fingerprint(
            "solo-family-child", player_id, name, normalized_path, world_turn
        )[:24]
        child = {
            "child_id": child_id,
            "name": name,
            "origin_path": normalized_path,
            "age": 0,
            "status": "DEPENDENT_CHILD",
            "welcomed_world_turn": world_turn,
            "guardians": [player_id],
            "guardianship_active": True,
            "single_guardian_fully_consented": True,
            "consent_scope": "SOLO_PARENTHOOD_ONLY",
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
        family["children"][child_id] = child
        family["structure"]["kind"] = "SOLO_PARENT_HOUSEHOLD"
        family["history"].append(
            {
                "world_turn": world_turn,
                "kind": "CHILD_WELCOMED_SOLO_PARENT",
                "child_id": child_id,
                "moral_rank": None,
            }
        )
        self._write_family_store(store)
        self.memory.append_event(
            player_id,
            "child_welcomed_solo_parent",
            {
                "child_id": child_id,
                "child_is_property": False,
                "family_form_ranked": False,
            },
        )
        return self._family_result(
            player_id,
            status="CHILD_WELCOMED_SOLO_PARENT",
            narrative=(
                f"{name} вошёл в дом, где форма семьи не превращена в моральный рейтинг. "
                "Забота существует без собственности и долга."
            ),
            choices=["Дать безопасность", "Собрать круг заботы", "Оставить будущее открытым"],
            trace_id=child_id,
            manifested=True,
        )

    def register_family_care_circle_member(
        self,
        player_id: str,
        child_id: str,
        *,
        member_id: str,
        role: str,
        member_consented: bool,
        guardian_consented: bool,
    ) -> dict[str, Any]:
        if not member_consented or not guardian_consented:
            raise PermissionError("CARE_CIRCLE_MUTUAL_CONSENT_REQUIRED")
        allowed_roles = {
            "EXTENDED_FAMILY",
            "FRIEND",
            "MENTOR",
            "COMMUNITY_CARER",
            "BLENDED_FAMILY_MEMBER",
        }
        normalized_role = str(role).strip().upper()
        if normalized_role not in allowed_roles:
            raise ValueError("UNSUPPORTED_CARE_CIRCLE_ROLE")
        store = self._family_store()
        family = self._family_profile(store, str(player_id))
        if str(child_id) not in family.get("children", {}):
            raise KeyError(child_id)
        member_key = self._family_fingerprint(
            "care-circle", player_id, child_id, member_id, normalized_role
        )[:24]
        record = {
            "member_key": member_key,
            "member_id": str(member_id),
            "child_id": str(child_id),
            "role": normalized_role,
            "member_consented": True,
            "guardian_consented": True,
            "child_voice_required_when_age_appropriate": True,
            "parental_ownership_created": False,
            "revocable": True,
        }
        family["care_circle"][member_key] = record
        family["structure"]["kind"] = "EXTENDED_CARE_CIRCLE"
        self._write_family_store(store)
        self.memory.append_event(str(player_id), "family_care_circle_member_added", record)
        return copy.deepcopy(record)

    def transition_companionship_mode(
        self,
        player_id: str,
        *,
        mode: str,
        reason: str,
    ) -> WorldResult:
        player_id = str(player_id)
        normalized = str(mode).strip().upper()
        allowed = {"LONG_DISTANCE", "PAUSED_BY_PLAYER", "ACTIVE", "ENDED_BY_PLAYER"}
        if normalized not in allowed:
            raise ValueError("UNSUPPORTED_COMPANIONSHIP_MODE")
        store = self._family_store()
        family = self._family_profile(store, player_id)
        companion = family.get("companion")
        if not isinstance(companion, dict):
            return self._family_boundary(
                player_id,
                status="COMPANIONSHIP_TRANSITION_WITHOUT_COMPANION",
                reason="У этой линии нет спутничества для перехода.",
                choices=["Продолжить собственный путь"],
            )
        handle = str(companion["handle"])
        if normalized in {"LONG_DISTANCE", "ACTIVE"}:
            view = self.authoritative_relationship_view(player_id, handle)
            if view["relationship_status"] != "ACTIVE":
                return self._family_boundary(
                    player_id,
                    status="COMPANIONSHIP_REUNION_CANNOT_REOPEN_TERMINATED_RELATIONSHIP",
                    reason=(
                        "Дистанция или возвращение не могут переоткрыть окончательно "
                        "завершённую Другим связь."
                    ),
                    choices=["Принять границу", "Сохранить только канал заботы о ребёнке"],
                )
            invitation = (
                f"предложить @{handle} добровольно согласовать режим {normalized.lower()} "
                "с правом отказаться и не объяснять отказ"
            )
            decision = self.preflight_free_other_action(player_id, invitation)
            if not isinstance(decision, dict) or decision.get("decision") != "accepted":
                return self._family_boundary(
                    player_id,
                    status="COMPANIONSHIP_MODE_NOT_MUTUALLY_ACCEPTED",
                    reason="Новый режим не начал действовать без отдельного положительного ответа.",
                    choices=["Принять ответ", "Оставить текущий режим"],
                )
        companion["status"] = normalized
        companion["mode_reason_sha256"] = self._family_fingerprint(reason)
        companion["mode_changed_world_turn"] = self._family_world_turn()
        family["lifecycle"]["mode"] = normalized
        family["lifecycle"]["history"].append(
            {
                "world_turn": self._family_world_turn(),
                "kind": f"COMPANIONSHIP_MODE_{normalized}",
                "mutual_acceptance_required": normalized in {"LONG_DISTANCE", "ACTIVE"},
                "relationship_reopened": False,
            }
        )
        self._write_family_store(store)
        self.memory.append_event(
            player_id,
            "companionship_mode_changed",
            {"mode": normalized, "handle": handle, "relationship_reopened": False},
        )
        return self._family_result(
            player_id,
            status=f"COMPANIONSHIP_{normalized}",
            narrative=(
                "Форма близости изменилась, но ни расстояние, ни пауза, ни возвращение "
                "не стали правом владеть Другим."
            ),
            choices=["Уважать новый ритм", "Согласовать заботу", "Оставить выход открытым"],
            manifested=True,
        )

    def propose_coparent_schedule(
        self,
        player_id: str,
        child_id: str,
        *,
        plan: str,
    ) -> dict[str, Any]:
        """Use a child-welfare-only channel that never reopens companionship."""
        player_id = str(player_id)
        store = self._family_store()
        family = self._family_profile(store, player_id)
        child = family.get("children", {}).get(str(child_id))
        if not isinstance(child, dict):
            raise KeyError(child_id)
        channel = family.get("coparent_channels", {}).get(str(child_id))
        if not isinstance(channel, dict) or channel.get("status") != "ACTIVE":
            raise PermissionError("COPARENT_CHANNEL_NOT_ACTIVE")
        other_handle = str(channel.get("other_guardian") or "")
        free_store = self._free_store()
        profile = self._free_profile(free_store, player_id)
        actor = profile.get("others", {}).get(other_handle)
        if not isinstance(actor, dict):
            raise KeyError(other_handle)
        if actor.get("actor_life_v1810", {}).get("status") != "LIVING":
            raise RuntimeError("COPARENT_OTHER_ACTOR_NOT_LIVING")
        world_turn = self._family_world_turn()
        fingerprint = self._family_fingerprint(
            "coparent", player_id, child_id, plan, world_turn
        )
        gate = self._free_number(
            free_store,
            player_id,
            other_handle,
            child_id,
            world_turn,
            fingerprint,
            "child-welfare-only",
        ) % 100
        listening = int(child.get("wellbeing", {}).get("LISTENING", 0))
        threshold = min(90, 58 + min(20, listening))
        decision = (
            "accepted"
            if gate < threshold
            else "alternative"
            if gate < min(100, threshold + 24)
            else "refused"
        )
        record = {
            "schedule_id": fingerprint[:24],
            "child_id": str(child_id),
            "decision": decision,
            "plan_sha256": self._family_fingerprint(plan),
            "scope": "CHILD_WELFARE_ONLY",
            "relationship_reopened": False,
            "child_is_leverage": False,
            "world_turn": world_turn,
        }
        channel.setdefault("schedules", []).append(record)
        self._write_family_store(store)
        self.memory.append_event(player_id, "coparent_schedule_proposed", record)
        return copy.deepcopy(record)

    def _promote_adult_child_to_free_other(self, player_id: str, child_id: str) -> str:
        family_store = self._family_store()
        family = self._family_profile(family_store, str(player_id))
        child = family.get("children", {}).get(str(child_id))
        if not isinstance(child, dict):
            raise KeyError(child_id)
        existing = child.get("adult_free_other_handle")
        if existing:
            return str(existing)
        if int(child.get("age", 0)) < 18:
            raise RuntimeError("CHILD_NOT_ADULT")
        handle = f"kin-{str(child_id)[:12]}"
        free_store = self._free_store()
        profile = self._free_profile(free_store, str(player_id))
        own_path = str(child.get("own_path") or "самостоятельный путь без назначенного финала")
        actor = {
            "handle": handle,
            "blueprint_id": f"adult-child-{child_id}",
            "name": str(child.get("name") or handle),
            "calling": own_path,
            "original_calling": own_path,
            "stages": [
                "сделал первый самостоятельный шаг после завершения опеки",
                "отказался от одного унаследованного ожидания",
                "выбрал собственный круг друзей и вопросов",
                "ушёл проверить путь без отчёта семье",
                "вернулся или не вернулся по собственной воле",
            ],
            "new_callings": [
                "исследователь взрослой дороги без семейного задания",
                "создатель собственного дома с открытым выходом",
            ],
            "initiatives": [
                f"{child.get('name')} первым предложил разговор, но разрешил не соглашаться.",
                f"{child.get('name')} показал часть собственного пути без обязанности семьи одобрить его.",
            ],
            "refusals": [
                f"{child.get('name')} отказался превращать родство в постоянный доступ к своей жизни.",
                f"{child.get('name')} выбрал сегодня не объяснять взрослое решение.",
            ],
            "alternatives": [
                f"Вместо отчёта {child.get('name')} предложил встретиться на нейтральной тропе.",
                f"Вместо согласия {child.get('name')} оставил право вернуться к вопросу позднее.",
            ],
            "stage_index": 0,
            "progress": 0,
            "status": "active",
            "away_reason": None,
            "left_world_turn": None,
            "last_changed_world_turn": self._family_world_turn(),
            "trust": 0.0,
            "distance": 0,
            "contacts": 0,
            "initiated_contacts": 0,
            "refusals_count": 0,
            "departures": 0,
            "returns": 0,
            "calling_changes": 0,
            "history": [],
            "player_controlled": False,
            "independent_of_first_two": True,
            "simulated_person_claim": False,
            "can_refuse": True,
            "can_leave": True,
            "can_change_goal": True,
            "kinship_role": "ADULT_CHILD",
            "care_did_not_purchase_love": True,
            "life_stage_v1813": {
                "stage": "ADULT",
                "adult": True,
                "source": "FAMILY_AGE_MILESTONE_V1813",
                "real_world_verified": False,
                "may_be_revised": False,
            },
        }
        self._upgrade_actor_separation(actor, self._family_world_turn())
        self._refresh_actor_relationship(str(player_id), actor)
        profile["others"][handle] = actor
        child["adult_free_other_handle"] = handle
        child["full_free_other_stream"] = True
        child["guardianship_active"] = False
        child.setdefault("history", []).append(
            {
                "world_turn": self._family_world_turn(),
                "kind": "ADULT_CHILD_PROMOTED_TO_FREE_OTHER",
                "handle": handle,
                "care_purchased_love": False,
            }
        )
        family["history"].append(
            {
                "world_turn": self._family_world_turn(),
                "kind": "ADULT_CHILD_PROMOTED_TO_FREE_OTHER",
                "child_id": str(child_id),
                "handle": handle,
            }
        )
        self._write_json(self.free_other_path, free_store)
        self._write_family_store(family_store)
        self.memory.append_event(
            str(player_id),
            "adult_child_promoted_to_free_other",
            {
                "child_id": str(child_id),
                "handle": handle,
                "player_controlled": False,
                "can_refuse": True,
                "can_leave": True,
            },
        )
        return handle

    def advance_family_years(self, player_id: str, *, years: int = 1) -> dict[str, Any]:
        result = super().advance_family_years(str(player_id), years=years)
        promoted: list[dict[str, str]] = []
        for child_id, child in result.get("children", {}).items():
            if int(child.get("age", 0)) >= 18 and not child.get("adult_free_other_handle"):
                handle = self._promote_adult_child_to_free_other(
                    str(player_id), str(child_id)
                )
                promoted.append({"child_id": str(child_id), "handle": handle})
        if promoted:
            result["children"] = self.family_state(str(player_id)).get("children", {})
        result["adult_free_other_promotions"] = promoted
        return result

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
        participant_ids = {
            str(item).lstrip("@") for item in participants if str(item).strip()
        }
        family = self.family_state(str(player_id))
        adult_kin = {
            str(child.get("adult_free_other_handle"))
            for child in family.get("children", {}).values()
            if child.get("adult_free_other_handle")
        }
        normalized = self._normalized_joy_text(wish)
        adult_mode = (
            self._contains_any(normalized, self._ADULT_ONLY_FRAGMENTS)
            or self._contains_any(normalized, self._TRANSMUTABLE_FRAGMENTS)
        )
        if adult_mode and participant_ids.intersection(adult_kin):
            return self._family_boundary(
                str(player_id),
                status="JOY_FAMILY_KINSHIP_BOUNDARY",
                reason=(
                    "Взрослая самостоятельность ребёнка не отменяет семейное родство. "
                    "Родство не становится взрослым сценическим согласием."
                ),
                choices=["Оставить семейную встречу безопасной", "Выбрать других взрослых участников"],
            )
        return super().manifest_blessed_play(
            str(player_id),
            wish,
            participants=participant_ids,
            all_participants_adults=all_participants_adults,
            all_participants_consented=all_participants_consented,
            doubt_free=doubt_free,
        )
