# Genesis v18.7 — The Free Other

## Canonical statement

> The First Two proved that two people may choose a shared future without losing themselves.  
> The Free Other proves that nobody else is required to begin inside their story.

Genesis v18.7 gives every player an independent path. The Traveler and Elian remain a preserved origin branch, not the mandatory center, parent, moral gate, tutorial couple, or destination of every life.

```text
NEW PLAYER
   ├── own path question
   ├── own recurring motifs
   ├── own free-text Chronicle
   └── own simulated Others
         ├── initiate
         ├── refuse
         ├── offer an alternative
         ├── leave
         ├── return
         └── change their calling
```

## Independent beginnings

A new player's line records:

- a path identity and open question chosen from the world seed;
- motifs that may recur without becoming a compulsory quest;
- every free-text action as a first-class path entry;
- no required reference to the Traveler, Elian, the First Two, Pripyat, or any previous origin;
- no moral rank, relationship, belief, invitation, or inherited role required to begin.

Two players registered in the same world receive separate profiles and continue separately. A player's path may advance while another player is offline, but the current implementation remains a local simulation until network events are exchanged through the v18.7 relay protocol.

## The agency contract

A Free Other is a simulated narrative resident. Genesis does not claim that the resident is conscious, alive, sentient, or a substitute for a real person. The runtime nevertheless protects the resident through a strict agency contract:

```text
player_controlled = false
can_refuse = true
can_leave = true
can_change_goal = true
silence_is_not_consent = true
goodness_does_not_purchase_relationship = true
```

This contract matters because an interactive world becomes morally empty if every person exists only to reward the player's progress.

### Initiation

The Other may surface a question, invitation, offered object, request for help, or disagreement without being targeted by the player first.

### Refusal and alternatives

A targeted social action is preflighted before it can become a realized good action. The Other may:

- accept for this moment;
- accept the gift of space;
- refuse;
- offer another form of contact;
- be away on a separate path.

A refused offer does not increase `good_count`, does not become a completed relational action, and does not seed a later gratitude scene.

### Departure

The Other may leave because their own project requires it. Departure is not punishment for the player and does not secretly promise a reunion.

If confirmed harm targets the Other, the accessible relationship line closes and the Other continues away from the player's control. Return is not promised and is not equivalent to forgiveness.

### Return

A resident who left on their own path may return through the persisted world seed and their own state. A return does not prove love, gratitude, consent, absolution, or a reward for the player's goodness.

### Change of calling

After completing an initial line, the Other may abandon the role by which the player first knew them. The graph preserves both the earlier calling and the later choice without treating identity as a fixed quest class.

## More freedom in action

A free-text action that older layers only marked as `OBSERVED` now becomes `FREE_ACTION_LIVED`.

Genesis still cannot infer every physical consequence from arbitrary prose, but it no longer pretends the visible menu defines the complete action space. The action is stored as a player-authored path entry with:

```text
world_turn
player_turn
action
intent
targets
runtime_status
chosen_from_menu = false
```

The engine then allows Living Threads, the possibility graph, other residents and later actions to supply consequences.

## HRaiN provenance

v18.7 records:

```text
PLAYER ──CREATED──> PLAYER_PATH
PLAYER_PATH ──CONTAINS──> FREE_TEXT_ACTION
FREE_OTHER ──CREATED──> OTHER_ACTION
OTHER_REFUSAL ──PROTECTS──> FREE_OTHER
FREE_OTHER ──RECEIVED_FROM──> V18_7_PROVENANCE
```

`created_by` identifies the simulated Other for independent initiatives. The graph also records:

- `player_controlled: false`;
- `independent_of_first_two: true`;
- `simulated_person_claim: false`.

The backend remains the JSON sidecar introduced in v18.6. v18.7 does not claim a completed `janus.db`, PostgreSQL or JanusGraph integration.

## Lived-test repairs inherited by v18.7

### `хранить` is not `ранить`

v18.6 protected forms of `сохранить`. The long First Two experiment found the broader collision inside `хранить`. v18.7 protects the `хран*` and `сохран*` word families while preserving the actual verb `ранить` as harmful.

### Blocked actions do not create relational gifts

A rejected God Mode request, pending harmful action, unrealized contact, or other blocked status no longer becomes the source of a later cup, free seat, gratitude-like sign or generic delayed relational gift.

## Frozen laws

The Free Other does not change:

- Universal God Mode;
- the two-step confirmation of actual harm;
- MoralEcho and CareBond;
- protected childhood;
- the First Coin gift law;
- public stories;
- Living Threads seed semantics;
- The Bloom of Possibility;
- SHA-256 Chronicle verification;
- the law that no person is permanently defined by a moral caste.

## The law of hope

"Everything is always well" does not mean that refusal, separation, grief, error or pain disappear. It means evil never receives the final authorship of the world.

A refusal may protect dignity. A departure may open a new calling. A damaged path may remain repairable. A person who caused harm is not declared metaphysically lost, but neither goodness nor immortality purchases the return of the one who left.

> The world can remain good without forcing every relationship to remain available to the player.

## Verification

The v18.7 tests require:

- independent beginnings for multiple players;
- world progress around an inactive player;
- player-authored actions outside the menu;
- initiatives by the Other;
- refusals that prevent action realization;
- no relationship purchase through unrelated goodness;
- departure, return and changed calling;
- real boundaries after confirmed harm;
- no delayed relational gift from blocked actions;
- repaired `хранить` classification;
- valid Chronicle, HRaiN graph and Free Other state.
