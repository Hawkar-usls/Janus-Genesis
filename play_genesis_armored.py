# -*- coding: utf-8 -*-
"""Canonical Armor-gated launcher for JANUS Genesis v18.7.50.

The historical ``play_genesis.py`` remains available for provenance and
compatibility. This launcher is the preferred executable entry because its
optional AI-provider egress and Genesis Network sync are wrapped by the frozen
v18.7.49 Armor gate before legacy adapter code can cross an external boundary.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import play_genesis as legacy
from genesis_v18_7_50_armor_routing import (
    ArmoredDurableGenesisNetworkClient,
    ArmoredGenesisAIBridge,
)

ARMOR_ENTRY_VERSION = "18.7.50"
_ORIGINAL_AI_BUILDER = legacy._build_ai_bridge


def _build_armored_ai_bridge(args: Any) -> ArmoredGenesisAIBridge | None:
    base = _ORIGINAL_AI_BUILDER(args)
    if base is None:
        return None
    return ArmoredGenesisAIBridge(base.provider)


def _build_armored_network_client(
    args: Any,
    data_dir: Path,
) -> ArmoredDurableGenesisNetworkClient | None:
    if not args.network_url:
        return None
    return ArmoredDurableGenesisNetworkClient(
        data_dir,
        hub_url=args.network_url,
        api_key_env=args.network_key_env,
        timeout_seconds=args.network_timeout,
    )


def main(argv: list[str] | None = None) -> int:
    # Cooperating canonical binding. Legacy module remains unchanged and is not
    # silently reclassified as armored when imported directly.
    legacy._build_ai_bridge = _build_armored_ai_bridge
    legacy._build_network_client = _build_armored_network_client
    return legacy.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
