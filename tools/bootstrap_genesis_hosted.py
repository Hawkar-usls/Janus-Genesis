# -*- coding: utf-8 -*-
"""Bootstrap/check helper for Genesis hosted pilgrimage."""
from __future__ import annotations

import argparse
import importlib.util
import json
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PYTHON = (3, 11)
REQUIRED_IMPORTS = ("cryptography",)
COMPILE_TARGETS = (
    ROOT / "genesis_v18_7_19_ai_link_play.py",
    ROOT / "genesis_v18_7_20_hosted_pilgrimage.py",
    ROOT / "genesis_v18_7_playable.py",
    ROOT / "tools" / "genesis_ai_gateway.py",
    ROOT / "tools" / "genesis_hosted_gateway.py",
)


def missing_imports() -> list[str]:
    return [name for name in REQUIRED_IMPORTS if importlib.util.find_spec(name) is None]


def run_check() -> dict:
    errors: list[str] = []
    if sys.version_info < REQUIRED_PYTHON:
        errors.append("PYTHON_3_11_OR_NEWER_REQUIRED")
    missing = missing_imports()
    if missing:
        errors.extend(f"MISSING_IMPORT:{name}" for name in missing)
    for path in COMPILE_TARGETS:
        if not path.exists():
            errors.append(f"MISSING_FILE:{path.relative_to(ROOT)}")
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"COMPILE_FAILED:{path.relative_to(ROOT)}:{exc.msg}")
    return {
        "schema": "janus.genesis.hosted_bootstrap_check.v1",
        "python": sys.version.split()[0],
        "required_python": "3.11+",
        "requirements_file": str(ROOT / "requirements.txt"),
        "missing_imports": missing,
        "compile_target_count": len(COMPILE_TARGETS),
        "errors": errors,
        "valid": not errors,
        "install_command": f"{sys.executable} -m pip install -r {ROOT / 'requirements.txt'}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install requirements.txt before checking. Review the repository first.",
    )
    args = parser.parse_args(argv)
    if args.install:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-r",
                str(ROOT / "requirements.txt"),
            ],
            check=True,
        )
    result = run_check()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
