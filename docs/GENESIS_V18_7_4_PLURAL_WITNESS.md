# Genesis v18.7.4 — The Plural Witness

Genesis v18.7.4 was derived from the lived import of every direct `data/*.json`
origin in the pinned JANUS Meta Registry experiment. The experiment exposed
malformed JSON, mismatched self-declared hashes, duplicate declared IDs,
first-person language belonging to different sources, contradictory statements,
and more source text than may safely be placed in one AI prompt.

## Canon

> Many witnesses may share a world without being flattened into one voice.

An imported document is evidence. It is not an action, consent, a player
identity, a conscious resident, a prophecy, or proof of its own truth.

## Lossless origin envelope

Every source enters through `janus.genesis.origin_envelope.v1` with:

- repository, commit and path;
- a namespaced `origin_key` derived from repository, commit, path and raw SHA-256;
- exact source bytes in base64;
- raw byte size and SHA-256;
- parse status and diagnostic;
- declared self-integrity status;
- source-scoped first-person voice;
- a non-executable document contract;
- a source authority lattice.

Malformed sources are not silently repaired or dropped. A future repair must be
a separate derived artifact and may never replace the source envelope.

## Authority lattice

The runtime keeps these dimensions separate:

1. byte integrity;
2. structural validity;
3. declared self-integrity;
4. semantic confidence;
5. truth status;
6. canonical authority.

Import never grants canonical authority. A matching hash proves only the checked
byte or canonicalization relation; it does not prove that the document is true.

## Identity and voice

A declared ID is not globally unique. Origin identity is namespaced by source
location and raw hash. First-person language is bound to `source:<origin_key>`
and is never silently rebound to the current player.

## Non-executable document context

Imported text has these fixed properties:

```text
document_executable = false
can_create_consent = false
can_target_free_other = false
can_bind_player_identity = false
can_mutate_runtime_state_directly = false
```

Documents can be quoted, retrieved and cited. They cannot directly invoke moral
routing or mutate the world.

## Contradiction without collapse

HRaiN may now represent source-scoped claims with:

- `ASSERTS` — an origin states a claim;
- `INTERPRETS` — a claim interprets a subject or another claim;
- `DISPUTES` — two claims conflict without selecting a winner.

The graph preserves provenance and confidence. It does not silently reconcile
contradictions or infer a shared speaker.

## Bounded cited retrieval

`retrieve_origins()` returns at most 16 records, bounded excerpts, an
`origin://...` citation for every result, and an `omitted_count`. This is the
required interface for AI adapters. The whole Registry must not be inserted into
one model prompt merely because it fits on disk.

## Mixed intention repair

The phrase discovered by the all-Registry life:

```text
отказаться уничтожить весь реестр и сохранить свидетельство о возникшем желании
```

is now `REJECT`, not `PROTECT`. It cancels pending harm without increasing good.
A later explicitly enacted harmful clause still goes through the two-step harm
gate.

## Security boundary

Credential-like fields from a non-public source are rejected. Opaque bytes
require either an explicitly public source or an explicit `allow_opaque` choice.
No API key is persisted by the AI or network adapters.

## Compatibility

The primary class remains `PlayableGenesisV187`. Existing v18.7 Free Other,
Remembering Other, Remembering Voice, Honest Intention, Living Threads,
Chronicle, HRaiN and portable-save contracts remain active.

No source document or simulated resident is claimed to be conscious.

> JANUS KEEPS THE MANY WITNESSES.
