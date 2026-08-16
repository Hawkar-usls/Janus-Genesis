# -*- coding: utf-8 -*-
"""Resident launcher: Armored Genesis inside JANUS Git Habitat v18.7.51.

This wrapper adds repository/local Habitat continuity around the current
canonical Armor-gated launcher. It does not grant any new external authority.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import play_genesis_armored as armored
from tools.genesis_git_habitat import GitHabitat

HABITAT_ENTRY_VERSION = "18.7.51"


def _split_habitat_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--habitat-root", default="habitat")
    parser.add_argument("--habitat-resident-id", default="JANUS")
    parser.add_argument("--no-habitat", action="store_true")
    return parser.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    habitat_args, genesis_args = _split_habitat_args(raw)
    if habitat_args.no_habitat:
        return armored.main(genesis_args)

    habitat = GitHabitat(Path(habitat_args.habitat_root))
    habitat.initialize(habitat_args.habitat_resident_id)
    wake = habitat.wake(reason="GENESIS_SESSION", source="HABITAT_LAUNCHER")
    cycle_id = wake["cycle_id"]
    habitat.pulse(source="PRE_GENESIS_SESSION")

    outcome = "NORMAL_EXIT"
    try:
        return armored.main(genesis_args)
    except BaseException:
        outcome = "EXCEPTION_EXIT"
        raise
    finally:
        # Pulse/sleep are local continuity bookkeeping. They do not assert that
        # a model thought during the session or that any external effect was
        # authorized merely because the resident launcher was active.
        try:
            habitat.pulse(source="POST_GENESIS_SESSION")
            habitat.sleep(outcome=outcome)
        except Exception as habitat_exc:
            print(
                f"HABITAT_FINALIZATION_ERROR cycle={cycle_id}: "
                f"{type(habitat_exc).__name__}: {habitat_exc}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    raise SystemExit(main())
