# Genesis v18.7.11 — The Sealed Threshold and the Right to Joy

Genesis v18.7.11 is a non-constitutional extension. It does not rewrite the
v18.7.10 Frozen Constitution. It adds a separately hashed covenant and hardens
the storage boundaries that protect canonical history.

## The Right to Joy

> LIGHT DOES NOT OWE THE WORLD PERMANENT EXHAUSTION.
> JOY MAY EXPAND WITHOUT CROSSING ANOTHER WILL.

Dignified rest is a baseline right, not a reward for productivity, suffering,
faith, moral score, or usefulness. An adult may remain playful, ridiculous,
curious, sensual, festive, and childlike without being treated as morally
unfinished.

Demonstrated benevolent conduct may open additional capabilities because, in
Genesis, goodness creates more future. It does not remove anyone else's basic
rights and it never purchases consent, affection, forgiveness, access to a
person, or immunity from a boundary.

The additional capabilities are intentionally easy to use:

- effortless blessed play;
- immediate safe spaces for celebration and adventure;
- harmless fictional analogues of desires that would otherwise carry poison,
  addiction, injury, debt, exploitation, or withdrawal;
- blessing of a nonliving or fictional bearer without claiming it is conscious;
- relay of a blessing through kindness to another consenting adult or to a
  nonliving bearer whose owner consents.

Genesis never declares literal harmful conduct harmless. It changes the
manifested object. The pleasure, symbolism, freedom, laughter, intimacy, or
intensity may remain; the toxin, dependency, disease, compulsion, hidden debt,
coercion, and victim do not manifest.

## Consent boundary

For a shared adult scene all of the following must be true:

1. every participant is an adult;
2. every participant gives a separate positive answer;
3. doubt is absent;
4. consent remains reversible at every moment;
5. stopping requires no explanation and creates no penalty.

The initiator cannot speak on behalf of a Free Other. Text such as “everyone
agrees” is not sufficient. `@FreeOther` participants are asked through the
existing authoritative consent gate. A refusal or alternative ends the proposed
scene without reducing relationship score or creating an obligation.

Any minor context redirects to child-safe play. Any coercion, blackmail,
concealment, impaired-consent shortcut, or attempt to cross another will is
fail-closed.

## Blessing chain

A benevolent holder may bless a nonliving or fictional bearer. The bearer is a
symbolic carrier, not a consciousness claim. It can relay a blessing to a
kindred target only when:

- there is recorded kindness evidence;
- a sentient target is an adult and consents;
- a nonliving target's owner consents;
- no ownership, debt, obligation, or authority is created;
- the bounded chain-depth limit is respected.

This allows a chain reaction of love without turning gratitude into currency or
belief into a permission to rule another person.

## Storage-domain boundary

The current backend remains JSON-sidecar, but runtime storage now exposes an
explicit domain capability:

- `CANONICAL` may write only inside the canonical root;
- `UNREALIZED_MIRROR` has a distinct domain id and no canonical write
  capability;
- mirror roots are mode `0700`;
- symlinks and hardlinks are rejected;
- file count, individual file size, and total snapshot size are bounded;
- arbitrary nested payloads cannot enter the numeric mirror metric archive.

The future SQLite adapter contract is now explicit but not falsely declared
implemented. Every mirror must use a separate database file, connection, WAL,
and SHM. `ATTACH DATABASE` and reuse of a canonical transaction are forbidden.

## Crash-safe sealing

Mirror archival is now a two-phase protocol:

```text
ACTIVE
  -> ARCHIVE_PREPARED
  -> WORKING_COPY_REMOVED
  -> ARCHIVED
```

If the process stops during deletion, the canonical runtime can recover an
`ARCHIVE_PREPARED` lease. Recovery first rechecks the canonical snapshot hash,
the disjoint root, and the root fingerprint. It then repeats deletion and seals
`ARCHIVED_RECOVERED`. Any canonical difference becomes
`FAIL_CLOSED_CANONICAL_CONTAMINATION`.

## Relationship epistemology

`actor.trust` remains a compatibility projection. Authoritative relationship
reasoning uses:

```text
relationship_bond
  -> relationship_score
  -> relationship_state_v1810
  -> acceptance_threshold
```

`actor_life_v1810` remains a separate life stream. A relationship can become
`TERMINATED_BY_OTHER` while the actor remains alive and continues offscreen.

## Permanent promoted regression

The `contact_accepted` Butterfly result is recorded at:

`regressions/relationship_bond_contact_accepted_v1.json`

The regression requires the same seed, actor, action, and non-relationship
state. Only the relationship prior may differ. The record binds the source
commit and proofpack hash and preserves the claim boundary: it proves a runtime
contract, not a universal law of human relationships.
