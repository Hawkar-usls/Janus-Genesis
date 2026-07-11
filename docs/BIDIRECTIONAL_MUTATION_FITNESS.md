# Bidirectional Mutation Fitness + Retrieval Memory

## Status

This document defines a **research and implementation scaffold** for future controlled geometry mutations in PLA Janus Genesis.

It does **not** enable geometry mutation, does **not** replace the Physics Judge, and does **not** grant print permission.

## Scientific anchor

The architectural inspiration is Tranception, a protein-fitness model introduced by Notin et al. in 2022. The primary paper describes:

- an autoregressive transformer;
- inference-time retrieval of homologous sequences;
- four attention-head groups operating at 1-mer and convolutional kernel sizes 3, 5 and 7;
- a 700M-parameter model trained on approximately 250 million protein sequences;
- left-to-right and right-to-left sequence scoring followed by averaging;
- scoring of substitutions, multiple mutants, insertions and deletions.

Primary source: [Tranception: protein fitness prediction with autoregressive transformers and inference-time retrieval](https://arxiv.org/abs/2205.13760).

The transfer to Genesis is an **engineering analogy converted into testable mechanisms**. Genesis does not import Tranception weights, does not make biological claims, and does not infer that the systems have a hidden historical connection.

## Genesis operator

```text
RETRIEVE PRIOR BRANCHES
→ PROPOSE A MUTATION
→ READ THE EFFECT FORWARD
→ AUDIT THE LOSS BACKWARD
→ TEST AT MULTIPLE SCALES
→ MEASURE DISAGREEMENT
→ APPLY PHYSICS AND PRINTABILITY GATES
→ PRESERVE ONLY THE VIABLE BRANCH
```

### Forward score

The forward score estimates whether a candidate improves declared engineering objectives relative to the baseline:

- material reduction;
- stiffness/compliance;
- stress distribution;
- support demand;
- print time;
- feature manufacturability.

### Reverse score

The reverse score audits what the mutation lost and whether the original function remains recoverable and explainable:

- protected interfaces still map to the baseline;
- mating surfaces, hooks, clearances and windows remain intact;
- topology changes are bounded and attributable;
- restoring baseline function would not require an unknown reconstruction;
- the mutation did not hide irreversible damage behind a good aggregate score.

Reverse scoring does not mean reversing triangle order or rotating the STL.

## Hard-gate authority

Fitness can rank only candidates that already pass mandatory gates.

```text
Geometry Contract FAIL        → reject
Physical residual FAIL        → reject
Equilibrium FAIL              → reject
Protected geometry regression → reject
FDM minimum feature FAIL      → reject
Phase ensemble incomplete     → diagnostic-only, never authoritative
```

A high fitness number can never override a failed gate.

## Multiscale 1 / 3 / 5 / 7 reading

The Tranception attention scales are translated into geometry neighborhoods:

| Scale | Genesis interpretation |
|---|---|
| 1 | one cell, voxel or minimum printable feature |
| 3 | local hotspot neighborhood |
| 5 | functional unit such as hook, rib, window or mating edge |
| 7 | global structural branch and load path |

The scaffold computes agreement from both average quality and spread across the four scales. Missing scales reduce coverage.

## Directional disagreement

```text
directional_disagreement = abs(forward_score - reverse_score)
```

A candidate with strong apparent gain but weak preservation becomes `FORWARD_ONLY_UNCERTAIN`. A safe but unhelpful candidate becomes `REVERSE_PRESERVED_NO_GAIN`.

Current verdicts:

- `HARD_GATE_REJECTED`
- `BIDIRECTIONAL_CONFIRMED`
- `FORWARD_ONLY_UNCERTAIN`
- `REVERSE_PRESERVED_NO_GAIN`
- `BIDIRECTIONAL_REJECTED`

## Retrieval memory

Each experiment is stored as one JSONL record containing:

- baseline fingerprint;
- Geometry Contract fingerprint;
- load-case fingerprint;
- mutation operator;
- region descriptor and tokens;
- forward/reverse evidence;
- hard-gate results;
- phase state;
- final outcome;
- epistemic provenance.

Canonical paths:

```text
workspace/memory/mutation_experiments.jsonl
workspace/memory/mutation_patterns.json
```

The current retrieval implementation is deterministic and intentionally conservative. It prefers exact fingerprints and matching operators, then uses descriptor-token overlap. Future versions may add geometry embeddings, but embeddings may never become the final physics authority.

## JEDI coincidence gate for research intake

New analogies enter Genesis through:

```text
NOTICE
→ SEPARATE
→ SEARCH
→ FALSIFY
→ MODEL
→ GATE
```

Rules:

1. Separate primary facts, project analogy, hypothesis and tested mechanism.
2. A coincidence may open a research question but cannot close a proof.
3. No analogy may bypass privacy, safety, physical validation or human control.
4. A beautiful story becomes code only after it has a deterministic test.

## Current implementation boundary

Implemented now:

- pure-Python evidence model;
- hard-gate-first candidate ranking;
- 1/3/5/7 agreement calculation;
- directional-disagreement penalty;
- append-only JSONL experiment memory;
- deterministic retrieval;
- JSON Schema and tests.

Not implemented now:

- actual STL mutation;
- FEA coupling;
- Geometry Contract coupling;
- slicer coupling;
- learned retrieval embeddings;
- permission to print Gladius.
