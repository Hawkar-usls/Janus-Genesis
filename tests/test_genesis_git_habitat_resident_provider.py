from __future__ import annotations

import json
import unittest
from unittest import mock
import urllib.error

from tools.genesis_git_habitat_resident_cycle import ResidentChoiceError, parse_resident_choice
from tools.genesis_git_habitat_resident_provider import (
    OllamaResidentChoiceProvider,
    RESIDENT_CHOICE_JSON_SCHEMA,
    RESIDENT_TRANSPORT_FIELDS,
    ResidentProviderError,
    _project_transport_choice,
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


def transport_envelope(**overrides):
    value = {
        "choice": "REFLECT",
        "reason": "return",
        "text": "home",
        "note": "seed note",
        "tags": ["resident"],
        "title": "workshop title",
        "capability_id": "EMAIL.SEND",
        "target": "operator-review",
        "purpose": "request review",
        "payload_summary": "bounded proposal",
    }
    value.update(overrides)
    return value


class ResidentStructuredProviderTests(unittest.TestCase):
    def test_request_uses_simple_fixed_schema_grounding_and_projects_selected_branch(self) -> None:
        wire_content = json.dumps(transport_envelope())
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.headers)
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"message": {"role": "assistant", "content": wire_content}})

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

        self.assertEqual(json.loads(output), {"choice": "REFLECT", "text": "home", "reason": "return"})
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
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertIn("Every transport key is required", body["messages"][0]["content"])
        self.assertIn('"required"', body["messages"][0]["content"])

    def test_transport_schema_uses_no_conditional_keywords_and_requires_all_keys(self) -> None:
        self.assertEqual(RESIDENT_CHOICE_JSON_SCHEMA["type"], "object")
        self.assertNotIn("oneOf", RESIDENT_CHOICE_JSON_SCHEMA)
        self.assertNotIn("anyOf", RESIDENT_CHOICE_JSON_SCHEMA)
        self.assertNotIn("allOf", RESIDENT_CHOICE_JSON_SCHEMA)
        self.assertNotIn("if", RESIDENT_CHOICE_JSON_SCHEMA)
        self.assertEqual(set(RESIDENT_CHOICE_JSON_SCHEMA["required"]), set(RESIDENT_TRANSPORT_FIELDS))
        self.assertEqual(set(RESIDENT_CHOICE_JSON_SCHEMA["properties"]), set(RESIDENT_TRANSPORT_FIELDS))
        self.assertFalse(RESIDENT_CHOICE_JSON_SCHEMA["additionalProperties"])

    def test_projection_drops_only_unused_fields_and_does_not_invent_content(self) -> None:
        workshop = transport_envelope(choice="WORKSHOP_NOTE", title="", note="keep")
        projected = json.loads(_project_transport_choice(json.dumps(workshop)))
        self.assertEqual(set(projected), {"choice", "title", "note", "reason"})
        self.assertEqual(projected["title"], "")
        self.assertEqual(projected["note"], "keep")
        with self.assertRaisesRegex(ResidentChoiceError, "TITLE_REQUIRED"):
            parse_resident_choice(json.dumps(projected))

    def test_projection_preserves_safe_outbox_fields_for_unchanged_parser(self) -> None:
        row = transport_envelope(
            choice="PROPOSE_OUTBOX",
            capability_id="GITHUB.PR.CREATE",
            target="review-target",
            purpose="review a bounded change",
            payload_summary="no execution",
        )
        projected = _project_transport_choice(json.dumps(row))
        parsed = parse_resident_choice(projected)
        self.assertEqual(parsed["choice"], "PROPOSE_OUTBOX")
        self.assertEqual(parsed["capability_id"], "GITHUB.PR.CREATE")

    def test_transport_missing_any_wire_key_fails_before_projection(self) -> None:
        row = transport_envelope()
        row.pop("title")
        with self.assertRaisesRegex(ResidentProviderError, "TRANSPORT_FIELDS_INVALID"):
            _project_transport_choice(json.dumps(row))

    def test_transport_wrong_scalar_type_fails_closed(self) -> None:
        row = transport_envelope(title=17)
        with self.assertRaisesRegex(ResidentProviderError, "SCALAR_TYPE_INVALID"):
            _project_transport_choice(json.dumps(row))

    def test_transport_wrong_tags_shape_fails_closed(self) -> None:
        row = transport_envelope(tags=["ok", 3])
        with self.assertRaisesRegex(ResidentProviderError, "TAGS_TYPE_INVALID"):
            _project_transport_choice(json.dumps(row))

    def test_invalid_choice_is_not_repaired_or_replaced_with_fallback(self) -> None:
        row = transport_envelope(choice="NOT_A_CHOICE")
        projected = _project_transport_choice(json.dumps(row))
        with self.assertRaisesRegex(ResidentChoiceError, "MODEL_CHOICE_NOT_ALLOWED"):
            parse_resident_choice(projected)

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
