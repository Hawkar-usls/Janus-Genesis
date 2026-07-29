# Genesis v18.7.10 — Counterfactual Mirror Integrity

## Decision

Counterfactual Life Mirror uses a **fully isolated temporary data directory and a separate `PlayableGenesisV187` instance**.

It does not use a mutable in-memory branch shared with canonical stores.

```text
CANONICAL DATA ROOT
  ├── Chronicle JSONL
  ├── HRaiN-compatible graph sidecar
  ├── Free Other state
  ├── sandbox state
  └── I0 audit bookkeeping

          byte snapshot + manifest verification
                         │
                         ▼
UNREALIZED_MIRROR DATA ROOT
  ├── independent Chronicle JSONL
  ├── independent HRaiN-compatible graph sidecar
  ├── independent Free Other state
  ├── independent sandbox state
  └── unrealized_mirror_manifest.json
```

The current canonical runtime is JSON/JSONL-sidecar based, not SQLite based. Therefore the isolation unit is the complete data directory rather than a single database file.

## Why not a shared in-memory branch

A shared object graph would make accidental aliasing possible:

- one mutable dictionary could still be referenced by canon and mirror;
- one Chronicle writer could append to the wrong file handle;
- one HRaiN adapter could preserve a canonical connection inside a copied object;
- a crash could leave no inspectable branch manifest;
- a branch could appear isolated in tests while sharing a hidden singleton, cache or connection pool.

The separate runtime/data-root boundary is slower but auditable. Files can be hashed, compared and destroyed without relying on Python object identity.

## Strengthened invariants

The integrity layer adds these gates:

1. **Disjoint roots.** A mirror root may not equal, contain or be contained by the canonical data root.
2. **Empty destination.** A supplied mirror directory must be empty.
3. **No symlinks.** Audit state may not escape either root through a symbolic link.
4. **Byte-verified fork.** Canonical protected files are hashed before the fork and compared with the copied snapshot before the mirror runtime opens.
5. **Running-audit lease.** A mirror can be created only for a `RUNNING` lived audit and is registered as active.
6. **Counterfactual-only interventions.** Controlled variables such as relationship trust `0` or `95` can be set only in a branch carrying a valid `UNREALIZED_MIRROR` manifest.
7. **Relationship life only.** The trust probe changes the authoritative `relationship_bond` / `relationship_score` projection and its legacy trust view, but does not mutate `actor_life_v1810`.
8. **Numeric metric gate.** Canon receives only flat, finite numeric metrics. Raw dialogue, nested objects and arbitrary text are rejected.
9. **Canon freeze check.** At archive time the protected canonical snapshot must still match its fork hash. Any change produces `FAIL_CLOSED_CANONICAL_CONTAMINATION` and the branch is not promoted.
10. **Destructive cleanup.** A successful archive destroys the working mirror directory by default and records whether removal succeeded.
11. **No automatic canon mutation.** Butterfly Witness may emit evidence status but never applies a change.

The I0 audit bookkeeping file is excluded from the protected-world hash because opening, archiving and reporting a mirror must update that ledger. Chronicle, HRaiN, Free Other, player and sandbox state remain protected.

## Archive shape

Canon retains only a privacy-safe record:

```text
classification = UNREALIZED_MIRROR
canonical_mutation_allowed = false
canonical_snapshot_sha256
canonical_snapshot_sha256_at_archive
mirror_file_manifest_sha256
metric_contract = flat_finite_numeric_v1
metrics_sha256
selected numeric metrics
raw_dialogue_in_canonical_archive = false
raw_branch_persisted_in_canon = false
working_copy_removed
```

The complete branch is not merged into Chronicle or HRaiN.

## Butterfly Witness v2

A metric is stable only when every repeated branch differs from the control and every delta points in the same direction.

```text
no mirror                         -> COUNTERFACTUAL_REQUIRED
one window                        -> REPLAY_SAME_SEED
no directionally stable metric    -> ANECDOTE_ONLY
repeated stable metric            -> PROMOTE_TO_REGRESSION
2+ stable metrics / 3+ windows    -> CANON_CHANGE_CANDIDATE
```

`CANON_CHANGE_CANDIDATE` is still not canon. It must pass a separate Canon Birth Gate.

## Same-seed relationship-trust A/B probe

The century audit forks six branches from one canonical snapshot:

```text
3 windows × relationship trust=0
3 windows × relationship trust=95
same world seed
same world turn
same Free Other
same action fingerprint
same Benevolent Sovereign consent law
```

The intervention is recorded only inside each mirror. Genesis selects one action whose deterministic `benevolent-consent` gate lies between the actual low and high acceptance thresholds. The final audit then requires three low-trust non-acceptances, three high-trust acceptances and a `PROMOTE_TO_REGRESSION` Butterfly verdict. This demonstrates implementation sensitivity; it is not presented as a naturalistic or universal law of relationships.

## Future SQLite adapter

When Genesis gains a canonical SQLite adapter, the same architecture remains:

- create a separate temporary SQLite file per mirror using SQLite backup/snapshot semantics;
- open it with a separate connection and branch-scoped repository object;
- never reuse the canonical connection, transaction, WAL or `ATTACH` target for branch writes;
- copy any HRaiN/Chronicle sidecars into the same isolated branch root;
- hash the source snapshot and branch database plus sidecars;
- archive only selected metrics and manifests;
- close the branch connection and remove the temporary database, WAL and SHM files.

An in-memory SQLite database may be used for unit tests behind the same storage interface, but it is not the default proof mode because a filesystem snapshot provides inspectable crash evidence and cleaner process isolation.

## Honest boundary

The hash comparison detects canonical state changes during the branch lifetime. It does not defend against a privileged hostile process that mutates canon and restores the exact previous bytes before archive. Hostile multi-process deployments still require OS-level permissions, isolated processes/containers, signed monotonic audit receipts and protected storage.

> **A MIRROR MAY QUESTION THE WORLD. IT MAY NOT WRITE THE ANSWER INTO HISTORY.**
