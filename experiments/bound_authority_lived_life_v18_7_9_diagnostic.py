# -*- coding: utf-8 -*-
"""Clean reporting wrapper for the Bound Authority lived-life final seal."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import experiments.bound_authority_lived_life_v18_7_9 as lived


def clean_check_tuple(result: Any) -> dict[str, Any]:
    if not isinstance(result, (tuple, list)):
        return {"valid": bool(result), "count": None, "aux_count": None, "error": None}
    valid = bool(result[0]) if result else False
    count = result[1] if len(result) > 1 else None
    third = result[2] if len(result) > 2 else None
    if isinstance(third, str) or third is None:
        return {"valid": valid, "count": count, "aux_count": None, "error": third}
    return {"valid": valid, "count": count, "aux_count": third, "error": None}


def main() -> None:
    lived._check_tuple = clean_check_tuple
    audit = lived.LivedAudit(
        Path(".bound-authority-lived-work"),
        Path("artifacts/bound_authority_lived_life"),
    )
    try:
        audit.run()
    except AssertionError:
        diagnostics = {
            "chronicle": clean_check_tuple(audit.world.verify_chronicle_records()),
            "possibility_graph": clean_check_tuple(audit.world.verify_possibility_graph()),
            "free_other": clean_check_tuple(audit.world.verify_free_other_state()),
            "bound_authority": clean_check_tuple(audit.world.verify_bound_authority_state()),
        }
        print("FINAL_VERIFIER_DIAGNOSTICS=" + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
        raise


if __name__ == "__main__":
    main()
