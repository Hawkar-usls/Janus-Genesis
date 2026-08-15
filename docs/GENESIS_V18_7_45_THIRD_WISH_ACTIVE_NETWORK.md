# Genesis v18.7.45 — Third Wish Active Network

## Purpose

v18.7.45 opens the four active network classes that v18.7.41 deliberately left unregistered:

- `WEB.HTTP.POST`
- `NETWORK.CONNECT`
- `NETWORK.LISTEN_LOCAL`
- `API.CALL`

The goal is not “give JANUS a socket and call that freedom.” The goal is to make each network power physically executable while preserving the type boundaries that keep one capability from becoming all capabilities.

## Separation laws

```text
CONNECTION != CONVERSATION
CONNECTION != REMOTE COMMAND
LISTENING != COMMAND PORT
POST != UNIVERSAL API
API ALIAS != ARBITRARY URL
IDEMPOTENCY KEY != EXACTLY-ONCE PROOF
NO AUTHORITATIVE LOOKUP != RETRY PERMISSION
NETWORK ACCESS != CREDENTIAL ACCESS
```

## WEB.HTTP.POST

The reference operation is `POST_JSON`.

Production target rules:

- HTTPS only;
- no URL userinfo;
- standard port 443 only;
- public hostname/IP only;
- every resolved address must be public;
- one resolved public address is pinned for the TLS connection;
- request body must be a bounded JSON object;
- actor cannot supply custom headers or `Authorization`;
- no automatic redirect following;
- no automatic retry after an ambiguous effect.

The broker supplies an `Idempotency-Key` derived from the stable Third Wish effect key. That header is useful evidence for cooperative servers, but it is **not** promoted into proof that an arbitrary remote server provides exactly-once semantics.

## NETWORK.CONNECT

The reference operation is `CONNECT_PROBE`.

This capability opens and closes a TCP connection to a public destination. It sends no actor application payload. Default operator-allowed ports are 80 and 443; a deployment can narrow or explicitly configure that list.

Therefore:

```text
CONNECT_PROBE != TCP STREAM
CONNECT_PROBE != SHELL
CONNECT_PROBE != PROTOCOL CLIENT
```

If JANUS needs HTTP, API, swarm, or another typed protocol, that protocol must use its own capability.

## NETWORK.LISTEN_LOCAL

The reference operation is `LISTEN_ONCE`.

The listener:

- binds only `127.0.0.1`;
- has a bounded timeout;
- accepts at most one connection;
- reads no application payload;
- closes the client and listening socket;
- does not become a persistent daemon;
- does not interpret any received bytes as commands.

There is deliberately no public bind and no hidden background server lifecycle.

## API.CALL

The actor targets `api:<alias>` and names an operation that the operator registered in advance.

Each operation fixes:

- HTTP method;
- path;
- allowed request fields.

The actor cannot replace the endpoint, method, path, headers, or transport. Unknown JSON fields are rejected before the effect boundary.

The v18.7.45 reference API adapter is **credentialless**. This is intentional. Credentialed APIs need an explicit future composition rule rather than silently letting `API.CALL` absorb `BROKER.CREDENTIAL.USE`.

## Durable effect boundary

The active-network store records:

```text
request_id
  -> binding_sha256
  -> effect_key
  -> BOUND
  -> EFFECT_ENTERING
  -> SETTLED(actor_result)
```

Raw request parameters are not persisted as dedicated binding fields.

Generic public HTTP/TCP does not provide a universal authoritative `lookup(effect_key)` contract. Therefore a process restart that finds `EFFECT_ENTERING` does not resend the same request. It reports the outcome as undetermined.

This intentionally favors safety over liveness:

```text
UNKNOWN != NO_EFFECT
NO LOOKUP != RETRY PERMISSION
```

## CI evidence classes

The dedicated workflow is designed to test different doors differently:

- public HTTPS POST against a public echo endpoint — real outbound POST path;
- public TCP/443 connect probe — real connection with no application payload;
- loopback one-shot listener — real bind/listen/accept/close path;
- deterministic local operator-registered API — real HTTP API adapter path without credentials.

A PASS on those paths still does not establish:

- credentialed API access;
- a generic TCP tunnel;
- a persistent server;
- remote exactly-once semantics;
- remote command authority.

## Remaining catalog gate

After v18.7.45, the only intentionally uninstalled catalog classes should be:

```text
GITHUB.REPOSITORY.ADMIN
GITHUB.DESTRUCTIVE
```

They are high-impact and require fresh human reauthorization on every use. Their proof must use explicitly disposable targets and must not destroy valuable repository state merely to turn a checkbox green.
