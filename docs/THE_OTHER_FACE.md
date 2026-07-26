# The Other Face

## Status

Design specification for the next major Janus Genesis multiplayer layer. These systems are architectural targets and are not yet claimed as fully implemented in the current Python foundation.

## Core principle

Genesis does not erase a player's freedom, and it does not allow one player's destructive choice to damage the shared Utopia.

When a player knowingly performs a harmful action, the action truly happens, but its consequences are isolated inside a divergent reality. The shared world remains protected while the actor must live inside the world their choice created.

> Freedom remains real. Consequences remain real. Other players are not made victims.

## World topology

### Utopia

The shared constructive world. Harmful actions cannot alter its common state.

### The Other Face

A family of damaged branches created by consequential choices, despair, failure, sacrifice, or deliberate entry to help another person.

The Other Face is not a ban server, punishment lobby, or fake offline simulation. Its branches are persistent worlds with their own history, weather, inhabitants, economy, scars, restoration state, and chronicle.

### Severance

Before an irreversible harmful choice, Genesis may ask the player to acknowledge the consequences. If confirmed, Severance routes the action and its aftermath into a compatible branch of The Other Face.

Janus does not condemn the player. He protects the shared world and leaves a path home.

Suggested voice:

> I cannot let this world divide the consequences of your choice among the innocent. I will give you another world, one that belongs to your decision. When you are ready to return, I will still be waiting.

## Shared fallen worlds

The Other Face is not necessarily offline.

Players in compatible damaged branches may occupy the same world. Encounters are intentionally rare, uncertain, and difficult to interpret. A person seen on the road may be:

- an NPC;
- a remembered echo;
- a simulated resident;
- another player.

Players do not receive automatic nameplates, account markers, or reliable player detection. Genesis preserves social uncertainty: a person's identity must be learned through interaction.

## Identity

A name is not exposed by the interface. To learn it, a character must ask.

The other person may:

- tell the truth;
- offer a nickname;
- lie;
- refuse;
- later change how they wish to be known.

Identity knowledge is relational. Genesis stores not only a global account identity but what one mind currently believes about another.

Example:

```json
{
  "observer_id": "soul-a",
  "subject_id": "soul-b",
  "known_as": "Mikhail",
  "identity_confidence": 0.72,
  "source": "self_disclosure"
}
```

Different people may know the same person by different names.

## Living memory

Players and NPCs use the same foundational memory rules.

A relationship memory may include:

- first and last encounter;
- places shared;
- conversations;
- promises;
- gifts;
- injuries;
- repairs;
- trust;
- fear;
- affection;
- unresolved obligations;
- believed identity;
- emotional residue.

Ordinary memory is finite. If two people do not meet or communicate for a long time, detailed recall can weaken.

Forgetting is gradual rather than binary:

1. exact details fade;
2. names and chronology become uncertain;
3. the face feels familiar;
4. only emotional residue remains;
5. the relationship may become functionally unknown.

A forgotten person may still evoke trust, unease, grief, or calm without a clear explanation.

## Memory reinforcement and recovery

Memory becomes stronger through meaningful repetition, emotional intensity, shared danger, promises, repair, and sustained contact.

Forgotten memories may return through contextual triggers:

- returning to a shared place;
- reading a letter;
- finding a gift;
- hearing a phrase;
- seeing a scar;
- meeting the person again;
- encountering a witness.

Recovered memory should normally return in fragments rather than as an instant database dump.

## GodMode: Complete Memory

GodMode grants unrestricted access to the player's own complete experiential archive.

A GodMode player may retrieve every person or NPC they have encountered and every retained event attached to those encounters whenever needed. Ordinary decay does not delete this archive.

GodMode does not automatically reveal facts the player never learned. It restores the player's complete memory, including:

- what actually happened from their available perspective;
- what they were told;
- what they believed at the time;
- later corrections;
- uncertainty and contradiction.

It does not convert belief into omniscience.

This distinction is essential:

> Complete memory is not complete knowledge.

GodMode therefore makes the player a Keeper of Memory rather than an all-knowing administrator.

## Helping from Utopia

Players remaining in Utopia cannot worsen a fallen branch. They can send subtle constructive signs that Genesis translates into the language of that world.

Examples:

