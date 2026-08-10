# Janus Cristal × FractalGPT sandbox

This experiment uses **Janus Genesis only as an isolated creative-technology sandbox**. It does not alter the authoritative Genesis gameplay runtime.

## Recovered FractalGPT

The user's prior `FractalGPT(12).py` was recovered from the file library and vendored unchanged into this sandbox as:

`recovered/FractalGPT.py`

Exact recovered source SHA-256:

`11e6c97ae7169a0fae4e0ad17f2fb7fb23b10265b04b4b057e3c968d6d0a3662`

The recovered source is a small autoregressive model whose state is approximately `[x, y, angle, scale, iteration]`. It also contains native generators for a Koch curve, a Sierpinski triangle and fractal Brownian motion. The sandbox uses those actual components rather than merely borrowing the name.

For this experiment:

```text
FractalGPT / fractal planner = WHERE / AT WHAT SCALE TO LOOK
OCR + image metrics         = WHAT THE FIXED DETECTOR MEASURES
matched shuffled control    = WHETHER THE EFFECT SURVIVES A NULL MODEL
admission gate              = WHETHER A RESULT MAY BE ESCALATED
```

The FractalGPT layer does **not** invent text, decode ciphers, or decide that a pattern is meaningful.

## v0.2 question

Do several content-independent search planners — including the recovered FractalGPT's own generators and a tiny deterministically trained instance of the recovered autoregressive model — independently converge on the same word/formula/code-like or geometric candidates in crystal imagery more often than on matched shuffled controls?

The first corpus intentionally reuses the strongest public pair from `Janus Cristal`:

- the same petroleum-quartz specimen in visible light;
- the same specimen under 405 nm UV;
- an ordinary USGS quartz image as a visible control.

## Five independent planners

Each planner emits 20 normalized `(x, y, scale)` windows from a fixed seed:

1. `logistic_baseline` — the v0.1 SHA-256-seeded coupled logistic map;
2. `fractalgpt_koch` — recovered `FractalGPT.koch_curve()`;
3. `fractalgpt_sierpinski` — recovered `FractalGPT.sierpinski_triangle()` with deterministic RNG seeds;
4. `fractalgpt_fbm` — recovered `FractalGPT.fractal_brownian_motion()`, promoted into a 2-D scan path;
5. `fractalgpt_model` — an actual tiny recovered `FractalGPT` instance (`1 layer / 8 embedding / 2 heads`) trained for eight deterministic steps on short Koch sequences, then used to generate a scan trajectory.

The exact same windows from every planner are applied to:

1. the real image;
2. a deterministic block-shuffled negative control.

That symmetry is mandatory. A candidate that also appears in the shuffled control is not special.

## Two replication levels

A raw OCR token can appear once and is recorded only as detector behavior. A planner-local escalation requires at least three characters, at least two hits within that planner, a word/formula/code-like class, and absence from that planner's matched control.

A **cross-planner escalation** requires the same admissible token to survive at least two independent planner families. A **cross-modality escalation** requires that stronger candidate to repeat across recorded modalities. Even that still opens only an independent replication gate.

## Semantic ceiling

```text
FRACTAL_PATH != DISCOVERY
OCR_TOKEN != MESSAGE
FORMULA_LIKE != FORMULA
CODE_LIKE != ALGORITHM
REAL_OVER_CONTROL_ENRICHMENT != INTENTIONAL_ENCODING
CROSS_PLANNER_REPLICATION != MESSAGE
CROSS_MODALITY_REPLICATION != MESSAGE
UV_DIFFERENCE != SEMANTIC_CONTENT
NO_POST_HOC_CIPHER_SEARCH
```

## Files

- `recovered/FractalGPT.py` — exact recovered user source
- `fractalgpt_adapter.py` — deterministic adapter and tiny-model trajectory runner
- `sources.json` — public source registry and planner configuration
- `fractal_crystal_probe.py` — multi-planner measurement + controls
- `../../tests/test_janus_cristal_fractalgpt.py` — deterministic/adversarial tests
- `../../.github/workflows/janus-cristal-fractalgpt.yml` — CI
- `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.1.json` — machine-readable experiment object
