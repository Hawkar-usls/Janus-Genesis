from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    MODE_AUTHORITATIVE,
    ORIGIN_HUMAN,
    ROLE_HUMAN_THROUGH_AI,
)
from genesis_v18_7_25_durable_journal_fencing import DurableHashJournal, SQLiteEffectFenceStore
from genesis_v18_7_26_controlled_ai_link import (
    ControlMode,
    ControlledGenesisAILinkGateway,
    RuntimeControlAdapter,
)
from genesis_v18_7_28_client_ledger_attestation import (
    ClientRequestConflict,
    ControlledClientExecutor,
    LifecycleSerializedGateway,
    PersistentClientRequestLedger,
)
from genesis_v18_7_playable import PlayableGenesisV187


class V18728CanonicalRuntimeIntegrationTests(unittest.TestCase):
    @staticmethod
    def _adapter(world, root: Path):
        return RuntimeControlAdapter(
            world,
            journal=DurableHashJournal(root / "runtime-control.jsonl"),
            fences=SQLiteEffectFenceStore(root / "runtime-fences.sqlite3"),
            mode=ControlMode.ENFORCED,
            holder_id="v18.7.28-integration",
            lease_ticks=1_000_000,
        )

    def test_persistent_client_request_retries_same_canonical_runtime_effect(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = self._adapter(world, root)
            ledger = PersistentClientRequestLedger(root / "client-requests.sqlite3")
            client = ControlledClientExecutor(ledger=ledger, runtime=adapter)
            action = "создать тихий сад"

            before = world.memory.load_player("mira").tick
            first = client.execute(
                client_id="default-cli",
                request_id="CLI-REQ-1",
                actor_id="mira",
                action=action,
            )
            after_first = world.memory.load_player("mira").tick
            self.assertGreater(after_first, before)

            second = client.execute(
                client_id="default-cli",
                request_id="CLI-REQ-1",
                actor_id="mira",
                action=action,
            )
            after_second = world.memory.load_player("mira").tick
            self.assertEqual(after_second, after_first)
            self.assertEqual(first.to_dict(internal=True), second.to_dict(internal=True))

            with self.assertRaises(ClientRequestConflict):
                client.execute(
                    client_id="default-cli",
                    request_id="CLI-REQ-1",
                    actor_id="mira",
                    action="создать мост",
                )

    def test_lifecycle_wrapper_composes_with_controlled_ai_link_gateway(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = self._adapter(world, root)
            base = ControlledGenesisAILinkGateway(world, root, adapter=adapter)
            gateway = LifecycleSerializedGateway(base, root)

            session = gateway.register_session(
                role=ROLE_HUMAN_THROUGH_AI,
                execution_mode=MODE_AUTHORITATIVE,
                display_name="Mira",
                provider="integration-provider",
                model="integration-model",
                actor_id="mira",
            )
            turn = gateway.process_turn(
                session["session_id"],
                "создать музыку и не требовать слушателя",
                origin=ORIGIN_HUMAN,
                human_confirmed=True,
            )
            self.assertEqual(turn["sequence"], 1)
            self.assertTrue(turn["result"]["canonical_runtime_outcome_recorded"])

            closed = gateway.close_session(session["session_id"], reason="integration-complete")
            self.assertEqual(closed["status"], "CLOSED")
            self.assertTrue(closed["return_open"])
            self.assertTrue(gateway.verify_store()["valid"])


if __name__ == "__main__":
    unittest.main()
