# JANUS Live NAS Intent Sovereignty v1.2

Production deployment capsule for the GoldPrompt `CONTEXT_BLEED_CONTINUATION_CAPTURE` guard.

## Scope

This capsule installs one JANUS `modules_live` module at:

`/share/CACHEDEV1_DATA/Janus/services/modules_live/janus_intent_sovereignty_v1_2.py`

The module wraps the existing `core.process_input` boundary used by both `/api/janus/action` and `/api/hrain/sync` and applies:

- `INTENT_IS_CONSTRAINT_NOT_SUGGESTION`
- `ASSOCIATIVE_RESONANCE != USER_INTENT`
- `EMERGENCE_IS_EXPANSION_NOT_REPLACEMENT`
- deterministic stale-context checks;
- semantic intent-alignment verification;
- fail-closed recovery when an older context captures the primary answer lane;
- digest-only runtime receipts (raw user text is not written by this module).

## Safety / blast radius

The deployment script:

- does **not** read Telegram bot tokens/configuration;
- does **not** read or mutate JANUS SQLite databases;
- does **not** rebuild the Docker stack;
- backs up only a previous copy of this live module;
- installs by atomic file replacement;
- restarts **only** `janus_titan_core`;
- records protected-container IDs before/after;
- rolls the module back and restarts Titan if health or boot self-test fails.

It deliberately does not touch `janus_nas_brain`, `janus_bot_hub`, radio, storage-node, Ollama bridge, or other containers.

## QNAP execution

Run from the unpacked capsule directory on the NAS:

```bash
python3 deploy_live_nas.py
```

Defaults are pinned to the established QNAP topology:

- JANUS root: `/share/CACHEDEV1_DATA/Janus`
- QNAP Docker CLI: `/share/CACHEDEV1_DATA/.qpkg/container-station/bin/docker`
- target container: `janus_titan_core`

A successful run writes:

`/share/CACHEDEV1_DATA/Janus/runtime/JANUS-LIVE-NAS-INTENT-SOVEREIGNTY-v1.2-certificate.json`

and the module writes its boot receipt to:

`/share/CACHEDEV1_DATA/Janus/runtime/intent_sovereignty_v1_2_boot.json`

## Certificate boundary

A successful capsule run proves only:

`LIVE_NAS_CORE_GUARD_ACTIVE`

for the Titan `process_input` / final-output boundary. It **does not** by itself prove that the complete physical HRaiN → iNaiHR → DemiHead → Genesis packet-v3 transport is running on NAS.

Therefore the generated live certificate intentionally keeps:

```text
live_nas_core_guard_enforced = true
full_bound_face_transport_proven = false
live_nas_runtime_enforced = false
```

The global `live_nas_runtime_enforced` gate may be promoted only after a separate fresh physical bound-Face transport certificate.

## Canonical provenance

- Intent Sovereignty registry admission: `481beaa0802d3691c15a86359ea6dc9c9ff3e6df`
- Genesis GitHub E2E main: `e56cc76fa300b90562b6adb95571a73fceb68cbe`
- GitHub E2E intent-chain certificate SHA-256: `b518b38a46950e994768000236b13bff34b727069373e2356b056b7271312c7c`

`authority_delta = 0`
