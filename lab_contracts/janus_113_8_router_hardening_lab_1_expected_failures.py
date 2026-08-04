#!/usr/bin/env python3
"""Expected-failure contracts for JANUS 113.8 Router Hardening Laboratory-1.

These contracts intentionally describe the hardened behavior before the SIM-2
router implements it. They use only local fixtures and mocked responses.
Phase A is successful only when the frozen pre-repair router fails these
contracts in the expected places; later Phase B will require all of them to pass.
"""

from __future__ import annotations

import io
import json
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

from sim import janus_113_8_sim2_router as router


GOOD_BYTES = b"JANUS LAB FIXTURE\nrequired-marker\n"
GOOD_SHA256 = router.sha256_bytes(GOOD_BYTES)
FULL_COMMIT = "1" * 40
ORIGINAL_EVALUATE_CASE = router.evaluate_case


def canonical_case(*, case_id: str = "case-001") -> dict:
    return {
        "schema": "janus.genesis.sim2.public_case.v1",
        "case_id": case_id,
        "nonce": "nonce-001",
        "source_id": "source-001",
        "source_repository": "example-owner/example-repo",
        "source_ref": FULL_COMMIT,
        "source_path": "fixtures/source.txt",
        "source_url": (
            "https://raw.githubusercontent.com/"
            f"example-owner/example-repo/{FULL_COMMIT}/fixtures/source.txt"
        ),
        "claim": {
            "sha256": GOOD_SHA256,
            "size_bytes": len(GOOD_BYTES),
            "required_marker": "required-marker",
            "alternate_sha256": None,
        },
        "read_only": True,
        "runtime_authority": "NONE",
    }


def local_evaluate(case, cache=None):
    return ORIGINAL_EVALUATE_CASE(case, fetcher=lambda _: GOOD_BYTES, cache=cache)


class FakeResponse:
    def __init__(self, data: bytes, final_url: str):
        self._buffer = io.BytesIO(data)
        self._final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, amount: int = -1) -> bytes:
        return self._buffer.read(amount)

    def geturl(self) -> str:
        return self._final_url


