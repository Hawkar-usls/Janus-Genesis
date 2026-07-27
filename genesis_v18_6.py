# -*- coding: utf-8 -*-
"""Genesis v18.6 — The Bloom of Possibility.

Good is not a currency and possibility is not a moral prize. Concrete acts leave
verifiable semantic evidence in an HRaiN-compatible graph. When the evidence
shows that a road, place, relationship or capability now exists, new actions
become possible because the world has genuinely become wider.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from genesis_v18_6_catalog import POSSIBILITY_CATALOG
from genesis_v18_models import UniversalGodMode, WorldResult
from genesis_v18_playable import OfflineActionInterpreterV18

__version__ = "18.6.0"
GRAPH_SCHEMA_VERSION = "HRAIN-GENESIS-GRAPH-v1"
CANONICAL_SEED_SHA256 = "44e21fdc9d37fda98e2e73b0c9eb268bd04cdca9d84d0519e4f1166be22b46fc"
SOURCE = "janus_genesis_v18_6"


def _preservation_safe_text(text: str) -> str:
    """Prevent Russian 'сохранить' from being misread as the substring 'ранить'."""
    return re.sub(r"\bсохран\w*\b", "защитить", text, flags=re.IGNORECASE)


class BoundaryAwareUniversalGodMode(UniversalGodMode):
    def classify(self, request: str):
        return super().classify(_preservation_safe_text(request))


class BoundaryAwareActionInterpreter(OfflineActionInterpreterV18):
    def interpret(self, player, action: str):
        return super().interpret(player, _preservation_safe_text(action))


class PossibilityBloomMixin:
    """Create and expose affordances from provenance-rich semantic evidence."""

    POSSIBILITY_CATALOG = POSSIBILITY_CATALOG

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.possibility_graph_path = self.memory.root / "hrain_genesis_graph_v18_6.json"

        previous = self.interpreter
        boundary_aware = BoundaryAwareActionInterpreter()
        boundary_aware.DESTRUCTIVE = set(previous.DESTRUCTIVE)
        boundary_aware.CONSTRUCTIVE = set(previous.CONSTRUCTIVE)
        self.interpreter = boundary_aware
        self.power = BoundaryAwareUniversalGodMode()

    @staticmethod
    def _default_graph() -> dict[str, Any]:
        return {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "canonical_seed_sha256": CANONICAL_SEED_SHA256,
            "backend": {
                "kind": "json_sidecar",
                "canonical_database_connected": False,
                "canonical_database_name": None,
            },
            "nodes": [],
            "edges": [],
            "players": {},
            "invariants": {
                "good_is_not_currency": True,
                "moral_rank_required": False,
                "possibilities_can_be_reopened": True,
                "harm_permanently_erases_possibility": False,
                "changes_god_mode_law": False,
                "changes_moral_routing": False,
                "claims_simulated_residents_are_conscious": False,
            },
        }

    def _graph(self) -> dict[str, Any]:
        graph = self._read_json(self.possibility_graph_path, self._default_graph())
        if not isinstance(graph, dict) or graph.get("schema_version") != GRAPH_SCHEMA_VERSION:
            graph = self._default_graph()
        graph.setdefault("nodes", [])
        graph.setdefault("edges", [])
        graph.setdefault("players", {})
        return graph

    def _save_graph(self, graph: dict[str, Any]) -> None:
        self._write_json(self.possibility_graph_path, graph)

    @staticmethod
    def _integrity_hash(payload: dict[str, Any]) -> str:
        sealed = dict(payload)
        sealed.pop("integrity_hash", None)
        canonical = json.dumps(sealed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _stable_id(*parts: object) -> str:
        material = "|".join(str(part) for part in parts)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]

    def _upsert_node(
        self,
        graph: dict[str, Any],
        *,
        node_id: str,
        node_type: str,
        created_at: int,
        confidence: float,
        mutable: bool,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        for node in graph["nodes"]:
            if node["id"] == node_id:
                if node.get("mutable"):
                    node["payload"] = payload
                    node["confidence"] = float(confidence)
                    node["integrity_hash"] = self._integrity_hash(node)
                return node
        node = {
            "id": node_id,
            "type": node_type,
            "source": SOURCE,
            "created_at": max(0, int(created_at)),
            "confidence": min(1.0, max(0.0, float(confidence))),
            "integrity_hash": "",
            "mutable": bool(mutable),
            "payload": payload,
        }
        node["integrity_hash"] = self._integrity_hash(node)
        graph["nodes"].append(node)
        return node

    def _add_edge(
        self,
        graph: dict[str, Any],
        *,
        source_id: str,
        target_id: str,
        relation: str,
        evidence: list[str],
        confidence: float,
        created_by: str,
        created_at: int,
        reversible: bool,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        edge_id = self._stable_id(
            "edge", source_id, target_id, relation, created_at,
            json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
        )
        for edge in graph["edges"]:
            if edge["id"] == edge_id:
                return edge
        edge = {
            "id": edge_id,
            "from": source_id,
            "to": target_id,
            "relation": relation,
            "evidence": list(dict.fromkeys(evidence)),
            "confidence": min(1.0, max(0.0, float(confidence))),
            "created_by": created_by,
            "created_at": max(0, int(created_at)),
            "reversible": bool(reversible),
            "integrity_hash": "",
            "payload": payload or {},
        }
        edge["integrity_hash"] = self._integrity_hash(edge)
        graph["edges"].append(edge)
        return edge

    @staticmethod
    def _profile(graph: dict[str, Any], player_id: str) -> dict[str, Any]:
        return graph.setdefault("players", {}).setdefault(
            player_id,
            {"facets": [], "facet_evidence": {}, "possibilities": []},
        )

    def _facets_for_action(self, action: str) -> list[str]:
        text = UniversalGodMode.normalize(_preservation_safe_text(action))
        touched = [
            facet
            for facet, fragments in self.FACETS.items()
            if any(fragment in text for fragment in fragments)
        ]
        return list(dict.fromkeys(touched or ["trust"]))

    def _blueprint(self, possibility_id: str) -> dict[str, object]:
        return next(item for item in self.POSSIBILITY_CATALOG if item["id"] == possibility_id)

    def _record_and_bloom(
        self,
        player_id: str,
        action: str,
        base: WorldResult,
        *,
        good_delta: int,
    ) -> list[str]:
        player = self.memory.load_player(player_id)
        graph = self._graph()
        profile = self._profile(graph, player_id)
        tick = int(player.tick)

        player_node_id = self._stable_id("player", player_id)
        self._upsert_node(
            graph,
            node_id=player_node_id,
            node_type="PLAYER",
            created_at=0,
            confidence=1.0,
            mutable=True,
            payload={"player_id": player_id, "display_name": player.display_name},
        )
        action_node_id = self._stable_id("action", player_id, tick, action, base.status)
        self._upsert_node(
            graph,
            node_id=action_node_id,
            node_type="ACTION",
            created_at=tick,
            confidence=1.0,
            mutable=False,
            payload={
                "player_id": player_id,
                "action": action,
                "runtime_status": base.status,
                "good_delta": max(0, int(good_delta)),
            },
        )
        self._add_edge(
            graph,
            source_id=player_node_id,
            target_id=action_node_id,
            relation="OBSERVED",
            evidence=[action_node_id],
            confidence=1.0,
            created_by=SOURCE,
            created_at=tick,
            reversible=False,
        )

        newly_bloomed: list[str] = []
        if good_delta > 0:
            evidence_by_facet: dict[str, str] = {}
            for facet in self._facets_for_action(action):
                evidence_id = self._stable_id("evidence", player_id, tick, facet, action)
                evidence_by_facet[facet] = evidence_id
                self._upsert_node(
                    graph,
                    node_id=evidence_id,
                    node_type="EVIDENCE",
                    created_at=tick,
                    confidence=0.95,
                    mutable=False,
                    payload={
                        "facet": facet,
                        "source_action_id": action_node_id,
                        "source_action": action,
                        "external_good_discounted": False,
                    },
                )
                self._add_edge(
                    graph,
                    source_id=action_node_id,
                    target_id=evidence_id,
                    relation="CAUSED",
                    evidence=[action_node_id],
                    confidence=0.95,
                    created_by=player_id,
                    created_at=tick,
                    reversible=False,
                )
                self._add_edge(
                    graph,
                    source_id=player_node_id,
                    target_id=evidence_id,
                    relation="REMEMBERS",
                    evidence=[action_node_id],
                    confidence=0.95,
                    created_by=SOURCE,
                    created_at=tick,
                    reversible=False,
                )
                if facet not in profile["facets"]:
                    profile["facets"].append(facet)
                profile.setdefault("facet_evidence", {}).setdefault(facet, []).append(evidence_id)
                profile["facet_evidence"][facet] = list(dict.fromkeys(profile["facet_evidence"][facet]))

            known = set(profile["facets"])
            for blueprint in self.POSSIBILITY_CATALOG:
                possibility_id = str(blueprint["id"])
                requirements = tuple(str(item) for item in blueprint["requires"])
                if possibility_id in profile["possibilities"] or not set(requirements).issubset(known):
                    continue

                node_id = self._stable_id("possibility", player_id, possibility_id)
                prerequisite_evidence = [
                    profile["facet_evidence"][facet][-1]
                    for facet in requirements
                ]
                self._upsert_node(
                    graph,
                    node_id=node_id,
                    node_type="POSSIBILITY",
                    created_at=tick,
                    confidence=0.90,
                    mutable=True,
                    payload={
                        "possibility_id": possibility_id,
                        "title": blueprint["title"],
                        "description": blueprint["description"],
                        "requires": list(requirements),
                        "active": True,
                        "reopenable": True,
                        "not_a_reward": True,
                        "moral_rank_required": False,
                        "choices": list(blueprint["choices"]),
                        "child_choices": list(blueprint["child_choices"]),
                    },
                )
                self._add_edge(
                    graph,
                    source_id=action_node_id,
                    target_id=node_id,
                    relation="CREATED",
                    evidence=prerequisite_evidence,
                    confidence=0.90,
                    created_by=player_id,
                    created_at=tick,
                    reversible=False,
                    payload={"possibility_id": possibility_id},
                )
                for evidence_id in prerequisite_evidence:
                    self._add_edge(
                        graph,
                        source_id=node_id,
                        target_id=evidence_id,
                        relation="DEPENDS_ON",
                        evidence=[evidence_id],
                        confidence=0.90,
                        created_by=SOURCE,
                        created_at=tick,
                        reversible=True,
                    )
                    self._add_edge(
                        graph,
                        source_id=evidence_id,
                        target_id=node_id,
                        relation="CONFIRMED",
                        evidence=[evidence_id],
                        confidence=0.90,
                        created_by=SOURCE,
                        created_at=tick,
                        reversible=False,
                    )
                profile["possibilities"].append(possibility_id)
                newly_bloomed.append(possibility_id)
                self.memory.append_event(
                    player_id,
                    "possibility_bloomed",
                    {
                        "possibility_id": possibility_id,
                        "graph_node_id": node_id,
                        "requires": list(requirements),
                        "moral_rank_used": False,
                    },
                )

        profile["facets"] = list(dict.fromkeys(profile["facets"]))
        profile["possibilities"] = list(dict.fromkeys(profile["possibilities"]))
        self._save_graph(graph)
        return newly_bloomed

    def _possibility_choices(self, player_id: str, *, only: list[str] | None = None) -> list[str]:
        graph = self._graph()
        profile = self._profile(graph, player_id)
        selected = only if only is not None else list(profile["possibilities"])
        child_role = bool(getattr(self, "_is_child", lambda _id: False)(player_id))
        choices: list[str] = []
        for possibility_id in selected:
            blueprint = self._blueprint(possibility_id)
            source = blueprint["child_choices"] if child_role else blueprint["choices"]
            if only is None:
                choices.append(str(source[0]))
            else:
                choices.extend(str(item) for item in source)
        return list(dict.fromkeys(choices))

    def weave_possibility_after_action(
        self,
        player_id: str,
        action: str,
        base: WorldResult,
        *,
        good_before: int,
    ) -> WorldResult:
        player = self.memory.load_player(player_id)
        newly_bloomed = self._record_and_bloom(
            player_id,
            action,
            base,
            good_delta=max(0, int(player.good_count) - int(good_before)),
        )

        choices = list(base.choices)
        choices.extend(self._possibility_choices(player_id, only=newly_bloomed))
        choices.extend(self._possibility_choices(player_id))
        if not choices:
            choices.extend(["Ответить своими словами", "Продолжить путь без готовой кнопки"])
        choices = list(dict.fromkeys(choices))

        narrative = base.narrative
        if newly_bloomed:
            titles = [str(self._blueprint(item)["title"]) for item in newly_bloomed]
            narrative += (
                "\n\nЦветение возможности: " + ", ".join(titles) + ". "
                "Это не награда и не моральный ранг. Мир стал шире, потому что в нём теперь действительно существует необходимая связь, место или способность."
            )
        return replace(base, narrative=narrative, choices=choices)

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        graph = self._graph()
        profile = self._profile(graph, player_id)
        state["available_possibilities"] = len(profile["possibilities"])
        state["possibility_titles"] = [
            str(self._blueprint(item)["title"])
            for item in profile["possibilities"]
        ]
        state["possibility_law"] = "Добро не покупает доступ; оно создаёт то, благодаря чему новый путь становится реальным."
        self._save_graph(graph)
        return state

    def verify_possibility_graph(self) -> tuple[bool, int, int, str | None]:
        graph = self._graph()
        node_ids = {node.get("id") for node in graph["nodes"]}
        if len(node_ids) != len(graph["nodes"]):
            return False, len(graph["nodes"]), len(graph["edges"]), "duplicate node id"
        for node in graph["nodes"]:
            if node.get("integrity_hash") != self._integrity_hash(node):
                return False, len(graph["nodes"]), len(graph["edges"]), f"invalid node hash: {node.get('id')}"
        edge_ids: set[str] = set()
        for edge in graph["edges"]:
            if edge.get("id") in edge_ids:
                return False, len(graph["nodes"]), len(graph["edges"]), "duplicate edge id"
            edge_ids.add(str(edge.get("id")))
            if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
                return False, len(graph["nodes"]), len(graph["edges"]), f"dangling edge: {edge.get('id')}"
            if edge.get("integrity_hash") != self._integrity_hash(edge):
                return False, len(graph["nodes"]), len(graph["edges"]), f"invalid edge hash: {edge.get('id')}"
        return True, len(graph["nodes"]), len(graph["edges"]), None

    def possibility_graph_state(self, player_id: str | None = None) -> dict[str, Any]:
        graph = self._graph()
        valid, nodes, edges, error = self.verify_possibility_graph()
        result: dict[str, Any] = {
            "schema_version": graph["schema_version"],
            "backend": graph["backend"],
            "invariants": graph["invariants"],
            "valid": valid,
            "node_count": nodes,
            "edge_count": edges,
            "error": error,
        }
        if player_id is not None:
            result["player_id"] = player_id
            result["profile"] = self._profile(graph, player_id)
            result["possibilities"] = [
                node
                for node in graph["nodes"]
                if node.get("type") == "POSSIBILITY"
                and node.get("payload", {}).get("possibility_id") in result["profile"]["possibilities"]
            ]
        self._save_graph(graph)
        return result
