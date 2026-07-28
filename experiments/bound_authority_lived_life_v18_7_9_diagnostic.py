# -*- coding: utf-8 -*-
"""Diagnostic wrapper for the Bound Authority lived-life final seal."""
from __future__ import annotations

import json
from pathlib import Path

from experiments.bound_authority_lived_life_v18_7_9 import LivedAudit, _check_tuple


def main() -> None:
    audit = LivedAudit(
        Path(".bound-authority-lived-work"),
        Path("artifacts/bound_authority_lived_life"),
    )
    try:
        audit.run()
    except AssertionError:
        diagnostics = {
            "chronicle": _check_tuple(audit.world.verify_chronicle_records()),
            "possibility_graph": _check_tuple(audit.world.verify_possibility_graph()),
            "free_other": _check_tuple(audit.world.verify_free_other_state()),
            "bound_authority": _check_tuple(audit.world.verify_bound_authority_state()),
        }
        print("FINAL_VERIFIER_DIAGNOSTICS=" + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
