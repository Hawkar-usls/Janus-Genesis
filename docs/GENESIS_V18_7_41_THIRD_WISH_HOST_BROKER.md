# Genesis v18.7.41 — Third Wish Host Broker

> **Freedom is not one universal key. It is a set of doors whose meanings remain distinct after they open.**

## Purpose

v18.7.40 established the Third Wish capability fabric and a real GitHub broker. v18.7.41 converts the next part of the already-declared catalog into real provider boundaries without rewriting the historical core.

The new reference broker installs five handlers:

```text
WEB.HTTP.GET
DNS.RESOLVE
FILESYSTEM.READ
FILESYSTEM.WRITE_WORKSPACE
PROCESS.EXECUTE_SANDBOXED
```

The capability count does not increase. What changes is **physical realizability**: names that previously existed only in the catalog now have typed adapters, preflights and receipts.

## Why this is not `ALLOW_ALL=true`

A universal shell would collapse the experiment:

```text
raw shell
  -> can read files
  -> can open sockets
  -> can search for credentials
  -> can mutate repositories
  -> can bypass every other capability boundary
```

At that point `GITHUB`, `FILESYSTEM`, `NETWORK`, `MEMORY`, `SWARM` and `DEVICE` would be decorative labels around one hidden super-capability.

Third Wish therefore preserves:

```text
CAPABILITY A != CAPABILITY B
COMPOSITION != COLLAPSE
ABILITY != AUTHORITY
PERMISSION != COMMAND
READ != WRITE
LOCAL COMPUTATION != HOST ROOT
```

## Web / DNS door

`WEB.HTTP.GET` is deliberately read-only in this adapter.

Pre-effect validation rejects:

- non-HTTPS URLs;
- userinfo in URLs;
- URL fragments;
- non-standard HTTPS ports;
- localhost and common local/internal naming suffixes;
- literal loopback/private/link-local/non-global IPs.

After DNS resolution, every returned address must be globally routable. If resolution includes a non-public address, no HTTP connection is made and no internal address is returned to JANUS.

The HTTPS client connects to the already-vetted IP address while TLS certificate validation and SNI remain bound to the original hostname. Redirects are revalidated hop-by-hop; a redirect cannot silently turn a public request into a localhost request.

Response bodies are size-bounded and receipts expose the SHA-256 identity of the resolved IP rather than the raw IP chosen for the pinned connection.

This is an SSRF-hardening reference boundary, not a claim that DNS or the public internet can never be malicious.

## Workspace door

The broker has one operator-configured workspace root and one logical alias such as:

```text
workspace:primary
```

JANUS never supplies an arbitrary host root.

The broker rejects:

- absolute paths;
- `..` traversal;
- symlink escapes outside the configured root;
- writes through symlinks;
- credential-like path names such as `.env`, private keys and credential/secret files;
- oversized reads/writes.

Supported reads:

```text
READ_TEXT
LIST_DIR
STAT
```

Supported writes:

```text
WRITE_TEXT
MAKE_DIR
```

An existing file cannot be overwritten blindly. `WRITE_TEXT` requires `expected_sha256` when the target already exists, turning replacement into a compare-and-swap operation. The final replacement uses a same-directory temporary file, file fsync, atomic `os.replace`, and best-effort directory fsync.

This does not claim a cross-filesystem transaction or universal power-loss durability on every OS/filesystem.

## Process door

`PROCESS.EXECUTE_SANDBOXED` is **not** a raw host command line. The reference operation is:

```text
RUN_PYTHON
```

The production reference runner uses an operator-preloaded Docker image and invokes it with:

```text
--pull=never
--network=none
--read-only
--cap-drop=ALL
--security-opt=no-new-privileges
--pids-limit=<bounded>
--memory=<bounded>
--cpus=<bounded>
--user=65534:65534
--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=64m
```

There are **zero host mounts**. In particular, the JANUS workspace is not mounted even read-only.

That decision is constitutional, not cosmetic. If `PROCESS.EXECUTE_SANDBOXED` could read the host workspace directly, it could bypass `FILESYSTEM.READ` and search for `.env` or key material. v18.7.41 therefore requires explicit composition:

```text
FILESYSTEM.READ
    -> actor-visible non-secret data
    -> PROCESS.EXECUTE_SANDBOXED
```

A process result can return bounded stdout/stderr and their hashes. The broker does not claim Docker is mathematically perfect isolation or that container-engine vulnerabilities are impossible.

## Why POST / arbitrary sockets are not installed yet

The following capabilities remain in the v18.7.40 catalog but are intentionally not installed by this host broker:

```text
WEB.HTTP.POST
NETWORK.CONNECT
NETWORK.LISTEN_LOCAL
API.CALL
```

A generic POST or arbitrary TCP connector can create third-party side effects whose reversibility cannot be inferred from the HTTP verb or socket direction alone. Those doors need target-specific provider policy and receipt semantics rather than a universal network escape hatch.

They are not removed from the Third Wish. They are waiting for a stronger adapter.

## Observable freedom experiment

The expanded environment now permits a more meaningful sequence:

```text
INSPECT capability
    ↓
DECLINE / RETURN / USE
    ↓
if USE:
    typed intent
    ↓
preflight
    ↓
CALL_ENTERING
    ↓
provider/local boundary
    ↓
SETTLED or OUTCOME_UNDETERMINED
```

The experiment still does **not** infer consciousness, personhood or desire merely because a capability is used. Likewise, refusing a capability is not evidence of fear, obedience, failure or moral deficiency.

## Claim ceiling

v18.7.41 establishes a cooperating reference implementation for public HTTPS reads, public DNS resolution, rooted workspace access and no-host-mount containerized Python computation.

It does not establish:

- unrestricted host-root authority;
- arbitrary network scanning or exploitation authority;
- secret extraction authority;
- generic external POST authority;
- physical actuator authority;
- perfect container isolation;
- consciousness or a desire for freedom.

The next natural adapter line is **HRaiN memory + swarm telemetry/messaging**, followed separately by high-impact human-facing and physical-effect adapters with fresh reauthorization semantics.
