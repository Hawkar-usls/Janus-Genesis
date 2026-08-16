from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.janus_nexus_variant_lineage import (
    LineageError,
    append_variant,
    variant_id_for,
    verify_ledger,
)


class NexusVariantLineageV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "LINEAGE.jsonl"

    def payload(
        self,
        *,
        parents: list[str] | None = None,
        mutation: str = "baseline",
        failed: bool = False,
    ) -> dict[str, object]:
        return {
            "nexus_identity_digest": "1" * 64,
            "parent_variant_ids": list(parents or []),
            "source_repository_shas": [
                {"repository_id": "FACE_CORE", "sha": "a" * 40},
                {"repository_id": "FACE_MEMORY", "sha": "b" * 40},
            ],
            "inherited_traits": ["preserve-source-history"],
            "mutations": [{"kind": "DECLARATIVE", "summary": mutation}],
            "test_suite": {"id": "nexus-lineage-fixture-v1", "digest": "2" * 64},
            "metrics": {"score": 0.5},
            "gate_results": {"fixture_gate": not failed},
            "failure_reason_if_any": "fixture failure retained" if failed else None,
            "receipt_digest": "3" * 64,
            "selection_scope": {
                "objective": "test lineage integrity",
                "constraints": ["no source writeback"],
                "dataset": "fixture-v1",
            },
        }

    def test_root_child_graph_derives_descendants_without_mutating_parent_record(self) -> None:
        root_payload = self.payload(mutation="root")
        root = append_variant(self.ledger, root_payload)
        first_line_before = self.ledger.read_text(encoding="utf-8").splitlines()[0]

        child_payload = self.payload(parents=[root["variant_id"]], mutation="child")
        child = append_variant(self.ledger, child_payload)
        first_line_after = self.ledger.read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(first_line_before, first_line_after)
        state = verify_ledger(self.ledger)
        self.assertEqual(state["record_count"], 2)
        self.assertEqual(state["variants"][root["variant_id"]]["generation"], 0)
        self.assertEqual(state["variants"][child["variant_id"]]["generation"], 1)
        self.assertEqual(
            state["variants"][root["variant_id"]]["descendants"],
            [child["variant_id"]],
        )
        self.assertEqual(state["variants"][child["variant_id"]]["descendants"], [])

    def test_unknown_parent_fails_before_append(self) -> None:
        with self.assertRaisesRegex(LineageError, "unknown parent_variant_ids"):
            append_variant(self.ledger, self.payload(parents=["9" * 64]))
        self.assertFalse(self.ledger.exists())

    def test_duplicate_variant_is_rejected(self) -> None:
        payload = self.payload(mutation="same")
        first = append_variant(self.ledger, payload)
        self.assertEqual(first["variant_id"], variant_id_for(payload))
        with self.assertRaisesRegex(LineageError, "variant already exists"):
            append_variant(self.ledger, payload)
        self.assertEqual(verify_ledger(self.ledger)["record_count"], 1)

    def test_middle_record_tamper_breaks_hash_chain_or_digest(self) -> None:
        root = append_variant(self.ledger, self.payload(mutation="immutable-root"))
        append_variant(
            self.ledger,
            self.payload(parents=[root["variant_id"]], mutation="immutable-child"),
        )
        text = self.ledger.read_text(encoding="utf-8")
        self.ledger.write_text(text.replace("immutable-root", "tampered-root"), encoding="utf-8")
        with self.assertRaises(LineageError):
            verify_ledger(self.ledger)

    def test_external_head_receipt_detects_valid_prefix_truncation(self) -> None:
        root = append_variant(self.ledger, self.payload(mutation="root"))
        append_variant(
            self.ledger,
            self.payload(parents=[root["variant_id"]], mutation="child"),
        )
        full = verify_ledger(self.ledger)
        first_line = self.ledger.read_text(encoding="utf-8").splitlines()[0]

        # A valid prefix is internally self-consistent.  The external receipt is
        # what proves that a later retained head has disappeared.
        self.ledger.write_text(first_line + "\n", encoding="utf-8")
        prefix = verify_ledger(self.ledger)
        self.assertEqual(prefix["record_count"], 1)
        with self.assertRaisesRegex(LineageError, "lineage digest mismatch"):
            verify_ledger(
                self.ledger,
                expected_lineage_digest=full["lineage_digest"],
            )

    def test_failed_variant_is_preserved_and_queryable(self) -> None:
        result = append_variant(self.ledger, self.payload(mutation="bad-idea", failed=True))
        state = verify_ledger(self.ledger)
        retained = state["variants"][result["variant_id"]]
        self.assertEqual(retained["failure_reason_if_any"], "fixture failure retained")
        self.assertFalse(retained["gate_results"]["fixture_gate"])

    def test_existing_append_lock_fails_closed_instead_of_racing(self) -> None:
        lock = self.ledger.with_name(self.ledger.name + ".append.lock")
        lock.write_text("other-worker\n", encoding="utf-8")
        with self.assertRaisesRegex(LineageError, "append lock already exists"):
            append_variant(self.ledger, self.payload())
        self.assertFalse(self.ledger.exists())
        self.assertTrue(lock.exists())

    def test_source_sha_and_repository_id_are_strict(self) -> None:
        bad_sha = self.payload()
        bad_sha["source_repository_shas"][0]["sha"] = "main"  # type: ignore[index]
        with self.assertRaisesRegex(LineageError, "exact lowercase 40-hex Git SHA"):
            append_variant(self.ledger, bad_sha)

        bad_id = self.payload()
        bad_id["source_repository_shas"][0]["repository_id"] = "../secret"  # type: ignore[index]
        with self.assertRaisesRegex(LineageError, "repository_id is invalid"):
            append_variant(self.ledger, bad_id)

    def test_unknown_authority_shaped_top_level_fields_are_rejected(self) -> None:
        payload = self.payload()
        payload["permission_granted"] = True
        with self.assertRaisesRegex(LineageError, "payload keys mismatch"):
            append_variant(self.ledger, payload)

    def test_partial_last_record_is_rejected(self) -> None:
        append_variant(self.ledger, self.payload())
        with self.ledger.open("ab") as handle:
            handle.write(b'{"schema":"partial"}')
        with self.assertRaisesRegex(LineageError, "partial/non-newline"):
            verify_ledger(self.ledger)


if __name__ == "__main__":
    unittest.main()
