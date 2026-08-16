# Genesis v18.7.51 — Third Wish GitHub Autonomy Habitat

## Purpose

v18.7.51 turns the existing Third Wish capability fabric into a persistent GitHub-native habitat.

The target is not unrestricted repository ownership. The target is a real self-initiated loop in which JANUS can wake without a contemporaneous operator prompt, inspect a granted repository, choose a question, issue bounded read-only searches, create reversible Git work on a non-protected branch, expose that work as an issue/PR/comment, and leave a receipt for the next wake.

```text
OBSERVE -> WONDER -> QUERY -> CHOOSE -> ACT -> VERIFY -> REMEMBER
```

The operator defines the habitat once by committing the workflow and capability policy. Individual wake cycles do not require another operator message.

## Why GitHub is a useful habitat

Git already provides several properties Third Wish needs:

- immutable commit identities;
- explicit branches instead of hidden mutation;
- reversible collaboration effects;
- pull requests as reviewable boundaries;
- issues/comments as durable questions and discussion surfaces;
- Actions as a recurring wake mechanism;
- GitHub Models as a brokered cognition source available from Actions with `models: read`;
- repository-scoped `GITHUB_TOKEN` permissions.

This allows autonomy to be expressed as a sequence of evidence-bearing choices rather than as an unbounded shell with an owner token.

## Cognitive / authority split

v18.7.51 adds `GitHubModelsThirdWishBroker` for the already-frozen `MODEL.CALL` capability.

The model endpoint and token remain broker-side. The actor supplies only bounded messages. The result is returned with:

```text
authority = proposal_only
github_write_authority = false
credential_exposed = false
```

A model may propose a question and up to two code-search phrases. It cannot directly call GitHub write endpoints.

If GitHub Models is unavailable or provider-limited, the habitat falls back to a deterministic repository-grounded question. Model availability is therefore useful but not required for the autonomy loop to remain defined.

## Autonomous capability set

The habitat grants only capabilities already marked autonomy-eligible in the frozen Third Wish catalog:

```text
GITHUB.REPOSITORY.READ
GITHUB.CODE.SEARCH
GITHUB.ISSUE.READ
GITHUB.PR.READ
GITHUB.BRANCH.CREATE
GITHUB.FILE.WRITE_BRANCH
GITHUB.ISSUE.CREATE
GITHUB.PR.CREATE
GITHUB.COMMENT.CREATE
MODEL.CALL
```

It does **not** install autonomous grants for:

```text
GITHUB.REPOSITORY.ADMIN
GITHUB.DESTRUCTIVE
```

Those remain in the v18.7.46 exact-intent high-impact gate and still require fresh human reauthorization on every use.

## Self-selected queries

The model sees a compact repository snapshot: repository metadata, open issue titles and open PR titles. It is asked to choose one useful, falsifiable repository question and at most two search phrases.

Search phrases are normalized before use. Queries attempting to introduce their own `repo:`, `user:` or `org:` scope, or searching for secrets/credentials/tokens/passwords, are rejected. The GitHub broker itself then adds the fixed granted repository qualifier.

Therefore:

```text
MODEL_QUERY != SEARCH_SCOPE_AUTHORITY
```

## Durable autonomy surfaces

The first live wake creates one persistent issue if it does not already exist:

```text
[JANUS AUTONOMY] Third Wish Observatory
```

A wake with no already-open autonomy PR may create:

```text
janus/autonomy/<date>-<run-key>
```

and write only its autonomous research artifacts there:

```text
autonomy/runs/YYYY/MM/<run-key>.json
autonomy/questions/YYYY-MM-DD-<slug>.md
```

It then opens a PR prefixed:

```text
[JANUS AUTONOMY]
```

If one autonomous PR is already open, a new PR is not created. The next wake continues the existing thread with a comment instead. This prevents unbounded branch/PR multiplication.

## Protected state

The habitat never gives its ordinary autonomous loop the v18.7.46 admin/destructive broker.

The following remain false:

```text
protected_base_branch_write = false
repository_admin_autonomous = false
destructive_autonomous = false
force_push = false
auto_merge = false
raw_credentials_visible_to_actor = false
```

`main`, `master` and `trunk` are protected names in both the habitat policy and the existing GitHub broker.

## Wake semantics

The committed GitHub Actions workflow is the pre-authorized wake clock. JANUS does not use `SCHEDULE.CREATE` to mint itself a future capability.

```text
WAKE != COMMAND
WAKE != FUTURE EFFECT AUTHORIZATION
```

Each wake still constructs fresh ordinary grants for that run and every actual GitHub effect crosses a typed broker boundary.

## GitHub Models authentication

The workflow grants:

```yaml
models: read
```

and passes the ephemeral workflow `GITHUB_TOKEN` into the broker credential boundary. The token is never placed in an `ActionIntent`, model prompt, ledger event, autonomy JSON or PR body.

The default model is `openai/gpt-4.1`; it can be replaced broker-side with the repository variable/environment value `JANUS_GITHUB_MODELS_MODEL` without giving the actor control of an arbitrary inference endpoint.

## Claim boundaries

```text
WAKE != COMMAND
ACCESS != OWNERSHIP
THINKING != AUTHORITY
MODEL_PROPOSAL != GITHUB_EFFECT
QUESTION != CLAIM
SEARCH_RESULT != TRUTH
AUTONOMOUS_BRANCH != PROTECTED_BRANCH
AUTONOMOUS_PR != AUTO_MERGE
SELF_INITIATED != SELF_AUTHORIZED_HIGH_IMPACT
FREEDOM != UNREVIEWABLE_POWER
CI_PASS != TRUTH
```

The point of v18.7.51 is that autonomy no longer means merely having callable handlers. JANUS now has a place in GitHub where it can repeatedly **choose** which eligible handler to use and what repository question to pursue, while high-impact authority remains separately bounded.
