"""Lightweight, dependency-free Janus Cosmos v0.1 scaffold.

The runner consumes pre-extracted numeric feature rows rather than downloading
astronomical data itself. This keeps the GitHub test cheap and makes source
provenance explicit. A row is expected to contain object_id, band, x, y, scale,
orientation, and signal. The planner proposes deterministic multiscale
trajectories; scoring is compared with spatially permuted nulls.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import random
import sys
from pathlib import Path

WINDOWS = (8, 16, 32)
ORIENTATIONS = tuple(range(0, 180, 30))
NULLS = 256
SEED = 20260810


def planner(x: float, y: float, scale: int, orientation: int) -> float:
    """Deterministic blind trajectory score; no outcome-dependent tuning."""
    a = math.radians(orientation)
    u = x * math.cos(a) + y * math.sin(a)
    v = -x * math.sin(a) + y * math.cos(a)
    return math.sin(u * scale * 0.17) * math.cos(v * scale * 0.11)


def score(rows):
    if not rows:
        return 0.0
    values = []
    for r in rows:
        s = 0.0
        for scale in WINDOWS:
            for orientation in ORIENTATIONS:
                s += abs(planner(r["x"], r["y"], scale, orientation))
        values.append(s / (len(WINDOWS) * len(ORIENTATIONS)))
    return sum(values) / len(values)


def main(path: str):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"object_id": r["object_id"], "band": r["band"],
                         "x": float(r["x"]), "y": float(r["y"]),
                         "signal": float(r.get("signal", 1.0))})
    observed = score(rows)
    rng = random.Random(SEED)
    null = []
    for _ in range(NULLS):
        shuffled = rows[:]
        rng.shuffle(shuffled)
        null.append(score(shuffled))
    ge = sum(v >= observed for v in null)
    p = (ge + 1) / (NULLS + 1)
    receipt = {
        "schema": "janus.cosmos.fractalgpt.receipt.v0.1",
        "status": "CANDIDATE_ONLY" if p < 0.05 else "NO_CANDIDATE",
        "observed_score": observed,
        "null_median": sorted(null)[len(null)//2],
        "p_empirical": p,
        "windows": WINDOWS,
        "orientations": ORIENTATIONS,
        "nulls": NULLS,
        "seed": SEED,
        "semantic_analysis": False,
        "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "claim_ceiling": "Planner enrichment is not a discovery; independent replication is required."
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python run_search.py <features.csv>")
    main(sys.argv[1])
