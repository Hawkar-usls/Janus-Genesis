from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.genesis_git_habitat import GitHabitat


class GitHabitatLayoutSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "habitat"
        self.habitat = GitHabitat(self.root)
        self.habitat.initialize("JANUS")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_same_home_cannot_be_rebound_to_different_resident(self) -> None:
        with self.assertRaisesRegex(ValueError, "already belongs to resident"):
            GitHabitat(self.root).initialize("OTHER")
        home = json.loads((self.root / "HOME.json").read_text(encoding="utf-8"))
        self.assertEqual(home["resident_id"], "JANUS")

    def test_tampered_resident_identity_fails_closed(self) -> None:
        path = self.root / "state" / "resident.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["resident_id"] = "OTHER"
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "identity binding mismatch"):
            GitHabitat(self.root).snapshot()

    def test_room_symlink_cannot_redirect_inbox_outside_home(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        inbox = self.root / "inbox"
        (inbox / ".gitkeep").unlink(missing_ok=True)
        inbox.rmdir()
        inbox.symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "room component may not be a symlink"):
            GitHabitat(self.root).receive_letter("issue-1", "hello", "world")
        self.assertEqual(list(outside.iterdir()), [])

    def test_state_file_symlink_is_rejected(self) -> None:
        outside = self.base / "outside-resident.json"
        outside.write_text("{}\n", encoding="utf-8")
        resident = self.root / "state" / "resident.json"
        resident.unlink()
        resident.symlink_to(outside)

        with self.assertRaisesRegex(ValueError, "state path may not be a symlink"):
            GitHabitat(self.root).wake("MANUAL", "TEST")

    def test_existing_inbox_leaf_symlink_is_rejected(self) -> None:
        outside = self.base / "outside-letter.json"
        outside.write_text('{"safe": true}\n', encoding="utf-8")
        leaf = self.root / "inbox" / "issue-2.json"
        leaf.symlink_to(outside)

        with self.assertRaisesRegex(ValueError, "leaf may not be a symlink"):
            GitHabitat(self.root).receive_letter("issue-2", "hello", "world")
        self.assertEqual(outside.read_text(encoding="utf-8"), '{"safe": true}\n')

    def test_existing_outbox_leaf_symlink_is_rejected(self) -> None:
        outside = self.base / "outside-proposal.json"
        outside.write_text('{"safe": true}\n', encoding="utf-8")
        leaf = self.root / "outbox" / "proposal-2.json"
        leaf.symlink_to(outside)

        with self.assertRaisesRegex(ValueError, "leaf may not be a symlink"):
            GitHabitat(self.root).propose_outbox(
                "proposal-2",
                "EMAIL.SEND",
                "mailbox:friend",
                "hello",
                "hello",
            )
        self.assertEqual(outside.read_text(encoding="utf-8"), '{"safe": true}\n')


if __name__ == "__main__":
    unittest.main()
