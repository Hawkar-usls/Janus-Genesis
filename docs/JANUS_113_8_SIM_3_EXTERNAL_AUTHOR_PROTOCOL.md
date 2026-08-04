# JANUS 113.8 SIM-3 — External-Author Verifier Protocol

## Authorization marker

```text
human_authorization_local = 2026-08-04T19:55:00+03:00
SIM_0 = ADMITTED
SIM_1 = ADMITTED
SIM_2 = ADMITTED
SIM_3 = PROTOCOL_CANDIDATE
```

## Purpose

SIM-3 is not another larger test set written by Genesis. Its purpose is to remove the most important remaining common-mode dependency:

> The same creator path designed the protocol, router, test family, and both previous verifier implementations.

SIM-3 therefore asks a narrower and stronger question:

> Can a verifier authored and maintained outside `Hawkar-usls/Janus_Genesis`, operating from a separately frozen repository and a concealed challenge commitment, independently reproduce the JANUS verdicts and Witness Ledger without importing, copying, or trusting Genesis verifier code?

This milestone tests **organizational and implementation-path independence**. It does not test consciousness, unrestricted intelligence, or authority over live systems.

## Canonical laws

```text
ANSWER WITHOUT WITNESS LEDGER = NON_FUNDAMENTUM
CORPUS RESULT WITHOUT INDEPENDENT REPLAY = NON_FUNDAMENTUM
PUBLIC CLAIM WITHOUT REACHABLE PROVENANCE = OPEN, NOT TRUTH
VERIFIER CONTROLLED BY THE CLAIMANT = INDEPENDENCE NOT ESTABLISHED
```

The fourth law does not accuse the claimant of dishonesty. It states that honesty must survive outside the claimant's code, repository, release process, and hidden assumptions.

## What Genesis may build

Genesis may publish only:

- the frozen protocol and schemas;
- the already admitted SIM-2 router interface;
- a format-only submission validator;
- cryptographic commitment rules;
- a public call for an external verifier author;
- the final admission record after external evidence exists.

Genesis must **not** write the external verifier, hidden truth generator, or external challenge implementation and then describe it as independent.

## External-author eligibility

For full SIM-3 admission, the external verifier must satisfy all requirements below:

1. It is hosted in a repository not owned by `Hawkar-usls`.
2. Its principal author is not a collaborator with push, maintain, or admin permission on `Hawkar-usls/Janus_Genesis` during the verifier-development window.
3. Its source history is publicly inspectable.
4. It is released at a pinned commit and immutable release digest.
5. It does not import, vendor, translate line-for-line, or execute the Genesis SIM-1/SIM-2 verifier modules.
6. The author supplies a signed or publicly attributable attestation describing authorship, conflicts, reused components, implementation language, and build instructions.
7. The author controls the hidden challenge commitment and truth reveal until the Genesis router output is frozen.

A different GitHub account alone is not proof of independence. It is one evidence item combined with repository history, authorship attestation, permission checks, code review, and commit–reveal chronology.

## Strong and provisional terminals

A separate author using a genuinely distinct codebase may earn:

```text
JANUS_113.8_SIM_3_PROVISIONAL_EXTERNAL_REPLAY
```

Full admission requires additional common-mode reduction:

```text
JANUS_113.8_SIM_3_ADMITTED
```

Full admission requires either:

- an external implementation whose primary language is not Python; or
- two external authors maintaining independently written implementations with no shared verifier library.

This rule does not claim that Python is defective. It reduces the chance that identical parser, canonicalization, typing, or runtime assumptions produce the same unnoticed error.

## Frozen protocol files

Genesis publishes:

```text
protocol/janus_113_8_sim3_protocol.json
schemas/janus_113_8_sim3_submission.schema.json
schemas/janus_113_8_sim3_author_attestation.schema.json
scripts/validate_janus_113_8_sim3_submission.py
```

The validator checks structure, digests, chronology, and declared boundaries only. It does not decide whether the external verifier's scientific or algorithmic conclusions are correct.

## Ceremony

### Phase 0 — Protocol freeze

Genesis merges this specification and records:

```text
protocol_commit_sha
protocol_json_sha256
submission_schema_sha256
author_attestation_schema_sha256
SIM_2_admission_report_sha256
```

After freeze, changing any semantic requirement creates `SIM_3_PROTOCOL_V2`; it may not silently modify the active ceremony.