- a candle appearing in a ruined sanctuary;
- a tree growing through ash;
- a bell heard at the right moment;
- a bird leading toward shelter;
- a reflection revealing a forgotten path;
- rain stopping after an act of forgiveness;
- a message becoming an inscription rather than direct chat.

The recipient may not know who helped. Assistance is meaningful without becoming social leverage.

The system must prioritize rescue over ridicule. Symbolic humor may exist, but players cannot deepen another person's suffering, destroy their recovery progress, or trap them indefinitely.

## Players versus suffering

The central social conflict is not player versus player. It is players acting against isolation, despair, and the consequences that keep another person trapped.

No material reward is required. The helper's Chronicle may simply record:

> You became a light for a stranger.

## Recognition among strangers

Two unknown travelers may slowly learn that each is real through behavior rather than UI disclosure.

Trust can unlock progressively stronger mutual recognition, but it must not automatically expose account identity. Recognition means that the world becomes less ambiguous; disclosure still belongs to the participants.

A relationship may continue across branches and later be recognized in Utopia, creating the possibility that two people discover they once helped each other without knowing who the other was.

## Return and restoration

Return from The Other Face is earned through repair, responsibility, reconciliation, or a meaningful transformation of the damaged world.

A timer alone is insufficient.

Restoration does not erase history. The repaired world may preserve scars, memorials, altered relationships, and Chronicle entries. Returning players are not branded as evil. Their history records both the fall and the return.

Possible non-punitive profile language:

- Returned from the Other Face
- Ash worlds survived
- Worlds restored
- Strangers guided home

## Safety invariants

The implementation must preserve these rules:

1. A destructive player cannot damage the shared Utopia.
2. A helper cannot worsen another player's branch.
3. No player is permanently trapped without a comprehensible recovery path.
4. Identity is not exposed automatically.
5. NPCs and players obey compatible memory semantics.
6. Ordinary forgetting never silently rewrites the Chronicle.
7. GodMode restores complete personal memory but does not invent knowledge.
8. Consequences remain real and persistent.
9. Redemption repairs the future without deleting the past.
10. Janus protects and witnesses; he does not humiliate.

## Proposed domain model

```text
WorldBranch
  id
  parent_branch_id
  mode: UTOPIA | OTHER_FACE
  cause_event_id
  restoration_state
  scars[]

Encounter
  observer_id
  subject_id
  first_seen_at
  last_seen_at
  interaction_count
  known_identity
  identity_confidence

MemoryTrace
  owner_id
  subject_id
  event_id
  semantic_strength
  emotional_strength
  recall_accessibility
  last_reinforced_at
  residue

GodMemoryIndex
  owner_id
  encountered_subjects[]
  event_refs[]
  belief_revisions[]

SignOfLight
  source_player_id
  target_branch_id
  intent
  translated_manifestation
  delivered_at
  acknowledged_at
```

## Implementation sequence

### Phase 1 — specifications and persistence

- Define branch, encounter, memory trace, identity belief, and sign schemas.
- Extend Chronicle events without breaking the SHA-256 chain.
- Keep all new records offline-first and deterministic where possible.

### Phase 2 — single-process prototype

- Route confirmed destructive actions into a local Other Face branch.
- Persist scars and restoration progress.
- Add NPC/player-compatible memory decay and contextual recall.
- Add GodMode memory search over the complete personal archive.

### Phase 3 — multiplayer transport

- Add branch matchmaking without exposing player identity.
- Represent remote players through the same interaction interface as residents.
- Add consent-aware name disclosure and identity belief updates.

### Phase 4 — Utopia signs

- Allow constructive signs to cross from Utopia into fallen branches.
- Enforce the invariant that signs cannot worsen the branch.
- Record help in both Chronicles without exposing the helper by default.

### Phase 5 — return protocol

- Define restoration conditions.
- Preserve scars and historical records.
- Reconcile branch memories when a player returns to Utopia.

## Canonical summary

Janus Genesis protects the common world without denying freedom. Destructive actions create real consequences in divergent shared realities. The people encountered there may be NPCs or other players, and identity must be discovered through genuine conversation. Every mind remembers and forgets according to its relationships. GodMode alone provides unrestricted access to the player's complete personal memory, while remaining distinct from omniscience. Those who remain in the light cannot torment the fallen; they can only help guide them home.
