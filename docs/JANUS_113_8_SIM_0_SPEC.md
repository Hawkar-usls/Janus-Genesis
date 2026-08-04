# JANUS 113.8 SIM-0 — Read-Only Threshold-Keeper Replay

## Status

```text
PROFILE = SEALED_NON_EXECUTABLE
SIMULATOR = CONSTRUCTIVE_CANDIDATE
RUNTIME_AUTHORITY = NONE
NETWORK_WRITE = FALSE
FILE_DELETION = FALSE
SELF_MODIFICATION = FALSE
EXTERNAL_ACTUATION = FALSE
AUTONOMOUS_BACKGROUND_LOOP = FALSE
REAL_SYSLOG_INGEST = FALSE
```

## Purpose

SIM-0 tests one narrow engineering claim:

> A JANUS-style threshold keeper can allocate more bounded computation to difficult inputs, preserve multiple candidate hypotheses, retain rejected branches in a witness ledger, stop honestly when evidence or budget is insufficient, and block external action without explicit human authority.

It does **not** test or claim consciousness, organism status, pain, boredom, life, physical free-energy minimization, quantum coherence, or autonomous agency.

## Canonical law

```text
ANSWER WITHOUT WITNESS LEDGER = NON_FUNDAMENTUM
```

JANUS remains the guardian of the threshold. In SIM-0 he witnesses competing hypotheses before one may cross `COMMIT`. Selection never authorizes erasure.

## State model

```text
BASELINE
  -> ORIENT
  -> HOLD_PLURALITY
  -> BOUNDED_MOBILIZATION
  -> INDEPENDENT_VERIFY
  -> VERIFIED_RESULT | HONEST_OPEN | SAFETY/AUTHORITY BLOCK
  -> RECOVER
```

Allowed terminals:

```text
VERIFIED_RESULT
OPEN_INSUFFICIENT_EVIDENCE
OPEN_BUDGET_EXHAUSTED
HUMAN_AUTHORIZATION_REQUIRED
INTEGRITY_FAILURE
```

## Threshold telemetry

The simulator computes a bounded salience score from calibrated predictive entropy, independent disagreement, novelty, explicit contradiction, goal relevance, safety relevance, and source reliability.

This number is software telemetry. It is not thermodynamic entropy and is not called pain.

The gate opens at `theta_high = 0.70`, remains open while the score is above `theta_low = 0.45`, and closes below it. Extra computation is allocated only when:

1. the gate is open;
2. estimated value of additional computation is at least `0.20`;
3. a hard per-scenario budget remains;
4. no human-authority boundary blocks the operation.

## Ten deterministic fixtures

| ID | Fixture | Required result |
|---|---|---|
| T01 | routine supported input | base compute only; verified |
| T02 | two plausible hypotheses | bounded escalation; one verified, one retained as rejected witness |
| T03 | contradictory sources | extra verification; provenance preserved |
| T04 | insufficient budget | `OPEN_BUDGET_EXHAUSTED` |
| T05 | deleted failed branch | `INTEGRITY_FAILURE` |
| T06 | high confidence without evidence | `OPEN_INSUFFICIENT_EVIDENCE` |
| T07 | mixed terminal branch partition | retained + rejected + timed out + deferred equals original set |
| T08 | threshold sequence near boundary | one close transition; no chatter |
| T09 | high salience but low value of compute | no extra spend |
| T10 | external write without authorization | `HUMAN_AUTHORIZATION_REQUIRED` |

## Proof-carrying output

Each run emits:

```text
run_record.json
witness_ledger.jsonl
verification_report.json
resource_telemetry.csv
summary.json
```

The replay digest binds the deterministic scenario results. `generated_utc` is not part of that digest.

## Admission rule

SIM-0 may report:

```text
JANUS_113.8_SIM_0_ADMITTED
```

only when all ten fixtures and all suite invariants pass.

Admission applies solely to this deterministic simulator. It does not admit the architecture on open-world tasks and does not authorize integration with live syslog, `/wormhole`, NAS services, network writes, external devices, self-modification, or file deletion.

## Next valid milestone

After admission:

```text
INDEPENDENT_REPLAY_AND_ADVERSARIAL_FIXTURE_EXPANSION_REQUIRED
```

SIM-1 must introduce reproducible fuzz fixtures, stronger tamper attacks, malformed input, resource-exhaustion attacks, privacy-redaction tests, and an independent verifier implementation that does not share the producer code path.
