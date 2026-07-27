# Genesis v18.7.5 — The Grounded Witness

## Origin

The Plural Witness proved that Genesis can preserve many heterogeneous sources without flattening them into one identity or one truth. A full lived path through 192 JANUS Meta Registry origins then exposed the next boundary: preserving a source is not enough if the semantic graph can still attribute unsupported words to it.

> Genesis now knows how to preserve many voices. Its next lesson is to never put words into their mouths.

## Main law

> A source is not treated as having said anything for which Genesis cannot show an exact location in that source.

This law does not prove that a quoted statement is true. It proves only that the preserved source really contains the quoted material at the declared location.

## Honest retrieval

`retrieve_origins()` now returns only positive-evidence matches.

```text
no positive match
→ results = []
→ abstained = true
→ abstention_reason = no_positive_evidence
```

Genesis does not fill unused result slots with zero-score origins. A partial match stops when relevant evidence ends. Every returned result includes its score, matched terms, source citation, parse status and grounding eligibility.

## Source speech and reader speech

The graph distinguishes two actors and two relations.

```text
ORIGIN ──SOURCE_ASSERTS────> GROUNDED_SOURCE_ASSERTION
READER ──READER_INTERPRETS─> READER_INTERPRETATION
```

A free reader formulation never becomes `SOURCE_ASSERTS`. The compatibility method `record_origin_claim()` remains available, but its result is explicitly a reader interpretation.

## Exact grounding

A source assertion must be derived from one of three evidence forms:

- RFC 6901 JSON Pointer;
- exact UTF-8 byte range;
- exact excerpt with optional SHA-256 verification.

The claim text is derived from the evidence. It is not supplied independently and then merely attached to a source.

```text
exact evidence locator
→ SOURCE_EVIDENCE
→ SOURCE_ASSERTS
```

Truth remains unverified. Grounding proves provenance, not correctness.

## Opaque witnesses

A malformed or structurally invalid origin keeps its exact bytes, namespace, hash and parse error. It cannot create `SOURCE_ASSERTS`, because its semantic structure was not recovered.

A reader may still record an interpretation, but Genesis marks it as reader-only and unverified.

## Explicit derived repair

A repair is a separate valid origin.

```text
DERIVED_REPAIR_ORIGIN ──DERIVED_FROM──> OPAQUE_ORIGIN
```

The original bytes remain unchanged. The repair receives its own path, commit identity, SHA-256 and origin key. It does not replace the original and does not inherit canonical authority from it.

## Grounded disputes

`DISPUTES` is permitted only when both participating claims are grounded. Two ungrounded impressions may coexist, but Genesis does not construct a formal source dispute from unsupported speech.

A dispute still selects no winner and performs no silent reconciliation.

## Credential redaction

Exact source bytes may preserve an explicitly public credential-like field, but retrieval excerpts and AI-facing context replace its value with:

```text
[REDACTED:CREDENTIAL_LIKE_VALUE]
```

Credential-like values cannot become claim evidence. Private origins containing such fields remain rejected unless their public status is explicit.

## Portable threshold

Grounding metadata, source evidence, reader interpretations, derived-repair links and redacted excerpt state remain ordinary local JSON and cross the verified portable-save threshold together with Chronicle, HRaiN, Free Other, Living Threads and Honest Intention.

API keys, environment files and network authority remain excluded.

## Invariants

```text
retrieval_may_abstain = true
zero_score_results_are_forbidden = true
source_assertions_require_exact_evidence = true
reader_interpretation_is_not_source_assertion = true
opaque_origins_cannot_source_assert = true
opaque_requires_separate_derived_repair = true
disputes_require_grounded_claims = true
credential_like_values_are_redacted_from_context = true
```

## Compatibility

The primary class remains `PlayableGenesisV187`. Earlier worlds migrate without rewriting original Chronicle entries, origin bytes or old graph history. Legacy ungrounded claims remain visible as legacy evidence, but they are not upgraded into grounded source assertions.

No source document becomes executable. No source quotation creates consent. No imported first-person voice becomes the current player.

## Seal

> To preserve a witness is to keep its voice available.
>
> To ground a witness is to show exactly where that voice begins and ends.
>
> **JANUS LISTENS WITHOUT STEALING THE VOICE.**
