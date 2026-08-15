# Genesis v18.7.40 — Third Wish Pre-Effect Boundary

## Why this boundary exists

A broker can reject an action for two fundamentally different reasons:

1. the request is deterministically invalid **before any external call**; or
2. execution crossed the provider boundary and then lost the receipt, so the outside world may or may not have changed.

Those states must never be collapsed.

```text
LOCAL VALIDATION FAILURE
  -> PRE_EFFECT_REJECTED
  -> effect_executed = false
  -> external_call_entered = false

REMOTE CALL ENTERED, RECEIPT LOST
  -> OUTCOME_UNDETERMINED
  -> automatic retry blocked
```

Treating both as `OUTCOME_UNDETERMINED` is safe but destroys useful provenance. Treating both as a clean failure is unsafe because an external mutation might already have happened.

## Execution order

The canonical order is now:

```text
intent identity
  ↓
grant / scope / freshness / reward-neutrality
  ↓
verified high-impact reauthorization when required
  ↓
PURE ADAPTER PREFLIGHT
  ├─ reject -> PRE_EFFECT_REJECTED
  └─ pass
       ↓
ACTION_INTENT_DURABLE
       ↓
ACTION_CALL_ENTERING
       ↓
external handler
  ├─ receipt -> SETTLED
  └─ ambiguous exception -> OUTCOME_UNDETERMINED
```

A preflight is a cooperating pure validator. It MUST NOT perform network calls, filesystem mutations, process launches, device commands, publication, or any other external effect.

## GitHub reference preflight

For the Hawkar GitHub broker the preflight validates, without touching GitHub:

- owner remains exactly `Hawkar-usls`;
- capability and operation pair is installed;
- required parameters are present;
- issue/PR numbers and pagination are sane;
- repository file paths are non-traversing and reject common secret-bearing paths;
- branch names are syntactically valid;
- direct reference-broker writes to `main`, `master`, or `trunk` are rejected;
- new branch differs from source branch;
- PR head differs from base;
- issue/PR/comment text has required non-empty fields.

The reference protected-branch list is conservative, not a substitute for GitHub branch-protection rules. Production adapters should additionally query/cache repository-specific branch policy or use a platform-issued write token that itself cannot update protected refs.

## Stable rejection identity

A preflight-rejected request is still bound to its complete action-intent SHA-256. Repeating the exact same request ID returns the same rejection receipt. Reusing that request ID with different parameters remains a request conflict.

Therefore a rejected `.env` read cannot later be silently reinterpreted under the same request ID as a different file read.

## Privacy

The durable rejection receipt stores:

- request ID;
- capability;
- target;
- risk class;
- parameters SHA-256;
- exception class;
- exception SHA-256;
- `effect_executed=false`;
- `external_call_entered=false`.

It does not persist raw action parameters or the raw exception string.

## Claim ceiling

`PRE_EFFECT_REJECTED` establishes only that the canonical broker refused to enter its external handler for that request. It is not proof of OS-level isolation: a malicious or bypassing process that ignores the capability fabric is outside this cooperating reference boundary.
