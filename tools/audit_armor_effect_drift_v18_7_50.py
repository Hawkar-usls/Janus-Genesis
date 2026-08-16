# -*- coding: utf-8 -*-
"""AST drift canary for JANUS Armor effect-capable Python surfaces.

This is a source-level inventory guard, not a sandbox.  It detects direct use of
selected network/process primitives and requires the containing production file
to live in an explicitly classified adapter/service set.  A new direct effect
surface therefore fails CI until it is reviewed and classified.

Tests, examples and this auditor itself are excluded because they are not
production effect entrypoints.  Classification does not mean "safe" or
"armored"; several allowlisted legacy surfaces are intentionally classified as
unarmored and remain migration debt.
"""
from __future__ import annotations

import ast
import fnmatch
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIRECT_EFFECT_CALLS = {
    "urllib.request.urlopen",
    "http.client.HTTPConnection",
    "http.client.HTTPSConnection",
    "socket.socket",
    "socket.create_connection",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "os.system",
    "os.popen",
}

# Classification is intentionally explicit.  It does NOT certify these files.
CLASSIFIED_EFFECT_SURFACE_PATTERNS = (
    "genesis_v18_7_ai.py",
    "genesis_v18_7_38_durable_network_outbox.py",
    "tools/genesis_third_wish_*.py",
    "tools/genesis_api_server.py",
    "tools/genesis_hosted_gateway.py",
    "tools/genesis_network_hub.py",
    "tools/bootstrap_genesis_hosted.py",
)

EXCLUDED_PATTERNS = (
    "tests/*",
    "test_*",
    "examples/*",
    "tools/audit_armor_effect_drift_v18_7_50.py",
)


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def excluded(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in EXCLUDED_PATTERNS)


def classified(path: str) -> bool:
    return any(
        fnmatch.fnmatch(path, pattern)
        for pattern in CLASSIFIED_EFFECT_SURFACE_PATTERNS
    )


def scan(path: Path) -> list[dict[str, object]]:
    rel = path.relative_to(ROOT).as_posix()
    if excluded(rel):
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    rows: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = dotted(node.func)
        if name in DIRECT_EFFECT_CALLS:
            rows.append(
                {
                    "path": rel,
                    "line": int(getattr(node, "lineno", 0)),
                    "call": name,
                    "classified": classified(rel),
                }
            )
    return rows


def main() -> int:
    findings: list[dict[str, object]] = []
    for path in sorted(ROOT.rglob("*.py")):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        findings.extend(scan(path))

    unclassified = [row for row in findings if not row["classified"]]
    by_path: dict[str, list[str]] = {}
    for row in findings:
        by_path.setdefault(str(row["path"]), []).append(str(row["call"]))

    report = {
        "schema": "janus.genesis.armor.effect_surface_drift.v1",
        "runtime_version": "18.7.50",
        "detected_surface_count": len(by_path),
        "classified_surface_count": len(
            {str(row["path"]) for row in findings if row["classified"]}
        ),
        "unclassified_surface_count": len(
            {str(row["path"]) for row in unclassified}
        ),
        "surfaces": {
            path: sorted(set(calls)) for path, calls in sorted(by_path.items())
        },
        "unclassified": unclassified,
        "classification_is_security_certification": False,
        "classified_legacy_surface_is_armored_by_classification_alone": False,
        "claim_ceiling": (
            "This AST canary detects selected direct network/process primitives and "
            "fails on newly unclassified production files. It does not prove absence "
            "of all side effects, dynamic execution, native-code effects, or bypass."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if unclassified else 0


if __name__ == "__main__":
    raise SystemExit(main())
