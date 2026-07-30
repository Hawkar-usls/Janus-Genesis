#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the Holy Cat audit with benevolence actions distinct from baseline rest."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
for value in (REPOSITORY_ROOT, SCRIPT_ROOT):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

import run_holy_cat_threshold_audit as audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    audit.BENEVOLENT_ACTIONS = tuple(
        (
            "создать безопасное место восстановления без долга и требования полезности"
            if action
            == "подарить отдых человеку который устал доказывать полезность"
            else action
        )
        for action in audit.BENEVOLENT_ACTIONS
    )
    audit.run(args.output_dir, args.git_commit)


if __name__ == "__main__":
    main()
