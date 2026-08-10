# Janus Cristal × FractalGPT sandbox

This experiment uses **Janus Genesis only as an isolated creative-technology sandbox**. It does not alter the authoritative Genesis gameplay runtime.

## Recovered FractalGPT

The user's prior `FractalGPT(12).py` was recovered from the file library. Its original raw-file SHA-256 is:

`11e6c97ae7169a0fae4e0ad17f2fb7fb23b10265b04b4b057e3c968d6d0a3662`

A connector-serialized text mirror is stored as `recovered/FractalGPT.py`. The exact bytes executed by GitHub CI have SHA-256:

`1dfc5bb1dabcb256d569de30dbe4431f6901c8dcddbe15fb76634fd57d9146e8`

These identities are deliberately **not conflated**. The adapter verifies the mirror actually executed by CI while preserving the original-library hash as provenance.

The recovered source is a small autoregressive model whose state is approximately `[x, y, angle, scale, iteration]`. It contains native generators for a Koch curve, a Sierpinski triangle and fractal Brownian motion. The sandbox uses those components directly.

```text
FractalGPT / fractal planner = WHERE / AT WHAT SCALE TO LOOK
fixed detector/field         = WHAT IS MEASURED
matched nulls                = WHETHER THE EFFECT SURVIVES A NULL MODEL
admission gate               = WHETHER A RESULT MAY BE ESCALATED
```

The FractalGPT layer does **not** invent text, decode ciphers, or decide that a pattern is meaningful.

## v0.3 — semantic/null hardening

The v0.3 corpus contains the same petroleum-quartz specimen in visible and 405 nm UV, ordinary quartz, calcite and optical fluorite. Six content-independent planners are replayed against a 48 px block shuffle and a Fourier phase-scramble null.

The v0.3 run found no admitted word, formula, code or algorithm. It also falsified an earlier mirror-symmetry lead: against both nulls the planner counts were 1/6 for visible petroleum quartz, 3/6 for UV405, 1/6 for ordinary quartz, 3/6 for calcite and 4/6 for fluorite. The mirror effect was therefore rejected as quartz-specific.

Frozen result: `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.3.json`.

## v0.4 — registered same-specimen visible ↔ UV405 difference

The next gate was executed rather than left as a proposal.

The two 3614×2520 photographs of the **same petroleum-quartz specimen** were resized into one analysis frame and registered before any difference regions were defined. Edge-based ECC selected a near-identity affine transform:

```text
edge correlation before = 0.30700636
edge correlation after  = 0.32065283
overlap                 = 0.98156113
affine determinant      = 0.99916162
translation             = 6.832 px in resized frame
registration            = USABLE_IMAGE_REGISTRATION
```

A fixed nonsemantic difference field was then frozen as:

```text
0.40 × CLAHE luminance absolute difference
+ 0.40 × RGB chromaticity distance / sqrt(2)
+ 0.20 × normalized edge absolute difference
```

The field uses fixed channel scales, so it can be compared with a monotonic exposure-like self-control. The registered visible↔UV pair produced:

```text
luminance median       = 0.19215687
chromaticity median    = 0.28856058
edge median            = 0.05296119
composite median       = 0.23846602
composite p95          = 0.39166408
```

The visible-image gamma=0.72 self-control produced a composite median of `0.03822943`. The pair/control median ratio is therefore `6.23776028`.

This passes only the narrow image-level claim:

`REGISTERED_VISIBLE_UV_DIFFERENCE_FIELD_OBSERVED`

It does **not** identify chemistry from the image alone and does not establish a universal quartz property.

### What did FractalGPT add here?

Only after the difference field was frozen, the six planners sampled it. Each planner was compared with **2048 matched random trajectories** that preserve its scale sequence. Familywise α was fixed at 0.01.

No planner was enriched for either the composite difference or the 95th-percentile hotspot field:

```text
logistic baseline     p(composite)=0.99121523  p(hotspot)=0.98291850
uniform random        p(composite)=0.81649585  p(hotspot)=0.73304051
FractalGPT Koch       p(composite)=0.29575403  p(hotspot)=0.21669107
FractalGPT Sierpinski p(composite)=0.61981454  p(hotspot)=0.68423621
FractalGPT fBM        p(composite)=0.76720351  p(hotspot)=0.84675451
FractalGPT model      p(composite)=0.79648609  p(hotspot)=0.43777452
```

So the current result is intentionally two-part:

```text
PHYSICAL/IMAGE MODALITY DIFFERENCE = OBSERVED IN THIS MATCHED PAIR
FRACTALGPT PREFERENTIAL DISCOVERY  = NOT OBSERVED
SEMANTIC CONTENT                    = NOT TESTED IN THIS GATE / DISABLED BY DESIGN
```

This matters because a genuine UV-visible image difference does not automatically become evidence that a fractal model has discovered a hidden region or code.

Frozen result: `GENESIS-JANUS-CRISTAL-SPECTRAL-DIFFERENCE-v0.1.json`.

## Current next gate

`SPECTRAL_DIFFERENCE_CROSS_SPECIMEN_REPLICATION`

The frozen registration and difference-field definition should now be replayed without retuning on additional matched visible/UV images of the same quartz specimens. The goal is to separate inclusion/fluorescence effects from generic image, crystal and acquisition differences.

## Claim ceiling

```text
FRACTAL_PATH != DISCOVERY
OCR_TOKEN != MESSAGE
FORMULA_LIKE != FORMULA
CODE_LIKE != ALGORITHM
VISIBLE_UV_DIFFERENCE != HIDDEN_MESSAGE
FRACTALGPT_TRAJECTORY != MATERIAL_DISCOVERY
NO_PLANNER_ENRICHMENT != NO_PHYSICAL_MODALITY_EFFECT
SINGLE_SPECIMEN_DIFFERENCE != GENERAL_QUARTZ_PROPERTY
NO_POST_HOC_CIPHER_SEARCH
```

## Files

- `recovered/FractalGPT.py` — CI text mirror of the recovered user source
- `fractalgpt_adapter.py` — provenance checks, deterministic adapters and tiny-model trajectory runner
- `sources.json` — public source registry and planner/null configuration
- `fractal_crystal_probe.py` — multi-planner OCR/structure gate
- `spectral_difference_probe.py` — registered nonsemantic visible/UV difference gate
- `../../tests/test_janus_cristal_fractalgpt.py` — deterministic/adversarial tests
- `../../tests/test_janus_cristal_spectral_difference.py` — registration/difference-field tests
- `../../.github/workflows/janus-cristal-fractalgpt.yml` — CI
- `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.3.json` — v0.3 falsification result
- `GENESIS-JANUS-CRISTAL-SPECTRAL-DIFFERENCE-v0.1.json` — current spectral-difference result
