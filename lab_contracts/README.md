# JANUS Laboratory Contracts

Files in this directory are not part of the repository's ordinary unit-test discovery.

Router Hardening Laboratory-1 uses a dedicated workflow with two explicit phases:

1. **Phase A — expected failure:** run the hardened contracts against the unchanged pre-repair router and preserve the failing transcript.
2. **Phase B — admission:** after a separately reviewed router repair, run the same contracts and require a clean pass.

This separation prevents ordinary CI from treating the intentionally failing pre-repair contract as an unexplained regression while still preserving exact machine-executed evidence that the defect existed before repair.
