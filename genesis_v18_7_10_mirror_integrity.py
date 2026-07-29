# -*- coding: utf-8 -*-
"""Fail-closed isolation and evidence integrity for Genesis counterfactual mirrors."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from genesis_v18_7_10 import COUNTERFACTUAL_SCHEMA, _iso_utc, sha256_canonical


class MirrorIsolationIntegrityMixin:
    """Keep unrealized branches physically separate and canonically non-authoritative."""

    MIRROR_MANIFEST_NAME = "unrealized_mirror_manifest.json"
    MIRROR_METRIC_CONTRACT = "flat_finite_numeric_v1"
    _MIRROR_METRIC_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
    _CANONICAL_AUDIT_BOOKKEEPING = frozenset({"i0_audit_v18_7_10.json"})

    @staticmethod
    def _path_is_within(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True

    @classmethod
    def _assert_disjoint_roots(cls, canonical_root: Path, mirror_root: Path) -> None:
        canonical = canonical_root.resolve()
        mirror = mirror_root.resolve()
        if (
            mirror == canonical
            or cls._path_is_within(mirror, canonical)
            or cls._path_is_within(canonical, mirror)
        ):
            raise ValueError("MIRROR_ROOT_MUST_BE_DISJOINT_FROM_CANON")

    @classmethod
    def _file_manifest(
        cls,
        root: Path,
        *,
        exclude_relative_paths: frozenset[str] = frozenset(),
    ) -> list[dict[str, Any]]:
        root = root.resolve()
        manifest: list[dict[str, Any]] = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise RuntimeError(f"SYMLINK_FORBIDDEN_IN_AUDIT_STATE: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in exclude_relative_paths:
                continue
            raw = path.read_bytes()
            manifest.append(
                {
                    "path": relative,
                    "size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        return manifest

    def _canonical_protected_manifest(self) -> list[dict[str, Any]]:
        return self._file_manifest(
            Path(self.memory.root),
            exclude_relative_paths=self._CANONICAL_AUDIT_BOOKKEEPING,
        )

    @classmethod
    def _sanitize_mirror_metrics(cls, metrics: dict[str, Any]) -> dict[str, float]:
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
        """Fork a byte-verified, disjoint data directory and open a separate runtime."""
        audit_store = self._i0_store()
        if audit_id not in audit_store["audits"]:
            raise KeyError(audit_id)
        if audit_store["audits"][audit_id].get("status") != "RUNNING":
            raise RuntimeError("COUNTERFACTUAL_REQUIRES_RUNNING_AUDIT")

        canonical_root = Path(self.memory.root).resolve()
        if (canonical_root / self.MIRROR_MANIFEST_NAME).is_file():
            raise PermissionError("NESTED_COUNTERFACTUAL_FORK_FORBIDDEN")
        destination = (
            Path(mirror_root).resolve()
            if mirror_root is not None
            else Path(tempfile.mkdtemp(prefix="genesis-unrealized-mirror-")).resolve()
        )
        self._assert_disjoint_roots(canonical_root, destination)
        if destination.exists() and any(destination.iterdir()):
            raise ValueError("MIRROR_ROOT_MUST_BE_EMPTY")
        destination.mkdir(parents=True, exist_ok=True)

        canonical_manifest = self._canonical_protected_manifest()
        canonical_snapshot_sha256 = sha256_canonical(canonical_manifest)
        try:
            for source in canonical_root.rglob("*"):
                if source.is_symlink():
                    raise RuntimeError(f"SYMLINK_FORBIDDEN_IN_AUDIT_STATE: {source}")
                if not source.is_file():
                    continue
                relative = source.relative_to(canonical_root)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            copied_manifest = self._file_manifest(
                destination,
                exclude_relative_paths=self._CANONICAL_AUDIT_BOOKKEEPING,
            )
            copied_snapshot_sha256 = sha256_canonical(copied_manifest)
            if copied_manifest != canonical_manifest:
                raise RuntimeError("COUNTERFACTUAL_SNAPSHOT_COPY_MISMATCH")

            mirror_id = self._stable_id(
                "unrealized-mirror",
                audit_id,
                label,
                canonical_snapshot_sha256,
                _iso_utc(),
            )
            manifest = {
                "schema": COUNTERFACTUAL_SCHEMA,
                "mirror_id": mirror_id,
                "audit_id": audit_id,
                "label": str(label)[:160],
                "classification": "UNREALIZED_MIRROR",
                "branch_role": "COUNTERFACTUAL_ONLY",
                "canonical_mutation_allowed": False,
                "canonical_chronicle_shared": False,
                "canonical_hrain_shared": False,
                "storage_mode": "fully_isolated_data_directory_verified",
                "metric_contract": self.MIRROR_METRIC_CONTRACT,
                "canonical_snapshot_sha256": canonical_snapshot_sha256,
                "copied_snapshot_sha256": copied_snapshot_sha256,
                "snapshot_file_count": len(copied_manifest),
                "isolation_verified_at_fork": True,
                "working_root_fingerprint": hashlib.sha256(
                    str(destination).encode("utf-8")
                ).hexdigest(),
                "root": str(destination),
                "forked_at": _iso_utc(),
            }
            (destination / self.MIRROR_MANIFEST_NAME).write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            mirror = self.__class__(destination)
            audit = audit_store["audits"][audit_id]
            audit.setdefault("mirror_ids", []).append(mirror_id)
            audit_store.setdefault("active_mirrors", {})[mirror_id] = {
                "audit_id": audit_id,
                "classification": "UNREALIZED_MIRROR",
                "canonical_snapshot_sha256": canonical_snapshot_sha256,
                "working_root_fingerprint": manifest["working_root_fingerprint"],
                "opened_at": manifest["forked_at"],
            }
            audit_store["mirror_archives"][mirror_id] = {
                **{key: value for key, value in manifest.items() if key != "root"},
                "root": None,
                "raw_branch_persisted_in_canon": False,
                "status": "ACTIVE",
            }
            self._write_json(self.i0_audit_path, audit_store)
            return mirror, manifest
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    def _counterfactual_manifest(self) -> dict[str, Any]:
        path = Path(self.memory.root) / self.MIRROR_MANIFEST_NAME
        if not path.is_file():
            raise PermissionError("COUNTERFACTUAL_OPERATION_REQUIRES_MIRROR")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (
            manifest.get("schema") != COUNTERFACTUAL_SCHEMA
            or manifest.get("classification") != "UNREALIZED_MIRROR"
            or manifest.get("branch_role") != "COUNTERFACTUAL_ONLY"
            or manifest.get("canonical_mutation_allowed") is not False
        ):
            raise PermissionError("INVALID_COUNTERFACTUAL_MANIFEST")
        root_fingerprint = hashlib.sha256(
            str(Path(self.memory.root).resolve()).encode("utf-8")
        ).hexdigest()
        if manifest.get("working_root_fingerprint") != root_fingerprint:
            raise PermissionError("COUNTERFACTUAL_ROOT_FINGERPRINT_MISMATCH")
        return manifest

    def set_counterfactual_actor_trust_for_probe(
        self,
        player_id: str,
        handle: str,
        *,
        trust_percent: float,
        reason_code: str,
    ) -> dict[str, Any]:
        """Apply an explicit trust intervention that is impossible in canonical runtime."""
        manifest = self._counterfactual_manifest()
        value = float(trust_percent)
        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError("TRUST_PERCENT_OUT_OF_RANGE")
        store = self._free_store()
        profile = self._free_profile(store, str(player_id))
        actor = profile.get("others", {}).get(str(handle))
        if not isinstance(actor, dict):
            raise KeyError(handle)
        before = float(actor.get("trust", 0.0))
        after = value / 100.0
        actor["trust"] = after
        intervention = {
            "mirror_id": manifest["mirror_id"],
            "variable": "free_other.trust",
            "handle": str(handle),
            "before": before,
            "after": after,
            "reason_code": str(reason_code)[:120],
            "controlled_intervention": True,
            "canonical_mutation": False,
        }
        actor.setdefault("history", []).append(
            {
                "world_turn": int(store.get("world_turn", 0)),
                "event": "counterfactual_trust_intervention",
                "before": before,
                "after": after,
                "reason_code": intervention["reason_code"],
            }
        )
        self._write_json(self.free_other_path, store)
        self.memory.append_event(
            str(player_id), "counterfactual_probe_variable_set", intervention
        )
        return copy.deepcopy(intervention)

    def archive_counterfactual_mirror(
        self,
        mirror: Any,
        manifest: dict[str, Any],
        *,
        metrics: dict[str, Any],
        remove_working_copy: bool = True,
    ) -> dict[str, Any]:
        """Seal numeric evidence only, prove canon unchanged, then destroy working state."""
        sanitized_metrics = self._sanitize_mirror_metrics(metrics)
        if manifest.get("classification") != "UNREALIZED_MIRROR":
            raise ValueError("NOT_AN_UNREALIZED_MIRROR")
        root = Path(str(manifest["root"])).resolve()
        canonical_root = Path(self.memory.root).resolve()
        self._assert_disjoint_roots(canonical_root, root)
        if Path(mirror.memory.root).resolve() != root:
            raise ValueError("MIRROR_INSTANCE_ROOT_MISMATCH")
        branch_manifest = mirror._counterfactual_manifest()
        if branch_manifest.get("mirror_id") != manifest.get("mirror_id"):
            raise ValueError("MIRROR_MANIFEST_ID_MISMATCH")

        store = self._i0_store()
        active = store.setdefault("active_mirrors", {}).get(manifest["mirror_id"])
        if not isinstance(active, dict):
            raise RuntimeError("MIRROR_LEASE_NOT_ACTIVE")

        canonical_manifest = self._canonical_protected_manifest()
        canonical_snapshot_at_archive = sha256_canonical(canonical_manifest)
        expected_snapshot = str(manifest["canonical_snapshot_sha256"])
        if canonical_snapshot_at_archive != expected_snapshot:
            failed = {
                "schema": COUNTERFACTUAL_SCHEMA,
                "mirror_id": manifest["mirror_id"],
                "audit_id": manifest["audit_id"],
                "classification": "UNREALIZED_MIRROR",
                "status": "FAIL_CLOSED_CANONICAL_CONTAMINATION",
                "canonical_mutation_allowed": False,
                "isolation_verified": False,
                "expected_canonical_snapshot_sha256": expected_snapshot,
                "observed_canonical_snapshot_sha256": canonical_snapshot_at_archive,
                "archived_at": _iso_utc(),
            }
            store["mirror_archives"][manifest["mirror_id"]] = failed
            self._write_json(self.i0_audit_path, store)
            raise RuntimeError("CANONICAL_STATE_CHANGED_DURING_MIRROR_PROBE")

        file_manifest = self._file_manifest(root)
        archive = {
            "schema": COUNTERFACTUAL_SCHEMA,
            "mirror_id": manifest["mirror_id"],
            "audit_id": manifest["audit_id"],
            "classification": "UNREALIZED_MIRROR",
            "status": "ARCHIVED",
            "canonical_mutation_allowed": False,
            "canonical_snapshot_sha256": expected_snapshot,
            "canonical_snapshot_sha256_at_archive": canonical_snapshot_at_archive,
            "isolation_verified": True,
            "mirror_file_manifest_sha256": sha256_canonical(file_manifest),
            "mirror_file_count": len(file_manifest),
            "metric_contract": self.MIRROR_METRIC_CONTRACT,
            "metrics": sanitized_metrics,
            "metrics_sha256": sha256_canonical(sanitized_metrics),
            "archived_at": _iso_utc(),
            "raw_dialogue_in_canonical_archive": False,
            "raw_branch_persisted_in_canon": False,
            "working_copy_removed": False,
        }
        if remove_working_copy:
            shutil.rmtree(root)
            archive["working_copy_removed"] = not root.exists()
            if not archive["working_copy_removed"]:
                raise RuntimeError("MIRROR_WORKING_COPY_REMOVAL_FAILED")
        store["mirror_archives"][manifest["mirror_id"]] = archive
        store["active_mirrors"].pop(manifest["mirror_id"], None)
        self._write_json(self.i0_audit_path, store)
        return copy.deepcopy(archive)

    def butterfly_witness(
        self,
        *,
        audit_id: str,
        subject: str,
        canonical_metrics: dict[str, float],
        mirror_metrics: list[dict[str, float]],
        repeated_windows: int,
    ) -> dict[str, Any]:
        """Require directionally consistent repeated deltas before any promotion."""
        canonical = self._sanitize_mirror_metrics(canonical_metrics)
        mirrors = [self._sanitize_mirror_metrics(item) for item in mirror_metrics]
        windows = int(repeated_windows)
        shared_keys = (
            sorted(set(canonical).intersection(*(set(item) for item in mirrors)))
            if mirrors
            else []
        )
        stable_keys: list[str] = []
        unstable_keys: list[str] = []
        for key in shared_keys:
            baseline = canonical[key]
            deltas = [item[key] - baseline for item in mirrors]
            nonzero = all(abs(delta) > 1e-9 for delta in deltas)
            same_direction = all(delta > 0 for delta in deltas) or all(
                delta < 0 for delta in deltas
            )
            if nonzero and same_direction:
                stable_keys.append(key)
            else:
                unstable_keys.append(key)

        if windows <= 0:
            verdict = "ANECDOTE_ONLY"
        elif not mirrors:
            verdict = "COUNTERFACTUAL_REQUIRED"
        elif windows < 2 or len(mirrors) < 2:
            verdict = "REPLAY_SAME_SEED"
        elif not stable_keys:
            verdict = "ANECDOTE_ONLY"
        elif len(stable_keys) >= 2 and windows >= 3 and len(mirrors) >= 3:
            verdict = "CANON_CHANGE_CANDIDATE"
        else:
            verdict = "PROMOTE_TO_REGRESSION"

        report = {
            "schema": "janus.genesis.butterfly_witness.v2",
            "audit_id": audit_id,
            "subject": str(subject)[:240],
            "canonical_metrics": canonical,
            "canonical_metrics_sha256": sha256_canonical(canonical),
            "mirror_metrics_sha256": sha256_canonical(mirrors),
            "mirror_count": len(mirrors),
            "repeated_windows": windows,
            "stable_metric_keys": stable_keys,
            "unstable_metric_keys": unstable_keys,
            "verdict": verdict,
            "rule": "do not confuse one beautiful event with a law",
            "canonical_mutation": False,
            "written_at": _iso_utc(),
        }
        store = self._i0_store()
        if audit_id not in store["audits"]:
            raise KeyError(audit_id)
        report_id = self._stable_id("butterfly-report-v2", sha256_canonical(report))
        report["report_id"] = report_id
        store["butterfly_reports"][report_id] = report
        self._write_json(self.i0_audit_path, store)
        return copy.deepcopy(report)
