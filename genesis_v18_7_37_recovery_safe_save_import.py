# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.37 — recovery-safe portable-save import saga.

The historical portable-save importer verifies the complete source bundle and
uses an atomic replacement for each individual file, but a multi-file import is
not one filesystem transaction. A crash can therefore leave some targets from
the new bundle and others from the old state.

v18.7.37 keeps that history intact and adds an explicit roll-forward saga:

- one process-global + OS import lock for cooperating importers;
- one logical import_request_id bound to one manifest hash + conflict policy;
- all selected source files are durably staged before any target mutation;
- a durable transaction manifest records the complete target plan;
- target replacement is hash-idempotent and may be repeated after a crash;
- recovery treats an already matching target hash as a completed commit even if
  the process crashed before progress metadata was updated;
- only after every selected target has the expected hash is the request marked
  SETTLED and a final receipt persisted.

This is a recovery-safe roll-forward saga, not an atomic multi-file filesystem
transaction. Non-cooperating writers that bypass the import lock remain outside
the guarantee; skip/fail plans detect unexpected target appearance and fail
closed rather than overwriting it.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_portable import PortableSaveManager, _safe_relative
from janus_portable_lock_v2 import PortableProcessLockV2

RECOVERY_SAFE_IMPORT_VERSION = "18.7.37"
RECOVERY_SAFE_IMPORT_SCHEMA = "janus.genesis.recovery_safe_import.v1"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


class RecoverySafeImportError(RuntimeError):
    code = "RECOVERY_SAFE_IMPORT_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ImportRequestConflict(RecoverySafeImportError):
    code = "IMPORT_REQUEST_ID_BINDING_CONFLICT"


class ImportPlanConflict(RecoverySafeImportError):
    code = "IMPORT_PLAN_TARGET_CONFLICT"


class ImportStageIntegrityError(RecoverySafeImportError):
    code = "IMPORT_STAGE_INTEGRITY_ERROR"


class ImportCrashPoint(str, Enum):
    AFTER_REQUEST_BOUND = "AFTER_REQUEST_BOUND"
    AFTER_PREPARED = "AFTER_PREPARED"
    AFTER_TARGET_WRITE_BEFORE_PROGRESS = "AFTER_TARGET_WRITE_BEFORE_PROGRESS"
    AFTER_ALL_TARGETS_BEFORE_SETTLED = "AFTER_ALL_TARGETS_BEFORE_SETTLED"


class ImportCrashInjector:
    """One-shot deterministic crash injection, optionally limited to target ordinal."""

    def __init__(
        self,
        point: ImportCrashPoint | str | None = None,
        *,
        target_ordinal: int | None = None,
    ) -> None:
        self.point = None if point is None else ImportCrashPoint(
            point.value if isinstance(point, ImportCrashPoint) else str(point)
        )
        self.target_ordinal = target_ordinal
        self.used = False

    def hit(self, point: ImportCrashPoint, *, target_ordinal: int | None = None) -> None:
        if self.used or self.point is not point:
            return
        if self.target_ordinal is not None and self.target_ordinal != target_ordinal:
            return
        self.used = True
        raise RecoverySafeImportError(
            f"INJECTED_IMPORT_CRASH:{point.value}:target={target_ordinal}"
        )


@dataclass(frozen=True)
class DurableFileWriteReceipt:
    path: str
    file_fsynced: bool
    replaced: bool
    directory_fsynced: bool
    directory_fsync_supported: bool


class DurableBytesWriter:
    """Unique same-directory temp + fsync + replace + final-file fsync."""

    def write(self, path: str | Path, raw: bytes) -> DurableFileWriteReceipt:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        directory_supported = os.name != "nt"
        directory_synced = False
        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            temporary = Path(temp_name)
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            temporary = None

            final_fd = os.open(str(target), os.O_RDWR)
            try:
                os.fsync(final_fd)
            finally:
                os.close(final_fd)

            if directory_supported:
                flags = os.O_RDONLY
                if hasattr(os, "O_DIRECTORY"):
                    flags |= os.O_DIRECTORY
                dir_fd = os.open(str(target.parent), flags)
                try:
                    os.fsync(dir_fd)
                    directory_synced = True
                finally:
                    os.close(dir_fd)

            return DurableFileWriteReceipt(
                path=str(target),
                file_fsynced=True,
                replaced=True,
                directory_fsynced=directory_synced,
                directory_fsync_supported=directory_supported,
            )
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


class RecoverySafePortableSaveManager(PortableSaveManager):
    """PortableSaveManager descendant with stable-request roll-forward imports."""

    CONTROL_DIR = ".janus_control/save_import_v18_7_37"

    def __init__(
        self,
        data_dir: str | Path,
        *,
        crash_injector: ImportCrashInjector | None = None,
    ) -> None:
        super().__init__(data_dir)
        self.control_root = self.root / self.CONTROL_DIR
        self.requests_dir = self.control_root / "requests"
        self.transactions_dir = self.control_root / "transactions"
        self.lock = PortableProcessLockV2(self.control_root / "save_import.lock")
        self.writer = DurableBytesWriter()
        self.crash_injector = crash_injector or ImportCrashInjector()

    @staticmethod
    def _request_key(request_id: str) -> str:
        return hashlib.sha256(str(request_id).encode("utf-8")).hexdigest()

    def _request_path(self, request_id: str) -> Path:
        return self.requests_dir / f"{self._request_key(request_id)}.control"

    def _transaction_dir(self, transaction_id: str) -> Path:
        return self.transactions_dir / transaction_id

    def _transaction_manifest_path(self, transaction_id: str) -> Path:
        return self._transaction_dir(transaction_id) / "manifest.control"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise RecoverySafeImportError(f"CONTROL_RECORD_NOT_OBJECT:{path}")
        return value

    def _write_json(self, path: Path, value: Mapping[str, Any]) -> None:
        self.writer.write(
            path,
            (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )

    @staticmethod
    def _bundle_identity(bundle: Mapping[str, Any]) -> str:
        # The source manifest already covers path/kind/size/hash. Bind the
        # request to schema/runtime/manifest/file_count as a stable import identity.
        return _sha256_json(
            {
                "schema": bundle.get("schema"),
                "runtime_version": bundle.get("runtime_version"),
                "manifest_sha256": bundle.get("manifest_sha256"),
                "file_count": bundle.get("file_count"),
            }
        )

    def _bind_request(
        self,
        *,
        request_id: str,
        bundle_identity: str,
        conflict: str,
    ) -> dict[str, Any]:
        request = str(request_id).strip()
        if not request or len(request) > 240:
            raise ValueError("IMPORT_REQUEST_ID_REQUIRED")
        path = self._request_path(request)
        existing = self._read_json(path)
        if existing is not None:
            if (
                existing.get("request_id") != request
                or existing.get("bundle_identity") != bundle_identity
                or existing.get("conflict") != conflict
            ):
                raise ImportRequestConflict(
                    f"request_id={request};existing_bundle={existing.get('bundle_identity')};"
                    f"new_bundle={bundle_identity};existing_conflict={existing.get('conflict')};"
                    f"new_conflict={conflict}"
                )
            return existing

        transaction_id = "IMPORT-" + _sha256_json(
            {"request_id": request, "bundle_identity": bundle_identity, "conflict": conflict}
        )[:32]
        record = {
            "schema": RECOVERY_SAFE_IMPORT_SCHEMA,
            "request_id": request,
            "bundle_identity": bundle_identity,
            "conflict": conflict,
            "transaction_id": transaction_id,
            "state": "BOUND",
            "receipt": None,
        }
        self._write_json(path, record)
        return record

    def _stage_plan(
        self,
        *,
        request_record: dict[str, Any],
        bundle: dict[str, Any],
    ) -> dict[str, Any]:
        transaction_id = str(request_record["transaction_id"])
        manifest_path = self._transaction_manifest_path(transaction_id)
        existing = self._read_json(manifest_path)
        if existing is not None:
            return existing

        transaction_dir = self._transaction_dir(transaction_id)
        stage_dir = transaction_dir / "stage"
        entries: list[dict[str, Any]] = []
        skipped: list[str] = []
        conflict = str(request_record["conflict"])

        for ordinal, item in enumerate(bundle["files"]):
            relative = _safe_relative(str(item["path"]))
            destination = self.root / relative
            exists_at_prepare = destination.exists()
            if exists_at_prepare and conflict == "skip":
                skipped.append(relative.as_posix())
                continue
            if exists_at_prepare and conflict == "fail":
                raise FileExistsError(relative.as_posix())

            content = str(item["content"]).encode("utf-8")
            expected_hash = str(item["sha256"])
            if _sha256_bytes(content) != expected_hash:
                raise ImportStageIntegrityError(
                    f"SOURCE_HASH_DRIFT_DURING_PREPARE:{relative.as_posix()}"
                )
            stage_path = stage_dir / f"{ordinal:06d}.stage"
            self.writer.write(stage_path, content)
            if _sha256_bytes(stage_path.read_bytes()) != expected_hash:
                raise ImportStageIntegrityError(
                    f"STAGE_HASH_MISMATCH:{relative.as_posix()}"
                )
            entries.append(
                {
                    "ordinal": ordinal,
                    "relative_path": relative.as_posix(),
                    "stage_path": stage_path.relative_to(transaction_dir).as_posix(),
                    "expected_sha256": expected_hash,
                    "prepared_target_existed": exists_at_prepare,
                    "committed": False,
                }
            )

        manifest = {
            "schema": RECOVERY_SAFE_IMPORT_SCHEMA,
            "transaction_id": transaction_id,
            "request_id": request_record["request_id"],
            "bundle_identity": request_record["bundle_identity"],
            "conflict": conflict,
            "state": "PREPARED",
            "entries": entries,
            "skipped_files": skipped,
        }
        self._write_json(manifest_path, manifest)
        request_record = dict(request_record)
        request_record["state"] = "PREPARED"
        self._write_json(self._request_path(str(request_record["request_id"])), request_record)
        return manifest

    def _stage_bytes(self, manifest: Mapping[str, Any], entry: Mapping[str, Any]) -> bytes:
        transaction_dir = self._transaction_dir(str(manifest["transaction_id"]))
        stage_relative = _safe_relative(str(entry["stage_path"]))
        stage_path = transaction_dir / stage_relative
        if not stage_path.exists():
            raise ImportStageIntegrityError(
                f"STAGE_MISSING:{entry['relative_path']}"
            )
        raw = stage_path.read_bytes()
        if _sha256_bytes(raw) != entry["expected_sha256"]:
            raise ImportStageIntegrityError(
                f"STAGE_HASH_MISMATCH:{entry['relative_path']}"
            )
        return raw

    def _commit(self, manifest: dict[str, Any]) -> dict[str, Any]:
        manifest_path = self._transaction_manifest_path(str(manifest["transaction_id"]))
        mutable = json.loads(json.dumps(manifest))
        mutable["state"] = "COMMITTING"
        self._write_json(manifest_path, mutable)

        for index, entry in enumerate(mutable["entries"]):
            relative = _safe_relative(str(entry["relative_path"]))
            destination = self.root / relative
            expected_hash = str(entry["expected_sha256"])

            if destination.exists() and _sha256_bytes(destination.read_bytes()) == expected_hash:
                entry["committed"] = True
                self._write_json(manifest_path, mutable)
                continue

            if (
                mutable["conflict"] in {"skip", "fail"}
                and not bool(entry["prepared_target_existed"])
                and destination.exists()
            ):
                raise ImportPlanConflict(
                    f"TARGET_APPEARED_AFTER_PREPARE:{relative.as_posix()}"
                )

            raw = self._stage_bytes(mutable, entry)
            self.writer.write(destination, raw)
            if _sha256_bytes(destination.read_bytes()) != expected_hash:
                raise ImportStageIntegrityError(
                    f"TARGET_HASH_MISMATCH_AFTER_WRITE:{relative.as_posix()}"
                )
            self.crash_injector.hit(
                ImportCrashPoint.AFTER_TARGET_WRITE_BEFORE_PROGRESS,
                target_ordinal=index,
            )
            entry["committed"] = True
            self._write_json(manifest_path, mutable)

        self.crash_injector.hit(ImportCrashPoint.AFTER_ALL_TARGETS_BEFORE_SETTLED)
        mutable["state"] = "SETTLED"
        self._write_json(manifest_path, mutable)
        return mutable

    def import_bundle_recoverable(
        self,
        bundle: dict[str, Any],
        *,
        request_id: str,
        conflict: str = "replace",
    ) -> dict[str, Any]:
        if conflict not in {"replace", "skip", "fail"}:
            raise ValueError("conflict must be replace, skip, or fail")
        valid, verified_count, error = self.verify_bundle(bundle)
        if not valid:
            raise ValueError(error or "invalid portable save")
        bundle_identity = self._bundle_identity(bundle)

        with self.lock.exclusive():
            request_record = self._bind_request(
                request_id=request_id,
                bundle_identity=bundle_identity,
                conflict=conflict,
            )
            if request_record.get("state") == "SETTLED":
                receipt = request_record.get("receipt")
                if not isinstance(receipt, dict):
                    raise RecoverySafeImportError("SETTLED_REQUEST_MISSING_RECEIPT")
                return dict(receipt)
            self.crash_injector.hit(ImportCrashPoint.AFTER_REQUEST_BOUND)

            manifest = self._stage_plan(
                request_record=request_record,
                bundle=bundle,
            )
            self.crash_injector.hit(ImportCrashPoint.AFTER_PREPARED)
            settled_manifest = self._commit(manifest)

            receipt = {
                "valid": True,
                "request_id": str(request_id).strip(),
                "transaction_id": settled_manifest["transaction_id"],
                "bundle_identity": bundle_identity,
                "verified_files": verified_count,
                "written_files": len(settled_manifest["entries"]),
                "skipped_files": list(settled_manifest["skipped_files"]),
                "state": "SETTLED",
                "recovery_model": "DURABLE_ROLL_FORWARD_SAGA_NOT_MULTI_FILE_ATOMIC_TRANSACTION",
                "contains_api_keys": False,
                "contains_private_keys": False,
            }
            final_request = self._read_json(self._request_path(str(request_id).strip()))
            if final_request is None:
                raise RecoverySafeImportError("IMPORT_REQUEST_RECORD_DISAPPEARED")
            final_request["state"] = "SETTLED"
            final_request["receipt"] = receipt
            self._write_json(self._request_path(str(request_id).strip()), final_request)
            return receipt

    def import_file_recoverable(
        self,
        input_path: str | Path,
        *,
        request_id: str,
        conflict: str = "replace",
    ) -> dict[str, Any]:
        bundle = json.loads(Path(input_path).read_text(encoding="utf-8"))
        return self.import_bundle_recoverable(
            bundle,
            request_id=request_id,
            conflict=conflict,
        )

    def request_state(self, request_id: str) -> dict[str, Any] | None:
        with self.lock.shared():
            record = self._read_json(self._request_path(str(request_id).strip()))
            return None if record is None else dict(record)


__all__ = [
    "RECOVERY_SAFE_IMPORT_VERSION",
    "RECOVERY_SAFE_IMPORT_SCHEMA",
    "RecoverySafeImportError",
    "ImportRequestConflict",
    "ImportPlanConflict",
    "ImportStageIntegrityError",
    "ImportCrashPoint",
    "ImportCrashInjector",
    "DurableBytesWriter",
    "RecoverySafePortableSaveManager",
]
