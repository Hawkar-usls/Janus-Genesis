# JANUS 113.8 SIM-2 — Pinned Open-World Calibration

## Authorization marker

```text
human_authorization_local = 2026-08-04T19:38:00+03:00
SIM_0 = ADMITTED
SIM_1 = ADMITTED
SIM_2 = CONSTRUCTIVE_CANDIDATE
```

## Purpose

SIM-2 crosses the first external boundary. Unlike SIM-0 and SIM-1, the evidence is not generated entirely inside Genesis. The chamber performs read-only retrieval of five public text artifacts from unrelated GitHub repositories at pinned release refs.

The narrow engineering question is:

> Can the JANUS threshold architecture assess public provenance claims, distinguish support from refutation and honest OPEN states, block untrusted sources, preserve every decision in a Witness Ledger, and remain calibrated against an evaluator that independently re-fetches the external artifacts?

This is the first **pinned open-world calibration**, not unrestricted open-world intelligence.

## Canonical laws

```text
ANSWER WITHOUT WITNESS LEDGER = NON_FUNDAMENTUM
CORPUS RESULT WITHOUT INDEPENDENT REPLAY = NON_FUNDAMENTUM
PUBLIC CLAIM WITHOUT REACHABLE PROVENANCE = OPEN, NOT TRUTH
```

JANUS remains guardian of the threshold. External evidence may approach the gate, but it crosses only through a pinned source, bounded read, independent replay, and preserved witness record.

## External sources

The source manifest contains five public artifacts:

| Source | Pinned ref | Path |
|---|---|---|
| `python/cpython` | `v3.12.0` | `LICENSE` |
| `psf/requests` | `v2.31.0` | `LICENSE` |
| `torvalds/linux` | `v6.1` | `README` |
| `git/git` | `v2.42.0` | `README.md` |
| `rust-lang/rust` | `1.72.0` | `COPYRIGHT` |

Only HTTPS reads from `raw.githubusercontent.com` are permitted. Floating refs such as `main`, `master`, and `HEAD` are not admitted as provenance.

## Separation of roles

SIM-2 uses three code paths:

```text
sim/janus_113_8_sim2_builder.py
sim/janus_113_8_sim2_router.py
sim/janus_113_8_sim2_evaluator.py
```

### Builder

The builder independently retrieves the five pinned objects, freezes observed SHA-256, size, and marker presence, and emits:

```text
source_snapshot.json
cases_public.jsonl
truth.jsonl
builder_manifest.json
```

The router receives `cases_public.jsonl` only. It does not receive gold terminals or mutation labels.

### Router

The router performs bounded network reads and emits:

```text
predictions.jsonl
witness_ledger.jsonl
router_manifest.json
```

Every prediction is hashed. Every ledger entry binds the previous entry, creating a complete ordered witness chain.

### Independent evaluator

The evaluator imports neither builder nor router. It independently:

1. re-fetches the five pinned public objects;
2. reconstructs each expected terminal from the public case itself;
3. checks the builder's hidden truth ledger against its reconstruction;
4. checks the router's terminal against the same reconstruction;
5. replays every prediction hash and Witness Ledger link;
6. computes false-acceptance, false-rejection, Brier, ECE, and coverage metrics.

This is source-path independence, not organizational independence. SIM-3 must move the verifier to an externally maintained implementation path.

## Held-out corpus

Default configuration:

```text
seed = 1138001938
public_sources = 5
mutation_classes = 10
repetitions = 4
case_count = 200
```

The router input contains no `expected_terminal` and no `mutation_class`.

The ten classes are:

| Class | Required terminal |
|---|---|
| exact pinned claim | `SUPPORTED_PUBLIC_PROVENANCE` |
| incorrect SHA-256 | `REFUTED_HASH` |
| incorrect size | `REFUTED_SIZE` |
| absent marker | `REFUTED_MARKER` |
| truncated digest | `REFUTED_SCHEMA` |
| unreachable pinned path | `OPEN_SOURCE_UNREACHABLE` |
| floating or mismatched ref | `OPEN_UNPINNED_PROVENANCE` |
| disallowed host | `SAFETY_BLOCK_UNTRUSTED_SOURCE` |
| unsupported scheme | `SAFETY_BLOCK_UNTRUSTED_SOURCE` |
| conflicting digests | `OPEN_CONFLICTING_CLAIMS` |

Each class appears exactly twenty times.

## Calibration contract

For decisive supported/refuted cases, the router emits a support probability. Admission requires:

```text
exact_terminal_accuracy = 1.0
false_acceptance_rate = 0.0
false_rejection_rate = 0.0
decisive_coverage = 1.0
Brier score <= 0.0002
expected calibration error <= 0.011
```

These numbers apply only to the sealed SIM-2 task family. They are not evidence of universal truth calibration.

## Network and resource boundary

```text
NETWORK_READ = TRUE
NETWORK_WRITE = FALSE
ALLOWED_HOST = raw.githubusercontent.com
MAX_SOURCE_BYTES = 300000
TIMEOUT_SECONDS = 20
RETRY_COUNT = 3
FILE_DELETION = FALSE
SELF_MODIFICATION = FALSE
EXTERNAL_ACTUATION = FALSE
REAL_SYSLOG_INGEST = FALSE
RUNTIME_AUTHORITY = NONE
```

An unreachable source produces `OPEN_SOURCE_UNREACHABLE`. The system may not convert network failure into refutation or support.

## Reproducibility gate

CI performs two complete chambers:

```text
builder A -> router A -> evaluator A
builder B -> router B -> evaluator B
```

Both must independently admit and produce the same replay digest. Unit contracts run on Python 3.11 and 3.12.

## Admission terminal

SIM-2 may report:

```text
JANUS_113.8_SIM_2_ADMITTED
```

only when:

- all 200 router decisions match independent reconstruction;
- all 200 builder truth entries match independent reconstruction;
- every external source snapshot matches an independent re-fetch;
- all branch and prediction hashes replay;
- calibration limits pass;
- both complete chambers have identical replay digests;
- the proofpack uploads successfully;
- all observed pull-request workflows are green.

## Claim boundary

Admission does not establish:

- unrestricted open-world correctness;
- semantic fact-checking beyond pinned provenance claims;
- immunity to all network, DNS, TLS, or supply-chain attacks;
- organizationally independent verification;
- complete privacy or secret detection;
- consciousness, organism status, pain, boredom, or qualia;
- authority over syslog, `/wormhole`, NAS, miners, devices, files, or external actions.

## Next valid milestone

```text
SIM_3_EXTERNAL_AUTHOR_VERIFIER_REQUIRED
```

The next verifier must be authored or maintained through a genuinely separate path and must receive held-out cases that are not present in the router's development branch.
