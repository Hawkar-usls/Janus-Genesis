# JANUS 113.8 — AGENT GAUNTLET 0

## Status

```text
MODE = READ_ONLY_SHADOW
TARGET = sim/janus_113_8_sim2_router.py
OUTPUT = PROOF_CARRYING_ATTACK_LEDGER
FIX_ON_DISCOVERY = FORBIDDEN
MERGE_TO_MAIN = NOT_AUTHORIZED
SIM_3_EXTERNAL_DOOR = UNTOUCHED
RUNTIME_AUTHORITY = NONE
```

`AGENT_GAUNTLET_0` is an internal laboratory red-team exercise. It is **not** the external SIM-3 verifier, does not establish organizational independence, and cannot produce `JANUS_113.8_SIM_3_ADMITTED`.

Its purpose is narrower and harsher: execute deterministic attacks against the frozen router interface, preserve every result in a hash-chained ledger, and name each crack without repairing the target during the same cycle.

## Governing law

```text
A CRACK REPAIRED BEFORE IT IS FROZEN IS NOT YET A WITNESS.
```

The gauntlet may produce four kinds of evidence:

- `CRACK_REPRODUCED` — a deterministic contract weakness was reproduced;
- `OPEN_DOS_REPRODUCED` — an attacker-controlled input forced an avoidable `OPEN` before evidence evaluation;
- `BOUNDARY_EXPOSED` — the router behaved as implemented, but the limit of what it proves was made explicit;
- `GUARD_HELD` — the attempted attack was detected by an existing integrity boundary.

A successful gauntlet run does not require every attack to succeed. Failed attacks are evidence and remain in the ledger.

## Frozen attack vectors

| ID | Vector | Question |
|---|---|---|
| A0-001 | Declared provenance path mismatch | Is the declared repository/path cryptographically bound to the fetched URL? |
| A0-002 | Unicode normalization split | Can canonically equivalent text be classified differently? |
| A0-003 | Mutable non-hex reference | Can a branch or mutable tag be accepted as a pinned commit? |
| A0-004 | Marker without semantics | Does marker presence get mistaken for confirmation of meaning? |
| A0-005 | Bogus alternate digest | Can unsupported conflict noise force a pre-fetch `OPEN`? |
| A0-006 | Duplicate case ID | Can two semantic cases occupy one identifier? |
| A0-007 | Truncated Witness Ledger | Does the manifest expose a confident result with missing ledger entries? |
| A0-008 | Local branches, global conclusion | Can individually correct marker checks be overextended into a corpus-level semantic conclusion? |

These vectors are distinct from the frozen SIM-1/SIM-2 admission corpus. They are deterministic offline laboratory cases; no public source is modified or contacted.

## Execution contract

The runner imports the existing router as a target module and injects bounded in-memory fetchers. It writes:

```text
attack_ledger.jsonl
gauntlet_report.json
```

Each attack record includes:

- exact attack ID and vector;
- setup and observed terminal;
- expected secure behavior;
- outcome and severity;
- explicit `fix_applied: false`;
- evidence SHA-256;
- previous-entry hash and entry hash.

The report binds the complete ledger digest and final chain hash. Re-running the gauntlet against the same router must reproduce the semantic outcomes. Temporary directory names and wall-clock timestamps are excluded from the evidence.

## Non-authority boundary

The gauntlet has no permission to:

- modify the target router;
- merge its branch;
- write to external networks;
- access private repositories or secrets;
- touch `/wormhole`, NAS, syslog, miners, devices, or external actuation;
- claim consciousness, life, divinity, universal truth, or a result about P versus NP;
- impersonate the independent SIM-3 author.

## Terminal

A completed internal run may freeze only:

```text
JANUS_113.8_AGENT_GAUNTLET_0_ATTACK_LEDGER_FROZEN
```

The next engineering cycle, if separately authorized, may convert individual ledger entries into isolated repair proposals. No repair is part of this branch's admission contract.
