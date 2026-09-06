#!/usr/bin/env python3
"""R50G32 remaining general two-occurrence sign-preserving nonswap grammar.

R50G30 exhausted reciprocal swaps and R50G31 exhausted one-relay minimum
histogram-drift rewires.  For two genuine sign-preserving occurrence edits over
the same variable universe, the remaining canonical role-equality patterns are:

  SHARED_SOURCE_DOUBLE_TO_ONE   x,x -> y,y
  SHARED_SOURCE_SPLIT_TO_TWO    x,x -> y,z
  DISTINCT_SOURCES_MERGE_ONE    x,z -> y,y
  FOUR_DISTINCT_REROUTE         x,z -> y,w

All role variables named distinctly where implied by the pattern.  Every
remaining pattern has occurrence-histogram L1 drift exactly 4.  Identity edits,
reciprocal swaps (R50G30), and one-relay patterns (R50G31) are excluded by
construction. Clause count/width, literal signs, and the complete variable
universe remain frozen; tautologies, duplicate literals, and canonical clause
collapse are rejected.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterator

import trump_r50g30_two_occurrence_coupled_rewire_agent as r50g30

PATTERNS = (
    "SHARED_SOURCE_DOUBLE_TO_ONE",
    "SHARED_SOURCE_SPLIT_TO_TWO",
    "DISTINCT_SOURCES_MERGE_ONE",
    "FOUR_DISTINCT_REROUTE",
)


def histogram_l1(a: Counter[int], b: Counter[int]) -> int:
    return sum(abs(int(a[k]) - int(b[k])) for k in set(a) | set(b))


def classify_roles(a: int, b: int, c: int, d: int) -> str:
    """Classify two genuine edits a->c, b->d by variable-role equality."""
    if c == a or d == b:
        return "IDENTITY_EDIT_INVALID"
    if a == b:
        if c == d:
            return "SHARED_SOURCE_DOUBLE_TO_ONE"
        return "SHARED_SOURCE_SPLIT_TO_TWO"
    # Distinct sources.
    if c == b and d == a:
        return "ALREADY_R50G30_RECIPROCAL_SWAP"
    # Either orientation of the one-relay pattern is R50G31 after ordering edits.
    if d == a and c not in {a, b}:
        return "ALREADY_R50G31_ONE_RELAY"
    if c == b and d not in {a, b}:
        return "ALREADY_R50G31_ONE_RELAY"
    # With genuine edits, any remaining common target cannot be either source.
    if c == d:
        return "DISTINCT_SOURCES_MERGE_ONE"
    # Any remaining distinct targets must both lie outside the source pair.
    if c not in {a, b} and d not in {a, b}:
        return "FOUR_DISTINCT_REROUTE"
    return "UNEXPECTED_ROLE_PATTERN"


def remaining_two_occurrence_mutants(r50g23, formula) -> Iterator[dict[str, Any]]:
    base = list(r50g23.canon(formula))
    base_tuple = tuple(base)
    base_clause_count = len(base)
    base_vars = {abs(int(lit)) for clause in base for lit in clause}
    vars_sorted = sorted(base_vars)
    base_hist = r50g30.occurrence_histogram(base)
    occ = r50g30.occurrences(base)

    # Choose an unordered pair of literal occurrences once. Target assignment is
    # still ordered because each target belongs to a specific occurrence/sign.
    for i in range(len(occ)):
        ci1, li1, lit1 = occ[i]
        a = abs(int(lit1)); sign1 = 1 if int(lit1) > 0 else -1
        for j in range(i + 1, len(occ)):
            ci2, li2, lit2 = occ[j]
            b = abs(int(lit2)); sign2 = 1 if int(lit2) > 0 else -1
            for c in vars_sorted:
                if c == a:
                    continue
                for d in vars_sorted:
                    if d == b:
                        continue
                    pattern = classify_roles(a, b, int(c), int(d))
                    if pattern not in PATTERNS:
                        continue

                    raw = [list(clause) for clause in base]
                    raw[ci1][li1] = sign1 * int(c)
                    raw[ci2][li2] = sign2 * int(d)
                    if any(not r50g30.valid_clause(raw[ci]) for ci in {ci1, ci2}):
                        continue
                    mutated = r50g23.canon(tuple(tuple(sorted(int(v) for v in clause)) for clause in raw))
                    if len(mutated) != base_clause_count or mutated == base_tuple:
                        continue
                    mutated_vars = {abs(int(v)) for clause in mutated for v in clause}
                    if mutated_vars != base_vars:
                        continue
                    mhist = r50g30.occurrence_histogram(mutated)
                    if histogram_l1(base_hist, mhist) != 4:
                        continue

                    delta = {k: int(mhist[k]) - int(base_hist[k]) for k in sorted(base_vars) if mhist[k] != base_hist[k]}
                    yield {
                        "pattern": pattern,
                        "first": {
                            "clause_index": int(ci1),
                            "literal_index": int(li1),
                            "old_literal": int(lit1),
                            "new_literal": sign1 * int(c),
                            "old_variable": a,
                            "new_variable": int(c),
                        },
                        "second": {
                            "clause_index": int(ci2),
                            "literal_index": int(li2),
                            "old_literal": int(lit2),
                            "new_literal": sign2 * int(d),
                            "old_variable": b,
                            "new_variable": int(d),
                        },
                        "histogram_delta": {str(k): v for k, v in delta.items()},
                        "mutated": mutated,
                    }
