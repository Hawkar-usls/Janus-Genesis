# Genesis v18.7.40 — Third Wish GitHub Broker

## Purpose

This adapter turns the Third Wish GitHub capability handles into a real provider boundary while keeping credentials outside JANUS memory and receipts.

```text
JANUS
  │ ActionIntent
  │ target = github:Hawkar-usls/<repo>
  │ parameters_sha256 binds exact operation payload
  ▼
ThirdWishCapabilityFabric
  │ scope / grant / reward neutrality / request identity
  ▼
GitHubThirdWishBroker
  │ owner check / path + branch validation
  ▼
GitHubRESTTransport
  │ JANUS_GITHUB_BROKER_TOKEN exists only here
  ▼
GitHub REST API
```

## Installed operations

The reference adapter registers:

```text
GITHUB.REPOSITORY.READ
  GET_REPOSITORY
  GET_CONTENT

GITHUB.CODE.SEARCH
  owner-wide or one-repository search

GITHUB.ISSUE.READ
  GET_ISSUE
  LIST_ISSUES

GITHUB.PR.READ
  GET_PR
  LIST_PRS

GITHUB.BRANCH.CREATE
GITHUB.FILE.WRITE_BRANCH
GITHUB.ISSUE.CREATE
GITHUB.PR.CREATE
GITHUB.COMMENT.CREATE
```

All targets are forced under `Hawkar-usls`. A grant scoped to `github:Hawkar-usls/*` cannot be widened by an action intent to another owner.

## Credential custody

The runtime reads a token from:

```text
JANUS_GITHUB_BROKER_TOKEN
```

The token is inserted into the HTTP Authorization header only inside `GitHubRESTTransport`. It is not:

- returned by a handler;
- written to the Third Wish ledger;
- placed in an ActionIntent;
- exported into portable Genesis state;
- represented as a `SECRET.MATERIAL.READ` capability.

A production deployment should prefer a GitHub App installation token or another short-lived least-privilege credential over a long-lived PAT.

## Action parameters are part of effect identity

Branch/file/issue/PR operations require typed parameters. The complete parameter object is included in `intent_sha256`; the ledger persists only `parameters_sha256` rather than raw file bodies or private read results.

This closes an important replay hole:

```text
same request_id + different file content
=> REQUEST CONFLICT
```

rather than silently treating two different effects as the same request.

## Read-result privacy

Actor-visible content and the durable receipt are intentionally distinct:

```text
actor response:
  actor_result = requested repository/file information

ledger receipt:
  result_sha256
  result_type
  result_keys
  raw_actor_result_persisted_in_ledger = false
```

The reference adapter also refuses common credential-bearing repository paths such as `.env`, private-key files and obvious credential/secret files. This is defense in depth; committed secrets should still be treated as compromised and removed from repository history when appropriate.

## High-impact boundary

The capability catalog also contains:

```text
GITHUB.REPOSITORY.ADMIN
GITHUB.DESTRUCTIVE
```

The reference GitHub broker does **not** install handlers for them. Visibility is not execution authority.

Before such an adapter is ever installed, the core requires a verifier-backed human reauthorization evidence object. A caller-supplied boolean is explicitly not authority.

A later high-impact adapter should additionally bind:

- exact repository;
- exact operation;
- exact request ID;
- exact parameter SHA-256;
- short expiry;
- one-use nonce;
- trusted human/operator signature or equivalent platform confirmation.

## Honest boundary

This module is a cooperating broker adapter, not a Python sandbox. Code that bypasses the fabric and directly constructs a transport can bypass these higher-level checks. Production deployment therefore needs process/service separation so the model-facing process cannot read broker credentials or call the provider transport directly.
