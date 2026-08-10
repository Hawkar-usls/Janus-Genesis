# Janus Cristal × FractalGPT sandbox

This experiment uses **Janus Genesis only as an isolated creative-technology sandbox**. It does not alter the authoritative Genesis gameplay runtime.

## Recovered FractalGPT

The user's prior `FractalGPT(12).py` was recovered from the file library. Its original raw-file SHA-256 is:

`11e6c97ae7169a0fae4e0ad17f2fb7fb23b10265b04b4b057e3c968d6d0a3662`

A connector-serialized text mirror is stored in this sandbox as `recovered/FractalGPT.py`. The exact bytes executed by GitHub CI have SHA-256:

`1dfc5bb1dabcb256d569de30dbe4431f6901c8dcddbe15fb76634fd57d9146e8`

These identities are deliberately **not conflated**. The adapter verifies the mirror actually executed by CI while preserving the original-library hash as provenance.

The recovered source is a small autoregressive model whose state is approximately `[x, y, angle, scale, iteration]`. It contains native generators for a Koch curve, a Sierpinski triangle and fractal Brownian motion. The sandbox uses those components directly rather than merely borrowing the FractalGPT name.

```text
FractalGPT / fractal planner = WHERE / AT WHAT SCALE TO LOOK
OCR + image metrics         = WHAT THE FIXED DETECTOR MEASURES
matched nulls               = WHETHER THE EFFECT SURVIVES A NULL MODEL
admission gate              = WHETHER A RESULT MAY BE ESCALATED
```

The FractalGPT layer does **not** invent text, decode ciphers, or decide that a pattern is meaningful.

## Current v0.3 design

The corpus now contains five open images: the same petroleum-quartz specimen in visible light and under 405 nm UV, ordinary USGS quartz, calcite, and an optical fluorite crystal with published Newton rings.

Six content-independent planners each emit 20 normalized `(x, y, scale)` windows:

1. `logistic_baseline`;
2. `uniform_random_baseline`;
3. `fractalgpt_koch`;
4. `fractalgpt_sierpinski`;
5. `fractalgpt_fbm`;
6. `fractalgpt_model` — an actual tiny recovered FractalGPT instance trained for eight deterministic steps before trajectory generation.

Every planner is replayed against two nulls:

- deterministic 48 px block shuffle — used for OCR and structure;
- Fourier-amplitude-preserving phase scramble — used as a second structure-only null.

## Result: semantic null, mirror candidate falsified

The v0.3 GitHub run analyzed **5/5 sources** with **11/11 tests PASS**. No word, formula, code or algorithm survived cross-planner admission, and no semantic candidate repeated across modalities.

The more interesting result is negative in the productive sense. In v0.2, mirror symmetry looked promising against only the block-shuffle control. v0.3 attacked that observation with a second null, a uniform planner, calcite and fluorite controls.

The count of planners with positive mirror correlation against **both** nulls became:

```text
petroleum quartz / visible = 1 / 6
petroleum quartz / UV405   = 3 / 6
ordinary quartz control    = 1 / 6
calcite control            = 3 / 6
optical fluorite control   = 4 / 6
```

Therefore the earlier mirror signal is **rejected as a quartz-specific effect**. Non-quartz crystals match or exceed it, and the target visible image largely loses the signal when phase structure is randomized.

That is a useful outcome: the sandbox found a positive-looking effect and then successfully killed its strongest interpretation with better controls.

## Next gate

The next useful target is not generic symmetry or symbolic decoding. It is **registered same-specimen spectral-difference mapping**: align the visible and UV405 images into one coordinate frame, build a preregistered nonsemantic difference/fluorescence field, and then let FractalGPT and uniform planners sample that fixed field under matched nulls.

## Claim ceiling

```text
FRACTAL_PATH != DISCOVERY
OCR_TOKEN != MESSAGE
FORMULA_LIKE != FORMULA
CODE_LIKE != ALGORITHM
CROSS_PLANNER_REPLICATION != MESSAGE
CROSS_MODALITY_REPLICATION != MESSAGE
IMAGE_SYMMETRY != MATERIAL_PROPERTY
NON_SPECIFIC_CONTROL_EFFECT_REJECTS_TARGET_SPECIFICITY
NO_POST_HOC_CIPHER_SEARCH
```

## Files

- `recovered/FractalGPT.py` — CI text mirror of the recovered user source
- `fractalgpt_adapter.py` — provenance checks, deterministic adapters and tiny-model trajectory runner
- `sources.json` — public source registry and planner/null configuration
- `fractal_crystal_probe.py` — multi-planner measurement + controls
- `../../tests/test_janus_cristal_fractalgpt.py` — deterministic/adversarial tests
- `../../.github/workflows/janus-cristal-fractalgpt.yml` — CI
- `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.1.json` — earlier gate/history
- `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.3.json` — current frozen v0.3 result
