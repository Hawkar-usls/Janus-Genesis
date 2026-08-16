# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from genesis_v18_7_50_armor_routing import ArmoredDurableGenesisNetworkClient
from genesis_v18_7_network import GenesisNetworkClient, LEGACY_DIRECT_EGRESS_ENV


class _JsonResponse:
    def __init__(self, body: bytes = b'{"events": [], "next_cursor": 0}') -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.body


class _PassingRouter:
    def __init__(self) -> None:
        self.calls = 0

    def authorize(self, **kwargs):
        self.calls += 1
        return {"status": "PASS", "decision": "ALLOW"}


class _RejectingRouter:
    def authorize(self, **kwargs):
        raise RuntimeError("TEST_ARMOR_HOLD")


class LegacyNetworkDefaultDenyTests(unittest.TestCase):
    def _clean_env(self):
        return patch.dict(
            os.environ,
            {
                "GENESIS_NETWORK_API_KEY": "test-key",
                LEGACY_DIRECT_EGRESS_ENV: "0",
            },
            clear=False,
        )

    def test_plain_legacy_client_cannot_enter_http_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._clean_env():
            client = GenesisNetworkClient(tmp, hub_url="https://example.invalid")
            with patch("genesis_v18_7_network.urllib.request.urlopen") as urlopen:
                with self.assertRaisesRegex(RuntimeError, "LEGACY_DIRECT_NETWORK_EGRESS_DEFAULT_DENY"):
                    client._request("GET", "/v1/network/events")
                urlopen.assert_not_called()

    def test_truthy_string_does_not_become_legacy_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "GENESIS_NETWORK_API_KEY": "test-key",
                LEGACY_DIRECT_EGRESS_ENV: "true",
            },
            clear=False,
        ):
            client = GenesisNetworkClient(tmp, hub_url="https://example.invalid")
            with patch("genesis_v18_7_network.urllib.request.urlopen") as urlopen:
                with self.assertRaisesRegex(RuntimeError, "LEGACY_DIRECT_NETWORK_EGRESS_DEFAULT_DENY"):
                    client._request("GET", "/v1/network/events")
                urlopen.assert_not_called()

    def test_explicit_compatibility_opt_in_can_enter_historical_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "GENESIS_NETWORK_API_KEY": "test-key",
                LEGACY_DIRECT_EGRESS_ENV: "1",
            },
            clear=False,
        ):
            client = GenesisNetworkClient(tmp, hub_url="https://example.invalid")
            with patch(
                "genesis_v18_7_network.urllib.request.urlopen",
                return_value=_JsonResponse(),
            ) as urlopen:
                value = client._request("GET", "/v1/network/events")
            self.assertEqual(value["next_cursor"], 0)
            self.assertEqual(urlopen.call_count, 1)

    def test_canonical_armored_sync_gets_transient_admission_only_after_router_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._clean_env():
            router = _PassingRouter()
            client = ArmoredDurableGenesisNetworkClient(
                tmp,
                hub_url="https://example.invalid",
                router=router,
            )
            with patch(
                "genesis_v18_7_network.urllib.request.urlopen",
                return_value=_JsonResponse(),
            ) as urlopen:
                value = client.sync()
                self.assertEqual(value["received"], 0)
                self.assertEqual(urlopen.call_count, 1)
                self.assertEqual(router.calls, 1)
                self.assertFalse(client._armor_egress_admitted)
                with self.assertRaisesRegex(RuntimeError, "LEGACY_DIRECT_NETWORK_EGRESS_DEFAULT_DENY"):
                    client._request("GET", "/v1/network/events")
                self.assertEqual(urlopen.call_count, 1)

    def test_armor_hold_occurs_before_network_admission_or_http(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._clean_env():
            client = ArmoredDurableGenesisNetworkClient(
                tmp,
                hub_url="https://example.invalid",
                router=_RejectingRouter(),
            )
            with patch("genesis_v18_7_network.urllib.request.urlopen") as urlopen:
                with self.assertRaisesRegex(RuntimeError, "TEST_ARMOR_HOLD"):
                    client.sync()
                urlopen.assert_not_called()
                self.assertFalse(client._armor_egress_admitted)

    def test_local_queue_remains_available_without_remote_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._clean_env():
            client = GenesisNetworkClient(tmp, hub_url="https://example.invalid")
            event = client.queue_public_event("player", "presence", {"text": "hello"})
            self.assertEqual(event["kind"], "presence")
            self.assertEqual(client.state()["queued_public_events"], 1)


if __name__ == "__main__":
    unittest.main()
