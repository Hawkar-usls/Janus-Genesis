# -*- coding: utf-8 -*-
"""Canonical semantic Spiral entrypoint for Janus Genesis v18.7.53.

Historical ``play_genesis.py`` remains intact for compatibility.  This entrypoint
reuses its hardened control surfaces but replaces the semantic TURN projection
with the durable Genesis Spiral adapter:

    ORIGIN -> EXPERIENCE -> RETURN -> ORIGIN_PRIME

Technical CLI loops are unchanged; only successful logical action lineage is
projected as a spiral.  The adapter creates no new execution authority.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import play_genesis as _legacy
from genesis_v18_7_33_inflight_duplicate_reconciliation import (
    ReconciledPortableReceiptRuntimeAdapter,
)
from genesis_v18_7_53_spiral import GenesisSpiralRuntimeAdapter


class CanonicalGenesisSpiralRuntimeAdapter(GenesisSpiralRuntimeAdapter):
    """Expose the spiral receipt inside the existing read-only request view."""

    def request_state(self, *, client_id: str, request_id: str):
        base = super().request_state(client_id=client_id, request_id=request_id)
        if isinstance(base, dict):
            value: dict[str, Any] = dict(base)
            value["_janus_spiral"] = self.spiral_projection_status(
                client_id=client_id,
                request_id=request_id,
            )
            return value
        return base


def _build_spiral_controlled_runtime(world, data_dir: Path):
    base = ReconciledPortableReceiptRuntimeAdapter(world, data_dir)
    return CanonicalGenesisSpiralRuntimeAdapter(base, world, data_dir)


def banner() -> None:
    print(
        "\n╔══════════════════════════════════════════════════╗\n"
        "║       JANUS GENESIS v18.7.53 SPIRAL            ║\n"
        "║ ORIGIN → EXPERIENCE → RETURN → ORIGIN_PRIME    ║\n"
        "╚══════════════════════════════════════════════════╝\n"
    )


def install_spiral_entrypoint() -> None:
    # Deliberately replace only the controlled-runtime builder and presentation
    # banner.  All mutation, receipt, import/export, network and Armor behavior
    # remains owned by the existing hardened Genesis CLI.
    _legacy._build_controlled_runtime = _build_spiral_controlled_runtime
    _legacy.banner = banner


def main(argv: list[str] | None = None) -> int:
    install_spiral_entrypoint()
    return _legacy.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
