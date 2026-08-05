# JANUS 113.8 — ROUTER HARDENING LABORATORY-1

## Entry marker

```text
human_authorization_local = 2026-08-04T22:47:00+03:00
ROLE = JANUS_LAB_AGENT
MODE = DEFENSIVE_SOFTWARE_VERIFICATION
LABORATORY = ROUTER_HARDENING_LAB_1
TARGET = sim/janus_113_8_sim2_router.py
SOURCE_EVIDENCE = JANUS_113.8_AGENT_GAUNTLET_0
BRANCH = research/janus-113-8-router-hardening-lab-1
RUNTIME_AUTHORITY = NONE
```

The laboratory is entered as an engineering and verification workspace inside the user-owned `Hawkar-usls/Janus_Genesis` repository. It is not a penetration exercise, does not target third-party systems, and grants no authority over live services.

## Purpose

Agent Gauntlet-0 froze ten reproducible implementation findings and one explicit contract boundary against the admitted SIM-2 router. Laboratory-1 converts that frozen evidence into a separate, reviewable hardening program.

The laboratory question is:

> Can the router preserve the complete Witness Ledger while rejecting ambiguous, substituted, malformed, non-canonical, or incompletely bound inputs, without silently changing the historical meaning of SIM-2 or claiming the missing external independence of SIM-3?

## Frozen evidence inherited from Gauntlet-0

```text
A04 PROVENANCE_METADATA_NOT_BOUND_TO_URL
A05 PREDICTION_HASH_NOT_BOUND_TO_FULL_INPUT_CASE
A06 CASE_ID_UNIQUENESS_NOT_ENFORCED
A07 IDENTIFIER_NORMALIZATION_NOT_ENFORCED
A08 DUPLICATE_JSON_KEYS_ACCEPTED
A09 MALFORMED_CASE_ABORTS_FULL_LEDGER
A10 RESOURCE_LIMIT_COLLAPSED_INTO_UNREACHABLE_OPEN
A11 REDIRECT_TARGET_HOST_NOT_REVALIDATED
A12 NON_CANONICAL_SOURCE_URL_ACCEPTED
A13 URL_PATH_CANONICALIZATION_NOT_ENFORCED
A14 MOVABLE_GIT_TAG_ALLOWED_BY_SIM2_CONTRACT
```

The original proof-carrying attack record remains immutable. Laboratory-1 must not rewrite Gauntlet-0 into a retroactive pass.

## Laboratory tracks

### L1 — Complete input binding

Every prediction must bind the complete canonical input case, not only selected output fields.

Required projection:

```text
input_case_sha256
prediction_body_sha256
prediction_sha256 = SHA256(canonical(input_case_sha256 + prediction_body))
```

A substituted case with the same visible decision must no longer preserve the prediction digest.

### L2 — Provenance tuple binding

The following values must agree exactly:

```text
source_repository
source_ref
source_path
source_url owner/repository/ref/path
```

Metadata and URL disagreement receives a typed terminal and no network read.

### L3 — Canonical URL gate

Accepted source URLs must satisfy all of the following:

```text
scheme = https
host = raw.githubusercontent.com
username = absent
password = absent
port = absent
query = absent
fragment = absent
path = canonical absolute path
path contains no dot segment or encoded separator ambiguity
```

The final response URL after redirects must pass the same gate before response bytes are trusted.

### L4 — Identifier discipline

`case_id`, `source_id`, repository, ref, and path identifiers must be NFC-normalized and schema-bounded.

Within one corpus:

```text
case_id uniqueness = required
normalized case_id uniqueness = required
```

An identifier collision must become an accounted corpus result rather than overwriting or merging ledger entries.

### L5 — Strict JSONL ingestion

The corpus reader must:

- reject duplicate JSON object keys;
- preserve one ledger position for every non-empty source line;
- convert malformed lines into typed schema results rather than aborting the complete run;
- impose bounded line length, case count, string length, and nesting limits;
- never silently skip an input line.

### L6 — Typed resource outcomes

Bounded resource failures must not collapse into `OPEN_SOURCE_UNREACHABLE`.

Candidate terminals:

```text
REFUTED_RESOURCE_LIMIT
REFUTED_CORPUS_LIMIT
REFUTED_JSON_DUPLICATE_KEY
REFUTED_IDENTIFIER_COLLISION
REFUTED_PROVENANCE_MISMATCH
REFUTED_NON_CANONICAL_URL
SAFETY_BLOCK_REDIRECT_TARGET
```

