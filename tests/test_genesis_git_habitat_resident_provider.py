from __future__ import annotations

import json
import unittest
from unittest import mock
import urllib.error

from tools.genesis_git_habitat_resident_provider import (
    OllamaResidentChoiceProvider,
    RESIDENT_CHOICE_JSON_SCHEMA,
    ResidentProviderError,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload


class ResidentStructuredProviderTests(unittest.TestCase):
    def test_request_uses_native_json_schema_and_returns_content_unchanged(self) -> None:
        model_content = '{"choice":"REFLECT","text":"home","reason":"return"}'
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"message": {"role": "assistant", "content": model_content}})

        provider = OllamaResidentChoiceProvider(
            model="qwen2.5:0.5b-instruct-q4_K_M",
            endpoint="http://127.0.0.1:11434",
            timeout_seconds=33,
        )
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            output = provider.chat([
                {"role": "system", "content": "choose"},
                {"role": "user", "content": "snapshot"},
            ])

        self.assertEqual(output, model_content)
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/chat")
        self.assertEqual(captured["timeout"], 33.0)
        body = captured["body"]
        self.assertEqual(body["model"], "qwen2.5:0.5b-instruct-q4_K_M")
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"], RESIDENT_CHOICE_JSON_SCHEMA)
        self.assertEqual(body["options"]["temperature"], 0)
        self.assertEqual(body["options"]["seed"], 1138)
        self.assertNotIn("tools", body)
        self.assertNotIn("authorization", {k.lower() for k in captured["headers"]})

    def test_schema_constrains_shape_but_does_not_select_one_choice(self) -> None:
        enum = RESIDENT_CHOICE_JSON_SCHEMA["properties"]["choice"]["enum"]
        self.assertEqual(
            set(enum),
            {
                "REST",
                "REFLECT",
                "BOOKMARK",
                "PLANT_SEED",
                "WORKSHOP_NOTE",
                "PROPOSE_OUTBOX",
            },
        )
        self.assertEqual(RESIDENT_CHOICE_JSON_SCHEMA["required"], ["choice"])
        self.assertFalse(RESIDENT_CHOICE_JSON_SCHEMA["additionalProperties"])
        self.assertNotIn("const", RESIDENT_CHOICE_JSON_SCHEMA["properties"]["choice"])
        self.assertNotIn("default", RESIDENT_CHOICE_JSON_SCHEMA["properties"]["choice"])

    def test_non_loopback_endpoint_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "MUST_BE_LOOPBACK_HTTP"):
            OllamaResidentChoiceProvider(
                model="qwen",
                endpoint="https://example.com",
            )

    def test_transport_failure_is_classified_without_fabricating_choice(self) -> None:
        provider = OllamaResidentChoiceProvider(model="qwen")
        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaisesRegex(ResidentProviderError, "CONNECTION_FAILED"):
                provider.chat([{"role": "user", "content": "snapshot"}])

    def test_invalid_response_envelope_is_rejected(self) -> None:
        provider = OllamaResidentChoiceProvider(model="qwen")
        with mock.patch(
            "urllib.request.urlopen",
            return_value=FakeResponse({"response": "wrong API shape"}),
        ):
            with self.assertRaisesRegex(ResidentProviderError, "MESSAGE_MISSING"):
                provider.chat([{"role": "user", "content": "snapshot"}])

    def test_invalid_message_role_is_rejected_before_transport(self) -> None:
        provider = OllamaResidentChoiceProvider(model="qwen")
        with mock.patch("urllib.request.urlopen") as transport:
            with self.assertRaisesRegex(ResidentProviderError, "ROLE_INVALID"):
                provider.chat([{"role": "tool", "content": "not allowed"}])
        transport.assert_not_called()

    def test_provider_error_is_local_runtime_error_without_legacy_coupling(self) -> None:
        self.assertTrue(issubclass(ResidentProviderError, RuntimeError))
        self.assertEqual(ResidentProviderError.__module__, "tools.genesis_git_habitat_resident_provider")


if __name__ == "__main__":
    unittest.main()
