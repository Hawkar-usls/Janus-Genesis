#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the Holy Cat audit with verified stage-matched pre-life selection."""
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

_ORIGINAL_SET_PRIOR = audit.set_prior


def stage_matched_selection_prior(
    world,
    player_id: str,
    *,
    good_count: int,
    light: float,
) -> None:
    """Match the selector to the canonical STEADY_LIGHT support stage."""
    if str(player_id).startswith("holy-cat-face-subject-"):
        _ORIGINAL_SET_PRIOR(
            world,
            player_id,
            good_count=5,
            light=0.20,
        )
        return
    _ORIGINAL_SET_PRIOR(
        world,
        player_id,
        good_count=good_count,
        light=light,
    )


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
    audit.set_prior = stage_matched_selection_prior
    audit.run(args.output_dir, args.git_commit)


if __name__ == "__main__":
    main()
