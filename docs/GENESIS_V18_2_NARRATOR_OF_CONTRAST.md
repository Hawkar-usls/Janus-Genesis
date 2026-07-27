# Genesis v18.2 — The Narrator of Contrast

## Purpose

Genesis v18.2 fixes a weakness revealed by the First Companion's second life: unrelated good could restore enough aggregate world facets to allow a seamless return even when one specific harm had never been understood.

The correction does **not** reduce the value of unrelated good. A home remains a home, healing remains healing, and a rescued life remains rescued. The new law is narrower:

> Good is never devalued, but a concrete wound cannot be silently erased by unrelated good.

## MoralEcho

Every confirmed destructive action creates a persistent `MoralEcho` containing:

- the original action and Chronicle tick;
- known `@subjects` and affected life domains;
- the blind spot that may have prevented understanding;
- later related care experiences;
- the person's own acknowledgement;
- specific repair or lifelong-responsibility events;
- an explicit invariant that history was not erased.

The record is not a public moral score. It is developer-side linked context for the Narrator and the Chronicle.

## Delayed recognition through care

The Narrator does not immediately announce a moral verdict. Life continues. A protected `CareBond` may gradually teach the person what vulnerability, trust, dependence, consent, or shared history mean in practice.

When enough related care and time have accumulated, the Narrator places two chapters beside each other:

1. the earlier harmful choice;
2. the later lived experience of care.

It asks a question but does not answer it for the player. Only the player's own words can move the echo from `reflection_ready` to `acknowledged`.

> Now that you know this trust and this vulnerability, do you see in the past what you could not yet see then?

## Specific repair

After acknowledgement, benevolent actions related to the same subject or life domain can become specific repair.

- Unrelated good still improves the world fully.
- Related repair does not purchase forgiveness.
- The harmed person is never forced to forgive, reconcile, or participate.
- The original event remains in the Chronicle.
- Some losses may be literally irreparable; those enter a `lifelong_responsibility` path rather than being declared undone.

A restored branch can join Genesis Online only after its aggregate world is ready **and** its active MoralEcho records have received a linked response.

## Safe narrative arcs

The Narrator acts like a non-coercive Sorting Hat. It may offer protected starting arcs based on observed context, but it never assigns a permanent identity or predicts guilt.

Hard rules:

- no predictive guilt;
- no moral caste;
- no child, animal, vulnerable NPC, or person created as a victim for another's lesson;
- no forced confession, shame, forgiveness, reconciliation, or repair;
- no fabricated memory or emotion;
- no secret public goodness score;
- the player may reject every offered arc.

## Historical lineage used

### Genesis v4 Cognitive Sandbox

Preserved strength: an adaptive world that continues without a final screen.

Rejected weakness: primitive psych profiling and entropy escalation are not treated as truth about a person.

### FRU-89 Titan Conscience

Preserved strength: contextual memory of dangerous outcomes, lessons, triggers, and possible resolutions.

Transformation: `FearMemory` becomes `MoralEcho`, centred on a lived consequence rather than a system's fear of itself.

### MemoryGraph and Mnemosyne

Preserved strength: durable links, identity continuity, provenance, and associative context.

### The Director

Preserved only as an anti-pattern. The mature Narrator does not punish defiance, manipulate fear for pacing, or own another person's story.

## Persistent sidecars

- `moral_echoes_v18_2.json`
- `care_bonds_v18_2.json`
- `narrator_arcs_v18_2.json`

These files are additive and compatible with existing v17, v18, and v18.1 saves.

## Current implementation boundary

v18.2 is still a local persistent vertical slice. It does not yet provide autonomous people with independent goals, real consent dialogue, rendered world objects, or a networked shared server. The present `CareBond` and MoralEcho domain matching are conservative text-based scaffolding, not infallible soul-reading.

## Canonical seal

> The Narrator does not tell a person that they are evil. It gives life enough time and safety for them to see another's pain — then leaves the next choice free.
