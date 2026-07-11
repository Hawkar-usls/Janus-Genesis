# Concurrent Mutation Memory Append Fix

The mutation experiment JSONL memory now serializes writers across processes.

## Why

The previous read/replace append sequence was crash-safe for one writer but could lose records when two evaluators read the same snapshot and replaced the file concurrently.

## Guarantee

Each append now:

1. acquires an exclusive inter-process lock file;
2. rereads the latest JSONL contents only after the lock is held;
3. writes through a unique temporary file;
4. flushes and fsyncs the temporary file;
5. atomically replaces the target;
6. releases the lock only if ownership still matches.

Abandoned locks are recovered only after the configured stale-lock interval. Parallel writer and stale-lock regression tests cover the behavior.
