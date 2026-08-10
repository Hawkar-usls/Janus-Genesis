"""Lightweight Janus Cosmos FractalGPT v0.1 preflight.

This runner intentionally consumes pre-extracted feature rows. It does not
claim to ingest or discover astronomical images by itself. The null model
randomizes coordinates while preserving the observed per-row signal/band
values, so the null can actually differ from the observed spatial arrangement.
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
                s += abs(planner(r["x"], r["y"], scale, orientation)) * abs(r["signal"])
        values.append(s / (len(WINDOWS) * len(ORIENTATIONS)))
    return sum(values) / len(values)


def main(path: str):
    source = Path(path)
    rows = []
    with source.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "object_id": r["object_id"],
                "band": r["band"],
                "x": float(r["x"]),
                "y": float(r["y"]),
                "signal": float(r.get("signal", 1.0)),
            })
    observed = score(rows)
    rng = random.Random(SEED)
    xs = [r["x"] for r in rows]
    ys = [r["y"] for r in rows]
    null = []
    for _ in range(NULLS):
        shuffled_x = xs[:]
        shuffled_y = ys[:]
        rng.shuffle(shuffled_x)
        rng.shuffle(shuffled_y)
        randomized = [dict(r, x=x, y=y) for r, x, y in zip(rows, shuffled_x, shuffled_y)]
        null.append(score(randomized))
    ge = sum(v >= observed for v in null)
    p = (ge + 1) / (NULLS + 1)
    null_sorted = sorted(null)
    receipt = {
        "schema": "janus.cosmos.fractalgpt.receipt.v0.1",
        "status": "CANDIDATE_ONLY" if p < 0.05 else "NO_CANDIDATE",
        "observed_score": observed,
        "null_median": null_sorted[len(null_sorted) // 2],
        "p_empirical": p,
        "windows": list(WINDOWS),
        "orientations": list(ORIENTATIONS),
        "nulls": NULLS,
        "seed": SEED,
        "semantic_analysis": False,
        "null_model": "independent coordinate permutation preserving row signal and band",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "claim_ceiling": "Planner enrichment is not a discovery; independent replication is required.",
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python run_search.py <features.csv>")
    main(sys.argv[1])
