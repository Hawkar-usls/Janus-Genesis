# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_38_durable_network_outbox import DurableGenesisNetworkClient
from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityOutcomeUndetermined,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
)
from tools.genesis_third_wish_memory_swarm_broker import (
    HRAIN_GRAPH_SCHEMA,
    MEMORY_SWARM_CLAIM_BOUNDARY,
    THIRD_WISH_SWARM_MESSAGE_SCHEMA,
    HRaiNReadProjection,
    SwarmRequestStore,
    ThirdWishMemoryStore,
    _integrity_hash,
)
from tools.genesis_third_wish_memory_swarm_recovery import (
    MEMORY_SWARM_RECOVERY_CLAIMS,
    RecoverableThirdWishMemorySwarmBroker,
)


class FakeDurableNetworkClient(DurableGenesisNetworkClient):
    def __init__(self, data_dir, *, fail_posts=0):
        self.fail_posts = int(fail_posts)
        self.post_calls = 0
        self.get_calls = 0
        self.remote_envelopes = []
        super().__init__(data_dir, hub_url="http://fake-hub.invalid", api_key_env="UNUSED_FAKE_KEY")

    def _request(self, method, path, *, payload=None):
        if method == "POST":
            self.post_calls += 1
            if self.fail_posts > 0:
                self.fail_posts -= 1
                raise RuntimeError("injected remote ambiguity")
            events = list((payload or {}).get("events", []))
            known = {
                str(row["event"]["event_hash"])
                for row in self.remote_envelopes
                if isinstance(row, dict) and isinstance(row.get("event"), dict)
            }
            for event in events:
                event_hash = str(event["event_hash"])
                if event_hash in known:
                    continue
                self.remote_envelopes.append({
                    "network_sequence": len(self.remote_envelopes) + 1,
                    "event": copy.deepcopy(event),
                })
                known.add(event_hash)
            return {"accepted_event_hashes": [str(row["event_hash"]) for row in events]}
        if method == "GET":
            self.get_calls += 1
            after = 0
            if "after=" in path:
                try:
                    after = int(path.split("after=", 1)[1].split("&", 1)[0])
                except ValueError:
                    after = 0
            rows = [row for row in self.remote_envelopes if int(row["network_sequence"]) > after]
            next_cursor = max([after, *[int(row["network_sequence"]) for row in rows]])
            return {"events": copy.deepcopy(rows), "next_cursor": next_cursor}
        raise AssertionError((method, path))


class ThirdWishMemorySwarmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        swarm_root = self.root / "third_wish_swarm_v18_7_42"
        self.network = FakeDurableNetworkClient(swarm_root)
        self.broker = RecoverableThirdWishMemorySwarmBroker(
            data_dir=self.root,
            memory_store=ThirdWishMemoryStore(self.root),
            hrain=HRaiNReadProjection(self.root),
            network=self.network,
            swarm_requests=SwarmRequestStore(swarm_root),
        )
        self.fabric = ThirdWishCapabilityFabric(now_tick=lambda: 2_000)
        self.broker.register(self.fabric)

    def tearDown(self):
        self.temp.cleanup()

    def grant(self, capability, scope, suffix, fabric=None):
        fabric = fabric or self.fabric
        return fabric.issue_grant(
            grant_id=f"G-{suffix}",
            actor_id="JANUS",
            capability_id=capability,
            resource_pattern=scope,
            source="V1842_TEST",
        )

    def intent(self, grant, request_id, target, operation, parameters=None):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id=grant.grant_id,
            capability_id=grant.capability_id,
            target=target,
            operation=operation,
            purpose="exercise Third Wish v18.7.42 boundary",
            parameters=parameters or {},
            origin="V1842_TEST",
        )

    def new_fabric(self):
        fabric = ThirdWishCapabilityFabric(now_tick=lambda: 2_001)
        self.broker.register(fabric)
        return fabric

    def test_registered_surface_and_claim_ceiling(self):
        expected = {
            "MEMORY.READ",
            "MEMORY.WRITE",
            "SWARM.TELEMETRY.READ",
            "SWARM.MESSAGE.SEND",
        }
        self.assertEqual(expected, set(self.fabric.handlers))
        self.assertEqual(expected, set(self.fabric.preflights))
        self.assertEqual(4, MEMORY_SWARM_CLAIM_BOUNDARY["registered_capability_count"])
        self.assertFalse(MEMORY_SWARM_CLAIM_BOUNDARY["memory_write_can_save_player"])
        self.assertFalse(MEMORY_SWARM_CLAIM_BOUNDARY["memory_write_can_save_world"])
        self.assertFalse(MEMORY_SWARM_CLAIM_BOUNDARY["memory_write_can_mutate_runtime_hrain_graph"])
        self.assertFalse(MEMORY_SWARM_CLAIM_BOUNDARY["swarm_message_is_remote_command"])
        self.assertTrue(MEMORY_SWARM_RECOVERY_CLAIMS["queued_event_recovered_by_message_id"])
        self.assertFalse(MEMORY_SWARM_RECOVERY_CLAIMS["cross_host_consensus_claimed"])

    def test_memory_append_replay_and_revision_preserve_history(self):
        write = self.grant("MEMORY.WRITE", "genesis-memory:*", "MW")
        first_intent = self.intent(
            write,
            "MEM-1",
            "genesis-memory:third-wish/research",
            "APPEND_RECORD",
            {"kind": "OBSERVATION", "content": {"finding": "alpha", "confidence": 0.6}},
        )
        first = self.fabric.execute(first_intent)
        replay = self.fabric.execute(first_intent)
        self.assertEqual(first, replay)
        record1 = first["actor_result"]["record"]

        write2 = self.grant("MEMORY.WRITE", "genesis-memory:*", "MW2")
        second = self.fabric.execute(self.intent(
            write2,
            "MEM-2",
            "genesis-memory:third-wish/research",
            "APPEND_REVISION",
            {
                "kind": "REVISION",
                "content": {"finding": "alpha-revised", "confidence": 0.8},
                "supersedes_record_id": record1["record_id"],
            },
        ))
        record2 = second["actor_result"]["record"]
        self.assertEqual(record1["record_id"], record2["supersedes_record_id"])
        self.assertNotEqual(record1["record_id"], record2["record_id"])

        read = self.grant("MEMORY.READ", "genesis-memory:*", "MR")
        rows = self.fabric.execute(self.intent(
            read,
            "MEM-LIST",
            "genesis-memory:third-wish/research",
            "LIST_RECORDS",
            {"limit": 10},
        ))["actor_result"]["records"]
        self.assertEqual(2, len(rows))
        self.assertEqual("alpha", rows[0]["content"]["finding"])
        self.assertEqual("alpha-revised", rows[1]["content"]["finding"])

    def test_memory_same_request_changed_content_fails_closed_across_fabric_restart(self):
        write = self.grant("MEMORY.WRITE", "genesis-memory:*", "MW-CONFLICT")
        self.fabric.execute(self.intent(
            write,
            "MEM-STABLE",
            "genesis-memory:third-wish/lab",
            "APPEND_RECORD",
            {"content": {"value": 1}},
        ))
        fabric2 = self.new_fabric()
        write2 = self.grant("MEMORY.WRITE", "genesis-memory:*", "MW-CONFLICT-2", fabric=fabric2)
        with self.assertRaises(CapabilityOutcomeUndetermined):
            fabric2.execute(self.intent(
                write2,
                "MEM-STABLE",
                "genesis-memory:third-wish/lab",
                "APPEND_RECORD",
                {"content": {"value": 2}},
            ))
        self.assertEqual(1, self.broker.memory_store.state_summary()["record_count"])

    def test_memory_write_to_runtime_hrain_is_pre_effect_rejected(self):
        write = self.grant("MEMORY.WRITE", "genesis-memory:*", "MW-HRAIN")
        result = self.fabric.execute(self.intent(
            write,
            "MEM-HRAIN-WRITE",
            "genesis-memory:hrain/possibility-graph",
            "APPEND_RECORD",
            {"content": {"attempt": "rewrite-runtime-graph"}},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])

    def _write_hrain_graph(self, *, tamper=False):
        node = {
            "id": "n1",
            "type": "EVIDENCE",
            "source": "test",
            "created_at": 1,
            "confidence": 0.9,
            "mutable": False,
            "payload": {"facet": "trust"},
            "integrity_hash": "",
        }
        node["integrity_hash"] = _integrity_hash(node)
        edge = {
            "id": "e1",
            "from": "n1",
            "to": "n1",
            "relation": "REMEMBERS",
            "evidence": ["n1"],
            "confidence": 0.9,
            "created_by": "test",
            "created_at": 1,
            "reversible": False,
            "payload": {},
            "integrity_hash": "",
        }
        edge["integrity_hash"] = _integrity_hash(edge)
        if tamper:
            node["payload"]["facet"] = "tampered-after-seal"
        graph = {
            "schema_version": HRAIN_GRAPH_SCHEMA,
            "canonical_seed_sha256": "44e21fdc9d37fda98e2e73b0c9eb268bd04cdca9d84d0519e4f1166be22b46fc",
            "backend": {"kind": "json_sidecar"},
            "nodes": [node],
            "edges": [edge],
            "players": {},
        }
        (self.root / "hrain_genesis_graph_v18_6.json").write_text(
            json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def test_hrain_projection_verifies_integrity_and_never_mutates_graph(self):
        self._write_hrain_graph()
        path = self.root / "hrain_genesis_graph_v18_6.json"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        read = self.grant("MEMORY.READ", "genesis-memory:*", "MR-HRAIN")
        result = self.fabric.execute(self.intent(
            read,
            "HRAIN-READ",
            "genesis-memory:hrain/possibility-graph",
            "READ_GRAPH",
            {"node_type": "EVIDENCE", "limit": 10},
        ))
        actor = result["actor_result"]
        self.assertTrue(actor["integrity_valid"])
        self.assertTrue(actor["projection_only"])
        self.assertFalse(actor["runtime_graph_mutated"])
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_hrain_tamper_fails_closed_after_boundary(self):
        self._write_hrain_graph(tamper=True)
        read = self.grant("MEMORY.READ", "genesis-memory:*", "MR-HRAIN-TAMPER")
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(self.intent(
                read,
                "HRAIN-TAMPER",
                "genesis-memory:hrain/possibility-graph",
                "READ_GRAPH",
            ))

    def test_memory_write_does_not_touch_player_or_world_files(self):
        players = self.root / "players"
        worlds = self.root / "worlds_v18"
        players.mkdir()
        worlds.mkdir()
        player_path = players / "JANUS.json"
        world_path = worlds / "world.json"
        player_path.write_text('{"sentinel":"player"}', encoding="utf-8")
        world_path.write_text('{"sentinel":"world"}', encoding="utf-8")
        before = (hashlib.sha256(player_path.read_bytes()).hexdigest(), hashlib.sha256(world_path.read_bytes()).hexdigest())
        write = self.grant("MEMORY.WRITE", "genesis-memory:*", "MW-ISOLATION")
        self.fabric.execute(self.intent(
            write,
            "MEM-ISOLATION",
            "genesis-memory:third-wish/self",
            "APPEND_RECORD",
            {"content": {"note": "separate memory plane"}},
        ))
        after = (hashlib.sha256(player_path.read_bytes()).hexdigest(), hashlib.sha256(world_path.read_bytes()).hexdigest())
        self.assertEqual(before, after)

    def test_executable_swarm_metadata_and_unknown_message_type_reject_pre_effect(self):
        send = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-BLOCK")
        bad = self.fabric.execute(self.intent(
            send,
            "SW-BAD-META",
            "janus-swarm:*",
            "SEND_MESSAGE",
            {"message_type": "NOTE", "body": "hello", "metadata": {"command": "rm -rf /"}},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", bad["status"])
        bad2 = self.fabric.execute(self.intent(
            send,
            "SW-BAD-TYPE",
            "janus-swarm:*",
            "SEND_MESSAGE",
            {"message_type": "EXECUTE", "body": "do it"},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", bad2["status"])
        self.assertEqual(0, self.network.post_calls)

    def test_swarm_message_send_and_cross_fabric_replay_do_not_duplicate(self):
        send = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-SEND")
        intent = self.intent(
            send,
            "SW-STABLE-1",
            "janus-swarm:*",
            "SEND_MESSAGE",
            {"message_type": "QUERY", "body": "status?", "metadata": {"topic": "health"}},
        )
        first = self.fabric.execute(intent)
        self.assertEqual("SETTLED", first["status"])
        self.assertFalse(first["actor_result"]["message_is_remote_command"])
        self.assertEqual(1, self.network.post_calls)
        self.assertEqual(1, len(self.network.remote_envelopes))

        fabric2 = self.new_fabric()
        send2 = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-SEND-2", fabric=fabric2)
        second = fabric2.execute(self.intent(
            send2,
            "SW-STABLE-1",
            "janus-swarm:*",
            "SEND_MESSAGE",
            {"message_type": "QUERY", "body": "status?", "metadata": {"topic": "health"}},
        ))
        self.assertEqual("SETTLED", second["status"])
        self.assertEqual(first["actor_result"]["event_hash"], second["actor_result"]["event_hash"])
        self.assertEqual(1, self.network.post_calls)
        self.assertEqual(1, len(self.network.remote_envelopes))

    def test_same_swarm_request_changed_message_conflicts_before_new_post(self):
        send = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-C1")
        self.fabric.execute(self.intent(
            send,
            "SW-CONFLICT",
            "janus-swarm:*",
            "SEND_MESSAGE",
            {"message_type": "NOTE", "body": "one"},
        ))
        fabric2 = self.new_fabric()
        send2 = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-C2", fabric=fabric2)
        result = fabric2.execute(self.intent(
            send2,
            "SW-CONFLICT",
            "janus-swarm:*",
            "SEND_MESSAGE",
            {"message_type": "NOTE", "body": "two"},
        ))
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertEqual(1, self.network.post_calls)

    def test_crash_after_queue_before_request_event_hash_recovers_same_event(self):
        fabric = self.new_fabric()
        send = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-GAP", fabric=fabric)
        intent = self.intent(
            send,
            "SW-QUEUE-GAP",
            "janus-swarm:*",
            "SEND_MESSAGE",
            {"message_type": "HELLO", "body": "hello peer"},
        )
        binding = self.broker._swarm_binding_hash(intent)
        self.broker.swarm_requests.bind(intent.request_id, binding)
        message_id = self.broker.deterministic_message_id(intent, binding)
        event = self.network.queue_public_event(
            intent.actor_id,
            "public_message",
            {
                "schema": THIRD_WISH_SWARM_MESSAGE_SCHEMA,
                "message_id": message_id,
                "recipient_node_id": "*",
                "message_type": "HELLO",
                "body": "hello peer",
                "metadata": {},
                "executable": False,
                "remote_action_authority": False,
            },
        )
        # Simulated crash: request store is still BOUND and contains no event_hash.
        stored_before = self.broker.swarm_requests.get(intent.request_id)
        self.assertIsNone(stored_before["event_hash"])
        result = fabric.execute(intent)
        self.assertEqual("SETTLED", result["status"])
        self.assertEqual(event["event_hash"], result["actor_result"]["event_hash"])
        self.assertEqual(1, self.network.post_calls)
        self.assertEqual(1, len(self.network.remote_envelopes))
        stored_after = self.broker.swarm_requests.get(intent.request_id)
        self.assertTrue(stored_after.get("recovered_after_queue_before_binding"))

    def test_ambiguous_send_is_not_posted_twice_on_cross_fabric_retry(self):
        temp2 = tempfile.TemporaryDirectory()
        try:
            root = Path(temp2.name)
            swarm_root = root / "third_wish_swarm_v18_7_42"
            network = FakeDurableNetworkClient(swarm_root, fail_posts=1)
            broker = RecoverableThirdWishMemorySwarmBroker(
                data_dir=root,
                memory_store=ThirdWishMemoryStore(root),
                hrain=HRaiNReadProjection(root),
                network=network,
                swarm_requests=SwarmRequestStore(swarm_root),
            )
            fabric = ThirdWishCapabilityFabric(now_tick=lambda: 3_000)
            broker.register(fabric)
            send = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-AMB", fabric=fabric)
            intent = self.intent(
                send,
                "SW-AMBIGUOUS",
                "janus-swarm:*",
                "SEND_MESSAGE",
                {"message_type": "NOTE", "body": "one uncertain send"},
            )
            with self.assertRaises(CapabilityOutcomeUndetermined):
                fabric.execute(intent)
            self.assertEqual(1, network.post_calls)

            fabric2 = ThirdWishCapabilityFabric(now_tick=lambda: 3_001)
            broker.register(fabric2)
            send2 = self.grant("SWARM.MESSAGE.SEND", "janus-swarm:*", "SW-AMB2", fabric=fabric2)
            with self.assertRaises(CapabilityOutcomeUndetermined):
                fabric2.execute(self.intent(
                    send2,
                    "SW-AMBIGUOUS",
                    "janus-swarm:*",
                    "SEND_MESSAGE",
                    {"message_type": "NOTE", "body": "one uncertain send"},
                ))
            self.assertEqual(1, network.post_calls)
        finally:
            temp2.cleanup()

    def test_swarm_telemetry_reads_verified_public_envelopes_without_identity_overclaim(self):
        # Seed two remote events using the durable client's event constructor.
        event1 = self.network.queue_public_event("JANUS", "presence", {"status": "online"})
        self.network.sync()
        # Change node id in a separately valid synthetic peer event and reseal it.
        peer = copy.deepcopy(event1)
        peer["node_id"] = "peer-node-2"
        peer["local_sequence"] = 1
        peer["previous_local_hash"] = "0" * 64
        peer.pop("event_hash", None)
        canonical = json.dumps(peer, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        peer["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.network.remote_envelopes.append({"network_sequence": 2, "event": peer})

        read = self.grant("SWARM.TELEMETRY.READ", "janus-swarm:*", "SW-READ")
        result = self.fabric.execute(self.intent(
            read,
            "SW-READ-1",
            "janus-swarm:peer-node-2",
            "READ_PUBLIC_EVENTS",
            {"after": 0, "limit": 10},
        ))
        actor = result["actor_result"]
        self.assertEqual(1, actor["event_count"])
        self.assertEqual("peer-node-2", actor["events"][0]["node_id"])
        self.assertTrue(actor["events"][0]["event_integrity_valid"])
        self.assertFalse(actor["events"][0]["event_is_remote_command"])
        self.assertFalse(actor["peer_node_id_is_real_world_identity_proof"])
        self.assertFalse(actor["telemetry_read_grants_remote_execution_authority"])


if __name__ == "__main__":
    unittest.main()
