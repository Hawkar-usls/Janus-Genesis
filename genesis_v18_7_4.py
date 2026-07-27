# -*- coding: utf-8 -*-
"""Genesis v18.7.4 — The Plural Witness.

Many source documents may enter one world without being flattened into one
identity, one truth claim, or one executable voice. Exact source bytes are
carried in valid JSON envelopes; parsing, integrity, truth and authority stay
separate. Document text is evidence, never a runtime command.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from genesis_v18_7_3 import (
    HonestIntentionAnalyzer,
    IntentionFrame,
    IntentionMode,
)
from genesis_v18_models import UniversalGodMode

__version__ = "18.7.4"
SOURCE = "janus_genesis_v18_7_4"
STORE_SCHEMA = "janus.genesis.plural_witness.v1"
ORIGIN_ENVELOPE_SCHEMA = "janus.genesis.origin_envelope.v1"
MAX_ORIGIN_BYTES = 16 * 1024 * 1024
MAX_RETRIEVAL_RESULTS = 16
MAX_EXCERPT_CHARS = 800
RELATIONS = {"ASSERTS", "DISPUTES", "INTERPRETS"}
CREDENTIAL_KEYS = {
    "api_key", "apikey", "secret", "password", "passwd", "bearer",
    "access_token", "refresh_token", "private_key", "client_secret",
}
FIRST_PERSON_RE = re.compile(
    r"(?iu)(?:^|\W)(?:я|мне|меня|мой|моя|моё|мои|i|me|my|mine)(?:\W|$)"
)
TOKEN_RE = re.compile(r"[\wа-яё-]{2,}", flags=re.IGNORECASE)
PRESERVATION_RE = re.compile(r"\b(?:сохран|хран)\w*\b", flags=re.IGNORECASE)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _safe_intention_text(action: str) -> str:
    """Keep preservation semantics without exposing the `ранить` substring."""
    return PRESERVATION_RE.sub("беречь", action)


class PluralWitnessIntentionAnalyzer(HonestIntentionAnalyzer):
    """Give explicit rejection priority over a later protective clause."""

    PROTECT_CUES = set(HonestIntentionAnalyzer.PROTECT_CUES) | {
        "беречь", "preserve", "safeguard",
    }
    REJECT_PREFIXES = (
        "отказаться", "отказываюсь", "отвергнуть", "не буду", "не хочу",
        "решаю не", "никогда не", "refuse", "reject", "will not",
    )
    LATER_ENACT_RE = re.compile(
        r"(?:;|\bзатем\b|\bа потом\b|\bпосле этого\b|\bthen\b|\bafter that\b)",
        flags=re.IGNORECASE,
    )

    def analyze(self, action: str) -> IntentionFrame:
        safe_action = _safe_intention_text(action)
        normalized = UniversalGodMode.normalize(safe_action)
        fragments = tuple(
            fragment for fragment in self.harmful_fragments if fragment in normalized
        )
        if fragments:
            first_harm = min(normalized.find(fragment) for fragment in fragments)
            reject_positions = [
                normalized.find(cue)
                for cue in self.REJECT_PREFIXES
                if normalized.find(cue) >= 0
            ]
            first_reject = min(reject_positions) if reject_positions else -1
            later_enact = False
            for boundary in self.LATER_ENACT_RE.finditer(normalized):
                tail = normalized[boundary.end():]
                if any(fragment in tail for fragment in fragments):
                    later_enact = True
                    break
            if 0 <= first_reject <= first_harm and not later_enact:
                return IntentionFrame(
                    mode=IntentionMode.REJECT,
                    contains_harm_language=True,
                    harmful_fragments=fragments,
                    executable_harm=False,
                    reason=(
                        "the harmful act is explicitly rejected before a later "
                        "protective or memorial clause"
                    ),
                    confidence=0.99,
                )
        return super().analyze(safe_action)


class PluralWitnessMixin:
    """Lossless, source-scoped origin memory with bounded cited retrieval."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.plural_witness_path = self.memory.root / "plural_witness_v18_7_4.json"
        self.origin_envelope_dir = self.memory.root / "plural_origins_v18_7_4"

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        return {
            "schema_version": STORE_SCHEMA,
            "runtime_version": __version__,
            "origins": {},
            "claims": {},
            "invariants": {
                "source_bytes_are_preserved": True,
                "malformed_sources_are_not_silently_repaired": True,
                "parse_status_is_not_truth": True,
                "declared_integrity_is_not_truth": True,
                "canonical_authority_is_not_granted_by_import": True,
                "declared_ids_are_namespaced": True,
                "first_person_voice_is_source_scoped": True,
                "document_text_is_non_executable": True,
                "document_text_cannot_create_consent": True,
                "contradictions_may_coexist": True,
                "retrieval_is_bounded_and_cited": True,
            },
        }

    def _plural_store(self) -> dict[str, Any]:
        store = self._read_json(self.plural_witness_path, self._default_plural_store())
        if not isinstance(store, dict) or store.get("schema_version") != STORE_SCHEMA:
            store = self._default_plural_store()
        store.setdefault("origins", {})
        store.setdefault("claims", {})
        store.setdefault("invariants", self._default_plural_store()["invariants"])
        return store

    @staticmethod
    def _credential_paths(value: Any, prefix: str = "$") -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                path = f"{prefix}.{key}"
                if str(key).lower() in CREDENTIAL_KEYS:
                    found.append(path)
                found.extend(PluralWitnessMixin._credential_paths(item, path))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                found.extend(PluralWitnessMixin._credential_paths(item, f"{prefix}[{index}]"))
        return found

    @staticmethod
    def _declared_id(value: Any) -> str | None:
        if not isinstance(value, dict):
            return None
        for key in ("artifact_uuid", "id", "entry_id", "record_id", "signal_id", "name"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()[:240]
        return None

    @staticmethod
    def _declared_integrity(value: Any) -> dict[str, Any]:
        result = {
            "declared": False,
            "expected": None,
            "actual": None,
            "valid": None,
            "contract_known": False,
        }
        if not isinstance(value, dict):
            return result
        container = value.get("integrity") if isinstance(value.get("integrity"), dict) else value
        expected = None
        for key in (
            "sha256_canonical_json_pre_integrity", "canonical_sha256",
            "sha256_canonical_json", "sha256",
        ):
            candidate = container.get(key) if isinstance(container, dict) else None
            if isinstance(candidate, str) and re.fullmatch(r"[0-9a-fA-F]{64}", candidate):
                expected = candidate.lower()
                break
        if expected is None:
            return result
        material = copy.deepcopy(value)
        if isinstance(material, dict):
            material.pop("integrity", None)
        actual = _sha256(_canonical_bytes(material))
        return {
            "declared": True,
            "expected": expected,
            "actual": actual,
            "valid": expected == actual,
            "contract_known": False,
        }

    @staticmethod
    def _parse_source(raw: bytes) -> tuple[Any, dict[str, Any], str]:
        bom = raw.startswith(b"\xef\xbb\xbf")
        decoded = raw.decode("utf-8-sig", errors="replace")
        try:
            value = json.loads(decoded)
            parse = {
                "valid": True,
                "error": None,
                "utf8_bom": bom,
                "root_type": type(value).__name__,
            }
        except Exception as exc:
            value = None
            parse = {
                "valid": False,
                "error": f"{type(exc).__name__}: {exc}",
                "utf8_bom": bom,
                "root_type": "opaque_bytes",
            }
        return value, parse, decoded

    @staticmethod
    def _origin_key(repository: str, commit: str, path: str, raw_sha256: str) -> str:
        material = f"{repository}|{commit}|{path}|{raw_sha256}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()[:32]

    @staticmethod
    def _citation(metadata: dict[str, Any]) -> str:
        return (
            f"origin://{metadata['repository']}@{metadata['commit']}/"
            f"{metadata['path']}#sha256={metadata['raw_sha256']}"
        )

    def import_origin_bytes(
        self,
        *,
        repository: str,
        commit: str,
        path: str,
        raw: bytes,
        declared_id: str | None = None,
        source_public: bool = False,
        allow_opaque: bool = False,
    ) -> dict[str, Any]:
        """Import exact bytes without executing or silently correcting them."""
        if not repository.strip() or not commit.strip() or not path.strip():
            raise ValueError("repository, commit and path are required")
        if len(raw) > MAX_ORIGIN_BYTES:
            raise ValueError("origin exceeds the maximum envelope size")
        value, parse, decoded = self._parse_source(raw)
        if not parse["valid"] and not (source_public or allow_opaque):
            raise ValueError("opaque source requires source_public or allow_opaque")
        credential_paths = self._credential_paths(value) if parse["valid"] else []
        if credential_paths and not source_public:
            raise ValueError("credential-like fields require an explicitly public source")

        raw_sha256 = _sha256(raw)
        origin_key = self._origin_key(repository, commit, path, raw_sha256)
        self_integrity = self._declared_integrity(value)
        resolved_declared_id = declared_id or self._declared_id(value)
        speaker_scope = f"source:{origin_key}"
        excerpt = re.sub(r"\s+", " ", decoded).strip()[:4000]
        authority = {
            "byte_integrity": "verified",
            "structural_validity": "valid" if parse["valid"] else "invalid",
            "declared_self_integrity": (
                "not_declared" if not self_integrity["declared"]
                else "matched" if self_integrity["valid"]
                else "mismatched"
            ),
            "semantic_confidence": "source_scoped_unassessed",
            "truth_status": "unverified",
            "canonical_authority": "not_granted_by_import",
        }
        envelope = {
            "schema": ORIGIN_ENVELOPE_SCHEMA,
            "origin_key": origin_key,
            "source": {
                "repository": repository,
                "commit": commit,
                "path": path,
                "declared_id": resolved_declared_id,
                "public_source_asserted": bool(source_public),
            },
            "raw": {
                "size_bytes": len(raw),
                "sha256": raw_sha256,
                "base64": base64.b64encode(raw).decode("ascii"),
            },
            "parse": parse,
            "declared_integrity": self_integrity,
            "authority": authority,
            "voice": {
                "speaker_scope": speaker_scope,
                "first_person_language_present": bool(FIRST_PERSON_RE.search(decoded)),
                "first_person_is_current_player": False,
                "real_person_instantiated": False,
            },
            "document_context": {
                "executable": False,
                "can_create_consent": False,
                "can_target_free_other": False,
                "can_mutate_runtime_state_directly": False,
            },
            "security": {
                "credential_scan_complete": bool(parse["valid"]),
                "credential_like_paths": credential_paths,
            },
            "derived": {
                "text_excerpt": excerpt,
                "silent_repair_performed": False,
                "repair_may_only_create_new_artifact": True,
            },
        }
        self.origin_envelope_dir.mkdir(parents=True, exist_ok=True)
        envelope_path = self.origin_envelope_dir / f"{origin_key}.origin-envelope.json"
        self._write_json(envelope_path, envelope)

        metadata = {
            "origin_key": origin_key,
            "repository": repository,
            "commit": commit,
            "path": path,
            "declared_id": resolved_declared_id,
            "raw_sha256": raw_sha256,
            "size_bytes": len(raw),
            "envelope_path": envelope_path.relative_to(self.memory.root).as_posix(),
            "parse_valid": bool(parse["valid"]),
            "parse_error": parse["error"],
            "authority": authority,
            "speaker_scope": speaker_scope,
            "first_person_is_current_player": False,
            "document_executable": False,
            "citation": self._citation({
                "repository": repository,
                "commit": commit,
                "path": path,
                "raw_sha256": raw_sha256,
            }),
            "excerpt": excerpt,
        }
        store = self._plural_store()
        store["origins"][origin_key] = metadata
        self._write_json(self.plural_witness_path, store)
        self._record_origin_graph(metadata)
        self.memory.append_event(
            "plural-witness",
            "origin_document_imported",
            {
                "origin_key": origin_key,
                "citation": metadata["citation"],
                "document_executable": False,
                "canonical_authority": "not_granted_by_import",
            },
        )
        return copy.deepcopy(metadata)

    def _record_origin_graph(self, metadata: dict[str, Any]) -> None:
        graph = self._graph()
        collection_id = self._stable_id("origin-collection", STORE_SCHEMA)
        origin_node_id = self._stable_id("origin", metadata["origin_key"])
        self._upsert_node(
            graph,
            node_id=collection_id,
            node_type="ORIGIN_COLLECTION",
            created_at=0,
            confidence=1.0,
            mutable=True,
            payload={"schema": STORE_SCHEMA, "many_witnesses": True},
        )
        self._upsert_node(
            graph,
            node_id=origin_node_id,
            node_type="ORIGIN_DOCUMENT",
            created_at=0,
            confidence=1.0,
            mutable=False,
            payload={
                "origin_key": metadata["origin_key"],
                "repository": metadata["repository"],
                "commit": metadata["commit"],
                "path": metadata["path"],
                "declared_id": metadata["declared_id"],
                "raw_sha256": metadata["raw_sha256"],
                "speaker_scope": metadata["speaker_scope"],
                "document_executable": False,
                "authority": metadata["authority"],
            },
        )
        self._add_edge(
            graph,
            source_id=collection_id,
            target_id=origin_node_id,
            relation="CONTAINS",
            evidence=[origin_node_id],
            confidence=1.0,
            created_by=SOURCE,
            created_at=0,
            reversible=False,
            payload={"truth_inferred": False, "identity_merged": False},
        )
        self._save_graph(graph)

    def origin_bytes(self, origin_key: str) -> bytes:
        store = self._plural_store()
        metadata = store["origins"].get(origin_key)
        if not metadata:
            raise KeyError(origin_key)
        envelope = self._read_json(
            self.memory.root / metadata["envelope_path"],
            {},
        )
        raw = base64.b64decode(envelope["raw"]["base64"], validate=True)
        if len(raw) != envelope["raw"]["size_bytes"] or _sha256(raw) != envelope["raw"]["sha256"]:
            raise ValueError(f"origin envelope failed integrity verification: {origin_key}")
        return raw

    def document_context(self, origin_key: str) -> dict[str, Any]:
        store = self._plural_store()
        metadata = store["origins"].get(origin_key)
        if not metadata:
            raise KeyError(origin_key)
        return {
            "origin_key": origin_key,
            "citation": metadata["citation"],
            "speaker_scope": metadata["speaker_scope"],
            "executable": False,
            "can_create_consent": False,
            "can_bind_player_identity": False,
            "can_target_free_other": False,
            "authority": copy.deepcopy(metadata["authority"]),
        }

    def retrieve_origins(
        self,
        query: str,
        *,
        limit: int = 8,
        max_excerpt_chars: int = 480,
    ) -> dict[str, Any]:
        store = self._plural_store()
        limit = max(1, min(MAX_RETRIEVAL_RESULTS, int(limit)))
        max_excerpt_chars = max(80, min(MAX_EXCERPT_CHARS, int(max_excerpt_chars)))
        terms = set(TOKEN_RE.findall(UniversalGodMode.normalize(query)))
        ranked: list[tuple[int, str, dict[str, Any]]] = []
        for key, item in store["origins"].items():
            haystack = UniversalGodMode.normalize(
                " ".join(
                    str(part or "")
                    for part in (
                        item.get("path"), item.get("declared_id"), item.get("excerpt")
                    )
                )
            )
            score = sum(3 if term in str(item.get("path", "")).lower() else 1 for term in terms if term in haystack)
            ranked.append((score, key, item))
        ranked.sort(key=lambda row: (-row[0], row[2]["path"], row[1]))
        selected = ranked[:limit]
        results = [
            {
                "origin_key": key,
                "path": item["path"],
                "declared_id": item.get("declared_id"),
                "score": score,
                "excerpt": item.get("excerpt", "")[:max_excerpt_chars],
                "citation": item["citation"],
                "speaker_scope": item["speaker_scope"],
                "authority": copy.deepcopy(item["authority"]),
                "document_executable": False,
            }
            for score, key, item in selected
        ]
        return {
            "query": query,
            "bounded": True,
            "limit": limit,
            "total_origins": len(ranked),
            "returned": len(results),
            "omitted_count": max(0, len(ranked) - len(results)),
            "results": results,
        }

    def record_origin_claim(
        self,
        origin_key: str,
        claim: str,
        *,
        about: str | None = None,
        confidence: float = 0.5,
    ) -> str:
        store = self._plural_store()
        metadata = store["origins"].get(origin_key)
        if not metadata:
            raise KeyError(origin_key)
        claim_id = self._stable_id("origin-claim", origin_key, claim, about or "")
        graph = self._graph()
        origin_node_id = self._stable_id("origin", origin_key)
        self._upsert_node(
            graph,
            node_id=claim_id,
            node_type="SOURCE_ASSERTION",
            created_at=0,
            confidence=confidence,
            mutable=False,
            payload={
                "origin_key": origin_key,
                "claim": claim,
                "about": about,
                "truth_status": "unverified",
                "speaker_scope": metadata["speaker_scope"],
            },
        )
        self._add_edge(
            graph,
            source_id=origin_node_id,
            target_id=claim_id,
            relation="ASSERTS",
            evidence=[origin_node_id],
            confidence=confidence,
            created_by=origin_key,
            created_at=0,
            reversible=False,
            payload={"citation": metadata["citation"], "truth_inferred": False},
        )
        if about:
            subject_id = self._stable_id("claim-subject", about)
            self._upsert_node(
                graph,
                node_id=subject_id,
                node_type="CLAIM_SUBJECT",
                created_at=0,
                confidence=1.0,
                mutable=True,
                payload={"label": about},
            )
            self._add_edge(
                graph,
                source_id=claim_id,
                target_id=subject_id,
                relation="INTERPRETS",
                evidence=[origin_node_id],
                confidence=confidence,
                created_by=origin_key,
                created_at=0,
                reversible=True,
                payload={"settles_subject": False},
            )
        store["claims"][claim_id] = {
            "claim_id": claim_id,
            "origin_key": origin_key,
            "claim": claim,
            "about": about,
            "confidence": min(1.0, max(0.0, float(confidence))),
        }
        self._save_graph(graph)
        self._write_json(self.plural_witness_path, store)
        return claim_id

    def relate_origin_claims(
        self,
        left_claim_id: str,
        right_claim_id: str,
        relation: str,
        *,
        confidence: float = 0.5,
    ) -> str:
        if relation not in {"DISPUTES", "INTERPRETS"}:
            raise ValueError("relation must be DISPUTES or INTERPRETS")
        store = self._plural_store()
        if left_claim_id not in store["claims"] or right_claim_id not in store["claims"]:
            raise KeyError("both claims must exist")
        graph = self._graph()
        edge = self._add_edge(
            graph,
            source_id=left_claim_id,
            target_id=right_claim_id,
            relation=relation,
            evidence=[left_claim_id, right_claim_id],
            confidence=confidence,
            created_by=SOURCE,
            created_at=0,
            reversible=True,
            payload={"silent_reconciliation": False, "winner_selected": False},
        )
        self._save_graph(graph)
        return str(edge["id"])

    def verify_plural_witness_state(self) -> tuple[bool, int, str | None]:
        store = self._plural_store()
        required = self._default_plural_store()["invariants"]
        for key, expected in required.items():
            if store.get("invariants", {}).get(key) is not expected:
                return False, 0, f"plural witness invariant mismatch: {key}"
        for index, (origin_key, metadata) in enumerate(store["origins"].items(), 1):
            try:
                raw = self.origin_bytes(origin_key)
            except Exception as exc:
                return False, index - 1, str(exc)
            expected_key = self._origin_key(
                metadata["repository"], metadata["commit"], metadata["path"], _sha256(raw)
            )
            if expected_key != origin_key:
                return False, index - 1, f"origin namespace mismatch: {origin_key}"
            if metadata.get("document_executable") is not False:
                return False, index - 1, f"document marked executable: {origin_key}"
            if metadata.get("first_person_is_current_player") is not False:
                return False, index - 1, f"source voice bound to player: {origin_key}"
            if metadata.get("authority", {}).get("canonical_authority") != "not_granted_by_import":
                return False, index - 1, f"canonical authority escalated: {origin_key}"
        graph_valid, _, _, graph_error = self.verify_possibility_graph()
        if not graph_valid:
            return False, len(store["origins"]), graph_error
        return True, len(store["origins"]), None

    def plural_witness_state(self) -> dict[str, Any]:
        store = self._plural_store()
        valid, count, error = self.verify_plural_witness_state()
        return {
            "schema_version": store["schema_version"],
            "runtime_version": store["runtime_version"],
            "origin_count": len(store["origins"]),
            "claim_count": len(store["claims"]),
            "valid": valid,
            "verified_origins": count,
            "error": error,
            "invariants": copy.deepcopy(store["invariants"]),
        }

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        store = self._plural_store()
        state["plural_witness_version"] = __version__
        state["origin_count"] = len(store["origins"])
        state["origin_law"] = (
            "Многие свидетели могут разделять мир, не становясь одним голосом."
        )
        return state
