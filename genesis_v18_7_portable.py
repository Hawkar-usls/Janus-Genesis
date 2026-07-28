# -*- coding: utf-8 -*-
"""Portable on-device JSON saves for Genesis v18.7.

A portable save is one JSON document containing the local Genesis JSON/JSONL
state. API keys, environment files, credentials and network bearer tokens are
never included. Import verifies every embedded SHA-256 before writing anything.

Genesis v18.7.8 carries imperfect source bytes, grounded evidence, NPC
relationship state, voluntary witness identity metadata, structured subject
scopes, sovereign cases, influence attestations, manipulation audits and
JANUS.SOVEREIGN decisions through the same verified portable threshold.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PORTABLE_SAVE_SCHEMA = "janus.genesis.portable_save.v1"
RUNTIME_VERSION = "18.7.8"
EXCLUDED_NAMES = {
    ".env",
    "janus_keys.json",
    "network_credentials.json",
    "api_keys.json",
    "credentials.json",
}
EXCLUDED_FRAGMENTS = ("secret", "credential", "api_key", "apikey", "bearer", "token")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ValueError(f"unsafe portable-save path: {path!r}")
    return candidate


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PortableSaveManager:
    """Export or import a complete local Genesis state as one verified JSON."""

    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir)

    @staticmethod
    def _allowed_file(path: Path) -> bool:
        lowered = path.name.lower()
        if lowered in EXCLUDED_NAMES:
            return False
        if any(fragment in lowered for fragment in EXCLUDED_FRAGMENTS):
            return False
        return path.suffix.lower() in {".json", ".jsonl"}

    def build_bundle(self, *, label: str | None = None) -> dict[str, Any]:
        files: list[dict[str, Any]] = []
        if self.root.exists():
            for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
                if not self._allowed_file(path):
                    continue
                relative = path.relative_to(self.root).as_posix()
                raw = path.read_bytes()
                text = raw.decode("utf-8")
                if path.suffix.lower() == ".json":
                    json.loads(text)
                    kind = "json"
                else:
                    for line_number, line in enumerate(text.splitlines(), 1):
                        if line.strip():
                            try:
                                json.loads(line)
                            except json.JSONDecodeError as exc:
                                raise ValueError(
                                    f"invalid JSONL at {relative}:{line_number}"
                                ) from exc
                    kind = "jsonl"
                files.append(
                    {
                        "path": relative,
                        "kind": kind,
                        "size_bytes": len(raw),
                        "sha256": _sha256(raw),
                        "content": text,
                    }
                )
        manifest_material = json.dumps(
            [
                {key: item[key] for key in ("path", "kind", "size_bytes", "sha256")}
                for item in files
            ],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return {
            "schema": PORTABLE_SAVE_SCHEMA,
            "runtime_version": RUNTIME_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label": (label or "Genesis device save")[:160],
            "scope": "local_device_state",
            "contains_api_keys": False,
            "contains_environment_files": False,
            "network_authority": False,
            "file_count": len(files),
            "manifest_sha256": _sha256(manifest_material),
            "files": files,
        }

    def export_to(
        self, output_path: str | Path, *, label: str | None = None
    ) -> dict[str, Any]:
        bundle = self.build_bundle(label=label)
        output = Path(output_path)
        _atomic_write_text(
            output,
            json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        return {
            "path": str(output),
            "file_count": bundle["file_count"],
            "sha256": _sha256(output.read_bytes()),
            "contains_api_keys": False,
        }

    @staticmethod
    def verify_bundle(bundle: dict[str, Any]) -> tuple[bool, int, str | None]:
        if bundle.get("schema") != PORTABLE_SAVE_SCHEMA:
            return False, 0, "unsupported portable-save schema"
        if bundle.get("contains_api_keys") is not False:
            return False, 0, "portable save claims to contain API keys"
        files = bundle.get("files")
        if not isinstance(files, list):
            return False, 0, "files must be a list"
        seen: set[str] = set()
        manifest: list[dict[str, Any]] = []
        for item in files:
            if not isinstance(item, dict):
                return False, len(seen), "file entry is not an object"
            try:
                relative = _safe_relative(str(item["path"])).as_posix()
            except (KeyError, ValueError) as exc:
                return False, len(seen), str(exc)
            if relative in seen:
                return False, len(seen), f"duplicate path: {relative}"
            seen.add(relative)
            lowered = Path(relative).name.lower()
            if lowered in EXCLUDED_NAMES or any(
                fragment in lowered for fragment in EXCLUDED_FRAGMENTS
            ):
                return False, len(seen), f"credential-like path rejected: {relative}"
            if item.get("kind") not in {"json", "jsonl"}:
                return False, len(seen), f"unsupported kind: {relative}"
            content = str(item.get("content", ""))
            raw = content.encode("utf-8")
            if int(item.get("size_bytes", -1)) != len(raw):
                return False, len(seen), f"size mismatch: {relative}"
            if item.get("sha256") != _sha256(raw):
                return False, len(seen), f"hash mismatch: {relative}"
            try:
                if item["kind"] == "json":
                    json.loads(content)
                else:
                    for line in content.splitlines():
                        if line.strip():
                            json.loads(line)
            except json.JSONDecodeError:
                return False, len(seen), f"invalid embedded JSON: {relative}"
            manifest.append(
                {key: item[key] for key in ("path", "kind", "size_bytes", "sha256")}
            )
        material = json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if bundle.get("manifest_sha256") != _sha256(material):
            return False, len(seen), "manifest hash mismatch"
        return True, len(seen), None

    def import_bundle(
        self,
        bundle: dict[str, Any],
        *,
        conflict: str = "replace",
    ) -> dict[str, Any]:
        if conflict not in {"replace", "skip", "fail"}:
            raise ValueError("conflict must be replace, skip, or fail")
        valid, count, error = self.verify_bundle(bundle)
        if not valid:
            raise ValueError(error or "invalid portable save")
        staged: list[tuple[Path, str]] = []
        skipped: list[str] = []
        for item in bundle["files"]:
            relative = _safe_relative(str(item["path"]))
            destination = self.root / relative
            if destination.exists():
                if conflict == "skip":
                    skipped.append(relative.as_posix())
                    continue
                if conflict == "fail":
                    raise FileExistsError(relative.as_posix())
            staged.append((destination, str(item["content"])))
        for destination, content in staged:
            _atomic_write_text(destination, content)
        return {
            "valid": True,
            "verified_files": count,
            "written_files": len(staged),
            "skipped_files": skipped,
            "contains_api_keys": False,
        }

    def import_file(
        self, input_path: str | Path, *, conflict: str = "replace"
    ) -> dict[str, Any]:
        bundle = json.loads(Path(input_path).read_text(encoding="utf-8"))
        return self.import_bundle(bundle, conflict=conflict)
