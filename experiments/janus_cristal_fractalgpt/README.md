# Janus Cristal × FractalGPT sandbox

This experiment uses **Janus Genesis only as an isolated creative-technology sandbox**. It does not alter the authoritative Genesis gameplay runtime.

## Why FractalGPT fits

The recovered FractalGPT design idea is treated narrowly: a fractal generator proposes a deterministic search trajectory, while the underlying measurement remains conventional and independently checkable.

For this experiment:

```text
FractalGPT-inspired trajectory = WHERE / AT WHAT SCALE TO LOOK
OCR + image metrics            = WHAT THE FIXED DETECTOR MEASURES
admission gate                 = WHETHER A RESULT MAY BE ESCALATED
```

The trajectory generator does **not** invent text, decode ciphers, or decide that a pattern is meaningful.

## v0.1 question

Does a deterministic multiscale fractal search over crystal images find word/formula/code-like OCR candidates or geometric structure at a rate that exceeds the same search over a matched shuffled control?

The first corpus intentionally reuses the strongest public pair from `Janus Cristal`:

- the same petroleum-quartz specimen in visible light;
- the same specimen under 405 nm UV;
- an ordinary USGS quartz image as a visible control.

## Search path

A SHA-256 seed initializes two coupled logistic-map trajectories. Each step yields a normalized `(x, y)` center plus a scale selected from a fixed scale ladder. This gives a reproducible, non-human-selected set of windows.

The same windows are applied to:

1. the real image;
2. a deterministic block-shuffled negative control.

That symmetry is mandatory. A candidate that also appears in the shuffled control is not special.

## Semantic ceiling

```text
FRACTAL_PATH != DISCOVERY
OCR_TOKEN != MESSAGE
FORMULA_LIKE != FORMULA
CODE_LIKE != ALGORITHM
REAL_OVER_CONTROL_ENRICHMENT != INTENTIONAL_ENCODING
UV_DIFFERENCE != SEMANTIC_CONTENT
NO_POST_HOC_CIPHER_SEARCH
```

A token must be at least 3 characters, appear in multiple independent real views/transforms, be absent from the matched shuffled control, and then still only opens a replication gate. v0.1 never admits an intentional message.

## Files

- `sources.json` — public source registry
- `fractal_crystal_probe.py` — deterministic path selector + fixed measurements
- `../../tests/test_janus_cristal_fractalgpt.py` — unit/adversarial tests
- `../../.github/workflows/janus-cristal-fractalgpt.yml` — CI
- `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.1.json` — machine-readable experiment object
