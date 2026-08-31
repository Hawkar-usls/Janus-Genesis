# Genesis World Shell R0

## Status

`IMPLEMENTED_LOCAL_VERTICAL_SLICE_R0`

This is the first browser-playable vertical slice of the Genesis generative-world architecture. It intentionally does **not** claim that a shared multiplayer authority server is online. GitHub Pages is the presentation and local-prototype surface.

## Core law

```text
ONE SHARED WORLD
      |
      +-- canonical terrain / object facts / mutations / Chronicle
      |
      +-- PERSONAL MIRROR A -> presentation A
      +-- PERSONAL MIRROR B -> presentation B
      +-- PERSONAL MIRROR C -> presentation C
```

A mirror may change palette, fog, lighting, material shading, procedural vector style and bounded audio presentation. It must not move canonical objects, change their type, rewrite coordinates or edit Chronicle history.

## Streaming model

The browser world uses the Parograd-style streaming pattern as conceptual lineage only:

```text
VISIBLE_RENDERED
      inside
PREWARM_PLAN_ONLY
      inside
RECIPE_ONLY_FAR
```

Default R0 radii are 2 visible chunks and 4 prewarm chunks around the player. Far world state is not materialized into rendered bytes.

## Procedural content model

The `.kkrieger` lesson is used as conceptual lineage, not copied code:

```text
CONTENT != ONLY STORED BYTES
CONTENT = GENERATOR + RECIPE + PARAMETERS + SEED + MUTATIONS
```

The World Shell generates deterministic terrain recipes, biome state, procedural vector object plans and occasional architecture primitives from `world_seed + chunk_coordinates + generator_version`. Personal mirror state is deliberately excluded from canonical chunk fingerprints.

## Current browser forges

- `MATERIAL_FORGE`: biome/material recipe -> deterministic Canvas shading.
- `MESH_FORGE`: bounded procedural vector plans for trees, rocks, crystals and ruins.
- `ARCHITECTURE_GRAMMAR`: First Fire plus deterministic arches/obelisks.
- `EFFECT_FORGE`: presentation-only fog, light and moisture effects.
- `AUDIO_FORGE`: existing HELIOS-derived WebAudio renderer.

These are R0 browser vertical-slice implementations. They are not promoted as final canonical runtime engines.

## Chronicle and world growth

Entering a previously unseen chunk writes a `CHUNK_DISCOVERED` event. The explicit `LEAVE MARK` action writes a `PLAYER_MARK_PLACED` mutation and event. Chronicle events are hash-linked with SHA-256 when WebCrypto is available.

Movement itself is not treated as a permanent world mutation. A renderer cannot create a mutation. Only the explicit player-action reducer can create the local demo mark.

## Cause-first save

Browser local storage keeps:

- world ID and seed;
- generator version;
- player position;
- selected mirror profile;
- discovered chunk coordinates;
- explicit world mutations;
- Chronicle hash chain.

It does not persist rendered terrain pixels, generated texture bitmaps, generated mesh buffers or audio PCM.

## JANUS organ boundary

Genesis is one organ of JANUS, not a replacement for JANUS.

- `Janus_Genesis`: game/world domain and one-world Chronicle law.
- `Janus-HELIOS`: procedural audio design lineage already adapted into the Audio Forge.
- `janus-lapis`: fail-closed JSON-to-IR lineage for later recipe distillation.
- `Janus-Demiurge`: reserved future external authority/reconciliation integration surface; **not** a Pages dependency.
- `PHYSARIUS Asset Trunk`: rights-aware external asset fallback when a procedural recipe is not sufficient.

The browser does not fetch code or data from those repositories at runtime. Cross-organ integration must be explicit, versioned and provenance-preserving.

## What R0 proves

1. The root GitHub Pages experience can be a playable world rather than only a control dashboard.
2. Walking causes new chunks to be materialized locally from deterministic recipes.
3. Canonical chunk fingerprints stay the same across mirror changes.
4. Personal mirrors can visibly alter the same canonical world.
5. World history can accumulate as causes without storing rendered world bytes.
6. The existing generative audio layer can react to the current generated environment without gaining world authority.

## What R0 does not prove

- online MMO synchronization;
- authoritative multi-user conflict resolution;
- account identity or anti-cheat;
- server persistence;
- final 3D/WebGPU rendering;
- final physics, NPC or economy systems;
- that a local Pages mutation is network-canonical.

Those require later JANUS-organ contracts and an authoritative runtime outside the static Pages renderer.
