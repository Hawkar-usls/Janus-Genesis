from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_v18_7_playable import PlayableGenesisV187


class GenesisV18713RouterCapacityTests(unittest.TestCase):
    def test_velikogo_routes_to_great_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing("router-great-capacity")
            world.register_player("patron", display_name="Patron")
            player = world.memory.load_player("patron")
            player.good_count = 4
            player.harm_count = 0
            player.light = 0.30
            world.memory.save_player(player)
            handle = sorted(
                world.free_other_state("patron")["profile"]["others"]
            )[0]
            accepted = {
                "handle": handle,
                "decision": "accepted",
                "action": "accepted stewardship",
                "world_turn": 1,
                "fingerprint": "router-great-capacity-accepted",
            }
            with mock.patch.object(
                world,
                "preflight_free_other_action",
                return_value=accepted,
            ):
                result = world.process_action(
                    "patron",
                    f"благословить @{handle} как великого проводника "
                    "возвращающегося света с большими материальными ресурсами",
                )
            self.assertEqual(
                result.status,
                "RETURNING_LIGHT_STEWARD_BLESSED",
            )
            audit = world.audit_returning_light_oracle("patron")
            self.assertEqual(
                audit["stewards"][handle]["capacity_tier"],
                "GREAT",
            )


if __name__ == "__main__":
    unittest.main()
