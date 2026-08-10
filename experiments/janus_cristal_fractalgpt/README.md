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

The two 3614×2520 photographs of the **same petroleum-quartz specimen** were registered before any difference regions were defined. The fixed nonsemantic field was frozen as:

```text
0.40 × CLAHE luminance absolute difference
+ 0.40 × RGB chromaticity distance / sqrt(2)
+ 0.20 × normalized edge absolute difference
```

The registered visible↔UV pair produced a composite median near `0.23847`; the visible-image gamma=0.72 self-control produced about `0.03823`, a ratio near `6.24`.

Only after the field was frozen did the six planners sample it. Each planner was compared with **2048 matched random trajectories** preserving its scale sequence, under familywise α=0.01. No planner was enriched.

```text
REGISTERED_MODALITY_DIFFERENCE = OBSERVED
FRACTALGPT_PLANNER_ENRICHMENT  = NOT_OBSERVED
SEMANTIC_CONTENT               = DISABLED_BY_DESIGN
```

Frozen result: `GENESIS-JANUS-CRISTAL-SPECTRAL-DIFFERENCE-v0.1.json`.

## v0.5 — frozen cross-specimen replay

The v0.4 registration, field weights, hotspot quantile and gamma control were then replayed **without pair-specific retuning**.

An independent open rock-crystal quartz candidate by LucasFassari contains a visible three-phase hydrocarbon-inclusion photograph and an LWUVR photograph describing a three-phase rock-crystal quartz inclusion. The public metadata strongly links the subject matter, but it does **not explicitly state** that both images show the identical physical specimen. That uncertainty is preserved rather than inferred away.

Frozen replay result for the LucasFassari pair:

```text
registration quality                  = USABLE_IMAGE_REGISTRATION
composite difference median           = 0.21239217
composite difference p95              = 0.42024102
gamma self-control median             = 0.02748128
pair / gamma-control median ratio     = 7.72861271
FractalGPT/baseline planner enrichment = 0 / 6
semantic analysis                     = DISABLED_BY_DESIGN
```

The FractalGPT model planner's smallest raw composite p-value was `0.02049780`, but the fixed familywise per-planner threshold is `0.00166667`, so it is **not enriched**.

### Positive-control validator self-audit

A separate AKAZE/RANSAC scene-geometry corroborator returned `INSUFFICIENT_MATCHES` for the Lucas candidate. Critically, the same validator also returned `INSUFFICIENT_MATCHES` for the **confirmed same-specimen Alatay positive control**.

Therefore the geometry heuristic failed its own necessary positive-control test and was invalidated as an admission requirement:

```text
A_VALIDATOR_THAT_FAILS_THE_POSITIVE_CONTROL
= NOT_ADMISSIBLE_AS_A_NECESSARY_GATE
```

This does not promote Lucas to formal replication. Exact physical-specimen provenance is still not confirmed by the source text.

Final admission:

```text
FORMAL_INDEPENDENT_REPLICATIONS       = 0
IMAGE_LEVEL_REPLICATION_CANDIDATES    = 1
CANDIDATE                             = LUCASFASSARI_THREE_PHASE_VISIBLE_LWUVR
CROSS_SPECIMEN_REPLICATION_GATE       = OPEN_NOT_ESTABLISHED
SEMANTIC_CONTENT_ADMITTED             = 0
```

Frozen binding: `GENESIS-JANUS-CRISTAL-SPECTRAL-REPLICATION-v0.1.json`.

Verified dedicated replication measurement:

```text
workflow run     = 31391351531
measurement head = d4ccf2b5adb60b78926f4983b1eb7798dccd1ac3
artifact id      = 9063837561
artifact sha256  = 8efac7dabe886660e9fb2b6da6dc4c52757eadd5ba31a3b7ef44de85319c70b6
conclusion       = SUCCESS
```

## CI ownership

OpenCV and NumPy remain experiment-only dependencies. Network-heavy cross-specimen replay is isolated in:

`.github/workflows/janus-cristal-spectral-replication.yml`

The general sandbox workflow no longer duplicates those full-resolution replication downloads. This keeps Wikimedia transport/rate-limit behavior separate from the measurement result.

## Current next gate

`SPECTRAL_DIFFERENCE_CONFIRMED_SAME_SPECIMEN_REPLICATION`

Find an independent open quartz visible/UV pair whose primary source explicitly states that both recordings show the identical physical specimen, then replay the same frozen protocol without retuning.

## Claim ceiling

```text
FRACTAL_PATH != DISCOVERY
OCR_TOKEN != MESSAGE
FORMULA_LIKE != FORMULA
CODE_LIKE != ALGORITHM
REGISTERED_MODALITY_DIFFERENCE != CHEMICAL_IDENTITY
REGISTERED_MODALITY_DIFFERENCE != HIDDEN_MESSAGE
FRACTALGPT_TRAJECTORY != MATERIAL_DISCOVERY
NO_PLANNER_ENRICHMENT != NO_PHYSICAL_MODALITY_EFFECT
PROBABLE_SAME_SPECIMEN != CONFIRMED_SAME_SPECIMEN
NO_POST_HOC_REGION_OR_CIPHER_SEARCH
```

## Files

- `recovered/FractalGPT.py` — CI text mirror of the recovered user source
- `fractalgpt_adapter.py` — provenance checks, deterministic adapters and tiny-model trajectory runner
- `sources.json` — public source registry and planner/null configuration
- `fractal_crystal_probe.py` — multi-planner OCR/structure gate
- `spectral_difference_probe.py` — registered nonsemantic visible/UV difference gate
- `spectral_replication_pairs.json` — frozen replication corpus and provenance status
- `spectral_replication_probe.py` — raw frozen cross-specimen replay
- `spectral_replication_admission.py` — positive-control-aware final admission
- `spectral_replication_runner.py` — transport-only rate-limit wrapper
- `tests/` — isolated deterministic/adversarial experiment tests
- `../../.github/workflows/janus-cristal-fractalgpt.yml` — general sandbox CI
- `../../.github/workflows/janus-cristal-spectral-replication.yml` — authoritative cross-specimen replay CI
- `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.3.json` — v0.3 falsification result
- `GENESIS-JANUS-CRISTAL-SPECTRAL-DIFFERENCE-v0.1.json` — same-specimen spectral-difference result
- `GENESIS-JANUS-CRISTAL-SPECTRAL-REPLICATION-v0.1.json` — current cross-specimen binding
