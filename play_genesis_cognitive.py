#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launch the ordinary Genesis CLI through the v18.7.19 cognitive runtime."""
from __future__ import annotations

import play_genesis as genesis_cli
from genesis_v18_7_19_cognitive_descent import PlayableGenesisV18719

# The established CLI keeps all AI, network, portable-save and debug commands.
# Only its runtime class is replaced for this process.
genesis_cli.PlayableGenesisV187 = PlayableGenesisV18719


if __name__ == "__main__":
    raise SystemExit(genesis_cli.main())