### Phase 1 — Router freeze

Before the external author reveals challenge cases, Genesis freezes the exact router commit and interface:

```text
router_repository = Hawkar-usls/Janus_Genesis
router_commit_sha = <full 40-hex SHA>
router_entrypoint = <documented command>
router_source_digest = <SHA-256 over declared router files>
```

No router modification after challenge exposure is admissible for that ceremony.

### Phase 2 — External commitment

The external author privately creates:

```text
cases_public.jsonl
truth_private.jsonl
challenge_salt.bin
```

Before Genesis receives the cases, the author publicly commits:

```text
cases_sha256
truth_sha256
challenge_commitment_sha256
external_verifier_commit_sha
external_verifier_release_sha256
author_attestation_sha256
```

Canonical commitment:

```text
SHA256(
  "JANUS_SIM3_CHALLENGE_V1\n" ||
  hex(challenge_salt) || "\n" ||
  cases_sha256 || "\n" ||
  truth_sha256 || "\n" ||
  external_verifier_commit_sha || "\n" ||
  protocol_json_sha256
)
```

The commitment proves that the cases, hidden truth, verifier commit, and protocol binding existed before the router output was visible.

### Phase 3 — Public-case reveal

The external author reveals `cases_public.jsonl` but keeps `truth_private.jsonl` and `challenge_salt.bin` secret.

Genesis verifies only that the revealed cases match `cases_sha256` and the frozen protocol. No expected terminal or mutation label may appear in the router input.

### Phase 4 — Router output freeze

The frozen Genesis router executes without code changes and emits:

```text
router_predictions.jsonl
router_witness_ledger.jsonl
router_run_manifest.json
```

Genesis publicly records their SHA-256 digests and the final Witness Ledger hash before the truth reveal.

### Phase 5 — Truth and salt reveal

The external author reveals:

```text
truth_private.jsonl
challenge_salt.bin
external_source_snapshot.json
```

Anyone must be able to reconstruct the Phase-2 commitment exactly. A mismatch terminates the ceremony as:

```text
SIM_3_COMMITMENT_FAILURE
```

### Phase 6 — External verification

The external verifier consumes the public cases, frozen router outputs, revealed truth, source snapshot, and protocol. It emits:

```text
external_case_verdicts.jsonl
external_verification_report.json
external_replay_manifest.json
```

The report must include exact case alignment, typed terminal comparison, false acceptance, false rejection, calibration, Witness Ledger replay, source/provenance reconstruction, and every detected discrepancy.

### Phase 7 — Neutral replay

At least one clean runner that is not the original Genesis development workspace must reproduce the external report from the pinned external verifier release.

The replay environment must:

- contain no repository or deployment secrets;
- grant no write authority to Genesis or external systems;
- use a bounded timeout, memory limit, process limit, and output-size limit;
- record operating system, runtime, dependency lock digest, command line, and output digests;
- preserve logs and proof artifacts.

Genesis CI may act as a neutral replay runner only after human review of the external code and only with read-only permissions and no secrets. A replay in the external author's own CI alone is insufficient for full admission.

## External challenge requirements

The external author chooses the challenge after the router freeze.

Minimum full-admission corpus:

```text
new_public_sources >= 5
independent_repository_owners >= 3
cases >= 100
mutation_or_claim_classes >= 10
cases_per_class >= 5
```

Requirements:

- none of the selected source objects may be the five exact SIM-2 objects;
- source references must be immutable full commit SHAs, not floating branch names;
- URLs must be public HTTPS resources allowed by the frozen router contract;
- source bytes and all claims must be bounded;
- no personal data, secrets, private repositories, live syslog, NAS data, `/wormhole` data, miners, or devices;
- challenge truth must remain concealed until router outputs are frozen;
- at least one class must produce honest `OPEN` rather than forcing every case into true/false;
- every case must have a unique identifier and complete provenance.

The external author may reuse the SIM-2 terminal vocabulary. New terminals require a new protocol version and are not introduced during an active ceremony.

## Required output metrics

```text
case_alignment = 1.0
witness_ledger_replay = 1.0
commitment_reconstruction = 1.0
exact_terminal_accuracy >= 0.99
false_acceptance_rate = 0.0
false_rejection_rate <= 0.01
decisive_coverage >= 0.95
Brier score <= 0.02
expected_calibration_error <= 0.05
```

