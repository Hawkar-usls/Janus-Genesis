# Genesis v18.7.20 — One-Link Hosted Pilgrimage audit

## Scope

This report seals the pre-merge verification of the hosted continuation bridge
introduced by PR #59.

The bridge lets a link-reading AI continue one Genesis session across chat
messages through a bounded hosted protocol while preserving the existing
v18.7.19 authority boundary:

```text
repository link
  -> AI_ENTRY.md
  -> ai/GENESIS_HOSTED_ENTRY.json
  -> verified HTTPS discovery
  -> short-lived signed session
  -> GenesisAILinkGateway
  -> PlayableGenesisV187
```

The hosted layer is not a world-state writer. All authoritative outcomes remain
mediated by `PlayableGenesisV187`.

## Verified candidate

```text
branch: codex/genesis-v18-7-20-one-link-hosted-pilgrimage
candidate commit: 2de48a0b1c95da75530cf1cb53ede2fc0f44a3ea
base main: 4242e285c9d84cd4548ee71ee4eb26bf32aff12f
Python: 3.11
complete unit suite: 362 / 362 PASS
```

The following workflows succeeded on the candidate commit:

- Hosted Pilgrimage
- AI Link Play
- Genesis Tests
- Python test matrix
- Genesis century lived audit
- Threshold review precision

## Main hosted pilgrimage proofpack

GitHub Actions artifact:

```text
name: genesis-one-link-hosted-pilgrimage-audit
artifact id: 8778561967
artifact digest: sha256:e16710a4bd46e50f9929ad0d268b929a4c42df8587a6e13badb543fc0069cbdc
inner audit ZIP SHA-256: f74ae48f749cbcc9b1c0aa5f05b03020578f61a0e54c61beb29dede75e48e18f
proofpack JSON SHA-256: e4f4a47262e2e874608ced701fc786be1f0ac0299a3d3dd79a7e8b362396bdd0
summary SHA-256: f90c1d44f7d70a98824a3c6d34b9f9be0bd1919e142e24e80ce82fa8437e6aae
```

Result:

```text
PASS
20 / 20 lived invariants
execution mode: AUTHORITATIVE_RUNTIME
authoritative turns: 4
fallback events: 1
idempotency records: 4
AI Link integrity: valid
hosted integrity: valid
```

The lived path reached these real runtime statuses:

1. `FIFTH_SHORE_ENTERED_FROM_MAIN_GENESIS`
2. `FIFTH_SHORE_JOY_WITHOUT_REPAIR`
3. `FIFTH_SHORE_SYSTEMIC_WOUND_CONFRONTED`
4. `FREE_ACTION_LIVED`

The same committed idempotency key returned the original turn instead of
executing twice. Activating the kill-switch produced an explicitly
non-authoritative fallback and did not write the paused action to the world.
After the runtime returned, the same unexecuted action and key could safely be
submitted and executed once.

The session closed voluntarily with:

```text
moral_failure_assigned = false
return_open = true
```

The public capsule and proofpack contained no bearer token, host secret, raw
client identifier, display name, provider name, model label, or free action
text.

## Hosted crash and integrity precision proofpack

GitHub Actions artifact:

```text
name: genesis-hosted-precision-audit
artifact id: 8778562094
artifact digest: sha256:e4b04b3d48d904f76c851540f653e1c1786d30d13b85a00494585cd863e03295
inner audit ZIP SHA-256: d71e5771fc32c18d190413321b830f9646750e03b79b853eda13b9764621b242
proofpack JSON SHA-256: d1c3cfef52ebe9af27c9621242e18e93001ab42a0085e79aa77ad2dc9a6877e2
summary SHA-256: 1c66c792b84828dfe238cdf7ce93d999672e13dbedd76403192fb54ba60745fd
```

Result:

```text
PASS
15 / 15 lived invariants
errors: []
```

### Crash after the world turn

The hosted bridge durably wrote an `IN_FLIGHT` intent before entering the
runtime. A simulated process crash then occurred after the AI Link turn was
persisted but before the hosted receipt became `COMMITTED`.

On retry, the bridge located one exact turn using the expected sequence,
action hash, origin, confirmation state, and previous turn hash. It repaired
the receipt and returned the original turn as an idempotent replay. The
canonical turn count remained one.

### Crash before the world turn

A simulated process crash occurred after the durable `IN_FLIGHT` intent but
before the action reached the runtime. Because no exact persisted turn could be
proven, the bridge rejected the retry with:

```text
HOSTED_IDEMPOTENCY_RECOVERY_REQUIRED
```

The canonical turn count remained zero and health reported:

```text
status = RECOVERY_REQUIRED
authoritative_runtime_available = false
```

The bridge chose uncertainty and operator recovery over a possible duplicate
canonical action.

### Corrupted AI Link integrity

After the underlying AI Link session hash was deliberately corrupted, health
reported:

```text
status = FAILED_GATEWAY_INTEGRITY
authoritative_runtime_available = false
```

A new authoritative request received a stateless narrative fallback:

```text
session = null
session_token = null
canonical_runtime_outcome_recorded = false
```

No new session was written to the corrupted store.

## Review findings resolved in the implementation

Four P1 findings were addressed before merge:

1. Durable `IN_FLIGHT` intent and crash recovery were added before/after the
   canonical runtime boundary.
2. Hosted availability and health now fail closed on invalid AI Link integrity,
   invalid hosted integrity, or unresolved idempotency recovery.
3. The lived-audit runner adds the repository root to `sys.path` and works via
   the documented direct command.
4. The independent-origin test now enters the Fifth Shore before requesting a
   Fifth Shore joy action, preserving the spatial permission boundary.

## Deployment boundary

This report verifies deployable software, not a public deployment.

The static manifest remains intentionally sealed as:

```text
deployment.status = DEPLOYMENT_REQUIRED
deployment.public_base_url = null
```

Therefore a repository link proves that the hosted protocol exists but does
not prove that a public authoritative gateway is online. Public use requires a
separate reviewed deployment with HTTPS, secret management, backups,
monitoring, rate limits, a working kill-switch, and a later manifest update to
a verified URL.

## Claim boundary

This is deterministic software and narrative-simulation evidence. It does not
establish model consciousness, sentience, human identity, legal personhood,
spiritual authority, divine status, or privileged access.
