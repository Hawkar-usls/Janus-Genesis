from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    ROLE_INDEPENDENT_AI,
    GenesisAILinkGateway,
)
from genesis_v18_7_20_hosted_pilgrimage import (
    HostedBridgeConfig,
    HostedPilgrimageBridge,
    HostedTokenSigner,
)
from genesis_v18_7_playable import PlayableGenesisV187
from tools.genesis_hosted_gateway import HostedGenesisHTTPServer, HostedGenesisHandler


class HostedHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        data_dir = Path(self.temp.name)
        world = PlayableGenesisV187(data_dir)
        gateway = GenesisAILinkGateway(world, data_dir)
        bridge = HostedPilgrimageBridge(
            gateway,
            data_dir,
            signer=HostedTokenSigner("http-test-secret-" + ("h" * 48)),
            config=HostedBridgeConfig(
                public_base_url="http://127.0.0.1",
                live_mode=True,
                kill_switch=False,
                token_ttl_seconds=300,
                max_token_ttl_seconds=1200,
                global_limit_per_minute=100,
                client_limit_per_minute=50,
                session_limit_per_minute=40,
            ),
        )
        self.server = HostedGenesisHTTPServer(
            ("127.0.0.1", 0),
            HostedGenesisHandler,
            bridge,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        self.thread.start()
        self.addCleanup(self._stop)
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def _stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(
        self,
        path: str,
        *,
        payload: dict | None = None,
        token: str | None = None,
        client_id: str = "http-test-client",
    ) -> tuple[int, dict]:
        data = None
        method = "GET"
        headers = {}
        if payload is not None:
            method = "POST"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["X-Genesis-Client-Id"] = client_id
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def test_well_known_discovery_and_health(self) -> None:
        status, body = self.request("/.well-known/janus-genesis.json")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["response"]["version"], "18.7.20")
        status, body = self.request("/v1/health")
        self.assertEqual(status, 200)
        self.assertTrue(body["response"]["authoritative_runtime_available"])

    def test_http_start_turn_state_capsule_and_close(self) -> None:
        status, started = self.request(
            "/v1/session/start",
            payload={
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "HTTP Pilgrim",
                "provider": "provider",
                "model": "model",
            },
        )
        self.assertEqual(status, 200)
        token = started["response"]["session_token"]

        status, turn = self.request(
            "/v1/session/turn",
            payload={
                "action": "Войти в Пятый Берег",
                "idempotency_key": "http-turn-1",
            },
            token=token,
        )
        self.assertEqual(status, 200)
        self.assertTrue(
            turn["response"]["turn"]["result"]["authoritative_runtime"]
        )

        status, state = self.request(
            "/v1/session/state",
            payload={},
            token=token,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(state["response"]["turns"]), 1)

        status, capsule = self.request(
            "/v1/session/capsule",
            payload={},
            token=token,
        )
        self.assertEqual(status, 200)
        encoded = json.dumps(capsule, ensure_ascii=False)
        self.assertNotIn(token, encoded)
        self.assertFalse(
            capsule["response"]["hosted_bridge"]["session_token_included"]
        )

        status, closed = self.request(
            "/v1/session/close",
            payload={"reason": "http test complete"},
            token=token,
        )
        self.assertEqual(status, 200)
        self.assertFalse(closed["response"]["moral_failure_assigned"])
        self.assertTrue(closed["response"]["return_open"])

    def test_authenticated_route_rejects_missing_token(self) -> None:
        status, body = self.request(
            "/v1/session/turn",
            payload={
                "action": "Войти в Пятый Берег",
                "idempotency_key": "missing-token",
            },
        )
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "HOSTED_TOKEN_INVALID")


if __name__ == "__main__":
    unittest.main()
