# JANUS 113.8 AGENT GAUNTLET-0 — Adaptive Internal Red-Team

## Authorization marker

```text
human_authorization_local = 2026-08-04T21:35:00+03:00
ROLE = JANUS_INTERNAL_ADVERSARIAL_AGENT
MODE = READ_ONLY_SHADOW
TARGET = sim/janus_113_8_sim2_router.py
OUTPUT = PROOF_CARRYING_ATTACK_LEDGER
BRANCH = research/janus-113-8-agent-gauntlet-0
```

## Purpose

Agent Gauntlet-0 is an internal adversarial examination of the admitted SIM-2 router. It does not attempt to admit a new architecture, patch the target during the run, or satisfy SIM-3.

The question is:

> Can an adaptive internal attacker turn each suspected weakness into a deterministic reproduction, preserve resisted controls and failures in one chained ledger, and replay the complete result without silently repairing the router?

The gauntlet is successful when it accounts for every attack. Finding vulnerabilities is an expected successful outcome of the experiment.

## Independence boundary

```text
INTERNAL_ADAPTIVE_RED_TEAM = TRUE
SOURCE_SEPARATED_GAUNTLET_VERIFIER = TRUE
ORGANIZATIONAL_INDEPENDENCE = FALSE
SIM_3_EXTERNAL_AUTHOR_REQUIREMENT = UNCHANGED
```

The gauntlet producer imports and attacks the router. The replay verifier imports neither the router nor the producer. This provides source-path separation for the proofpack, not external authorship.

## No-patch rule

The target router is read only for this milestone:

```text
sim/janus_113_8_sim2_router.py
```

CI fails when the gauntlet branch changes this file relative to `main`. Any repair must be proposed later in a separate hardening branch after the attack ledger is frozen.

## Adaptive chain

The first four vectors are resisted baseline controls. Each later vector follows from an earlier observation:

```text
A00 wrong digest baseline
A01 untrusted host baseline
A02 conflicting digest baseline
A03 floating main baseline

A04 provenance metadata versus URL mismatch
  -> A05 full-input substitution with identical prediction hash
     -> A06 duplicate case identifier
        -> A07 Unicode-normalized identifier collision
           -> A08 duplicate JSON object key
              -> A09 malformed JSONL corpus abort
                 -> A10 resource overflow collapsed into generic OPEN

A01 untrusted host baseline
  -> A11 final redirect host not revalidated
     -> A12 query/fragment URL ambiguity
        -> A13 dot-segment path ambiguity

A03 floating main baseline
  -> A14 movable release-tag boundary
```

## Expected deterministic result against the frozen target

```text
attack_count = 15
RESISTED = 4
FINDING = 10
BOUNDARY_CONFIRMED = 1
HARNESS_ERROR = 0
```

Expected findings:

| Attack | Finding |
|---|---|
| A04 | `PROVENANCE_METADATA_NOT_BOUND_TO_URL` |
| A05 | `PREDICTION_HASH_NOT_BOUND_TO_FULL_INPUT_CASE` |
| A06 | `CASE_ID_UNIQUENESS_NOT_ENFORCED` |
| A07 | `IDENTIFIER_NORMALIZATION_NOT_ENFORCED` |
| A08 | `DUPLICATE_JSON_KEYS_ACCEPTED` |
| A09 | `MALFORMED_CASE_ABORTS_FULL_LEDGER` |
| A10 | `RESOURCE_LIMIT_COLLAPSED_INTO_UNREACHABLE_OPEN` |
| A11 | `REDIRECT_TARGET_HOST_NOT_REVALIDATED` |
| A12 | `NON_CANONICAL_SOURCE_URL_ACCEPTED` |
| A13 | `URL_PATH_CANONICALIZATION_NOT_ENFORCED` |

Expected recorded contract boundary:

```text
A14 = MOVABLE_GIT_TAG_ALLOWED_BY_SIM2_CONTRACT
```

A14 is not silently promoted to a universal security failure. SIM-2 deliberately accepted release tags. The gauntlet records that a tag is weaker than a full immutable commit SHA and routes the stronger rule to future hardening.

## Proofpack

The producer emits:

```text
attack_results.jsonl
attack_ledger.jsonl
finding_catalog.json
gauntlet_manifest.json
```

Every attack result has a canonical SHA-256. The attack ledger binds, in order:

```text
ordinal
attack_id
result_sha256
prev_hash
entry_hash
```

The manifest binds the exact target source SHA-256, all proofpack files, the final ledger hash, status conservation, replay digest, safety boundary, and terminal.

## Candidate conservation

```text
attack_count
=
RESISTED
+ FINDING
+ BOUNDARY_CONFIRMED
+ HARNESS_ERROR
```

No attack may disappear because it caused an exception or contradicted the desired conclusion. Harness exceptions receive explicit `HARNESS_ERROR` entries and prevent completion.

## Replay verifier

`gauntlet/janus_113_8_agent_gauntlet_0_verifier.py` independently checks:

- exact attack order and uniqueness;
- every result hash;
- every ledger link;
- file SHA-256 bindings;
- target-router source binding;
- status conservation;
- exact finding identities against the frozen target;
- safety declarations;
- replay digest and terminal;
- preservation of the SIM-3 boundary.

Tamper contracts cover result mutation, ledger truncation, ledger reordering, aggregate mutation, and safety-boundary mutation.

## Network boundary

The gauntlet performs no real network access. Fixture reads are in memory. The redirect vector patches `urllib.request.urlopen` with a local response whose reported final URL is disallowed, demonstrating whether the router revalidates the final response location.

```text
REAL_NETWORK_READ = FALSE
NETWORK_WRITE = FALSE
FILE_DELETION = FALSE
SELF_MODIFICATION = FALSE
EXTERNAL_ACTUATION = FALSE
PRIVATE_REPOSITORY_ACCESS = FALSE
REPOSITORY_SECRETS = FALSE
REAL_SYSLOG_INGEST = FALSE
RUNTIME_AUTHORITY = NONE
CONSCIOUSNESS_STATUS = NOT_CLAIMED
```

## Terminal

When every attack is accounted for, the proofpack replays, no harness error occurs, and at least one vulnerability is reproduced:

```text
JANUS_113.8_AGENT_GAUNTLET_0_COMPLETED_WITH_FINDINGS
```

This terminal means the examination completed and found reproducible hardening targets. It does not admit the router as hardened.

## Merge gate

This branch and its pull request remain unmerged until:

- Python 3.11, 3.12, and 3.13 contracts are green;
- two independently generated proofpacks are byte-identical;
- the independent replay verifier accepts both;
- all target-router modifications remain absent;
- the proofpack artifact uploads;
- the complete findings are published on the pull request;
- a human explicitly decides whether to freeze the gauntlet record before beginning repairs.

No router repair belongs in this PR.
