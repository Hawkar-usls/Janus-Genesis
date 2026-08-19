from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from genesis_v18_7_ai import GenesisAIBridge
from genesis_v18_7_auth import api_key_sha256, verify_bearer
from genesis_v18_7_network import GenesisNetworkClient
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager
from tools.genesis_network_hub import GenesisNetworkHub


class FakeProvider:
    def chat(self, messages: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "action": "поставить пустое кресло под дождём и не занимать его",
                "reason": "проверить, продолжится ли сцена без центра",
                "expected_uncertainty": "неизвестно, кто заметит кресло",
            },
            ensure_ascii=False,
        )


class GenesisV187ConnectivityTests(unittest.TestCase):
    def test_ai_bridge_proposes_but_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            before = world.memory.load_player("architect")
            proposal = GenesisAIBridge(FakeProvider()).propose_action(
                world,
                "architect",
                "удиви меня действием, которого нет в меню",
            )
            after = world.memory.load_player("architect")

            self.assertEqual(proposal["authority"], "proposal_only")
            self.assertFalse(proposal["executed"])
            self.assertIn("пустое кресло", proposal["action"])
            self.assertEqual(before.tick, after.tick)
            self.assertEqual(before.good_count, after.good_count)

    def test_portable_save_is_one_verified_json_without_api_keys(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            source_path = Path(source)
            world = PlayableGenesisV187(source_path)
            world.process_action("architect", "создать сад для неизвестного посетителя")
            world.process_action("architect", "наблюдать дождь из пустой обсерватории")
            manager = PortableSaveManager(source_path)
            output = source_path.parent / "architect.genesis-save.json"
            try:
                exported = manager.export_to(output, label="Architect test save")
                bundle = json.loads(output.read_text(encoding="utf-8"))
                valid, count, error = manager.verify_bundle(bundle)
                raw = output.read_text(encoding="utf-8")

                self.assertTrue(valid, error)
                self.assertGreater(count, 0)
                self.assertFalse(bundle["contains_api_keys"])
                self.assertNotIn("GENESIS_NETWORK_API_KEY", raw)
                self.assertEqual(exported["contains_api_keys"], False)

                imported = PortableSaveManager(target).import_bundle(bundle)
                restored = PlayableGenesisV187(Path(target))
                self.assertTrue(imported["valid"])
                self.assertEqual(
                    restored.public_state("architect")["free_path_turns"],
                    world.public_state("architect")["free_path_turns"],
                )
                self.assertTrue(restored.verify_chronicle_records()[0])
                self.assertTrue(restored.verify_free_other_state()[0])
            finally:
                output.unlink(missing_ok=True)

    def test_portable_save_rejects_credential_named_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = PortableSaveManager(directory)
            content = "{}"
            bundle = {
                "schema": "janus.genesis.portable_save.v1",
                "runtime_version": "18.7.0",
                "contains_api_keys": False,
                "files": [
                    {
                        "path": "api_keys.json",
                        "kind": "json",
                        "size_bytes": len(content.encode("utf-8")),
                        "sha256": __import__("hashlib").sha256(content.encode("utf-8")).hexdigest(),
                        "content": content,
                    }
                ],
                "manifest_sha256": "0" * 64,
            }
            valid, _, error = manager.verify_bundle(bundle)
            self.assertFalse(valid)
            self.assertIn("credential-like", error or "")

    def test_network_event_is_public_hashed_and_key_is_not_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_key = "network-key-that-must-not-enter-json"
            with patch.dict(os.environ, {"GENESIS_NETWORK_API_KEY": raw_key}, clear=False):
                client = GenesisNetworkClient(
                    directory,
                    hub_url="http://127.0.0.1:9",
                )
                event = client.queue_public_event(
                    "architect",
                    "public_creation",
                    {"title": "Обсерватория без центрального кресла"},
                )
                state_text = (Path(directory) / "network_client_v18_7.json").read_text(encoding="utf-8")

            self.assertTrue(client.verify_event(event)[0])
            self.assertNotIn("architect", event["public_player_id"])
            self.assertNotIn(raw_key, state_text)
            self.assertFalse(client.state()["api_key_persisted"])

    def test_network_rejects_secret_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = GenesisNetworkClient(directory, hub_url="http://127.0.0.1:9")
            with self.assertRaises(ValueError):
                client.queue_public_event(
                    "architect",
                    "public_message",
                    {"api_key": "never"},
                )

    def test_hashed_bearer_verification(self) -> None:
        key = "local-test-key"
        digest = api_key_sha256(key)
        with patch.dict(os.environ, {"TEST_KEY_HASHES": digest}, clear=False):
            self.assertTrue(
                verify_bearer(
                    {"Authorization": f"Bearer {key}"},
                    hashes_env="TEST_KEY_HASHES",
                )
            )
            self.assertFalse(
                verify_bearer(
                    {"Authorization": "Bearer wrong"},
                    hashes_env="TEST_KEY_HASHES",
                )
            )

    def test_two_devices_exchange_events_through_reference_hub(self) -> None:
        with tempfile.TemporaryDirectory() as hub_dir, tempfile.TemporaryDirectory() as node_a, tempfile.TemporaryDirectory() as node_b:
            key = "shared-network-test-key"
            with patch.dict(
                os.environ,
                {
                    "GENESIS_NETWORK_KEY_HASHES": api_key_sha256(key),
                    "NODE_A_KEY": key,
                    "NODE_B_KEY": key,
                    "JANUS_LEGACY_DIRECT_EGRESS": "1",
                },
                clear=False,
            ):
                hub = GenesisNetworkHub(("127.0.0.1", 0), Path(hub_dir))
                thread = threading.Thread(target=hub.serve_forever, daemon=True)
                thread.start()
                try:
                    url = f"http://127.0.0.1:{hub.server_address[1]}"
                    alpha = GenesisNetworkClient(node_a, hub_url=url, api_key_env="NODE_A_KEY")
                    beta = GenesisNetworkClient(node_b, hub_url=url, api_key_env="NODE_B_KEY")
                    event = alpha.queue_public_event(
                        "alpha",
                        "shared_place",
                        {"title": "Мост без объявленного назначения"},
                    )
                    first = alpha.sync()
                    second = beta.sync()
                    inbox = beta.public_inbox()

                    self.assertEqual(first["accepted"], 1)
                    self.assertGreaterEqual(second["received"], 1)
                    self.assertTrue(any(item["event"]["event_hash"] == event["event_hash"] for item in inbox))
                    self.assertTrue(all(item["event"]["schema"] == "janus.genesis.network.event.v1" for item in inbox))
                finally:
                    hub.shutdown()
                    hub.server_close()
                    thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
