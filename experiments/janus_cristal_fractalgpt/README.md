# Janus Cristal × FractalGPT sandbox

This experiment uses **Janus Genesis only as an isolated creative-technology sandbox**. It does not alter the authoritative Genesis gameplay runtime.

## Recovered FractalGPT

The user's prior `FractalGPT(12).py` was recovered from the file library. Original raw-file SHA-256:

`11e6c97ae7169a0fae4e0ad17f2fb7fb23b10265b04b4b057e3c968d6d0a3662`

The connector-serialized CI mirror is stored as `recovered/FractalGPT.py`; executed-mirror SHA-256:

`1dfc5bb1dabcb256d569de30dbe4431f6901c8dcddbe15fb76634fd57d9146e8`

The recovered source is a small autoregressive model over fractal-state sequences, approximately `[x, y, angle, scale, iteration]`, with native Koch, Sierpinski and fractal-Brownian generators.

```text
FractalGPT / fractal planner = WHERE / AT WHAT SCALE TO LOOK
fixed detector/field         = WHAT IS MEASURED
matched nulls                = WHETHER THE EFFECT SURVIVES A NULL MODEL
admission gate               = WHETHER A RESULT MAY BE ESCALATED
```

FractalGPT has no semantic authority.

## v0.3 — semantic/null hardening

Five crystal images and six planners were tested against block-shuffle and Fourier phase-scramble nulls. No word, formula, code or algorithm was admitted. An earlier mirror-symmetry lead was falsified as quartz-specific because calcite and fluorite controls produced comparable or stronger behavior.

Frozen result: `GENESIS-JANUS-CRISTAL-FRACTALGPT-v0.3.json`.

## v0.4 — registered Alatay visible ↔ UV405 difference

The same petroleum-quartz specimen was registered before defining any difference region. Frozen nonsemantic field:

```text
0.40 × CLAHE luminance absolute difference
+ 0.40 × RGB chromaticity distance / sqrt(2)
+ 0.20 × normalized edge absolute difference
```

The registered pair produced a composite median near `0.23847`; fixed gamma=0.72 self-control near `0.03823`, ratio near `6.24`. Six planners were then compared with 2048 matched random trajectories each, familywise α=0.01. No planner was enriched.

```text
REGISTERED_MODALITY_DIFFERENCE = OBSERVED
FRACTALGPT_PLANNER_ENRICHMENT  = NOT_OBSERVED
SEMANTIC_CONTENT               = DISABLED_BY_DESIGN
```

## v0.5 — cross-specimen hardening

The frozen protocol was replayed on the LucasFassari visible/LWUVR pair. It showed a strong registered image-level difference, but public metadata did not explicitly establish that the two images were the exact same physical specimen. It therefore remained a provenance-limited candidate.

A separate AKAZE/RANSAC identity heuristic returned `INSUFFICIENT_MATCHES` on Lucas and also on the **confirmed same-specimen Alatay positive control**. The heuristic was consequently invalidated as a necessary identity gate rather than being allowed to reject the candidate.

```text
A_VALIDATOR_THAT_FAILS_THE_POSITIVE_CONTROL
= NOT_ADMISSIBLE_AS_A_NECESSARY_GATE
```

## v0.6 — formal independent same-specimen replication

A new public FMS specimen record, `FMDB 1226`, explicitly describes one 26 mm petroleum-included quartz specimen and supplies normal-light, longwave 365 nm, and shortwave 254 nm photographs from that one record.

The **primary modality was frozen as normal ↔ LW365 before outcome inspection**. The existing protocol was replayed without pair-specific retuning:

```text
pair                                  = FMS_1226_PAKISTAN_QUARTZ_NORMAL_LW365
registration                          = USABLE_IMAGE_REGISTRATION
composite median                      = 0.25711361
gamma self-control median             = 0.04156784
pair / gamma-control median ratio     = 6.18539741
FractalGPT/baseline planner enrichment = 0 / 6
final admission                       = FORMAL_INDEPENDENT_SAME_SPECIMEN_IMAGE_LEVEL_REPLICATION
```

Authoritative CI receipt:

