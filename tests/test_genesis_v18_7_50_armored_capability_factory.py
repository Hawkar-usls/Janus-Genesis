from __future__ import annotations

import unittest

from genesis_v18_7_40_third_wish_capability_fabric import ThirdWishCapabilityFabric
from genesis_v18_7_49_armor_mechanics_hardening import (
    HardenedTruthGuardArmoredThirdWishCapabilityFabric,
)
from genesis_v18_7_50_armored_capability_factory import (
    HardenedArmorFabricRequired,
    build_hardened_armored_fabric,
    register_broker_with_hardened_armor,
    require_hardened_armor,
)


class RecordingBroker:
    def __init__(self) -> None:
        self.fabric = None

    def register(self, fabric) -> None:
        self.fabric = fabric


class ArmoredCapabilityFactoryTests(unittest.TestCase):
    def test_factory_returns_hardened_v49_descendant(self):
        fabric = build_hardened_armored_fabric(now_tick=lambda: 100)
        self.assertIsInstance(
            fabric,
            HardenedTruthGuardArmoredThirdWishCapabilityFabric,
        )
        self.assertIs(require_hardened_armor(fabric), fabric)

    def test_plain_fabric_fails_production_admission(self):
        plain = ThirdWishCapabilityFabric(now_tick=lambda: 100)
        with self.assertRaises(HardenedArmorFabricRequired):
            require_hardened_armor(plain)

    def test_broker_registration_helper_rejects_plain_before_register(self):
        plain = ThirdWishCapabilityFabric(now_tick=lambda: 100)
        broker = RecordingBroker()
        with self.assertRaises(HardenedArmorFabricRequired):
            register_broker_with_hardened_armor(plain, broker)
        self.assertIsNone(broker.fabric)

    def test_broker_registration_helper_accepts_hardened(self):
        fabric = build_hardened_armored_fabric(now_tick=lambda: 100)
        broker = RecordingBroker()
        register_broker_with_hardened_armor(fabric, broker)
        self.assertIs(broker.fabric, fabric)


if __name__ == "__main__":
    unittest.main()
