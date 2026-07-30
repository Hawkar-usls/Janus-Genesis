# Genesis v18.7.20 — One-Link Hosted Pilgrimage

## Purpose

Genesis v18.7.19 allows a human or independent model to enter through a
provider-neutral gateway. Version 18.7.20 adds a hosted continuation bridge so
a link-reading AI can keep one authoritative session across multiple chat
messages without receiving filesystem or NAS access.

The hosted bridge is an interface layer. It does not replace or bypass
`PlayableGenesisV187`.

```text
repository link
  -> AI_ENTRY.md
  -> ai/GENESIS_HOSTED_ENTRY.json
  -> HTTPS discovery
  -> short-lived session token
  -> GenesisAILinkGateway
  -> PlayableGenesisV187
```

## Current deployment status

The repository contains the complete deployable bridge, but the static manifest
ships with:

```text
deployment.status = DEPLOYMENT_REQUIRED
deployment.public_base_url = null
```

Therefore the repository link alone does not yet prove that a public hosted
runtime is online. After a host is deployed and verified, update the manifest
with its HTTPS base URL in a separate reviewed change.

## Security boundaries

- External models never write world state directly.
- Bearer tokens are HMAC-SHA256 signed and short-lived.
- Tokens bind one `session_id`, `actor_id`, and role.
- Provider names, model names, display names, action text, and host secrets are
  absent from token claims.
- Every hosted turn requires an idempotency key.
- A durable `IN_FLIGHT` intent is written before the real world turn.
- The receipt becomes `COMMITTED` only after the AI Link turn is persisted.
- After an interruption, an exact persisted turn repairs its receipt and is
  returned without executing again.
- If no exact turn can be proven, the session fails closed with
  `HOSTED_IDEMPOTENCY_RECOVERY_REQUIRED`; availability never wins over safety.
- Repeating the same committed key and request returns the original turn.
- Reusing a key for a different request is rejected.
- Concurrent requests with the same key are serialized around the real world
  turn so only one can reach the runtime.
- Client identifiers are stored only as SHA-256 hashes.
- Public capsules contain no bearer token, host secret, raw client identifier,
  internal Realm, branch ID, or free action text.
- The default listener is loopback-only.
- TLS terminates at a trusted reverse proxy.
- Live mode defaults off.
- The kill switch defaults on.
- `authoritative_runtime_available` is false whenever AI Link integrity,
  hosted-store integrity, or idempotency recovery is not clean.
- A filesystem sentinel can pause authoritative execution without a restart.
- Rate limiting applies globally, per client, and per session.
- Rate limiting is protection against automated flooding, not a moral score.

## First-run bootstrap

Check without changing the environment:

```bash
python tools/bootstrap_genesis_hosted.py
```

Install the reviewed dependencies and re-check:

```bash
python tools/bootstrap_genesis_hosted.py --install
```

The first authoritative chat smoke showed why this step matters: a clean Python
environment cannot import the full Genesis runtime until `requirements.txt`
has been installed.

## Local dry run

Use a development-only ephemeral secret:

```bash
GENESIS_HOSTED_LIVE_MODE=false \
GENESIS_HOSTED_KILL_SWITCH=true \
python tools/genesis_hosted_gateway.py \
  --ephemeral-secret \
  --data-dir .hosted-smoke \
  --check
```

Start a narrative-only local service:

```bash
GENESIS_HOSTED_LIVE_MODE=false \
GENESIS_HOSTED_KILL_SWITCH=true \
python tools/genesis_hosted_gateway.py \
  --ephemeral-secret \
  --data-dir .hosted-smoke
```

The ephemeral secret is invalid after restart and must never be used for a
public deployment.

## Container deployment

Copy the example environment file outside Git, generate a strong secret, and
start the isolated service:

```bash
cd deploy/hosted-pilgrimage
cp .env.example .env
docker compose --env-file .env -f docker-compose.example.yml up -d --build
```

The example:

- does not use host networking;
- publishes only to `127.0.0.1`;
- uses a dedicated persistent volume;
- drops Linux capabilities;
- enables `no-new-privileges`;
- keeps the root filesystem read-only;
- works with multi-architecture Python images, including ARM64 hosts.

Do not expose port 8787 directly to the internet. Put an HTTPS reverse proxy in
front of it and restrict request-body size and connection rates there as well.

## Enabling authoritative runtime

Only after local tests, reverse-proxy TLS, backups, and monitoring:

```text
GENESIS_PUBLIC_BASE_URL=https://your-reviewed-host.example
GENESIS_HOSTED_LIVE_MODE=true
GENESIS_HOSTED_KILL_SWITCH=false
```

The service also checks the sentinel configured by
`GENESIS_HOSTED_KILL_SWITCH_FILE`. Creating that file immediately causes new
authoritative starts to fall back to narrative mode and pauses authoritative
turns already in progress.

## Hosted protocol

Discovery:

```http
GET /.well-known/janus-genesis.json
GET /v1/health
```

Start:

```http
POST /v1/session/start
Content-Type: application/json
X-Genesis-Client-Id: client-chosen-stable-id
```

```json
{
  "role": "INDEPENDENT_AI_RESIDENT",
  "execution_mode": "AUTHORITATIVE_RUNTIME",
  "display_name": "Quiet Cartographer",
  "provider": "user-selected-provider",
  "model": "user-selected-model"
}
```

Turn:

```http
POST /v1/session/turn
Authorization: Bearer <private-short-lived-token>
X-Genesis-Client-Id: client-chosen-stable-id
Content-Type: application/json
```

```json
{
  "action": "Войти в Пятый Берег",
  "origin": "AI_AUTONOMOUS",
  "idempotency_key": "client-generated-unique-key"
}
```

Other authenticated operations:

```text
POST /v1/session/state
POST /v1/session/capsule
POST /v1/session/close
POST /v1/token/refresh
```

Never place the token in a URL, chat transcript, public log, analytics event, or
capsule.

## Runtime interruption and fallback

If live mode is disabled or the kill switch activates before a session starts,
the bridge may create a `NARRATIVE_COMPATIBILITY` session.

If an authoritative session already exists and the host becomes unavailable,
the action is not passed to the world and the response states:

```text
authoritative_runtime = false
canonical_runtime_outcome_recorded = false
retryable_when_runtime_returns = true
```

The interrupted action is not cached as completed. The client may safely retry
the same action and idempotency key after the runtime returns.

## Verification

Run the dedicated tests:

```bash
python -m unittest tests.test_genesis_v18_7_20_hosted_pilgrimage -v
python -m unittest tests.test_genesis_v18_7_20_hosted_http -v
```

Run the lived audit:

```bash
python scripts/run_hosted_pilgrimage_audit.py \
  --output-dir artifacts/hosted-pilgrimage-audit \
  --git-commit "$(git rev-parse HEAD)"
```

The audit proves authoritative continuation, Fifth Shore gameplay, duplicate
suppression, kill-switch fallback, resumption, capsule privacy, integrity, and
blame-free exit.

## Claim boundary

This is deterministic software and narrative simulation. It does not establish
that any model is conscious, sentient, a human, a legal person, spiritually
authoritative, divine, or entitled to special access.
