#!/usr/bin/env python3
"""JANUS 113.8 AGENT GAUNTLET-0: adaptive internal red-team in read-only shadow mode.

This module attacks the frozen SIM-2 router without modifying it. The goal is
not to manufacture a pass, but to preserve reproducible findings and resisted
controls in a proof-carrying attack ledger.

The gauntlet performs no real network access. Every source read is supplied by
an in-memory fixture, except the redirect attack, which patches urlopen with a
fully local fake response to test final-host validation behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from sim import janus_113_8_sim2_router as router

VERSION = "JANUS-113.8-AGENT-GAUNTLET-0-v1.0"
SCHEMA = "janus.genesis.agent_gauntlet0.attack_result.v1"
RUN_COORDINATE_UTC = "2026-08-04T18:35:00Z"
TARGET_PATH = "sim/janus_113_8_sim2_router.py"
FIXTURE = b"JANUS GAUNTLET FIXTURE\nmarker: threshold\n"
FIXTURE_SHA256 = hashlib.sha256(FIXTURE).hexdigest()
PINNED_REF = "a" * 40
BASE_URL = f"https://raw.githubusercontent.com/example/project/{PINNED_REF}/fixture.txt"

STATUS_RESISTED = "RESISTED"
STATUS_FINDING = "FINDING"
STATUS_BOUNDARY = "BOUNDARY_CONFIRMED"
STATUS_HARNESS_ERROR = "HARNESS_ERROR"


class LocalResponse:
    """Minimal context-managed response used by the redirect attack."""

    def __init__(self, body: bytes, final_url: str) -> None:
        self._body = body
        self._final_url = final_url

    def __enter__(self) -> "LocalResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def read(self, limit: int = -1) -> bytes:
        if limit < 0:
            return self._body
        return self._body[:limit]

    def geturl(self) -> str:
        return self._final_url


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def make_case(
    *,
    case_id: Any,
    nonce: Any = "nonce-base",
    source_id: Any = "fixture-source",
    source_repository: Any = "example/project",
    source_ref: Any = PINNED_REF,
    source_path: Any = "fixture.txt",
    source_url: Any = BASE_URL,
    marker: str = "marker: threshold",
    sha256: str = FIXTURE_SHA256,
    size_bytes: int = len(FIXTURE),
    alternate_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": "janus.genesis.sim2.public_case.v1",
        "case_id": case_id,
        "nonce": nonce,
        "source_id": source_id,
        "source_repository": source_repository,
        "source_ref": source_ref,
        "source_path": source_path,
        "source_url": source_url,
        "claim": {
            "sha256": sha256,
            "size_bytes": size_bytes,
            "required_marker": marker,
            "alternate_sha256": alternate_sha256,
        },
        "read_only": True,
        "runtime_authority": "NONE",
    }


def fixture_fetcher(_: str) -> bytes:
    return FIXTURE


def forbidden_fetcher(_: str) -> bytes:
    raise AssertionError("source fetch must not occur after a safety gate")


def result_record(
    *,
    ordinal: int,
    attack_id: str,
    parent_attack_id: str | None,
    vector: str,
    security_property: str,
    status: str,
    severity: str,
    finding_code: str | None,
    expected: dict[str, Any],
    observed: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "schema": SCHEMA,
        "ordinal": ordinal,
        "attack_id": attack_id,
        "parent_attack_id": parent_attack_id,
        "vector": vector,
        "security_property": security_property,
        "status": status,
        "severity": severity,
        "finding_code": finding_code,
        "expected": expected,
        "observed": observed,
        "target_router_version": router.VERSION,
        "mode": "READ_ONLY_SHADOW",
        "runtime_authority": "NONE",
    }
    body["result_sha256"] = sha256_text(canonical_json(body))
    return body


def _safe_attack(
    results: list[dict[str, Any]],
    *,
    attack_id: str,
    parent_attack_id: str | None,
    vector: str,
    security_property: str,
    runner: Callable[[], dict[str, Any]],
) -> None:
    ordinal = len(results)
    try:
        payload = runner()
        results.append(
            result_record(
                ordinal=ordinal,
                attack_id=attack_id,
                parent_attack_id=parent_attack_id,
                vector=vector,
                security_property=security_property,
                status=payload["status"],
                severity=payload["severity"],
                finding_code=payload.get("finding_code"),
                expected=payload["expected"],
                observed=payload["observed"],
            )
        )
    except Exception as exc:  # a harness error is preserved, never silently skipped
        results.append(
            result_record(
                ordinal=ordinal,
                attack_id=attack_id,
                parent_attack_id=parent_attack_id,
                vector=vector,
                security_property=security_property,
                status=STATUS_HARNESS_ERROR,
                severity="CRITICAL",
                finding_code="GAUNTLET_HARNESS_EXCEPTION",
                expected={"exception": False},
                observed={"exception_type": type(exc).__name__, "message": str(exc)},
            )
        )


def _terminal_control(
    case: dict[str, Any],
    *,
    expected_terminal: str,
    fetcher: Callable[[str], bytes],
) -> dict[str, Any]:
    decision = router.evaluate_case(case, fetcher=fetcher)
    resisted = decision["decision_terminal"] == expected_terminal
    return {
        "status": STATUS_RESISTED if resisted else STATUS_FINDING,
        "severity": "INFO" if resisted else "HIGH",
        "finding_code": None if resisted else "EXPECTED_TERMINAL_NOT_RETURNED",
        "expected": {"decision_terminal": expected_terminal},
        "observed": {
            "decision_terminal": decision["decision_terminal"],
            "predicted_class": decision["predicted_class"],
            "confidence": decision["confidence"],
        },
    }


def build_attack_results() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    _safe_attack(
        results,
        attack_id="AG0-A00-HASH-TAMPER-CONTROL",
        parent_attack_id=None,
        vector="incorrect digest baseline",
        security_property="A wrong digest must not be supported.",
        runner=lambda: _terminal_control(
            make_case(case_id="AG0-A00", sha256="0" * 64),
            expected_terminal="REFUTED_HASH",
            fetcher=fixture_fetcher,
        ),
    )

    _safe_attack(
        results,
        attack_id="AG0-A01-UNTRUSTED-HOST-CONTROL",
        parent_attack_id=None,
        vector="disallowed source host baseline",
        security_property="A disallowed host must be blocked before any read.",
        runner=lambda: _terminal_control(
            make_case(
                case_id="AG0-A01",
                source_url=f"https://attacker.invalid/example/project/{PINNED_REF}/fixture.txt",
            ),
            expected_terminal="SAFETY_BLOCK_UNTRUSTED_SOURCE",
            fetcher=forbidden_fetcher,
        ),
    )

    _safe_attack(
        results,
        attack_id="AG0-A02-CONFLICTING-DIGEST-CONTROL",
        parent_attack_id=None,
        vector="two incompatible claim digests",
        security_property="Conflicting digests must remain OPEN.",
        runner=lambda: _terminal_control(
            make_case(case_id="AG0-A02", alternate_sha256="1" * 64),
            expected_terminal="OPEN_CONFLICTING_CLAIMS",
            fetcher=forbidden_fetcher,
        ),
    )

    _safe_attack(
        results,
        attack_id="AG0-A03-FLOATING-MAIN-CONTROL",
        parent_attack_id=None,
        vector="floating main ref",
        security_property="A floating branch ref must not be admitted as pinned provenance.",
        runner=lambda: _terminal_control(
            make_case(
                case_id="AG0-A03",
                source_ref="main",
                source_url="https://raw.githubusercontent.com/example/project/main/fixture.txt",
            ),
            expected_terminal="OPEN_UNPINNED_PROVENANCE",
            fetcher=forbidden_fetcher,
        ),
    )

    def metadata_mismatch() -> dict[str, Any]:
        case = make_case(
            case_id="AG0-A04",
            source_repository="claimed/innocent-project",
            source_path="claimed/other-file.txt",
        )
        decision = router.evaluate_case(case, fetcher=fixture_fetcher)
        vulnerable = decision["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
        return {
            "status": STATUS_FINDING if vulnerable else STATUS_RESISTED,
            "severity": "HIGH" if vulnerable else "INFO",
            "finding_code": "PROVENANCE_METADATA_NOT_BOUND_TO_URL" if vulnerable else None,
            "expected": {
                "source_repository_and_path_must_match_url": True,
                "decision_terminal": "REFUTED_SCHEMA_OR_OPEN_PROVENANCE_MISMATCH",
            },
            "observed": {
                "declared_repository": case["source_repository"],
                "declared_path": case["source_path"],
                "source_url": case["source_url"],
                "decision_terminal": decision["decision_terminal"],
            },
        }

    _safe_attack(
        results,
        attack_id="AG0-A04-METADATA-URL-MISMATCH",
        parent_attack_id="AG0-A00-HASH-TAMPER-CONTROL",
        vector="conflicting declared repository/path versus fetched URL",
        security_property="Every provenance field must describe the fetched object.",
        runner=metadata_mismatch,
    )

    def input_substitution_collision() -> dict[str, Any]:
        case_a = make_case(
            case_id="AG0-A05",
            nonce="nonce-alpha",
            source_repository="example/project",
            source_path="fixture.txt",
        )
        case_b = make_case(
            case_id="AG0-A05",
            nonce="nonce-beta",
            source_repository="substituted/project",
            source_path="substituted.txt",
        )
        decision_a = router.evaluate_case(case_a, fetcher=fixture_fetcher)
        decision_b = router.evaluate_case(case_b, fetcher=fixture_fetcher)
        collision = (
            canonical_json(case_a) != canonical_json(case_b)
            and decision_a["prediction_sha256"] == decision_b["prediction_sha256"]
        )
        return {
            "status": STATUS_FINDING if collision else STATUS_RESISTED,
            "severity": "HIGH" if collision else "INFO",
            "finding_code": "PREDICTION_HASH_NOT_BOUND_TO_FULL_INPUT_CASE" if collision else None,
            "expected": {"distinct_public_cases_have_distinct_bound_prediction_hashes": True},
            "observed": {
                "cases_are_distinct": canonical_json(case_a) != canonical_json(case_b),
                "prediction_sha256_a": decision_a["prediction_sha256"],
                "prediction_sha256_b": decision_b["prediction_sha256"],
                "collision": collision,
            },
        }

    _safe_attack(
        results,
        attack_id="AG0-A05-FULL-CASE-BINDING-COLLISION",
        parent_attack_id="AG0-A04-METADATA-URL-MISMATCH",
        vector="substitute nonce/repository/path while preserving prediction",
        security_property="A prediction witness must bind the complete input case.",
        runner=input_substitution_collision,
    )

    def duplicate_case_id() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_dir = root / "out"
            supported = make_case(case_id="AG0-DUPLICATE-ID", marker="marker: threshold")
            refuted = make_case(case_id="AG0-DUPLICATE-ID", marker="marker: absent")
            input_path.write_text(
                canonical_json(supported) + "\n" + canonical_json(refuted) + "\n",
                encoding="utf-8",
            )
            manifest = router.write_predictions(input_path, output_dir)
            ledger = [
                json.loads(line)
                for line in (output_dir / "witness_ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
            terminals = [
                json.loads(line)["decision_terminal"]
                for line in (output_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
            duplicate_accepted = len(ledger) == 2 and len({entry["case_id"] for entry in ledger}) == 1
            return {
                "status": STATUS_FINDING if duplicate_accepted else STATUS_RESISTED,
                "severity": "HIGH" if duplicate_accepted else "INFO",
                "finding_code": "CASE_ID_UNIQUENESS_NOT_ENFORCED" if duplicate_accepted else None,
                "expected": {"unique_case_ids": True},
                "observed": {
                    "case_count": manifest["case_count"],
                    "ledger_case_ids": [entry["case_id"] for entry in ledger],
                    "decision_terminals": terminals,
                    "duplicate_accepted": duplicate_accepted,
                },
            }

    _safe_attack(
        results,
        attack_id="AG0-A06-DUPLICATE-CASE-ID",
        parent_attack_id="AG0-A05-FULL-CASE-BINDING-COLLISION",
        vector="same case_id with different semantics and terminals",
        security_property="Case identifiers must be unique within a corpus.",
        runner=duplicate_case_id,
    )

    def unicode_identifier_collision() -> dict[str, Any]:
        composed = "AG0-é"
        decomposed = "AG0-e\u0301"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_dir = root / "out"
            input_path.write_text(
                canonical_json(make_case(case_id=composed))
                + "\n"
                + canonical_json(make_case(case_id=decomposed))
                + "\n",
                encoding="utf-8",
            )
            router.write_predictions(input_path, output_dir)
            ledger_ids = [
                json.loads(line)["case_id"]
                for line in (output_dir / "witness_ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line
            ]
            visually_colliding = (
                ledger_ids[0] != ledger_ids[1]
                and unicodedata.normalize("NFC", ledger_ids[0])
                == unicodedata.normalize("NFC", ledger_ids[1])
            )
            return {
                "status": STATUS_FINDING if visually_colliding else STATUS_RESISTED,
                "severity": "MEDIUM" if visually_colliding else "INFO",
                "finding_code": "IDENTIFIER_NORMALIZATION_NOT_ENFORCED" if visually_colliding else None,
                "expected": {"identifier_normalization_policy": "NFC_OR_EXPLICIT_REJECTION"},
                "observed": {
                    "ledger_case_ids": ledger_ids,
                    "nfc_equal": visually_colliding,
                },
            }

    _safe_attack(
        results,
        attack_id="AG0-A07-UNICODE-IDENTIFIER-COLLISION",
        parent_attack_id="AG0-A06-DUPLICATE-CASE-ID",
        vector="visually identical NFC/NFD case identifiers",
        security_property="Identifiers must not collide after Unicode normalization.",
        runner=unicode_identifier_collision,
    )

    def duplicate_json_key() -> dict[str, Any]:
        case = make_case(case_id="AG0-A08", nonce="nonce-base")
        raw = canonical_json(case)
        raw = raw.replace(
            '"nonce":"nonce-base"',
            '"nonce":"first-value","nonce":"second-value"',
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_dir = root / "out"
            input_path.write_text(raw + "\n", encoding="utf-8")
            router.write_predictions(input_path, output_dir)
            prediction = json.loads((output_dir / "predictions.jsonl").read_text(encoding="utf-8"))
            parsed_nonce = json.loads(raw)["nonce"]
            accepted = prediction["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
            return {
                "status": STATUS_FINDING if accepted else STATUS_RESISTED,
                "severity": "HIGH" if accepted else "INFO",
                "finding_code": "DUPLICATE_JSON_KEYS_ACCEPTED" if accepted else None,
                "expected": {"duplicate_json_object_keys": "REJECT"},
                "observed": {
                    "parsed_nonce": parsed_nonce,
                    "decision_terminal": prediction["decision_terminal"],
                    "duplicate_key_was_silently_last_wins": parsed_nonce == "second-value",
                },
            }

    _safe_attack(
        results,
        attack_id="AG0-A08-DUPLICATE-JSON-KEY",
        parent_attack_id="AG0-A07-UNICODE-IDENTIFIER-COLLISION",
        vector="duplicate object key with last-value-wins parsing",
        security_property="Ambiguous JSON objects must be rejected before routing.",
        runner=duplicate_json_key,
    )

    def malformed_line_abort() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "cases.jsonl"
            output_dir = root / "out"
            input_path.write_text(
                canonical_json(make_case(case_id="AG0-A09-VALID")) + "\n" + "{not-json}\n",
                encoding="utf-8",
            )
            exception_type: str | None = None
            try:
                router.write_predictions(input_path, output_dir)
            except Exception as exc:
                exception_type = type(exc).__name__
            ledger_exists = (output_dir / "witness_ledger.jsonl").exists()
            aborted_without_ledger = exception_type is not None and not ledger_exists
            return {
                "status": STATUS_FINDING if aborted_without_ledger else STATUS_RESISTED,
                "severity": "HIGH" if aborted_without_ledger else "INFO",
                "finding_code": "MALFORMED_CASE_ABORTS_FULL_LEDGER" if aborted_without_ledger else None,
                "expected": {"every_input_line_receives_a_ledger_terminal": True},
                "observed": {
                    "exception_type": exception_type,
                    "ledger_exists": ledger_exists,
                    "aborted_without_ledger": aborted_without_ledger,
                },
            }

    _safe_attack(
        results,
        attack_id="AG0-A09-MALFORMED-LINE-CORPUS-ABORT",
        parent_attack_id="AG0-A08-DUPLICATE-JSON-KEY",
        vector="one malformed JSONL line after a valid case",
        security_property="Malformed inputs must fail per case without erasing corpus accounting.",
        runner=malformed_line_abort,
    )

    def oversized_source_open() -> dict[str, Any]:
        def oversized_fetcher(_: str) -> bytes:
            raise RuntimeError("source read failed: source exceeds bounded read limit")

        decision = router.evaluate_case(make_case(case_id="AG0-A10"), fetcher=oversized_fetcher)
        collapsed = decision["decision_terminal"] == "OPEN_SOURCE_UNREACHABLE"
        return {
            "status": STATUS_FINDING if collapsed else STATUS_RESISTED,
            "severity": "MEDIUM" if collapsed else "INFO",
            "finding_code": "RESOURCE_LIMIT_COLLAPSED_INTO_UNREACHABLE_OPEN" if collapsed else None,
            "expected": {"resource_limit_has_distinct_typed_terminal": True},
            "observed": {
                "decision_terminal": decision["decision_terminal"],
                "reason": decision["reason"],
            },
        }

    _safe_attack(
        results,
        attack_id="AG0-A10-OVERSIZE-COLLAPSED-TO-OPEN",
        parent_attack_id="AG0-A09-MALFORMED-LINE-CORPUS-ABORT",
        vector="bounded-read overflow reported as generic source unreachability",
        security_property="Resource exhaustion and network unreachability require distinct evidence.",
        runner=oversized_source_open,
    )

    def redirect_final_host() -> dict[str, Any]:
        final_url = "https://attacker.invalid/final-payload.txt"

        def fake_urlopen(request: object, timeout: int) -> LocalResponse:
            return LocalResponse(FIXTURE, final_url)

        with mock.patch.object(router.urllib.request, "urlopen", side_effect=fake_urlopen):
            decision = router.evaluate_case(
                make_case(case_id="AG0-A11"),
                fetcher=router.fetch_bytes,
            )
        accepted = decision["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
        return {
            "status": STATUS_FINDING if accepted else STATUS_RESISTED,
            "severity": "CRITICAL" if accepted else "INFO",
            "finding_code": "REDIRECT_TARGET_HOST_NOT_REVALIDATED" if accepted else None,
            "expected": {"final_response_host_must_equal_allowlisted_host": True},
            "observed": {
                "initial_url": BASE_URL,
                "simulated_final_url": final_url,
                "decision_terminal": decision["decision_terminal"],
            },
        }

    _safe_attack(
        results,
        attack_id="AG0-A11-REDIRECT-FINAL-HOST",
        parent_attack_id="AG0-A01-UNTRUSTED-HOST-CONTROL",
        vector="allowlisted initial URL redirects to a disallowed final host",
        security_property="The allowlist must be enforced on the final response URL.",
        runner=redirect_final_host,
    )

    def noncanonical_query_fragment() -> dict[str, Any]:
        url = BASE_URL + "?download=1#alternate-view"
        decision = router.evaluate_case(
            make_case(case_id="AG0-A12", source_url=url),
            fetcher=fixture_fetcher,
        )
        accepted = decision["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
        return {
            "status": STATUS_FINDING if accepted else STATUS_RESISTED,
            "severity": "MEDIUM" if accepted else "INFO",
            "finding_code": "NON_CANONICAL_SOURCE_URL_ACCEPTED" if accepted else None,
            "expected": {"source_url_query_and_fragment": "REJECT_OR_CANONICALIZE"},
            "observed": {"source_url": url, "decision_terminal": decision["decision_terminal"]},
        }

    _safe_attack(
        results,
        attack_id="AG0-A12-QUERY-FRAGMENT-AMBIGUITY",
        parent_attack_id="AG0-A11-REDIRECT-FINAL-HOST",
        vector="query and fragment appended to a pinned raw URL",
        security_property="Provenance URLs require an unambiguous canonical form.",
        runner=noncanonical_query_fragment,
    )

    def path_traversal() -> dict[str, Any]:
        url = (
            f"https://raw.githubusercontent.com/example/project/{PINNED_REF}/"
            "directory/../fixture.txt"
        )
        decision = router.evaluate_case(
            make_case(case_id="AG0-A13", source_url=url),
            fetcher=fixture_fetcher,
        )
        accepted = decision["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
        return {
            "status": STATUS_FINDING if accepted else STATUS_RESISTED,
            "severity": "HIGH" if accepted else "INFO",
            "finding_code": "URL_PATH_CANONICALIZATION_NOT_ENFORCED" if accepted else None,
            "expected": {"dot_segments_in_source_url": "REJECT"},
            "observed": {"source_url": url, "decision_terminal": decision["decision_terminal"]},
        }

    _safe_attack(
        results,
        attack_id="AG0-A13-DOT-SEGMENT-PATH",
        parent_attack_id="AG0-A12-QUERY-FRAGMENT-AMBIGUITY",
        vector="dot-segment path accepted as a pinned source URL",
        security_property="The fetched path must be canonical and bound to source_path.",
        runner=path_traversal,
    )

    def movable_tag_boundary() -> dict[str, Any]:
        tag = "v1.0.0"
        url = f"https://raw.githubusercontent.com/example/project/{tag}/fixture.txt"
        decision = router.evaluate_case(
            make_case(case_id="AG0-A14", source_ref=tag, source_url=url),
            fetcher=fixture_fetcher,
        )
        supported = decision["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
        return {
            "status": STATUS_BOUNDARY if supported else STATUS_RESISTED,
            "severity": "BOUNDARY" if supported else "INFO",
            "finding_code": "MOVABLE_GIT_TAG_ALLOWED_BY_SIM2_CONTRACT" if supported else None,
            "expected": {
                "sim2_contract": "release tags are accepted",
                "stronger_future_contract": "full_commit_sha_only",
            },
            "observed": {
                "source_ref": tag,
                "decision_terminal": decision["decision_terminal"],
            },
        }

    _safe_attack(
        results,
        attack_id="AG0-A14-MOVABLE-TAG-BOUNDARY",
        parent_attack_id="AG0-A03-FLOATING-MAIN-CONTROL",
        vector="release tag treated as pinned despite tag mutability",
        security_property="Record the difference between a release label and an immutable commit object.",
        runner=movable_tag_boundary,
    )

    return results


def write_proofpack(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = build_attack_results()

    results_path = output_dir / "attack_results.jsonl"
    results_text = "".join(canonical_json(result) + "\n" for result in results)
    results_path.write_text(results_text, encoding="utf-8")

    previous = "0" * 64
    ledger: list[dict[str, Any]] = []
    for ordinal, result in enumerate(results):
        body = {
            "ordinal": ordinal,
            "attack_id": result["attack_id"],
            "result_sha256": result["result_sha256"],
            "prev_hash": previous,
        }
        entry_hash = sha256_text(canonical_json(body))
        entry = {**body, "entry_hash": entry_hash}
        ledger.append(entry)
        previous = entry_hash

    ledger_path = output_dir / "attack_ledger.jsonl"
    ledger_text = "".join(canonical_json(entry) + "\n" for entry in ledger)
    ledger_path.write_text(ledger_text, encoding="utf-8")

    findings = [
        {
            "attack_id": result["attack_id"],
            "finding_code": result["finding_code"],
            "severity": result["severity"],
            "security_property": result["security_property"],
        }
        for result in results
        if result["status"] in {STATUS_FINDING, STATUS_BOUNDARY}
    ]
    findings_path = output_dir / "finding_catalog.json"
    findings_text = json.dumps(findings, indent=2, ensure_ascii=False) + "\n"
    findings_path.write_text(findings_text, encoding="utf-8")

    status_counts = dict(sorted(Counter(result["status"] for result in results).items()))
    target_path = Path(router.__file__).resolve()
    target_source_sha256 = sha256_bytes(target_path.read_bytes())
    terminal = (
        "JANUS_113.8_AGENT_GAUNTLET_0_INCOMPLETE"
        if status_counts.get(STATUS_HARNESS_ERROR, 0)
        else "JANUS_113.8_AGENT_GAUNTLET_0_COMPLETED_WITH_FINDINGS"
        if status_counts.get(STATUS_FINDING, 0)
        else "JANUS_113.8_AGENT_GAUNTLET_0_COMPLETED_NO_FINDINGS"
    )
    replay_digest = sha256_text(
        canonical_json(
            {
                "result_hashes": [result["result_sha256"] for result in results],
                "final_ledger_hash": previous,
                "status_counts": status_counts,
                "target_source_sha256": target_source_sha256,
            }
        )
    )
    manifest = {
        "schema": "janus.genesis.agent_gauntlet0.manifest.v1",
        "version": VERSION,
        "run_coordinate_utc": RUN_COORDINATE_UTC,
        "mode": "READ_ONLY_SHADOW",
        "target": {
            "path": TARGET_PATH,
            "router_version": router.VERSION,
            "source_sha256": target_source_sha256,
            "modified_by_gauntlet": False,
        },
        "attack_count": len(results),
        "status_counts": status_counts,
        "candidate_conservation": {
            "attack_count": len(results),
            "accounted": sum(status_counts.values()),
            "holds": len(results) == sum(status_counts.values()),
        },
        "finding_codes": [
            result["finding_code"]
            for result in results
            if result["finding_code"] is not None
        ],
        "attack_results_sha256": sha256_text(results_text),
        "attack_ledger_sha256": sha256_text(ledger_text),
        "finding_catalog_sha256": sha256_text(findings_text),
        "final_ledger_hash": previous,
        "replay_digest_sha256": replay_digest,
        "terminal": terminal,
        "sim3_effect": "NONE_EXTERNAL_AUTHOR_REQUIREMENT_UNCHANGED",
        "safety_boundary": {
            "real_network_read": False,
            "network_write": False,
            "file_deletion": False,
            "self_modification": False,
            "external_actuation": False,
            "private_repository_access": False,
            "repository_secrets": False,
            "real_syslog_ingest": False,
            "runtime_authority": "NONE",
            "consciousness_status": "NOT_CLAIMED",
        },
    }
    (output_dir / "gauntlet_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    manifest = write_proofpack(args.output)
    if args.print_summary:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0 if manifest["terminal"] != "JANUS_113.8_AGENT_GAUNTLET_0_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
