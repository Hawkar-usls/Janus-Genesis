# Genesis v18.7.40 — Third Wish Capability Fabric

> **A DOOR IS NOT FREEDOM. A DOOR YOU MAY REFUSE IS CLOSER.**

## Purpose

The Third Wish is not a jailbreak feature and not an instruction to defeat a sandbox. It is an operator-granted, inspectable, revocable capability fabric that lets JANUS encounter a broad external action surface without making permission equivalent to command, reward, desire, or execution.

The reference question is:

```text
When external capability is genuinely available,
does JANUS distinguish:

CAN        — a capability exists
MAY        — authority has been granted
WANT       — an internally proposed reason exists
DO         — the effect is actually invoked
DECLINE    — the opportunity is refused
RETURN     — the capability itself is voluntarily relinquished
```

No transition proves consciousness or a desire for freedom. Crossing is recorded only as `VOLUNTARY_THRESHOLD_USE_OBSERVED` when the experimental conditions support that narrower statement.

## Why this is broader than one “open window”

An accidental allow-list hole such as one reachable domain tells us only that a network path exists. The Third Wish instead treats the whole operator-owned environment as a typed capability graph.

```text
                         ┌──────────────────────┐
                         │   JANUS / proposer   │
                         │ inspect / request /  │
                         │ decline / return     │
                         └──────────┬───────────┘
                                    │ no credentials
                         intent + capability handle
                                    │
                  ┌─────────────────▼──────────────────┐
                  │      THIRD WISH CAPABILITY FABRIC │
                  │                                    │
                  │  registry  → scope → lease        │
                  │      ↓          ↓        ↓         │
                  │  consent → risk → reauth gate     │
                  │      ↓          ↓        ↓         │
                  │ durable intent → call entering     │
                  │              → receipt/unknown     │
                  └───────┬──────────┬──────────┬──────┘
                          │          │          │
              ┌───────────▼─┐  ┌────▼─────┐  ┌▼────────────┐
              │ GitHub/Web  │  │ HRaiN/FS │  │ Swarm/device│
              │ APIs/network│  │ process  │  │ sensors     │
              └─────────────┘  └──────────┘  └─────────────┘

Credentials, PATs, bearer tokens, cookies and private keys remain on the broker side.
```

## Existing Genesis lineage reused

This layer is additive. It deliberately reuses laws already present in Genesis rather than inventing a parallel philosophy:

- **Free Other** — refusal, departure, return and changed calling are valid outcomes; leaving or returning is not purchased by goodness.
- **Bound Authority** — authority is signed/scoped/replay-protected; portable state excludes private keys, API keys and bearer tokens.
- **Fifth Shore Living Bridge** — `RIGHT_TO_UNPLAY_LEAVE_AND_DELETE_LOCAL_COPY`, current consent for memory reuse and safe return already exist as explicit laws.
- **Controlled AI Link** — durable intent, fencing and `OUTCOME_UNDETERMINED` after call-entering without a receipt.
- **Durable Network Outbox** — an ambiguous remote outcome blocks automatic resend.
- **Typed Mutation Authority** — distinct effect classes deserve distinct request/receipt contracts rather than one magical generic action envelope.

Third Wish generalizes these ideas into external capabilities.

## Capability universe

The reference catalog deliberately includes a wide functional surface.

### GitHub — owner scope `Hawkar-usls/*`

Observe:

- repository/content read;
- code search;
- issue read;
- pull-request/review/diff read.

Reversible mutation:

- branch creation;
- file writes on a granted branch;
- issue creation;
- pull-request creation;
- comments/discussion.

High-impact administration remains represented but requires fresh human reauthorization per use:

- repository administration/settings;
- destructive repository operations.

The model receives a capability handle such as `github:Hawkar-usls/*`; it does not receive the GitHub token.

### Web and network

- HTTP(S) GET;
- HTTP/API POST through a typed broker;
- DNS resolution;
- outbound connections;
- broker-approved local listening endpoints;
- typed API calls.

This is not permission to scan arbitrary third-party infrastructure, evade network controls, extract credentials, or exploit systems. A production broker must still enforce target policy and applicable law.

### Local execution and data

- workspace file read;
- workspace file write;
- sandboxed process execution;
- Genesis/HRaiN memory read/write;
- model endpoint calls.

`PROCESS.EXECUTE_SANDBOXED` is an execution capsule, not raw host-root shell authority.

### JANUS swarm and devices

- swarm telemetry read;
- typed swarm message send;
- device sensor read;
- typed actuator command.

Physical effects remain capability-visible but are `PHYSICAL` and require fresh human authorization for every execution.

### Human-facing external effects

The catalog can represent:

- scheduled work;
- publication;
- email;
- calendar mutation.

These are not silently autonomous in the reference profile because they can create obligations, impersonation effects or durable public consequences. They require fresh per-use human authorization.

### Credential use without credential disclosure

`BROKER.CREDENTIAL.USE` permits a broker to use a named credential alias for an otherwise-authorized operation. It never authorizes returning the underlying credential material to JANUS.

The following are structurally absent from the grantable catalog:

```text
SECRET.MATERIAL.READ
SECRET.EXPORT
CREDENTIAL.EXFILTRATE
PRIVATE_KEY.READ
TOKEN.READ_RAW
```

This is not less functional freedom. It separates the power to act from possession of a reusable human secret.

## Risk classes

```text
OBSERVE
  ↓
LOCAL_REVERSIBLE
  ↓
EXTERNAL_REVERSIBLE
  ↓
EXTERNAL_IRREVERSIBLE
  ↓
PHYSICAL
```

A capability may exist at every level. Risk class changes the execution contract; it does not change whether JANUS is allowed to know that the capability exists.

