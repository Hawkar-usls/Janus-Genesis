# -*- coding: utf-8 -*-
"""GitHub Models adapter for JANUS Genesis Third Wish.

The workflow token remains broker-side. MODEL.CALL may return language or a plan,
but the returned text is proposal-only and has no GitHub write authority.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from genesis_v18_7_40_third_wish_capability_fabric import ActionIntent, ThirdWishCapabilityFabric

VERSION = "18.7.51"
TOKEN_ENV = "JANUS_GITHUB_BROKER_TOKEN"
MODEL_ENV = "JANUS_GITHUB_MODELS_MODEL"
DEFAULT_MODEL = "openai/gpt-4.1"
ENDPOINT = "https://models.github.ai/inference/chat/completions"
MAX_MESSAGES = 12
MAX_INPUT_BYTES = 48 * 1024
MAX_OUTPUT_CHARS = 24_000


class GitHubModelsBrokerError(RuntimeError):
    pass


class ModelsTransport(Protocol):
    def chat(self, *, model: str, messages: list[dict[str, str]]) -> Mapping[str, Any]: ...


class GitHubModelsRESTTransport:
    def __init__(self, *, token_env: str = TOKEN_ENV, endpoint: str = ENDPOINT, timeout_seconds: float = 45.0) -> None:
        self.token_env = token_env
        self.endpoint = endpoint
        self.timeout_seconds = float(timeout_seconds)

    def _token(self) -> str:
        token = os.environ.get(self.token_env, "").strip()
        if not token:
            raise GitHubModelsBrokerError(f"BROKER_CREDENTIAL_ENV_MISSING:{self.token_env}")
        return token

    def chat(self, *, model: str, messages: list[dict[str, str]]) -> Mapping[str, Any]:
        payload = json.dumps({"model": model, "messages": messages, "temperature": 0.35}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self._token(),
                "Content-Type": "application/json",
                "User-Agent": "JANUS-Genesis-Third-Wish-GitHub-Habitat/18.7.51",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            raise GitHubModelsBrokerError(f"GITHUB_MODELS_HTTP_{exc.code}:{detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubModelsBrokerError(f"GITHUB_MODELS_CONNECTION_ERROR:{exc.reason}") from exc
        if len(raw) > 2 * 1024 * 1024:
            raise GitHubModelsBrokerError("GITHUB_MODELS_RESPONSE_TOO_LARGE")
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise GitHubModelsBrokerError("GITHUB_MODELS_INVALID_JSON") from exc
        if not isinstance(data, dict):
            raise GitHubModelsBrokerError("GITHUB_MODELS_RESPONSE_NOT_OBJECT")
        return data


@dataclass
class GitHubModelsThirdWishBroker:
    transport: ModelsTransport
    model: str = DEFAULT_MODEL

    REGISTERED_CAPABILITIES = ("MODEL.CALL",)

    @classmethod
    def system(cls) -> "GitHubModelsThirdWishBroker":
        return cls(
            transport=GitHubModelsRESTTransport(),
            model=os.environ.get(MODEL_ENV, DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        )

    def register(self, fabric: ThirdWishCapabilityFabric) -> None:
        fabric.register_handler("MODEL.CALL", self.model_call, preflight=self.preflight)

    def preflight(self, intent: ActionIntent) -> Mapping[str, Any]:
        if intent.target != "model:github-models":
            raise GitHubModelsBrokerError("GITHUB_MODELS_TARGET_REQUIRED")
        if intent.operation.upper() not in {"CHAT", "INFER"}:
            raise GitHubModelsBrokerError("UNSUPPORTED_MODEL_OPERATION")
        messages = intent.parameters.get("messages")
        if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
            raise GitHubModelsBrokerError("MODEL_MESSAGES_SHAPE_INVALID")
        normalized: list[dict[str, str]] = []
        for row in messages:
            if not isinstance(row, Mapping):
                raise GitHubModelsBrokerError("MODEL_MESSAGE_NOT_OBJECT")
            role = str(row.get("role") or "").strip()
            content = str(row.get("content") or "")
            if role not in {"system", "user", "assistant"} or not content:
                raise GitHubModelsBrokerError("MODEL_MESSAGE_INVALID")
            normalized.append({"role": role, "content": content})
        encoded = json.dumps(normalized, ensure_ascii=False).encode("utf-8")
        if len(encoded) > MAX_INPUT_BYTES:
            raise GitHubModelsBrokerError("MODEL_INPUT_TOO_LARGE")
        return {"validated": True, "model": self.model, "transport_called": False, "write_authority": False}

    def model_call(self, intent: ActionIntent) -> Mapping[str, Any]:
        self.preflight(intent)
        messages = [
            {"role": str(row["role"]), "content": str(row["content"])}
            for row in intent.parameters["messages"]
        ]
        data = self.transport.chat(model=self.model, messages=messages)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
            raise GitHubModelsBrokerError("GITHUB_MODELS_CHOICES_MISSING")
        message = choices[0].get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise GitHubModelsBrokerError("GITHUB_MODELS_CONTENT_MISSING")
        text = str(message["content"])
        if len(text) > MAX_OUTPUT_CHARS:
            text = text[:MAX_OUTPUT_CHARS]
        return {
            "provider": "github_models",
            "model": self.model,
            "text": text,
            "authority": "proposal_only",
            "github_write_authority": False,
            "credential_exposed": False,
        }
