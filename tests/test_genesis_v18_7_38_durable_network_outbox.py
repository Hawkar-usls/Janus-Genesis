from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from genesis_v18_7_38_durable_network_outbox import (
    DurableGenesisNetworkClient,
    MAX_DURABLE_OUTBOX,
    NetworkCrashInjector,
    NetworkCrashPoint,
    NetworkOutboxCapacityError,
    NetworkSendOutcomeUndetermined,
    NetworkStateIntegrityError,
)


class FakeHubClient(DurableGenesisNetworkClient):
    def __init__(
        self,
        *args,
        accept_mode: str = "all",
        fail_post: bool = False,
        **kwargs,
    ) -> None:
        self.accept_mode = accept_mode
        self.fail_post = fail_post
        self.calls = []
        super().__init__(*args, **kwargs)

    def _request(self, method, path, *, payload=None):
        self.calls.append((method, path, payload))
        if method == "POST":
            if self.fail_post:
                raise RuntimeError("simulated remote transport ambiguity")
            events = list((payload or {}).get("events", []))
            hashes = [str(event["event_hash"]) for event in events]
            if self.accept_mode == "all":
                accepted = hashes
            elif self.accept_mode == "first":
                accepted = hashes[:1]
            elif self.accept_mode == "none":
                accepted = []
            else:
                raise AssertionError("unknown accept mode")
            return {"accepted_event_hashes": accepted}
        if method == "GET":
            return {"events": [], "next_cursor": 0}
        raise AssertionError(f"unexpected method {method}")


