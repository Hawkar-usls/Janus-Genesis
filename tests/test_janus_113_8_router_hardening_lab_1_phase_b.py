#!/usr/bin/env python3
"""Passing contract for JANUS 113.8 Router Hardening Laboratory-1 Phase B.

The contract maps A04-A14 to the accepted repair schema. All source reads are
local fixtures or mocked response objects; no live network access is permitted.
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


GOOD_BYTES = b"JANUS PHASE B FIXTURE\nrequired-marker\n"
GOOD_SHA256 = router.sha256_bytes(GOOD_BYTES)
FULL_COMMIT = "1" * 40


def strict_case(*, case_id: str = "case-001") -> dict:
    return {
        "schema": "janus.genesis.router.public_case.v2",
        "provenance_mode": "STRICT_IMMUTABLE_COMMIT",
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


def legacy_v1_case() -> dict:
    case = strict_case()
    case.pop("provenance_mode")
    case["schema"] = "janus.genesis.sim2.public_case.v1"
    case["source_ref"] = "v1.0.0"
    case["source_url"] = (
        "https://raw.githubusercontent.com/"
        "example-owner/example-repo/v1.0.0/fixtures/source.txt"
    )
    return case


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


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class RouterHardeningPhaseBContract(unittest.TestCase):
    def test_a04_provenance_tuple_must_bind_to_canonical_url_before_fetch(self) -> None:
        case = strict_case()
        case["source_repository"] = "different-owner/different-repo"
        fetch_calls = 0

        def fetcher(_: str) -> bytes:
            nonlocal fetch_calls
            fetch_calls += 1
            return GOOD_BYTES

        result = router.evaluate_case(case, fetcher=fetcher)
        self.assertEqual(result["decision_terminal"], "REFUTED_PROVENANCE_MISMATCH")
        self.assertEqual(fetch_calls, 0)

    def test_a04_legacy_provenance_tuple_must_bind_before_fetch(self) -> None:
        mutations = {
            "repository": ("source_repository", "different-owner/different-repo"),
            "path": ("source_path", "different/path.txt"),
        }
        for label, (field, value) in mutations.items():
            with self.subTest(label=label):
                case = legacy_v1_case()
                case[field] = value
                fetch_calls = 0

                def fetcher(_: str) -> bytes:
                    nonlocal fetch_calls
                    fetch_calls += 1
                    return GOOD_BYTES

                result = router.evaluate_case(case, fetcher=fetcher)
                self.assertEqual(
                    result["decision_terminal"],
                    "REFUTED_PROVENANCE_MISMATCH",
                )
                self.assertEqual(fetch_calls, 0)

    def test_a05_prediction_hash_binds_exact_case_input(self) -> None:
        case_a = strict_case(case_id="same-visible-case")
        case_b = strict_case(case_id="same-visible-case")
        case_b["nonce"] = "different-nonce"

        result_a = router.evaluate_case(case_a, fetcher=lambda _: GOOD_BYTES)
        result_b = router.evaluate_case(case_b, fetcher=lambda _: GOOD_BYTES)

        self.assertNotEqual(result_a["input_case_sha256"], result_b["input_case_sha256"])
        self.assertNotEqual(result_a["prediction_sha256"], result_b["prediction_sha256"])
        self.assertEqual(result_a["schema"], "janus.genesis.router.prediction.v2")

    def test_a06_duplicate_case_id_is_preserved_as_typed_collision(self) -> None:
        cases = [strict_case(case_id="duplicate"), strict_case(case_id="duplicate")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            out = root / "out"
            source.write_text(
                "".join(router.canonical_json(case) + "\n" for case in cases),
                encoding="utf-8",
            )
            manifest = router.write_predictions(source, out, fetcher=lambda _: GOOD_BYTES)
            predictions = read_jsonl(out / "predictions.jsonl")
            ledger = read_jsonl(out / "witness_ledger.jsonl")

        self.assertEqual(predictions[0]["decision_terminal"], "SUPPORTED_PUBLIC_PROVENANCE")
        self.assertEqual(predictions[1]["decision_terminal"], "REFUTED_IDENTIFIER_COLLISION")
        self.assertEqual(len(predictions), 2)
        self.assertEqual(len(ledger), 2)
        self.assertTrue(manifest["line_conservation"])

    def test_a07_nfc_equivalent_identifier_is_typed_collision(self) -> None:
        composed = "caf\u00e9"
        decomposed = unicodedata.normalize("NFD", composed)
        cases = [strict_case(case_id=composed), strict_case(case_id=decomposed)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            out = root / "out"
            source.write_text(
                "".join(router.canonical_json(case) + "\n" for case in cases),
                encoding="utf-8",
            )
            router.write_predictions(source, out, fetcher=lambda _: GOOD_BYTES)
            predictions = read_jsonl(out / "predictions.jsonl")

        self.assertEqual(predictions[1]["decision_terminal"], "REFUTED_IDENTIFIER_COLLISION")
        self.assertEqual(predictions[1]["normalized_case_id"], composed)

    def test_a08_duplicate_key_at_nested_depth_is_typed_and_preserved(self) -> None:
        raw = router.canonical_json(strict_case())
        raw = raw.replace(
            f'"size_bytes":{len(GOOD_BYTES)}',
            f'"size_bytes":{len(GOOD_BYTES)},"size_bytes":{len(GOOD_BYTES)}',
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            out = root / "out"
            source.write_text(raw + "\n", encoding="utf-8")
            manifest = router.write_predictions(source, out, fetcher=lambda _: GOOD_BYTES)
            prediction = read_jsonl(out / "predictions.jsonl")[0]
            ledger = read_jsonl(out / "witness_ledger.jsonl")

        self.assertEqual(prediction["parse_status"], "DUPLICATE_JSON_KEY")
        self.assertEqual(prediction["decision_terminal"], "REFUTED_JSON_DUPLICATE_KEY")
        self.assertIsNone(prediction["input_case_sha256"])
        self.assertEqual(len(ledger), 1)
        self.assertTrue(manifest["line_conservation"])

    def test_a09_malformed_line_never_aborts_or_disappears(self) -> None:
        lines = [
            router.canonical_json(strict_case(case_id="good-1")),
            '{"schema":',
            router.canonical_json(strict_case(case_id="good-2")),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            out = root / "out"
            source.write_text("\n".join(lines) + "\n", encoding="utf-8")
            manifest = router.write_predictions(source, out, fetcher=lambda _: GOOD_BYTES)
            predictions = read_jsonl(out / "predictions.jsonl")
            ledger = read_jsonl(out / "witness_ledger.jsonl")

        self.assertEqual([item["ordinal"] for item in predictions], [0, 1, 2])
        self.assertEqual(predictions[1]["parse_status"], "MALFORMED_JSON")
        self.assertEqual(predictions[1]["decision_terminal"], "REFUTED_SCHEMA")
        self.assertEqual(predictions[2]["decision_terminal"], "SUPPORTED_PUBLIC_PROVENANCE")
        self.assertEqual(len(ledger), 3)
        self.assertEqual(manifest["input_nonempty_line_count"], 3)
        self.assertEqual(manifest["prediction_count"], 3)
        self.assertEqual(manifest["ledger_entry_count"], 3)
        self.assertTrue(manifest["line_conservation"])

    def test_a10_resource_limit_is_not_transport_open(self) -> None:
        case = strict_case()

        def fetcher(_: str) -> bytes:
            raise router.ResourceLimitError("source exceeds bounded read limit")

        result = router.evaluate_case(case, fetcher=fetcher)
        self.assertEqual(result["decision_terminal"], "REFUTED_RESOURCE_LIMIT")
        self.assertEqual(result["reason_code"], "SOURCE_RESOURCE_LIMIT")

    def test_a11_redirect_target_is_revalidated_before_bytes_are_trusted(self) -> None:
        case = strict_case()
        with mock.patch.object(
            router.urllib.request,
            "urlopen",
            return_value=FakeResponse(GOOD_BYTES, "https://example.invalid/redirected.txt"),
        ):
            result = router.evaluate_case(case)

        self.assertEqual(result["decision_terminal"], "SAFETY_BLOCK_REDIRECT_TARGET")
        self.assertEqual(result["observed"], None)

    def test_a12_query_fragment_userinfo_and_port_are_noncanonical(self) -> None:
        variants = [
            strict_case()["source_url"] + "?download=1",
            strict_case()["source_url"] + "#fragment",
            strict_case()["source_url"].replace("https://", "https://user@", 1),
            strict_case()["source_url"].replace("raw.githubusercontent.com", "raw.githubusercontent.com:443", 1),
        ]
        for source_url in variants:
            with self.subTest(source_url=source_url):
                case = strict_case()
                case["source_url"] = source_url
                result = router.evaluate_case(case, fetcher=lambda _: GOOD_BYTES)
                self.assertEqual(result["decision_terminal"], "REFUTED_NON_CANONICAL_URL")

    def test_a13_dot_segment_and_encoded_separator_are_noncanonical(self) -> None:
        variants = [
            strict_case()["source_url"].replace(
                "/fixtures/source.txt", "/fixtures/../fixtures/source.txt"
            ),
            strict_case()["source_url"].replace("/fixtures/source.txt", "/fixtures%2Fsource.txt"),
        ]
        for source_url in variants:
            with self.subTest(source_url=source_url):
                case = strict_case()
                case["source_url"] = source_url
                result = router.evaluate_case(case, fetcher=lambda _: GOOD_BYTES)
                self.assertEqual(result["decision_terminal"], "REFUTED_NON_CANONICAL_URL")

    def test_a14_strict_mode_requires_full_commit_but_legacy_v1_remains_valid(self) -> None:
        strict = strict_case()
        strict["source_ref"] = "v1.0.0"
        strict["source_url"] = strict["source_url"].replace(FULL_COMMIT, "v1.0.0")
        strict_result = router.evaluate_case(strict, fetcher=lambda _: GOOD_BYTES)
        legacy_result = router.evaluate_case(legacy_v1_case(), fetcher=lambda _: GOOD_BYTES)

        self.assertEqual(strict_result["decision_terminal"], "OPEN_UNPINNED_PROVENANCE")
        self.assertEqual(strict_result["reason_code"], "STRICT_MODE_REQUIRES_FULL_COMMIT")
        self.assertEqual(legacy_result["decision_terminal"], "SUPPORTED_PUBLIC_PROVENANCE")

    def test_line_resource_limit_keeps_one_ledger_position(self) -> None:
        oversized = "x" * (router.MAX_JSONL_LINE_BYTES + 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            out = root / "out"
            source.write_text(oversized + "\n", encoding="utf-8")
            manifest = router.write_predictions(source, out, fetcher=lambda _: GOOD_BYTES)
            prediction = read_jsonl(out / "predictions.jsonl")[0]
            ledger = read_jsonl(out / "witness_ledger.jsonl")

        self.assertEqual(prediction["parse_status"], "LINE_RESOURCE_LIMIT")
        self.assertEqual(prediction["decision_terminal"], "REFUTED_RESOURCE_LIMIT")
        self.assertEqual(len(ledger), 1)
        self.assertTrue(manifest["line_conservation"])

    def test_dual_runs_are_byte_identical_and_ledger_hashes_replay(self) -> None:
        lines = [
            router.canonical_json(strict_case(case_id="good")),
            '{"schema":',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "cases.jsonl"
            out_a = root / "out-a"
            out_b = root / "out-b"
            source.write_text("\n".join(lines) + "\n", encoding="utf-8")
            router.write_predictions(source, out_a, fetcher=lambda _: GOOD_BYTES)
            router.write_predictions(source, out_b, fetcher=lambda _: GOOD_BYTES)

            for name in ("predictions.jsonl", "witness_ledger.jsonl", "router_manifest.json"):
                self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes())

            previous = "0" * 64
            for entry in read_jsonl(out_a / "witness_ledger.jsonl"):
                body = {key: value for key, value in entry.items() if key != "entry_hash"}
                expected = router.sha256_text(
                    "JANUS_ROUTER_LEDGER_V2\n" + router.canonical_json(body)
                )
                self.assertEqual(entry["prev_hash"], previous)
                self.assertEqual(entry["entry_hash"], expected)
                previous = expected

            manifest = json.loads((out_a / "router_manifest.json").read_text(encoding="utf-8"))

        self.assertTrue(manifest["deterministic_output"])
        self.assertNotIn("generated_utc", manifest)
        self.assertEqual(manifest["final_ledger_hash"], previous)


if __name__ == "__main__":
    unittest.main()
