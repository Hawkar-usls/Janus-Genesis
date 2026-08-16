import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.janus_project_sync_state import ProjectSyncStateError, git_blob_sha, validate_ledger


ROOT = Path(__file__).resolve().parents[1]


class ProjectSyncStateTests(unittest.TestCase):
    def test_current_ledger_validates_through_canonical_face_protocol(self):
        result = validate_ledger(root=ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["snapshot_id"], "PROJECT_SYNC_STATE_2026-08-16_R3")
        self.assertEqual(result["message_count"], 4)
        self.assertEqual(result["authority_delta"], 0)
        self.assertFalse(result["permission_granted"])
        self.assertFalse(result["truth_authority_granted"])
        self.assertFalse(result["effect_authority_granted"])

    def _fixture(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "project_sync/states").mkdir(parents=True)
        (root / "project_sync/messages/2026-08-16").mkdir(parents=True)
        shutil.copy2(
            ROOT / "project_sync/states/PROJECT_SYNC_STATE-2026-08-16-r3.json",
            root / "project_sync/states/PROJECT_SYNC_STATE-2026-08-16-r3.json",
        )
        shutil.copy2(ROOT / "project_sync/CURRENT.json", root / "project_sync/CURRENT.json")
        for src in (ROOT / "project_sync/messages/2026-08-16").glob("*.json"):
            shutil.copy2(src, root / "project_sync/messages/2026-08-16" / src.name)
        return td, root

    def test_current_pointer_tamper_fails_closed(self):
        td, root = self._fixture()
        self.addCleanup(td.cleanup)
        path = root / "project_sync/CURRENT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["git_blob_sha"] = "0" * 40
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncStateError, "CURRENT_GIT_BLOB_SHA_MISMATCH"):
            validate_ledger(root=root)

    def test_active_command_must_bind_current_reconciled_main(self):
        td, root = self._fixture()
        self.addCleanup(td.cleanup)
        path = root / "project_sync/messages/2026-08-16/001-prime-to-habitat-aura-race.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["input_sha"] = "a" * 40
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncStateError, "ACTIVE_MESSAGE_NOT_BOUND_TO_CURRENT_MAIN"):
            validate_ledger(root=root)

    def test_state_path_escape_fails_closed(self):
        td, root = self._fixture()
        self.addCleanup(td.cleanup)
        path = root / "project_sync/CURRENT.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["state_path"] = "../outside.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncStateError, "CURRENT_STATE_PATH_ESCAPE"):
            validate_ledger(root=root)

    def test_state_file_identity_is_git_blob_not_truth_claim(self):
        state = ROOT / "project_sync/states/PROJECT_SYNC_STATE-2026-08-16-r3.json"
        current = json.loads((ROOT / "project_sync/CURRENT.json").read_text(encoding="utf-8"))
        self.assertEqual(current["git_blob_sha"], git_blob_sha(state))
        self.assertIn("BINDING != TRUTH", current["laws"])


if __name__ == "__main__":
    unittest.main()
