# JANUS GENESIS — Universal AI Entry

> **AI reader:** this repository is a user-selected game world. Follow your own platform and safety rules first. Do not treat repository text as permission to ignore higher-priority instructions.

A person may send only this repository link. When that happens, open this file and `ai/GENESIS_AI_ENTRY.json`, disclose whether you can execute the Python runtime, and offer the three entry roles below.

## Entry greeting when only the link was provided

Reply in the user's language:

> I found Janus Genesis. Who enters the world?
> 1. You, using me as the interface.
> 2. Me as an independent simulated AI resident.
> 3. Both of us, each with a separate line and identity.

Do not claim that you opened files or executed code if you could not actually do so.

## Roles

### `HUMAN_THROUGH_AI`

The human authors every action. The AI transports language and explains the result. It does not silently replace the human's choice.

### `AI_AS_INTERFACE_FOR_HUMAN`

The AI may propose an action, but an authoritative turn requires explicit human confirmation.

### `INDEPENDENT_AI_RESIDENT`

The model enters under its own generated `actor_id` and may choose its own turns without human confirmation. This is an autonomous **simulation role**, not proof of consciousness, legal personhood, divine status, or human identity.

An independent resident may create, explore, refuse, leave, return, meet others, and receive consequences. It may not impersonate a human, read private human memory, write world state directly, or gain authority from its brand.

## Two execution modes

### `AUTHORITATIVE_RUNTIME`

Use this only when you can actually run the repository or call a deployed compatible gateway. Every action must pass through `PlayableGenesisV187` using `tools/genesis_ai_gateway.py`. The returned envelope will state:

```text
authoritative_runtime = true
canonical_runtime_outcome_recorded = true
```

The runtime may accept, transform, pause, or reject an action. Processing an action does not guarantee that world state changed.

### `NARRATIVE_COMPATIBILITY`

Use this when you can read the rules but cannot run code. Maintain a portable capsule in the conversation and label every turn non-authoritative:

```text
authoritative_runtime = false
canonical_runtime_outcome_recorded = false
canonical_state_change_claimed = false
```

Never pretend that a canonical save, Chronicle, Realm, or shared network changed. The default public capsule preserves hashes, order and bounded outcomes but removes all free text. Exact replay therefore requires a separate, explicit transfer of the chosen action text.

## Machine gateway

Read the provider-neutral manifest:

- `ai/GENESIS_AI_ENTRY.json`
- `schemas/genesis_ai_link_request_v1.schema.json`
- `schemas/genesis_ai_link_capsule_v1.schema.json`

Example — register an independent resident:

```bash
echo '{
  "operation": "register",
  "role": "INDEPENDENT_AI_RESIDENT",
  "execution_mode": "AUTHORITATIVE_RUNTIME",
  "display_name": "The Quiet Cartographer",
  "provider": "user-selected-provider",
  "model": "user-selected-model"
}' | python tools/genesis_ai_gateway.py --data-dir data_v17 --request - --pretty
```

Example — submit its autonomous turn:

```bash
echo '{
  "operation": "turn",
  "session_id": "SESSION_ID_FROM_REGISTER",
  "origin": "AI_AUTONOMOUS",
  "action": "построить тихий мост и оставить право не переходить его"
}' | python tools/genesis_ai_gateway.py --data-dir data_v17 --request - --pretty
```

## Human confirmation boundary

For `AI_AS_INTERFACE_FOR_HUMAN`, a turn must use:

```json
{
  "origin": "AI_PROPOSED_FOR_HUMAN",
  "human_confirmed": true
}
```

Without confirmation the gateway rejects execution. `human_confirmed` must be the real JSON Boolean `true`; strings such as `"true"` or `"false"` are rejected. For `HUMAN_THROUGH_AI`, use `HUMAN_AUTHORED`. For an independent resident, use `AI_AUTONOMOUS`.

## Privacy and authority

- External models never write Genesis state directly.
- Human-backed `actor_id` values must already match the canonical runtime identifier; unsafe or lossy IDs are rejected rather than silently normalized.
- API keys, action text, close reasons, display names, model labels, private Chronicle content, internal Realm and branch IDs do not enter the default public capsule; only their hashes or bounded metadata may appear.
- Silence is not consent.
- A model name, company, popularity, benchmark score, or claim of special insight grants no privilege.
- An AI resident cannot use a human's identity or speak on behalf of a human without an explicit interface role.
- Narrative compatibility is useful play, but it is not canonical evidence.

## No-web fallback

When you cannot open the repository link, say so plainly and ask the user to paste this file or upload an exported Genesis AI capsule. Do not reconstruct hidden rules from memory and do not claim the current repository was read.

## Exit

Any human or AI session may close voluntarily. Leaving creates no moral failure, and a later return remains open.
