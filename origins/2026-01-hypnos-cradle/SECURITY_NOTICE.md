# Security notice — archived Janus origins

The uploaded historical iOS scripts contained literal Google Generative Language API keys.

They are **not committed** to this repository. Every matching credential was replaced with an explicit
`REDACTED_ORIGIN_API_KEY_*` placeholder before archival. The archived Python files are historical source
artifacts and are not imported by the active Genesis runtime.

The original uploaded-file SHA-256 values are preserved in `ORIGINS_MANIFEST.json` so provenance can be
checked without publishing the credentials.

Because the credentials appeared in historical files and were shared outside their original environment,
they should be treated as exposed and revoked or rotated at the provider.
