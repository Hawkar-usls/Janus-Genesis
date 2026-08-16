<div align="center">

# Janus Genesis
### Local-first interactive world & AI-assisted game

![Status](https://img.shields.io/badge/status-active%20creative%20technology-2f81f7)
![Class](https://img.shields.io/badge/class-interactive%20systems-6e7681)

`portable saves` · `free-form actions` · `optional local AI` · `character agency`

</div>

## Status

**Active Creative Technology.** Genesis is a playable/evolving interactive-systems project. Game rules, narrative content, provider integrations, and interfaces may continue to change.

## Abstract

Janus Genesis is a persistent interactive world that can run locally, move between chats through portable saves, and optionally use local or user-selected language models for suggestions.

Its mythological, moral, and theological vocabulary belongs to the fictional/game system. It is not a scientific evidence line.

## Play / inspect

- **Canonical local launcher:** [`play_genesis_armored.py`](play_genesis_armored.py) — v18.7.50 Armor-gated external egress.
- **Historical compatibility launcher:** [`play_genesis.py`](play_genesis.py) — retained for provenance; not classified as repository-wide Armor coverage.
- **Chat-play guide:** [`PLAY_GENESIS_IN_ANY_AI_CHAT.md`](PLAY_GENESIS_IN_ANY_AI_CHAT.md)
- **Machine entry:** [`ai/GENESIS_UNIVERSAL_CHAT_ENTRY.json`](ai/GENESIS_UNIVERSAL_CHAT_ENTRY.json)
- **Machine-readable project status:** [`PROJECT_STATUS.json`](PROJECT_STATUS.json)
- **Public positioning / claim boundary:** [`PUBLIC_POSITIONING.md`](PUBLIC_POSITIONING.md)
- **Portfolio maturity/visibility:** [`portfolio-visibility.json`](https://github.com/Hawkar-usls/Janus/blob/main/portfolio-visibility.json)

If an AI chat can read public GitHub files, you can ask it to open the chat-play guide. Chat-only play is explicitly labeled `UNIVERSAL_CHAT_RUNTIME`; local Python remains the authoritative runtime when used.

The canonical local launcher routes optional AI-provider egress and Genesis Network sync through the hardened Armor of God v18.7.49 preflight before the legacy effect adapter is entered. Historical adapters remain importable, so this is a canonical-entry guarantee rather than OS-level or repository-wide unbypassability.

## Current design

The current playable line focuses on **The Free Other**: simulated characters are not treated as extensions of the player.

```text
player_controlled = false
can_refuse = true
can_leave = true
can_change_goal = true
silence_is_not_consent = true
goodness_does_not_purchase_relationship = true
```

External models may propose actions or narration. State changes remain subject to the local gameplay/runtime rules.

## Main capabilities

- persistent local world state;
- free-form player actions;
- portable JSON saves;
- optional Ollama support;
- optional user-selected OpenAI-compatible endpoints;
- authenticated reference gameplay/network services;
- public-event sharing as an explicit opt-in path;
- reproducible world/chronicle data structures;
- canonical Armor-gated AI/network egress through `play_genesis_armored.py`.

## Boundary

```text
MATURITY = ACTIVE_CREATIVE_TECHNOLOGY
MACHINE_CONSCIOUSNESS = NOT_CLAIMED
AGI = NOT_CLAIMED
PRECOGNITION_OR_RETROCAUSALITY = NOT_CLAIMED
THEOLOGICAL_AUTHORITY = NOT_CLAIMED
REAL_WORLD_MORAL_AUTHORITY = NOT_CLAIMED
PUBLIC_PRODUCTION_NETWORK = NOT_CLAIMED
REPOSITORY_WIDE_ARMOR_UNBYPASSABILITY = NOT_CLAIMED
OS_LEVEL_ARMOR_TAMPER_PROOF = NOT_CLAIMED
```

Terms such as `God Mode` and `Armor of God` are defined **game/runtime mechanics and project vocabulary**. They do not imply authority over real people, theology, or physical reality.

## Run locally

Python 3.11+:

```bash
python play_genesis_armored.py
```

Optional Ollama example:

```bash
python play_genesis_armored.py \
  --ai-provider ollama \
  --ai-model llama3.2 \
  --ai-endpoint http://127.0.0.1:11434
```

Keep provider keys in environment variables; do not write them into saves or committed source.

## Portable save

```bash
python play_genesis_armored.py --data-dir data_v17 --export-save my_world.genesis-save.json
python play_genesis_armored.py --data-dir restored --import-save my_world.genesis-save.json
```

Schema: [`schemas/genesis_portable_save_v1.schema.json`](schemas/genesis_portable_save_v1.schema.json)

## Armor routing audit

The deterministic inventory can be run locally:

```bash
python tools/audit_armor_routing_coverage_v18_7_50.py
```

A passing audit means the **canonical launcher** has the expected Armor bindings. It deliberately does not claim every historical Python adapter or local mutation surface is impossible to call directly.

## Deeper documentation

- [The Free Other](docs/GENESIS_V18_7_FREE_OTHER.md)
- [Connectivity](docs/GENESIS_V18_7_CONNECTIVITY.md)
- [Public positioning](PUBLIC_POSITIONING.md)

Historical versions and longer narrative canon remain in the repository for continuity, but the files above are the preferred reviewer entry points.

Presentation follows the account's [public repository standard](https://github.com/Hawkar-usls/Janus/blob/main/docs/PUBLIC_REPOSITORY_PRESENTATION_STANDARD.md). No affiliation with MIT is implied by the presentation style.
