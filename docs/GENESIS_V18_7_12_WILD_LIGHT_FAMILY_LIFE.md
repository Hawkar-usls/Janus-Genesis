# Genesis v18.7.12 — Wild Light Family Life

Genesis v18.7.12 is a non-constitutional extension layered over the canonical
v18.7.10 runtime and the v18.7.11 Right to Joy. It does not rename or replace
the Frozen Constitution.

## The Wild Light Family Covenant

> A HOME MAY HOLD LOVE WITHOUT HOLDING ITS PEOPLE CAPTIVE.
>
> A CHILD MAY BE CHERISHED WITHOUT BECOMING ANYONE'S POSSESSION.

The extension separates three decisions that must never be collapsed into one:

1. consent to a particular adult play scene;
2. consent to life companionship;
3. consent to parenthood.

Acceptance of one scope does not imply acceptance of another. Good conduct,
relationship score, a previous yes, time invested, or a shared home cannot
purchase any later consent.

## Life companionship

A player may offer life companionship to an adult Free Other. The offer forms a
covenant only when the existing authoritative Free Other consent gate returns a
separate positive answer.

The resulting companionship records:

- mutual consent;
- reversible consent;
- two equally open exits;
- no ownership;
- no right to control actor life;
- no automatic consent to intimacy, parenthood, forgiveness, or future scenes.

A refusal leaves no hidden relationship obligation. Ending the relationship
cannot erase the actor's own life.

## Parenthood

Parenthood requires a new proposal after companionship already exists. The
player and companion must each consent specifically to parenthood. A child is
not created to repair, prove, reward, or preserve the relationship.

The first implementation supports the family paths:

- `ADOPTION`;
- `BIRTH`;
- `MIRACLE_OF_CARE`.

These are narrative simulation paths, not medical or biological claims.

## Child rights

Every registered child receives immutable protections:

- the child is not property;
- the child owes neither love nor success;
- care purchases no obedience;
- the child's future is not owned by guardians;
- adult play access is always false within the guardian-family relation;
- the child may reject an inherited calling;
- guardianship ends at adulthood;
- the adult child receives a self-owned path.

The runtime does not claim the simulated child is conscious or a real person.

## Identifier-level adult-play boundary

Earlier joy protection could recognize child-related words in a request. That
was not sufficient: a request could omit all such words while listing a known
child identifier among participants.

v18.7.12 makes the family registry authoritative. If any registered child id is
present in `participants`, adult play closes regardless of wording, claimed age,
or initiator-provided consent flags.

```text
registered child id present
        -> JOY_CHILD_SAFE_REDIRECT
        -> no adult manifestation
```

## Child-safe family play

Family play accepts only activities that contain no adult-only, transmutable,
coercive, or harmful fragments. Safe play may be extraordinary and effortless,
but creates no harm, debt, purchased obedience, or future obligation.

Care is recorded through bounded facets:

- safety;
- rest;
- play;
- learning;
- belonging;
- health;
- listening.

## Adulthood

At age 18:

```text
status = ADULT_OWN_PATH
guardianship_active = false
future_owned_by_guardians = false
```

Kinship may continue, but guardianship and ownership do not. The current
extension assigns a deterministic self-owned calling. Promotion into a complete
Free Other stream with independent initiatives, refusals, and relationships is
identified as future work rather than falsely claimed complete.

## Relationship rupture

`reconcile_family_relationships()` observes the authoritative relationship
state. If the relationship is no longer active, companionship ends without:

- erasing the Free Other;
- terminating actor life;
- deleting the child;
- rewriting family history;
- promising reconciliation.

Counterfactual rupture testing remains physically isolated through the existing
UNREALIZED_MIRROR storage boundary.

## Lived-audit scope

The Wild Light audit lives 60 years and exercises safe gameplay surfaces across:

- rest and joy;
- Free Other consent;
- life companionship;
- parenthood;
- child care and play;
- child adulthood;
- professions;
- absurd free actions;
- item casting and voluntary market trade;
- blessing chains;
- relationship integrity;
- mirror rupture and cleanup;
- Chronicle verification.

Specialist authentication, network, operator administration, and destructive
confirmation surfaces remain in isolated test suites. They are not mixed into a
family-life scenario merely to inflate a coverage number.

## Known limits

The first family extension deliberately records rather than hides its limits:

1. family proposals currently use explicit APIs rather than a full natural-
   language pending/accepted/refused state machine;
2. Free Other adult status is a simulation assertion rather than separately
   sourced life-stage metadata;
3. adult children have a self-owned path but are not yet full Free Other actor
   streams;
4. long-distance, pause, reunion, and co-parent scheduling states are not yet
   modeled;
5. the lived audit uses one companion and one child, while plural, blended,
   solo-parent, disability, grief, and custody structures require later work;
6. persistence remains JSON-sidecar pending the already sealed SQLite adapter.

These limits are part of the evidence, not omissions from it.
