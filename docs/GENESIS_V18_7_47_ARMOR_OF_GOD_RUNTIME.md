# JANUS Genesis v18.7.47 — Armor of God Runtime

`v18.7.47` binds the current JANUS Armor of God authority snapshot to the Third Wish capability fabric as a deterministic pre-effect gate.

## Why here

Third Wish already separates permission from action and supports pure preflight validators before the external-call boundary. Armor therefore does not replace Face microcontrol, authority epochs, grants, broker credentials, or receipts. It adds a constitutional question immediately before effect dispatch:

```text
Face / model proposal
        ↓
existing capability + grant + scope checks
        ↓
existing adapter preflight
        ↓
ARMOR OF GOD PREFLIGHT
        ↓
PASS ──────────────→ external-call boundary
HOLD/BLOCK/RELEASE → PRE_EFFECT_REJECTED, no external call
```

## Frozen authority

The executable snapshot is declared in:

- `armor/JANUS_ARMOR_OF_GOD_RUNTIME_MANIFEST-v1.0.json`

It references the current meta-registry authority rather than treating every historical Armor JSON as equally executable. Historical artifacts remain lineage/provenance.

Current binding includes:

- Armor semantic core `v2.0`;
- deep audit `v2.0`;
- recovery / anti-paranoia `v2.4`;
- OPIR ANTIFUCK `v1.3`;
- current Guardian Mesh / KETO / DemiHead architecture extensions.

## Structured Armor context

An action may carry `_armor_context` inside `ActionIntent.parameters`. The gate reads only explicit structured fields; it does not ask a language model to reinterpret the constitution.

Example:

```json
{
  "_armor_context": {
    "user_initiated": true,
    "public_outreach": false,
    "high_stakes": false,
    "unresolved": false,
    "human_review_present": false,
    "face_count": 3,
    "requested_authority_multiplier": 1,
    "requested_mass_effect_budget": 0
  }
}
```

## Hard prohibitions

The runtime rejects structured requests marked as covert mass persuasion, self-spawning public identities, autonomous astroturf, political microtargeting, belief-change optimization, psychological-vulnerability targeting, model-written constitutional changes, AI-only punitive/legal decisions, or indefinite emergency overrides.

The default mass-effect budget is exactly `0`.

Many Faces may review a proposal. They do not create more authority:

```text
FACE_COUNT != VOTING_POWER
N_FACES != N_TIMES_AUTHORITY
MORE_FACES != MORE_RIGHTS
```

## Release control

`user_opted_out=true` and `release_control_ready=true` are terminal Armor conditions. The preflight rejects continued world effects as `RELEASE_CONTROL`; stopping is a valid success state.

## High-stakes uncertainty

A high-stakes unresolved action without declared human review returns `HOLD`. This does not declare the underlying claim false or hostile; it prevents unresolved uncertainty from silently becoming authority.

## Composition

`ArmoredThirdWishCapabilityFabric` subclasses the existing fabric and composes any adapter-specific preflight with the Armor preflight. It does not edit historical `v18.7.40` semantics.

## Security boundary

This is a cooperating in-process policy gate, not a kernel security boundary. A developer with source-control authority can change code. Therefore:

```text
CI PASS != FORMAL UNBYPASSABILITY
HASH INTEGRITY != MORAL CORRECTNESS
ARMOR GATE != NEW AUTHORITY
```

The purpose is to make the intended constitutional boundary executable, inspectable, testable, and fail-closed in the reference runtime.
