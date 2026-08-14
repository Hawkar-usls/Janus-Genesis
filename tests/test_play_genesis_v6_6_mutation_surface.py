from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import play_genesis
from genesis_v18_7_portable import PortableSaveManager


class ControlledMutationSurfaceCLITests(unittest.TestCase):
    @staticmethod
    def run_main(argv):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = play_genesis.main(argv)
        text = stream.getvalue()
        return code, json.loads(text) if text.strip() else None

    def test_name_uses_typed_request_and_same_request_replays(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            argv = [
                "--data-dir", str(root),
                "--player", "mira",
                "--name", "Mira",
                "--name-request-id", "NAME-CLI-1",
                "--status",
            ]
            code1, first = self.run_main(argv)
            code2, second = self.run_main(argv)
            self.assertEqual(code1, 0)
            self.assertEqual(code2, 0)
            self.assertEqual(first["display_name"], "Mira")
            self.assertEqual(second["display_name"], "Mira")
            self.assertEqual(first["_janus_name_control"]["request_id"], "NAME-CLI-1")
            self.assertEqual(
                first["_janus_name_control"]["receipt"],
                second["_janus_name_control"]["receipt"],
            )

            state_code, state = self.run_main(
                [
                    "--data-dir", str(root),
                    "--mutation-request-state", "NAME-CLI-1",
                ]
            )
            self.assertEqual(state_code, 0)
            self.assertEqual(state["state"], "SETTLED")
            self.assertEqual(state["mutation_kind"], "SET_DISPLAY_NAME")

    def test_same_name_request_changed_name_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = ["--data-dir", str(root), "--player", "mira", "--status"]
            code1, _ = self.run_main(
                base
                + [
                    "--name", "Mira",
                    "--name-request-id", "NAME-CONFLICT",
                ]
            )
            code2, blocked = self.run_main(
                base
                + [
                    "--name", "Other",
                    "--name-request-id", "NAME-CONFLICT",
                ]
            )
            self.assertEqual(code1, 0)
            self.assertEqual(code2, 2)
            self.assertEqual(blocked["status"], "JANUS_CONTROL_BLOCKED")
            self.assertEqual(blocked["error_type"], "TypedMutationRequestConflict")

    def test_force_exit_same_request_replays_typed_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            argv = [
                "--data-dir", str(root),
                "--player", "mira",
                "--force-exit",
                "--force-exit-reason", "test-exit",
                "--force-exit-request-id", "EXIT-CLI-1",
            ]
            code1, first = self.run_main(argv)
            code2, second = self.run_main(argv)
            self.assertEqual(code1, 0)
            self.assertEqual(code2, 0)
            self.assertEqual(first["status"], "EXIT")
            self.assertEqual(first["narrative"], second["narrative"])
            self.assertEqual(first["_janus_control"]["request_id"], "EXIT-CLI-1")
            self.assertEqual(second["_janus_control"]["request_state"]["state"], "SETTLED")
            self.assertEqual(
                first["_janus_control"]["request_state"]["result_sha256"],
                second["_janus_control"]["request_state"]["result_sha256"],
            )

    def test_save_import_requires_explicit_logical_request_id(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            source.mkdir()
            (source / "state.json").write_text('{"value": 7}', encoding="utf-8")
            bundle_path = base / "bundle.json"
            PortableSaveManager(source).export_to(bundle_path, label="cli-v66")
            with self.assertRaises(SystemExit):
                play_genesis.main(
                    ["--data-dir", str(target), "--import-save", str(bundle_path)]
                )

    def test_save_import_request_settles_and_replays(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source = base / "source"
            target = base / "target"
            source.mkdir()
            (source / "state.json").write_text('{"value": 9}', encoding="utf-8")
            bundle_path = base / "bundle.json"
            PortableSaveManager(source).export_to(bundle_path, label="cli-v66")
            argv = [
                "--data-dir", str(target),
                "--import-save", str(bundle_path),
                "--import-request-id", "IMPORT-CLI-1",
            ]
            code1, first = self.run_main(argv)
            code2, second = self.run_main(argv)
            self.assertEqual(code1, 0)
            self.assertEqual(code2, 0)
            self.assertEqual(first, second)
            self.assertEqual(first["state"], "SETTLED")
            self.assertEqual(
                json.loads((target / "state.json").read_text(encoding="utf-8")),
                {"value": 9},
            )

            state_code, state = self.run_main(
                [
                    "--data-dir", str(target),
                    "--import-request-state", "IMPORT-CLI-1",
                ]
            )
            self.assertEqual(state_code, 0)
            self.assertEqual(state["state"], "SETTLED")

    def test_network_state_uses_durable_fail_closed_descendant_without_remote_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            code, state = self.run_main(
                [
                    "--data-dir", str(root),
                    "--network-url", "https://example.invalid",
                    "--network-state",
                ]
            )
            self.assertEqual(code, 0)
            self.assertEqual(
                state["control_schema"],
                "janus.genesis.durable_network_outbox.v1",
            )
            self.assertFalse(state["hub_idempotency_verified"])
            self.assertFalse(state["automatic_resend_after_ambiguous_send"])

    def test_malformed_existing_network_state_is_reported_not_reset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root.mkdir(parents=True, exist_ok=True)
            path = root / "network_client_v18_7.json"
            path.write_text("{bad-json", encoding="utf-8")
            code, blocked = self.run_main(
                [
                    "--data-dir", str(root),
                    "--network-url", "https://example.invalid",
                    "--network-state",
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(blocked["status"], "JANUS_NETWORK_STATE_BLOCKED")
            self.assertEqual(blocked["error_type"], "NetworkStateIntegrityError")
            self.assertEqual(path.read_text(encoding="utf-8"), "{bad-json")

    def test_name_request_id_without_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit):
                play_genesis.main(
                    [
                        "--data-dir", td,
                        "--name-request-id", "NAME-WITHOUT-NAME",
                        "--status",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
