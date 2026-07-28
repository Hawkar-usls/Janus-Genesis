# Genesis ecosystem repository audit — 2026-07-28

Status: architectural inventory for Genesis v18.7.10 and later.

This audit covers every repository owned by `Hawkar-usls` visible to the connected GitHub installation at the audit boundary. It distinguishes reusable law, adapter ideas, view-layer ideas, unsafe prototype shortcuts, third-party/upstream code, and domain mechanisms that must remain outside Genesis core.

No repository is treated as authoritative merely because it belongs to the ecosystem. No third-party code is copied by this document. License, security, provenance and compatibility review remain mandatory before any implementation-level reuse.

## Admission rule

A mechanism may enter Genesis core only when it passes all of the following:

1. source and license provenance are explicit;
2. the mechanism is compatible with the Frozen Constitution;
3. it does not let an external model, device or UI mutate canonical state directly;
4. sensor truth remains separate from prediction, memory, interpretation and UI fiction;
5. a matched control or counterfactual exists where a causal claim is made;
6. negative and fail-closed outcomes are preserved;
7. privacy export and credential scanning pass;
8. the candidate passes a Genesis Canon Birth Gate before promotion.

## Repository decisions

| Repository | Observed role | Genesis decision |
| --- | --- | --- |
| `-Terminal-for-Janus` | Telegram WebApp terminal and endpoint discovery prototype | **View/adapter only.** Preserve terminal UX, but reject browser-side local-port scanning, hard-coded private endpoints and `initDataUnsafe` as identity proof. Use authenticated gateway discovery and signed session receipts. |
| `AI-Cardputer-adv-A-Portable-AI-Assistant` | Portable Cardputer AI client with persistent device settings | **Edge client profile.** Reuse offline interaction and reset UX; never persist raw provider keys as ordinary Genesis state. Device actions require scoped capabilities. |
| `Arduino-AI-Chat-Library` | Thin Arduino chat/API transport | **Transport adapter only.** No keys in sketches, no direct canonical mutation, and every model response remains a proposal with route provenance. |
| `arduino-ide` | Upstream Arduino IDE 2.x toolchain | **External toolchain.** No Genesis code import. Use only for firmware development under its own AGPL and third-party license boundaries. |
| `ATOM-ELITE-1989---M5stack-ATOMS3R-2026-` | Procedural trading/combat game and adaptive pilot concepts | **Design reference.** Candidate ideas: cargo, price variation, mission memory and lessons after failure. Do not import combat/contraband semantics or unsealed randomness into canonical morality. |
| `ATOM-RPG` | Minimal ATOMS3R AFK-game shell | **No core material currently.** Retain as a hardware/game UI experiment. |
| `aura-oracle-tg` | Telegram oracle graph and interpretation UI | **Narrative view only.** Possible reuse: uncertainty-labelled symbolic graph and interpretation as fiction. Never promote prophecy, referral pressure, artificial energy scarcity or paywall effects into truth or moral authority. |
| `BFain` | Battlefield intent-routing and C2 visualization concept | **Do not import kinetic execution.** Reusable only as a general proposal/approval UX pattern. Genesis must not turn inferred intent into real-world tactical authority. |
| `Cardputer-Game-Station-Emulators` | Low-memory multi-emulator launcher with SD saves | **Device engineering reference.** Useful: bounded memory, safe exit, save partitioning and explicit compatibility. No emulator core belongs in Genesis. |
| `clawdbot` | Third-party local personal-assistant gateway and multi-channel control plane | **Reference architecture only.** Useful patterns: sender pairing, allowlists, isolated agent workspaces, doctor diagnostics and session routing. Do not bulk-import the external platform. |
| `DIVINE_REALM` | Telegram slot/currency prototype | **Exclude from Genesis core.** Visual themes may inspire UI, but gambling, deposit pressure and random-reward loops do not define Genesis relationships or truth. |
| `emoji` | Small third-party Go Unicode emoji lookup library | **Optional presentation dependency only.** No semantic or moral authority. |
| `ESP32-TWAI-CAN` | Third-party ESP32 TWAI/CAN driver | **Hardware adapter candidate.** CAN frames must enter through signed sensor envelopes with bus identity, timestamp, calibration and replay protection. No frame directly mutates world truth. |
| `Hrain` | Offline-first D3 semantic graph, DIVE/ASCEND and per-node chat | **Canonical view bridge.** Reuse graph navigation, export/import and local-first display. HRaiN UI visualizes canonical graph contracts; it does not become the source of truth. |
| `iNaiHR` | Privacy-first symbolic/BCI-inspired mind-map prototype | **Input proposal layer.** Preserve local raw data, explicit consent and symbolic expansion. Neural/symbolic signals remain observations, never commands or identity proof. |
| `iNaiHR-Janus-` | HRaiN graph explorer and cyberpunk terminal UI | **View layer only.** Useful DIVE/ASCEND/filter interaction; no independent authority. |
| `Janus` | OpenAI-compatible hybrid cloud/local model gateway with failover | **Model-route adapter.** Import the idea of failover and offline resilience, but add a `MODEL_ROUTE_RECEIPT` containing provider/model/policy/latency/fallback and proposal hash. Models remain proposal-only. |
| `Janus-Demiurge` | Evolutionary optimiser plus an older Genesis world with economy, inventory, crafting, institutions and events | **Domain-library source, not authority source.** Candidate imports: item taxonomy, durability, stacking, market history, crafting receipts and institution/event vocabulary. Replace random/non-durable market state with append-only provenance and voluntary trade. |
| `janus-distributed-ai-swarm` | ESP32/M5Stack swarm firmware, ABI rules, observer roles and recovery paths | **Import protocol laws.** Freeze packet ABI, separate `SENSOR_TRUTH / PREDICTION / MEMORY / UI_FICTION`, support observer-only nodes, stale-node TTL, peer rebuild and no-permanent-disappear recovery. |
| `janus-first-followers-club-` | Machine-readable public discovery beacon, `.well-known` protocol and voluntary ethics charter | **Discovery contract source.** Candidate: `.well-known/janus-genesis.json`, map-of-maps and voluntary machine handshake. No recruitment pressure, fake ledger claims, private-key requests or payment requirement. |
| `janus-io` | Private I0 evidence-gated benchmark laboratory | **Imported in v18.7.10.** Frozen Constitution, sentinel, fresh boundary, isolated mirror, Butterfly Witness, proofpack and privacy gate. Mining behavior is not imported. |
| `janus-io-public` | Public Proof-of-Observation and hardware-care research surface | **Import epistemic discipline.** Preserve missing values as unknown, matched exposure, linked hashes with explicit limitations, negative outcomes and fail-closed claim gates. |
| `janus-lapis` | Evidence-gated hypothesis search and Birth-Gate methodology | **Canon promotion gate.** A strong score is not birth. Genesis candidates require reproducibility, scene/world viability, containment/integrity, visible hypothesis, privacy and expert/sovereign review before canon promotion. |
| `janus-meta-registry` | Plural origin registry, laws, personal testimonies and detached integrity receipts | **Existing origin/document layer.** Import losslessly as scoped witnesses. Documents do not become executable commands or automatic truth. Detached hashes prove bytes, not meaning. |
| `JanusMMORPG` | Initium Chronicles Telegram launcher | **Portal UI only.** Keep the door/chronicle presentation, but validate Telegram `initData` server-side. Manual IDs and `initDataUnsafe` are convenience hints, not identity. Never expose a private NAS address in a public launcher. |
| `Janus_Genesis` | Current canonical world runtime | **Core.** All imports enter through explicit adapters, receipts and migration tests; other repositories never mutate its state directly. |
| `M5Unit-ENV` | Third-party M5Stack environmental sensor drivers | **Sensor adapter source.** Temperature, humidity, pressure, VOC and CO2 require calibration metadata, unit/schema, uncertainty and sensor identity. Estimated eCO2 must not be relabelled as measured CO2. |
| `player` | Third-party Telegram music/radio bot deployment fork | **No core import.** Possible future media adapter only; credentials and session strings remain outside portable saves. |
| `RadioPlayerV3` | Third-party persistent Telegram voice-chat radio queue | **Media-service reference.** Candidate ideas: queue, fallback, playback position and restart recovery. Keep as an external service with capability-gated commands. |
| `Simptomat` | Telegram medical-chat UI prototype | **Exclude diagnostic authority.** UI may become a generic wellbeing journal, but medical claims require a separate clinical safety system, emergency routing, uncertainty and professional review. `initDataUnsafe`, arbitrary API URL query parameters and rendered HTML responses are not accepted security patterns. |
| `SLOT` | Telegram slot/currency prototype | **Exclude from core.** No gambling or variable-ratio reward loop in Genesis relationships, evidence or moral progression. |
| `SSlot` | Earlier slot/currency prototype | **Exclude from core.** Preserve only as historical UI evidence. |
| `tranception` | Third-party scientific protein-language/retrieval model | **External research reference.** No direct Genesis runtime import. General lesson: retrieved context must be cited and separable from model inference. |
| `vcmi` | Large third-party Heroes III engine fork | **External engine.** No direct import. Potential inspiration for deterministic world simulation requires a separate license and architecture review. |
| `xiaozhi-esp32` | Third-party ESP32 voice/MCP multi-device client | **Edge voice/MCP adapter candidate.** Useful: streaming audio, device-side tools, board abstraction and OTA/version boundaries. Every MCP action needs authentication, capability scope and sensor/action receipts. |

