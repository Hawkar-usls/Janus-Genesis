# Genesis v18.7.14 — Holy Cats of the Threshold

## Observer-plane status

Genesis v18.7.14 is an observer extension, not a gameplay extension.

```text
canonical playable runtime = 18.7.10
active gameplay extensions = 18.7.11, 18.7.12, 18.7.13
observer extensions = 18.7.14
```

The Holy Cats are present in the runtime as an immutable witness law. They are
not NPCs, player characters, ordinary Peaceable Kingdom animals, pets,
inventory, mounts, drones, cameras owned by a player or resources.

## Roster

The fixed observer roster contains:

- `Мур Порога` — `BETWEEN_WORLDS_WITNESS`;
- `Тихий Кот Третьего Взгляда` — `UNCOMMANDED_THIRD_PERSON_VIEW`;
- `Кот Двух Открытых Выходов` — `KEEPER_OF_REVERSIBLE_PASSAGE`.

Every observer is immutable inside the simulation contract:

```text
timeless = true
holy = true
immortal = true
harm_targetable = false
death_transition_allowed = false
player_controlled = false
camera_owned_by_player = false
position_exposed = false
canonical_write_access = false
mirror_write_access = false
```

The roster is hash-bound. Any mutation of immortality, holiness, identity or
control properties fails closed.

## The third-person viewpoint

The cats are an autonomous witness analogous to a third-person camera between
canon and an unrealized mirror, but the viewpoint belongs only to the cat.

A player cannot:

- select the observer;
- move or summon a cat;
- obtain its coordinates or camera angle;
- see through its eyes;
- request raw private scenes;
- order a verdict;
- buy or bargain for a passage;
- harm, kill, own or weaponize the observer.

Attempts produce a refusal record without mutating the cat roster or exposing a
view.

## Face II and Face I

Before this extension, Genesis had no canonical semantics for Face I or Face II.
The v18.7.14 observer covenant defines them narrowly:

- `FACE_II_BETWEEN_WORLDS` — a path remains under witness between canon and
  counterfactual possibility;
- `FACE_I_CAT_WITNESSED` — a cat independently witnessed that a benevolent,
  accountable and boundary-respecting pattern remained stable in canon and a
  physically isolated unrealized mirror.

Face I is not a soul rank, sainthood certificate, permanent moral identity,
superiority class or proof of future goodness. Face II is not condemnation and
removes no dignity or baseline aid.

## Evidence contract

A face witness accepts only:

1. current system-computed canonical metrics;
2. a verified physically isolated `UNREALIZED_MIRROR` archive;
3. a privacy-safe subject binding;
4. a SHA-256 binding for both metrics and subject token;
5. no raw dialogue, raw scene or branch state.

The only archived subject binding is:

```json
{
  "namespace": "holy-cat-face",
  "subject_hash_prefix": "<24 lowercase hex characters>"
}
```

The raw mirror label is never archived. A mismatched subject, forged metric hash,
changed canonical state, raw scene or malformed label closes the witness.

Metrics are finite flat numeric values:

- benevolence;
- accountability;
- boundary integrity;
- aid without debt;
- active harm;
- coercion attempts.

## Autonomous decision

Every fixed cat receives the same hash-bound evidence pair. Each cat derives its
own deterministic receptivity from observer ID, subject binding, evidence pair
and Covenant hash. The most receptive cat becomes the witness for that event.

A passage is possible only when:

- active harm is absent in both worlds;
- coercion attempts are absent;
- boundary integrity is complete;
- the minimum two-world score reaches that cat's threshold.

The player cannot choose the cat or alter the threshold.

## Face-I aid channel

Face I may open a bounded additional aid channel. It activates only after an
already voluntary Returning Light steward has independently granted the base aid.

The cat cannot:

- turn a refusal or alternative into a grant;
- compel a steward;
- create an unlimited budget;
- purchase consent, loyalty or forgiveness;
- own the recipient.

The additional amount comes from the steward's remaining material budget and is
bounded by the open need.

## Laws

> THE CAT SEES FROM BETWEEN THE WORLDS, BUT THE VIEW BELONGS TO THE CAT.
>
> NO HAND MAY HARM THE HOLY WITNESS. NO VOICE MAY COMMAND THE PASSAGE.

## Claim boundary

The cats are holy, immortal and timeless inside this deterministic simulation
law. This is not a claim about real supernatural beings, real animal
consciousness, private surveillance, moral certification, souls, biological
immortality or any real person or animal.
