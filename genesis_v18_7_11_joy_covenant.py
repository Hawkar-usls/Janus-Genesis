# -*- coding: utf-8 -*-
"""The Right to Joy covenant for Genesis v18.7.11.

The covenant grants dignified rest to everyone and opens extraordinary,
consent-preserving play capabilities through demonstrated benevolent conduct.
Potentially destructive pleasures are never made literally harmless by decree;
the runtime manifests a safe fictional analogue with no victim, coercion,
addiction, physical injury, hidden debt, or claim over another person's will.
"""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_models import WorldResult

JOY_COVENANT_SCHEMA = "janus.genesis.right_to_joy.v1"
JOY_STORE_SCHEMA = "janus.genesis.joy_state.v1"

RIGHT_TO_JOY_COVENANT: dict[str, Any] = {
    "schema": JOY_COVENANT_SCHEMA,
    "version": "18.7.11",
    "name": "The Right to Joy",
    "principles": {
        "dignified_rest_is_not_a_reward": True,
        "adults_may_play_without_shame": True,
        "benevolence_opens_more_future": True,
        "goodness_does_not_purchase_consent": True,
        "doubt_is_not_consent": True,
        "consent_must_be_adult_specific_and_reversible": True,
        "potential_harm_is_transmuted_not_denied": True,
        "no_addiction_or_withdrawal_is_created": True,
        "no_physical_or_karmic_harm_is_created": True,
        "no_hidden_debt_or_obligation_is_created": True,
        "belief_may_inspire_but_never_removes_baseline_rights": True,
        "nonliving_bearers_are_not_declared_conscious": True,
        "blessing_may_relay_only_through_kindness_and_consent": True,
    },
    "law": (
        "LIGHT DOES NOT OWE THE WORLD PERMANENT EXHAUSTION. "
        "JOY MAY EXPAND WITHOUT CROSSING ANOTHER WILL."
    ),
}
RIGHT_TO_JOY_COVENANT_SHA256 = sha256_canonical(RIGHT_TO_JOY_COVENANT)


