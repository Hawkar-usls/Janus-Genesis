from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_31_portable_receipt_runtime import (
    PortableCrashInjector,
    PortableCrashPoint,
    PortableReceiptRuntimeAdapter,
    PortableRuntimeControlError,
    PortableRuntimeOutcomeUndetermined,
)
from genesis_v18_7_playable import PlayableGenesisV187


class RealPortableRuntimeIntegrationTests(unittest.TestCase):
    def test_real_canonical_world_settles_and_replays_without_second_tick(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = PortableReceiptRuntimeAdapter(world, root)
            before = world.memory.load_player("mira").tick
            first = adapter.execute(
                client_id="play-genesis",
                request_id="REAL-1",
                actor_id="mira",
                action="создать тихий сад",
            )
            after = world.memory.load_player("mira").tick
            self.assertGreater(after, before)
            replayed = adapter.execute(
                client_id="play-genesis",
                request_id="REAL-1",
                actor_id="mira",
                action="создать тихий сад",
            )
            self.assertEqual(world.memory.load_player("mira").tick, after)
            self.assertEqual(first.to_dict(internal=True), replayed.to_dict(internal=True))

    def test_real_world_after_world_before_receipt_is_blocked_not_reexecuted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = PortableReceiptRuntimeAdapter(
                world,
                root,
                crash_injector=PortableCrashInjector(PortableCrashPoint.AFTER_WORLD_BEFORE_RECEIPT),
            )
            before = world.memory.load_player("mira").tick
            with self.assertRaises(PortableRuntimeControlError):
                adapter.execute(
                    client_id="play-genesis",
                    request_id="REAL-2",
                    actor_id="mira",
                    action="создать музыку",
                )
            after = world.memory.load_player("mira").tick
            self.assertGreater(after, before)
            with self.assertRaises(PortableRuntimeOutcomeUndetermined):
                PortableReceiptRuntimeAdapter(world, root).execute(
                    client_id="play-genesis",
                    request_id="REAL-2",
                    actor_id="mira",
                    action="создать музыку",
                )
            self.assertEqual(world.memory.load_player("mira").tick, after)


if __name__ == "__main__":
    unittest.main()
