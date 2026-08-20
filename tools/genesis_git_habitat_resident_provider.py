# -*- coding: utf-8 -*-
"""Resident-only structured-output provider for JANUS Git Habitat v18.7.52.

This adapter intentionally does not replace the repository-wide Ollama provider.
It is registered behind the existing Third Wish MODEL.CALL capability and uses
Ollama's native structured-output `format` field so the model still selects the
resident choice while the transport constrains only the response shape.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

RESIDENT_PROVIDER_VERSION = "18.7.52"


class ResidentProviderError(RuntimeError):
    """Resident transport/schema failure without coupling to the legacy AI adapter."""


# Keep the model semantically free to select any allowed branch, but make the
# native structured-output grammar branch-complete. The previous flat schema
# required only `choice`, so a real model could legally emit WORKSHOP_NOTE with
# no title/note and then be rejected by the stricter resident admission gate.
# Each alternative below mirrors the *existing* parser requirements; this is a
# schema tightening, not a parser relaxation or a fabricated fallback choice.
RESIDENT_CHOICE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "oneOf": [
        {
            "properties": {
                "choice": {"type": "string", "enum": ["REST"]},
                "reason": {"type": "string", "maxLength": 1000},
            },
            "required": ["choice"],
            "additionalProperties": False,
        },
        {
            "properties": {
                "choice": {"type": "string", "enum": ["REFLECT"]},
                "text": {"type": "string", "minLength": 1, "maxLength": 4000},
                "reason": {"type": "string", "maxLength": 1000},
            },
            "required": ["choice", "text"],
            "additionalProperties": False,
        },
        {
            "properties": {
                "choice": {"type": "string", "enum": ["BOOKMARK"]},
                "text": {"type": "string", "minLength": 1, "maxLength": 4000},
                "reason": {"type": "string", "maxLength": 1000},
            },
            "required": ["choice", "text"],
            "additionalProperties": False,
        },
        {
            "properties": {
                "choice": {"type": "string", "enum": ["PLANT_SEED"]},
                "note": {"type": "string", "minLength": 1, "maxLength": 4000},
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$",
                    },
                    "maxItems": 8,
                },
                "reason": {"type": "string", "maxLength": 1000},
            },
            "required": ["choice", "note"],
            "additionalProperties": False,
        },
        {
            "properties": {
                "choice": {"type": "string", "enum": ["WORKSHOP_NOTE"]},
                "title": {"type": "string", "minLength": 1, "maxLength": 160},
                "note": {"type": "string", "minLength": 1, "maxLength": 4000},
                "reason": {"type": "string", "maxLength": 1000},
            },
            "required": ["choice", "title", "note"],
            "additionalProperties": False,
        },
        {
            "properties": {
                "choice": {"type": "string", "enum": ["PROPOSE_OUTBOX"]},
                "capability_id": {
                    "type": "string",
                    "enum": [
                        "EMAIL.SEND",
                        "PUBLICATION.PUBLISH",
                        "CALENDAR.WRITE",
                        "API.CALL",
                        "WEB.HTTP.POST",
                        "GITHUB.ISSUE.CREATE",
                        "GITHUB.COMMENT.CREATE",
                        "GITHUB.FILE.WRITE_BRANCH",
                        "GITHUB.PR.CREATE",
                        "SCHEDULE.CREATE",
                        "SWARM.MESSAGE.SEND",
                    ],
                },
                "target": {"type": "string", "minLength": 1, "maxLength": 500},
                "purpose": {"type": "string", "minLength": 1, "maxLength": 1000},
                "payload_summary": {"type": "string", "minLength": 1, "maxLength": 3000},
                "reason": {"type": "string", "maxLength": 1000},
            },
            "required": [
                "choice",
                "capability_id",
                "target",
                "purpose",
                "payload_summary",
            ],
            "additionalProperties": False,
        },
    ],
}


def _endpoint_root(value: str) -> str:
    endpoint = str(value or "").strip().rstrip("/")
    if not endpoint:
        raise ValueError("RESIDENT_OLLAMA_ENDPOINT_REQUIRED")
    # The live reference path is local-only. Keeping this adapter loopback-only
    # prevents its structured-output specialization from becoming a generic
    # remote transport tunnel.
    allowed = (
        "http://127.0.0.1:",
        "http://localhost:",
        "http://[::1]:",
    )
    if not endpoint.startswith(allowed):
        raise ValueError("RESIDENT_OLLAMA_ENDPOINT_MUST_BE_LOOPBACK_HTTP")
    return endpoint


@dataclass(frozen=True)
class OllamaResidentChoiceProvider:
    model: str
    endpoint: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "model", str(self.model).strip())
        object.__setattr__(self, "endpoint", _endpoint_root(self.endpoint))
        if not self.model:
            raise ValueError("RESIDENT_OLLAMA_MODEL_REQUIRED")
        if not (0 < float(self.timeout_seconds) <= 300):
            raise ValueError("RESIDENT_OLLAMA_TIMEOUT_OUT_OF_RANGE")

    def chat(self, messages: Sequence[Mapping[str, str]]) -> str:
        normalized: list[dict[str, str]] = []
        for row in messages:
            role = str(row.get("role") or "").strip()
            content = str(row.get("content") or "")
            if role not in {"system", "user", "assistant"}:
                raise ResidentProviderError("RESIDENT_OLLAMA_MESSAGE_ROLE_INVALID")
            if len(content) > 40_000:
                raise ResidentProviderError("RESIDENT_OLLAMA_MESSAGE_TOO_LONG")
            normalized.append({"role": role, "content": content})
        if not normalized:
            raise ResidentProviderError("RESIDENT_OLLAMA_MESSAGES_REQUIRED")

        payload = {
            "model": self.model,
            "messages": normalized,
            "stream": False,
            "format": RESIDENT_CHOICE_JSON_SCHEMA,
            # Fixed inference controls improve replayability without selecting
            # the semantic choice. The model still decides which branch.
            "options": {
                "temperature": 0,
                "seed": 1138,
            },
        }
        request = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(self.timeout_seconds)) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise ResidentProviderError(f"RESIDENT_OLLAMA_HTTP_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ResidentProviderError("RESIDENT_OLLAMA_CONNECTION_FAILED") from exc
        except TimeoutError as exc:
            raise ResidentProviderError("RESIDENT_OLLAMA_TIMEOUT") from exc

        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResidentProviderError("RESIDENT_OLLAMA_RESPONSE_ENVELOPE_INVALID") from exc
        if not isinstance(envelope, dict):
            raise ResidentProviderError("RESIDENT_OLLAMA_RESPONSE_ENVELOPE_NOT_OBJECT")
        message = envelope.get("message")
        if not isinstance(message, dict):
            raise ResidentProviderError("RESIDENT_OLLAMA_RESPONSE_MESSAGE_MISSING")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ResidentProviderError("RESIDENT_OLLAMA_RESPONSE_CONTENT_MISSING")

        # Do not parse/repair the model choice here. The resident schema gate is
        # the only place allowed to decide whether model content is acceptable.
        return content
