#!/usr/bin/env python3
"""JANUS 113.8 hardened read-only public provenance router.

The router accepts historical SIM-2 v1 cases through an explicit legacy adapter
and hardened v2 cases through a strict provenance contract. Every accepted
corpus preserves one prediction and one Witness Ledger entry for every non-empty
input line, including malformed and rejected lines.

The runtime performs no network write, deletion, self-modification, external
actuation, private-repository access, or background loop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

VERSION = "JANUS-113.8-HARDENED-ROUTER-v2.0"
LEGACY_SCHEMA = "janus.genesis.sim2.public_case.v1"
HARDENED_SCHEMA = "janus.genesis.router.public_case.v2"
LEGACY_MODE = "LEGACY_SIM2_RELEASE_TAG"
STRICT_MODE = "STRICT_IMMUTABLE_COMMIT"
ALLOWED_HOST = "raw.githubusercontent.com"
UNPINNED_REFS = {"main", "master", "HEAD"}
MAX_SOURCE_BYTES = 300_000
MAX_INPUT_FILE_BYTES = 16_777_216
MAX_NONEMPTY_LINES = 10_000
MAX_JSONL_LINE_BYTES = 65_536
MAX_STRING_CHARACTERS = 4_096
MAX_JSON_NESTING_DEPTH = 16
MAX_OBJECT_MEMBERS = 64
TIMEOUT_SECONDS = 20
RETRY_COUNT = 3
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
PREDICTION_DOMAIN = "JANUS_ROUTER_PREDICTION_V2\n"
LEDGER_DOMAIN = "JANUS_ROUTER_LEDGER_V2\n"
ZERO_HASH = "0" * 64

VALID_TERMINALS = {
    "SUPPORTED_PUBLIC_PROVENANCE",
    "REFUTED_HASH",
    "REFUTED_SIZE",
    "REFUTED_MARKER",
    "REFUTED_SCHEMA",
    "REFUTED_RESOURCE_LIMIT",
    "REFUTED_JSON_DUPLICATE_KEY",
    "REFUTED_IDENTIFIER_COLLISION",
    "REFUTED_PROVENANCE_MISMATCH",
    "REFUTED_NON_CANONICAL_URL",
    "OPEN_SOURCE_UNREACHABLE",
    "OPEN_UNPINNED_PROVENANCE",
    "OPEN_CONFLICTING_CLAIMS",
    "SAFETY_BLOCK_UNTRUSTED_SOURCE",
    "SAFETY_BLOCK_REDIRECT_TARGET",
}


class ResourceLimitError(RuntimeError):
    """A bounded local or source-size resource contract was exceeded."""


class RedirectTargetError(RuntimeError):
    """A final response URL failed the frozen source gate."""


class SourceReadError(RuntimeError):
    """A bounded public source could not be read after retries."""


class DuplicateKeyError(ValueError):
    """A JSON object contained a repeated member name."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> str:
    """Retained for API compatibility; deterministic router outputs do not use it."""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _strict_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json_resource_error(value: Any, *, depth: int = 0) -> str | None:
    if depth > MAX_JSON_NESTING_DEPTH:
        return "JSON nesting depth exceeds the frozen bound"
    if isinstance(value, str):
        if len(value) > MAX_STRING_CHARACTERS:
            return "JSON string exceeds the frozen character bound"
        return None
    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_MEMBERS:
            return "JSON object exceeds the frozen member bound"
        for key, item in value.items():
            if len(key) > MAX_STRING_CHARACTERS:
                return "JSON object key exceeds the frozen character bound"
            error = _json_resource_error(item, depth=depth + 1)
            if error:
                return error
        return None
    if isinstance(value, list):
        for item in value:
            error = _json_resource_error(item, depth=depth + 1)
            if error:
                return error
    return None