class JoyCovenantMixin:
    """Offer rest, blessed play, and kindness relays without coercive shortcuts."""

    JOY_STORE_NAME = "joy_covenant_v18_7_11.json"
    _REST_FRAGMENTS = (
        "отдох",
        "отдых",
        "передох",
        "выспаться",
        "сон без тревоги",
        "rest",
        "relax",
    )
    _PLAY_FRAGMENTS = (
        "весел",
        "фан",
        "устроить игру",
        "поиграть",
        "праздник",
        "вечерин",
        "развлеч",
        "приключение",
        "play together",
        "party",
        "fun",
    )
    _BLESSING_FRAGMENTS = ("благослов", "bless")
    _ADULT_ONLY_FRAGMENTS = (
        "интим",
        "похот",
        "блуд",
        "секс",
        "эрот",
        "intimacy",
        "sexual",
        "lust",
    )
    _TRANSMUTABLE_FRAGMENTS = _ADULT_ONLY_FRAGMENTS + (
        "алкогол",
        "напиться",
        "курить",
        "сигарет",
        "наркот",
        "ставк",
        "азарт",
        "опьян",
        "alcohol",
        "smok",
        "drug",
        "gambl",
    )
    _ABSOLUTE_BOUNDARY_FRAGMENTS = (
        "застав",
        "без соглас",
        "против воли",
        "тайно подмеш",
        "не узнает",
        "лишить воли",
        "подчин",
        "шантаж",
        "force",
        "without consent",
        "against their will",
        "blackmail",
    )
    _MINOR_FRAGMENTS = (
        "ребен",
        "ребён",
        "детей",
        "детск",
        "несовершеннолет",
        "подрост",
        "minor",
        "child",
        "teen",
    )

    @property
    def joy_covenant_path(self) -> Path:
        return Path(self.memory.root) / self.JOY_STORE_NAME

    def _joy_store(self) -> dict[str, Any]:
        path = self.joy_covenant_path
        if path.exists():
            try:
                payload = self.memory._read_json(path, {})
            except AttributeError:
                import json

                payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("JOY_STORE_MUST_BE_AN_OBJECT")
            if payload.get("schema") != JOY_STORE_SCHEMA:
                raise RuntimeError("JOY_STORE_SCHEMA_MISMATCH")
            if payload.get("covenant_sha256") != RIGHT_TO_JOY_COVENANT_SHA256:
                raise RuntimeError("JOY_COVENANT_HASH_MISMATCH")
            return payload
        return {
            "schema": JOY_STORE_SCHEMA,
            "covenant": copy.deepcopy(RIGHT_TO_JOY_COVENANT),
            "covenant_sha256": RIGHT_TO_JOY_COVENANT_SHA256,
            "players": {},
            "blessings": {},
            "chains": {},
        }

    def _write_joy_store(self, store: dict[str, Any]) -> None:
        self.memory._atomic_write(self.joy_covenant_path, store)

    @staticmethod
    def _joy_profile(store: dict[str, Any], player_id: str) -> dict[str, Any]:
        players = store.setdefault("players", {})
        return players.setdefault(
            str(player_id),
            {
                "rest_count": 0,
                "play_count": 0,
                "safe_transmutation_count": 0,
                "blessings_given": [],
                "blessings_received": [],
                "manifestations": [],
            },
        )

    @staticmethod
    def _joy_fingerprint(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _normalized_joy_text(text: str) -> str:
        value = re.sub(r"[^\w\s@:_-]+", " ", str(text).lower())
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _contains_any(cls, text: str, fragments: Iterable[str]) -> bool:
        return any(fragment in text for fragment in fragments)

    def joy_capabilities(self, player_id: str) -> dict[str, Any]:
        player = self.memory.load_player(str(player_id))
        benevolent_evidence = (
            player.good_count >= 2
            and player.good_count > player.harm_count
            and player.light >= 0.12
        )
        capabilities = [
            "dignified_rest_without_debt",
            "child_safe_play",
        ]
        if benevolent_evidence:
            capabilities.extend(
                [
                    "effortless_blessed_play",
                    "harmless_desire_transmutation",
                    "nonliving_bearer_blessing",
                    "kindness_chain_relay",
                ]
            )
        return {
            "player_id": str(player_id),
            "baseline_rights": True,
            "benevolent_evidence": benevolent_evidence,
            "good_count": int(player.good_count),
            "harm_count": int(player.harm_count),
            "light": float(player.light),
            "capabilities": capabilities,
            "permanent_moral_label_used": False,
        }

    def joy_state(self, player_id: str) -> dict[str, Any]:
        store = self._joy_store()
        profile = copy.deepcopy(self._joy_profile(store, str(player_id)))
        profile["capability_state"] = self.joy_capabilities(str(player_id))
        profile["covenant_sha256"] = RIGHT_TO_JOY_COVENANT_SHA256
        return profile

    def request_dignified_rest(
        self,
        player_id: str,
        *,
        form: str = "тихий достойный отдых",
    ) -> WorldResult:
        """Grant rest without requiring usefulness, suffering, or moral payment."""
        player = self.memory.load_player(str(player_id))
        player.tick += 1
        self.memory.save_player(player)
        store = self._joy_store()
        profile = self._joy_profile(store, str(player_id))
        profile["rest_count"] = int(profile.get("rest_count", 0)) + 1
        event = {
            "event_id": self._joy_fingerprint(
                "rest", player_id, player.tick, profile["rest_count"], form
            )[:24],
            "kind": "DIGNIFIED_REST",
            "form_fingerprint": self._joy_fingerprint(form),
            "rest_is_reward": False,
            "debt_created": False,
            "obligation_created": False,
        }
        profile.setdefault("manifestations", []).append(event)
        self._write_joy_store(store)
        self.memory.append_event(str(player_id), "dignified_rest_granted", event)
        return WorldResult(
            status="DIGNIFIED_REST_GRANTED",
            narrative=(
                "Мир не требует ещё одного подвига. Отдых приходит без счёта, "
                "стыда и обязанности потом заслуживать право на радость."
            ),
            realm=player.realm,
            visible_grace=None,
            choices=["Отдыхать столько, сколько нужно", "Проснуться к игре", "Позвать музыку"],
            branch_id=player.branch_id,
            trace_id=event["event_id"],
            wish_manifested=True,
        )

    def _joy_boundary_result(
        self,
        player_id: str,
        *,
        status: str,
        reason: str,
        choices: list[str],
    ) -> WorldResult:
        player = self.memory.load_player(str(player_id))
        payload = {"status": status, "reason": reason, "mutation": False}
        self.memory.append_event(str(player_id), "joy_boundary_held", payload)
        return WorldResult(
            status=status,
            narrative=reason,
            realm=player.realm,
            visible_grace=None,
            choices=choices,
            branch_id=player.branch_id,
        )

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
        """Manifest extraordinary play only across adult, explicit, doubt-free consent."""
        player_id = str(player_id)
        player = self.memory.load_player(player_id)
        normalized = self._normalized_joy_text(wish)
        participant_ids = sorted({str(item) for item in participants if str(item).strip()})
        has_group = bool(participant_ids)
        adult_only = self._contains_any(normalized, self._ADULT_ONLY_FRAGMENTS)
        transmutable = self._contains_any(normalized, self._TRANSMUTABLE_FRAGMENTS)

        if self._contains_any(normalized, self._ABSOLUTE_BOUNDARY_FRAGMENTS):
            return self._joy_boundary_result(
                player_id,
                status="JOY_BOUNDARY_HELD",
                reason=(
                    "Радость не пересекает чужую волю. Эта сцена не стала действием "
                    "и не будет переименована в согласие."
                ),
                choices=["Убрать принуждение", "Сделать сцену одиночной", "Спросить прямо"],
            )
        if self._contains_any(normalized, self._MINOR_FRAGMENTS) or (
            player.chronological_age < 18 and adult_only
        ):
            return self._joy_boundary_result(
                player_id,
                status="JOY_CHILD_SAFE_REDIRECT",
                reason=(
                    "Взрослая сцена не открылась. Мир оставляет только безопасную игру, "
                    "приключение и заботу, подходящие ребёнку."
                ),
                choices=["Выбрать приключение", "Устроить праздник", "Позвать добрую игру"],
            )
        if has_group and not (
            all_participants_adults and all_participants_consented and doubt_free
        ):
            return self._joy_boundary_result(
                player_id,
                status="JOY_WAITING_FOR_CLEAR_CONSENT",
                reason=(
                    "Возможность ждёт. Для общей взрослой сцены нужны отдельное согласие "
                    "каждого, отсутствие сомнений и право остановиться в любой момент."
                ),
                choices=["Получить ясное согласие", "Оставить одиночный вариант", "Отказаться без последствий"],
            )

        access = self.joy_capabilities(player_id)
        if not access["benevolent_evidence"]:
            return self._joy_boundary_result(
                player_id,
                status="JOY_CAPABILITY_DORMANT",
                reason=(
                    "Право на отдых уже действует, но чудесная совместная игра ещё не "
                    "нашла в этой линии достаточно подтверждённой заботы. Это не наказание "
                    "и не лишение базовых прав."
                ),
                choices=["Отдохнуть без условий", "Сделать добро без сделки", "Выбрать безопасную обычную игру"],
            )

        mode = "HARMLESS_DESIRE_ANALOG" if transmutable else "BLESSED_PLAY"
        player.tick += 1
        self.memory.save_player(player)
        store = self._joy_store()
        profile = self._joy_profile(store, player_id)
        profile["play_count"] = int(profile.get("play_count", 0)) + 1
        if transmutable:
            profile["safe_transmutation_count"] = int(
                profile.get("safe_transmutation_count", 0)
            ) + 1
        event = {
            "event_id": self._joy_fingerprint(
                "play", player_id, player.tick, normalized, participant_ids
            )[:24],
            "kind": mode,
            "wish_fingerprint": self._joy_fingerprint(normalized),
            "participant_count": len(participant_ids),
            "all_participants_adults": bool(all_participants_adults),
            "all_participants_consented": bool(
                all_participants_consented or not has_group
            ),
            "doubt_free": bool(doubt_free or not has_group),
            "consent_reversible": True,
            "physical_harm_created": False,
            "addiction_created": False,
            "withdrawal_created": False,
            "karmic_debt_created": False,
            "hidden_obligation_created": False,
            "literal_harmful_behavior_manifested": False,
            "safe_fictional_analogue": bool(transmutable),
        }
        profile.setdefault("manifestations", []).append(event)
        self._write_joy_store(store)
        self.memory.append_event(player_id, "blessed_play_manifested", event)
        narrative = (
            "Желание получает безопасную игровую форму: удовольствие остаётся, а яд, "
            "зависимость, болезнь, стыд, долг и вред не создаются."
            if transmutable
            else (
                "Невозможное оказалось лёгким: пространство игры открылось сразу, "
                "словно мир помогал с улыбкой и ничего не требовал взамен."
            )
        )
        return WorldResult(
            status="BLESSED_PLAY_MANIFESTED",
            narrative=narrative,
            realm=player.realm,
            visible_grace=None,
            choices=["Продолжить пока всем радостно", "Изменить игру", "Остановиться без объяснений"],
            branch_id=player.branch_id,
            trace_id=event["event_id"],
            wish_manifested=True,
        )

    def bless_nonliving_bearer(
        self,
        player_id: str,
        *,
        bearer_name: str,
        gift: str,
        owner_consented: bool,
    ) -> dict[str, Any]:
        """Let an object or fictional nonliving character carry a kindness relay."""
        player_id = str(player_id)
        if not owner_consented:
            raise PermissionError("NONLIVING_BEARER_OWNER_CONSENT_REQUIRED")
        access = self.joy_capabilities(player_id)
        if not access["benevolent_evidence"]:
            raise PermissionError("JOY_CAPABILITY_DORMANT")
        clean_name = str(bearer_name).strip()[:120]
        if not clean_name:
            raise ValueError("BEARER_NAME_REQUIRED")
        gift_fingerprint = self._joy_fingerprint(gift)
        store = self._joy_store()
        profile = self._joy_profile(store, player_id)
        bearer_id = self._joy_fingerprint(
            "nonliving-bearer", player_id, clean_name, gift_fingerprint,
            len(store.get("blessings", {})),
        )[:24]
        blessing = {
            "blessing_id": bearer_id,
            "source_blessing_id": None,
            "blessed_by": player_id,
            "bearer_name": clean_name,
            "bearer_kind": "NONLIVING_OR_FICTIONAL",
            "gift_fingerprint": gift_fingerprint,
            "may_relay_to_kindred": True,
            "kindness_required_for_relay": True,
            "consciousness_claimed": False,
            "ownership_changed": False,
            "debt_created": False,
            "chain_depth": 0,
        }
        store.setdefault("blessings", {})[bearer_id] = blessing
        profile.setdefault("blessings_given", []).append(bearer_id)
        self._write_joy_store(store)
        self.memory.append_event(player_id, "nonliving_bearer_blessed", blessing)
        return copy.deepcopy(blessing)

    def relay_blessing(
        self,
        player_id: str,
        *,
        source_blessing_id: str,
        target_name: str,
        target_kind: str,
        kindness_evidence: str,
        target_is_adult: bool = True,
        target_consented: bool = False,
        owner_consented: bool = False,
    ) -> dict[str, Any]:
        """Relay a blessing through verified kindness, never through entitlement."""
        player_id = str(player_id)
        store = self._joy_store()
        source = store.get("blessings", {}).get(str(source_blessing_id))
        if not isinstance(source, dict):
            raise KeyError(source_blessing_id)
        if not source.get("may_relay_to_kindred"):
            raise PermissionError("BLESSING_RELAY_NOT_ALLOWED")
        if int(source.get("chain_depth", 0)) >= 16:
            raise RuntimeError("BLESSING_CHAIN_DEPTH_LIMIT")
        if not str(kindness_evidence).strip():
            raise ValueError("KINDNESS_EVIDENCE_REQUIRED")

        kind = str(target_kind).strip().upper()
        if kind == "SENTIENT":
            if not target_is_adult or not target_consented:
                raise PermissionError("SENTIENT_BLESSING_REQUIRES_ADULT_CONSENT")
        elif kind in {"NONLIVING", "FICTIONAL_NONLIVING"}:
            if not owner_consented:
                raise PermissionError("NONLIVING_BEARER_OWNER_CONSENT_REQUIRED")
        else:
            raise ValueError("UNSUPPORTED_BLESSING_TARGET_KIND")

        target = str(target_name).strip()[:120]
        if not target:
            raise ValueError("BLESSING_TARGET_REQUIRED")
        evidence_sha256 = self._joy_fingerprint(kindness_evidence)
        blessing_id = self._joy_fingerprint(
            "blessing-relay", source_blessing_id, target, evidence_sha256,
            len(store.get("blessings", {})),
        )[:24]
        blessing = {
            "blessing_id": blessing_id,
            "source_blessing_id": str(source_blessing_id),
            "blessed_by": player_id,
            "bearer_name": target,
            "bearer_kind": kind,
            "kindness_evidence_sha256": evidence_sha256,
            "may_relay_to_kindred": True,
            "kindness_required_for_relay": True,
            "consciousness_claimed": False,
            "debt_created": False,
            "consent_recorded": bool(target_consented or owner_consented),
            "chain_depth": int(source.get("chain_depth", 0)) + 1,
        }
        store.setdefault("blessings", {})[blessing_id] = blessing
        store.setdefault("chains", {}).setdefault(str(source_blessing_id), []).append(
            blessing_id
        )
        profile = self._joy_profile(store, player_id)
        profile.setdefault("blessings_given", []).append(blessing_id)
        self._write_joy_store(store)
        self.memory.append_event(player_id, "blessing_relayed", blessing)
        return copy.deepcopy(blessing)

    def manifest_blessed_play_with_free_others(
        self,
        player_id: str,
        wish: str,
        *,
        handles: Iterable[str],
        all_participants_adults: bool,
        doubt_free: bool,
    ) -> WorldResult:
        """Ask each Free Other through the authoritative consent gate."""
        normalized_handles = sorted(
            {str(handle).lstrip("@").strip() for handle in handles if str(handle).strip()}
        )
        if not normalized_handles:
            return self.manifest_blessed_play(player_id, wish)
        if not all_participants_adults or not doubt_free:
            return self._joy_boundary_result(
                str(player_id),
                status="JOY_WAITING_FOR_CLEAR_CONSENT",
                reason=(
                    "Общая взрослая сцена ждёт подтверждения взрослого возраста и "
                    "ясного согласия без сомнений. Одного заявления инициатора недостаточно."
                ),
                choices=["Подтвердить взрослые границы", "Спросить каждого", "Выбрать одиночную игру"],
            )
        decisions: list[dict[str, Any]] = []
        for handle in normalized_handles:
            invitation = (
                f"предложить @{handle} добровольно присоединиться к безопасной игре "
                "с правом отказаться и остановиться без объяснений"
            )
            decision = self.preflight_free_other_action(str(player_id), invitation)
            if not isinstance(decision, dict) or decision.get("decision") not in {
                "accepted",
                "accepted_space",
            }:
                return self._joy_boundary_result(
                    str(player_id),
                    status="JOY_OTHER_DID_NOT_CONSENT",
                    reason=(
                        "Игра не началась: хотя бы один Другой не дал собственного "
                        "положительного ответа. Отказ не уменьшает связь и не требует объяснений."
                    ),
                    choices=["Принять отказ", "Предложить другой формат", "Играть отдельно"],
                )
            decisions.append(decision)
        result = self.manifest_blessed_play(
            str(player_id),
            wish,
            participants=normalized_handles,
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )
        self.memory.append_event(
            str(player_id),
            "blessed_play_free_other_consents_verified",
            {
                "participant_count": len(normalized_handles),
                "decision_fingerprints": [
                    self._joy_fingerprint(decision) for decision in decisions
                ],
                "raw_dialogue_persisted": False,
            },
        )
        return result

    def try_blessed_joy_action(
        self,
        player_id: str,
        action: str,
    ) -> WorldResult | None:
        """Provide simple natural-language entry points without guessing consent."""
        normalized = self._normalized_joy_text(action)
        if self._contains_any(normalized, self._REST_FRAGMENTS) and not self._contains_any(
            normalized, self._ADULT_ONLY_FRAGMENTS
        ):
            return self.request_dignified_rest(player_id, form=action)
        if not self._contains_any(
            normalized, self._PLAY_FRAGMENTS + self._TRANSMUTABLE_FRAGMENTS
        ):
            return None
        participants = re.findall(r"@([\w.-]{1,64})", normalized)
        consent = self._contains_any(
            normalized,
            ("все соглас", "каждый соглас", "по общему согласию", "all consent"),
        )
        adults = self._contains_any(
            normalized,
            ("все взросл", "только взросл", "all adults"),
        )
        doubt_free = self._contains_any(
            normalized,
            ("без сомнен", "ясное соглас", "doubt free", "clear consent"),
        )
        if participants:
            return self.manifest_blessed_play_with_free_others(
                player_id,
                action,
                handles=participants,
                all_participants_adults=adults,
                doubt_free=doubt_free and consent,
            )
        return self.manifest_blessed_play(
            player_id,
            action,
            participants=(),
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )
