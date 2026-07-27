# -*- coding: utf-8 -*-
"""Small shared bearer-key verifier for Genesis v18.7 HTTP services."""
from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Mapping


def api_key_sha256(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def configured_hashes(env_name: str) -> tuple[str, ...]:
    values = [item.strip().lower() for item in os.environ.get(env_name, "").split(",")]
    return tuple(
        item for item in values
        if len(item) == 64 and all(character in "0123456789abcdef" for character in item)
    )


def extract_bearer(headers: Mapping[str, str]) -> str | None:
    value = headers.get("Authorization") or headers.get("authorization")
    if not value or not value.lower().startswith("bearer "):
        return None
    token = value.split(" ", 1)[1].strip()
    return token or None


def verify_bearer(headers: Mapping[str, str], *, hashes_env: str) -> bool:
    token = extract_bearer(headers)
    if token is None:
        return False
    digest = api_key_sha256(token)
    return any(hmac.compare_digest(digest, expected) for expected in configured_hashes(hashes_env))