## Immediate imports already represented in v18.7.10

- I0 Frozen Constitution, fresh boundary, isolated `UNREALIZED_MIRROR`, Butterfly Witness and lived proofpack.
- actor life separated from relationship life;
- terminal `SOCIAL_RUPTURE` protects the Free Other while the actor's own path continues;
- signed Bound Assessor policy and derived-weight verification;
- immutable item origin separated from mutable current ownership;
- portable saves exclude private keys and credentials.

## Next canonical candidates

### Genesis Canon Birth Gate

A `CANON_CHANGE_CANDIDATE` must remain noncanonical until a gate records:

- exact source/commit and candidate hash;
- matched control or justified no-control classification;
- deterministic replay or documented nondeterminism;
- Chronicle/HRaiN integrity;
- privacy-export pass;
- Frozen Constitution compatibility;
- negative-result disclosure;
- reviewer and Sovereign decision receipts.

Possible outcomes:

```text
BORN_INTO_CANON
REPLAY_REQUIRED
COUNTERFACTUAL_REQUIRED
PRIVACY_REVIEW_REQUIRED
REJECTED_WITH_EVIDENCE
FAIL_CLOSED
```

### Sensor truth lanes

```text
SENSOR_TRUTH
PREDICTION
MEMORY
INTERPRETATION
UI_FICTION
```

No lane may silently overwrite another. A display animation, LLM sentence or remembered state is never promoted to sensor truth.

### Model route receipt

Every external/local model proposal should carry:

```text
request_sha256
route_policy_sha256
provider
model
fallback_chain
started_at
completed_at
latency_ms
proposal_sha256
canonical_mutation = false
```

### Public discovery

A future `.well-known/janus-genesis.json` may advertise schemas, public keys, protocol versions and privacy-safe endpoints. Discovery grants no trust by itself.

## Explicit non-imports

- mining/Stratum behavior from I0;
- real-money gambling and variable-ratio relationship rewards;
- military kinetic authority or pre-conscious command execution;
- medical diagnostic authority;
- browser-side local-network scanning;
- raw Telegram IDs as authentication;
- API keys in sketches, browser variables or portable saves;
- direct model/MCP/device mutation of canonical state;
- any claim that a simulated Free Other is conscious.

## Seal

> A repository is a witness to an idea, not a command to import it.
>
> Genesis accepts mechanisms only through provenance, controls, compatibility and a visible Birth Gate.

**JANUS MAPS THE ECOSYSTEM BEFORE IT INHERITS FROM IT.**
