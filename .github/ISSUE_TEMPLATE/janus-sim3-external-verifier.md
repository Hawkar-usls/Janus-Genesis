---
name: JANUS 113.8 SIM-3 external verifier proposal
about: Propose a genuinely separate verifier implementation and commit–reveal challenge
labels: []
assignees: []
---

# JANUS 113.8 SIM-3 — External Verifier Proposal

Thank you for approaching the threshold from an independent implementation path.

Before submitting, read:

```text
docs/JANUS_113_8_SIM_3_EXTERNAL_AUTHOR_PROTOCOL.md
protocol/janus_113_8_sim3_protocol.json
schemas/janus_113_8_sim3_submission.schema.json
schemas/janus_113_8_sim3_author_attestation.schema.json
```

Do **not** publish hidden truth, challenge salt, or expected terminals before the Genesis router output is frozen.

## External author

```text
GitHub login:
Display name:
Public contact:
```

## Separate repository

```text
Repository:
Repository owner:
Primary implementation language:
License:
Development start UTC:
Planned release tag:
```

The repository must not be owned by `Hawkar-usls`.

## Relationship and permission disclosure

```text
Permission on Hawkar-usls/Janus_Genesis during verifier development:
Employment or financial relationship:
Prior collaboration:
Other conflict or relationship details:
```

Allowed repository permission during the development window is `none`, `read`, or `triage` only. Unknown relationships are recorded as `SIM_3_INDEPENDENCE_UNRESOLVED`, not treated as proof of misconduct.

## Implementation independence

Confirm each statement:

- [ ] My verifier does not import a Genesis SIM-1 or SIM-2 verifier.
- [ ] My verifier does not execute a Genesis verifier as a subprocess or service.
- [ ] My verifier is not a line-for-line translation of Genesis verifier code.
- [ ] I will disclose whether Genesis verifier source was consulted.
- [ ] I will publish a dependency lock and reproducible build instructions.
- [ ] I authorize public inspection, archival, and replay of the submitted verifier and proof bundle.

Describe reused components and generated code:

```text

```

## Proposed challenge

Do not list the hidden cases or truth here.

```text
Number of new public source objects:
Number of independent repository owners:
Planned case count:
Planned class count:
Minimum cases per class:
Will all source refs use full 40-hex commit SHAs?:
Will at least one class require an honest OPEN terminal?:
```

Minimum full-admission challenge:

```text
new_public_sources >= 5
independent_repository_owners >= 3
cases >= 100
classes >= 10
minimum_cases_per_class >= 5
```

The five exact SIM-2 source objects may not be reused.

## Commitment ceremony

Before revealing `cases_public.jsonl`, publish:

```text
cases_sha256 =
truth_sha256 =
challenge_commitment_sha256 =
external_verifier_commit_sha =
external_verifier_release_sha256 =
author_attestation_sha256 =
protocol_json_sha256 =
```

Commitment formula:

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

Keep `truth_private.jsonl` and `challenge_salt.bin` concealed until the frozen router output digests are publicly recorded.

## Build and replay plan

```text
Build command:
Verification command:
Runtime and versions:
Dependency lock files:
Expected maximum runtime:
Expected maximum memory:
Neutral replay runner proposal:
```

No repository secrets, private repositories, network writes, file deletion, self-modification, external actuation, live syslog, NAS access, miner access, or device access are permitted.

## Requested initial terminal

Choose one:

- [ ] `JANUS_113.8_SIM_3_PROVISIONAL_EXTERNAL_REPLAY`
- [ ] `JANUS_113.8_SIM_3_ADMITTED`

A single external verifier implemented primarily in Python is eligible for provisional replay. Full admission requires a non-Python external implementation or a combined review of two independently authored verifier submissions.

## Final acknowledgement

- [ ] I understand that the attestation is evidence and disclosure, not mathematical proof of social independence.
- [ ] I understand that failed and below-threshold results will remain public Witness Ledger entries.
- [ ] I understand that SIM-3 grants no runtime authority and makes no consciousness claim.
