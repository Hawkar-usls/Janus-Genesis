from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

# Reuse the non-ledger adversarial gates from v18.7.28. They are imported
# deliberately so unittest includes them in this descendant module as well.
from tests.test_genesis_v18_7_28_client_ledger_attestation import (
    LifecycleSerializationTests,
    LineageAttestationTests,
    PortableLockTests,
    ProviderEvidenceTests,
    RecordingRuntime,
)
from genesis_v18_7_29_portable_resource_lifetime import (
    ClientRequestConflict,
    PersistentClientRequestLedger,
    PortableControlledClientExecutor,
)


class PortableLedgerResourceLifetimeTests(unittest.TestCase):
    def test_temp_directory_can_delete_database_immediately_after_ledger_use(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        ledger = PersistentClientRequestLedger(root / "client-requests.sqlite3")
        ledger.bind(
            client_id="windows-regression",
            request_id="REQ-1",
            actor_id="mira",
            action="создать сад",
        )
        self.assertIsNotNone(
            ledger.get(client_id="windows-regression", request_id="REQ-1")
        )
        # On Windows this raises PermissionError if a sqlite connection leaked.
        temp.cleanup()
        self.assertFalse(root.exists())

    def test_same_request_same_action_reuses_identity_and_conflict_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = PersistentClientRequestLedger(Path(td) / "client-requests.sqlite3")
            a = ledger.bind(
                client_id="cli-main",
                request_id="REQ-77",
                actor_id="mira",
                action="создать сад",
            )
            b = ledger.bind(
                client_id="cli-main",
                request_id="REQ-77",
                actor_id="mira",
                action="создать сад",
            )
            self.assertEqual(a.runtime_request_id, b.runtime_request_id)
            with self.assertRaises(ClientRequestConflict):
                ledger.bind(
                    client_id="cli-main",
                    request_id="REQ-77",
                    actor_id="mira",
                    action="создать мост",
                )

    def test_failed_outer_execution_preserves_request_identity_for_retry(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = PersistentClientRequestLedger(Path(td) / "client-requests.sqlite3")
            runtime = RecordingRuntime(fail_first=True)
            executor = PortableControlledClientExecutor(ledger=ledger, runtime=runtime)
            with self.assertRaises(RuntimeError):
                executor.execute(
                    client_id="cli-main",
                    request_id="REQ-88",
                    actor_id="mira",
                    action="создать музыку",
                )
            bound = ledger.get(client_id="cli-main", request_id="REQ-88")
            self.assertEqual(bound.state, "BOUND")

            executor.execute(
                client_id="cli-main",
                request_id="REQ-88",
                actor_id="mira",
                action="создать музыку",
            )
            self.assertEqual(runtime.calls[0][2], runtime.calls[1][2])
            self.assertEqual(
                ledger.get(client_id="cli-main", request_id="REQ-88").state,
                "SETTLED",
            )


if __name__ == "__main__":
    unittest.main()
