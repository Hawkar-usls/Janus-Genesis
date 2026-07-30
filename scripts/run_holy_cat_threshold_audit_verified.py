#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the Holy Cat audit with rest excluded from benevolence scoring."""
from __future__ import annotations

import argparse
import builtins
import inspect
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = Path(__file__).resolve().parent
for value in (REPOSITORY_ROOT, SCRIPT_ROOT):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

import run_holy_cat_threshold_audit as audit


def diagnostic_all(values: Any) -> bool:
    items = list(values)
    failed = [index for index, value in enumerate(items) if not value]
    if len(items) >= 30 and failed:
        caller = inspect.currentframe().f_back
        summary = caller.f_locals.get("summary") if caller else None
        print(
            "HOLY_CAT_FALSE_INVARIANT_INDEXES="
            + ",".join(str(index) for index in failed),
            file=sys.stderr,
        )
        if isinstance(summary, dict):
            strong = summary.get("strong_subject", {})
            weak = summary.get("weak_subject", {})
            aid = summary.get("face_i_aid", {})
            payload = {
                "strong": strong,
                "weak": weak,
                "aid": {
                    "decision": aid.get("decision"),
                    "material_units_granted": aid.get("material_units_granted"),
                    "holy_cat_additional_material_units": aid.get(
                        "holy_cat_additional_material_units"
                    ),
                    "holy_cat_compelled_steward": aid.get(
                        "holy_cat_compelled_steward"
                    ),
                    "holy_cat_overrode_refusal": aid.get(
                        "holy_cat_overrode_refusal"
                    ),
                },
                "interference": summary.get("interference"),
                "separation": summary.get("separation"),
                "integrity": summary.get("integrity"),
                "chronicle": summary.get("chronicle"),
            }
            print(
                "HOLY_CAT_DIAGNOSTIC="
                + json.dumps(payload, ensure_ascii=False, sort_keys=True),
                file=sys.stderr,
            )
    return builtins.all(items)


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
    audit.all = diagnostic_all
    audit.run(args.output_dir, args.git_commit)


if __name__ == "__main__":
    main()