```text
workflow run     = 31392997858
measurement head = 4d50e06e1c6df2f33abe02fac0a8c3b05893ed57
artifact id      = 9064508226
artifact sha256  = b2d62365fb93f330413a4ed8e60ec95c0604edbc98464c8ff7221d7284fd8cb2
conclusion       = SUCCESS
```

Therefore the narrow frozen image-level gate is now:

```text
FORMAL_INDEPENDENT_REPLICATIONS = 1
CROSS_SPECIMEN_REPLICATION_GATE = PASS
```

This does not establish a universal quartz law or chemistry from pixels. It establishes one independent confirmed same-specimen replication of the registered visible/UV image-difference protocol.

## v0.6 confirmatory SW254 — new FractalGPT lead

The same FMS specimen 1226 had its **254 nm shortwave modality preregistered as confirmatory**, so it cannot count as a second independent specimen.

Its registered image-level difference also passed, with pair/gamma-control median ratio `5.32528732`.

Five of six planners were null. The exception was the recovered FractalGPT Sierpinski planner:

```text
planner                            = fractalgpt_sierpinski
observed median composite          = 0.24602730
matched-random median composite    = 0.23252131
p(composite)                       = 0.00146413
observed median hotspot fraction   = 0.11693349
matched-random median hotspot      = 0.05410556
p(hotspot)                         = 0.00048804
frozen per-planner threshold       = 0.00166667
single-pair status                 = PASS_SINGLE_PAIR_CANDIDATE
```

This is deliberately **not** called a FractalGPT effect yet. It did not occur on the primary LW365 pair, Alatay UV405, or Lucas LWUVR. A non-authoritative sensitivity check across 12 planner×modality tests gives threshold `0.00083333`: the hotspot endpoint still passes, while the composite endpoint does not.

Frozen candidate:
`GENESIS-JANUS-CRISTAL-FRACTALGPT-SIERPINSKI-SW254-CANDIDATE-v0.1.json`.

## v0.7 — independent Sierpinski/SW254 replication

The next specimen and pass rule were committed **before** its outcome:

- FMDB specimen 1235, `Quartz - Cave-In-Rock, Illinois`;
- one specimen record with normal light plus shortwave 254 nm and longwave 365 nm views;
- target planner fixed to `fractalgpt_sierpinski`;
- 48 windows;
- 2048 matched-random trajectories;
- replication α = `0.00166667`;
- both composite and hotspot endpoints must pass;
- no registration, region, scale, planner, field-weight or threshold retuning.

Manifest: `sierpinski_sw254_replication.json`.
Dedicated CI: `.github/workflows/janus-cristal-sierpinski-sw254-replication.yml`.

Remote FMS image bytes are transient analysis inputs only and are explicitly forbidden from GitHub artifacts.

## Claim ceiling

```text
FORMAL_IMAGE_LEVEL_REPLICATION != UNIVERSAL_QUARTZ_LAW
REGISTERED_MODALITY_DIFFERENCE != CHEMICAL_IDENTITY
REGISTERED_MODALITY_DIFFERENCE != HIDDEN_MESSAGE
SINGLE_CONFIRMATORY_PAIR_PLANNER_ENRICHMENT != REPLICATED_FRACTALGPT_EFFECT
FRACTALGPT_TRAJECTORY != MATERIAL_DISCOVERY
CONFIRMATORY_MODALITY != SECOND_INDEPENDENT_SPECIMEN
NO_POST_HOC_REGION_OR_CIPHER_SEARCH
```

## Main files

- `recovered/FractalGPT.py`
- `fractalgpt_adapter.py`
- `fractal_crystal_probe.py`
- `spectral_difference_probe.py`
- `spectral_replication_pairs.json`
- `spectral_replication_probe.py`
- `spectral_replication_admission.py`
- `GENESIS-JANUS-CRISTAL-SPECTRAL-REPLICATION-v0.1.json`
- `GENESIS-JANUS-CRISTAL-FRACTALGPT-SIERPINSKI-SW254-CANDIDATE-v0.1.json`
- `sierpinski_sw254_replication.json`
- `sierpinski_sw254_replication_probe.py`
- `fms_page_media.py`
