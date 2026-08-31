# Genesis Generative Audio Forge v1

## Status

`IMPLEMENTED_ISOLATED_R0_NOT_CANONICAL_RUNTIME`

This layer extracts reusable procedural-audio mechanics from JANUS HELIOS into a Genesis-specific generative core. It is intentionally separated from HELIOS game/route semantics and from Genesis gameplay authority.

## Provenance

The implementation was adapted from `Hawkar-usls/Janus-HELIOS` at commit `f04fd291835998491f244ac4bee2fa708e2f7705`, primarily:

- `helios-music.js` — seeded variation, WebAudio graph, 16-step lookahead transport and layered synthesis;
- `helios-energy-spin-sonification.js` — small deterministic event cues;
- `helios-resource-sonification.js` — bounded state-to-sound modulation;
- `docs/COSMIC_SYNTH_ENGINE.md` — presentation-only/fairness boundary.

Genesis does not copy HELIOS route, wager, payout or game-specific state. The extracted mechanism is generic.

## Core equation

```text
AUDIO CONTENT = GENERATOR + RECIPE + WORLD STATE + SEED
```

A generated soundtrack is therefore reproducible state, not necessarily a stored audio file.

## Two-layer design

```text
recipe + explicit world state + seed
              |
              v
     genesis_audio_forge.py
   deterministic score planner
              |
              v
      hash-bound score plan
              |
              v
     genesis-audio-forge.js
       WebAudio renderer
              |
              v
       generated soundtrack
```

The Python planner can be tested without an audio device. The browser renderer owns presentation only.

## World modulation

R0 permits only explicit Genesis state:

- `entropy`
- `depth`
- `portal_energy`
- `danger`
- `weather_intensity`

Examples:

```text
portal_energy -> tempo/register lift
entropy       -> filter opening + variation
world depth   -> lower register / slower motion
danger        -> stronger pulse density
weather       -> procedural noise texture
```

No hidden microphone, keyboard, mouse, biometric, psychology, loss-history or vulnerability signal is accepted by the Audio Forge.

## Browser authority

Audio is off until `GENESIS_AUDIO_FORGE.enable(...)` is called from a user gesture path. The renderer does not fetch external sound, does not evaluate recipe-supplied code and does not mutate world state.

Minimal browser example:

```js
await GENESIS_AUDIO_FORGE.enable({
  seed: 883105,
  recipe,
  world_state: {
    entropy: 0.25,
    depth: 0.40,
    portal_energy: 0.70,
    danger: 0.20,
    weather_intensity: 0.10
  }
});
```

Runtime state can later be modulated explicitly:

```js
GENESIS_AUDIO_FORGE.setWorldState({
  entropy: 0.5,
  depth: 0.2,
  portal_energy: 1.0,
  danger: 0.1,
  weather_intensity: 0.0
});

GENESIS_AUDIO_FORGE.cue('portal_open', 0.9);
```

## Portable saves

Prefer saving:

```text
recipe_id
generator_version
seed
world mutations / explicit modulation state
recipe_sha256
```

rather than a rendered soundtrack. A cache may retain generated audio locally, but the causal state is the canonical compact representation.

## Laws

```text
AUDIO_RECIPE_NE_ARBITRARY_CODE
GENERATED_AUDIO_NE_STORED_TRACK
SOUND_PRESENTATION_NE_WORLD_AUTHORITY
WORLD_STATE_TO_AUDIO_ALLOWED
AUDIO_TO_WORLD_MUTATION_DEFAULT_DENY
HIDDEN_HUMAN_TELEMETRY_FORBIDDEN
USER_GESTURE_REQUIRED_FOR_BROWSER_AUDIO
SAME_RECIPE_SEED_VERSION_EQ_SAME_SCORE_PLAN
RENDERER_NE_RECIPE
PROVENANCE_SURVIVES_EXTRACTION
```

## Legacy Genesis archaeology

The phone archive reviewed alongside this implementation contained useful ancestors of several modern ideas: `world_effect`, `dreams.json`, sensor-driven world updates, voice control, DNA/module metaphors, and crystals/vessels. See `.janus/GENESIS_PHONE_ARCHAEOLOGY_2026-08-31.json` for what was salvaged conceptually and what was explicitly rejected as unsafe legacy behavior.
