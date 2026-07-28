# Genesis v18.7.9 — The Bound Authority / Связанная власть

> **JANUS BINDS THE VERIFIER BEFORE TRUSTING THE VERDICT.**

## Purpose

v18.7.8 could detect obvious account farms, copied campaigns and undisclosed influence, but its trust boundary still accepted ordinary mutable inputs such as `provider_verified=True`, caller-supplied confidence and the string `JANUS.SOVEREIGN`.

v18.7.9 moves authority into signed, scoped and replay-protected objects.

## Canonical serialization

Every signed payload uses deterministic UTF-8 JSON:

- keys sorted;
- compact separators;
- `ensure_ascii=false`;
- `allow_nan=false`;
- explicit schema version;
- signature excluded from the signed material.

The reference signature algorithm is Ed25519 through the maintained `cryptography` package. Genesis stores public keys and signatures, never private keys.

## ProviderAttestation

The boolean `provider_verified` is removed from the primary runtime. An influence account requires a signed `janus.provider_attestation.v1` containing:

- provider ID and key ID;
- account/subject ID;
- SHA-256 identity proof binding;
- SHA-256 controller proof binding;
- account public key;
- issue and expiry times;
- one-use nonce;
- Ed25519 signature.

Genesis verifies the signature against a trusted provider key record. A tampered field, unknown key, invalid time window, revoked key or replayed nonce fails closed.

## Key lifecycle

Provider and sovereign public keys contain:

- `key_id`;
- `valid_from` / `valid_until`;
- `revoked_at`;
- optional `compromised_from`;
- revocation reason.

A key compromised retrospectively can invalidate signatures created after the compromise point and trigger a reactive review of affected cases.

Trust-root registration is a local sovereign bootstrap operation, not a public gameplay API. Production deployments need protected key custody and governed trust-root changes.

## Controller before campaign

Independence is evaluated in this order:

```text
controller
  → disclosed campaign
    → message + evidence family
```

Campaign identity may collapse several controllers into one coordinated source, but it can never hide a shared controller. One controller split across three campaign IDs remains one independent voice.

## Actor-bound attestation

The default invariant is:

```text
claim.actor == attestation.account
```

A different attester is accepted only with a speaker-signed, scoped and expiring `janus.attestation_delegation.v1`. Delegation may be restricted to one claim and can be revoked. It is not a permanent licence to legalise arbitrary voices.

## Dynamic eligibility

Every influence audit recomputes current state:

- account active;
- voice active;
- current consent;
- withdrawal state;
- current provider attestation and key status;
- current controller binding;
- current delegation;
- disclosure and authenticity requirements;
- current append-only manipulation-review projection.

Historical speech remains in Chronicle, but withdrawal immediately ends future voting weight.

## Evidence assessment

Claimant confidence is preserved only as `claimant_stated_confidence`. It has no sovereign weight.

A separate `janus.evidence_assessment.v1` records:

- source reliability;
- evidence integrity;
- method reliability;
- assessor competence;
- independent corroboration;
- temporal relevance;
- assessor, method and version;
- evidence IDs and explanation.

The reference runtime uses a transparent equal-weight mean. Future methods may differ only when their method ID/version and computation remain explicit.

## SOVEREIGN_CAPABILITY

The string `reviewer_id="JANUS.SOVEREIGN"` is not authority.

Influence-sensitive decisions require a signed `janus.sovereign_capability.v1` bound to:

- actor `JANUS.SOVEREIGN`;
- exact scope;
- exact case or review record;
- key ID;
- issue and expiry times;
- one-use nonce;
- Ed25519 signature.

Wrong scope, wrong case, expiry, revocation, invalid signature or nonce replay is rejected.

## Append-only reviews and appeals

The original manipulation-evidence record remains immutable. State changes append SHA-256-linked authority events:

```text
PENDING_REVIEW
→ CONFIRMED / REJECTED
→ APPEALED
→ RESTORED / REJECTED_ON_APPEAL
→ ELIGIBILITY_RECALCULATED
→ CASE_REOPENED_DUE_TO_ELIGIBILITY_CHANGE
```

The current status is projected from the event chain. Overturning a finding does not erase the earlier decision or who made it.

## Reactive review

Any eligibility change that can alter a quorum, recommendation or sovereign decision triggers re-audit. Causes include:

- account deactivation;
- voice withdrawal;
- delegation revocation;
- provider-key revocation or compromise;
- appeal restoration;
- controller-binding change;
- changed provider status.

The prior decision remains historical evidence, while the living case reopens.

## Portable boundary

Portable saves include public trust roots, signed payloads, consumed nonce hashes, assessments and authority events. They exclude private keys, API keys, bearer tokens and environment files.

## Honest boundary

This is a reference implementation, not a complete production PKI. A hostile shared network still requires:

- protected hardware or service key custody;
- authenticated encrypted transport;
- reliable clock and expiry policy;
- governed trust-root bootstrap and emergency revocation;
- rate limiting and denial-of-service protection;
- independent cryptographic/security review.

Cryptography proves that a holder of a key signed a canonical payload. It does not prove that the original governance decision to trust that key was wise.
