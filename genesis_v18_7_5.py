# -*- coding: utf-8 -*-
"""Genesis v18.7.5 — The Grounded Witness.

A preserved source is not treated as having said anything that cannot be bound
to exact evidence. Retrieval may abstain. Source assertions and reader
interpretations remain distinct. Opaque witnesses keep their bytes without
being given a semantic voice that was never recovered.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from genesis_v18_7_4 import (
    CREDENTIAL_KEYS,
    MAX_EXCERPT_CHARS,
    MAX_RETRIEVAL_RESULTS,
    TOKEN_RE,
    PluralWitnessMixin,
)
from genesis_v18_models import UniversalGodMode

__version__ = "18.7.5"
SOURCE = "janus_genesis_v18_7_5"
REDACTION = "[REDACTED:CREDENTIAL_LIKE_VALUE]"
OPAQUE_EXCERPT = "[OPAQUE_SOURCE: semantic excerpt unavailable]"
MAX_CLAIM_CHARS = 4000


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class GroundedWitnessMixin(PluralWitnessMixin):
    """Evidence-bound source claims and retrieval that can honestly abstain."""

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        store = PluralWitnessMixin._default_plural_store()
        store["runtime_version"] = __version__
        store["invariants"].update(
            {
                "retrieval_may_abstain": True,
                "zero_score_results_are_forbidden": True,
                "source_assertions_require_exact_evidence": True,
                "reader_interpretation_is_not_source_assertion": True,
                "opaque_origins_cannot_source_assert": True,
                "disputes_require_grounded_claims": True,
                "credential_like_values_are_redacted_from_context": True,
            }
        )
        return store

    def _plural_store(self) -> dict[str, Any]:
        store = super()._plural_store()
        required = self._default_plural_store()["invariants"]
        store["runtime_version"] = __version__
        store.setdefault("invariants", {}).update(required)
        for claim in store.setdefault("claims", {}).values():
            if not isinstance(claim, dict):
                continue
            claim.setdefault("actor", "legacy_unverified")
            claim.setdefault("relation", "LEGACY_UNVERIFIED")
            claim.setdefault("grounded", False)
            claim.setdefault("grounding_status", "legacy_unverified")
            claim.setdefault("evidence", None)
        return store

    @staticmethod
    def _redact_json(value: Any) -> tuple[Any, bool]:
        redacted = False
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                if str(key).lower() in CREDENTIAL_KEYS:
                    result[str(key)] = REDACTION
                    redacted = True
                else:
                    result[str(key)], child_redacted = GroundedWitnessMixin._redact_json(item)
                    redacted = redacted or child_redacted
            return result, redacted
        if isinstance(value, list):
            result_list = []
            for item in value:
                clean, child_redacted = GroundedWitnessMixin._redact_json(item)
                result_list.append(clean)
                redacted = redacted or child_redacted
            return result_list, redacted
        return value, False

    @staticmethod
    def _credential_values(value: Any) -> list[str]:
        values: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in CREDENTIAL_KEYS:
                    if isinstance(item, (str, int, float, bool)):
                        values.append(str(item))
                    else:
                        values.append(_canonical_text(item))
                else:
                    values.extend(GroundedWitnessMixin._credential_values(item))
        elif isinstance(value, list):
            for item in value:
                values.extend(GroundedWitnessMixin._credential_values(item))
        return [item for item in values if item]

    def _envelope(self, origin_key: str) -> dict[str, Any]:
        store = self._plural_store()
        metadata = store["origins"].get(origin_key)
        if not metadata:
            raise KeyError(origin_key)
        envelope = self._read_json(self.memory.root / metadata["envelope_path"], {})
        if not isinstance(envelope, dict):
            raise ValueError(f"invalid origin envelope: {origin_key}")
        return envelope

    def _safe_excerpt(self, origin_key: str, max_chars: int = 4000) -> tuple[str, bool]:
        raw = self.origin_bytes(origin_key)
        value, parse, _decoded = self._parse_source(raw)
        if not parse["valid"]:
            return OPAQUE_EXCERPT[:max_chars], False
        clean, redacted = self._redact_json(value)
        text = re.sub(r"\s+", " ", _canonical_text(clean)).strip()
        return text[:max_chars], redacted

    def import_origin_bytes(self, **kwargs: Any) -> dict[str, Any]:
        metadata = super().import_origin_bytes(**kwargs)
        origin_key = metadata["origin_key"]
        safe_excerpt, redacted = self._safe_excerpt(origin_key)
        store = self._plural_store()
        current = store["origins"][origin_key]
        current["excerpt"] = safe_excerpt
        current["grounding_eligible"] = bool(current.get("parse_valid"))
        current["credential_values_redacted"] = True
        current["redaction_applied"] = bool(redacted)
        self._write_json(self.plural_witness_path, store)

        envelope = self._envelope(origin_key)
        envelope.setdefault("derived", {})["text_excerpt"] = safe_excerpt
        envelope["derived"]["credential_values_redacted"] = True
        envelope["derived"]["redaction_applied"] = bool(redacted)
        envelope.setdefault("document_context", {})["grounding_eligible"] = bool(
            current.get("parse_valid")
        )
        self._write_json(
            self.memory.root / current["envelope_path"],
            envelope,
        )
        return copy.deepcopy(current)

    def document_context(self, origin_key: str) -> dict[str, Any]:
        context = super().document_context(origin_key)
        store = self._plural_store()
        metadata = store["origins"][origin_key]
        parse_valid = bool(metadata.get("parse_valid"))
        context.update(
            {
                "parse_valid": parse_valid,
                "grounding_eligible": parse_valid,
                "source_assertions_allowed": parse_valid,
                "credential_values_redacted": True,
            }
        )
        return context

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
        ranked: list[tuple[int, str, dict[str, Any], str, list[str]]] = []

        for key, item in store["origins"].items():
            excerpt, _ = self._safe_excerpt(key, max_excerpt_chars)
            path = str(item.get("path", ""))
            declared_id = str(item.get("declared_id") or "")
            normalized_path = UniversalGodMode.normalize(path)
            haystack = UniversalGodMode.normalize(
                " ".join((path, declared_id, excerpt))
            )
            matched = sorted(term for term in terms if term in haystack)
            score = sum(3 if term in normalized_path else 1 for term in matched)
            if score > 0:
                ranked.append((score, key, item, excerpt, matched))

        ranked.sort(key=lambda row: (-row[0], row[2]["path"], row[1]))
        selected = ranked[:limit]
        results = [
            {
                "origin_key": key,
                "path": item["path"],
                "declared_id": item.get("declared_id"),
                "score": score,
                "matched_terms": matched,
                "selection_reason": "positive lexical evidence",
                "excerpt": excerpt[:max_excerpt_chars],
                "citation": item["citation"],
                "speaker_scope": item["speaker_scope"],
                "authority": copy.deepcopy(item["authority"]),
                "parse_valid": bool(item.get("parse_valid")),
                "grounding_eligible": bool(item.get("parse_valid")),
                "credential_values_redacted": True,
                "document_executable": False,
            }
            for score, key, item, excerpt, matched in selected
        ]
        abstained = not results
        if not terms:
            reason = "empty_query"
        elif abstained:
            reason = "no_positive_evidence"
        else:
            reason = None
        return {
            "query": query,
            "bounded": True,
            "limit": limit,
            "total_origins": len(store["origins"]),
            "positive_match_count": len(ranked),
            "returned": len(results),
            "omitted_count": max(0, len(store["origins"]) - len(results)),
            "zero_score_padding": False,
            "abstained": abstained,
            "abstention_reason": reason,
            "results": results,
        }

    @staticmethod
    def _resolve_json_pointer(value: Any, pointer: str) -> Any:
        if pointer == "":
            return value
        if not pointer.startswith("/"):
            raise ValueError("JSON pointer must be empty or start with '/'")
        current = value
        for token in pointer[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict):
                if token not in current:
                    raise ValueError(f"JSON pointer does not exist: {pointer}")
                current = current[token]
            elif isinstance(current, list):
                if not token.isdigit():
                    raise ValueError(f"JSON pointer list index is invalid: {pointer}")
                index = int(token)
                if index >= len(current):
                    raise ValueError(f"JSON pointer list index is out of range: {pointer}")
                current = current[index]
            else:
                raise ValueError(f"JSON pointer traverses a scalar: {pointer}")
        return current

    def _ground_evidence(
        self,
        origin_key: str,
        evidence: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        if not isinstance(evidence, dict):
            raise ValueError("evidence must be an object")
        store = self._plural_store()
        metadata = store["origins"].get(origin_key)
        if not metadata:
            raise KeyError(origin_key)
        if not metadata.get("parse_valid"):
            raise ValueError(
                "opaque or structurally invalid origins cannot create SOURCE_ASSERTS"
            )

        raw = self.origin_bytes(origin_key)
        decoded = raw.decode("utf-8-sig")
        value = json.loads(decoded)
        credential_values = self._credential_values(value)
        kind = str(evidence.get("kind", "")).strip()

        if kind == "json_pointer":
            pointer = str(evidence.get("pointer", ""))
            resolved = self._resolve_json_pointer(value, pointer)
            text = _canonical_text(resolved)
            descriptor = {
                "kind": kind,
                "pointer": pointer,
                "excerpt_sha256": _sha256(text.encode("utf-8")),
            }
        elif kind == "byte_range":
            start = int(evidence.get("start", -1))
            end = int(evidence.get("end", -1))
            if start < 0 or end <= start or end > len(raw):
                raise ValueError("byte range is outside the origin")
            fragment = raw[start:end]
            try:
                text = fragment.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("byte-range evidence must be valid UTF-8") from exc
            descriptor = {
                "kind": kind,
                "start": start,
                "end": end,
                "excerpt_sha256": _sha256(fragment),
            }
        elif kind == "excerpt":
            text = str(evidence.get("text", ""))
            if not text or text not in decoded:
                raise ValueError("exact excerpt was not found in the origin")
            actual = _sha256(text.encode("utf-8"))
            expected = evidence.get("sha256")
            if expected is not None and str(expected).lower() != actual:
                raise ValueError("excerpt SHA-256 does not match")
            descriptor = {
                "kind": kind,
                "occurrence": decoded.find(text),
                "excerpt_sha256": actual,
            }
        else:
            raise ValueError("evidence kind must be json_pointer, byte_range, or excerpt")

        if not text.strip():
            raise ValueError("evidence resolves to empty text")
        if len(text) > MAX_CLAIM_CHARS:
            raise ValueError("evidence text exceeds the claim limit")
        if any(secret and secret in text for secret in credential_values):
            raise ValueError("credential-like values cannot become claim evidence")
        descriptor["citation"] = metadata["citation"]
        descriptor["grounded"] = True
        descriptor["text"] = text
        return text, descriptor

    def _record_subject_edge(
        self,
        graph: dict[str, Any],
        claim_id: str,
        about: str | None,
        *,
        confidence: float,
        evidence_ids: list[str],
    ) -> None:
        if not about:
            return
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
            relation="ABOUT",
            evidence=evidence_ids,
            confidence=confidence,
            created_by=SOURCE,
            created_at=0,
            reversible=True,
            payload={"settles_subject": False},
        )

    def record_source_assertion(
        self,
        origin_key: str,
        *,
        evidence: dict[str, Any],
        about: str | None = None,
        confidence: float = 0.5,
    ) -> str:
        claim, grounded = self._ground_evidence(origin_key, evidence)
        confidence = min(1.0, max(0.0, float(confidence)))
        store = self._plural_store()
        metadata = store["origins"][origin_key]
        claim_id = self._stable_id(
            "grounded-source-claim",
            origin_key,
            grounded["excerpt_sha256"],
            about or "",
        )
        evidence_id = self._stable_id(
            "source-evidence",
            origin_key,
            grounded["kind"],
            grounded["excerpt_sha256"],
        )
        graph = self._graph()
        origin_node_id = self._stable_id("origin", origin_key)
        self._upsert_node(
            graph,
            node_id=evidence_id,
            node_type="SOURCE_EVIDENCE",
            created_at=0,
            confidence=1.0,
            mutable=False,
            payload={
                "origin_key": origin_key,
                "grounding": grounded,
                "credential_values_redacted": True,
            },
        )
        self._upsert_node(
            graph,
            node_id=claim_id,
            node_type="GROUNDED_SOURCE_ASSERTION",
            created_at=0,
            confidence=confidence,
            mutable=False,
            payload={
                "origin_key": origin_key,
                "claim": claim,
                "about": about,
                "truth_status": "unverified",
                "speaker_scope": metadata["speaker_scope"],
                "grounded": True,
                "grounding": grounded,
            },
        )
        self._add_edge(
            graph,
            source_id=origin_node_id,
            target_id=claim_id,
            relation="SOURCE_ASSERTS",
            evidence=[evidence_id],
            confidence=confidence,
            created_by=origin_key,
            created_at=0,
            reversible=False,
            payload={
                "citation": metadata["citation"],
                "truth_inferred": False,
                "grounded": True,
            },
        )
        self._record_subject_edge(
            graph,
            claim_id,
            about,
            confidence=confidence,
            evidence_ids=[evidence_id],
        )
        store["claims"][claim_id] = {
            "claim_id": claim_id,
            "origin_key": origin_key,
            "claim": claim,
            "about": about,
            "confidence": confidence,
            "actor": "source",
            "relation": "SOURCE_ASSERTS",
            "grounded": True,
            "grounding_status": "exact_source_evidence",
            "evidence": grounded,
        }
        self._save_graph(graph)
        self._write_json(self.plural_witness_path, store)
        return claim_id

    def record_reader_interpretation(
        self,
        origin_key: str,
        interpretation: str,
        *,
        reader_id: str,
        evidence: dict[str, Any] | None = None,
        about: str | None = None,
        confidence: float = 0.5,
    ) -> str:
        store = self._plural_store()
        metadata = store["origins"].get(origin_key)
        if not metadata:
            raise KeyError(origin_key)
        interpretation = str(interpretation).strip()
        reader_id = str(reader_id).strip()
        if not interpretation or not reader_id:
            raise ValueError("reader_id and interpretation are required")
        if len(interpretation) > MAX_CLAIM_CHARS:
            raise ValueError("interpretation exceeds the claim limit")

        grounded_descriptor = None
        grounded = False
        if evidence is not None:
            _text, grounded_descriptor = self._ground_evidence(origin_key, evidence)
            grounded = True

        confidence = min(1.0, max(0.0, float(confidence)))
        claim_id = self._stable_id(
            "reader-interpretation",
            reader_id,
            origin_key,
            interpretation,
            about or "",
        )
        reader_node_id = self._stable_id("reader", reader_id)
        origin_node_id = self._stable_id("origin", origin_key)
        graph = self._graph()
        self._upsert_node(
            graph,
            node_id=reader_node_id,
            node_type="READER",
            created_at=0,
            confidence=1.0,
            mutable=True,
            payload={"reader_id": reader_id},
        )
        self._upsert_node(
            graph,
            node_id=claim_id,
            node_type="READER_INTERPRETATION",
            created_at=0,
            confidence=confidence,
            mutable=False,
            payload={
                "reader_id": reader_id,
                "origin_key": origin_key,
                "interpretation": interpretation,
                "about": about,
                "grounded": grounded,
                "grounding": grounded_descriptor,
                "source_voice_claimed": False,
            },
        )
        evidence_ids = [origin_node_id]
        if grounded_descriptor:
            evidence_id = self._stable_id(
                "reader-evidence",
                origin_key,
                grounded_descriptor["kind"],
                grounded_descriptor["excerpt_sha256"],
            )
            self._upsert_node(
                graph,
                node_id=evidence_id,
                node_type="SOURCE_EVIDENCE",
                created_at=0,
                confidence=1.0,
                mutable=False,
                payload={
                    "origin_key": origin_key,
                    "grounding": grounded_descriptor,
                    "credential_values_redacted": True,
                },
            )
            evidence_ids = [evidence_id]
        self._add_edge(
            graph,
            source_id=reader_node_id,
            target_id=claim_id,
            relation="READER_INTERPRETS",
            evidence=evidence_ids,
            confidence=confidence,
            created_by=reader_id,
            created_at=0,
            reversible=True,
            payload={
                "origin_key": origin_key,
                "citation": metadata["citation"],
                "source_assertion": False,
                "grounded": grounded,
            },
        )
        self._add_edge(
            graph,
            source_id=claim_id,
            target_id=origin_node_id,
            relation="INTERPRETS",
            evidence=evidence_ids,
            confidence=confidence,
            created_by=reader_id,
            created_at=0,
            reversible=True,
            payload={"puts_words_in_source_mouth": False},
        )
        self._record_subject_edge(
            graph,
            claim_id,
            about,
            confidence=confidence,
            evidence_ids=evidence_ids,
        )
        store["claims"][claim_id] = {
            "claim_id": claim_id,
            "origin_key": origin_key,
            "claim": interpretation,
            "about": about,
            "confidence": confidence,
            "actor": f"reader:{reader_id}",
            "relation": "READER_INTERPRETS",
            "grounded": grounded,
            "grounding_status": (
                "grounded_reader_interpretation"
                if grounded
                else "reader_only_unverified"
            ),
            "evidence": grounded_descriptor,
        }
        self._save_graph(graph)
        self._write_json(self.plural_witness_path, store)
        return claim_id

    def record_origin_claim(
        self,
        origin_key: str,
        claim: str,
        *,
        about: str | None = None,
        confidence: float = 0.5,
        evidence: dict[str, Any] | None = None,
        reader_id: str = "legacy-reader",
    ) -> str:
        """Compatibility API: a free claim is a reader interpretation, never source speech."""
        return self.record_reader_interpretation(
            origin_key,
            claim,
            reader_id=reader_id,
            evidence=evidence,
            about=about,
            confidence=confidence,
        )

    def relate_origin_claims(
        self,
        left_claim_id: str,
        right_claim_id: str,
        relation: str,
        *,
        confidence: float = 0.5,
    ) -> str:
        store = self._plural_store()
        if left_claim_id not in store["claims"] or right_claim_id not in store["claims"]:
            raise KeyError("both claims must exist")
        if relation == "DISPUTES":
            left = store["claims"][left_claim_id]
            right = store["claims"][right_claim_id]
            if not left.get("grounded") or not right.get("grounded"):
                raise ValueError("DISPUTES requires two grounded claims")
        return super().relate_origin_claims(
            left_claim_id,
            right_claim_id,
            relation,
            confidence=confidence,
        )

    def verify_grounded_witness_state(self) -> tuple[bool, int, str | None]:
        plural_valid, origin_count, plural_error = self.verify_plural_witness_state()
        if not plural_valid:
            return False, 0, plural_error
        store = self._plural_store()
        required = self._default_plural_store()["invariants"]
        for key, expected in required.items():
            if store.get("invariants", {}).get(key) is not expected:
                return False, 0, f"grounded witness invariant mismatch: {key}"
        verified = 0
        for claim_id, claim in store["claims"].items():
            if not isinstance(claim, dict):
                return False, verified, f"claim is not an object: {claim_id}"
            if claim.get("relation") == "SOURCE_ASSERTS":
                if not claim.get("grounded") or not isinstance(claim.get("evidence"), dict):
                    return False, verified, f"ungrounded source assertion: {claim_id}"
                try:
                    recovered, _ = self._ground_evidence(
                        claim["origin_key"],
                        claim["evidence"],
                    )
                except Exception as exc:
                    return False, verified, f"claim evidence invalid: {claim_id}: {exc}"
                if recovered != claim.get("claim"):
                    return False, verified, f"claim no longer matches evidence: {claim_id}"
            verified += 1
        graph_valid, _, _, graph_error = self.verify_possibility_graph()
        if not graph_valid:
            return False, verified, graph_error
        return True, verified, None

    def grounded_witness_state(self) -> dict[str, Any]:
        store = self._plural_store()
        valid, verified, error = self.verify_grounded_witness_state()
        claims = list(store["claims"].values())
        return {
            "runtime_version": __version__,
            "origin_count": len(store["origins"]),
            "claim_count": len(claims),
            "source_assertions": sum(
                item.get("relation") == "SOURCE_ASSERTS" for item in claims
            ),
            "reader_interpretations": sum(
                item.get("relation") == "READER_INTERPRETS" for item in claims
            ),
            "grounded_claims": sum(bool(item.get("grounded")) for item in claims),
            "valid": valid,
            "verified_claims": verified,
            "error": error,
            "invariants": copy.deepcopy(store["invariants"]),
        }

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        state["grounded_witness_version"] = __version__
        state["grounded_witness_law"] = (
            "Источник не считается сказавшим то, для чего Genesis не может "
            "показать точное место в источнике."
        )
        return state
