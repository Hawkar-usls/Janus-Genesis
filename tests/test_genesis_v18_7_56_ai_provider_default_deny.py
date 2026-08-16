# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from genesis_v18_7_50_armor_routing import ArmoredGenesisAIBridge
from genesis_v18_7_ai import (
    AIProviderConfig,
    LEGACY_AI_DIRECT_EGRESS_ENV,
    OllamaChatProvider,
    OpenAICompatibleChatProvider,
)


class _JsonResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.body


class _World:
    def public_state(self, player_id: str):
        return {
            "display_name": "Traveler",
            "world_response": "calm",
            "free_path_title": "Open path",
            "free_path_question": "Where next?",
            "possibility_titles": ["Observe"],
        }

    def free_other_state(self, player_id: str):
        return {"profile": {"others": {}}}


class _PassingRouter:
    def __init__(self) -> None:
        self.calls = 0

    def authorize(self, **kwargs):
        self.calls += 1
        return {"status": "PASS", "decision": "ALLOW"}


class _RejectingRouter:
    def authorize(self, **kwargs):
        raise RuntimeError("TEST_ARMOR_HOLD")


class AIProviderDefaultDenyTests(unittest.TestCase):
    @staticmethod
    def _ollama() -> OllamaChatProvider:
        return OllamaChatProvider(
            AIProviderConfig(
                provider="ollama",
                model="test-model",
                endpoint="http://127.0.0.1:11434",
                timeout_seconds=1.0,
            )
        )

    def test_plain_builtin_provider_cannot_enter_http_by_default(self) -> None:
        provider = self._ollama()
        with patch.dict(os.environ, {LEGACY_AI_DIRECT_EGRESS_ENV: "0"}, clear=False), patch(
            "genesis_v18_7_ai.urllib.request.urlopen"
        ) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "LEGACY_DIRECT_AI_EGRESS_DEFAULT_DENY"):
                provider.chat([{"role": "user", "content": "hello"}])
            urlopen.assert_not_called()

    def test_truthy_string_does_not_become_provider_permission(self) -> None:
        provider = self._ollama()
        with patch.dict(os.environ, {LEGACY_AI_DIRECT_EGRESS_ENV: "true"}, clear=False), patch(
            "genesis_v18_7_ai.urllib.request.urlopen"
        ) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "LEGACY_DIRECT_AI_EGRESS_DEFAULT_DENY"):
                provider.chat([{"role": "user", "content": "hello"}])
            urlopen.assert_not_called()

    def test_explicit_legacy_compatibility_opt_in_reaches_provider_adapter(self) -> None:
        provider = self._ollama()
        response = _JsonResponse(b'{"message":{"content":"ok"}}')
        with patch.dict(os.environ, {LEGACY_AI_DIRECT_EGRESS_ENV: "1"}, clear=False), patch(
            "genesis_v18_7_ai.urllib.request.urlopen", return_value=response
        ) as urlopen:
            self.assertEqual(provider.chat([{"role": "user", "content": "hello"}]), "ok")
            self.assertEqual(urlopen.call_count, 1)

    def test_openai_compatible_builtin_is_also_default_deny(self) -> None:
        provider = OpenAICompatibleChatProvider(
            AIProviderConfig(
                provider="openai-compatible",
                model="test-model",
                endpoint="https://example.invalid",
                api_key_env=None,
                timeout_seconds=1.0,
            )
        )
        with patch.dict(os.environ, {LEGACY_AI_DIRECT_EGRESS_ENV: "0"}, clear=False), patch(
            "genesis_v18_7_ai.urllib.request.urlopen"
        ) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "LEGACY_DIRECT_AI_EGRESS_DEFAULT_DENY"):
                provider.chat([{"role": "user", "content": "hello"}])
            urlopen.assert_not_called()

    def test_canonical_bridge_opens_builtin_provider_only_after_armor_pass(self) -> None:
        provider = self._ollama()
        router = _PassingRouter()
        bridge = ArmoredGenesisAIBridge(provider, router=router)
        body = (
            b'{"message":{"content":"{\\"action\\":\\"observe\\",'
            b'\\"reason\\":\\"careful\\",\\"expected_uncertainty\\":\\"open\\"}"}}'
        )
        with patch.dict(os.environ, {LEGACY_AI_DIRECT_EGRESS_ENV: "0"}, clear=False), patch(
            "genesis_v18_7_ai.urllib.request.urlopen", return_value=_JsonResponse(body)
        ) as urlopen:
            proposal = bridge.propose_action(_World(), "player", "look around")
            self.assertEqual(proposal["action"], "observe")
            self.assertFalse(proposal["executed"])
            self.assertEqual(router.calls, 1)
            self.assertEqual(urlopen.call_count, 1)
            self.assertFalse(provider._armor_egress_admitted)
            with self.assertRaisesRegex(RuntimeError, "LEGACY_DIRECT_AI_EGRESS_DEFAULT_DENY"):
                provider.chat([{"role": "user", "content": "second"}])
            self.assertEqual(urlopen.call_count, 1)

    def test_armor_hold_occurs_before_provider_admission_or_http(self) -> None:
        provider = self._ollama()
        bridge = ArmoredGenesisAIBridge(provider, router=_RejectingRouter())
        with patch.dict(os.environ, {LEGACY_AI_DIRECT_EGRESS_ENV: "0"}, clear=False), patch(
            "genesis_v18_7_ai.urllib.request.urlopen"
        ) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "TEST_ARMOR_HOLD"):
                bridge.propose_action(_World(), "player", "look around")
            urlopen.assert_not_called()
            self.assertFalse(provider._armor_egress_admitted)


if __name__ == "__main__":
    unittest.main()
