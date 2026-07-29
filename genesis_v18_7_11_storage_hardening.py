# -*- coding: utf-8 -*-
"""Storage-domain preparation and crash-safe mirror sealing for Genesis v18.7.11."""
from __future__ import annotations

import copy
import hashlib
import math
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from genesis_v18_7_10 import COUNTERFACTUAL_SCHEMA, _iso_utc, sha256_canonical


@dataclass(frozen=True, slots=True)
class StorageDomain:
    """A capability boundary around one physical Genesis state root."""

    domain_id: str
    role: str
    backend: str
    root: str
    canonical_writes_allowed: bool
    sqlite_attach_allowed: bool = False

    def assert_write_target(self, target: str | Path) -> Path:
        root = Path(self.root).resolve()
        candidate = Path(target).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError("STORAGE_DOMAIN_WRITE_ESCAPE") from exc
        if self.role == "UNREALIZED_MIRROR" and self.canonical_writes_allowed:
            raise PermissionError("MIRROR_DOMAIN_CANNOT_HAVE_CANONICAL_WRITE_CAPABILITY")
        return candidate


class SealedMirrorStorageMixin:
    """Harden file IO and make interrupted mirror deletion recoverable."""

    MIRROR_MAX_FILES = 8192
    MIRROR_MAX_FILE_BYTES = 64 * 1024 * 1024
    MIRROR_MAX_TOTAL_BYTES = 512 * 1024 * 1024
    MIRROR_METRIC_CONTRACT = "flat_finite_numeric_v1"

    @staticmethod
    def _storage_domain_id(role: str, root: Path) -> str:
        raw = f"{role}\x1f{root.resolve()}\x1fjson-sidecar-v1".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def storage_domain(self) -> StorageDomain:
        root = Path(self.memory.root).resolve()
        manifest = root / self.MIRROR_MANIFEST_NAME
        role = "UNREALIZED_MIRROR" if manifest.is_file() else "CANONICAL"
        return StorageDomain(
            domain_id=self._storage_domain_id(role, root),
            role=role,
            backend="json-sidecar-v1",
            root=str(root),
            canonical_writes_allowed=role == "CANONICAL",
            sqlite_attach_allowed=False,
        )

    @classmethod
    def _file_manifest(
        cls,
        root: Path,
        *,
        exclude_relative_paths: frozenset[str] = frozenset(),
    ) -> list[dict[str, Any]]:
        """Hash a bounded tree while rejecting symlinks and shared inodes."""
        root = root.resolve()
        if not root.exists():
            raise FileNotFoundError(root)
        if root.is_symlink():
            raise RuntimeError(f"SYMLINK_FORBIDDEN_IN_AUDIT_STATE: {root}")

        manifest: list[dict[str, Any]] = []
        total_bytes = 0
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise RuntimeError(f"SYMLINK_FORBIDDEN_IN_AUDIT_STATE: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in exclude_relative_paths:
                continue
            stat = path.lstat()
            if stat.st_nlink != 1:
                raise RuntimeError(f"HARDLINK_FORBIDDEN_IN_AUDIT_STATE: {path}")
            if stat.st_size > cls.MIRROR_MAX_FILE_BYTES:
                raise RuntimeError(f"MIRROR_FILE_SIZE_LIMIT_EXCEEDED: {relative}")
            total_bytes += int(stat.st_size)
            if total_bytes > cls.MIRROR_MAX_TOTAL_BYTES:
                raise RuntimeError("MIRROR_TOTAL_SIZE_LIMIT_EXCEEDED")
            if len(manifest) >= cls.MIRROR_MAX_FILES:
                raise RuntimeError("MIRROR_FILE_COUNT_LIMIT_EXCEEDED")
            raw = path.read_bytes()
            manifest.append(
                {
                    "path": relative,
                    "size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "inode_links": int(stat.st_nlink),
                }
            )
        return manifest

    @classmethod
    def _sanitize_mirror_metrics(cls, metrics: dict[str, Any]) -> dict[str, float]:
        """Accept only flat finite numeric values; bool is normalized explicitly."""
        if not isinstance(metrics, dict):
            raise TypeError("MIRROR_METRICS_MUST_BE_AN_OBJECT")
        if len(metrics) > 64:
            raise ValueError("MIRROR_METRIC_LIMIT_EXCEEDED")
        sanitized: dict[str, float] = {}
        for raw_key, raw_value in metrics.items():
            key = str(raw_key)
            if not cls._MIRROR_METRIC_KEY.fullmatch(key):
                raise ValueError(f"INVALID_MIRROR_METRIC_KEY: {key}")
            if isinstance(raw_value, bool):
                value = 1.0 if raw_value else 0.0
            elif isinstance(raw_value, (int, float)):
                value = float(raw_value)
            else:
                raise TypeError(f"MIRROR_METRIC_MUST_BE_NUMERIC: {key}")
            if not math.isfinite(value):
                raise ValueError(f"MIRROR_METRIC_MUST_BE_FINITE: {key}")
            sanitized[key] = value
        return sanitized

    def fork_counterfactual_world(
        self,
        *,
        audit_id: str,
        label: str,
        mirror_root: str | Path | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        mirror, manifest = super().fork_counterfactual_world(
            audit_id=audit_id,
            label=label,
            mirror_root=mirror_root,
        )
        root = Path(str(manifest["root"])).resolve()
        try:
            os.chmod(root, 0o700)
        except OSError as exc:
            shutil.rmtree(root, ignore_errors=True)
            raise RuntimeError("MIRROR_ROOT_PERMISSION_HARDENING_FAILED") from exc

        canonical_domain = self.storage_domain()
        mirror_domain = mirror.storage_domain()
        if canonical_domain.domain_id == mirror_domain.domain_id:
            shutil.rmtree(root, ignore_errors=True)
            raise RuntimeError("STORAGE_DOMAIN_COLLISION")
        if canonical_domain.role != "CANONICAL":
            shutil.rmtree(root, ignore_errors=True)
            raise PermissionError("COUNTERFACTUAL_FORK_REQUIRES_CANONICAL_DOMAIN")
        if mirror_domain.role != "UNREALIZED_MIRROR":
            shutil.rmtree(root, ignore_errors=True)
            raise PermissionError("MIRROR_STORAGE_DOMAIN_ROLE_MISMATCH")

        manifest = {
            **manifest,
            "storage_contract": "separate-domain-capability-v1",
            "canonical_storage_domain_id": canonical_domain.domain_id,
            "mirror_storage_domain_id": mirror_domain.domain_id,
            "mirror_root_mode": "0700",
            "sqlite_future_contract": {
                "separate_database_file_required": True,
                "separate_connection_required": True,
                "separate_wal_shm_required": True,
                "attach_database_forbidden": True,
                "canonical_transaction_reuse_forbidden": True,
            },
        }
        mirror.memory._atomic_write(root / self.MIRROR_MANIFEST_NAME, manifest)

        store = self._i0_store()
        active = store.setdefault("active_mirrors", {}).get(manifest["mirror_id"])
        if not isinstance(active, dict):
            shutil.rmtree(root, ignore_errors=True)
            raise RuntimeError("MIRROR_LEASE_NOT_ACTIVE_AFTER_FORK")
        active.update(
            {
                "working_root": str(root),
                "canonical_storage_domain_id": canonical_domain.domain_id,
                "mirror_storage_domain_id": mirror_domain.domain_id,
                "phase": "ACTIVE",
            }
        )
        archive = store.setdefault("mirror_archives", {}).get(manifest["mirror_id"])
        if isinstance(archive, dict):
            archive.update(
                {
                    "storage_contract": manifest["storage_contract"],
                    "canonical_storage_domain_id": canonical_domain.domain_id,
                    "mirror_storage_domain_id": mirror_domain.domain_id,
                }
            )
        self._write_json(self.i0_audit_path, store)
        return mirror, copy.deepcopy(manifest)

    def archive_counterfactual_mirror(
        self,
        mirror: Any,
        manifest: dict[str, Any],
        *,
        metrics: dict[str, Any],
        remove_working_copy: bool = True,
    ) -> dict[str, Any]:
        """Prepare evidence first so a crash during deletion can be recovered."""
        sanitized = self._sanitize_mirror_metrics(metrics)
        root = Path(str(manifest["root"])).resolve()
        self._assert_disjoint_roots(Path(self.memory.root).resolve(), root)
        file_manifest = self._file_manifest(root)

        store = self._i0_store()
        active = store.setdefault("active_mirrors", {}).get(manifest["mirror_id"])
        if not isinstance(active, dict):
            raise RuntimeError("MIRROR_LEASE_NOT_ACTIVE")
        active.update(
            {
                "working_root": str(root),
                "phase": "ARCHIVE_PREPARED",
            }
        )
        prepared = {
            "schema": COUNTERFACTUAL_SCHEMA,
            "mirror_id": manifest["mirror_id"],
            "audit_id": manifest["audit_id"],
            "classification": "UNREALIZED_MIRROR",
            "status": "ARCHIVE_PREPARED",
            "canonical_mutation_allowed": False,
            "canonical_snapshot_sha256": manifest["canonical_snapshot_sha256"],
            "mirror_file_manifest_sha256": sha256_canonical(file_manifest),
            "mirror_file_count": len(file_manifest),
            "metric_contract": self.MIRROR_METRIC_CONTRACT,
            "metrics": sanitized,
            "metrics_sha256": sha256_canonical(sanitized),
            "working_root_fingerprint": manifest["working_root_fingerprint"],
            "storage_contract": manifest.get("storage_contract"),
            "canonical_storage_domain_id": manifest.get(
                "canonical_storage_domain_id"
            ),
            "mirror_storage_domain_id": manifest.get("mirror_storage_domain_id"),
            "raw_dialogue_in_canonical_archive": False,
            "raw_branch_persisted_in_canon": False,
            "working_copy_removed": False,
            "prepared_at": _iso_utc(),
        }
        store.setdefault("mirror_archives", {})[manifest["mirror_id"]] = prepared
        self._write_json(self.i0_audit_path, store)

        archive = super().archive_counterfactual_mirror(
            mirror,
            manifest,
            metrics=sanitized,
            remove_working_copy=remove_working_copy,
        )
        archive["archive_protocol"] = "prepare-delete-commit-v1"
        archive["storage_contract"] = manifest.get("storage_contract")
        store = self._i0_store()
        store["mirror_archives"][manifest["mirror_id"]] = archive
        self._write_json(self.i0_audit_path, store)
        return copy.deepcopy(archive)

    def recover_incomplete_mirror_archives(self) -> list[dict[str, Any]]:
        """Finish deletion after a process crash without trusting stale canon."""
        root = Path(self.memory.root).resolve()
        if (root / self.MIRROR_MANIFEST_NAME).is_file():
            return []
        store = self._i0_store()
        recovered: list[dict[str, Any]] = []
        active_mirrors = store.setdefault("active_mirrors", {})
        archives = store.setdefault("mirror_archives", {})

        for mirror_id, active in list(active_mirrors.items()):
            archive = archives.get(mirror_id)
            if not isinstance(active, dict) or not isinstance(archive, dict):
                continue
            if archive.get("status") != "ARCHIVE_PREPARED":
                continue
            expected = str(archive.get("canonical_snapshot_sha256", ""))
            observed = sha256_canonical(self._canonical_protected_manifest())
            if not expected or observed != expected:
                archive.update(
                    {
                        "status": "FAIL_CLOSED_CANONICAL_CONTAMINATION",
                        "isolation_verified": False,
                        "observed_canonical_snapshot_sha256": observed,
                        "recovery_checked_at": _iso_utc(),
                    }
                )
                self._write_json(self.i0_audit_path, store)
                raise RuntimeError("CANONICAL_STATE_CHANGED_DURING_MIRROR_RECOVERY")

            working_root_raw = active.get("working_root")
            if not working_root_raw:
                raise RuntimeError("MIRROR_RECOVERY_ROOT_MISSING")
            working_root = Path(str(working_root_raw)).resolve()
            self._assert_disjoint_roots(root, working_root)
            fingerprint = hashlib.sha256(
                str(working_root).encode("utf-8")
            ).hexdigest()
            if fingerprint != archive.get("working_root_fingerprint"):
                raise RuntimeError("MIRROR_RECOVERY_ROOT_FINGERPRINT_MISMATCH")
            if working_root.is_symlink():
                raise RuntimeError("MIRROR_RECOVERY_SYMLINK_FORBIDDEN")
            if working_root.exists():
                shutil.rmtree(working_root)
            if working_root.exists():
                raise RuntimeError("MIRROR_WORKING_COPY_REMOVAL_FAILED")

            archive.update(
                {
                    "status": "ARCHIVED_RECOVERED",
                    "working_copy_removed": True,
                    "isolation_verified": True,
                    "archive_protocol": "prepare-delete-commit-v1",
                    "recovered_at": _iso_utc(),
                }
            )
            active_mirrors.pop(mirror_id, None)
            recovered.append(copy.deepcopy(archive))

        if recovered:
            self._write_json(self.i0_audit_path, store)
        return recovered

    def storage_contract_report(self) -> dict[str, Any]:
        domain = self.storage_domain()
        return {
            "schema": "janus.genesis.storage_contract.v1",
            "domain": asdict(domain),
            "mirror_max_files": self.MIRROR_MAX_FILES,
            "mirror_max_file_bytes": self.MIRROR_MAX_FILE_BYTES,
            "mirror_max_total_bytes": self.MIRROR_MAX_TOTAL_BYTES,
            "mirror_metric_contract": self.MIRROR_METRIC_CONTRACT,
            "archive_protocol": "prepare-delete-commit-v1",
            "sqlite_adapter_status": "INTERFACE_PREPARED_NOT_IMPLEMENTED",
            "sqlite_requirements": {
                "separate_database_file": True,
                "separate_connection": True,
                "separate_wal_shm": True,
                "attach_database_forbidden": True,
                "canonical_transaction_reuse_forbidden": True,
            },
        }
