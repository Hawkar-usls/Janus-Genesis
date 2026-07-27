# Security Notice

The supplied `artifacts.rar` contained literal historical credentials and private operational material.

Detected classes included:

- Google API keys;
- a Telegram bot token;
- a private LAN host;
- an ephemeral tunnel endpoint;
- bot/payment and operational backup files.

No literal credential is committed to Git. The private sanitized archive replaces them with explicit redaction markers while preserving source-file SHA-256 values in the catalog. The original secret-bearing RAR remains outside Git.

All discovered credentials must be treated as compromised and revoked or rotated.

No archived Python or JavaScript file was executed. Selected Python files were syntax-checked only after redaction.

Sanitized archive SHA-256: `458779303df79f6ee65869b2579de70e8f4045808e6b65ca95acfced5bddaec9`.
