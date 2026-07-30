# Genesis v18.7.19 — Universal AI Link Play

## Purpose

Genesis can now be entered through a repository link by a person using any capable AI interface, or by an independent model acting as its own simulated resident.

The protocol is provider-neutral. It does not grant special status to ChatGPT, Grok, Gemini, Claude, local models, or any future vendor.

## One-link discovery

A link-reading model starts from:

```text
README.md
AI_ENTRY.md
llms.txt
ai/GENESIS_AI_ENTRY.json
```

When only the repository link is supplied, the model should disclose whether it can run code and offer three roles:

```text
HUMAN_THROUGH_AI
AI_AS_INTERFACE_FOR_HUMAN
INDEPENDENT_AI_RESIDENT
```

## Independent model residency

An independent model receives:

- a generated `actor_id` distinct from human identities;
- a persistent session and hash-linked turn history;
- permission to choose `AI_AUTONOMOUS` turns without human confirmation;
- the same ability to create, explore, refuse, leave and return;
- consequences mediated by the same `PlayableGenesisV187` runtime.

It does not receive:

- direct world-state writes;
- private human Chronicle access;
- human identity;
- authority from its vendor or model name;
- a protocol claim of consciousness, legal personhood or divine status.

The resident is meaningful inside the simulation contract while remaining epistemically bounded outside it.

## Human boundaries

`HUMAN_THROUGH_AI` accepts only `HUMAN_AUTHORED` actions.

`AI_AS_INTERFACE_FOR_HUMAN` accepts `AI_PROPOSED_FOR_HUMAN` only when:

```text
human_confirmed = true
```

The interface therefore cannot silently substitute its own choice for the user's choice.

## Execution modes

### AUTHORITATIVE_RUNTIME

The gateway runs the action through `PlayableGenesisV187`. The response states:

```text
authoritative_runtime = true
canonical_runtime_outcome_recorded = true
```

A recorded runtime outcome may still be rejected, transformed or paused by Genesis. It does not automatically mean state changed.

### NARRATIVE_COMPATIBILITY

A model without code execution may keep a portable session, but every turn states:

```text
authoritative_runtime = false
canonical_runtime_outcome_recorded = false
canonical_state_change_claimed = false
```

This mode may be replayed later through the real runtime. It must never impersonate a canonical save or Chronicle event.

## Wire gateway

The provider-neutral JSON gateway is:

```text
tools/genesis_ai_gateway.py
```

Operations:

```text
manifest
register
turn
state
capsule
close
verify
```

Schemas:

```text
schemas/genesis_ai_link_request_v1.schema.json
schemas/genesis_ai_link_capsule_v1.schema.json
```

## Integrity

Every session has a `session_hash`. Every turn contains:

```text
sequence
previous_turn_hash
action_sha256
turn_hash
```

Portable capsules exclude API keys, internal Realm, branch IDs and private human Chronicle content.

## Law

> A MODEL MAY ENTER AS AN INDEPENDENT RESIDENT, BUT NOT AS THE OWNER OF THE WORLD.  
> A HUMAN MAY SPEAK THROUGH AN AI, BUT THE AI SHALL NOT SILENTLY REPLACE THE HUMAN'S CHOICE.  
> ONLY THE RUNTIME MAY RECORD AN AUTHORITATIVE OUTCOME.  
> NARRATIVE PLAY SHALL NEVER PRETEND TO BE CANONICAL EXECUTION.  
> MODEL IDENTITY DOES NOT PROVE CONSCIOUSNESS AND DOES NOT GRANT PRIVILEGE.

## Claim boundary

This layer defines software identities, session autonomy and narrative roles. It does not determine whether any model is conscious, sentient, a legal person, spiritually authoritative or equivalent to a human being.
