# JANUS 113.8 — Router Hardening Laboratory-1 Phase B

## Repair schema freeze

```text
ROLE = JANUS_LAB_AGENT
MODE = DEFENSIVE_SOFTWARE_VERIFICATION
PHASE = B_SCHEMA_FREEZE
TARGET = sim/janus_113_8_sim2_router.py
ROUTER_PATCH = ABSENT
RUNTIME_AUTHORITY = NONE
CURRENT_TERMINAL = ROUTER_HARDENING_LAB_1_REPAIR_SCHEMA_FROZEN_FOR_REVIEW
```

Phase A established the pre-repair evidence. Phase B begins by freezing the shape of the repair before any implementation change is permitted.

The frozen machine-readable contract is:

```text
protocol/janus_113_8_router_hardening_repair_schema_v1.json
```

It binds four output and input schemas:

```text
schemas/janus_113_8_router_case_v2.schema.json
schemas/janus_113_8_router_prediction_v2.schema.json
schemas/janus_113_8_router_ledger_entry_v2.schema.json
schemas/janus_113_8_router_manifest_v2.schema.json
```

## Contract-to-crack map

### A04 — provenance metadata not bound to URL

The decoded canonical URL tuple must equal:

```text
source_repository owner
source_repository repository
source_ref
source_path
```

A mismatch receives `REFUTED_PROVENANCE_MISMATCH` before any network read.

### A05 — prediction hash not bound to complete input

Every prediction binds both representations of its input:

```text
input_line_sha256 = SHA256(exact non-empty JSONL line bytes)
input_case_sha256 = SHA256(canonical parsed case)
prediction_body_sha256 = SHA256(canonical prediction body)
prediction_sha256 = SHA256(domain separator + all three hashes)
```

When parsing is impossible or non-unique, `input_case_sha256` is `null`, but the exact line hash still binds the rejected witness.

### A06 — duplicate case identifier

The first occurrence is evaluated normally. Every later raw duplicate receives `REFUTED_IDENTIFIER_COLLISION`; it is not overwritten, merged, or dropped.

### A07 — Unicode-normalized collision

Identity comparison uses Unicode NFC. Raw identifiers that normalize to the same value collide. The output preserves `normalized_case_id` so the collision is independently replayable.

### A08 — duplicate JSON keys

Duplicate keys must be detected at every object depth before object construction. The line receives:

```text
parse_status = DUPLICATE_JSON_KEY
decision_terminal = REFUTED_JSON_DUPLICATE_KEY
network read = false
```

### A09 — malformed JSONL aborts the ledger

Parsing becomes line-local. A malformed line receives one ordinal, one line hash, one typed prediction, and one ledger entry. Processing continues with the following line.

For every completed bounded run:

```text
input_nonempty_line_count
= prediction_count
= ledger_entry_count
= sum(parse_status_counts)
= sum(decision_counts)
```

### A10 — resource limit collapsed into unreachable OPEN

Resource exhaustion and transport failure are separated:

```text
source or line bound exceeded -> REFUTED_RESOURCE_LIMIT
transport failure -> OPEN_SOURCE_UNREACHABLE
corpus rejected before a completed run -> run terminal REFUTED_CORPUS_LIMIT
```

A corpus-limit refusal may not claim completed-input conservation.

### A11 — redirect target not revalidated

The final response URL must pass the same origin, canonicalization, and tuple-binding gate as the requested URL. A redirected target that changes the trusted tuple receives `SAFETY_BLOCK_REDIRECT_TARGET` before response bytes are trusted.

### A12 — query and fragment ambiguity

Canonical source URLs contain no userinfo, explicit port, query, or fragment. Ambiguous variants receive `REFUTED_NON_CANONICAL_URL` without a network read.

### A13 — path canonicalization

Each URL segment is decoded once, checked for dot segments, encoded separators, backslashes, NUL, invalid escapes, and empty segments, then re-encoded canonically. Failure of the exact round trip receives `REFUTED_NON_CANONICAL_URL`.

### A14 — release tag boundary

Two provenance modes are explicit:

```text
LEGACY_SIM2_RELEASE_TAG
STRICT_IMMUTABLE_COMMIT
```

Historical valid v1 cases enter through a compatibility adapter and retain the semantics of SIM-2. Future held-out and SIM-3 inputs use v2 strict mode and require a lowercase full 40-hex commit SHA. No earlier release tag is retroactively described as a commit.

## Historical evidence preservation

The Phase-A expected-failure module and transcripts remain historical evidence. They are not rewritten into passing tests.

Phase B will introduce a separate contract module:

```text
tests/test_janus_113_8_router_hardening_lab_1_phase_b.py
```

That module must map every coordinate A04–A14 to the frozen schema. It may clarify fixtures for v2, but it may not delete, weaken, invert, or bypass the original behavior being tested.

## Review gates before router repair

A reviewer should verify all of the following:

1. Every Phase-A finding has exactly one typed repair path.
2. Malformed, duplicated, rejected, OPEN, and safety-blocked lines remain visible in the ledger.
3. URL canonicalization occurs before every network read and after every redirect.
4. Legacy compatibility cannot silently enter strict mode.
5. Strict mode cannot silently accept a tag, branch, abbreviated SHA, or floating ref.
6. Output hashes bind the exact input line and the canonical parsed case.
7. Corpus refusal cannot masquerade as a completed conserved run.
8. Deterministic proofpacks contain no wall-clock fields.
9. No schema grants runtime authority or access to private systems.
10. SIM-3 organizational independence remains unsatisfied.

## Boundary

This freeze authorizes review, not implementation.

```text
ROUTER_PATCH_ALLOWED_NOW = FALSE
NEXT_ACTION = HUMAN_REVIEW_REPAIR_SCHEMA_BEFORE_ROUTER_PATCH
NEXT_TERMINAL_ON_ACCEPTANCE = ROUTER_HARDENING_LAB_1_REPAIR_SCHEMA_ACCEPTED
```

The laboratory repairs an internal verification instrument. It does not create an external verifier, establish organizational independence, or alter the historical SIM-2 admission record.
