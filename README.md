<div align="center">

# Janus Genesis
### Local-first interactive world & AI-assisted game

`portable saves` · `free-form actions` · `optional local AI` · `character agency`

</div>

Janus Genesis is a **creative-technology project**: a persistent interactive world that can run locally, move between chats through portable saves, and optionally use local or user-selected language models for suggestions.

Its mythological, moral and theological vocabulary belongs to the fictional/game system. It is not a scientific evidence line.

## Play / inspect

- **Chat-play guide:** [`PLAY_GENESIS_IN_ANY_AI_CHAT.md`](PLAY_GENESIS_IN_ANY_AI_CHAT.md)
- **Machine entry:** [`ai/GENESIS_UNIVERSAL_CHAT_ENTRY.json`](ai/GENESIS_UNIVERSAL_CHAT_ENTRY.json)
- **Machine-readable project status:** [`PROJECT_STATUS.json`](PROJECT_STATUS.json)
- **Public positioning / claim boundary:** [`PUBLIC_POSITIONING.md`](PUBLIC_POSITIONING.md)

If an AI chat can read public GitHub files, you can ask it to open the chat-play guide. Local Python remains the authoritative runtime when used.

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
- reproducible world/chronicle data structures.

## What is not claimed

```text
MACHINE_CONSCIOUSNESS = NOT_CLAIMED
AGI = NOT_CLAIMED
PRECOGNITION_OR_RETROCAUSALITY = NOT_CLAIMED
THEOLOGICAL_AUTHORITY = NOT_CLAIMED
REAL_WORLD_MORAL_AUTHORITY = NOT_CLAIMED
PUBLIC_PRODUCTION_NETWORK = NOT_CLAIMED
```

Terms such as `God Mode` are defined **game mechanics / narrative vocabulary**. They do not imply authority over real people, theology or physical reality.

## Run locally

Python 3.11+:

```bash
python play_genesis.py
```

Optional Ollama example:

```bash
python play_genesis.py \
  --ai-provider ollama \
  --ai-model llama3.2 \
  --ai-endpoint http://127.0.0.1:11434
```

Keep provider keys in environment variables; do not write them into saves or committed source.

## Portable save

```bash
python play_genesis.py --data-dir data_v17 --export-save my_world.genesis-save.json
python play_genesis.py --data-dir restored --import-save my_world.genesis-save.json
```

Schema: [`schemas/genesis_portable_save_v1.schema.json`](schemas/genesis_portable_save_v1.schema.json)

## Deeper documentation

- [The Free Other](docs/GENESIS_V18_7_FREE_OTHER.md)
- [Connectivity](docs/GENESIS_V18_7_CONNECTIVITY.md)
- [Public positioning](PUBLIC_POSITIONING.md)

Historical versions and longer narrative canon remain in the repository for continuity, but the files above are the preferred reviewer entry points.
