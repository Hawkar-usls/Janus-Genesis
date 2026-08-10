#!/usr/bin/env python3
"""Admission layer for cross-specimen spectral replication receipts.

The AKAZE geometry heuristic is calibrated against the known Alatay same-specimen
positive control. If that validator rejects the known positive control, it is
invalidated and cannot be used to reject or promote an independent candidate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def admit(raw: dict) -> dict:
    pairs = raw.get("pairs", [])
    anchor = next((p for p in pairs if p.get("role") == "FROZEN_DISCOVERY_ANCHOR_NOT_REPLICATION"), None)
    if anchor is None:
        geometry_status = "NOT_EVALUABLE_NO_POSITIVE_CONTROL"
        geometry_usable = False
    else:
        anchor_geo = anchor.get("geometry_corroboration", {}).get("status")
        geometry_usable = anchor_geo == "IMAGE_GEOMETRY_SUPPORTS_SAME_SCENE"
        geometry_status = (
            "VALIDATED_ON_CONFIRMED_SAME_SPECIMEN_POSITIVE_CONTROL"
            if geometry_usable
            else "INVALIDATED_FALSE_NEGATIVE_ON_CONFIRMED_SAME_SPECIMEN_POSITIVE_CONTROL"
        )

    decisions = []
    formal = []
    candidates = []
    for p in pairs:
        pid = p.get("pair_id")
        if p.get("role") == "FROZEN_DISCOVERY_ANCHOR_NOT_REPLICATION":
            decision = "DISCOVERY_ANCHOR_EXCLUDED_FROM_REPLICATION_COUNT"
        elif p.get("replication_admission") == "ERROR_NOT_ADMITTED":
            decision = "ERROR_NOT_ADMITTED"
        else:
            observed = p.get("image_level_gate", {}).get("status") == "REGISTERED_MODALITY_DIFFERENCE_OBSERVED"
            provenance = p.get("same_specimen_status", "")
            if observed and provenance.startswith("CONFIRMED"):
                decision = "FORMAL_INDEPENDENT_SAME_SPECIMEN_IMAGE_LEVEL_REPLICATION"
                formal.append(pid)
            elif observed and provenance.startswith("PROBABLE"):
                decision = "IMAGE_LEVEL_MODALITY_DIFFERENCE_REPLICATION_CANDIDATE_PROVENANCE_UNCONFIRMED"
                candidates.append(pid)
            elif observed:
                decision = "IMAGE_LEVEL_MODALITY_DIFFERENCE_OBSERVED_IDENTITY_UNRESOLVED"
            else:
                decision = "REPLICATION_NOT_ESTABLISHED"

        decisions.append({
            "pair_id": pid,
            "role": p.get("role"),
            "same_specimen_status": p.get("same_specimen_status"),
            "registered_difference_status": p.get("image_level_gate", {}).get("status"),
            "geometry_raw_status": p.get("geometry_corroboration", {}).get("status"),
            "geometry_used_for_admission": geometry_usable,
            "planner_enrichment": p.get("planner_enrichment", {}).get("status"),
            "decision": decision,
        })

    planner_hits = [
        p.get("pair_id") for p in pairs
        if p.get("planner_enrichment", {}).get("status") == "SINGLE_PAIR_PLANNER_ENRICHMENT_CANDIDATE"
    ]
    return {
        "schema": "genesis.janus_cristal.spectral_replication_admission.v1",
        "artifact_id": "GENESIS-JANUS-CRISTAL-SPECTRAL-REPLICATION-ADMISSION-v0.1",
        "geometry_validator": {
            "status": geometry_status,
            "usable_for_admission": geometry_usable,
            "reason": "A necessary identity validator must accept the confirmed Alatay same-specimen positive control before it may be used on independent candidates."
        },
        "pair_decisions": decisions,
        "formal_independent_replications": formal,
        "formal_independent_replication_count": len(formal),
        "provenance_unconfirmed_image_level_candidates": candidates,
        "candidate_count": len(candidates),
        "planner_enrichment_pair_count": len(planner_hits),
        "planner_enrichment_pairs": planner_hits,
        "cross_specimen_replication_gate": "PASS" if formal else "OPEN_NOT_ESTABLISHED",
        "semantic_content_admitted": 0,
        "status": (
            "FORMAL_REPLICATION_ESTABLISHED" if formal
            else "IMAGE_LEVEL_CANDIDATE_ONLY_PROVENANCE_BLOCKS_FORMAL_REPLICATION" if candidates
            else "NO_INDEPENDENT_REPLICATION_CANDIDATE_ADMITTED"
        ),
        "formal_rules": [
            "A_VALIDATOR_THAT_FAILS_THE_POSITIVE_CONTROL_IS_NOT_ADMISSIBLE_AS_A_NECESSARY_GATE",
            "PROBABLE_SAME_SPECIMEN != CONFIRMED_SAME_SPECIMEN",
            "REGISTERED_MODALITY_DIFFERENCE != CHEMICAL_IDENTITY",
            "REGISTERED_MODALITY_DIFFERENCE != HIDDEN_MESSAGE",
            "FRACTALGPT_TRAJECTORY != MATERIAL_DISCOVERY",
            "NO_POST_HOC_REGION_OR_CIPHER_SEARCH"
        ]
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    result = admit(raw)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "formal": result["formal_independent_replication_count"],
        "candidates": result["candidate_count"],
        "geometry_validator": result["geometry_validator"]["status"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
