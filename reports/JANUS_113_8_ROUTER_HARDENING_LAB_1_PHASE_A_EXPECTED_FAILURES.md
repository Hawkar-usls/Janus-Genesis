# JANUS 113.8 Router Hardening Laboratory-1 — Phase A

## Expected-failure evidence

Phase A intentionally runs eleven defensive regression contracts against the unchanged pre-repair SIM-2 router.

A successful Phase-A workflow means:

```text
router unchanged relative to main
contract module compiled
all eleven contract names executed
unittest recorded FAILED
failure transcript uploaded
real network read = false
```

The workflow itself remains green only when it proves that the pre-repair implementation still fails the hardened contract. This preserves a machine-readable distinction between:

```text
TEST PROCESS FAILED UNEXPECTEDLY
```

and:

```text
EXPECTED PRE-REPAIR CONTRACT FAILURE REPRODUCED
```

No router correction is permitted until the Phase-A transcript is available for Python 3.11, 3.12, and 3.13.

## Contract map

| Contract | Frozen coordinate |
|---|---|
| A04 | provenance metadata must bind to URL |
| A05 | prediction digest must bind the complete input case |
| A06 | duplicate case identifiers remain accounted and typed |
| A07 | NFC/NFD collisions remain accounted and typed |
| A08 | duplicate JSON keys become typed rejections |
| A09 | malformed JSONL cannot abort the remaining ledger |
| A10 | resource bounds receive a typed resource terminal |
| A11 | final redirect location is revalidated |
| A12 | query and fragment ambiguity is rejected |
| A13 | dot-segment path ambiguity is rejected |
| A14 | strict mode requires a full immutable commit SHA |

## Boundary

This phase uses only the user-owned repository, local byte fixtures, temporary directories, and mocked response objects. It does not contact third-party systems, modify the router, satisfy SIM-3, or claim organizational independence.
