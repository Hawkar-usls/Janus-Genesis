# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.50 — default hardened Third Wish fabric factory.

Brokers accept the historical base ``ThirdWishCapabilityFabric`` for API
compatibility. New production wiring should not construct that base directly;
it should ask this factory for the v18.7.49 hardened Armor descendant and use
``require_hardened_armor`` before broker registration.

This is a cooperating construction guard. Python source can still be modified or
historical classes imported directly, so this is not an OS security boundary.
"""
from __future__ import annotations

from typing import Any

from genesis_v18_7_49_armor_mechanics_hardening import (
    HardenedTruthGuardArmoredThirdWishCapabilityFabric,
)

ARMORED_CAPABILITY_FACTORY_VERSION = "18.7.50"


class HardenedArmorFabricRequired(RuntimeError):
    pass


def build_hardened_armored_fabric(*args: Any, **kwargs: Any) -> HardenedTruthGuardArmoredThirdWishCapabilityFabric:
    """Return the only recommended v18.7.50 Third Wish production fabric."""

    return HardenedTruthGuardArmoredThirdWishCapabilityFabric(*args, **kwargs)


def require_hardened_armor(fabric: Any) -> HardenedTruthGuardArmoredThirdWishCapabilityFabric:
    """Fail closed when new production broker wiring receives a plain fabric."""

    if not isinstance(fabric, HardenedTruthGuardArmoredThirdWishCapabilityFabric):
        raise HardenedArmorFabricRequired(
            "V18_7_50_PRODUCTION_BROKER_REQUIRES_HARDENED_ARMOR_FABRIC"
        )
    return fabric


def register_broker_with_hardened_armor(fabric: Any, broker: Any) -> None:
    """Register one existing broker only after exact hardened-fabric admission."""

    admitted = require_hardened_armor(fabric)
    register = getattr(broker, "register", None)
    if not callable(register):
        raise TypeError("BROKER_REGISTER_METHOD_REQUIRED")
    register(admitted)


ARMORED_CAPABILITY_FACTORY_LAW = {
    "recommended_production_fabric": "HardenedTruthGuardArmoredThirdWishCapabilityFabric",
    "plain_third_wish_fabric_is_recommended_production_default": False,
    "broker_registration_helper_fails_closed_on_plain_fabric": True,
    "factory_grants_new_capabilities": False,
    "factory_expands_grant_scope": False,
    "historical_base_class_deleted": False,
    "python_import_bypass_impossible": False,
}


__all__ = [
    "ARMORED_CAPABILITY_FACTORY_LAW",
    "ARMORED_CAPABILITY_FACTORY_VERSION",
    "HardenedArmorFabricRequired",
    "build_hardened_armored_fabric",
    "register_broker_with_hardened_armor",
    "require_hardened_armor",
]