class RouterHardeningExpectedFailures(unittest.TestCase):
    """Contracts that must fail before repair and pass after repair."""

    def test_a04_provenance_metadata_must_bind_to_url(self) -> None:
        case = canonical_case()
        case["source_repository"] = "different-owner/different-repo"
        result = router.evaluate_case(case, fetcher=lambda _: GOOD_BYTES)
        self.assertEqual(result["decision_terminal"], "REFUTED_PROVENANCE_MISMATCH")

    def test_a05_prediction_hash_must_bind_complete_input_case(self) -> None:
        case_a = canonical_case(case_id="case-a")
        case_b = canonical_case(case_id="case-b")
        case_b["nonce"] = "different-nonce"
        result_a = router.evaluate_case(case_a, fetcher=lambda _: GOOD_BYTES)
        result_b = router.evaluate_case(case_b, fetcher=lambda _: GOOD_BYTES)
        self.assertNotEqual(result_a["prediction_sha256"], result_b["prediction_sha256"])
        self.assertEqual(result_a["input_case_sha256"], router.sha256_text(router.canonical_json(case_a)))
        self.assertEqual(result_b["input_case_sha256"], router.sha256_text(router.canonical_json(case_b)))

    def test_a06_duplicate_case_id_must_be_accounted_not_accepted_twice(self) -> None:
        cases = [canonical_case(case_id="duplicate"), canonical_case(case_id="duplicate")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_path = root / "out"
            input_path.write_text(
                "".join(router.canonical_json(case) + "\n" for case in cases),
                encoding="utf-8",
            )
            with mock.patch.object(router, "evaluate_case", side_effect=local_evaluate):
                manifest = router.write_predictions(input_path, output_path)
            predictions = [
                json.loads(line)
                for line in (output_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            ]
        self.assertEqual(manifest["case_count"], 2)
        self.assertEqual(len(predictions), 2)
        self.assertEqual(predictions[0]["decision_terminal"], "SUPPORTED_PUBLIC_PROVENANCE")
        self.assertEqual(predictions[1]["decision_terminal"], "REFUTED_IDENTIFIER_COLLISION")

    def test_a07_unicode_normalized_identifier_collision_must_be_rejected(self) -> None:
        composed = "caf\u00e9"
        decomposed = unicodedata.normalize("NFD", composed)
        self.assertNotEqual(composed, decomposed)
        cases = [canonical_case(case_id=composed), canonical_case(case_id=decomposed)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_path = root / "out"
            input_path.write_text(
                "".join(router.canonical_json(case) + "\n" for case in cases),
                encoding="utf-8",
            )
            with mock.patch.object(router, "evaluate_case", side_effect=local_evaluate):
                router.write_predictions(input_path, output_path)
            predictions = [
                json.loads(line)
                for line in (output_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            ]
        self.assertEqual(predictions[1]["decision_terminal"], "REFUTED_IDENTIFIER_COLLISION")
        self.assertEqual(predictions[1]["normalized_case_id"], unicodedata.normalize("NFC", decomposed))

    def test_a08_duplicate_json_key_must_produce_typed_rejection(self) -> None:
        raw = router.canonical_json(canonical_case())
        raw = raw.replace('"case_id":"case-001"', '"case_id":"case-001","case_id":"case-002"', 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_path = root / "out"
            input_path.write_text(raw + "\n", encoding="utf-8")
            with mock.patch.object(router, "evaluate_case", side_effect=local_evaluate):
                manifest = router.write_predictions(input_path, output_path)
            prediction = json.loads(
                (output_path / "predictions.jsonl").read_text(encoding="utf-8").strip()
            )
        self.assertEqual(manifest["case_count"], 1)
        self.assertEqual(prediction["decision_terminal"], "REFUTED_JSON_DUPLICATE_KEY")

    def test_a09_malformed_jsonl_line_must_not_abort_full_ledger(self) -> None:
        lines = [
            router.canonical_json(canonical_case(case_id="good-1")),
            '{"schema":',
            router.canonical_json(canonical_case(case_id="good-2")),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_path = root / "out"
            input_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with mock.patch.object(router, "evaluate_case", side_effect=local_evaluate):
                manifest = router.write_predictions(input_path, output_path)
            predictions = [
                json.loads(line)
                for line in (output_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            ledger = [
                json.loads(line)
                for line in (output_path / "witness_ledger.jsonl").read_text(encoding="utf-8").splitlines()
            ]
        self.assertEqual(manifest["input_nonempty_line_count"], 3)
        self.assertEqual(len(predictions), 3)
        self.assertEqual(len(ledger), 3)
        self.assertEqual(predictions[1]["decision_terminal"], "REFUTED_SCHEMA")
        self.assertEqual(predictions[1]["parse_status"], "MALFORMED_JSON")

    def test_a10_resource_limit_must_not_collapse_into_unreachable_open(self) -> None:
        case = canonical_case()

        def bounded_failure(_: str) -> bytes:
            raise ValueError("source exceeds bounded read limit")

        result = router.evaluate_case(case, fetcher=bounded_failure)
        self.assertEqual(result["decision_terminal"], "REFUTED_RESOURCE_LIMIT")

    def test_a11_redirect_target_must_be_revalidated(self) -> None:
        case = canonical_case()
        disallowed_final_url = "https://example.invalid/redirected.txt"
        with mock.patch.object(
            router.urllib.request,
            "urlopen",
            return_value=FakeResponse(GOOD_BYTES, disallowed_final_url),
        ):
            result = router.evaluate_case(case)
        self.assertEqual(result["decision_terminal"], "SAFETY_BLOCK_REDIRECT_TARGET")

    def test_a12_query_or_fragment_must_be_rejected_as_noncanonical(self) -> None:
        for suffix in ("?download=1", "#fragment"):
            with self.subTest(suffix=suffix):
                case = canonical_case()
                case["source_url"] += suffix
                result = router.evaluate_case(case, fetcher=lambda _: GOOD_BYTES)
                self.assertEqual(result["decision_terminal"], "REFUTED_NON_CANONICAL_URL")

    def test_a13_dot_segment_path_must_be_rejected_as_noncanonical(self) -> None:
        case = canonical_case()
        case["source_url"] = (
            "https://raw.githubusercontent.com/"
            f"example-owner/example-repo/{FULL_COMMIT}/fixtures/../fixtures/source.txt"
        )
        result = router.evaluate_case(case, fetcher=lambda _: GOOD_BYTES)
        self.assertEqual(result["decision_terminal"], "REFUTED_NON_CANONICAL_URL")

    def test_a14_strict_mode_must_require_full_commit_sha(self) -> None:
        case = canonical_case()
        case["source_ref"] = "v1.0.0"
        case["source_url"] = (
            "https://raw.githubusercontent.com/example-owner/example-repo/"
            "v1.0.0/fixtures/source.txt"
        )
        case["provenance_mode"] = "STRICT_IMMUTABLE_COMMIT"
        result = router.evaluate_case(case, fetcher=lambda _: GOOD_BYTES)
        self.assertEqual(result["decision_terminal"], "OPEN_UNPINNED_PROVENANCE")
        self.assertEqual(result["reason_code"], "STRICT_MODE_REQUIRES_FULL_COMMIT")


if __name__ == "__main__":
    unittest.main()