class DurableNetworkLocalStateTests(unittest.TestCase):
    def test_two_client_instances_queue_without_lost_update(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = FakeHubClient(root, hub_url="https://example.invalid")
            b = FakeHubClient(root, hub_url="https://example.invalid")
            start = threading.Barrier(2)

            def queue(client, text):
                start.wait(timeout=5)
                return client.queue_public_event(
                    "mira",
                    "public_message",
                    {"text": text},
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                events = [
                    future.result(timeout=10)
                    for future in (
                        pool.submit(queue, a, "A"),
                        pool.submit(queue, b, "B"),
                    )
                ]
            state = json.loads((root / "network_client_v18_7.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["outbox"]), 2)
            self.assertEqual(sorted(event["local_sequence"] for event in events), [1, 2])
            self.assertEqual(state["next_local_sequence"], 3)
            self.assertEqual(len({event["event_hash"] for event in state["outbox"]}), 2)

    def test_invalid_json_existing_state_fails_closed_instead_of_reset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root.mkdir(parents=True, exist_ok=True)
            (root / "network_client_v18_7.json").write_text("{not-json", encoding="utf-8")
            with self.assertRaises(NetworkStateIntegrityError):
                FakeHubClient(root, hub_url="https://example.invalid")
            self.assertEqual(
                (root / "network_client_v18_7.json").read_text(encoding="utf-8"),
                "{not-json",
            )

    def test_wrong_schema_existing_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root.mkdir(parents=True, exist_ok=True)
            path = root / "network_client_v18_7.json"
            path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
            with self.assertRaises(NetworkStateIntegrityError):
                FakeHubClient(root, hub_url="https://example.invalid")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema"], "wrong")

    def test_outbox_capacity_is_backpressure_not_silent_truncation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            client = FakeHubClient(root, hub_url="https://example.invalid")
            with client.local_lock.exclusive():
                state = client._load()
                state["outbox"] = [{"placeholder": index} for index in range(MAX_DURABLE_OUTBOX)]
                client._save(state)
            with self.assertRaises(NetworkOutboxCapacityError):
                client.queue_public_event("mira", "public_message", {"text": "must not drop oldest"})
            with client.local_lock.shared():
                state = client._load()
            self.assertEqual(len(state["outbox"]), MAX_DURABLE_OUTBOX)
            self.assertEqual(state["next_local_sequence"], 1)


class DurableNetworkRemoteBoundaryTests(unittest.TestCase):
    def test_complete_ack_durably_removes_outbox_and_clears_pending_send(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            client = FakeHubClient(root, hub_url="https://example.invalid")
            one = client.queue_public_event("mira", "public_message", {"text": "one"})
            two = client.queue_public_event("mira", "public_message", {"text": "two"})
            result = client.sync()
            self.assertEqual(result["accepted"], 2)
            self.assertEqual(result["remaining_outbox"], 0)
            state = client.state()
            self.assertIsNone(state["pending_send"])
            self.assertFalse(state["hub_idempotency_verified"])
            raw = json.loads((root / "network_client_v18_7.json").read_text(encoding="utf-8"))
            receipts = raw["control_v18_7_38"]["completed_send_receipts"]
            self.assertEqual(len(receipts), 1)
            self.assertEqual(
                set(receipts[0]["accepted_event_hashes"]),
                {one["event_hash"], two["event_hash"]},
            )

    def test_crash_after_send_entering_before_remote_blocks_later_automatic_send(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            crashing = FakeHubClient(
                root,
                hub_url="https://example.invalid",
                crash_injector=NetworkCrashInjector(
                    NetworkCrashPoint.AFTER_SEND_ENTERING_BEFORE_REMOTE
                ),
            )
            crashing.queue_public_event("mira", "public_message", {"text": "one"})
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                crashing.sync()
            self.assertEqual([call for call in crashing.calls if call[0] == "POST"], [])

            retry = FakeHubClient(root, hub_url="https://example.invalid")
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                retry.sync()
            self.assertEqual(retry.calls, [])
            self.assertEqual(retry.state()["pending_send"]["state"], "SEND_ENTERING")

    def test_remote_transport_error_leaves_ambiguous_send_and_retry_does_not_post(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            failing = FakeHubClient(
                root,
                hub_url="https://example.invalid",
                fail_post=True,
            )
            failing.queue_public_event("mira", "public_message", {"text": "one"})
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                failing.sync()
            self.assertEqual(len([call for call in failing.calls if call[0] == "POST"]), 1)

            retry = FakeHubClient(root, hub_url="https://example.invalid")
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                retry.sync()
            self.assertEqual(retry.calls, [])

    def test_crash_after_remote_ack_before_local_ack_blocks_duplicate_post(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            crashing = FakeHubClient(
                root,
                hub_url="https://example.invalid",
                crash_injector=NetworkCrashInjector(
                    NetworkCrashPoint.AFTER_REMOTE_RESPONSE_BEFORE_LOCAL_ACK
                ),
            )
            event = crashing.queue_public_event("mira", "public_message", {"text": "one"})
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                crashing.sync()
            self.assertEqual(len([call for call in crashing.calls if call[0] == "POST"]), 1)
            raw = json.loads((root / "network_client_v18_7.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["outbox"][0]["event_hash"], event["event_hash"])
            self.assertEqual(raw["control_v18_7_38"]["pending_send"]["state"], "SEND_ENTERING")

            retry = FakeHubClient(root, hub_url="https://example.invalid")
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                retry.sync()
            self.assertEqual(retry.calls, [])

    def test_partial_ack_removes_only_explicit_accepts_and_blocks_unresolved_resend(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            client = FakeHubClient(
                root,
                hub_url="https://example.invalid",
                accept_mode="first",
            )
            one = client.queue_public_event("mira", "public_message", {"text": "one"})
            two = client.queue_public_event("mira", "public_message", {"text": "two"})
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                client.sync()
            raw = json.loads((root / "network_client_v18_7.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [event["event_hash"] for event in raw["outbox"]],
                [two["event_hash"]],
            )
            pending = raw["control_v18_7_38"]["pending_send"]
            self.assertEqual(pending["state"], "PARTIAL_ACK_UNRESOLVED")
            self.assertEqual(pending["accepted_event_hashes"], [one["event_hash"]])
            self.assertEqual(pending["unresolved_event_hashes"], [two["event_hash"]])

            retry = FakeHubClient(root, hub_url="https://example.invalid")
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                retry.sync()
            self.assertEqual(retry.calls, [])

    def test_empty_ack_is_ambiguous_not_automatic_retry_permission(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            client = FakeHubClient(
                root,
                hub_url="https://example.invalid",
                accept_mode="none",
            )
            client.queue_public_event("mira", "public_message", {"text": "one"})
            with self.assertRaises(NetworkSendOutcomeUndetermined):
                client.sync()
            self.assertEqual(client.state()["pending_send"]["state"], "PARTIAL_ACK_UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
