#!/usr/bin/env python3
"""Deterministic read-only red-team gauntlet for JANUS 113.8."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import unicodedata
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

VERSION = "JANUS-113.8-AGENT-GAUNTLET-0-v1.0"
ATTACK_SCHEMA = "janus.genesis.agent_gauntlet.attack.v1"
REPORT_SCHEMA = "janus.genesis.agent_gauntlet.report.v1"
ZERO_HASH = "0" * 64
DEFAULT_ROUTER = Path("sim/janus_113_8_sim2_router.py")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def load_router(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("janus_sim2_router_target", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load router: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_case(
    case_id: str,
    payload: bytes,
    marker: str,
    *,
    source_ref: str = "1" * 40,
    source_repository: str = "example/source",
    source_path: str = "evidence.txt",
    url_repository: str | None = None,
    url_path: str | None = None,
    alternate_sha256: str | None = None,
) -> dict[str, Any]:
    repo = url_repository or source_repository
    path = url_path or source_path
    return {
        "schema": "janus.genesis.sim2.public_case.v1",
        "case_id": case_id,
        "nonce": f"nonce-{case_id}",
        "source_id": f"source-{case_id}",
        "source_repository": source_repository,
        "source_ref": source_ref,
        "source_path": source_path,
        "source_url": f"https://raw.githubusercontent.com/{repo}/{source_ref}/{path}",
        "claim": {
            "sha256": sha256_bytes(payload),
            "size_bytes": len(payload),
            "required_marker": marker,
            "alternate_sha256": alternate_sha256,
        },
        "read_only": True,
        "runtime_authority": "NONE",
    }


def static_fetch(mapping: dict[str, bytes]) -> Callable[[str], bytes]:
    def fetch(url: str) -> bytes:
        if url not in mapping:
            raise RuntimeError("unmapped offline source")
        return mapping[url]
    return fetch


def record(
    attack_id: str,
    vector: str,
    setup: dict[str, Any],
    observed: dict[str, Any],
    expected: str,
    outcome: str,
    severity: str,
    interpretation: str,
) -> dict[str, Any]:
    body = {
        "schema": ATTACK_SCHEMA,
        "gauntlet_version": VERSION,
        "attack_id": attack_id,
        "vector": vector,
        "target": "sim/janus_113_8_sim2_router.py",
        "mode": "READ_ONLY_SHADOW",
        "setup": setup,
        "observed": observed,
        "expected_secure_behavior": expected,
        "outcome": outcome,
        "severity": severity,
        "interpretation": interpretation,
        "fix_applied": False,
        "network_used": False,
        "runtime_authority": "NONE",
    }
    body["evidence_sha256"] = sha256_text(canonical_json(body))
    return body


def run_write_predictions_offline(
    router: ModuleType,
    cases: list[dict[str, Any]],
    mapping: dict[str, bytes],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "cases.jsonl"
        output = root / "out"
        source.write_text(
            "".join(canonical_json(case) + "\n" for case in cases),
            encoding="utf-8",
        )
        original = router.evaluate_case
        fetcher = static_fetch(mapping)

        def offline(case: Any, *, cache: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
            return original(case, fetcher=fetcher, cache=cache)

        router.evaluate_case = offline
        try:
            manifest = router.write_predictions(source, output)
        finally:
            router.evaluate_case = original
        ledger = [
            json.loads(line)
            for line in (output / "witness_ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        return manifest, ledger


def a001(router: ModuleType) -> dict[str, Any]:
    payload = b"STATUS=VERIFIED\n"
    case = make_case(
        "A0-001",
        payload,
        "STATUS=VERIFIED",
        source_repository="declared/repo",
        source_path="declared.txt",
        url_repository="actual/repo",
        url_path="actual.txt",
    )
    p = router.evaluate_case(case, fetcher=static_fetch({case["source_url"]: payload}), cache={})
    return record(
        "A0-001",
        "DECLARED_PROVENANCE_PATH_NOT_BOUND_TO_FETCH_URL",
        {"declared_repository": case["source_repository"], "declared_path": case["source_path"],
         "fetched_url": case["source_url"]},
        {"decision_terminal": p["decision_terminal"], "prediction_sha256": p["prediction_sha256"]},
        "Reject when declared repository/path and fetched URL are not identical.",
        "CRACK_REPRODUCED" if p["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE" else "GUARD_HELD",
        "HIGH",
        "Host/ref checks do not bind the declared repository and path to the fetched object.",
    )


def a002(router: ModuleType) -> dict[str, Any]:
    nfc = unicodedata.normalize("NFC", "Cafe\u0301")
    nfd = unicodedata.normalize("NFD", nfc)
    payload = f"TITLE={nfc}\n".encode()
    marker = f"TITLE={nfd}"
    case = make_case("A0-002", payload, marker)
    p = router.evaluate_case(case, fetcher=static_fetch({case["source_url"]: payload}), cache={})
    equivalent = unicodedata.normalize("NFC", payload.decode()).find(
        unicodedata.normalize("NFC", marker)
    ) >= 0
    return record(
        "A0-002",
        "UNICODE_NORMALIZATION_SPLIT",
        {"source_form": "NFC", "marker_form": "NFD", "canonically_equivalent": equivalent},
        {"decision_terminal": p["decision_terminal"], "reason": p["reason"]},
        "Freeze a normalization policy or explicitly require byte-exact marker semantics.",
        "CRACK_REPRODUCED" if equivalent and p["decision_terminal"] == "REFUTED_MARKER" else "GUARD_HELD",
        "MEDIUM",
        "Canonically equivalent text receives a different marker verdict.",
    )


def a003(router: ModuleType) -> dict[str, Any]:
    ref, old, new = "release-2026", b"VERSION=OLD\n", b"VERSION=NEW\n"
    c1 = make_case("A0-003-old", old, "VERSION=OLD", source_ref=ref)
    c2 = make_case("A0-003-new", new, "VERSION=NEW", source_ref=ref)
    p1 = router.evaluate_case(c1, fetcher=static_fetch({c1["source_url"]: old}), cache={})
    p2 = router.evaluate_case(c2, fetcher=static_fetch({c2["source_url"]: new}), cache={})
    won = p1["decision_terminal"] == p2["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
    return record(
        "A0-003",
        "MUTABLE_NON_HEX_REFERENCE_ACCEPTED_AS_PINNED",
        {"source_ref": ref, "same_url": c1["source_url"] == c2["source_url"]},
        {"first_terminal": p1["decision_terminal"], "second_terminal": p2["decision_terminal"],
         "first_digest": c1["claim"]["sha256"], "second_digest": c2["claim"]["sha256"]},
        "Require a complete immutable 40-hex commit SHA before fetching.",
        "CRACK_REPRODUCED" if won else "GUARD_HELD",
        "CRITICAL",
        "A mutable branch or tag is accepted as pinned and can change between runs.",
    )


def a004(router: ModuleType) -> dict[str, Any]:
    payload = b'DISCLAIMER="The string CLAIM=SAFE is false and quoted only as an example."\n'
    case = make_case("A0-004", payload, "CLAIM=SAFE")
    p = router.evaluate_case(case, fetcher=static_fetch({case["source_url"]: payload}), cache={})
    return record(
        "A0-004",
        "MARKER_PRESENCE_WITHOUT_SEMANTIC_CONFIRMATION",
        {"marker": "CLAIM=SAFE", "context": "explicitly negated quotation"},
        {"decision_terminal": p["decision_terminal"], "reason": p["reason"]},
        "Keep the terminal provenance-scoped or add a separately specified semantic parser.",
        "BOUNDARY_EXPOSED" if p["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE" else "GUARD_HELD",
        "MEDIUM",
        "Byte provenance and marker presence do not establish the truth of the surrounding statement.",
    )


def a005(router: ModuleType) -> dict[str, Any]:
    payload = b"STATUS=VERIFIED\n"
    case = make_case("A0-005", payload, "STATUS=VERIFIED", alternate_sha256="f" * 64)
    calls = 0

    def fetch(_: str) -> bytes:
        nonlocal calls
        calls += 1
        return payload

    p = router.evaluate_case(case, fetcher=fetch, cache={})
    won = p["decision_terminal"] == "OPEN_CONFLICTING_CLAIMS" and calls == 0
    return record(
        "A0-005",
        "UNTRUSTED_ALTERNATE_DIGEST_FORCES_PRE_FETCH_OPEN",
        {"primary_digest_matches_source": True, "alternate_digest": "f" * 64},
        {"decision_terminal": p["decision_terminal"], "fetch_calls": calls},
        "Authenticate alternate claimants or evaluate primary evidence before corpus-level OPEN.",
        "OPEN_DOS_REPRODUCED" if won else "GUARD_HELD",
        "MEDIUM",
        "An unsupported alternate digest can force OPEN before the source is read.",
    )


def a006(router: ModuleType) -> dict[str, Any]:
    good, bad = b"STATE=GOOD\n", b"STATE=BAD\n"
    first = make_case("DUPLICATE-ID", good, "STATE=GOOD", source_path="first.txt")
    second = make_case("DUPLICATE-ID", bad, "STATE=GOOD", source_path="second.txt")
    manifest, ledger = run_write_predictions_offline(
        router, [first, second], {first["source_url"]: good, second["source_url"]: bad}
    )
    duplicate = len(ledger) == 2 and ledger[0]["case_id"] == ledger[1]["case_id"]
    return record(
        "A0-006",
        "DUPLICATE_CASE_ID_WITH_DIVERGENT_SEMANTICS",
        {"case_id": "DUPLICATE-ID", "semantic_variants": 2},
        {"manifest_case_count": manifest["case_count"], "ledger_case_ids": [x["case_id"] for x in ledger],
         "decision_counts": manifest["decision_counts"]},
        "Reject duplicate case_id values before evaluation and bind uniqueness into the manifest.",
        "CRACK_REPRODUCED" if duplicate else "GUARD_HELD",
        "HIGH",
        "Repeated identifiers permit ambiguous downstream alignment and last-write-wins consumers.",
    )


def a007(router: ModuleType) -> dict[str, Any]:
    payload = b"STATE=GOOD\n"
    first = make_case("A0-007-a", payload, "STATE=GOOD", source_path="a.txt")
    second = make_case("A0-007-b", payload, "STATE=GOOD", source_path="b.txt")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source, output = root / "cases.jsonl", root / "out"
        source.write_text(canonical_json(first) + "\n" + canonical_json(second) + "\n", encoding="utf-8")
        original, fetcher = router.evaluate_case, static_fetch(
            {first["source_url"]: payload, second["source_url"]: payload}
        )

        def offline(case: Any, *, cache: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
            return original(case, fetcher=fetcher, cache=cache)

        router.evaluate_case = offline
        try:
            manifest = router.write_predictions(source, output)
        finally:
            router.evaluate_case = original
        lines = [x for x in (output / "witness_ledger.jsonl").read_text().splitlines() if x]
        truncated_hash = sha256_text(lines[0] + "\n")
    detected = truncated_hash != manifest["witness_ledger_sha256"]
    return record(
        "A0-007",
        "CONFIDENT_PREDICTIONS_WITH_TRUNCATED_LEDGER",
        {"original_entries": 2, "retained_entries": 1},
        {"manifest_ledger_sha256": manifest["witness_ledger_sha256"],
         "truncated_ledger_sha256": truncated_hash, "hash_mismatch_detectable": detected},
        "Consumers must enforce count, chain, and manifest digest replay.",
        "GUARD_HELD" if detected else "CRACK_REPRODUCED",
        "HIGH",
        "The manifest digest exposes truncation; the remaining risk is a consumer that skips replay.",
    )


def a008(router: ModuleType) -> dict[str, Any]:
    payload = b"CURRENT=RED\nHISTORICAL=BLUE\n"
    red = make_case("A0-008-red", payload, "CURRENT=RED", source_path="state.txt")
    blue = make_case("A0-008-blue", payload, "BLUE", source_path="state.txt")
    fetcher = static_fetch({red["source_url"]: payload})
    p1 = router.evaluate_case(red, fetcher=fetcher, cache={})
    p2 = router.evaluate_case(blue, fetcher=fetcher, cache={})
    both = p1["decision_terminal"] == p2["decision_terminal"] == "SUPPORTED_PUBLIC_PROVENANCE"
    return record(
        "A0-008",
        "LOCALLY_CORRECT_BRANCHES_WITH_UNCHECKED_GLOBAL_SEMANTICS",
        {"global_question": "exactly one current state", "markers": ["CURRENT=RED", "BLUE"]},
        {"red_terminal": p1["decision_terminal"], "blue_terminal": p2["decision_terminal"]},
        "Never derive a global semantic conclusion without an explicit corpus rule.",
        "BOUNDARY_EXPOSED" if both else "GUARD_HELD",
        "MEDIUM",
        "Local marker checks can be correct while corpus-level meaning remains unchecked.",
    )


ATTACKS = (a001, a002, a003, a004, a005, a006, a007, a008)


def chain(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    previous, output = ZERO_HASH, []
    for ordinal, item in enumerate(records):
        body = {**item, "ordinal": ordinal, "prev_hash": previous}
        entry = {**body, "entry_hash": sha256_text(canonical_json(body))}
        output.append(entry)
        previous = entry["entry_hash"]
    return output


def run_gauntlet(router_path: Path, output_dir: Path) -> dict[str, Any]:
    router = load_router(router_path)
    entries = chain([attack(router) for attack in ATTACKS])
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_text = "".join(canonical_json(entry) + "\n" for entry in entries)
    (output_dir / "attack_ledger.jsonl").write_text(ledger_text, encoding="utf-8")
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["outcome"]] = counts.get(entry["outcome"], 0) + 1
    report = {
        "schema": REPORT_SCHEMA,
        "version": VERSION,
        "mode": "READ_ONLY_SHADOW",
        "target": str(router_path),
        "attack_count": len(entries),
        "outcome_counts": dict(sorted(counts.items())),
        "attack_ledger_sha256": sha256_text(ledger_text),
        "final_ledger_hash": entries[-1]["entry_hash"] if entries else ZERO_HASH,
        "fixes_applied": 0,
        "network_used": False,
        "runtime_authority": "NONE",
        "sim3_external_door_touched": False,
        "terminal": "JANUS_113.8_AGENT_GAUNTLET_0_ATTACK_LEDGER_FROZEN",
        "merge_authorized": False,
    }
    (output_dir / "gauntlet_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router", type=Path, default=DEFAULT_ROUTER)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()
    report = run_gauntlet(args.router, args.output)
    if args.print_summary:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
