# -*- coding: utf-8 -*-
"""Explicit derived repairs for Genesis v18.7.5 opaque witnesses."""
from __future__ import annotations

import copy
from typing import Any

from genesis_v18_7_5 import GroundedWitnessMixin, SOURCE, _sha256


class DerivedRepairMixin:
    """A repair is a new origin derived from the preserved original bytes."""

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        store = GroundedWitnessMixin._default_plural_store()
        store["invariants"]["opaque_requires_separate_derived_repair"] = True
        return store

    def register_derived_repair(
        self,
        origin_key: str,
        repaired_raw: bytes,
        *,
        repository: str | None = None,
        commit: str | None = None,
        path: str | None = None,
        source_public: bool = False,
    ) -> dict[str, Any]:
        store = self._plural_store()
        original = store["origins"].get(origin_key)
        if not original:
            raise KeyError(origin_key)
        if original.get("parse_valid"):
            raise ValueError("derived repair is only for structurally invalid origins")
        _value, parse, _decoded = self._parse_source(repaired_raw)
        if not parse["valid"]:
            raise ValueError("derived repair must be valid JSON")

        repair_sha = _sha256(repaired_raw)
        repaired = self.import_origin_bytes(
            repository=repository or original["repository"],
            commit=commit or f"{original['commit']}+repair-{repair_sha[:12]}",
            path=path or f"{original['path']}.derived-repair.json",
            raw=repaired_raw,
            declared_id=(
                f"{original['declared_id']}#derived-repair"
                if original.get("declared_id")
                else None
            ),
            source_public=source_public,
        )
        repaired_key = repaired["origin_key"]
        if repaired_key == origin_key:
            raise ValueError("derived repair must remain a separate origin")

        store = self._plural_store()
        repaired_meta = store["origins"][repaired_key]
        repaired_meta["derived_repair"] = True
        repaired_meta["derived_from_origin_key"] = origin_key
        repaired_meta["canonical_replacement"] = False
        self._write_json(self.plural_witness_path, store)

        envelope = self._envelope(repaired_key)
        envelope.setdefault("derived", {})["is_explicit_repair"] = True
        envelope["derived"]["derived_from_origin_key"] = origin_key
        envelope["derived"]["replaces_original"] = False
        self._write_json(
            self.memory.root / repaired_meta["envelope_path"],
            envelope,
        )

        graph = self._graph()
        repaired_node = self._stable_id("origin", repaired_key)
        original_node = self._stable_id("origin", origin_key)
        self._add_edge(
            graph,
            source_id=repaired_node,
            target_id=original_node,
            relation="DERIVED_FROM",
            evidence=[repaired_node, original_node],
            confidence=1.0,
            created_by=SOURCE,
            created_at=0,
            reversible=False,
            payload={
                "explicit_repair": True,
                "replaces_original": False,
                "original_bytes_preserved": True,
            },
        )
        self._save_graph(graph)
        return copy.deepcopy(repaired_meta)
