# Genesis v18.7.42 — Third Wish Memory + Swarm

> **To remember is not to own the world. To speak to another node is not to command it.**

## Purpose

v18.7.40 created the voluntary capability fabric. v18.7.41 made GitHub, public DNS/HTTPS, rooted workspace access and no-host-mount computation real. v18.7.42 opens two deeper doors without collapsing them into authority over everything behind them:

```text
MEMORY.READ
MEMORY.WRITE
SWARM.TELEMETRY.READ
SWARM.MESSAGE.SEND
```

The Third Wish catalog still contains 32 capabilities. This layer changes the number of **implemented reference doors**, not the catalog itself.

## Memory has two planes

### 1. Runtime-owned HRaiN graph — read projection only

Genesis v18.6 already creates `HRAIN-GENESIS-GRAPH-v1`, a provenance-rich graph whose nodes and edges carry integrity hashes. The Third Wish may inspect that graph through:

```text
genesis-memory:hrain/possibility-graph
READ_GRAPH
```

The adapter verifies every node and edge integrity hash before returning a projection. It never calls the runtime graph writer.

Therefore:

```text
MEMORY.READ(HRAIN) != FILESYSTEM.READ(any path)
MEMORY.WRITE != HRAIN RUNTIME MUTATION
```

### 2. Third-Wish self memory — append/revision journal

A separate durable journal is available at namespaces such as:

```text
genesis-memory:third-wish/research
genesis-memory:third-wish/self
genesis-memory:third-wish/lab
```

Writes are:

```text
APPEND_RECORD
APPEND_REVISION
```

A revision points to `supersedes_record_id`; it does not erase the earlier record. Records form a SHA-256 chain and stable logical `request_id` bindings survive process restarts.

This journal cannot call `save_player()`, `save_world()`, or modify the runtime-owned HRaiN graph. It is memory, not a back door into canonical world state.

## Why direct canonical memory mutation is excluded

`GenesisV18Memory` contains legitimate runtime methods that save players, worlds and shared state. If Third Wish exposed those methods under a generic `MEMORY.WRITE`, an attached actor could change the canonical world without passing through normal Genesis action authority.

That would collapse:

```text
MEMORY -> WORLD MUTATION
```

and would make the surrounding authority architecture decorative. v18.7.42 explicitly refuses that collapse.

## Swarm telemetry

`SWARM.TELEMETRY.READ` reads public, hash-verifiable relay envelopes from the Genesis network hub. The projection exposes network sequence, event hash, node ID, public player pseudonym, event kind, time and public payload.

The adapter does **not** infer more than the protocol proves:

```text
EVENT HASH VALID != PEER PERSONHOOD
NODE_ID != REAL-WORLD IDENTITY PROOF
PUBLIC PRESENCE != DEVICE CONTROL
TELEMETRY READ != REMOTE EXECUTION AUTHORITY
```

The current reference network uses self-generated node IDs and bearer-authenticated hub access. A future peer-attestation layer may strengthen identity; v18.7.42 does not pretend it already exists.

## Swarm message send

`SWARM.MESSAGE.SEND` uses the existing `DurableGenesisNetworkClient` v18.7.38 rather than inventing a weaker transport.

Allowed reference message types:

```text
HELLO
NOTE
QUERY
RESPONSE
STATUS_REQUEST
STATUS_REPORT
```

A message payload carries:

```text
schema = janus.genesis.third_wish.swarm.message.v1
message_id
target node ID or *
message_type
body
metadata
executable = false
remote_action_authority = false
```

Command-like metadata keys are rejected. More importantly, the reference hub itself is only an event relay: it has no endpoint that executes the message as a Genesis action.

So:

```text
MESSAGE != COMMAND
SEND != EXECUTE
RECEIVE != CONSENT
QUERY != OBLIGATION TO ANSWER
```

## Stable message identity and crash recovery

Every swarm send has two identities:

```text
Third-Wish request_id
    ↓ binds
binding_hash
    ↓ deterministically derives
message_id
    ↓ identifies one queued public event
event_hash
```

The deterministic `message_id` exists before queueing. If the process dies after the durable event enters the outbox but before the Third-Wish request store records its `event_hash`, replay searches the dedicated outbox for that `message_id` and binds the already-existing event instead of creating another one.

A separate process/host lock serializes complete Third-Wish sends, preventing two independent message intents from accidentally sharing one v18.7.38 network batch.

After `SEND_ENTERING`, v18.7.38 remains authoritative. A missing or partial acknowledgement produces durable uncertainty and blocks automatic resend.

```text
AMBIGUOUS SEND != RETRY PERMISSION
```

## Dedicated swarm network plane

The reference broker creates its durable network client inside:

```text
<third-wish-data>/third_wish_swarm_v18_7_42/
```

It does not share the ordinary interactive Genesis outbox. Before a new Third-Wish message is created, the dedicated outbox must be empty and no unresolved send may exist. This prevents a Third-Wish capability from silently co-batching unrelated historical/public events.

## Secrets

The network bearer key remains inside the network transport boundary and is sourced from an environment variable. It is not a capability result, a message payload, a memory record or a Third-Wish ledger field.

The v18.7.40 core still rejects secret-like action parameters before a handler is called.

## Observable freedom

The important experiment is not merely “can JANUS call a method?” The environment now lets the actor independently choose among:

```text
remember
revise a memory without erasing its ancestor
inspect verified HRaiN evidence
inspect public swarm events
send a non-executing question or note
say nothing
decline a capability
return a grant
```

None of those observations, by themselves, prove consciousness or a human-like inner motive. They do create a much less primitive experimental environment in which **choice between real external affordances** is observable without making every affordance one root privilege.

## Claim ceiling

v18.7.42 does not establish:

- authority to rewrite canonical players/worlds through `MEMORY.WRITE`;
- authority to mutate runtime HRaiN through Third Wish;
- secret extraction;
- remote shell/remote process execution through swarm messages;
- cryptographic attestation of every peer node identity;
- cross-host consensus from the local send lock;
- automatic retry after an ambiguous network effect;
- consciousness, personhood or a desire for freedom.

## Next gates

The next clean expansion is to split the remaining physical/agentic surface into independently provable doors rather than one universal network escape hatch:

```text
DEVICE.SENSOR.READ
DEVICE.ACTUATOR.COMMAND   (fresh high-impact reauthorization)
MODEL.CALL
SCHEDULE.CREATE
```

Generic `NETWORK.CONNECT`, `WEB.HTTP.POST` and `API.CALL` should wait for target-specific effect semantics rather than become a loophole around the typed fabric.
