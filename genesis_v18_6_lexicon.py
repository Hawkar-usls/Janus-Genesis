# -*- coding: utf-8 -*-
"""External lexical gifts for Genesis v18.6.

VOCAD stays the native semantic core. HRaiN stores one external-lexicon node;
a token becomes a graph node only after it is linked to a real concept.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "janus.genesis.lexicon.manifest.v1"
REGISTRY_SCHEMA = "janus.genesis.lexicon.registry.v1"
SOURCE = "janus_genesis_v18_6_external_lexicons"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class ExternalLexiconGiftMixin:
    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.external_lexicon_registry_path = self.memory.root / "external_lexicons_v18_6.json"

    @staticmethod
    def _default_lexicons() -> dict[str, Any]:
        return {
            "schema": REGISTRY_SCHEMA,
            "lexicons": {},
            "invariants": {
                "vocad_is_native_semantic_core": True,
                "external_lexicon_replaces_vocad": False,
                "source_order_must_be_preserved": True,
                "duplicates_must_be_preserved": True,
                "all_tokens_become_visible_graph_nodes": False,
                "license_must_be_confirmed_before_redistribution": True
            }
        }

    def _lexicons(self) -> dict[str, Any]:
        store = self._read_json(self.external_lexicon_registry_path, self._default_lexicons())
        if not isinstance(store, dict) or store.get("schema") != REGISTRY_SCHEMA:
            store = self._default_lexicons()
        store.setdefault("lexicons", {})
        store.setdefault("invariants", self._default_lexicons()["invariants"])
        return store

    def _save_lexicons(self, store: dict[str, Any]) -> None:
        self._write_json(self.external_lexicon_registry_path, store)

    @staticmethod
    def _load_manifest(value: dict[str, Any] | str | Path) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else json.loads(Path(value).read_text(encoding="utf-8"))

    @staticmethod
    def _validate_manifest(m: dict[str, Any]) -> None:
        required = {
            "schema", "lexicon_id", "name", "kind", "language", "token_count",
            "source", "indexing", "source_sha256", "generated_sha256",
            "order_preserved", "duplicates_preserved", "accepted_by", "role",
            "redistribution"
        }
        missing = sorted(required - set(m))
        if missing:
            raise ValueError("missing lexicon fields: " + ", ".join(missing))
        if m["schema"] != MANIFEST_SCHEMA or m["accepted_by"] != "JANUS GENESIS":
            raise ValueError("unsupported or unaccepted lexicon manifest")
        if m["role"] != "external_lexical_gift" or int(m["token_count"]) <= 0:
            raise ValueError("invalid external lexical gift")
        if not SHA256_RE.fullmatch(str(m["source_sha256"])) or not SHA256_RE.fullmatch(str(m["generated_sha256"])):
            raise ValueError("invalid lexicon hash")
        idx = m.get("indexing") or {}
        if idx.get("id_rule") != "array_index":
            raise ValueError("token IDs must equal array indexes")
        if idx.get("preserve_source_order") is not True or idx.get("sorting_allowed") is not False:
            raise ValueError("source order must be preserved")
        if idx.get("deduplication_allowed") is not False:
            raise ValueError("deduplication is forbidden")
        if m.get("order_preserved") is not True or m.get("duplicates_preserved") is not True:
            raise ValueError("order or duplicate preservation is unproven")

    def register_external_lexicon(self, value: dict[str, Any] | str | Path) -> dict[str, Any]:
        m = self._load_manifest(value)
        self._validate_manifest(m)
        lexicon_id = str(m["lexicon_id"])
        store = self._lexicons()
        old = store["lexicons"].get(lexicon_id)
        if old and old.get("generated_sha256") != m["generated_sha256"]:
            raise ValueError("lexicon_id already has another generated hash")
        store["lexicons"][lexicon_id] = m
        self._save_lexicons(store)

        graph = self._graph()
        lex = self._stable_id("external-lexicon", lexicon_id)
        received_as = str((m.get("source") or {}).get("received_as") or "external source")
        provenance = self._stable_id("provenance", received_as)
        vocad = self._stable_id("system", "VOCAD")
        self._upsert_node(graph, node_id=lex, node_type="EXTERNAL_LEXICON", created_at=0, confidence=1.0, mutable=False,
                          payload={"lexicon_id": lexicon_id, "name": m["name"], "kind": m["kind"],
                                   "language": m["language"], "token_count": int(m["token_count"]),
                                   "source_sha256": m["source_sha256"], "generated_sha256": m["generated_sha256"],
                                   "role": m["role"], "visible_token_nodes": 0, "vocad_replaced": False})
        self._upsert_node(graph, node_id=provenance, node_type="PROVENANCE", created_at=0, confidence=0.95, mutable=False,
                          payload={"label": received_as, "source": m["source"], "redistribution": m["redistribution"]})
        self._upsert_node(graph, node_id=vocad, node_type="SYSTEM", created_at=0, confidence=1.0, mutable=False,
                          payload={"system_id": "VOCAD", "role": "native_semantic_core"})
        proof = [m["source_sha256"], m["generated_sha256"]]
        self._add_edge(graph, source_id=lex, target_id=provenance, relation="RECEIVED_FROM", evidence=proof,
                       confidence=0.95, created_by=SOURCE, created_at=0, reversible=False)
        self._add_edge(graph, source_id=lex, target_id=vocad, relation="SUPPLEMENTS", evidence=proof,
                       confidence=1.0, created_by=SOURCE, created_at=0, reversible=True,
                       payload={"replaces_native_vocabulary": False})
        self._save_graph(graph)
        return {"lexicon_id": lexicon_id, "graph_node_id": lex, "token_count": int(m["token_count"]),
                "visible_token_nodes": 0, "vocad_replaced": False}

    def promote_lexicon_token(self, *, lexicon_id: str, token_id: int, token: str,
                              concept_id: str, concept_label: str) -> dict[str, str]:
        store = self._lexicons()
        m = store["lexicons"].get(lexicon_id)
        if not m:
            raise ValueError("lexicon is not registered")
        token_id = int(token_id)
        if token_id < 0 or token_id >= int(m["token_count"]) or not token:
            raise ValueError("invalid token reference")
        graph = self._graph()
        lex = self._stable_id("external-lexicon", lexicon_id)
        tok = self._stable_id("lexicon-token", lexicon_id, token_id)
        concept = self._stable_id("vocad-concept", concept_id)
        proof = [m["generated_sha256"]]
        self._upsert_node(graph, node_id=tok, node_type="TOKEN", created_at=0, confidence=0.95, mutable=False,
                          payload={"lexicon_id": lexicon_id, "token_id": token_id, "token": token, "id_rule": "array_index"})
        self._upsert_node(graph, node_id=concept, node_type="CONCEPT", created_at=0, confidence=1.0, mutable=True,
                          payload={"concept_id": concept_id, "label": concept_label, "semantic_core": "VOCAD"})
        self._add_edge(graph, source_id=lex, target_id=tok, relation="CONTAINS", evidence=proof,
                       confidence=1.0, created_by=SOURCE, created_at=0, reversible=False)
        self._add_edge(graph, source_id=tok, target_id=concept, relation="EXPRESSES", evidence=proof,
                       confidence=0.90, created_by=SOURCE, created_at=0, reversible=True)
        lex_node = next(node for node in graph["nodes"] if node["id"] == lex)
        lex_node["payload"]["visible_token_nodes"] = sum(
            node["type"] == "TOKEN" and node["payload"].get("lexicon_id") == lexicon_id for node in graph["nodes"]
        )
        lex_node["integrity_hash"] = self._integrity_hash(lex_node)
        self._save_graph(graph)
        return {"token_node_id": tok, "concept_node_id": concept}

    def external_lexicon_state(self) -> dict[str, Any]:
        store = self._lexicons()
        graph = self._graph()
        return {"schema": store["schema"], "invariants": store["invariants"], "lexicons": store["lexicons"],
                "promoted_token_nodes": sum(node["type"] == "TOKEN" for node in graph["nodes"])}
