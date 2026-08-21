from __future__ import annotations

import importlib.util
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "janus_sysear_router_syslog_observer.py"
spec = importlib.util.spec_from_file_location("sysear", TOOL)
assert spec and spec.loader
sysear = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sysear)


class SysEarRouterSyslogObserverTests(unittest.TestCase):
    def test_classification(self) -> None:
        self.assertEqual(sysear.classify("kernel: DROP IN=wan0"), "FIREWALL")
        self.assertEqual(sysear.classify("dnsmasq-dhcp: lease renewed"), "DHCP")
        self.assertEqual(sysear.classify("wlan client deauth"), "WIFI")
        self.assertEqual(sysear.classify("route gateway changed"), "ROUTING")

    def test_identifier_detector(self) -> None:
        self.assertTrue(sysear.contains_deployment_identifier("192.168.1.1"))
        self.assertTrue(sysear.contains_deployment_identifier("aa:bb:cc:dd:ee:ff"))
        self.assertFalse(sysear.contains_deployment_identifier("NETWORK_EDGE_TELEMETRY"))

    def test_public_receipt_withholds_router_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            local = root / "local.json"
            public = root / "public.json"
            local.write_text(json.dumps({
                "schema": sysear.SCHEMA,
                "status": "PASS_CAPTURED",
                "listen_port": 5514,
                "accepted_events": 3,
                "rejected_non_router_source_events": 1,
                "event_classes": {"FIREWALL": 2, "DHCP": 1},
                "raw_jsonl_sha256": "a" * 64,
                "expected_source_exact_local_only": "192.168.1.1",
                "raw_jsonl_path_local_only": "C:/private/router.jsonl",
            }), encoding="utf-8")
            rc = sysear.public_receipt(SimpleNamespace(local_receipt=local, output=public))
            self.assertEqual(rc, 0)
            text = public.read_text(encoding="utf-8")
            self.assertNotIn("192.168.1.1", text)
            self.assertNotIn("C:/private", text)
            payload = json.loads(text)
            self.assertEqual(payload["authority_delta"], 0)
            self.assertFalse(payload["transport_authenticated"])

    def test_bounded_loopback_capture(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            probe.close()
            args = SimpleNamespace(
                expected_source="127.0.0.1",
                raw_output=root / "raw.jsonl",
                local_receipt=root / "local.json",
                listen_host="127.0.0.1",
                listen_port=port,
                timeout=0.1,
                duration=2.0,
                max_events=1,
                max_datagram_bytes=8192,
            )
            result: list[int] = []
            errors: list[BaseException] = []

            def target() -> None:
                try:
                    result.append(sysear.listen(args))
                except BaseException as exc:  # pragma: no cover - diagnostic path
                    errors.append(exc)

            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            time.sleep(0.15)
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender.sendto(b"kernel: DROP test-source", ("127.0.0.1", port))
            sender.close()
            thread.join(timeout=3.0)
            self.assertFalse(errors)
            self.assertEqual(result, [0])
            receipt = json.loads(args.local_receipt.read_text(encoding="utf-8"))
            self.assertEqual(receipt["accepted_events"], 1)
            self.assertEqual(receipt["event_classes"], {"FIREWALL": 1})


if __name__ == "__main__":
    unittest.main()
