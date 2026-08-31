# Genesis Action Forge R0

Status: `IMPLEMENTED_LOCAL_R0_BOUNDED_INTENT_COMPILER`

Genesis now accepts explicit typed player actions on the GitHub Pages World Shell. The text is not granted direct authority over the world. It is normalized, combined with canonical world causes to derive an action seed, compiled into a bounded intent vocabulary, validated, and only then applied through existing World Shell mechanisms.

## Core law

```text
ACTION_SEED = H(CANONICAL_WORLD_STATE || NORMALIZED_PLAYER_TEXT)
```

Canonical world state includes world identity/seed, generator version, player position, discovered chunks, explicit world mutations and the Chronicle tip. Personal presentation does not participate in canonical action seeding: Mirror style, 2D/3D mode, camera mode and camera heading remain presentation-only.

## R0 vocabulary

World/local actions:

- `MOVE`
- `PLACE_MARK`
- `PLACE_ACTION_ANCHOR`
- `RETURN_TO_HEARTH`

Presentation actions:

- `TURN_CAMERA`
- `SET_MIRROR`
- `SET_DIMENSION`
- `SET_CAMERA`

Unknown text fails closed and returns examples instead of inventing arbitrary execution.

Examples:

```text
иди на север 5 шагов
исследуй мир
оставь знак
построй маяк
вернись к огню
первое лицо
3D
EMBER
```

## Action anchors

R0 deliberately does not pretend that every free-form noun already has a bespoke procedural mesh/material implementation. `построй маяк` creates a visible `PLAYER_MARK`-compatible action anchor with a sanitized concept, deterministic action seed and recipe provenance. Later Material/Mesh/Architecture promotion may resolve such anchors into richer generated structures.

This preserves the distinction:

```text
TEXT INTENT != ARBITRARY GENERATED ASSET
ACTION ANCHOR != FINAL BESPOKE GEOMETRY
```

## Legacy lineage

The design intentionally recovers useful mechanics from older Genesis/Hypnos work:

- the original text-action loop: player writes an action and persistent world state survives between turns;
- Hypnos `VOICE OF CREATOR`: explicit typed input can redirect generation;
- the compact action-vocabulary idea from the older TD work.

The unsafe historical interpretation is not restored. There is no embedded credential material, hidden psychology inference, arbitrary prompt authority, external runtime model dependency, or arbitrary code execution.

## Authority boundary

```text
PLAYER TEXT != DIRECT WORLD AUTHORITY
PRESENTATION != CANONICAL ACTION SEED
LOCAL PAGES MUTATION != ONLINE MMO AUTHORITY
```

R0 remains a local browser vertical slice. A future shared-world authority may accept validated intent receipts, but Pages itself does not claim network-canonical MMO authority.
