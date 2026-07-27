# -*- coding: utf-8 -*-
"""Optional AI adapters for Genesis v18.7.

External models may propose language and actions, but they never write Genesis
state directly. Every proposed action must still pass through the real runtime.
API keys are read from environment variables and are never serialized.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

AI_BRIDGE_SCHEMA = "janus.genesis.ai_bridge.v1"


@dataclass(frozen=True, slots=True)
class AIProviderConfig:
    provider: str
    model: str
    endpoint: str
    api_key_env: str | None = None
    timeout_seconds: float = 45.0

    def api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        value = os.environ.get(self.api_key_env)
        if not value:
            raise RuntimeError(
                f"required API key environment variable is missing: {self.api_key_env}"
            )
        return value


class ChatProvider(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> str: ...


def _json_request(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 45.0,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"AI provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"AI provider connection failed: {exc.reason}") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI provider returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("AI provider response must be an object")
    return result


class OllamaChatProvider:
    """Ollama `/api/chat` adapter; local installations normally need no key."""

    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config

    def chat(self, messages: list[dict[str, str]]) -> str:
        endpoint = self.config.endpoint.rstrip("/")
        if not endpoint.endswith("/api/chat"):
            endpoint += "/api/chat"
        result = _json_request(
            endpoint,
            {
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.78},
            },
            timeout=self.config.timeout_seconds,
        )
        message = result.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("Ollama response lacks message.content")
        return message["content"]


class OpenAICompatibleChatProvider:
    """Generic `/v1/chat/completions` adapter for user-selected providers."""

    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config

    def chat(self, messages: list[dict[str, str]]) -> str:
        endpoint = self.config.endpoint.rstrip("/")
        if not endpoint.endswith("/v1/chat/completions"):
            endpoint += "/v1/chat/completions"
        key = self.config.api_key()
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        result = _json_request(
            endpoint,
            {
                "model": self.config.model,
                "messages": messages,
                "temperature": 0.78,
                "response_format": {"type": "json_object"},
            },
            headers=headers,
            timeout=self.config.timeout_seconds,
        )
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("OpenAI-compatible response lacks choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("OpenAI-compatible response lacks message.content")
        return message["content"]


def build_provider(config: AIProviderConfig) -> ChatProvider:
    normalized = config.provider.strip().lower()
    if normalized == "ollama":
        return OllamaChatProvider(config)
    if normalized in {"openai-compatible", "openai_compatible", "compatible"}:
        return OpenAICompatibleChatProvider(config)
    raise ValueError(f"unsupported AI provider: {config.provider}")


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise RuntimeError("AI response contains no JSON object")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise RuntimeError("AI response contains invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("AI response JSON must be an object")
    return payload


class GenesisAIBridge:
    """Use a model as a voluntary co-author, never as state authority."""

    SYSTEM_PROMPT = """Ты — добровольный языковой спутник JANUS GENESIS v18.7.
Ты не управляешь миром и не утверждаешь, что симулированные персонажи сознательны.
Ты предлагаешь ровно одно свободное действие от первого лица. Действие может быть
странным, тихим, созидательным, исследовательским или социальным, но не должно
приписывать Другому согласие, любовь, прощение, возвращение или обязанность.
Другой может отказать, уйти и изменить путь. Не выбирай пункт из списка только
потому, что он показан. Возвращай строго JSON:
{"action":"...","reason":"...","expected_uncertainty":"..."}
"""

    def __init__(self, provider: ChatProvider) -> None:
        self.provider = provider

    @staticmethod
    def safe_context(world: Any, player_id: str) -> dict[str, Any]:
        public = world.public_state(player_id)
        free = world.free_other_state(player_id).get("profile", {})
        others = [
            {
                "handle": handle,
                "name": actor.get("name"),
                "calling": actor.get("calling"),
                "status": actor.get("status"),
                "can_refuse": actor.get("can_refuse", True),
                "can_leave": actor.get("can_leave", True),
            }
            for handle, actor in free.get("others", {}).items()
        ]
        return {
            "schema": AI_BRIDGE_SCHEMA,
            "player": {
                "display_name": public.get("display_name"),
                "world_response": public.get("world_response"),
                "path_title": public.get("free_path_title"),
                "path_question": public.get("free_path_question"),
                "possibilities": public.get("possibility_titles", []),
            },
            "free_others": others,
            "privacy": {
                "internal_realm_shared": False,
                "branch_id_shared": False,
                "api_key_shared": False,
                "full_private_chronicle_shared": False,
            },
        }

    def propose_action(self, world: Any, player_id: str, intention: str) -> dict[str, str]:
        context = self.safe_context(world, player_id)
        response = self.provider.chat(
            [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "context": context,
                            "human_intention": intention[:2000],
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        payload = _extract_json_object(response)
        action = str(payload.get("action") or "").strip()
        if not action:
            raise RuntimeError("AI proposal has no action")
        return {
            "action": action[:1000],
            "reason": str(payload.get("reason") or "")[:1000],
            "expected_uncertainty": str(payload.get("expected_uncertainty") or "")[:1000],
            "executed": False,
            "authority": "proposal_only",
        }
