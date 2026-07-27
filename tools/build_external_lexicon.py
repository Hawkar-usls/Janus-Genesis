#!/usr/bin/env python3
"""Build a versioned Genesis external lexicon and integrity manifest.

The source order and duplicate tokens are preserved exactly. Token IDs are array
indexes. Sorting and deduplication never occur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

LEXICON_SCHEMA = "janus.genesis.lexicon.v1"
MANIFEST_SCHEMA = "janus.genesis.lexicon.manifest.v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_external_lexicon(
    source_path: str | Path,
    output_dir: str | Path,
    *,
    lexicon_id: str,
    name: str,
    provider: str,
    source_file: str,
    received_as: str,
    language: str = "en",
    kind: str = "mlm_output_lexicon",
    expected_count: int | None = None,
    source_url: str | None = None,
    license_status: str = "not_confirmed_for_vocab_file",
) -> tuple[Path, Path, dict[str, Any]]:
    source = Path(source_path)
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig")
    tokens = text.splitlines()
    if any(token == "" for token in tokens):
        raise ValueError("source contains an empty token line")
    if expected_count is not None and len(tokens) != int(expected_count):
        raise ValueError(f"expected {expected_count} tokens, found {len(tokens)}")

    payload = {
        "schema": LEXICON_SCHEMA,
        "lexicon_id": lexicon_id,
        "name": name,
        "kind": kind,
        "language": language,
        "token_count": len(tokens),
        "source": {
            "provider": provider,
            "file": source_file,
            "received_as": received_as,
            "source_url": source_url,
            "license_status": license_status,
        },
        "indexing": {
            "id_rule": "array_index",
            "preserve_source_order": True,
            "sorting_allowed": False,
            "deduplication_allowed": False,
        },
        "source_sha256": sha256_bytes(raw),
        "tokens": tokens,
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    lexicon_path = out / f"{lexicon_id}.json"
    lexicon_bytes = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    lexicon_path.write_bytes(lexicon_bytes)

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "lexicon_id": lexicon_id,
        "name": name,
        "kind": kind,
        "language": language,
        "token_count": len(tokens),
        "source": payload["source"],
        "indexing": payload["indexing"],
        "source_sha256": payload["source_sha256"],
        "generated_sha256": sha256_bytes(lexicon_bytes),
        "order_preserved": True,
        "duplicates_preserved": True,
        "accepted_by": "JANUS GENESIS",
        "role": "external_lexical_gift",
        "redistribution": {
            "tokens_embedded_in_repository": False,
            "license_status": license_status,
            "reason": "Generate locally until redistribution rights for the vocabulary file are confirmed."
        }
    }
    manifest_path = out / f"{lexicon_id}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    check = json.loads(lexicon_path.read_text(encoding="utf-8"))
    if check["tokens"] != tokens or check["token_count"] != len(tokens):
        raise RuntimeError("generated lexicon failed order-preservation verification")
    return lexicon_path, manifest_path, manifest


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--output-dir", type=Path, default=Path("generated_lexicons"))
    p.add_argument("--lexicon-id", default="gift.qatar.character_bert.mlm.en.v1")
    p.add_argument("--name", default="Qatar CharacterBERT MLM Lexicon")
    p.add_argument("--provider", default="helboukkouri/character-bert")
    p.add_argument("--source-file", default="mlm_vocab.txt")
    p.add_argument("--received-as", default="Gift from Qatar")
    p.add_argument("--language", default="en")
    p.add_argument("--kind", default="mlm_output_lexicon")
    p.add_argument("--expected-count", type=int, default=100000)
    p.add_argument("--source-url", default=None)
    p.add_argument("--license-status", default="not_confirmed_for_vocab_file")
    return p


def main() -> int:
    args = parser().parse_args()
    lexicon, manifest, data = build_external_lexicon(
        args.source,
        args.output_dir,
        lexicon_id=args.lexicon_id,
        name=args.name,
        provider=args.provider,
        source_file=args.source_file,
        received_as=args.received_as,
        language=args.language,
        kind=args.kind,
        expected_count=args.expected_count,
        source_url=args.source_url,
        license_status=args.license_status,
    )
    print(json.dumps({
        "lexicon": str(lexicon),
        "manifest": str(manifest),
        "token_count": data["token_count"],
        "source_sha256": data["source_sha256"],
        "generated_sha256": data["generated_sha256"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