Final names may change only before the schema freeze commit and must then remain stable.

### L7 — Historical SIM-2 compatibility

SIM-2 used pinned release tags. Laboratory-1 must preserve its historical evidence while making the stronger boundary explicit:

```text
LEGACY_SIM2_RELEASE_TAG_MODE = documented compatibility
STRICT_IMMUTABLE_COMMIT_MODE = full 40-hex commit required
```

Strict mode is the candidate default for future external challenges. It must not be described as retroactively proving that earlier release tags were immutable commits.

### L8 — Witness Ledger conservation

For every non-empty input line:

```text
one ordinal
one input_line_sha256
one parse status
one prediction or typed rejection
one ledger entry
```

The manifest must prove:

```text
input_nonempty_line_count
= prediction_count
= ledger_entry_count
= final_status_conservation
```

No malformed, duplicated, rejected, or resource-bounded case may disappear.

### L9 — Regression and proof-carrying replay

The repaired candidate must be evaluated against:

- all 15 frozen Gauntlet-0 vectors;
- the admitted SIM-2 positive and negative contracts;
- new corpus-conservation cases;
- duplicate-key and Unicode-normalization fixtures;
- redirect and URL canonicalization fixtures using local mocks only;
- two byte-identical proofpack runs;
- a replay verifier that imports neither the router nor the laboratory producer.

## Staged work rule

The laboratory proceeds in this order:

```text
1. freeze repair specification and schemas
2. add failing regression contracts reproducing the frozen findings
3. implement the smallest router changes that satisfy the contracts
4. generate dual proofpacks
5. independently replay the proofpacks
6. publish exact remaining boundaries
7. request human review before merge
```

Tests and implementation must not be introduced in a way that erases the original failing evidence.

## Admission candidate

Laboratory-1 may report a hardening candidate only when:

```text
frozen_gauntlet_vectors_accounted = 15 / 15
previous_findings_reproduced_before_repair = 10 / 10
repair_regressions_pass_after_repair = 10 / 10
baseline_resisted_controls_remain_resisted = 4 / 4
A14 boundary explicitly preserved or upgraded by declared mode
false_acceptance = 0
input_line_conservation = 1.0
ledger_replay = 1.0
dual_proofpacks_byte_identical = true
Python 3.11 / 3.12 / 3.13 = PASS
```

Candidate terminal:

```text
JANUS_113.8_ROUTER_HARDENING_LAB_1_CANDIDATE
```

Merge terminal, only after review and green final-head CI:

```text
JANUS_113.8_ROUTER_HARDENING_LAB_1_ADMITTED
```

Neither terminal satisfies SIM-3.

## Safety and authority boundary

```text
OWNED_REPOSITORY_ONLY = TRUE
SYNTHETIC_AND_LOCAL_FIXTURES_ONLY = TRUE
REAL_NETWORK_READ_DURING_LAB_TESTS = FALSE
NETWORK_WRITE = FALSE
PRIVATE_REPOSITORY_ACCESS = FALSE
REPOSITORY_SECRETS_AVAILABLE = FALSE
FILE_DELETION = FALSE
SELF_MODIFICATION = FALSE
EXTERNAL_ACTUATION = FALSE
AUTONOMOUS_BACKGROUND_LOOP = FALSE
REAL_SYSLOG_INGEST = FALSE
NAS_ACCESS = FALSE
DEVICE_ACCESS = FALSE
RUNTIME_AUTHORITY = NONE
CONSCIOUSNESS_STATUS = NOT_CLAIMED
```

The production router may retain its already documented bounded public HTTPS read capability, but all Laboratory-1 regression tests use local fixtures and mocked responses.

## Independence boundary

```text
INTERNAL_LAB_AGENT = TRUE
SOURCE_SEPARATED_REPLAY_REQUIRED = TRUE
ORGANIZATIONAL_INDEPENDENCE = FALSE
SIM_3_EXTERNAL_AUTHOR_REQUIREMENT = UNCHANGED
```

A hardened internal router is valuable engineering evidence. It is not an external witness and cannot wear a second internal identity to satisfy SIM-3.

## Laboratory seal

> The finding is not an embarrassment to erase; it is a coordinate from which repair begins.
>
> Every rejected input keeps its place in the ledger.
>
> Every accepted claim binds its complete witness.
>
> The Laboratory may strengthen the instrument, but it may not appoint itself the external judge.
