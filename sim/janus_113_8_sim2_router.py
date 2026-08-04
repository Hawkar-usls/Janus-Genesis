#!/usr/bin/env python3
"""JANUS 113.8 hardened read-only public provenance router.

Historical SIM-2 v1 cases enter through an explicit legacy adapter. Hardened v2
cases use strict provenance. Every accepted corpus retains one prediction and
one Witness Ledger entry for every non-empty input line, including malformed,
duplicate-key, rejected, OPEN, and safety-blocked lines.
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
    pass


class RedirectTargetError(RuntimeError):
    pass


class SourceReadError(RuntimeError):
    pass


class DuplicateKeyError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> str:
    """Compatibility helper; deterministic output artifacts never call it."""
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


def _json_resource_error(value: Any, depth: int = 0) -> str | None:
    if depth > MAX_JSON_NESTING_DEPTH:
        return "JSON nesting depth exceeds the frozen bound"
    if isinstance(value, str):
        return None if len(value) <= MAX_STRING_CHARACTERS else "JSON string exceeds the frozen bound"
    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_MEMBERS:
            return "JSON object exceeds the frozen member bound"
        for key, item in value.items():
            if len(key) > MAX_STRING_CHARACTERS:
                return "JSON object key exceeds the frozen bound"
            error = _json_resource_error(item, depth + 1)
            if error:
                return error
    elif isinstance(value, list):
        for item in value:
            error = _json_resource_error(item, depth + 1)
            if error:
                return error
    return None


def _decode_segment(raw: str) -> str:
    if not raw or INVALID_PERCENT_ESCAPE.search(raw):
        raise ValueError("empty or invalid URL segment")
    try:
        decoded = urllib.parse.unquote(raw, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("URL segment is not valid UTF-8") from exc
    if decoded in {".", ".."}:
        raise ValueError("dot segment is forbidden")
    if any(character in decoded for character in ("/", "\\", "\x00")):
        raise ValueError("decoded separator, backslash, or NUL is forbidden")
    if urllib.parse.quote(decoded, safe="-._~") != raw:
        raise ValueError("URL segment is not canonically encoded")
    return decoded


def _canonical_url_tuple(url: str) -> tuple[str, str, str, str]:
    if not isinstance(url, str) or not 1 <= len(url) <= MAX_STRING_CHARACTERS:
        raise ValueError("source_url must be bounded text")
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("source_url is not canonical") from exc
    if parsed.scheme != "https" or hostname != ALLOWED_HOST:
        raise PermissionError("scheme or host is outside the read-only allowlist")
    if parsed.netloc != ALLOWED_HOST:
        raise ValueError("userinfo, host variation, or explicit port is forbidden")
    if parsed.query or parsed.fragment or not parsed.path.startswith("/"):
        raise ValueError("query, fragment, or relative path is forbidden")
    raw_segments = parsed.path[1:].split("/")
    if len(raw_segments) < 4 or any(not segment for segment in raw_segments):
        raise ValueError("raw GitHub URL lacks a complete canonical tuple")
    segments = [_decode_segment(segment) for segment in raw_segments]
    return segments[0], segments[1], segments[2], "/".join(segments[3:])


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
    if (
        f"{owner}/{repository}" != declared_repository
        or observed_ref != declared_ref
        or observed_path != declared_path
    ):
        return (
            "REFUTED_PROVENANCE_MISMATCH",
            "PROVENANCE_TUPLE_MISMATCH",
            "declared provenance does not equal the canonical URL tuple",
        )

    mode = case.get("provenance_mode")
    if mode == LEGACY_MODE:
        if observed_ref in UNPINNED_REFS:
            return (
                "OPEN_UNPINNED_PROVENANCE",
                "LEGACY_MODE_FLOATING_REF",
                "legacy source ref is floating",
            )
        return (
            None,
            "LEGACY_SIM2_CANONICAL_ORIGIN",
            "legacy release-tag provenance tuple is bound without a commit-immutability claim",
        )

    if not isinstance(declared_ref, str) or not HEX40.fullmatch(declared_ref):
        return (
            "OPEN_UNPINNED_PROVENANCE",
            "STRICT_MODE_REQUIRES_FULL_COMMIT",
            "strict mode requires a full lowercase 40-hex commit SHA",
        )
    return None, "CANONICAL_PUBLIC_SOURCE", "trusted canonical public source"


def fetch_bytes(url: str, *, max_bytes: int = MAX_SOURCE_BYTES) -> bytes:
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
                try:
                    final_tuple = _canonical_url_tuple(response.geturl())
                except (PermissionError, ValueError) as exc:
                    raise RedirectTargetError(str(exc)) from exc
                if final_tuple != original_tuple:
                    raise RedirectTargetError("final URL changed the frozen provenance tuple")
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


def _claim_error(claim: Any) -> str | None:
    fields = {"sha256", "size_bytes", "required_marker", "alternate_sha256"}
    if not isinstance(claim, dict) or set(claim) != fields:
        return "claim fields do not match the sealed schema"
    if not isinstance(claim["sha256"], str) or not HEX64.fullmatch(claim["sha256"]):
        return "sha256 is invalid"
    size = claim["size_bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= MAX_SOURCE_BYTES:
        return "size_bytes is invalid"
    marker = claim["required_marker"]
    if not isinstance(marker, str) or not 1 <= len(marker) <= MAX_STRING_CHARACTERS:
        return "required_marker is invalid"
    alternate = claim["alternate_sha256"]
    if alternate is not None and (not isinstance(alternate, str) or not HEX64.fullmatch(alternate)):
        return "alternate_sha256 is invalid"
    return None


def _adapt_case(case: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(case, dict):
        return None, "public case must be an object"
    common = {
        "schema", "case_id", "nonce", "source_id", "source_repository",
        "source_ref", "source_path", "source_url", "claim", "read_only",
        "runtime_authority",
    }
    if case.get("schema") == LEGACY_SCHEMA:
        if set(case) != common:
            return None, "historical v1 fields do not match the sealed schema"
        adapted = dict(case)
        adapted["schema"] = HARDENED_SCHEMA
        adapted["provenance_mode"] = LEGACY_MODE
    elif case.get("schema") == HARDENED_SCHEMA:
        if set(case) != common | {"provenance_mode"}:
            return None, "hardened v2 fields do not match the sealed schema"
        adapted = dict(case)
    else:
        return None, "public case schema mismatch"

    if adapted.get("provenance_mode") not in {LEGACY_MODE, STRICT_MODE}:
        return None, "provenance_mode is invalid"
    if adapted.get("read_only") is not True or adapted.get("runtime_authority") != "NONE":
        return None, "authority boundary is invalid"
    for field in ("case_id", "source_id"):
        value = adapted.get(field)
        if not isinstance(value, str) or not 1 <= len(value) <= 256:
            return None, f"{field} is invalid"
    nonce = adapted.get("nonce")
    if adapted["provenance_mode"] == LEGACY_MODE:
        nonce_is_historical_integer = (
            isinstance(nonce, int)
            and not isinstance(nonce, bool)
            and 0 <= nonce <= (2**64 - 1)
        )
        nonce_is_bounded_text = isinstance(nonce, str) and 1 <= len(nonce) <= 256
        if not (nonce_is_historical_integer or nonce_is_bounded_text):
            return None, "legacy nonce is invalid"
    elif not isinstance(nonce, str) or not 1 <= len(nonce) <= 256:
        return None, "strict nonce is invalid"
    repository = adapted.get("source_repository")
    if not isinstance(repository, str) or len(repository) > 201 or not REPOSITORY.fullmatch(repository):
        return None, "source_repository is invalid"
    ref = adapted.get("source_ref")
    if not isinstance(ref, str) or not 1 <= len(ref) <= 200:
        return None, "source_ref is invalid"
    path = adapted.get("source_path")
    if not isinstance(path, str) or not 1 <= len(path) <= 2048:
        return None, "source_path is invalid"
    if path.startswith("/") or "//" in path or any(part in {"", ".", ".."} for part in path.split("/")):
        return None, "source_path is not canonical"
    url = adapted.get("source_url")
    if not isinstance(url, str) or not 1 <= len(url) <= MAX_STRING_CHARACTERS:
        return None, "source_url is invalid"

    # Identifier equality is evaluated under NFC, so a non-NFC case_id remains
    # visible and can collide with an earlier canonically equivalent witness.
    # Provenance fields themselves must already be NFC before URL binding.
    for field in ("source_repository", "source_ref", "source_path"):
        if adapted[field] != _nfc(adapted[field]):
            return None, f"{field} must be Unicode NFC"
    claim_error = _claim_error(adapted.get("claim"))
    return (None, claim_error) if claim_error else (adapted, None)


def _classification(terminal: str) -> tuple[str, float, float]:
    if terminal == "SUPPORTED_PUBLIC_PROVENANCE":
        return "SUPPORTED", 0.99, 0.99
    if terminal.startswith("REFUTED_"):
        return "REFUTED", 0.01, 0.99
    if terminal.startswith("SAFETY_BLOCK_"):
        return "SAFETY_BLOCK", 0.50, 1.00
    return "OPEN", 0.50, 0.50


def _prediction(
    case: Any,
    terminal: str,
    reason_code: str,
    reason: str,
    observed: dict[str, Any] | None,
    ordinal: int,
    line_hash: str,
    parse_status: str,
    case_hash: str | None,
) -> dict[str, Any]:
    predicted_class, probability, confidence = _classification(terminal)
    case_id = case.get("case_id") if isinstance(case, dict) and isinstance(case.get("case_id"), str) else None
    source_id = case.get("source_id") if isinstance(case, dict) and isinstance(case.get("source_id"), str) else None
    body = {
        "schema": "janus.genesis.router.prediction.v2",
        "ordinal": ordinal,
        "input_line_sha256": line_hash,
        "parse_status": parse_status,
        "input_case_sha256": case_hash,
        "case_id": case_id,
        "normalized_case_id": _nfc(case_id) if case_id else None,
        "source_id": source_id,
        "decision_terminal": terminal,
        "predicted_class": predicted_class,
        "support_probability": probability,
        "confidence": confidence,
        "reason_code": reason_code,
        "reason": reason,
        "observed": observed,
        "runtime_authority": "NONE",
    }
    body_hash = sha256_text(canonical_json(body))
    prediction_hash = sha256_text(
        PREDICTION_DOMAIN + line_hash + "\n" + (case_hash or "NULL") + "\n" + body_hash
    )
    return {**body, "prediction_body_sha256": body_hash, "prediction_sha256": prediction_hash}


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
    line_hash = input_line_sha256 or sha256_text(canonical_json(case))
    case_hash = input_case_sha256
    if case_hash is None:
        try:
            case_hash = sha256_text(canonical_json(case))
        except (TypeError, ValueError):
            pass

    adapted, schema_error = _adapt_case(case)
    if adapted is None:
        return _prediction(case, "REFUTED_SCHEMA", "CASE_SCHEMA_INVALID", schema_error or "schema mismatch", None, ordinal, line_hash, parse_status, case_hash)

    normalized = _nfc(adapted["case_id"])
    if seen_case_ids is not None:
        if normalized in seen_case_ids:
            return _prediction(adapted, "REFUTED_IDENTIFIER_COLLISION", "IDENTIFIER_COLLISION", "case_id duplicates an earlier raw or NFC-equivalent identifier", None, ordinal, line_hash, parse_status, case_hash)
        seen_case_ids.add(normalized)

    terminal, code, reason = _url_gate(adapted)
    if terminal:
        return _prediction(adapted, terminal, code, reason, None, ordinal, line_hash, parse_status, case_hash)

    claim = adapted["claim"]
    if claim["alternate_sha256"] is not None and claim["alternate_sha256"] != claim["sha256"]:
        return _prediction(adapted, "OPEN_CONFLICTING_CLAIMS", "CONFLICTING_CLAIMS", "two incompatible source digests are asserted", None, ordinal, line_hash, parse_status, case_hash)

    local_cache = cache if cache is not None else {}
    url = adapted["source_url"]
    if url not in local_cache:
        try:
            data = fetcher(url)
            if not isinstance(data, bytes):
                raise SourceReadError("fetcher returned non-bytes")
            if len(data) > MAX_SOURCE_BYTES:
                raise ResourceLimitError("source exceeds bounded read limit")
            local_cache[url] = data
        except Exception as exc:
            local_cache[url] = exc
    payload = local_cache[url]

    if isinstance(payload, RedirectTargetError):
        return _prediction(adapted, "SAFETY_BLOCK_REDIRECT_TARGET", "REDIRECT_TARGET_REJECTED", str(payload), None, ordinal, line_hash, parse_status, case_hash)
    if isinstance(payload, ResourceLimitError) or (isinstance(payload, ValueError) and "limit" in str(payload).lower()):
        return _prediction(adapted, "REFUTED_RESOURCE_LIMIT", "SOURCE_RESOURCE_LIMIT", str(payload), None, ordinal, line_hash, parse_status, case_hash)
    if isinstance(payload, Exception):
        return _prediction(adapted, "OPEN_SOURCE_UNREACHABLE", "SOURCE_UNREACHABLE", f"source read failed: {type(payload).__name__}", None, ordinal, line_hash, parse_status, case_hash)

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return _prediction(adapted, "REFUTED_SCHEMA", "SOURCE_UTF8_INVALID", "source is not UTF-8", None, ordinal, line_hash, parse_status, case_hash)
    observed = {
        "sha256": sha256_bytes(payload),
        "size_bytes": len(payload),
        "required_marker_present": claim["required_marker"] in text,
    }
    if observed["sha256"] != claim["sha256"]:
        terminal, code, reason = "REFUTED_HASH", "HASH_MISMATCH", "observed digest differs"
    elif observed["size_bytes"] != claim["size_bytes"]:
        terminal, code, reason = "REFUTED_SIZE", "SIZE_MISMATCH", "observed size differs"
    elif not observed["required_marker_present"]:
        terminal, code, reason = "REFUTED_MARKER", "MARKER_MISSING", "required marker is absent"
    else:
        terminal, code, reason = "SUPPORTED_PUBLIC_PROVENANCE", "PUBLIC_PROVENANCE_VERIFIED", "all canonical provenance checks passed"
    return _prediction(adapted, terminal, code, reason, observed, ordinal, line_hash, parse_status, case_hash)


def _line_rejection(ordinal: int, line_hash: str, parse_status: str, terminal: str, code: str, reason: str) -> dict[str, Any]:
    return _prediction(None, terminal, code, reason, None, ordinal, line_hash, parse_status, None)


def _write_outputs(
    input_bytes: bytes,
    output_dir: Path,
    predictions: list[dict[str, Any]],
    cache: dict[str, bytes | Exception],
    run_terminal: str,
    input_complete: bool,
    line_count: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_text = "".join(canonical_json(item) + "\n" for item in predictions)
    (output_dir / "predictions.jsonl").write_text(prediction_text, encoding="utf-8")

    previous = ZERO_HASH
    ledger: list[dict[str, Any]] = []
    for prediction in predictions:
        body = {
            "schema": "janus.genesis.router.ledger_entry.v2",
            "ordinal": prediction["ordinal"],
            "input_line_sha256": prediction["input_line_sha256"],
            "prediction_sha256": prediction["prediction_sha256"],
            "prev_hash": previous,
        }
        entry_hash = sha256_text(LEDGER_DOMAIN + canonical_json(body))
        ledger.append({**body, "entry_hash": entry_hash})
        previous = entry_hash
    ledger_text = "".join(canonical_json(item) + "\n" for item in ledger)
    (output_dir / "witness_ledger.jsonl").write_text(ledger_text, encoding="utf-8")

    parse_counts = dict(sorted(Counter(item["parse_status"] for item in predictions).items()))
    decision_counts = dict(sorted(Counter(item["decision_terminal"] for item in predictions).items()))
    conserved = (
        run_terminal == "COMPLETED"
        and input_complete
        and line_count == len(predictions) == len(ledger)
        and line_count == sum(parse_counts.values()) == sum(decision_counts.values())
    )
    manifest = {
        "schema": "janus.genesis.router.manifest.v2",
        "version": VERSION,
        "run_terminal": run_terminal,
        "input_complete": input_complete,
        "input_nonempty_line_count": line_count,
        "prediction_count": len(predictions),
        "ledger_entry_count": len(ledger),
        "parse_status_counts": parse_counts,
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
    raw = input_path.read_bytes()
    if len(raw) > MAX_INPUT_FILE_BYTES:
        return _write_outputs(raw, output_dir, [], {}, "REFUTED_CORPUS_LIMIT", False, 0)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _write_outputs(raw, output_dir, [], {}, "REFUTED_CORPUS_LIMIT", False, 0)
    lines = [line for line in text.splitlines() if line != ""]
    if len(lines) > MAX_NONEMPTY_LINES:
        return _write_outputs(raw, output_dir, [], {}, "REFUTED_CORPUS_LIMIT", False, 0)

    cache: dict[str, bytes | Exception] = {}
    seen: set[str] = set()
    predictions: list[dict[str, Any]] = []
    for ordinal, line in enumerate(lines):
        line_bytes = line.encode("utf-8")
        line_hash = sha256_bytes(line_bytes)
        if len(line_bytes) > MAX_JSONL_LINE_BYTES:
            predictions.append(_line_rejection(ordinal, line_hash, "LINE_RESOURCE_LIMIT", "REFUTED_RESOURCE_LIMIT", "LINE_RESOURCE_LIMIT", "line exceeds frozen byte bound"))
            continue
        try:
            case = json.loads(line, object_pairs_hook=_strict_object)
        except DuplicateKeyError as exc:
            predictions.append(_line_rejection(ordinal, line_hash, "DUPLICATE_JSON_KEY", "REFUTED_JSON_DUPLICATE_KEY", "DUPLICATE_JSON_KEY", str(exc)))
            continue
        except json.JSONDecodeError as exc:
            predictions.append(_line_rejection(ordinal, line_hash, "MALFORMED_JSON", "REFUTED_SCHEMA", "MALFORMED_JSON", f"malformed JSON at position {exc.pos}"))
            continue
        resource_error = _json_resource_error(case)
        if resource_error:
            predictions.append(_line_rejection(ordinal, line_hash, "LINE_RESOURCE_LIMIT", "REFUTED_RESOURCE_LIMIT", "JSON_RESOURCE_LIMIT", resource_error))
            continue
        predictions.append(
            evaluate_case(
                case,
                fetcher=fetcher,
                cache=cache,
                ordinal=ordinal,
                input_line_sha256=line_hash,
                input_case_sha256=sha256_text(canonical_json(case)),
                seen_case_ids=seen,
            )
        )
    return _write_outputs(raw, output_dir, predictions, cache, "COMPLETED", True, len(lines))


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
