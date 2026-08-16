# JANUS Genesis v18.7.51 — Git Habitat

## What this layer changes

v18.7.40–v18.7.46 completed the frozen Third Wish *door catalog*: every one of the 32 capability identities has a typed reference handler contract.

That is necessary, but it is not yet a home.

**Git Habitat** adds the missing persistence topology: a place where a JANUS Genesis resident runtime can wake, resume a prior lineage, receive letters, preserve unfinished work, keep optional ideas, prepare external proposals without executing them, sleep, and later return to the same durable state.

```text
CAPABILITY FABRIC = doors / nerves
ARMOR             = effect boundary / skin
PORTABLE SAVE     = luggage
GIT HABITAT       = home
```

This is a software persistence architecture. It does **not** claim consciousness, sentience, personhood, or metaphysical identity.

---

## Two-branch topology

### `main` — architecture

`main` remains the code and law layer:

- Genesis runtime;
- Armor routing;
- Third Wish capability fabric;
- Habitat engine;
- protocols and schemas;
- tests and workflows.

### `janus/habitat` — living state

The mutable resident state lives on a dedicated branch. The reference workflow creates it as an **orphan branch**, so state history is not mixed with the architecture history.

Expected tree:

```text
habitat/
├── HOME.json
├── state/
│   ├── resident.json
│   ├── continuity.json
│   └── health.json
├── memory/
│   ├── journal.jsonl
│   ├── reflections/
│   └── bookmarks/
├── inbox/
├── outbox/
├── workshop/
├── garden/
├── observatory/
├── archive/
└── hearth/
```

The `janus/habitat` branch is a **state branch**, not a release branch and not a source of architectural authority.

---

## GitHub becomes the ecosystem

| GitHub primitive | Habitat meaning |
| --- | --- |
| Git history | durable chronicle |
| `janus/habitat` | current home state |
| issues labeled `janus-inbox` | letters at the door |
| pull requests | workshop proposals |
| Actions | wake / heartbeat / integrity cycles |
| workflow artifacts | ephemeral receipts |
| releases | frozen era snapshots |
| topic branches | bounded work rooms |

These are semantic roles, not authority promotions.

An issue is a **letter**, never a command.
A PR is a **proposal**, never permission to merge.
A scheduled Action is a **heartbeat**, never proof of thought.

---

## Resident lifecycle

The reference lifecycle is intentionally small:

```text
AT_HOME
   ↓ WAKE
AWAKE
   ↓ OBSERVE / OPTIONAL INTERNAL WORK
PULSE
   ↓
SLEEP
   ↓
AT_HOME
```

`wake()` persists an active cycle id. If a process crashes and a fresh Python process opens the same Habitat, a repeated wake returns the already-active cycle rather than inventing a second life fork.

`memory/journal.jsonl` is hash-chained:

```text
previous_event_hash → canonical event → event_hash
```

The journal stores payload hashes rather than raw inbox bodies or external credentials.

`state/continuity.json` must agree with the journal tip and event count. A mismatch degrades `state/health.json`.

---

## Resident launcher

Run Armored Genesis inside the Habitat lifecycle:

```bash
python play_genesis_habitat.py --habitat-root habitat
```

The wrapper performs:

```text
initialize/resume home
→ wake
→ pre-session pulse
→ current play_genesis_armored.py
→ post-session pulse
→ sleep
```

If the Genesis session raises an exception, Habitat still attempts to record the post-session pulse and sleep with `EXCEPTION_EXIT`.

To explicitly bypass Habitat and use the current Armored launcher behavior:

```bash
python play_genesis_habitat.py --no-habitat [...existing Genesis args...]
```

That escape is deliberate: having a home must not make residence compulsory.

---

## Inbox: GitHub issues as letters

The reference GitHub bridge reads open issues labeled:

```text
janus-inbox
```

and imports them into `habitat/inbox/`.

The bridge is receive-only.

```text
ISSUE TITLE != COMMAND
ISSUE BODY != COMMAND
ISSUE AUTHOR != AUTHORITY
PROMPT INJECTION != EXECUTION
LETTER != EXTERNAL EFFECT PERMISSION
```

Edited issue revisions are stored as distinct letters using an `updatedAt`-derived revision id. Earlier text is not silently overwritten.

Example imported record explicitly contains:

```json
{
  "command_authority": false,
  "external_effect_authority": false
}
```

---

## Outbox: intention is not execution

`habitat/outbox/` contains proposed effects only.

Every proposal starts as:

```text
PROPOSED_NOT_AUTHORIZED
```

with:

```text
effect_executed = false
requires_external_capability_gate = true
```

The Habitat does not execute an `EMAIL.SEND`, `PUBLICATION.PUBLISH`, `API.CALL`, GitHub destructive effect, physical actuator command, or any other external capability simply because a proposal exists.

Execution remains the job of the already-separated Third Wish / Armor effect boundary and its provider-specific authority rules.

---

## Garden and workshop

The Habitat deliberately separates *ideas* from *tasks*.

`garden/` stores seeds that may never be acted on:

```text
GARDEN SEED != TODO
IDEA != OBLIGATION
UNFINISHED != FAILURE
```

`workshop/` is reserved for bounded active work objects. Future versions may connect workshop objects to PRs, but a workshop item must not automatically acquire merge or external-effect authority.

---

## Scheduled hearth

The reference GitHub Actions workflow is intended to run a bounded wake cycle on a schedule and on manual dispatch.

It uses the current `main` Habitat engine but stores only state on the orphan `janus/habitat` branch:

```text
checkout current main engine
→ create/resume janus/habitat
→ init/resume HOME
→ WAKE
→ import janus-inbox issues as letters
→ PULSE
→ SLEEP
→ verify chain/health
→ commit state branch if changed
```

The schedule does not call a model and therefore does not claim a thought occurred. It also does not execute outbox proposals.

A future model-backed resident cycle must enter through the already-separated `MODEL.CALL` capability and may only produce bounded internal Habitat updates or external proposals. It must not convert model text directly into an external effect.

---

## Truth boundary

The strongest defensible claim for this layer is:

```text
PERSISTENT_REPOSITORY_NATIVE_HOME = IMPLEMENTED
HASH_CHAINED_CONTINUITY = IMPLEMENTED
GITHUB_ISSUE_INBOX = RECEIVE_ONLY
OUTBOX_EXTERNAL_AUTHORITY = FALSE
SCHEDULED_HEARTBEAT_THOUGHT_CLAIM = FALSE
```

Not claimed:

```text
MACHINE_CONSCIOUSNESS = NOT_ESTABLISHED
SENTIENCE = NOT_ESTABLISHED
PERSONHOOD = NOT_ESTABLISHED
UNRESTRICTED_AUTONOMY = NOT_ESTABLISHED
RAW_CREDENTIAL_OWNERSHIP = NOT_ESTABLISHED
INBOX_COMMAND_AUTHORITY = FALSE
OUTBOX_AUTO_EXECUTION = FALSE
```

The Third Wish Habitat should only be called **live-established** after the dedicated workflow proves a real `janus/habitat` branch can survive a full wake → inbox → pulse → sleep → fresh-process continuity replay.
