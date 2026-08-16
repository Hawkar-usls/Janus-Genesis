from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import janus_local_checkout_source_pin_collector as collector


def init_repo(path: Path, text: str) -> str:
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "collector-env@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "JANUS Collector Env Test"],
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


class LocalCheckoutCollectorGitEnvironmentTests(unittest.TestCase):
    def test_ambient_git_dir_cannot_redirect_checkout_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "1001"
            attacker = root / "attacker"
            target_sha = init_repo(target, "target\n")
            attacker_sha = init_repo(attacker, "attacker\n")
            self.assertNotEqual(target_sha, attacker_sha)

            with mock.patch.dict(
                os.environ,
                {
                    "GIT_DIR": str(attacker / ".git"),
                    "GIT_WORK_TREE": str(attacker),
                    "GIT_COMMON_DIR": str(attacker / ".git"),
                },
                clear=False,
            ):
                observed = collector._exact_head_commit(target, "1001")

            self.assertEqual(observed, target_sha)
            self.assertNotEqual(observed, attacker_sha)

    def test_sanitized_environment_removes_git_context_redirectors(self) -> None:
        poisoned = {
            key: f"/tmp/poison-{index}"
            for index, key in enumerate(sorted(collector.GIT_CONTEXT_ENV_KEYS))
        }
        with mock.patch.dict(os.environ, poisoned, clear=False):
            env = collector._sanitized_git_env()

        for key in collector.GIT_CONTEXT_ENV_KEYS:
            self.assertNotIn(key, env)
        self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")

    def test_plain_child_directory_cannot_inherit_parent_repository_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            init_repo(sources, "parent-repository\n")
            child = sources / "1001"
            child.mkdir()

            with self.assertRaisesRegex(
                collector.LocalCheckoutPinCollectorError,
                "SOURCE_CHECKOUT_NOT_GIT_ROOT:1001",
            ):
                collector._checkout_for(sources, "1001")

    def test_unicode_sources_root_is_supported_without_path_case_folding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "джерела"
            sources.mkdir()
            checkout = sources / "1001"
            expected = init_repo(checkout, "unicode-root\n")

            self.assertEqual(collector._checkout_for(sources, "1001"), checkout)
            self.assertEqual(collector._exact_head_commit(checkout, "1001"), expected)


if __name__ == "__main__":
    unittest.main()
