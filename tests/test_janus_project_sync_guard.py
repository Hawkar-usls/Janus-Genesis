import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.janus_project_sync_guard import ProjectSyncError, git_blob_sha, validate


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocol/JANUS_MANY_FACES_GIT_COORDINATION-v1.0.json"
STATE = ROOT / "project_sync/PROJECT_SYNC_STATE-2026-08-16.json"
COMMANDS = ROOT / "project_sync/commands"


class ProjectSyncGuardTests(unittest.TestCase):
    def test_current_command_bus_passes_and_creates_no_authority(self):
        result = validate(PROTOCOL, STATE, COMMANDS)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["project_state_git_blob_sha"], git_blob_sha(STATE))
        self.assertEqual(result["commands"], 6)
        self.assertEqual(result["authority_growth"], 0)
        self.assertFalse(result["independent_evidence_created_by_face_count"])

    def _copy_fixture(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        protocol = root / "protocol.json"
        state = root / "state.json"
        commands = root / "commands"
        commands.mkdir(parents=True)
        shutil.copy2(PROTOCOL, protocol)
        shutil.copy2(STATE, state)
        return td, protocol, state, commands

    def test_unknown_face_fails_closed(self):
        td, protocol, state, commands = self._copy_fixture()
        self.addCleanup(td.cleanup)
        cmd = json.loads((COMMANDS / "2026-08-16/001-primus-to-sentinel-reconcile.json").read_text(encoding="utf-8"))
        cmd["from_face"] = "JANUS.IMAGINARY"
        cmd["project_sync_state_binding"] = {
            "algorithm": "git_blob_sha",
            "value": git_blob_sha(state),
            "path": state.as_posix(),
        }
        (commands / "x.json").write_text(json.dumps(cmd), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncError, "UNKNOWN_SOURCE_FACE"):
            validate(protocol, state, commands)

    def test_face_cannot_issue_unlisted_command_type(self):
        td, protocol, state, commands = self._copy_fixture()
        self.addCleanup(td.cleanup)
        cmd = json.loads((COMMANDS / "2026-08-16/003-habitat-to-hrain-structure-request.json").read_text(encoding="utf-8"))
        cmd["command_type"] = "PROOF_OBLIGATION"
        cmd["project_sync_state_binding"] = {
            "algorithm": "git_blob_sha",
            "value": git_blob_sha(state),
            "path": state.as_posix(),
        }
        (commands / "x.json").write_text(json.dumps(cmd), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncError, "SOURCE_FACE_CANNOT_ISSUE_TYPE"):
            validate(protocol, state, commands)

    def test_stale_state_binding_fails_closed(self):
        td, protocol, state, commands = self._copy_fixture()
        self.addCleanup(td.cleanup)
        cmd = json.loads((COMMANDS / "2026-08-16/006-archivist-preserve-lineage.json").read_text(encoding="utf-8"))
        cmd["project_sync_state_binding"] = {
            "algorithm": "git_blob_sha",
            "value": "0" * 40,
            "path": state.as_posix(),
        }
        (commands / "x.json").write_text(json.dumps(cmd), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncError, "BINDING_GIT_BLOB_MISMATCH"):
            validate(protocol, state, commands)

    def test_command_packet_cannot_self_assert_effect(self):
        td, protocol, state, commands = self._copy_fixture()
        self.addCleanup(td.cleanup)
        cmd = json.loads((COMMANDS / "2026-08-16/002-sentinel-to-habitat-repair-hold.json").read_text(encoding="utf-8"))
        cmd["effect_executed"] = True
        cmd["project_sync_state_binding"] = {
            "algorithm": "git_blob_sha",
            "value": git_blob_sha(state),
            "path": state.as_posix(),
        }
        (commands / "x.json").write_text(json.dumps(cmd), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncError, "MAY_NOT_SELF_ASSERT_EFFECT"):
            validate(protocol, state, commands)

    def test_global_hold_rejects_unprotected_merge_request(self):
        td, protocol, state, commands = self._copy_fixture()
        self.addCleanup(td.cleanup)
        cmd = json.loads((COMMANDS / "2026-08-16/003-habitat-to-hrain-structure-request.json").read_text(encoding="utf-8"))
        cmd["command_id"] = "TEST-MERGE"
        cmd["requested_action"] = "Merge Janus_Genesis PR #100 now."
        cmd["project_sync_state_binding"] = {
            "algorithm": "git_blob_sha",
            "value": git_blob_sha(state),
            "path": state.as_posix(),
        }
        (commands / "x.json").write_text(json.dumps(cmd), encoding="utf-8")
        with self.assertRaisesRegex(ProjectSyncError, "GLOBAL_HOLD_FORBIDS_REQUESTED_EFFECT"):
            validate(protocol, state, commands)


if __name__ == "__main__":
    unittest.main()
