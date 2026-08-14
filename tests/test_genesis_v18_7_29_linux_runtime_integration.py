from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_25_durable_journal_fencing import DurableHashJournal, SQLiteEffectFenceStore
from genesis_v18_7_26_controlled_ai_link import ControlMode, RuntimeControlAdapter
from genesis_v18_7_29_portable_resource_lifetime import (
    ClientRequestConflict,
    PersistentClientRequestLedger,
    PortableControlledClientExecutor,
)
from genesis_v18_7_playable import PlayableGenesisV187


class V18729CanonicalRuntimeIntegrationTests(unittest.TestCase):
    def test_corrected_ledger_reuses_one_real_canonical_runtime_effect(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = RuntimeControlAdapter(
                world,
                journal=DurableHashJournal(root / "runtime-control.jsonl"),
                fences=SQLiteEffectFenceStore(root / "runtime-fences.sqlite3"),
                mode=ControlMode.ENFORCED,
                holder_id="v18.7.29-integration",
                lease_ticks=1_000_000,
            )
            ledger = PersistentClientRequestLedger(root / "client-requests.sqlite3")
            client = PortableControlledClientExecutor(ledger=ledger, runtime=adapter)
            action = "создать тихий сад"

            before = world.memory.load_player("mira").tick
            first = client.execute(
                client_id="default-cli-prototype",
                request_id="CLI-REQ-1",
                actor_id="mira",
                action=action,
            )
            after_first = world.memory.load_player("mira").tick
            self.assertGreater(after_first, before)

            second = client.execute(
                client_id="default-cli-prototype",
                request_id="CLI-REQ-1",
                actor_id="mira",
                action=action,
            )
            self.assertEqual(world.memory.load_player("mira").tick, after_first)
            self.assertEqual(first.to_dict(internal=True), second.to_dict(internal=True))

            with self.assertRaises(ClientRequestConflict):
                client.execute(
                    client_id="default-cli-prototype",
                    request_id="CLI-REQ-1",
                    actor_id="mira",
                    action="создать мост",
                )


if __name__ == "__main__":
    unittest.main()
