# -*- coding: utf-8 -*-
"""Scope audit for JANUS v18.7.57 authenticated API mutation authority.

Authentication answers who reached the API. It must not itself grant direct
access to raw PlayableGenesisV187 mutation methods. This audit checks the
cooperating HTTP API source is wired through the already-existing durable action
receipt runtime, typed auxiliary mutation authority, and recovery-safe save
import saga.

This is a source/CI scope audit, not a Python sandbox or repository-wide proof.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "tools" / "genesis_api_server.py"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    source = text(API)
    checks = {
        "action_receipt_runtime_bound": (
            "ReconciledPortableReceiptRuntimeAdapter" in source
            and "self.actions.execute(" in source
        ),
        "typed_name_mutation_bound": (
            "TypedAuxiliaryMutationAdapter" in source
            and "self.auxiliary.set_display_name(" in source
        ),
        "recovery_safe_import_bound": (
            "RecoverySafePortableSaveManager" in source
            and "import_bundle_recoverable(" in source
        ),
        "mutation_request_id_required": (
            "request_id is required for mutation" in source
            and "request_id = self._request_id(payload)" in source
        ),
        "request_state_endpoints_exist": all(
            marker in source
            for marker in (
                '"/v1/request/action"',
                '"/v1/request/mutation"',
                '"/v1/request/import"',
            )
        ),
        "raw_handler_process_action_removed": "self.server.world.process_action" not in source,
        "raw_handler_set_display_name_removed": "self.server.world.set_display_name" not in source,
        "raw_handler_import_bundle_removed": "self.server.saves.import_bundle(" not in source,
        "undetermined_is_not_auto_reexecuted": (
            '"automatic_reexecution_attempted": False' in source
            and "PortableRuntimeOutcomeUndetermined" in source
            and "TypedMutationOutcomeUndetermined" in source
        ),
        "successful_import_rebuilds_world_adapters": (
            "self._reload_world_control_plane()" in source
            and "import_bundle_recoverable(" in source
        ),
    }
    scope_pass = all(checks.values())
    report = {
        "schema": "janus.genesis.local_mutation_api_audit.v18_7_57",
        "runtime_version": "18.7.57",
        "scope": "AUTHENTICATED_HTTP_API_LOCAL_MUTATION_ROUTING",
        "checks": checks,
        "scope_pass": scope_pass,
        "canonical_laws": [
            "AUTHENTICATION != MUTATION_AUTHORITY",
            "MUTATION_REQUEST_ID_REQUIRED = TRUE",
            "ACTION -> RECONCILED_RECEIPT_RUNTIME",
            "DISPLAY_NAME -> TYPED_AUXILIARY_MUTATION_AUTHORITY",
            "SAVE_IMPORT -> RECOVERY_SAFE_ROLL_FORWARD_SAGA",
            "OUTCOME_UNDETERMINED != SAFE_TO_REEXECUTE",
            "REQUEST_ID + RECEIPT != NEW_PERMISSION",
        ],
        "remaining_local_mutation_debt": {
            "tools/genesis_ai_gateway.py": "SEPARATE_AI_LINK_LOCAL_MUTATION_SURFACE_REVIEW_REQUIRED",
            "tools/genesis_hosted_gateway.py": "SEPARATE_HOSTED_LOCAL_MUTATION_SURFACE_REVIEW_REQUIRED",
        },
        "arbitrary_python_raw_world_construction_prevented": False,
        "repository_wide_complete_routing_coverage_proven": False,
        "os_level_tamper_proof": False,
        "claim_ceiling": (
            "v18.7.57 routes the cooperating authenticated HTTP API's action, display-name, "
            "and save-import mutations through existing durable/typed/recovery-safe control "
            "mechanisms with stable request identifiers. It does not make authentication a "
            "permission oracle, does not prevent arbitrary Python from constructing the raw "
            "world, and does not yet close the AI or hosted gateway mutation surfaces."
        ),
        "next_gate": "AI_GATEWAY_MUTATION_AUTHORITY_THEN_HOSTED_GATEWAY_MUTATION_AUTHORITY",
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if scope_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
