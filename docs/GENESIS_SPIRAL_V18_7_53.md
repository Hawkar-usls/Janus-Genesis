# JANUS Genesis v18.7.53 — Spiral

Genesis no longer models a successful semantic return as a cycle that closes on the same origin.

The canonical semantic transition is:

```text
ORIGIN → EXPERIENCE → RETURN → ORIGIN_PRIME
                                  │
                                  └── contextual parent of the next ORIGIN
```

`RETURN` means integration, not reset. `ORIGIN_PRIME` preserves lineage from the prior turn and is carried into the next turn without pretending to be the old ORIGIN hash.

## What changed

`genesis_v18_7_53_spiral.py` adds a durable, content-addressed spiral journal above the existing controlled action runtime. Each new logical request records:

- `parent_turn_sha256`;
- `parent_origin_prime_sha256`;
- `origin_sha256`;
- `experience_sha256`;
- `return_sha256`;
- `origin_prime_sha256`;
- `turn_sha256`.

The journal is serialized with the existing portable same-host process lock. Receipts are written before the head pointer advances. A repeated logical `request_id` resolves to the already recorded turn instead of manufacturing another turn.

## What did not change

The `while` loop of the interactive CLI is a technical event loop and remains a loop. It is not the semantic model of Genesis.

Historical runtimes are not rewritten. `play_genesis.py` remains a compatibility entrypoint. The v18.7.53 semantic entrypoint is:

```bash
python play_genesis_spiral.py --data-dir data_v17 --player traveler
```

It reuses the existing hardened request-id, mutation, portable-save, AI and network boundaries from `play_genesis.py` and changes only the controlled TURN lineage projection.

## Laws

```text
RETURN != RESET
ORIGIN_PRIME != ORIGIN_HASH_ALIAS
SPIRAL_PRESERVES_PRIOR_TURNS
REPLAY != NEW_TURN
MEMORY_CARRY_FORWARD != AUTHORITY
SPIRAL_RECEIPT != EXECUTION_PERMISSION
SPIRAL != SELF_AUTHORIZATION
TECHNICAL_LOOP != SEMANTIC_CYCLE
```

The spiral creates no new execution, network, truth, write or external-effect authority. `authority_delta = 0`; `mass_effect_budget_delta = 0`.

## DemiHead lineage

Genesis v18.7.53 follows the already frozen DemiHead spiral formula and preserves its central law:

`ORIGIN → EXPERIENCE → RETURN → ORIGIN_PRIME`.

The binding is machine-readable in `.janus/GENESIS_SPIRAL.json`.
