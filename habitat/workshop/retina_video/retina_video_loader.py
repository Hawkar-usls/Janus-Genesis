#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

PINNED_COMMIT = "be5d88d6c5afd63b6f1b105791a489d1a787f132"
EXPECTED_GIT_BLOB_SHA1 = "206056bce5b9b980311df680dffdc53393d3bd3e"
RAW_URL = (
    "https://raw.githubusercontent.com/Hawkar-usls/TOPA/"
    f"{PINNED_COMMIT}/tools/topa_retina_video.py"
)


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def main() -> int:
    cache_root = Path(os.environ.get("JANUS_HABITAT_CACHE", ".janus_habitat_cache"))
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / f"topa_retina_video-{PINNED_COMMIT[:12]}.py"

    if target.exists():
        data = target.read_bytes()
        if git_blob_sha1(data) != EXPECTED_GIT_BLOB_SHA1:
            target.unlink()

    if not target.exists():
        req = urllib.request.Request(
            RAW_URL,
            headers={"User-Agent": "JANUS-Habitat-Retina-Video/1.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
        actual = git_blob_sha1(data)
        if actual != EXPECTED_GIT_BLOB_SHA1:
            raise SystemExit(
                f"RETINA_VIDEO_PIN_MISMATCH expected={EXPECTED_GIT_BLOB_SHA1} actual={actual}"
            )
        target.write_bytes(data)

    cmd = [sys.executable, str(target), *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
