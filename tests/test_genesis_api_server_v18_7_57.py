# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_31_portable_receipt_runtime import PortableRequestConflict
from genesis_v18_7_39_typed_mutation_authority import TypedMutationRequestConflict
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager
from tools.genesis_api_server import GenesisAPIHandler, GenesisAPIServer


class GenesisAPIServerV1857Tests(unittest.TestCase):
    def _server(self, root: str) -> GenesisAPIServer:
        return GenesisAPIServer(("127.0.0.1", 0), Path(root))

    def test_mutation_request_id_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "request_id is required"):
            GenesisAPIHandler._request_id({})
        with self.assertRaisesRegex(ValueError, "request_id is required"):
            GenesisAPIHandler._request_id({"request_id": "   "})
        self.assertEqual(
            GenesisAPIHandler._request_id({"request_id": "REQ-1"}),
            "REQ-1",
        )

    def test_action_request_replays_without_second_world_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = self._server(tmp)
            try:
                calls = 0
                raw = server.world.process_action

                def counted(actor_id, action):
                    nonlocal calls
                    calls += 1
                    return raw(actor_id, action)

                server.world.process_action = counted
                first = server.process_action(
                    request_id="ACTION-1",
                    player_id="traveler",
                    action="look around",
                )
                second = server.process_action(
                    request_id="ACTION-1",
                    player_id="traveler",
                    action="look around",
                )
                self.assertEqual(first.to_dict(internal=True), second.to_dict(internal=True))
                self.assertEqual(calls, 1)
                state = server.actions.request_state(
                    client_id="genesis-api-server",
                    request_id="ACTION-1",
                )
                self.assertEqual(state["state"], "SETTLED")
            finally:
                server.server_close()

    def test_action_request_id_cannot_be_rebound_to_different_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = self._server(tmp)
            try:
                server.process_action(
                    request_id="ACTION-CONFLICT",
                    player_id="traveler",
                    action="look around",
                )
                with self.assertRaises(PortableRequestConflict):
                    server.process_action(
                        request_id="ACTION-CONFLICT",
                        player_id="traveler",
                        action="walk elsewhere",
                    )
            finally:
                server.server_close()

    def test_name_request_replays_and_conflicting_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = self._server(tmp)
            try:
                calls = 0
                raw = server.world.set_display_name

                def counted(actor_id, display_name):
                    nonlocal calls
                    calls += 1
                    return raw(actor_id, display_name)

                server.world.set_display_name = counted
                first = server.set_display_name(
                    request_id="NAME-1",
                    player_id="traveler",
                    display_name="Janus",
                )
                second = server.set_display_name(
                    request_id="NAME-1",
                    player_id="traveler",
                    display_name="Janus",
                )
                self.assertEqual(first, second)
                self.assertEqual(calls, 1)
                with self.assertRaises(TypedMutationRequestConflict):
                    server.set_display_name(
                        request_id="NAME-1",
                        player_id="traveler",
                        display_name="Different",
                    )
            finally:
                server.server_close()

    def test_recovery_safe_import_replays_same_logical_request(self) -> None:
        with tempfile.TemporaryDirectory() as source_tmp, tempfile.TemporaryDirectory() as dest_tmp:
            PlayableGenesisV187(source_tmp)
            source = PortableSaveManager(source_tmp)
            bundle = source.build_bundle(label="api-v57-test")
            server = self._server(dest_tmp)
            try:
                first = server.import_save(
                    request_id="IMPORT-1",
                    bundle=bundle,
                    conflict="replace",
                )
                second = server.import_save(
                    request_id="IMPORT-1",
                    bundle=bundle,
                    conflict="replace",
                )
                self.assertEqual(first, second)
                state = server.saves.request_state("IMPORT-1")
                self.assertEqual(state["state"], "SETTLED")
                self.assertIs(server.actions.world, server.world)
                self.assertIs(server.auxiliary.world, server.world)
            finally:
                server.server_close()

    def test_handler_source_no_longer_contains_raw_mutation_calls(self) -> None:
        source = Path("tools/genesis_api_server.py").read_text(encoding="utf-8")
        self.assertNotIn("self.server.world.process_action", source)
        self.assertNotIn("self.server.world.set_display_name", source)
        self.assertNotIn("self.server.saves.import_bundle(", source)
        self.assertIn("self.server.process_action(", source)
        self.assertIn("self.server.set_display_name(", source)
        self.assertIn("self.server.import_save(", source)


if __name__ == "__main__":
    unittest.main()
