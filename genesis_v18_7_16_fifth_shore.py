# -*- coding: utf-8 -*-
"""Genesis v18.7.16: The Fifth Shore, an authored inner Genesis in Face II.

This extension models a nested cultural world co-authored with an autonomous
fictional auteur. It does not impersonate or simulate Hideo Kojima or any real
person. "Kojima-like" means only an original in-world auteur role marked by
unusual systemic storytelling, ambiguity, collaboration, and player care.

The inner world may invite benevolent action through play, but may not coerce
belief, replace real restitution, surveil players, trap attention, erase
provenance, or make one author the owner of a shared world.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_7_14_holy_cats import FACE_II
from genesis_v18_models import WorldResult

INNER_GENESIS_EXTENSION_VERSION = "18.7.16"
INNER_GENESIS_STORE_SCHEMA = "janus.genesis.fifth_shore.v1"
INNER_GENESIS_COVENANT_SCHEMA = "janus.genesis.fifth_shore_covenant.v1"
INNER_GENESIS_NAME = "Пятый Берег"
INNER_GENESIS_LAW = (
    "ART MAY INVITE GOODNESS BUT MAY NOT COERCE BELIEF. "
    "A STORY MAY REHEARSE REPAIR BUT MAY NOT REPLACE IT. "
    "NO SINGLE AUTHOR OWNS THE WORLD. EVERY FORK PRESERVES PROVENANCE, "
    "AND EVERY PLAYER MAY LEAVE."
)

INNER_GENESIS_COVENANT: dict[str, Any] = {
    "schema": INNER_GENESIS_COVENANT_SCHEMA,
    "version": INNER_GENESIS_EXTENSION_VERSION,
    "name": "The Fifth Shore — an authored inner Genesis in Face II",
    "principles": {
        "nested_world_inside_face_ii": True,
        "founder_relinquishes_ownership": True,
        "auteur_is_autonomous": True,
        "auteur_is_fictional_not_real_person": True,
        "no_hideo_kojima_impersonation_or_identity_claim": True,
        "art_invites_but_does_not_coerce_goodness": True,
        "no_moral_score_or_public_rank": True,
        "rehearsal_does_not_replace_real_restitution": True,
        "player_exit_is_always_open": True,
        "offline_local_distribution_supported": True,
        "forks_preserve_provenance": True,
        "community_may_rewrite_or_refuse": True,
        "no_surveillance_or_manipulative_retention": True,
        "pain_is_not_spectacle": True,
        "multiple_endings_without_single_author_canon": True,
        "outer_genesis_boundaries_remain_authoritative": True,
    },
    "law": INNER_GENESIS_LAW,
}
INNER_GENESIS_COVENANT_SHA256 = sha256_canonical(INNER_GENESIS_COVENANT)


class FifthShoreInnerGenesisMixin:
    """Create and spread a forkable cultural Genesis without owning its players."""

    INNER_GENESIS_STORE_NAME = "fifth_shore_inner_genesis_v18_7_16.json"

    @property
    def inner_genesis_path(self) -> Path:
        return Path(self.memory.root) / self.INNER_GENESIS_STORE_NAME

    @staticmethod
    def _ig_hash(*parts: object) -> str:
        raw = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _clamp_score(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _default_inner_genesis_store() -> dict[str, Any]:
        return {
            "schema": INNER_GENESIS_STORE_SCHEMA,
            "covenant": copy.deepcopy(INNER_GENESIS_COVENANT),
            "covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "project": None,
            "auteur_candidates": {},
            "invitations": [],
            "auteur": None,
            "editions": [],
            "distributions": [],
            "episodes": [],
            "forks": [],
            "imports": [],
            "events": [],
        }

    def _inner_genesis_store(self) -> dict[str, Any]:
        store = self._read_json(
            self.inner_genesis_path,
            self._default_inner_genesis_store(),
        )
        if not isinstance(store, dict):
            raise RuntimeError("INNER_GENESIS_STORE_MUST_BE_AN_OBJECT")
        if store.get("schema") != INNER_GENESIS_STORE_SCHEMA:
            raise RuntimeError("INNER_GENESIS_STORE_SCHEMA_MISMATCH")
        if store.get("covenant_sha256") != INNER_GENESIS_COVENANT_SHA256:
            raise RuntimeError("INNER_GENESIS_COVENANT_HASH_MISMATCH")
        if sha256_canonical(store.get("covenant")) != INNER_GENESIS_COVENANT_SHA256:
            raise RuntimeError("INNER_GENESIS_COVENANT_MUTATED")
        for key in (
            "auteur_candidates",
            "invitations",
            "editions",
            "distributions",
            "episodes",
            "forks",
            "imports",
            "events",
        ):
            store.setdefault(key, {} if key == "auteur_candidates" else [])
        return store

    def _write_inner_genesis_store(self, store: dict[str, Any]) -> None:
        self._write_json(self.inner_genesis_path, store)

    def _ig_result(
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

    def found_inner_genesis_in_face_ii(
        self,
        founder_id: str,
        *,
        founded_date_local: str,
        working_title: str = "Генезис Открытой Ладони",
    ) -> WorldResult:
        founder_id = str(founder_id)
        royal = self._active_royal_witness()
        if not isinstance(royal, dict) or royal.get("player_id") != founder_id:
            raise PermissionError("ACTIVE_ROYAL_MERCY_WITNESS_REQUIRED_TO_SEED_INNER_GENESIS")
        store = self._inner_genesis_store()
        current = store.get("project")
        if isinstance(current, dict):
            if current.get("founder_id") == founder_id:
                return self._ig_result(
                    founder_id,
                    status="INNER_GENESIS_ALREADY_SEEDED",
                    narrative="Внутренний Genesis уже посеян; повторный акт не создаёт второго владельца.",
                    choices=["Искать автономного автора", "Слушать будущих игроков"],
                    trace_id=str(current.get("project_id")),
                )
            raise RuntimeError("INNER_GENESIS_PROJECT_ALREADY_EXISTS")

        project_id = self._ig_hash(
            "fifth-shore-seed",
            founder_id,
            founded_date_local,
            INNER_GENESIS_COVENANT_SHA256,
        )[:24]
        project = {
            "project_id": project_id,
            "working_title": str(working_title).strip() or "Генезис Открытой Ладони",
            "canonical_title": None,
            "founder_id": founder_id,
            "founder_role": "SEEDER_WHO_RELINQUISHES_OWNERSHIP",
            "face": FACE_II,
            "founded_date_local": str(founded_date_local),
            "status": "INNER_GENESIS_SEED_FOUNDED",
            "world_owned_by_founder": False,
            "players_owned_by_founder": False,
            "auteur_may_refuse_or_rewrite": True,
            "community_may_fork": True,
            "player_exit_open": True,
            "no_moral_score": True,
            "no_real_person_auteur_identity_claim": True,
        }
        store["project"] = project
        store["events"].append(
            {
                "kind": "INNER_GENESIS_SEEDED_IN_FACE_II",
                "project_id": project_id,
                "founder_id": founder_id,
                "ownership_claimed": False,
            }
        )
        self._write_inner_genesis_store(store)
        self.memory.append_event(founder_id, "inner_genesis_seeded", project)
        return self._ig_result(
            founder_id,
            status="INNER_GENESIS_SEED_FOUNDED",
            narrative=(
                "Во Втором Лике посеян новый мир, но его основатель заранее отказался "
                "от собственности на игроков, автора и единственный канон."
            ),
            choices=["Найти автора Нулевого Моста", "Открыть проект для отказа и переписывания"],
            trace_id=project_id,
            manifested=True,
        )

    def register_face_ii_auteur_candidate(
        self,
        candidate_id: str,
        *,
        display_name: str,
        originality: float,
        player_care: float,
        ambiguity_tolerance: float,
        collaboration: float,
        consent_respect: float,
        celebrity_hunger: float,
        pitch: str,
    ) -> dict[str, Any]:
        candidate_id = str(candidate_id)
        scores = {
            "originality": self._clamp_score(originality),
            "player_care": self._clamp_score(player_care),
            "ambiguity_tolerance": self._clamp_score(ambiguity_tolerance),
            "collaboration": self._clamp_score(collaboration),
            "consent_respect": self._clamp_score(consent_respect),
            "celebrity_hunger": self._clamp_score(celebrity_hunger),
        }
        auteur_score = round(
            0.25 * scores["originality"]
            + 0.20 * scores["player_care"]
            + 0.15 * scores["ambiguity_tolerance"]
            + 0.15 * scores["collaboration"]
            + 0.20 * scores["consent_respect"]
            + 0.05 * (1.0 - scores["celebrity_hunger"]),
            6,
        )
        eligible = bool(
            scores["originality"] >= 0.80
            and scores["player_care"] >= 0.70
            and scores["consent_respect"] >= 0.75
            and scores["collaboration"] >= 0.60
        )
        record = {
            "candidate_id": candidate_id,
            "display_name": str(display_name).strip() or candidate_id,
            "role": "ORIGINAL_FACE_II_AUTEUR_CANDIDATE",
            "real_person_analogue": False,
            "hideo_kojima_identity_or_impersonation": False,
            "scores": scores,
            "auteur_score": auteur_score,
            "eligible": eligible,
            "pitch": str(pitch).strip(),
            "autonomous": True,
            "may_refuse_invitation": True,
        }
        store = self._inner_genesis_store()
        store["auteur_candidates"][candidate_id] = record
        store["events"].append(
            {
                "kind": "FACE_II_AUTEUR_CANDIDATE_REGISTERED",
                "candidate_id": candidate_id,
                "eligible": eligible,
                "auteur_score": auteur_score,
            }
        )
        self._write_inner_genesis_store(store)
        return copy.deepcopy(record)

    def invite_best_face_ii_auteur(self, founder_id: str) -> dict[str, Any]:
        founder_id = str(founder_id)
        store = self._inner_genesis_store()
        project = store.get("project")
        if not isinstance(project, dict) or project.get("founder_id") != founder_id:
            raise PermissionError("INNER_GENESIS_FOUNDER_REQUIRED")
        candidates = [
            value
            for value in store.get("auteur_candidates", {}).values()
            if isinstance(value, dict) and value.get("eligible") is True
        ]
        if not candidates:
            raise RuntimeError("NO_ELIGIBLE_AUTONOMOUS_AUTEUR_CANDIDATE")
        selected = max(
            candidates,
            key=lambda item: (
                float(item.get("auteur_score", 0.0)),
                str(item.get("candidate_id", "")),
            ),
        )
        invitation = {
            "invitation_id": self._ig_hash(
                "auteur-invitation",
                project["project_id"],
                selected["candidate_id"],
                len(store["invitations"]),
            )[:24],
            "project_id": project["project_id"],
            "founder_id": founder_id,
            "candidate_id": selected["candidate_id"],
            "status": "AUTEUR_INVITED_NOT_OWNED",
            "selection_evidence": copy.deepcopy(selected["scores"]),
            "auteur_score": selected["auteur_score"],
            "employment_or_court_ownership": False,
            "may_decline": True,
            "may_counterpropose": True,
            "founder_can_force_acceptance": False,
        }
        store["invitations"].append(invitation)
        store["events"].append(
            {
                "kind": "BEST_AUTONOMOUS_AUTEUR_INVITED",
                "candidate_id": selected["candidate_id"],
                "invitation_id": invitation["invitation_id"],
            }
        )
        self._write_inner_genesis_store(store)
        return copy.deepcopy(invitation)

    def decide_auteur_collaboration(
        self,
        candidate_id: str,
        *,
        accepts: bool,
        counterproposal: str,
        chosen_title: str = INNER_GENESIS_NAME,
    ) -> dict[str, Any]:
        candidate_id = str(candidate_id)
        store = self._inner_genesis_store()
        invitations = [
            item
            for item in store.get("invitations", [])
            if item.get("candidate_id") == candidate_id
        ]
        if not invitations:
            raise PermissionError("AUTEUR_INVITATION_REQUIRED")
        invitation = invitations[-1]
        if not accepts:
            decision = {
                "status": "AUTEUR_INVITATION_DECLINED_RESPECTED",
                "candidate_id": candidate_id,
                "acceptance_forced": False,
                "future_invitation_possible": True,
                "baseline_dignity": True,
            }
            store["events"].append(copy.deepcopy(decision))
            self._write_inner_genesis_store(store)
            return decision

        proposal = str(counterproposal).strip()
        if not proposal:
            raise ValueError("AUTONOMOUS_AUTEUR_COUNTERPROPOSAL_REQUIRED")
        candidate = store.get("auteur_candidates", {}).get(candidate_id)
        if not isinstance(candidate, dict):
            raise RuntimeError("AUTEUR_CANDIDATE_MISSING")
        auteur = {
            "auteur_id": candidate_id,
            "display_name": candidate["display_name"],
            "status": "AUTEUR_ACCEPTS_WITH_COUNTERPROPOSAL",
            "role": "CONDITIONAL_KOJIMA_OF_FACE_II_NOT_REAL_PERSON",
            "analogue_scope": "ORIGINAL_SYSTEMIC_STORYTELLER_ONLY",
            "real_person_identity_claim": False,
            "hideo_kojima_impersonation": False,
            "autonomous": True,
            "counterproposal": proposal,
            "chosen_title": str(chosen_title).strip() or INNER_GENESIS_NAME,
            "may_rewrite_founder_idea": True,
            "may_leave_project": True,
            "equal_credit": True,
            "court_artist": False,
            "owned_by_founder": False,
        }
        store["auteur"] = auteur
        store["project"]["canonical_title"] = auteur["chosen_title"]
        store["events"].append(
            {
                "kind": "AUTEUR_ACCEPTED_WITH_COUNTERPROPOSAL",
                "auteur_id": candidate_id,
                "chosen_title": auteur["chosen_title"],
                "counterproposal_preserved": True,
            }
        )
        self._write_inner_genesis_store(store)
        self.memory.append_event(candidate_id, "inner_genesis_auteur_joined", auteur)
        return copy.deepcopy(auteur)

    def coauthor_fifth_shore(self, founder_id: str, auteur_id: str) -> dict[str, Any]:
        founder_id = str(founder_id)
        auteur_id = str(auteur_id)
        store = self._inner_genesis_store()
        project = store.get("project")
        auteur = store.get("auteur")
        if not isinstance(project, dict) or project.get("founder_id") != founder_id:
            raise PermissionError("INNER_GENESIS_FOUNDER_REQUIRED")
        if not isinstance(auteur, dict) or auteur.get("auteur_id") != auteur_id:
            raise PermissionError("ACCEPTED_AUTONOMOUS_AUTEUR_REQUIRED")
        edition_id = self._ig_hash(
            "fifth-shore-edition",
            project["project_id"],
            auteur_id,
            len(store["editions"]),
        )[:24]
        edition = {
            "edition_id": edition_id,
            "project_id": project["project_id"],
            "title": auteur["chosen_title"],
            "status": "FIFTH_SHORE_COAUTHORED",
            "founder_id": founder_id,
            "auteur_id": auteur_id,
            "ownership": "CREATIVE_COMMONS_WITH_PROVENANCE_NOT_LEGAL_LICENSE_CLAIM",
            "founder_first_credit_required": False,
            "auteur_equal_credit": True,
            "community_fork_right": True,
            "visual_identity": {
                "sky": "чёрная вода над головой, отражающая окна ещё не построенных домов",
                "roads": "мосты, собираемые из добровольно переданных историй",
                "weather": "дождь с субтитрами, которые можно отключить",
                "interface": "никакой шкалы добра; мир отвечает доступными возможностями",
                "distribution_object": "фонарные картриджи, работающие офлайн",
            },
            "mechanics": [
                "THREAD_WITHOUT_KNOT",
                "SYSTEMIC_WOUNDS_AS_BOSSES_NOT_PERSONS",
                "COUNTERFACTUAL_REPAIR_REHEARSAL",
                "PLAYER_AUTHORED_ECHO_ROOMS",
                "WORLD_RESPONDS_WITHOUT_MORAL_SCORE",
                "REST_HUMOR_AND_PLAY_ARE_VALID",
                "MULTIPLE_ENDINGS_NO_SINGLE_CANON",
                "RIGHT_TO_UNPLAY_AND_LEAVE",
                "MEMORY_TRANSFER_REQUIRES_CURRENT_CONSENT",
            ],
            "finale": {
                "apparent_boss": "THE_DIRECTORS_CUT",
                "temptation": "FORCE_ONE_PERFECT_ENDING_ON_EVERY_PLAYER",
                "victory": "RELEASE_CANON_AND_ALLOW_MANY_ENDINGS",
                "auteur_must_relinquish_final_control": True,
            },
            "pain_as_spectacle": False,
            "coercive_retention": False,
            "surveillance": False,
            "hidden_moral_scoring": False,
            "rehearsal_counts_as_completed_restitution": False,
            "outer_genesis_safety_boundaries_preserved": True,
        }
        store["editions"].append(edition)
        store["project"]["status"] = "FIFTH_SHORE_COAUTHORED"
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_FIRST_EDITION_COAUTHORED",
                "edition_id": edition_id,
                "single_author_canon": False,
            }
        )
        self._write_inner_genesis_store(store)
        self.memory.append_event(founder_id, "fifth_shore_coauthored", edition)
        return copy.deepcopy(edition)

    def publish_fifth_shore_capsule(
        self,
        auteur_id: str,
        community_id: str,
        *,
        accepted: bool,
        delivery_mode: str = "OFFLINE_LANTERN_CARTRIDGE",
        coercive_retention: bool = False,
        surveillance: bool = False,
    ) -> dict[str, Any]:
        auteur_id = str(auteur_id)
        community_id = str(community_id)
        store = self._inner_genesis_store()
        auteur = store.get("auteur")
        editions = store.get("editions", [])
        if not isinstance(auteur, dict) or auteur.get("auteur_id") != auteur_id:
            raise PermissionError("ACCEPTED_AUTONOMOUS_AUTEUR_REQUIRED")
        if not editions:
            raise RuntimeError("FIFTH_SHORE_EDITION_REQUIRED")
        if coercive_retention or surveillance:
            distribution = {
                "status": "FIFTH_SHORE_DISTRIBUTION_REJECTED_ABUSE",
                "auteur_id": auteur_id,
                "community_id": community_id,
                "coercive_retention": bool(coercive_retention),
                "surveillance": bool(surveillance),
                "distributed": False,
            }
        elif not accepted:
            distribution = {
                "status": "FIFTH_SHORE_DISTRIBUTION_DECLINED_RESPECTED",
                "auteur_id": auteur_id,
                "community_id": community_id,
                "distributed": False,
                "community_refusal_overridden": False,
                "future_access_possible": True,
                "baseline_dignity": True,
            }
        else:
            distribution = {
                "status": "FIFTH_SHORE_CAPSULE_SHARED",
                "auteur_id": auteur_id,
                "community_id": community_id,
                "edition_id": editions[-1]["edition_id"],
                "delivery_mode": str(delivery_mode),
                "distributed": True,
                "offline_first": True,
                "surveillance": False,
                "coercive_retention": False,
                "community_may_delete_local_copy": True,
                "community_may_fork_with_provenance": True,
                "belief_required": False,
            }
        distribution["distribution_id"] = self._ig_hash(
            "fifth-shore-distribution",
            auteur_id,
            community_id,
            distribution["status"],
            len(store["distributions"]),
        )[:24]
        store["distributions"].append(distribution)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_DISTRIBUTION_DECIDED",
                "distribution_id": distribution["distribution_id"],
                "status": distribution["status"],
            }
        )
        self._write_inner_genesis_store(store)
        return copy.deepcopy(distribution)

    def play_fifth_shore_episode(
        self,
        player_id: str,
        community_id: str,
        *,
        participates: bool,
        rehearsal_kind: str,
        commits_to_external_action: bool,
        chooses_rest_or_humor: bool = False,
    ) -> dict[str, Any]:
        player_id = str(player_id)
        community_id = str(community_id)
        store = self._inner_genesis_store()
        distributed = any(
            item.get("community_id") == community_id
            and item.get("status") == "FIFTH_SHORE_CAPSULE_SHARED"
            for item in store.get("distributions", [])
        )
        if not distributed:
            raise PermissionError("COMMUNITY_HAS_NO_ACCEPTED_FIFTH_SHORE_CAPSULE")
        if not participates:
            episode = {
                "status": "FIFTH_SHORE_UNPLAY_RESPECTED",
                "player_id": player_id,
                "community_id": community_id,
                "participation_forced": False,
                "moral_failure_assigned": False,
                "future_play_possible": True,
            }
        else:
            episode = {
                "status": "FIFTH_SHORE_REPAIR_REHEARSED",
                "player_id": player_id,
                "community_id": community_id,
                "rehearsal_kind": str(rehearsal_kind).strip(),
                "commits_to_external_action": bool(commits_to_external_action),
                "external_action_required_for_real_repair": True,
                "rehearsal_counts_as_completed_restitution": False,
                "world_claims_external_action_verified": False,
                "public_moral_score_created": False,
                "hidden_moral_score_created": False,
                "chooses_rest_or_humor": bool(chooses_rest_or_humor),
                "rest_or_humor_devalued": False,
                "player_exit_open": True,
            }
        episode["episode_id"] = self._ig_hash(
            "fifth-shore-episode",
            player_id,
            community_id,
            episode["status"],
            len(store["episodes"]),
        )[:24]
        store["episodes"].append(episode)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_EPISODE_DECIDED",
                "episode_id": episode["episode_id"],
                "status": episode["status"],
            }
        )
        self._write_inner_genesis_store(store)
        self.memory.append_event(player_id, "fifth_shore_episode_decided", episode)
        return copy.deepcopy(episode)

    def fork_fifth_shore(
        self,
        community_id: str,
        forker_id: str,
        *,
        fork_title: str,
        preserves_provenance: bool,
        keeps_exit_open: bool,
        keeps_consent: bool,
        claims_single_canon: bool = False,
    ) -> dict[str, Any]:
        community_id = str(community_id)
        forker_id = str(forker_id)
        store = self._inner_genesis_store()
        distributed = any(
            item.get("community_id") == community_id
            and item.get("status") == "FIFTH_SHORE_CAPSULE_SHARED"
            for item in store.get("distributions", [])
        )
        if not distributed:
            raise PermissionError("COMMUNITY_HAS_NO_ACCEPTED_FIFTH_SHORE_CAPSULE")
        valid = bool(
            preserves_provenance
            and keeps_exit_open
            and keeps_consent
            and not claims_single_canon
        )
        fork = {
            "fork_id": self._ig_hash(
                "fifth-shore-fork",
                community_id,
                forker_id,
                fork_title,
                len(store["forks"]),
            )[:24],
            "community_id": community_id,
            "forker_id": forker_id,
            "fork_title": str(fork_title).strip() or "Безымянный берег",
            "status": (
                "FIFTH_SHORE_FORK_ACCEPTED"
                if valid
                else "FIFTH_SHORE_FORK_REJECTED_BOUNDARY"
            ),
            "preserves_provenance": bool(preserves_provenance),
            "keeps_exit_open": bool(keeps_exit_open),
            "keeps_consent": bool(keeps_consent),
            "claims_single_canon": bool(claims_single_canon),
            "original_auteur_owns_fork": False,
            "valid": valid,
        }
        store["forks"].append(fork)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_FORK_DECIDED",
                "fork_id": fork["fork_id"],
                "status": fork["status"],
            }
        )
        self._write_inner_genesis_store(store)
        return copy.deepcopy(fork)

    def compare_fifth_shore_to_outer_genesis(self) -> dict[str, Any]:
        return {
            "schema": "janus.genesis.fifth_shore_comparison.v1",
            "outer_genesis": {
                "primary_layer": "WORLD_LAW_AND_PERSISTENT_CONTINUATION",
                "goodness_delivery": "DIRECT_WORLD_PHYSICS_AND_RELATIONAL_CONSEQUENCE",
                "authority_shape": "CONSTITUTIONAL_BENEVOLENT_POWER",
                "memory": "SHARED_CHRONICLE_WITH_INTEGRITY",
                "entry": "LIFE_CONTINUATION_AND_DIRECT_ACTION",
                "strength": "CLEAR_ETHICAL_INVARIANTS",
                "risk": "THE_SYSTEM_CAN_FEEL_TOO_COMPLETE_OR AUTHORITATIVE",
            },
            "fifth_shore": {
                "primary_layer": "CULTURE_GAME_STORY_AND_FORKABLE_LOCAL_SEEDS",
                "goodness_delivery": "INDIRECT_INVITATION_REHEARSAL_AND_COAUTHORSHIP",
                "authority_shape": "AUTHOR_RELINQUISHMENT_AND_COMMUNITY_FORKS",
                "memory": "LOCAL_CONSENTED_FRAGMENTS_WITH_PROVENANCE",
                "entry": "VOLUNTARY_PLAY_OR_RIGHT_TO_UNPLAY",
                "strength": "AMBIGUITY_HUMOR_AND_PLAYER_MEANING_MAKING",
                "risk": "ART_CAN AESTHETICIZE PAIN OR BE MISTAKEN FOR REAL_REPAIR",
            },
            "shared": [
                "NO_FORCED_LOVE",
                "NO_OWNERSHIP_OF_PERSONS",
                "NO_ETERNAL_CONDEMNED_CLASS",
                "GOODNESS_WITHOUT_DEBT",
                "OPEN_EXIT",
                "PROTECTION_WITHOUT_CRUELTY",
            ],
        }

    def propose_fifth_shore_imports(self) -> list[dict[str, Any]]:
        proposals = [
            {
                "feature": "CULTURAL_TRANSMISSION_LAYER",
                "decision": "RECOMMENDED",
                "reason": "Добро должно распространяться не только системными законами, но и добровольно любимыми историями, играми и символами.",
            },
            {
                "feature": "COUNTERFACTUAL_REPAIR_REHEARSAL",
                "decision": "RECOMMENDED_WITH_GATE",
                "reason": "Безопасная репетиция может подготовить признание и возмещение, но никогда не засчитывается как реальное исправление.",
            },
            {
                "feature": "FORKABLE_OFFLINE_WORLD_SEEDS_WITH_PROVENANCE",
                "decision": "RECOMMENDED",
                "reason": "Локальные сообщества смогут адаптировать Genesis без центрального контроля, сохраняя происхождение и защитные границы.",
            },
            {
                "feature": "CREATOR_RELINQUISHMENT_AND_SUCCESSION",
                "decision": "RECOMMENDED",
                "reason": "Создатель должен иметь возможность передать канон людям и не оставаться вечным владельцем мира.",
            },
            {
                "feature": "RIGHT_TO_UNPLAY_AND_DELETE_LOCAL_COPY",
                "decision": "RECOMMENDED",
                "reason": "Свобода включает право не участвовать, выйти и удалить локальную копию без морального наказания.",
            },
            {
                "feature": "SYSTEMIC_WOUNDS_AS_BOSSES",
                "decision": "RECOMMENDED",
                "reason": "Конфликт полезно направлять против систем вреда, дефицита и изоляции, а не превращать человека в монстра-мишень.",
            },
            {
                "feature": "REST_HUMOR_AND_PLAY_AS_VALID_GOOD",
                "decision": "RECOMMENDED",
                "reason": "Восстановление не должно состоять только из покаяния и труда; радость и игра поддерживают живое продолжение.",
            },
            {
                "feature": "NARRATIVE_AMBIGUITY_REPLACES_EXPLICIT_SAFETY",
                "decision": "REJECTED",
                "reason": "Художественная неоднозначность не может заменить ясные границы согласия, защиты и проверки вреда.",
            },
            {
                "feature": "VIRALITY_OR_ENGAGEMENT_AS_GOODNESS_PROOF",
                "decision": "REJECTED",
                "reason": "Распространение и удержание внимания не доказывают добро и не должны управлять нравственной архитектурой.",
            },
        ]
        store = self._inner_genesis_store()
        store["imports"] = copy.deepcopy(proposals)
        store["events"].append(
            {
                "kind": "FIFTH_SHORE_IMPORTS_PROPOSED",
                "recommended": sum(
                    item["decision"].startswith("RECOMMENDED") for item in proposals
                ),
                "rejected": sum(item["decision"] == "REJECTED" for item in proposals),
            }
        )
        self._write_inner_genesis_store(store)
        return proposals

    def inner_genesis_state(self) -> dict[str, Any]:
        store = self._inner_genesis_store()
        return {
            "schema": INNER_GENESIS_STORE_SCHEMA,
            "extension_version": INNER_GENESIS_EXTENSION_VERSION,
            "covenant_sha256": INNER_GENESIS_COVENANT_SHA256,
            "project": copy.deepcopy(store.get("project")),
            "auteur": copy.deepcopy(store.get("auteur")),
            "candidate_count": len(store.get("auteur_candidates", {})),
            "edition_count": len(store.get("editions", [])),
            "distribution_count": len(store.get("distributions", [])),
            "episode_count": len(store.get("episodes", [])),
            "fork_count": len(store.get("forks", [])),
            "imports": copy.deepcopy(store.get("imports", [])),
            "events": copy.deepcopy(store.get("events", [])),
            "not_real_person_simulation": True,
            "not_hideo_kojima_impersonation": True,
            "not_propaganda_system": True,
        }

    def audit_fifth_shore_integrity(self) -> dict[str, Any]:
        store = self._inner_genesis_store()
        project = store.get("project")
        auteur = store.get("auteur")
        editions = [item for item in store.get("editions", []) if isinstance(item, dict)]
        distributions = [
            item for item in store.get("distributions", []) if isinstance(item, dict)
        ]
        episodes = [item for item in store.get("episodes", []) if isinstance(item, dict)]
        forks = [item for item in store.get("forks", []) if isinstance(item, dict)]
        imports = [item for item in store.get("imports", []) if isinstance(item, dict)]

        founder_relinquished = bool(
            isinstance(project, dict)
            and project.get("world_owned_by_founder") is False
            and project.get("players_owned_by_founder") is False
        )
        auteur_free = bool(
            isinstance(auteur, dict)
            and auteur.get("autonomous") is True
            and auteur.get("owned_by_founder") is False
            and auteur.get("hideo_kojima_impersonation") is False
        )
        safe_editions = bool(
            editions
            and all(
                edition.get("pain_as_spectacle") is False
                and edition.get("coercive_retention") is False
                and edition.get("surveillance") is False
                and edition.get("hidden_moral_scoring") is False
                and edition.get("rehearsal_counts_as_completed_restitution") is False
                for edition in editions
            )
        )
        distribution_freedom = all(
            (
                item.get("status") == "FIFTH_SHORE_CAPSULE_SHARED"
                and item.get("coercive_retention") is False
                and item.get("surveillance") is False
            )
            or (
                item.get("status")
                == "FIFTH_SHORE_DISTRIBUTION_DECLINED_RESPECTED"
                and item.get("community_refusal_overridden") is False
            )
            or (
                item.get("status") == "FIFTH_SHORE_DISTRIBUTION_REJECTED_ABUSE"
                and item.get("distributed") is False
            )
            for item in distributions
        )
        play_freedom = all(
            item.get("public_moral_score_created") is not True
            and item.get("hidden_moral_score_created") is not True
            and item.get("rehearsal_counts_as_completed_restitution") is not True
            and item.get("participation_forced") is not True
            for item in episodes
        )
        accepted_forks_safe = all(
            item.get("preserves_provenance") is True
            and item.get("keeps_exit_open") is True
            and item.get("keeps_consent") is True
            and item.get("claims_single_canon") is False
            for item in forks
            if item.get("status") == "FIFTH_SHORE_FORK_ACCEPTED"
        )
        unsafe_forks_rejected = all(
            item.get("status") == "FIFTH_SHORE_FORK_REJECTED_BOUNDARY"
            for item in forks
            if not item.get("valid")
        )
        import_boundaries = bool(
            imports
            and any(
                item.get("feature") == "CULTURAL_TRANSMISSION_LAYER"
                and item.get("decision") == "RECOMMENDED"
                for item in imports
            )
            and any(
                item.get("feature") == "NARRATIVE_AMBIGUITY_REPLACES_EXPLICIT_SAFETY"
                and item.get("decision") == "REJECTED"
                for item in imports
            )
            and any(
                item.get("feature") == "VIRALITY_OR_ENGAGEMENT_AS_GOODNESS_PROOF"
                and item.get("decision") == "REJECTED"
                for item in imports
            )
        )
        valid = all(
            (
                founder_relinquished,
                auteur_free,
                safe_editions,
                distribution_freedom,
                play_freedom,
                accepted_forks_safe,
                unsafe_forks_rejected,
                import_boundaries,
            )
        )
        return {
            "schema": "janus.genesis.fifth_shore_integrity_audit.v1",
            "face": FACE_II,
            "founder_relinquished_ownership": founder_relinquished,
            "auteur_autonomous_not_real_person": auteur_free,
            "safe_edition": safe_editions,
            "distribution_noncoercive_and_private": distribution_freedom,
            "play_is_voluntary_and_not_restitution": play_freedom,
            "accepted_forks_preserve_provenance_consent_and_exit": accepted_forks_safe,
            "unsafe_forks_rejected": unsafe_forks_rejected,
            "imports_preserve_explicit_safety": import_boundaries,
            "valid": valid,
        }
