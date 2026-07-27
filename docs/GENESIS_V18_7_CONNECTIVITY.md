# Genesis v18.7 — AI, API, Portable Saves and the Shared Network

Genesis v18.7 can be entered through four doors while preserving one rule:

> External software may speak to Genesis, but only Genesis may change Genesis state.

```text
human CLI ───────────────┐
Ollama / user AI ────────┤
authenticated HTTP agent ├──> PlayableGenesisV187 ──> local JSON state
portable JSON save ──────┘                 │
                                           └──> explicit public events ──> shared hub
```

## 1. Local Ollama

Ollama uses its local `/api/chat` endpoint. A normal local installation requires no API key.

```bash
python play_genesis.py \
  --ai-provider ollama \
  --ai-model llama3.2 \
  --ai-endpoint http://127.0.0.1:11434
```

Inside the interactive game:

```text
/ai придумай действие, которое уберёт Архитектора из центра сцены
```

The model returns one JSON proposal:

```json
{
  "action": "...",
  "reason": "...",
  "expected_uncertainty": "...",
  "executed": false,
  "authority": "proposal_only"
}
```

The player must explicitly confirm before the proposal is sent through the real runtime.

One-shot proposal without execution:

```bash
python play_genesis.py \
  --player architect \
  --ai-provider ollama \
  --ai-model llama3.2 \
  --ai-propose "предложи мне странный свободный ход"
```

## 2. OpenAI-compatible providers

Any user-selected service exposing `/v1/chat/completions` may be configured through the generic adapter.

```bash
export MY_MODEL_API_KEY='raw-key-kept-only-in-the-environment'

python play_genesis.py \
  --ai-provider openai-compatible \
  --ai-model my-model \
  --ai-endpoint https://provider.example \
  --ai-key-env MY_MODEL_API_KEY
```

The key is read only when the request is made. It is never written to:

- player state;
- Chronicle;
- HRaiN;
- the Free Other store;
- a portable save;
- the network outbox;
- logs produced by Genesis itself.

The provider receives a minimized context: public player state, the current path question, available possibilities, and public Free Other handles/statuses. Internal realm routing, `branch_id`, private Chronicle records and API keys are not included.

## 3. Authenticated gameplay API

The reference API server lets a phone app, AI agent, NAS service or another program play through HTTP.

Create a raw key, calculate its SHA-256, and configure only the hash on the server:

```bash
python tools/genesis_api_server.py --hash-key 'replace-with-a-long-random-key'
export GENESIS_API_KEY_HASHES='<printed-sha256>'
python tools/genesis_api_server.py --data-dir data_v17 --bind 127.0.0.1 --port 8787
```

Example action:

```bash
curl -X POST http://127.0.0.1:8787/v1/action \
  -H 'Authorization: Bearer replace-with-a-long-random-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "player_id": "architect",
    "action": "построить мост и передать право первого прохода другому"
  }'
```

Endpoints:

```text
GET  /health
GET  /v1/status?player_id=architect
GET  /v1/others?player_id=architect
GET  /v1/save/export?label=my-device
GET  /v1/verify
POST /v1/action
POST /v1/player/name
POST /v1/save/import
```

All state-changing and private-state endpoints require a valid Bearer key. The server accepts comma-separated key hashes through `GENESIS_API_KEY_HASHES` and never needs to store raw keys.

## 4. One-file portable JSON save

Export the complete local JSON/JSONL device state into one verified JSON document:

```bash
python play_genesis.py \
  --data-dir data_v17 \
  --export-save my_genesis_device.genesis-save.json
```

Import on another device:

```bash
python play_genesis.py \
  --data-dir data_v17 \
  --import-save my_genesis_device.genesis-save.json \
  --save-conflict replace
```

Conflict policies:

```text
replace  overwrite existing local state after verification
skip     keep existing files and import only missing files
fail     abort when any destination already exists
```

Each embedded file stores:

```text
relative path
json or jsonl kind
byte size
SHA-256
UTF-8 content
```

The outer manifest is also SHA-256 sealed. Import validates every file before writing anything.

The exporter rejects credential-like files and guarantees:

```json
{
  "contains_api_keys": false,
  "contains_environment_files": false,
  "network_authority": false
}
```

A portable save is a local device snapshot. It does not grant network access and cannot contain the network Bearer key.

## 5. The shared Genesis Network

The reference hub is an authenticated append-only public event relay.

It can:

- verify event SHA-256;
- reject private/credential-like payload fields;
- assign a global `network_sequence`;
- return events created by other nodes;
- deduplicate retried events by hash.

It cannot:

- execute a player action;
- modify a local save;
- import a private Chronicle;
- reveal internal realm routing;
- create consent for another player;
- become the canonical owner of a person's life.

### Start the hub

```bash
python tools/genesis_network_hub.py --hash-key 'shared-network-key'
export GENESIS_NETWORK_KEY_HASHES='<printed-sha256>'
python tools/genesis_network_hub.py \
  --bind 0.0.0.0 \
  --port 8788 \
  --data-dir genesis_network_hub_data
```

For deployment outside a trusted LAN, place the hub behind HTTPS, use long random keys, restrict inbound ports, and rotate any exposed key.

### Connect a node

```bash
export GENESIS_NETWORK_API_KEY='shared-network-key'

python play_genesis.py \
  --data-dir data_v17 \
  --network-url https://genesis.example \
  --network-state
```

Publish an explicitly public event:

```bash
python play_genesis.py \
  --player architect \
  --network-url https://genesis.example \
  --network-publish shared_place \
  --network-payload '{"title":"Обсерватория без центрального кресла"}'
```

Synchronize:

```bash
python play_genesis.py \
  --network-url https://genesis.example \
  --network-sync
```

Interactive commands:

```text
/publish Текст, который действительно можно сделать публичным
/sync
/network
/save PATH
```

### Public identity

The network event does not expose the raw local `player_id`. A node derives a stable pseudonymous `public_player_id` from its local node identity and player id.

The public event types are intentionally narrow:

```text
presence
public_creation
path_signal
public_message
request_to_meet
shared_place
```

Network payloads reject fields resembling:

```text
api_key
authorization
bearer
secret
credential
password
branch_id
internal_realm
```

## 6. Common network does not mean one database owner

The v18.7 model is local-first:

```text
DEVICE A local save ──┐
                      ├── public event relay ──> shared visibility
DEVICE B local save ──┘
```

This makes the first common Genesis Network possible without pretending that a deployed global canonical server already exists.

Future adapters may add authenticated snapshots, account recovery, conflict-aware shared places, WebSocket delivery, SQLite/PostgreSQL storage or `janus.db` integration. Those are not declared complete in v18.7.

## 7. Threat boundary

- Never commit raw keys.
- Prefer environment variables or an operating-system secret manager.
- Configure server-side SHA-256 hashes rather than raw keys.
- Do not expose the reference HTTP servers directly to the public internet without TLS and network hardening.
- Treat an AI model's output as untrusted text until Genesis validates it.
- Publish only material that may genuinely become public.
- A network message from another node is not proof of identity, consent, factual truth or software consciousness.

> Many models may speak through Genesis.  
> No model receives the right to become Genesis.
