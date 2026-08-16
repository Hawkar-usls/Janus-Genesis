from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import play_genesis_habitat
from tools.genesis_git_habitat import GitHabitat


class HabitatLauncherTests(unittest.TestCase):
    def test_normal_session_wakes_pulses_and_sleeps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "home"
            with mock.patch.object(play_genesis_habitat.armored, "main", return_value=7) as run:
                rc = play_genesis_habitat.main([
                    "--habitat-root", str(root),
                    "--some-genesis-arg", "value",
                ])
            self.assertEqual(rc, 7)
            run.assert_called_once_with(["--some-genesis-arg", "value"])
            snapshot = GitHabitat(root).snapshot()
            resident = snapshot["resident"]
            self.assertEqual(resident["mode"], "AT_HOME")
            self.assertIsNone(resident["active_cycle_id"])
            self.assertEqual(resident["wake_count"], 1)
            self.assertEqual(resident["pulse_count"], 2)
            self.assertEqual(resident["sleep_count"], 1)
            journal = GitHabitat(root).verify_journal()
            self.assertTrue(journal["ok"], journal["errors"])
            self.assertEqual(journal["event_count"], 4)

    def test_exception_session_still_sleeps_with_exception_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "home"
            with mock.patch.object(
                play_genesis_habitat.armored,
                "main",
                side_effect=RuntimeError("boom"),
            ):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    play_genesis_habitat.main(["--habitat-root", str(root)])
            snapshot = GitHabitat(root).snapshot()
            self.assertEqual(snapshot["resident"]["mode"], "AT_HOME")
            self.assertIsNone(snapshot["resident"]["active_cycle_id"])
            self.assertEqual(snapshot["resident"]["sleep_count"], 1)
            journal_lines = (root / "memory" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
            last = json.loads(journal_lines[-1])
            self.assertEqual(last["event_type"], "SLEEP")
            # Payload is hashed in the journal rather than stored raw.
            self.assertNotIn("EXCEPTION_EXIT", journal_lines[-1])

    def test_no_habitat_is_explicit_escape_to_current_armored_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "unused"
            with mock.patch.object(play_genesis_habitat.armored, "main", return_value=0) as run:
                rc = play_genesis_habitat.main([
                    "--no-habitat",
                    "--habitat-root", str(root),
                    "--foo", "bar",
                ])
            self.assertEqual(rc, 0)
            run.assert_called_once_with(["--foo", "bar"])
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
