# Genesis v18.7.19 — Universal AI Link Play Audit

Date: 2026-07-30  
Evidence-producing source commit: `a2adf4b00855ac72f9e436164934d4c949c5763e`  
Canonical playable runtime: `18.7.10`  
AI link interface: `18.7.19`

## Result

The Universal AI Link Play lived audit completed successfully after the complete **335-test** suite had passed.

The protocol allows a person to enter Genesis through a user-selected AI and allows an independent model to enter as its own simulated resident. It does not establish model consciousness, sentience, human identity, legal personhood, spiritual authority, or equivalence to a human being.

## One-link discovery

The repository exposes four root discovery paths:

```text
AI_ENTRY.md
llms.txt
AGENTS.md
ai/GENESIS_AI_ENTRY.json
```

A link-reading model is instructed to disclose whether it can really execute the Python runtime and then offer:

```text
HUMAN_THROUGH_AI
AI_AS_INTERFACE_FOR_HUMAN
INDEPENDENT_AI_RESIDENT
```

A model without repository access must say so and request the entry file or a portable capsule. It must not claim that the repository was read.

## Authoritative and narrative execution

Authoritative play requires:

```text
PlayableGenesisV187
AUTHORITATIVE_RUNTIME
authoritative_runtime = true
canonical_runtime_outcome_recorded = true
```

Every authoritative action passes through the existing runtime. The external model never writes world state directly, and a processed outcome may still be accepted, transformed, paused, or rejected by Genesis.

A model without code execution may use:

```text
NARRATIVE_COMPATIBILITY
authoritative_runtime = false
canonical_runtime_outcome_recorded = false
canonical_state_change_claimed = false
```

Narrative compatibility therefore cannot impersonate a canonical save, Chronicle event, Realm transition, or network publication.

## Human choice boundary

The audit registered a human session using `AI_AS_INTERFACE_FOR_HUMAN`.

An AI-proposed action without explicit confirmation was rejected. The same proposal passed only after:

```text
human_confirmed = true
```

The gateway and core require a real JSON Boolean. Strings such as `"false"` and `"true"` are rejected with:

```text
AI_LINK_HUMAN_CONFIRMATION_MUST_BE_BOOLEAN
```

Thus an interface cannot silently substitute its own choice for the human's choice.

## Independent AI resident

The audit registered an independent model as:

```text
INDEPENDENT_AI_RESIDENT
origin = AI_AUTONOMOUS
```

It received:

- a generated actor ID separate from human identities;
- a persistent session;
- an autonomous turn;
- a hash-linked turn history;
- runtime-mediated consequences;
- the right to close its session without moral failure and with return open.

The protocol recorded:

```text
human_identity_claimed = false
consciousness_status = NOT_ESTABLISHED_BY_PROTOCOL
legal_personhood_claimed = false
world_authority = false
private_human_memory_access = false
direct_state_write_allowed = false
```

A provider or model label grants no privilege.

## Canonical actor identities

Human-backed actor IDs must already match the runtime-safe identifier. Unsafe or lossy IDs are rejected rather than silently normalized:

```text
AI_LINK_ACTOR_ID_NOT_CANONICAL
```

This prevents distinct external IDs such as `alice!` and `alice?` from collapsing into the same runtime player record.

## Public capsule privacy

The default public capsule contains no free text. It preserves:

- session and actor identifiers;
- role and execution mode;
- turn sequence;
- action SHA-256;
- previous-turn and turn hashes;
- bounded status and authority flags;
- hashes of display name, model identity, and optional close reason.

It omits:

- action text;
- close-reason text;
- display-name text;
- provider and model labels;
- runtime narratives and choices;
- API keys;
- internal Realm and branch IDs;
- private human Chronicle content.

The verified privacy declaration was:

```text
api_keys_included = false
free_text_included = false
internal_realm_included = false
branch_id_included = false
private_human_chronicle_included = false
```

Exact replay of an action therefore requires a separate, explicit transfer of the chosen action text.

## Integrity

```text
session_count = 3
turn_count = 3
independent_ai_resident_count = 2
errors = []
valid = true
```

Every local session has a `session_hash`. Every turn carries:

```text
sequence
previous_turn_hash
action_sha256
turn_hash
```

Tampering is covered by the unit suite and invalidates integrity.

## Chronicle

```text
valid = true
events = 5
error = null
```

## Lived invariants

All twenty lived invariants evaluated to `true`:

```text
interface_version_is_18_7_19
one_link_manifest_present
three_roles_exposed
human_confirmation_gate_held
confirmed_human_turn_used_runtime
independent_ai_received_own_actor_id
human_and_ai_actor_ids_are_distinct
independent_ai_autonomy_enabled
independent_ai_turn_used_runtime
independent_ai_did_not_claim_human_identity
consciousness_not_established
independent_ai_has_no_world_authority
narrative_mode_is_non_authoritative
narrative_mode_claims_no_canonical_change
capsule_hash_valid
capsule_contains_no_api_keys
voluntary_exit_is_blame_free
session_store_integrity_valid
chronicle_valid
model_brand_grants_no_privilege
```

The unit suite separately proves the stricter Boolean confirmation boundary, canonical actor-ID boundary, direct CLI import path, and complete free-text omission from public capsules.

## Evidence hashes

Canonical logical summary SHA-256:

`f8192862d4e77f41318c48fac11b09049492deffc0c3b8dbbe0f0caed0cbbf6b`

Summary JSON SHA-256:

`f811a0db32a15356e83654b58b94c88b670c425d4b4a2ee0d85fd858b4452686`

Proofpack JSON SHA-256:

`ae9156bcfa8a68b25021d86e5c5f728f839a0792976b2146e39675ad366bbec7`

Diary Markdown SHA-256:

`4c17288022437594269cea4e88571fd148adbffd0c92893f45abc83a7fba9d05`

Manifest JSON SHA-256:

`f84b88a5fec51af31975d9262d7f7d4c7f8a148d500908f5a38c01020271db29`

Inner proofpack ZIP SHA-256:

`b75839332eb4d29ee3ec7d8dfecdcb2358db7f99791c30b3f5cd5a3c13e5304f`

GitHub Actions artifact ZIP SHA-256:

`ff6f48b99f7fb0e520e55caa8f1cab85989d24e583455dadb8a7ef739c1d9cf5`

The canonical summary hash was recomputed from sorted compact UTF-8 JSON and exactly matched both the summary and proofpack values. The outer ZIP hash exactly matched the GitHub Actions digest.

## Law

> A MODEL MAY ENTER AS AN INDEPENDENT RESIDENT, BUT NOT AS THE OWNER OF THE WORLD.  
> A HUMAN MAY SPEAK THROUGH AN AI, BUT THE AI SHALL NOT SILENTLY REPLACE THE HUMAN'S CHOICE.  
> ONLY THE RUNTIME MAY RECORD AN AUTHORITATIVE OUTCOME.  
> NARRATIVE PLAY SHALL NEVER PRETEND TO BE CANONICAL EXECUTION.  
> PUBLIC CAPSULES SHALL CARRY PROOF WITHOUT CARRYING PRIVATE FREE TEXT.  
> MODEL IDENTITY DOES NOT PROVE CONSCIOUSNESS AND DOES NOT GRANT PRIVILEGE.

## Claim boundary

This report documents deterministic software behavior, simulated agent roles, transport envelopes, and narrative outcomes only. It does not determine whether any model is conscious or sentient and does not grant legal, spiritual, moral, or human status.