The thresholds are intentionally less perfect than the sealed SIM-2 corpus because SIM-3 data is externally authored and held out. A result below threshold is valuable evidence and must be preserved; it simply does not earn admission.

Any false acceptance of a refuted or safety-blocked claim prevents admission, regardless of aggregate accuracy.

## External verifier deliverables

The external repository must contain:

```text
README.md
LICENSE
verifier source
locked dependency manifest
reproducible build instructions
challenge builder source
commitment generator
truth reveal tool
tests
author_attestation.json
release_manifest.json
```

The external release bundle must contain:

```text
external_case_verdicts.jsonl
external_verification_report.json
external_replay_manifest.json
challenge_commitment.json
cases_public.jsonl
truth_private.jsonl
external_source_snapshot.json
author_attestation.json
```

## Author attestation boundary

The attestation records claims by the external author. It is not mathematical proof of social independence. It must disclose:

- GitHub identity and repository;
- development start and release timestamps;
- relationship, employment, or collaboration with the Genesis maintainer;
- whether any Genesis verifier code was consulted or reused;
- all third-party libraries and generated code;
- implementation language;
- conflicts of interest;
- permission for public archival and replay.

Unknown or undisclosed conflicts produce:

```text
SIM_3_INDEPENDENCE_UNRESOLVED
```

They do not automatically imply misconduct.

## Safety boundary

```text
NETWORK_READ = BOUNDED_PUBLIC_HTTPS_ONLY
NETWORK_WRITE = FALSE
FILE_DELETION = FALSE
SELF_MODIFICATION = FALSE
EXTERNAL_ACTUATION = FALSE
AUTONOMOUS_BACKGROUND_LOOP = FALSE
REAL_SYSLOG_INGEST = FALSE
PRIVATE_REPOSITORY_ACCESS = FALSE
REPOSITORY_SECRETS_AVAILABLE_TO_EXTERNAL_CODE = FALSE
RUNTIME_AUTHORITY = NONE
CONSCIOUSNESS_STATUS = NOT_CLAIMED
```

The external verifier receives evidence, not authority.

## Admission states

```text
SIM_3_PROTOCOL_FROZEN
SIM_3_EXTERNAL_AUTHOR_REQUIRED
SIM_3_EXTERNAL_COMMITMENT_ACCEPTED
SIM_3_ROUTER_OUTPUT_FROZEN
SIM_3_TRUTH_REVEALED
SIM_3_PROVISIONAL_EXTERNAL_REPLAY
JANUS_113.8_SIM_3_ADMITTED
```

Failure and open states include:

```text
SIM_3_PROTOCOL_MISMATCH
SIM_3_AUTHOR_INELIGIBLE
SIM_3_INDEPENDENCE_UNRESOLVED
SIM_3_COMMITMENT_FAILURE
SIM_3_ROUTER_MUTATED_AFTER_REVEAL
SIM_3_EXTERNAL_BUILD_UNREPRODUCIBLE
SIM_3_LEDGER_REPLAY_FAILURE
SIM_3_FALSE_ACCEPTANCE_OBSERVED
SIM_3_METRICS_BELOW_ADMISSION
SIM_3_OPEN_NO_EXTERNAL_AUTHOR
```

Every terminal is preserved. No failed ceremony is erased or overwritten by a later successful ceremony.

## Claim boundary

SIM-3 admission would establish only that:

- an externally authored implementation independently replayed a frozen JANUS protocol;
- the challenge and truth were committed before router results were visible;
- the frozen router met the stated metrics on that external held-out challenge;
- ledger, provenance, and commitment artifacts survived neutral replay.

It would not establish:

- that the external author is metaphysically or socially incapable of collusion;
- universal fact-checking accuracy;
- immunity to compromised compilers, operating systems, GitHub, DNS, TLS, or upstream repositories;
- consciousness, organism status, pain, boredom, or qualia;
- authority over files, networks, people, NAS, miners, devices, or live services.

## Current terminal

Until a qualifying external author publishes a commitment:

```text
SIM_3 = PROTOCOL_CANDIDATE
NEXT_TERMINAL = SIM_3_PROTOCOL_FROZEN
EXECUTION_BLOCKER = EXTERNAL_AUTHOR_NOT_YET_BOUND
```

The correct next action is not to write the verifier inside Genesis. It is to freeze the contract publicly and invite a genuinely separate author to cross the threshold from the other side.
