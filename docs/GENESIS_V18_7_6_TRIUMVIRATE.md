# Genesis v18.7.6 — The Triumvirate of Witnesses

## Canonical correction

A contradiction may begin with two voices, but a canonical Genesis dispute
requires three grounded and independent voices.

Two voices can enclose the whole field inside a duel. The third voice opens the
field again. It is not an automatic judge, mediator, majority maker, or source
of final truth.

> A dispute requires three voices by the path of the triumvirate.

## Contract

A canonical dispute is created only when all of the following are true:

- exactly three distinct claim IDs are supplied;
- every claim is grounded in exact source evidence;
- all three claims address the same explicit subject;
- all three claims belong to different voice scopes;
- no voice receives a privileged role;
- no winner is selected;
- no silent reconciliation is performed.

Three excerpts from one source remain one source voice. Three interpretations
written by one reader remain one reader voice. Quantity of claims does not
manufacture independence.

## Graph form

```text
GROUNDED CLAIM A ─┐
GROUNDED CLAIM B ─┼─ DISPUTES ─> TRIUMVIRATE_DISPUTE
GROUNDED CLAIM C ─┘
```

The dispute node records:

```text
member_count = 3
all_members_grounded = true
all_voices_independent = true
role_equality = true
third_voice_is_judge = false
winner_selected = false
silent_reconciliation = false
```

Each participant edge uses `member_role = equal_voice`.

## Compatibility

Historical pairwise `DISPUTES` edges are preserved as historical graph records.
They are not deleted or rewritten, but they are not promoted into canonical
v18.7.6 disputes.

The old pairwise API now refuses to create a new dispute and directs callers to:

```python
record_triumvirate_dispute([claim_a, claim_b, claim_c])
```

## Portable state

The three claims, their exact grounding evidence, voice scopes, dispute node,
three membership edges, and no-winner contract cross the same verified portable
save as Chronicle, HRaiN, Free Other, Honest Intention, Plural Witness, and
Grounded Witness state.

## Invariants

```text
disputes_require_triumvirate = true
triumvirate_requires_exactly_three_claims = true
triumvirate_requires_three_grounded_claims = true
triumvirate_requires_three_independent_voices = true
triumvirate_requires_one_explicit_subject = true
third_voice_is_not_automatic_judge = true
triumvirate_selects_no_winner_by_default = true
legacy_pairwise_disputes_are_not_promoted = true
```

## Seal

> Two voices reveal opposition. Three voices create a field in which opposition
> can be witnessed without becoming a closed duel.
>
> **JANUS KEEPS THE THIRD VOICE.**
