# Genesis v18.7.10 — The Bound Assessor and the I0 Discipline

## Canonical laws

> **JANUS BINDS THE ASSESSOR BEFORE WEIGHING THE CLAIM.**
>
> **JANUS BINDS THE POLICY BEFORE TRUSTING THE WEIGHT.**
>
> **JANUS MAY REMEMBER A LOVE WITHOUT ENSLAVING IT.**
>
> **JANUS MAY RECORD A DEPARTURE WITHOUT ERASING THE ONE WHO LEFT.**

Genesis v18.7.10 closes BA-179-LIVED-001: ordinary in-process code can no
longer create sovereign evidence weight by calling `record_evidence_assessment`
with an arbitrary `assessor_id` and self-selected component values.

This reference implementation imports the epistemic discipline of private
JANUS I0 without importing any mining, Stratum, nonce, pool or z-bit behavior.

## 1. Signed assessor observation

The accepted object uses schema:

```text
janus.evidence_assessment.v2
```

It is canonical-JSON serialized and signed with Ed25519. It binds:

- assessment, assessor and key IDs;
- one claim and structured subject scope;
- authorized method and method version;
- policy ID, version and SHA-256;
- sorted, unique evidence SHA-256 values and their set hash;
- signed observation components;
- explanation hash;
- issued/expiry timestamps;
- one-use nonce;
- optional explicit supersession.

The assessor may sign only observations:

```text
source_reliability
evidence_integrity
method_reliability
temporal_relevance
```

The assessor may **not** self-assign:

```text
assessor_competence
independent_corroboration
```

Competence comes from a root-authorized credential. Corroboration is computed
by Genesis from independent current sources/controllers.

## 2. White-box confidence policy

The effective confidence is deterministically computed from:

```text
signed observations
+ root-authorized assessor competence
+ system-computed independent corroboration
+ hash-bound public policy
```

Every accepted record preserves:

- `policy_sha256`;
- `assessment_input_sha256`;
- calculated effective confidence;
- credential ID;
- historical signature integrity;
- current authority state.

Claimant-stated confidence has no sovereign weight.

## 3. Root governance boundary

Ordinary runtime calls cannot trust provider or sovereign roots. Root changes
require a signed `janus.root_governance_manifest.v1` authorized by an offline
bootstrapped root key.

Reference bootstrap is intentionally locked behind the installation boundary:

```text
GENESIS_OFFLINE_ROOT_BOOTSTRAP=1
```

This is not presented as production HSM security. A hostile deployment still
requires offline quorum/HSM custody and authenticated administration.

Root operations can:

- trust provider, assessor and sovereign public keys;
- install assessor credentials;
- install a hash-bound confidence policy;
- revoke assessor keys or credentials.

Key/credential revocation removes current assessment authority, preserves old
signature integrity and reopens affected sovereign cases.

## 4. Replay, semantic replay and event sourcing

A nonce is single-use. Reusing it is rejected as `REPLAYED`.

A new assessment over the same assessor, claim, method, evidence set and policy
must explicitly name `supersedes_assessment_id`. Otherwise it is rejected as:

```text
SEMANTIC_REPLAY_REQUIRES_SUPERSEDES
```

Accepted, superseded and revoked assessments remain in an append-only hash
chain. No old assessment is silently overwritten or resurrected.

## 5. Security Ear

Authority breaches create safe append-only security events and emit through:

```python
logging.getLogger("JANUS")
```

The event contains IDs, violation class and payload hashes. Raw evidence,
identity proofs, private keys and sensitive full text are not written to the
security log.

## 6. Frozen Constitution from JANUS I0

The I0 frozen-wire principle becomes a frozen constitutional boundary.
Experimental layers may change narrative, policies or probes, but cannot
silently change:

- silence is not consent;
- goodness does not purchase relationship;
- Free Other may refuse and leave;
- actor life is not relationship life;
- Chronicle remains an append-only hash chain;
- canonical JSON is signed;
- private keys are not persisted;
- sovereignty rules the record, not the soul;
- love cannot be used as coercion;
- mirrors cannot mutate canonical history.

The frozen payload is protected by `FROZEN_CONSTITUTION_SHA256`.

## 7. Fresh Boundary and Lived Audit Proofpack

Every lived audit can record:

- runtime version and sentinel;
- Git commit;
- confidence-policy hash;
- frozen-constitution hash;
- world-seed fingerprint;
- fresh Chronicle boundary;
- action-script hash;
- explicit limitations.

The proofpack includes Chronicle, HRaiN, Free Other and Bound Assessor health,
while declaring that it contains no private/API keys, raw identity proofs or
raw private dialogue.

Negative results remain evidence.

## 8. Counterfactual Life Mirror

A mirror is **not** an in-memory branch sharing mutable stores. It receives a
fully isolated data directory and a separate Genesis instance.

```text
classification = UNREALIZED_MIRROR
canonical Chronicle shared = false
canonical HRaiN shared = false
canonical mutation allowed = false
```

After the probe, canonical state retains only a manifest hash and selected
metrics. Raw mirror dialogue is not merged into canonical history.

## 9. Butterfly Witness

The conservative offline verdicts are:

```text
ANECDOTE_ONLY
REPLAY_SAME_SEED
COUNTERFACTUAL_REQUIRED
PROMOTE_TO_REGRESSION
CANON_CHANGE_CANDIDATE
```

The governing rule is:

> Do not confuse one beautiful event with a law.

Butterfly Witness observes and proposes evidence status. It cannot mutate the
canonical life.

## 10. Actor life is not relationship life

A Free Other now has two separate projections:

```text
actor_life_v1810
relationship_state_v1810
```

A terminal rupture sets the relationship to:

```text
TERMINATED_BY_OTHER
```

The player, goodwill score and `JANUS.SOVEREIGN` cannot reopen it. Chronicle
records `free_other_relationship_terminated`. HRaiN records an immutable
`SOCIAL_RUPTURE` with `CHOSE`, `PROTECTS`, `ENDS` and `CONTINUES` edges.

The relationship ends; the actor continues an offscreen path. Return is not
promised, and continued life is not a message to the player.

## 11. Long-life sandbox

The v18.7.10 sandbox supports:

- explicit passage of years;
- profession history, including morally framed fictional roles;
- bounded item casting with provenance and a finite reality budget;
- voluntary listings and purchases;
- finite assessed values and price caps;
- immutable origin ownership separated from mutable current ownership.

Profession labels grant no real-world authority and do not authorize real harm.
The sandbox currency is fictional `GENESIS_CREDIT`.

## Honest boundaries

- Ed25519 authenticates a signed payload; it does not establish real-world
  competence without a governed credential.
- The environment-gated root bootstrap is a reference installation boundary,
  not a production HSM ceremony.
- Current time still depends on the host clock; signed multi-witness monotonic
  time remains future work.
- Nonce archival currently persists JSON records; Merkle-partition compaction
  remains future work.
- Free Others are narrative simulations. Lived audits demonstrate runtime
  contracts, not consciousness or personhood.
