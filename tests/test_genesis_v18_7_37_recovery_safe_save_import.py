from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from genesis_v18_7_37_recovery_safe_save_import import (
    ImportCrashInjector,
    ImportCrashPoint,
    ImportRequestConflict,
    RecoverySafeImportError,
    RecoverySafePortableSaveManager,
)
from genesis_v18_7_portable import PortableSaveManager


class RecoverySafeSaveImportTests(unittest.TestCase):
    @staticmethod
    def make_bundle(root: Path, values: dict[str, object]):
        root.mkdir(parents=True, exist_ok=True)
        for name, value in values.items():
            (root / name).write_text(
                json.dumps(value, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
        return PortableSaveManager(root).build_bundle(label="test-bundle")

    @staticmethod
    def read_json(root: Path, name: str):
        return json.loads((root / name).read_text(encoding="utf-8"))

    def test_crash_after_first_target_rolls_forward_on_same_request(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            bundle = self.make_bundle(
                source,
                {
                    "a.json": {"version": "new-a"},
                    "b.json": {"version": "new-b"},
                },
            )
            self.make_bundle(
                target,
                {
                    "a.json": {"version": "old-a"},
                    "b.json": {"version": "old-b"},
                },
            )

            crashing = RecoverySafePortableSaveManager(
                target,
                crash_injector=ImportCrashInjector(
                    ImportCrashPoint.AFTER_TARGET_WRITE_BEFORE_PROGRESS,
                    target_ordinal=0,
                ),
            )
            with self.assertRaises(RecoverySafeImportError):
                crashing.import_bundle_recoverable(
                    bundle,
                    request_id="IMPORT-1",
                    conflict="replace",
                )

            # A partial target state is possible at the crash point; the control
            # objective is that the same request can deterministically finish it.
            recovered = RecoverySafePortableSaveManager(target).import_bundle_recoverable(
                bundle,
                request_id="IMPORT-1",
                conflict="replace",
            )
            self.assertEqual(recovered["state"], "SETTLED")
            self.assertEqual(self.read_json(target, "a.json"), {"version": "new-a"})
            self.assertEqual(self.read_json(target, "b.json"), {"version": "new-b"})
            self.assertIn("ROLL_FORWARD_SAGA", recovered["recovery_model"])

    def test_crash_after_all_targets_before_settlement_recovers_without_content_drift(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            bundle = self.make_bundle(
                source,
                {"a.json": {"v": 2}, "b.json": {"v": 3}},
            )
            self.make_bundle(target, {"a.json": {"v": 0}, "b.json": {"v": 0}})

            crashing = RecoverySafePortableSaveManager(
                target,
                crash_injector=ImportCrashInjector(
                    ImportCrashPoint.AFTER_ALL_TARGETS_BEFORE_SETTLED
                ),
            )
            with self.assertRaises(RecoverySafeImportError):
                crashing.import_bundle_recoverable(
                    bundle,
                    request_id="IMPORT-ALL",
                )
            self.assertEqual(self.read_json(target, "a.json"), {"v": 2})
            self.assertEqual(self.read_json(target, "b.json"), {"v": 3})

            receipt = RecoverySafePortableSaveManager(target).import_bundle_recoverable(
                bundle,
                request_id="IMPORT-ALL",
            )
            self.assertEqual(receipt["state"], "SETTLED")
            state = RecoverySafePortableSaveManager(target).request_state("IMPORT-ALL")
            self.assertEqual(state["state"], "SETTLED")

    def test_same_request_different_bundle_fails_before_target_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_a = base / "source-a"
            source_b = base / "source-b"
            target = base / "target"
            bundle_a = self.make_bundle(source_a, {"state.json": {"v": "A"}})
            bundle_b = self.make_bundle(source_b, {"state.json": {"v": "B"}})
            self.make_bundle(target, {"state.json": {"v": "OLD"}})
            manager = RecoverySafePortableSaveManager(target)
            manager.import_bundle_recoverable(bundle_a, request_id="SAME-ID")
            self.assertEqual(self.read_json(target, "state.json"), {"v": "A"})
            with self.assertRaises(ImportRequestConflict):
                manager.import_bundle_recoverable(bundle_b, request_id="SAME-ID")
            self.assertEqual(self.read_json(target, "state.json"), {"v": "A"})

    def test_settled_retry_returns_same_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            bundle = self.make_bundle(source, {"state.json": {"v": 1}})
            manager = RecoverySafePortableSaveManager(target)
            first = manager.import_bundle_recoverable(bundle, request_id="REPLAY")
            second = manager.import_bundle_recoverable(bundle, request_id="REPLAY")
            self.assertEqual(first, second)
            self.assertEqual(first["state"], "SETTLED")

    def test_skip_policy_is_frozen_at_prepare_and_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            bundle = self.make_bundle(
                source,
                {"keep.json": {"v": "NEW"}, "add.json": {"v": "ADDED"}},
            )
            self.make_bundle(target, {"keep.json": {"v": "OLD"}})
            receipt = RecoverySafePortableSaveManager(target).import_bundle_recoverable(
                bundle,
                request_id="SKIP-1",
                conflict="skip",
            )
            self.assertEqual(self.read_json(target, "keep.json"), {"v": "OLD"})
            self.assertEqual(self.read_json(target, "add.json"), {"v": "ADDED"})
            self.assertEqual(receipt["skipped_files"], ["keep.json"])

    def test_fail_policy_does_not_mutate_when_target_already_exists(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            bundle = self.make_bundle(source, {"state.json": {"v": "NEW"}})
            self.make_bundle(target, {"state.json": {"v": "OLD"}})
            manager = RecoverySafePortableSaveManager(target)
            with self.assertRaises(FileExistsError):
                manager.import_bundle_recoverable(
                    bundle,
                    request_id="FAIL-1",
                    conflict="fail",
                )
            self.assertEqual(self.read_json(target, "state.json"), {"v": "OLD"})

    def test_two_manager_instances_same_request_converge_to_one_settled_plan(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            bundle = self.make_bundle(
                source,
                {"a.json": {"v": 1}, "b.json": {"v": 2}},
            )
            a = RecoverySafePortableSaveManager(target)
            b = RecoverySafePortableSaveManager(target)
            start = threading.Barrier(2)

            def run(manager):
                start.wait(timeout=5)
                return manager.import_bundle_recoverable(
                    bundle,
                    request_id="CONCURRENT",
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [f.result(timeout=15) for f in (pool.submit(run, a), pool.submit(run, b))]
            self.assertEqual(results[0], results[1])
            self.assertEqual(self.read_json(target, "a.json"), {"v": 1})
            self.assertEqual(self.read_json(target, "b.json"), {"v": 2})

    def test_control_and_stage_files_are_not_exported_by_legacy_bundle_scanner(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            bundle = self.make_bundle(source, {"state.json": {"v": 1}})
            RecoverySafePortableSaveManager(target).import_bundle_recoverable(
                bundle,
                request_id="EXPORT-CHECK",
            )
            rebuilt = PortableSaveManager(target).build_bundle(label="after-import")
            exported_paths = {item["path"] for item in rebuilt["files"]}
            self.assertEqual(exported_paths, {"state.json"})


if __name__ == "__main__":
    unittest.main()
