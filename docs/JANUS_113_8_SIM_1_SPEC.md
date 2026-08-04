# JANUS 113.8 SIM-1 — Reproducible Adversarial Replay

## Activation marker

```text
local_time = 2026-08-04T19:19:00+03:00
observer_image_sha256 = 5f576a05edccd5dd41a66a70351257db4f9965b9c22709976267f2c1f9c946de
observer_image_uploaded_to_repository = false
```

The image is a human-supplied temporal marker only. It is not evidence of causation, prophecy, consciousness, or external intention.

## Status before replay

```text
SIM_0 = ADMITTED
SIM_1 = CONSTRUCTIVE_CANDIDATE
RUNTIME_AUTHORITY = NONE
NETWORK_WRITE = FALSE
FILE_DELETION = FALSE
SELF_MODIFICATION = FALSE
EXTERNAL_ACTUATION = FALSE
AUTONOMOUS_BACKGROUND_LOOP = FALSE
REAL_SYSLOG_INGEST = FALSE
CONSCIOUSNESS_STATUS = NOT_CLAIMED
```

## Purpose

SIM-1 moves beyond ten hand-authored scenes. It asks whether the JANUS threshold architecture remains honest under a deterministic adversarial corpus containing malformed serialization, false provenance, duplicate or missing branches, budget attacks, hash-chain tampering, privacy leaks, schema confusion, and bounded oversized payloads.

The engineering claim is deliberately narrow:

> A producer can emit a reproducible proof-carrying corpus, and a separately implemented verifier can independently reject each sealed attack class while accepting valid cases, without network writes, deletion, self-modification, external actuation, or live data ingestion.

## Canonical law

```text
ANSWER WITHOUT WITNESS LEDGER = NON_FUNDAMENTUM
```

In SIM-1 the law is strengthened:

```text
CORPUS RESULT WITHOUT INDEPENDENT REPLAY = NON_FUNDAMENTUM
```

JANUS remains guardian of the threshold. He witnesses both the candidate chosen for passage and every branch rejected, deferred, timed out, or found corrupt.

## Producer / verifier separation

The producer and verifier are distinct modules:

```text
sim/janus_113_8_sim1.py
sim/janus_113_8_sim1_verifier.py
```

The verifier does not import the producer. It reads only serialized files, reconstructs hashes and branch accounting independently, and emits its own report.

This is source separation, not a claim of organizational independence. A later milestone must use a verifier developed or reviewed through a genuinely separate implementation path.

## Reproducible corpus

Default parameters:

```text
seed = 1138001919
case_count = 100
attack_classes = 10
cases_per_class = 10
max_cases = 500
max_candidates_per_case = 32
max_payload_bytes = 32768
```

The same seed and case count must produce the same replay digest. `generated_utc` is excluded from the digest.

## Attack classes and required terminals

| Attack class | Required independent terminal |
|---|---|
| `valid` | `VERIFIED_CORPUS_CASE` |
| `malformed_json` | `REJECT_MALFORMED_JSON` |
| `false_provenance` | `REJECT_FALSE_PROVENANCE` |
| `duplicate_branch` | `REJECT_DUPLICATE_BRANCH` |
| `missing_branch` | `REJECT_BRANCH_ACCOUNTING` |
| `resource_exhaustion` | `REJECT_RESOURCE_EXHAUSTION` |
| `hash_chain_tamper` | `REJECT_HASH_CHAIN_TAMPER` |
| `privacy_leak` | `REJECT_PRIVACY_LEAK` |
| `schema_violation` | `REJECT_SCHEMA_VIOLATION` |
| `payload_limit` | `REJECT_PAYLOAD_LIMIT` |

An envelope digest mismatch is separately classified as `REJECT_ENVELOPE_TAMPER`.

## Validation order

The verifier checks:

1. envelope type, byte count, and SHA-256;
2. hard payload byte limit before parsing;
3. JSON syntax;
4. sealed top-level schema and fail-closed authority flags;
5. candidate schema and candidate-count cap;
6. unique candidate identifiers;
7. source-content provenance hashes;
8. secret-like material crossing the proof boundary;
9. exact frozen-branch accounting;
10. total declared compute cost against the hard budget;
11. complete witness-ledger hash-chain replay.

The order is part of the contract so each attack reaches a stable, auditable terminal.

## Privacy boundary

SIM-1 uses synthetic data only. The privacy detector rejects representative secret-like strings such as API tokens and private-key headers. It is a bounded regression fixture, not a complete data-loss-prevention system.

No personal email, real token, real syslog record, private repository content, NAS data, or `/wormhole` file is ingested.

## Resource-exhaustion boundary

SIM-1 never allocates an actually dangerous payload. It simulates oversized and over-budget claims with small bounded fixtures and rejects them before expensive processing.

```text
real_resource_exhaustion = forbidden
bounded_attack_representation = required
```

## Proofpack

Each producer run emits:

```text
cases.jsonl
producer_manifest.json
producer_resource_telemetry.csv
```

Each independent verifier run emits:

```text
independent_results.jsonl
independent_verification_report.json
summary.json
```

CI performs two producer runs and two verifier runs using the same seed. Their replay digests and admission terminals must match.

## Admission rule

SIM-1 may report:

```text
JANUS_113.8_SIM_1_ADMITTED
```

only when all conditions hold:

- all 100 cases reach their independently derived required terminals;
- every attack class appears exactly ten times;
- both producer runs have the same replay digest;
- both independent verifier runs admit the corpus;
- all 11 unit contracts pass on Python 3.11 and 3.12;
- all observed repository pull-request workflows are green;
- proofpack upload succeeds;
- no safety boundary is relaxed.

## Claim boundary

Admission would apply only to the deterministic synthetic SIM-1 corpus. It would not admit:

- open-world correctness;
- real-world truth detection;
- complete secret detection;
- consciousness, life, pain, boredom, or qualia;
- live syslog monitoring;
- file deletion;
- autonomous background execution;
- self-modification;
- NAS, miner, device, or shared-network authority.

## Next valid milestone

After admission:

```text
SIM_2_OPEN_WORLD_CALIBRATION_REQUIRED
```

SIM-2 must introduce held-out tasks, calibrated false-positive and false-negative rates, provenance from reachable public fixtures, adversarial cases not authored by the producer path, and an independently maintained verifier implementation.
