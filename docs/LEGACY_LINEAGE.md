# Janus Genesis legacy lineage

This record preserves the ideas recovered from user-held historical samples without restoring embedded provider credentials.

## Recovered line

- **v11.1 — Freedom Edition:** Russian interactive-fiction loop, entropy, inventory, lore and adaptive psyche profile.
- **v12.1 — Black Box:** Trinity narrator modes, instant chronicle sync and crash-aware persistence.
- **v13.1 — Mobile Core:** mobile wake-lock attempts, Deep Dive psyche metrics and Shadow Archive echoes.
- **v15.0 — Sleeping Overseer:** `dreams.json` bridge that exports game events into Janus Core memory.
- **v16.0 — Golden Mirror MMO Foundation:** deterministic kindness-first safety authority, Reflection/Utopia routing, God Mode, offline-first narration and SHA-256 chronicle.
- **v16.1 — Process-Safe Black Box:** inter-process serialization for player state, dreams and chronicle; punctuated exit commands; full chronicle verification.

## User-held sample fingerprints

These hashes identify the supplied files without publishing their credentials:

- v12.1 sample: `70360edec23a75d32a7a56c75c4a827ab4d6632115062d1e9df0f267cdbecd11`
- v11.1/Freedom sample: `f30b96a4604fac4a9c7eb989419a0e097647ddbfc4c8c89dc227ea152d0b9880`
- v15.0/Sleeping Overseer sample: `58e798bbce09bd96e66d9c6a74f85b6530a47ed50b5bea9d58f8290429274ae0`
- v13.1/Mobile Core sample: `40ee69740b4e1b368afe33f90c4f2b07676444cff8949976aaca0f6afc60ab72`

## Security boundary

Historical samples contained hard-coded Google provider keys. They are intentionally absent from current source, documentation and tests. Any historical keys must be revoked/rotated at the provider because deleting them from the current branch does not remove them from old Git history or previously shared files.