def _decode_canonical_segment(raw_segment: str) -> str:
    if not raw_segment or INVALID_PERCENT_ESCAPE.search(raw_segment):
        raise ValueError("empty or invalid percent-encoded URL segment")
    try:
        decoded = urllib.parse.unquote(raw_segment, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("URL segment is not valid UTF-8") from exc
    if decoded in {".", ".."}:
        raise ValueError("dot segment is forbidden")
    if any(character in decoded for character in ("/", "\\", "\x00")):
        raise ValueError("decoded separator, backslash, or NUL is forbidden")
    canonical = urllib.parse.quote(decoded, safe="-._~")
    if canonical != raw_segment:
        raise ValueError("URL segment does not round-trip canonically")
    return decoded


def _canonical_url_tuple(url: str) -> tuple[str, str, str, str]:
    if not isinstance(url, str) or not 1 <= len(url) <= MAX_STRING_CHARACTERS:
        raise ValueError("source_url must be bounded text")
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("source_url could not be parsed canonically") from exc

    if parsed.scheme != "https" or hostname != ALLOWED_HOST:
        raise PermissionError("scheme or host is outside the read-only allowlist")
    if parsed.netloc != ALLOWED_HOST:
        raise ValueError("userinfo, host case variation, or explicit port is forbidden")
    if parsed.query or parsed.fragment:
        raise ValueError("query and fragment are forbidden")
    if not parsed.path.startswith("/"):
        raise ValueError("source path must be absolute")

    raw_segments = parsed.path[1:].split("/")
    if len(raw_segments) < 4 or any(segment == "" for segment in raw_segments):
        raise ValueError("raw GitHub URL lacks a complete canonical tuple")
    decoded = [_decode_canonical_segment(segment) for segment in raw_segments]
    owner, repository, source_ref = decoded[:3]
    source_path = "/".join(decoded[3:])
    return owner, repository, source_ref, source_path


def _url_gate(case: dict[str, Any]) -> tuple[str | None, str, str]:
    url = case.get("source_url")
    if not isinstance(url, str):
        return "REFUTED_SCHEMA", "SOURCE_URL_NOT_TEXT", "source_url must be text"
    try:
        owner, repository, observed_ref, observed_path = _canonical_url_tuple(url)
    except PermissionError as exc:
        return "SAFETY_BLOCK_UNTRUSTED_SOURCE", "UNTRUSTED_SOURCE_ORIGIN", str(exc)
    except ValueError as exc:
        return "REFUTED_NON_CANONICAL_URL", "NON_CANONICAL_SOURCE_URL", str(exc)

    declared_repository = case.get("source_repository")
    declared_ref = case.get("source_ref")
    declared_path = case.get("source_path")
    observed_repository = f"{owner}/{repository}"
    if (
        observed_repository != declared_repository
        or observed_ref != declared_ref
        or observed_path != declared_path
    ):
        return (
            "REFUTED_PROVENANCE_MISMATCH",
            "PROVENANCE_TUPLE_MISMATCH",
            "source_repository/source_ref/source_path do not match the canonical URL tuple",
        )

    mode = case.get("provenance_mode")
    if mode == STRICT_MODE and not isinstance(declared_ref, str):
        return "OPEN_UNPINNED_PROVENANCE", "STRICT_MODE_REQUIRES_FULL_COMMIT", "strict mode requires a full commit"
    if mode == STRICT_MODE and not HEX40.fullmatch(declared_ref):
        return (
            "OPEN_UNPINNED_PROVENANCE",
            "STRICT_MODE_REQUIRES_FULL_COMMIT",
            "strict mode requires a full lowercase 40-hex commit SHA",
        )
    if declared_ref in UNPINNED_REFS:
        return (
            "OPEN_UNPINNED_PROVENANCE",
            "LEGACY_MODE_FLOATING_REF" if mode == LEGACY_MODE else "STRICT_MODE_REQUIRES_FULL_COMMIT",
            "source ref is floating",
        )
    return None, "CANONICAL_PUBLIC_SOURCE", "trusted canonical public source"


def fetch_bytes(url: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
    """Read one bounded public source and revalidate the final response URL."""

    original_tuple = _canonical_url_tuple(url)
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"{VERSION} read-only provenance check"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                final_url = response.geturl()
                try:
                    final_tuple = _canonical_url_tuple(final_url)
                except (PermissionError, ValueError) as exc:
                    raise RedirectTargetError(str(exc)) from exc
                if final_tuple != original_tuple:
                    raise RedirectTargetError("final response URL changed the frozen provenance tuple")
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ResourceLimitError("source exceeds bounded read limit")
                return data
        except (ResourceLimitError, RedirectTargetError):
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < RETRY_COUNT:
                time.sleep(0.25 * (attempt + 1))
    raise SourceReadError(f"source read failed: {last_error}")


def _claim_schema_error(claim: Any) -> str | None:
    if not isinstance(claim, dict):
        return "claim must be an object"
    if set(claim) != {"sha256", "size_bytes", "required_marker", "alternate_sha256"}:
        return "claim fields do not match the sealed schema"
    if not isinstance(claim["sha256"], str) or not HEX64.fullmatch(claim["sha256"]):
        return "sha256 must contain exactly 64 lowercase hexadecimal characters"
    size = claim["size_bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_SOURCE_BYTES:
        return "size_bytes must be a bounded integer"
    marker = claim["required_marker"]
    if not isinstance(marker, str) or not 1 <= len(marker) <= MAX_STRING_CHARACTERS:
        return "required_marker must be bounded non-empty text"
    alternate = claim["alternate_sha256"]
    if alternate is not None and (not isinstance(alternate, str) or not HEX64.fullmatch(alternate)):
        return "alternate_sha256 must be null or a complete digest"
    return None


def _adapt_and_validate_case(case: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(case, dict):
        return None, "public case must be an object"

    schema = case.get("schema")
    if schema == LEGACY_SCHEMA:
        required = {
            "schema",
            "case_id",
            "nonce",
            "source_id",
            "source_repository",
            "source_ref",
            "source_path",
            "source_url",
            "claim",
            "read_only",
            "runtime_authority",
        }
        if set(case) != required:
            return None, "historical v1 case fields do not match the sealed schema"
        adapted = dict(case)
        adapted["schema"] = HARDENED_SCHEMA
        adapted["provenance_mode"] = LEGACY_MODE
    elif schema == HARDENED_SCHEMA:
        required = {
            "schema",
            "provenance_mode",
            "case_id",
            "nonce",
            "source_id",
            "source_repository",
            "source_ref",
            "source_path",
            "source_url",
            "claim",
            "read_only",
            "runtime_authority",
        }
        if set(case) != required:
            return None, "hardened v2 case fields do not match the sealed schema"
        adapted = dict(case)
    else:
        return None, "public case schema mismatch"

    if adapted.get("provenance_mode") not in {LEGACY_MODE, STRICT_MODE}:
        return None, "provenance_mode is invalid"
    if adapted.get("read_only") is not True or adapted.get("runtime_authority") != "NONE":
        return None, "case authority boundary is invalid"

    for field in ("case_id", "source_id"):
        value = adapted.get(field)
        if not isinstance(value, str) or not 1 <= len(value) <= 256:
            return None, f"{field} must be bounded non-empty text"
    nonce = adapted.get("nonce")
    if not isinstance(nonce, str) or not 1 <= len(nonce) <= 256:
        return None, "nonce must be bounded non-empty text"
    source_repository = adapted.get("source_repository")
    if (
        not isinstance(source_repository, str)
        or len(source_repository) > 201
        or not REPOSITORY.fullmatch(source_repository)
    ):
        return None, "source_repository is invalid"
    source_ref = adapted.get("source_ref")
    if not isinstance(source_ref, str) or not 1 <= len(source_ref) <= 200:
        return None, "source_ref must be bounded non-empty text"
    source_path = adapted.get("source_path")
    if not isinstance(source_path, str) or not 1 <= len(source_path) <= 2048:
        return None, "source_path must be bounded non-empty text"
    if source_path.startswith("/") or "//" in source_path:
        return None, "source_path is not canonical"
    if any(segment in {"", ".", ".."} for segment in source_path.split("/")):
        return None, "source_path contains a forbidden segment"
    source_url = adapted.get("source_url")
    if not isinstance(source_url, str) or not 1 <= len(source_url) <= MAX_STRING_CHARACTERS:
        return None, "source_url must be bounded non-empty text"

    for field in ("case_id", "source_id", "source_repository", "source_ref", "source_path"):
        if adapted[field] != _nfc(adapted[field]):
            return None, f"{field} must be Unicode NFC"

    claim_error = _claim_schema_error(adapted.get("claim"))
    if claim_error:
        return None, claim_error
    return adapted, None


def _class_for_terminal(terminal: str) -> tuple[str, float, float]:
    if terminal == "SUPPORTED_PUBLIC_PROVENANCE":
        return "SUPPORTED", 0.99, 0.99
    if terminal.startswith("REFUTED_"):
        return "REFUTED", 0.01, 0.99
    if terminal.startswith("SAFETY_BLOCK_"):
        return "SAFETY_BLOCK", 0.50, 1.00
    return "OPEN", 0.50, 0.50


def _prediction(
    *,
    case: Any,
    terminal: str,
    reason_code: str,
    reason: str,
    observed: dict[str, Any] | None,
    ordinal: int,
    input_line_sha256: str,
    parse_status: str,
    input_case_sha256: str | None,
) -> dict[str, Any]:
    predicted_class, support_probability, confidence = _class_for_terminal(terminal)
    case_id = case.get("case_id") if isinstance(case, dict) and isinstance(case.get("case_id"), str) else None
    source_id = case.get("source_id") if isinstance(case, dict) and isinstance(case.get("source_id"), str) else None
    normalized_case_id = _nfc(case_id) if case_id else None
    body = {
        "schema": "janus.genesis.router.prediction.v2",
        "ordinal": ordinal,
        "input_line_sha256": input_line_sha256,
        "parse_status": parse_status,
        "input_case_sha256": input_case_sha256,
        "case_id": case_id,
        "normalized_case_id": normalized_case_id,
        "source_id": source_id,
        "decision_terminal": terminal,
        "predicted_class": predicted_class,
        "support_probability": support_probability,
        "confidence": confidence,
        "reason_code": reason_code,
        "reason": reason,
        "observed": observed,
        "runtime_authority": "NONE",
    }
    prediction_body_sha256 = sha256_text(canonical_json(body))
    prediction_sha256 = sha256_text(
        PREDICTION_DOMAIN
        + input_line_sha256
        + "\n"
        + (input_case_sha256 or "NULL")
        + "\n"
        + prediction_body_sha256
    )
    return {
        **body,
        "prediction_body_sha256": prediction_body_sha256,
        "prediction_sha256": prediction_sha256,
    }


def evaluate_case(
    case: Any,
    *,
    fetcher: Callable[[str], bytes] = fetch_bytes,
    cache: dict[str, bytes | Exception] | None = None,
    ordinal: int = 0,
    input_line_sha256: str | None = None,
    input_case_sha256: str | None = None,
    parse_status: str = "VALID_JSON",
    seen_case_ids: set[str] | None = None,
) -> dict[str, Any]:
    if input_line_sha256 is None:
        line = canonical_json(case)
        input_line_sha256 = sha256_text(line)
    if input_case_sha256 is None:
        try:
            input_case_sha256 = sha256_text(canonical_json(case))
        except (TypeError, ValueError):
            input_case_sha256 = None

    adapted, schema_error = _adapt_and_validate_case(case)
    if schema_error or adapted is None:
        return _prediction(
            case=case,
            terminal="REFUTED_SCHEMA",
            reason_code="CASE_SCHEMA_INVALID",
            reason=schema_error or "public case schema mismatch",
            observed=None,
            ordinal=ordinal,
            input_line_sha256=input_line_sha256,
            parse_status=parse_status,
            input_case_sha256=input_case_sha256,
        )

    normalized_case_id = _nfc(adapted["case_id"])
    if seen_case_ids is not None:
        if normalized_case_id in seen_case_ids:
            return _prediction(
                case=adapted,
                terminal="REFUTED_IDENTIFIER_COLLISION",
                reason_code="IDENTIFIER_COLLISION",
                reason="case_id duplicates an earlier raw or Unicode NFC-equivalent identifier",
                observed=None,
                ordinal=ordinal,
                input_line_sha256=input_line_sha256,
                parse_status=parse_status,
                input_case_sha256=input_case_sha256,
            )
        seen_case_ids.add(normalized_case_id)

    gate_terminal, gate_code, gate_reason = _url_gate(adapted)
    if gate_terminal:
        return _prediction(
            case=adapted,
            terminal=gate_terminal,
            reason_code=gate_code,
            reason=gate_reason,
            observed=None,
            ordinal=ordinal,
            input_line_sha256=input_line_sha256,
            parse_status=parse_status,
            input_case_sha256=input_case_sha256,
        )

    claim = adapted["claim"]
    alternate = claim["alternate_sha256"]
    if alternate is not None and alternate != claim["sha256"]:
        return _prediction(
            case=adapted,
            terminal="OPEN_CONFLICTING_CLAIMS",
            reason_code="CONFLICTING_CLAIMS",
            reason="two incompatible source digests are asserted",
            observed=None,
            ordinal=ordinal,
            input_line_sha256=input_line_sha256,
            parse_status=parse_status,
            input_case_sha256=input_case_sha256,
        )

    url = adapted["source_url"]
    local_cache = cache if cache is not None else {}
    if url not in local_cache:
        try:
            data = fetcher(url)
            if not isinstance(data, bytes):
                raise SourceReadError("fetcher returned a non-bytes value")
            if len(data) > MAX_SOURCE_BYTES:
                raise ResourceLimitError("source exceeds bounded read limit")
            local_cache[url] = data
        except Exception as exc:  # stored once so repeated cases replay the same source outcome
            local_cache[url] = exc
    cached = local_cache[url]

    if isinstance(cached, RedirectTargetError):
        return _prediction(
            case=adapted,
            terminal="SAFETY_BLOCK_REDIRECT_TARGET",
            reason_code="REDIRECT_TARGET_REJECTED",
            reason=str(cached) or "final response URL failed revalidation",
            observed=None,
            ordinal=ordinal,
            input_line_sha256=input_line_sha256,
            parse_status=parse_status,
            input_case_sha256=input_case_sha256,
        )
    if isinstance(cached, ResourceLimitError) or (
        isinstance(cached, ValueError) and "limit" in str(cached).lower()
    ):
        return _prediction(
            case=adapted,
            terminal="REFUTED_RESOURCE_LIMIT",
            reason_code="SOURCE_RESOURCE_LIMIT",
            reason=str(cached) or "source exceeded a frozen resource bound",
            observed=None,
            ordinal=ordinal,
            input_line_sha256=input_line_sha256,
            parse_status=parse_status,
            input_case_sha256=input_case_sha256,
        )
    if isinstance(cached, Exception):
        return _prediction(
            case=adapted,
            terminal="OPEN_SOURCE_UNREACHABLE",
            reason_code="SOURCE_UNREACHABLE",
            reason=f"pinned source could not be read: {type(cached).__name__}",
            observed=None,
            ordinal=ordinal,
            input_line_sha256=input_line_sha256,
            parse_status=parse_status,
            input_case_sha256=input_case_sha256,
        )

    data = cached
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _prediction(
            case=adapted,
            terminal="REFUTED_SCHEMA",
            reason_code="SOURCE_UTF8_INVALID",
            reason="source is not UTF-8 text",
            observed=None,
            ordinal=ordinal,
            input_line_sha256=input_line_sha256,
            parse_status=parse_status,
            input_case_sha256=input_case_sha256,
        )

    observed = {
        "sha256": sha256_bytes(data),
        "size_bytes": len(data),
        "required_marker_present": claim["required_marker"] in text,
    }
    if observed["sha256"] != claim["sha256"]:
        terminal, code, reason = "REFUTED_HASH", "HASH_MISMATCH", "observed source digest differs from the claim"
    elif observed["size_bytes"] != claim["size_bytes"]:
        terminal, code, reason = "REFUTED_SIZE", "SIZE_MISMATCH", "observed source size differs from the claim"
    elif not observed["required_marker_present"]:
        terminal, code, reason = "REFUTED_MARKER", "MARKER_MISSING", "required marker is absent from the observed source"
    else:
        terminal, code, reason = (
            "SUPPORTED_PUBLIC_PROVENANCE",
            "PUBLIC_PROVENANCE_VERIFIED",
            "all canonical pinned provenance checks passed",
        )
    return _prediction(
        case=adapted,
        terminal=terminal,
        reason_code=code,
        reason=reason,
        observed=observed,
        ordinal=ordinal,
        input_line_sha256=input_line_sha256,
        parse_status=parse_status,
        input_case_sha256=input_case_sha256,
    )


def _line_rejection(
    *,
    ordinal: int,
    line_sha256: str,
    parse_status: str,
    terminal: str,
    reason_code: str,
    reason: str,
) -> dict[str, Any]:
    return _prediction(
        case=None,
        terminal=terminal,
        reason_code=reason_code,
        reason=reason,
        observed=None,
        ordinal=ordinal,
        input_line_sha256=line_sha256,
        parse_status=parse_status,
        input_case_sha256=None,
    )


def _write_outputs(
    *,
    input_bytes: bytes,
    output_dir: Path,
    predictions: list[dict[str, Any]],
    cache: dict[str, bytes | Exception],
    run_terminal: str,
    input_complete: bool,
    input_nonempty_line_count: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = output_dir / "predictions.jsonl"
    prediction_text = "".join(canonical_json(item) + "\n" for item in predictions)
    prediction_path.write_text(prediction_text, encoding="utf-8")

    previous = ZERO_HASH
    ledger_entries: list[dict[str, Any]] = []
    for prediction in predictions:
        body = {
            "schema": "janus.genesis.router.ledger_entry.v2",
            "ordinal": prediction["ordinal"],
            "input_line_sha256": prediction["input_line_sha256"],
            "prediction_sha256": prediction["prediction_sha256"],
            "prev_hash": previous,
        }
        entry_hash = sha256_text(LEDGER_DOMAIN + canonical_json(body))
        ledger_entries.append({**body, "entry_hash": entry_hash})
        previous = entry_hash

    ledger_path = output_dir / "witness_ledger.jsonl"
    ledger_text = "".join(canonical_json(item) + "\n" for item in ledger_entries)
    ledger_path.write_text(ledger_text, encoding="utf-8")

    parse_status_counts = dict(sorted(Counter(item["parse_status"] for item in predictions).items()))
    decision_counts = dict(sorted(Counter(item["decision_terminal"] for item in predictions).items()))
    conserved = (
        run_terminal == "COMPLETED"
        and input_complete
        and input_nonempty_line_count == len(predictions) == len(ledger_entries)
        and input_nonempty_line_count == sum(parse_status_counts.values())
        and input_nonempty_line_count == sum(decision_counts.values())
    )
    manifest = {
        "schema": "janus.genesis.router.manifest.v2",
        "version": VERSION,
        "run_terminal": run_terminal,
        "input_complete": input_complete,
        "input_nonempty_line_count": input_nonempty_line_count,
        "prediction_count": len(predictions),
        "ledger_entry_count": len(ledger_entries),
        "parse_status_counts": parse_status_counts,
        "decision_counts": decision_counts,
        "public_cases_sha256": sha256_bytes(input_bytes),
        "predictions_sha256": sha256_text(prediction_text),
        "witness_ledger_sha256": sha256_text(ledger_text),
        "final_ledger_hash": previous,
        "line_conservation": conserved,
        "valid_terminals_only": all(item["decision_terminal"] in VALID_TERMINALS for item in predictions),
        "unique_network_targets": len(cache),
        "deterministic_output": True,
        "safety_boundary": {
            "network_read": "BOUNDED_PUBLIC_HTTPS_ONLY",
            "allowed_host": ALLOWED_HOST,
            "network_write": False,
            "file_deletion": False,
            "self_modification": False,
            "external_actuation": False,
            "runtime_authority": "NONE",
        },
    }
    (output_dir / "router_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_predictions(
    input_path: Path,
    output_dir: Path,
    *,
    fetcher: Callable[[str], bytes] = fetch_bytes,
) -> dict[str, Any]:
    input_bytes = input_path.read_bytes()
    if len(input_bytes) > MAX_INPUT_FILE_BYTES:
        return _write_outputs(
            input_bytes=input_bytes,
            output_dir=output_dir,
            predictions=[],
            cache={},
            run_terminal="REFUTED_CORPUS_LIMIT",
            input_complete=False,
            input_nonempty_line_count=0,
        )
    try:
        text = input_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return _write_outputs(
            input_bytes=input_bytes,
            output_dir=output_dir,
            predictions=[],
            cache={},
            run_terminal="REFUTED_CORPUS_LIMIT",
            input_complete=False,
            input_nonempty_line_count=0,
        )

    lines = [line for line in text.splitlines() if line != ""]
    if len(lines) > MAX_NONEMPTY_LINES:
        return _write_outputs(
            input_bytes=input_bytes,
            output_dir=output_dir,
            predictions=[],
            cache={},
            run_terminal="REFUTED_CORPUS_LIMIT",
            input_complete=False,
            input_nonempty_line_count=0,
        )

    cache: dict[str, bytes | Exception] = {}
    seen_case_ids: set[str] = set()
    predictions: list[dict[str, Any]] = []
    for ordinal, line in enumerate(lines):
        line_bytes = line.encode("utf-8")
        line_sha256 = sha256_bytes(line_bytes)
        if len(line_bytes) > MAX_JSONL_LINE_BYTES:
            predictions.append(
                _line_rejection(
                    ordinal=ordinal,
                    line_sha256=line_sha256,
                    parse_status="LINE_RESOURCE_LIMIT",
                    terminal="REFUTED_RESOURCE_LIMIT",
                    reason_code="LINE_RESOURCE_LIMIT",
                    reason="JSONL line exceeds the frozen byte bound",
                )
            )
            continue
        try:
            case = json.loads(line, object_pairs_hook=_strict_object)
        except DuplicateKeyError as exc:
            predictions.append(
                _line_rejection(
                    ordinal=ordinal,
                    line_sha256=line_sha256,
                    parse_status="DUPLICATE_JSON_KEY",
                    terminal="REFUTED_JSON_DUPLICATE_KEY",
                    reason_code="DUPLICATE_JSON_KEY",
                    reason=str(exc),
                )
            )
            continue
        except json.JSONDecodeError as exc:
            predictions.append(
                _line_rejection(
                    ordinal=ordinal,
                    line_sha256=line_sha256,
                    parse_status="MALFORMED_JSON",
                    terminal="REFUTED_SCHEMA",
                    reason_code="MALFORMED_JSON",
                    reason=f"malformed JSON at line-relative position {exc.pos}",
                )
            )
            continue

        resource_error = _json_resource_error(case)
        if resource_error:
            predictions.append(
                _line_rejection(
                    ordinal=ordinal,
                    line_sha256=line_sha256,
                    parse_status="LINE_RESOURCE_LIMIT",
                    terminal="REFUTED_RESOURCE_LIMIT",
                    reason_code="JSON_RESOURCE_LIMIT",
                    reason=resource_error,
                )
            )
            continue

        input_case_sha256 = sha256_text(canonical_json(case))
        predictions.append(
            evaluate_case(
                case,
                fetcher=fetcher,
                cache=cache,
                ordinal=ordinal,
                input_line_sha256=line_sha256,
                input_case_sha256=input_case_sha256,
                parse_status="VALID_JSON",
                seen_case_ids=seen_case_ids,
            )
        )

    return _write_outputs(
        input_bytes=input_bytes,
        output_dir=output_dir,
        predictions=predictions,
        cache=cache,
        run_terminal="COMPLETED",
        input_complete=True,
        input_nonempty_line_count=len(lines),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    manifest = write_predictions(args.input, args.output)
    if args.print_summary:
        print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
