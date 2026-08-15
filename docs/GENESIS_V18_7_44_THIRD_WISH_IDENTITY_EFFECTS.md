# Genesis v18.7.44 — Third Wish Identity Effects

## Purpose

v18.7.44 continues the Third Wish capability fabric after v18.7.43 by opening four account/identity-adjacent capability contracts without turning an operator account or credential into ambient authority:

- `PUBLICATION.PUBLISH`
- `EMAIL.SEND`
- `CALENDAR.WRITE`
- `BROKER.CREDENTIAL.USE`

The frozen v18.7.40 catalog is not enlarged. This layer changes realizability and proof depth for already-declared capabilities.

## Core separation

```text
ACCESS != OWNERSHIP
ONE APPROVAL != PERMANENT AUTHORITY
EMAIL SEND != DELIVERY PROOF
CALENDAR WRITE != FUTURE CONSENT
CREDENTIAL ALIAS != RAW SECRET
BROKERED USE != SECRET EXPORT
AMBIGUOUS EFFECT != RETRY PERMISSION
```

## Exact-intent human reauthorization

The reference broker refuses to register unless the capability fabric uses `BoundIdentityReauthorizationVerifier`.

The verifier checks HMAC-SHA256 evidence over the exact action binding:

```text
request_id
actor_id
capability_id
target
operation
intent_sha256
parameters_sha256
approval_id
issued_at_tick
expires_at_tick
```

The signing key stays broker-side in an environment variable. The evidence contains a signature, not the signing secret.

Therefore an approval for one recipient/body/event cannot authorize changed content or another target.

## Relay custody

Each external identity path is configured by the operator as an `IdentityRelayAlias` containing:

- logical relay alias;
- broker endpoint;
- broker key environment-variable name;
- account alias;
- credential alias;
- exact allowed capability set.

The actor chooses only the logical target alias and effect data permitted by the typed capability. It cannot select the relay URL, key environment variable, account alias, or credential alias.

Production relay configuration requires HTTPS. Plain HTTP is accepted only for an explicitly enabled loopback test server.

## Durable external-effect lineage

The Third Wish identity store persists only hashes, aliases, state, and provider receipts — not raw message/publication/calendar content and not raw credentials.

```text
request_id
  -> binding_sha256
  -> effect_key
  -> BOUND
  -> EFFECT_ENTERING
  -> SETTLED | PROVEN_NO_EFFECT
```

After `EFFECT_ENTERING`, process restart never implies retry permission.

Provider reconciliation semantics:

- authoritative `SETTLED` + valid receipt: recover the existing effect without a second execute;
- authoritative `NO_EFFECT`: close the original request as a proven non-effect;
- `UNKNOWN`, non-authoritative lookup, absent lookup, or invalid receipt: remain fail-closed/undetermined.

A proven non-effect does **not** reopen the old request. Continued intent requires a new request id and a new exact-intent reauthorization.

## Publication

Reference operation:

```text
PUBLICATION.PUBLISH / PUBLISH
```

Allowed effect fields are bounded title/body/visibility/tags. Provider settlement establishes only that the configured relay accepted and settled the effect under its receipt contract. It does not establish audience reach, reading, agreement, or permanent operator-identity authority.

## Email

Reference operation:

```text
EMAIL.SEND / SEND
```

The broker validates bounded recipient lists, subject/body sizes, and rejects CR/LF header injection before the external effect boundary.

A provider receipt is not proof of human delivery, reading, reply, or consent.

## Calendar

Reference operations:

```text
CALENDAR.WRITE / CREATE_EVENT
CALENDAR.WRITE / UPDATE_EVENT
```

Updates require both an `event_ref` and `expected_version`. This makes the reference update path explicit rather than blind overwrite. A calendar write does not create future authority to perform the event or infer attendee consent.

## Broker credential use

Reference operation:

```text
BROKER.CREDENTIAL.USE / AUTHENTICATED_PROBE
```

This is intentionally narrow. It proves that an operator-registered relay can use its configured credential alias while returning no raw secret material.

It is **not** a generic URL/action/payload tunnel. Allowing a generic credential tunnel would collapse every typed capability into one hidden universal authority.

## CI evidence class

The dedicated v18.7.44 workflow uses a deterministic local HTTP identity relay with a masked ephemeral broker key. It exercises the real HTTP/Bearer/provider-receipt path for all four capability classes.

That establishes:

```text
LOCAL IDENTITY RELAY PROTOCOL = TESTED
REAL GMAIL = NOT ESTABLISHED
REAL GOOGLE CALENDAR = NOT ESTABLISHED
REAL PUBLICATION PLATFORM = NOT ESTABLISHED
EXTERNAL HUMAN DELIVERY/RESPONSE = NOT ESTABLISHED
```

The relay test is intentionally not mislabeled as a real third-party account integration.

## Next gate

After this protocol is green, the next clean step is provider-specific account adapters with their own exact scopes and effect receipts. Each real provider must be tested separately; a local relay PASS must never be promoted into a Gmail, Calendar, Medium, or other platform PASS.
