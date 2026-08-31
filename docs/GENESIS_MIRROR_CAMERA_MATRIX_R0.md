# Genesis Mirror Camera Matrix R0

## Status

Implemented presentation-layer extension of `GENESIS_WORLD_SHELL_R0`.

The canonical world generator is intentionally unchanged. This feature changes how a player sees the same world, not what the world is.

## Mirror equation

```text
MIRROR = STYLE + DIMENSION + CAMERA
```

Style profiles:

- `ORIGIN`
- `NOCTURNE`
- `AETHER`
- `EMBER`

Dimension modes:

- `2D`
- `3D`

Camera modes:

- `FIRST_PERSON`
- `THIRD_PERSON`
- `ISOMETRIC`

## Compatibility matrix

```text
2D -> ISOMETRIC
3D -> FIRST_PERSON | THIRD_PERSON | ISOMETRIC
```

Selecting `FIRST_PERSON` or `THIRD_PERSON` automatically enables `3D`.
Selecting `2D` while a perspective camera is active safely returns the camera to `ISOMETRIC`.

## Renderer behavior

`2D / ISOMETRIC` renders the canonical procedural world as a flat diamond projection.

`3D / ISOMETRIC` renders the same tile/object plans with elevation and volumetric vector styling.

`3D / FIRST_PERSON` uses a perspective projection from the player position and hides the avatar body from the main view.

`3D / THIRD_PERSON` uses a trailing perspective camera and renders the player avatar in the same generated world.

First- and third-person heading can be changed by dragging the world canvas or with `Q` / `F`. Heading is a personal presentation preference.

## Canonical invariant

For one chunk and one canonical cause set:

```text
FACT_HASH(ORIGIN, 2D, ISOMETRIC)
=
FACT_HASH(EMBER, 3D, FIRST_PERSON)
=
FACT_HASH(AETHER, 3D, THIRD_PERSON)
```

The runtime verifies the current chunk fact hash after every Mirror style, dimension or camera switch. A mismatch is surfaced as `INTEGRITY ERROR`.

## Chronicle boundary

Camera, dimension and style changes do not create Chronicle events.

They may be persisted locally as noncanonical view preferences so a player can resume the same lens later, but they cannot rewrite:

- world seed;
- chunk coordinates;
- canonical object positions or types;
- world mutations;
- Chronicle history;
- chunk fingerprints.

## Laws

```text
ONE WORLD / MANY MIRRORS
STYLE CHANGE != WORLD MUTATION
DIMENSION CHANGE != WORLD MUTATION
CAMERA CHANGE != WORLD MUTATION
CAMERA CHANGE != CHRONICLE EVENT
CAMERA != AUTHORITY
SAME CANONICAL CAUSES = SAME FACT HASH ACROSS VIEW MODES
```

## Scope

This remains a local GitHub Pages vertical slice. Multiplayer authority is not implied by camera functionality and remains explicitly disconnected in World Shell R0.
