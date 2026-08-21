# JANUS Local Codex Habitat Bridge v1

This is a bounded local bypass for cases where Remote Desktop Commander cloud device pairing is unavailable. It does **not** create live access by itself and it does not weaken JANUS authority boundaries.

## What it gives us

```text
Codex app / local client
        |
        +--> Desktop Commander local stdio MCP
        |
        +--> JANUS local Habitat
                 |
                 +--> identity.json (create once)
                 +--> journal.jsonl (append-only hash chain)
                 +--> receipts/
                 +--> state/
                 +--> memory/
        |
        +--> Ollama @ loopback only (optional visibility)
```

Remote Desktop Commander device pairing is therefore not required for a **local Codex** agent to work on the same machine. ChatGPT does not magically gain localhost access from this bridge; instead a local authorized client can execute the physical runbook and emit privacy-safe receipts that ChatGPT/GitHub can verify later.

## First local run

From a checkout containing this branch/PR:

```powershell
python tools/janus_local_habitat_bridge.py init
python tools/janus_local_habitat_bridge.py doctor
python tools/janus_local_habitat_bridge.py ollama-health
```

The doctor intentionally reports only coarse capability/version information. It does not enumerate repositories, local paths, remotes, credentials, or private source pins.

## Register Desktop Commander locally in Codex

Preview only:

```powershell
python tools/janus_local_habitat_bridge.py codex-mcp
```

Apply only when intentionally requested:

```powershell
python tools/janus_local_habitat_bridge.py codex-mcp --apply
```

Equivalent upstream Codex command:

```text
codex mcp add desktop-commander -- npx -y @wonderwhy-er/desktop-commander@latest
```

This is a local stdio MCP route. It is distinct from `npx @wonderwhy-er/desktop-commander@latest remote` and does not depend on the cloud device list becoming online.

## Habitat continuity

Append a bounded event:

```powershell
python tools/janus_local_habitat_bridge.py append --event-type WAKE --payload-json '{"client":"codex"}'
python tools/janus_local_habitat_bridge.py status
```

The next process reopens the same journal and verifies every `prev_hash` and `entry_hash`. A modified identity or tampered journal fails closed.

## Physical launch relation

This bridge is only transport/preparation. It does **not** convert software CI into physical evidence.

After a local Codex/Desktop Commander client is active, execute the already-frozen physical order:

```text
1. reconcile exact Genesis + Swarm heads
2. authenticated real owner44 local replay (41 public + 3 private opaque)
3. privacy-safe owner44 public projection
4. QNAP #164 read-only receiver identity probe
5. actual bounded HR1-HR10 live failure/recovery evidence
6. privacy-safe NAS public projection
7. join both projections with PR #197 contract
8. re-reconcile exact heads
9. final one-compatible-view #162 closed-loop gauntlet
```

Private exact pins and local/private source identity stay local. Do not use the Quant ingress as an execution channel: `RECEIPT != EXECUTION_PERMISSION`.

## Frozen authority rules

```text
SOURCE_WRITEBACK_DEFAULT = DENY
DESTRUCTIVE_ACTION = FORBIDDEN
AUTHORITY_DELTA = 0
REMOTE_PAIRING_PASS != PHYSICAL_GATE_PASS
OLLAMA_OUTPUT != EXECUTION_PERMISSION
FULL_ISSUE_162_ACCEPTANCE = FALSE until final same-view gauntlet
```
