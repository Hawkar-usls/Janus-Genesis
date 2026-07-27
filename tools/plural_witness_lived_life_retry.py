# -*- coding: utf-8 -*-
"""Run the same lived life with a query lexically absent from the pinned Registry."""
from __future__ import annotations

import tools.plural_witness_lived_life as life

# The first probe contained "квантовый", which correctly matched two quantum origins.
# These synthetic lexemes are intentionally meaningless and absent from the pinned
# source collection; they contain no private or real-world information.
life.NO_MATCH_QUERY = "zzqvplmno brtkgfwyu nxephora20260728"

if __name__ == "__main__":
    life.main()
