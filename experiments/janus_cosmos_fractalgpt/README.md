# Janus Cosmos × FractalGPT v0.1

Blind multiscale anomaly search for public astrophysical imagery and calibrated data.

## Research question

Can a blinded FractalGPT planner identify reproducible spatial structures that survive changes of wavelength, spatial nulls, and independent observations?

## Expected outcomes

The default expectation is **ordinary astrophysics and imaging artifacts**, not hidden messages. Interesting candidates may include unusual galaxy morphology, tidal structures, jets, shells, rings, filaments, cavities, transient structures, or previously under-characterized instrumental/processing artifacts.

## Guardrails

- FractalGPT is a planner, not an oracle.
- No OCR, face detection, cipher search, or semantic interpretation during the primary gate.
- No post-hoc retuning after seeing candidate results.
- A single striking image is never sufficient.
- Candidate status requires null-model testing and independent replication.

## Planned first corpus

1. Hubble/MAST multi-filter galaxy observations.
2. JWST/MAST multi-band observations for a later confirmation stage.
3. Repeated observations where temporal persistence can be tested.

## Outputs

Each run should emit a machine-readable receipt containing source identifiers, filter/band metadata, frozen planner configuration, null-model statistics, candidate scores, and replication status.