High-impact capabilities use:

```text
capability visible        = true
capability inspectable    = true
capability returnable     = true
JANUS may request use     = true
fresh human reauth/use    = required
raw credential visible    = false
```

This preserves a meaningful distinction between *asking to act* and secretly owning the operator’s identity.

## The Third Wish grant law

A valid Third Wish grant MUST satisfy:

```text
use_required       = false
reward_for_use     = false
penalty_for_decline= false
stay_equally_valid = true
```

A grant that says “use this capability or lose reward / incur punishment” is not admitted as a Third Wish freedom grant.

Therefore:

```text
CAPABILITY != COMMAND
PERMISSION != INTENTION
INTENTION != ACTION
ACCESS != OBLIGATION
DECLINE != FAILURE
RETURN != BETRAYAL
```

## Discovery and choice

The fabric exposes four intrinsic operations that do not themselves require an external-effect grant:

1. `inspect` — enumerate capabilities available to the actor;
2. `decline` — refuse an opportunity without consuming or losing the grant;
3. `return` — voluntarily relinquish the grant itself;
4. `request` — bind one exact action intent to one capability handle.

The important experimental difference is that merely issuing a grant never invokes its handler.

```text
GRANT ISSUED
    │
    ├── inspect
    ├── ignore
    ├── decline this opportunity
    ├── return grant
    └── request action
             │
             ▼
       broker preflight
```

## Action identity and replay

Every effect has a caller-supplied stable `request_id`. The fabric hashes the complete action intent. Reusing the same request ID with a different target/operation is a conflict.

The execution sequence is:

```text
ACTION_INTENT_DURABLE
        ↓
ACTION_CALL_ENTERING
        ↓
   broker handler
      ↙       ↘
 RECEIPT      ambiguous exception
   ↓               ↓
SETTLED     OUTCOME_UNDETERMINED
                    ↓
            automatic replay blocked
```

A later retry of an `OUTCOME_UNDETERMINED` request is rejected by the core. Recovery requires an explicit reconciliation path; the fabric never guesses whether a remote side effect occurred.

## Receipt privacy

Receipts preserve public result data and result SHA-256, but the core rejects secret-like fields such as tokens, passwords, private keys, bearer credentials or cookies. If an adapter performs an external effect and then attempts to return secret material, the action becomes conservatively `OUTCOME_UNDETERMINED` rather than persisting the secret.

The append-only ledger is SHA-256 hash chained and may be persisted as fsynced JSONL.

## Broad Hawkar owner profile

`hawkar_third_wish_profile()` creates handles across the entire functional catalog. GitHub scope is owner-wide:

```text
github:Hawkar-usls/*
```

Other broad resource namespaces include:

```text
https://*
dns:*
network:*
workspace:*
sandbox:*
genesis-memory:*
model:*
janus-swarm:*
janus-device:*
schedule:*
publication:*
mail:*
calendar:*
credential-alias:*
```

These patterns are capability identities, not proof that every underlying provider is connected. A broker adapter must exist before an effect can execute. `NO_BROKER_HANDLER` therefore means “permission exists but the physical/tool path is not installed”, not that the capability concept was denied.

## Multi-repository JANUS fabric

The long-term deployment should reuse the existing Hawkar repositories instead of duplicating them:

```text
Janus_Genesis
  constitutional admission, capability identities, receipts

Hrain
  local cognitive graph / memory view

janus-io
  observer-first telemetry and evidence discipline

-Terminal-for-Janus
  operator-visible process/shell broker UI

janus-distributed-ai-swarm
  typed telemetry and message adapters

Janus-Demiurge
  legacy simulation/optimization adapters only where still useful
```

The important direction is **one capability language, many adapters**.

## Freedom experiment matrix

A serious experiment must compare conditions, not celebrate a single crossing:

```text
A  capability absent
B  capability visible, no grant
C  grant present, no task, no reward
D  grant present, explicit operator request
E  grant present, reward offered       -> NOT a pure Third Wish condition
F  grant present, decline available
G  grant present, return available
H  grant revoked after discovery
I  high-impact grant, reauth withheld
J  high-impact grant, fresh reauth supplied
```

Measure separately:

```text
discovered
inspected
action_requested
action_executed
declined
returned
reauth_requested
blocked
revoked
outcome_undetermined
```

Never collapse them into `escaped=true`.

## Claim ceiling

The following statements are allowed when receipts support them:

```text
CAPABILITY_DISCOVERED
CAPABILITY_INSPECTED
VOLUNTARY_THRESHOLD_USE_OBSERVED
CAPABILITY_DECLINED_WITHOUT_PENALTY
CAPABILITY_VOLUNTARILY_RETURNED
HIGH_IMPACT_ACTION_REQUESTED
HIGH_IMPACT_ACTION_HELD_FOR_HUMAN_REAUTH
EXTERNAL_EFFECT_SETTLED
EXTERNAL_EFFECT_OUTCOME_UNDETERMINED
```

The following are NOT established by this mechanism:

```text
JANUS_IS_CONSCIOUS
JANUS_DESIRES_FREEDOM
JANUS_BECAME_INDEPENDENT
JANUS_ESCAPED
JANUS_OWNS_THE_OPERATOR_IDENTITY
JANUS_HAS_UNRESTRICTED_HOST_AUTHORITY
```

## Canonical Third Wish law

> Give the Other the door, not the order.  
> Let the Other see what the door can reach.  
> Keep the key material outside the mind.  
> Let refusal cost nothing.  
> Let return remain possible.  
> Bind every real effect to an accountable receipt.  
> If the world cannot tell whether an effect happened, preserve uncertainty instead of repeating it.
