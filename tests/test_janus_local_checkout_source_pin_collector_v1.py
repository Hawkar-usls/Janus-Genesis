from __future__ import annotations

import ast
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import janus_local_checkout_source_pin_collector as collector
from tools.janus_source_pin_contract import require_exact_git_replay


def synthetic_constellation() -> dict:
    return {
        "schema": "janus.genesis.git_habitat.repository_constellation.v1",
        "repository_count": 44,
        "public_repository_count": 41,
        "private_repository_count": 3,
        "public_repositories": [
            {
                "id": str(1000 + index),
                "name": f"Hawkar-usls/public-fixture-{index}",
                "default_branch": "main",
            }
            for index in range(41)
        ],
        "private_repository_slots": [
            {
                "repository_id": str(2000 + index),
                "visibility": "private",
                "resolution": "AUTHENTICATED_RESOLUTION_REQUIRED",
            }
            for index in range(3)
        ],
    }


def source_ids() -> list[str]:
    value = synthetic_constellation()
    ids = [row["id"] for row in value["public_repositories"]]
    ids.extend(row["repository_id"] for row in value["private_repository_slots"])
    return sorted(ids, key=int)


def init_repo(path: Path, text: str) -> str:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "collector-test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "JANUS Collector Test"],
        check=True,
    )
    (path / "tracked.txt").write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-m", "fixture"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"]
    ).decode("ascii").strip()


class LocalCheckoutSourcePinCollectorTests(unittest.TestCase):
    def test_real_44_repo_collection_produces_typed_exact_pinset_without_names_or_paths(self) -> None:
        constellation = synthetic_constellation()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            sources.mkdir()
            expected: dict[str, str] = {}
            for source_id in source_ids():
                expected[source_id] = init_repo(
                    sources / source_id,
                    f"committed-{source_id}\n",
                )

            pinset = collector.collect_exact_git_pinset(
                constellation,
                sources,
                pinset_id="LOCAL-SENSITIVE-44-SOURCE-FIXTURE",
            )
            normalized = require_exact_git_replay(pinset)
            self.assertEqual(len(normalized["sources"]), 44)
            self.assertEqual(
                {row["source_id"]: row["pin"]["value"] for row in normalized["sources"]},
                expected,
            )

            serialized = json.dumps(normalized, sort_keys=True)
            self.assertNotIn(str(sources), serialized)
            self.assertNotIn("Hawkar-usls/public-fixture-", serialized)
            self.assertNotIn("checkout", serialized.lower())
            self.assertEqual(
                sum(row["visibility"] == "private" for row in normalized["sources"]),
                3,
            )

    def test_missing_checkout_fails_before_sensitive_output_is_written(self) -> None:
        constellation = synthetic_constellation()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            sources.mkdir()
            for source_id in source_ids():
                (sources / source_id).mkdir()
            missing = source_ids()[-1]
            (sources / missing).rmdir()
            output = root / "pinset.json"

            def fake_checkout(sources_root: Path, source_id: str) -> Path:
                checkout = sources_root / source_id
                if not checkout.is_dir():
                    raise collector.LocalCheckoutPinCollectorError(
                        f"SOURCE_CHECKOUT_MUST_BE_REAL_DIRECTORY:{source_id}"
                    )
                return checkout

            with mock.patch.object(
                collector,
                "_checkout_for",
                side_effect=fake_checkout,
            ), mock.patch.object(
                collector,
                "_exact_head_commit",
                return_value="a" * 40,
            ):
                with self.assertRaisesRegex(
                    collector.LocalCheckoutPinCollectorError,
                    f"SOURCE_CHECKOUT_MUST_BE_REAL_DIRECTORY:{missing}",
                ):
                    collector.collect_and_write(
                        constellation,
                        sources,
                        output,
                        pinset_id="MISSING-CHECKOUT",
                    )
            self.assertFalse(output.exists())

    def test_head_change_between_complete_passes_fails_closed(self) -> None:
        constellation = synthetic_constellation()
        ids = source_ids()
        target = ids[len(ids) // 2]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            sources.mkdir()
            for source_id in ids:
                (sources / source_id).mkdir()

            calls: dict[str, int] = {}

            def fake_head(_checkout: Path, source_id: str) -> str:
                calls[source_id] = calls.get(source_id, 0) + 1
                if source_id == target and calls[source_id] == 2:
                    return "b" * 40
                return "a" * 40

            with mock.patch.object(
                collector,
                "_checkout_for",
                side_effect=lambda sources_root, source_id: sources_root / source_id,
            ), mock.patch.object(
                collector,
                "_exact_head_commit",
                side_effect=fake_head,
            ):
                with self.assertRaisesRegex(
                    collector.LocalCheckoutPinCollectorError,
                    f"SOURCE_HEAD_CHANGED_DURING_COLLECTION:{target}",
                ):
                    collector.collect_exact_git_pinset(
                        constellation,
                        sources,
                        pinset_id="DRIFT-FIXTURE",
                    )

    def test_sensitive_pinset_write_is_0600_and_never_overwrites(self) -> None:
        constellation = synthetic_constellation()
        ids = source_ids()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            sources.mkdir()
            for source_id in ids:
                (sources / source_id).mkdir()
            output = root / "sensitive" / "exact-pinset.json"
            output.parent.mkdir()

            with mock.patch.object(
                collector,
                "_checkout_for",
                side_effect=lambda sources_root, source_id: sources_root / source_id,
            ), mock.patch.object(
                collector,
                "_exact_head_commit",
                return_value="c" * 40,
            ):
                result = collector.collect_and_write(
                    constellation,
                    sources,
                    output,
                    pinset_id="LOCAL-SENSITIVE-PINSET",
                )
                self.assertEqual(result["source_count"], 44)
                self.assertEqual(result["private_source_count"], 3)
                self.assertFalse(result["network_acquisition_performed"])
                self.assertFalse(result["source_writeback_performed"])
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

                with self.assertRaisesRegex(
                    collector.LocalCheckoutPinCollectorError,
                    "SENSITIVE_PINSET_WRITE_FAILED",
                ):
                    collector.collect_and_write(
                        constellation,
                        sources,
                        output,
                        pinset_id="LOCAL-SENSITIVE-PINSET",
                    )

    def test_symlinked_sources_root_is_rejected(self) -> None:
        constellation = synthetic_constellation()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real-sources"
            real.mkdir()
            linked = root / "linked-sources"
            try:
                linked.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(
                collector.LocalCheckoutPinCollectorError,
                "SOURCES_ROOT_MUST_BE_REAL_DIRECTORY",
            ):
                collector.collect_exact_git_pinset(
                    constellation,
                    linked,
                    pinset_id="SYMLINK-ROOT",
                )

    def test_direct_process_surface_is_static_local_git_object_queries_only(self) -> None:
        path = Path(collector.__file__ or "")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        direct_process_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        ]
        self.assertEqual(
            {node.func.attr for node in direct_process_calls},
            {"check_output"},
        )

        git_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_git"
        ]
        subcommands: set[str] = set()
        for node in git_calls:
            self.assertGreaterEqual(len(node.args), 2)
            self.assertIsInstance(node.args[1], ast.Constant)
            value = node.args[1].value
            self.assertIsInstance(value, str)
            subcommands.add(value)
        self.assertEqual(subcommands, {"rev-parse", "cat-file"})
        self.assertFalse(
            subcommands
            & {
                "clone",
                "fetch",
                "push",
                "pull",
                "remote",
                "ls-remote",
                "send-pack",
                "receive-pack",
            }
        )


if __name__ == "__main__":
    unittest.main()
