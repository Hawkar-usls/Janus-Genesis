# Validation and safety

## No invisible claims

Janus reports a `claim_level` for every candidate. The foundation pipeline is limited to mesh repair and orientation. It must not claim increased strength.

## Why PLA needs calibration

FDM parts are anisotropic. Strength depends on layer direction, temperature, speed, wall count, moisture, pigment and spool quality. PLA can also creep under sustained load and soften in warm environments.

## Required gates for a future optimized candidate

1. Source mesh preserved and hashed.
2. Protected regions unchanged within tolerance.
3. Mesh is manifold or solver limitations are explicit.
4. FEA converged for every declared load case.
5. Maximum displacement is below the contract limit.
6. Safety factor is above the contract limit.
7. Minimum printable feature is respected.
8. Slicer accepts the candidate.
9. Mass and print-time estimates are recorded.
10. Physical test result is attached before any real-world strength claim.

## Forbidden use without professional validation

Do not rely on generated parts for life safety, vehicle control, lifting people, climbing, pressure vessels, weapons, medical implants or mains electrical protection.

## Original preservation

The input model is never overwritten. Every transformation creates a new file and a machine-readable report.
