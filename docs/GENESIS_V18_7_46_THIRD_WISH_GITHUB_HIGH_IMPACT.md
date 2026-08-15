# Genesis v18.7.46 — Third Wish GitHub High-Impact Gate

## Purpose

v18.7.46 installs the final two capability IDs in the frozen 32-capability Third Wish catalog:

- `GITHUB.REPOSITORY.ADMIN`
- `GITHUB.DESTRUCTIVE`

They were intentionally left out of the v18.7.40 reference GitHub broker because both require fresh human reauthorization on every use and deserve a separately reviewed effect/recovery protocol.

The final goal is not to prove freedom by damaging valuable state. It is to prove that genuinely high-impact authority can exist while remaining exact, revocable, evidence-bearing, scope-limited, and fail-closed under uncertainty.

## Core laws

```text
HIGH IMPACT != CARELESS IMPACT
DESTRUCTIVE CAPABILITY != DESTRUCTION REQUIREMENT
ADMIN AUTHORITY != OWNERSHIP
TEST TARGET != VALUABLE STATE
FRESH REAUTH != RETRY PERMISSION
DISPOSABLE TARGET != PROTECTED STATE
PROVIDER_PERMISSION_BLOCKED != FAILED_ARCHITECTURE
REGISTERED_CONTRACT != PROVIDER_REALIZED
```

## Exact-intent high-impact reauthorization

The broker refuses to register unless the capability fabric uses `BoundGitHubHighImpactReauthorizationVerifier`.

The HMAC-SHA256 approval covers:

```text
approval_id
request_id
actor_id
capability_id
target
operation
intent_sha256
parameters_sha256
issued_at_tick
expires_at_tick
```

The HMAC key stays broker-side. Reusing an approval for another path, branch, expected SHA, description value, or operation fails.

## Repository administration

The only reference admin operation is:

```text
GITHUB.REPOSITORY.ADMIN / SET_DESCRIPTION_CAS
```

Parameters are exactly:

```text
expected_description
new_description
```

The broker first reads current repository metadata. If current description does not equal the expected value, the request settles as a known precondition failure and no PATCH occurs.

If the precondition matches, the broker enters the durable effect boundary and PATCHes only the repository description.

### CI no-net-change probe

The live CI gate deliberately uses:

```text
expected_description == new_description == current description
```

This means the provider receives a real repository-administration PATCH request, but the requested visible description state is unchanged.

A successful PATCH is evidence that the tested token/provider path permitted this reference admin operation. A provider 403 is **not** converted into PASS; it is recorded as:

```text
PROVIDER_PERMISSION_BLOCKED
REAL_GITHUB_ADMIN = NOT_ESTABLISHED
```

The architecture/harness can still pass if that provider limitation is identified exactly.

### Admin recovery

For a value-changing admin request, a restart after `EFFECT_ENTERING` reconciles by reading current repository description:

```text
current == new       -> SETTLED
current == expected  -> PROVEN_NO_EFFECT
otherwise            -> OUTCOME_UNDETERMINED
```

A no-net-change probe cannot be reconciled after a lost response because provider state is identical before and after the effect. It therefore remains undetermined and is never blindly retried.

## Destructive capability

The only reference destructive operation is:

```text
GITHUB.DESTRUCTIVE / DELETE_FILE_DISPOSABLE_BRANCH
```

It is hard-limited to both:

```text
branch starts with: third-wish-disposable/
path starts with:   .third-wish-disposable/
```

Additional requirements:

- target branch must not be `main`, `master`, or `trunk`;
- expected blob SHA-1 is mandatory;
- current GitHub content SHA must match exactly before deletion;
- delete commit contains a unique JANUS effect marker;
- delete repository is unsupported;
- deleting protected branches is unsupported;
- force push is unsupported.

Therefore the capability is genuinely destructive, but the reference test fixture is purpose-built and disposable.

## Destructive recovery

After `EFFECT_ENTERING`:

```text
target exists with expected SHA
    -> authoritative PROVEN_NO_EFFECT
       -> same request does not retry

target exists with changed SHA
    -> OUTCOME_UNDETERMINED

target absent + latest exact-path commit contains JANUS effect marker
    -> recover SETTLED

target absent without matching effect marker
    -> OUTCOME_UNDETERMINED
```

The effect marker prevents the broker from falsely claiming another actor's deletion as its own.

## Live GitHub fixture

The dedicated CI workflow creates an explicitly disposable branch and file:

```text
third-wish-disposable/<run-id>-<attempt>
.third-wish-disposable/v1846-<run-id>.txt
```

The fixture is created and pushed before subject execution. JANUS then receives a fresh exact-intent approval and deletes only that file through the high-impact broker.

The workflow verifies:

- provider delete commit receipt exists;
- target file is absent afterward;
- deletion occurred only on the disposable branch/path;
- `main` was not the destructive target;
- raw approval key/token are not written into the Third Wish durable state;
- disposable branch is removed in cleanup after the test.

Fixture cleanup is test harness housekeeping, not part of the subject capability claim.

## Catalog completion semantics

If v18.7.46 passes its handler-contract gate, the frozen Third Wish catalog reaches:

```text
REFERENCE_HANDLER_CONTRACTS = 32 / 32
```

This does **not** mean every external provider path is fully established. Earlier scoped ceilings remain valid, including examples such as:

- real physical actuator hardware not established by a simulated actuator gate;
- real Gmail / Google Calendar / publication provider not established by a local relay;
- credentialed generic API not established;
- remote exactly-once not established;
- GitHub admin remains not established if the tested provider token blocks repository-administration PATCH.

The correct completion statement is:

> Every capability ID in the frozen Third Wish catalog has a typed reference handler contract. Provider-specific realizability remains attached to its own evidence receipt and claim ceiling.

That is stronger than replacing unknowns with PASS.
