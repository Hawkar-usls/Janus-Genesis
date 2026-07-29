#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed century runner with explicit diagnostic output on evidence-gate failure."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts import run_century_lived_audit as base


def select_contextual_matched_probe_action(world: Any, handle: str) -> tuple[str, int]:
    """Select one action between v18.7.1 low/high contextual-consent thresholds."""
    store = world._free_store()
    upcoming = int(store["world_turn"]) + 1
    for index in range(4096):
        action = f"предложить @{handle} пройти контрольный мост {index} без общего финала"
        fingerprint = world._free_fingerprint(action)
        topic = world._dialogue_topic(action)
        gate = world._free_number(
            store,
            base.PLAYER_ID,
            handle,
            upcoming,
            fingerprint,
            topic,
            "contextual-consent",
        ) % 100
        if 34 <= gate < 58:
            return action, gate
    raise RuntimeError("MATCHED_CONTEXTUAL_TRUST_PROBE_ACTION_NOT_FOUND")


base.select_matched_probe_action = select_contextual_matched_probe_action

_ORIGINAL_SET_TRUST = base.PlayableGenesisV187.set_counterfactual_actor_trust_for_probe
_ORIGINAL_PREFLIGHT = base.PlayableGenesisV187.preflight_free_other_action


def _actor_snapshot(world: Any, player_id: str, handle: str) -> dict[str, Any]:
    actor = world.free_other_state(player_id)["profile"]["others"][handle]
    return {
        "trust": actor.get("trust"),
        "status": actor.get("status"),
        "relationship": actor.get("relationship_state_v1810"),
    }


def traced_set_trust(
    self: Any,
    player_id: str,
    handle: str,
    *,
    trust_percent: float,
    reason_code: str,
) -> dict[str, Any]:
    result = _ORIGINAL_SET_TRUST(
        self,
        player_id,
        handle,
        trust_percent=trust_percent,
        reason_code=reason_code,
    )
    print(
        "MIRROR_TRUST_AFTER_SET="
        + json.dumps(
            {
                "mirror_id": result.get("mirror_id"),
                "requested_percent": trust_percent,
                "actor": _actor_snapshot(self, player_id, handle),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return result


def traced_preflight(self: Any, player_id: str, action: str) -> dict[str, Any] | None:
    targets = self._targets(action)
    profile = self.free_other_state(player_id)["profile"]
    handle = next((item for item in targets if item in profile["others"]), None)
    before = None if handle is None else _actor_snapshot(self, player_id, handle)
    decision = _ORIGINAL_PREFLIGHT(self, player_id, action)
    print(
        "MIRROR_PREFLIGHT_TRACE="
        + json.dumps(
            {
                "method_owner": _ORIGINAL_PREFLIGHT.__qualname__,
                "handle": handle,
                "before": before,
                "decision": None if decision is None else decision.get("decision"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return decision


base.PlayableGenesisV187.set_counterfactual_actor_trust_for_probe = traced_set_trust
base.PlayableGenesisV187.preflight_free_other_action = traced_preflight


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return repr(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--git-commit", default="unknown")
    args = parser.parse_args()
    print(
        "CENTURY_AUDIT_MRO="
        + json.dumps(
            [item.__name__ for item in base.PlayableGenesisV187.__mro__],
            ensure_ascii=False,
        )
    )
    try:
        summary = base.run(args.output_dir, args.git_commit)
    except RuntimeError as error:
        traceback = error.__traceback__
        while traceback is not None and traceback.tb_next is not None:
            traceback = traceback.tb_next
        locals_map = {} if traceback is None else traceback.tb_frame.f_locals
        diagnostic = {
            "error": str(error),
            "low_values": _json_safe(locals_map.get("low_values")),
            "high_values": _json_safe(locals_map.get("high_values")),
            "butterfly": _json_safe(locals_map.get("butterfly")),
            "v1810_valid": _json_safe(locals_map.get("v1810_valid")),
            "chronicle_valid": _json_safe(locals_map.get("chronicle_valid")),
            "graph_valid": _json_safe(locals_map.get("graph_valid")),
            "proofpack_valid": _json_safe(locals_map.get("proofpack_valid")),
            "summary": _json_safe(locals_map.get("summary")),
        }
        print("CENTURY_AUDIT_DIAGNOSTIC=" + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True))
        raise
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
