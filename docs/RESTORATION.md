# Restoration record

- The original Janus Genesis game remained available in Git history.
- The PLA rebuild began at commit `546d2766ad277b9b292d8b76fea591a9488f51ec`.
- The last complete Deep Dive game line was preserved at `14e1e726a5402c2f947d424917fbe408c669f78c`.
- The PLA head was preserved in `archive/pla-genesis-before-game-restore`.
- Rescue PR #4 restored the game and merged as `29d2a140fcd34023fb8175bdce703b14fcd70493`.
- The rescue combines the historical Mirror Protocol with user-preserved v11.1, v12.1, v13.1 and v15 concepts.
- Embedded provider credentials were intentionally not restored.
- v16.1 closes the post-merge review findings: cross-process Black Box serialization and punctuated explicit exits.

No PLA history was destroyed. See `LEGACY_LINEAGE.md` for the recovered feature lineage and sample fingerprints.
