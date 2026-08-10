#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

OFFWORLD = "MOTHERSHIP_ZETA_OFFWORLD"
CROSS_WORLD = "POINT_LOOKOUT_CROSS_WORLDSPACE"
QUEST_GATED = "BROKEN_STEEL_QUEST_GATED"
EXPLICIT_EDGE = "EXPLICIT_JAMES_PLACEMENT_EDGE"
PRE_JAMES_B_OBSERVABLE = "PRE_JAMES_B_OBSERVABLE"
DYNAMIC_AFTER_JAMES_B = "DYNAMIC_AFTER_JAMES_B_EDGE"
EXACT_REFR_BOUND = "EXACT_REFR_BOUND"
LIFECYCLE_BOUND = "REFR_LIFECYCLE_BOUND"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def as_set(obj):
    if isinstance(obj, dict):
        if "locations" in obj:
            obj = obj["locations"]
        else:
            obj = list(obj.keys())
    if not isinstance(obj, list):
        raise ValueError("route ledger must be a list or object containing locations")
    return {str(x) for x in obj}


def _flag(scene, tag, field):
    return tag in set(scene.get("tags", [])) or scene.get(field) is True


def evaluate(scenes, james_a_route, james_b_route=None):
    if not isinstance(scenes, list):
        raise ValueError("scene ledger must be a JSON array")
    a_route = as_set(james_a_route)
    b_route = as_set(james_b_route or [])

    explicit = []
    a_overlap = []
    b_overlap = []
    offworld = []
    cross_world = []
    quest_gated = []
    missing_location = []
    pre_b_observable = []
    dynamic_after_b = []
    temporal_candidates = []
    source_bound_temporal_falsifiers = []

    for scene in scenes:
        sid = scene.get("scene_id") or scene.get("name") or "UNKNOWN_SCENE"
        loc = scene.get("location_key")
        tags = set(scene.get("tags", []))
        if not loc:
            missing_location.append(sid)
        else:
            if loc in a_route:
                a_overlap.append(sid)
            if loc in b_route:
                b_overlap.append(sid)

        if OFFWORLD in tags:
            offworld.append(sid)
        if CROSS_WORLD in tags:
            cross_world.append(sid)
        if QUEST_GATED in tags:
            quest_gated.append(sid)
        if EXPLICIT_EDGE in tags or scene.get("explicit_james_placement_edge") is True:
            explicit.append(sid)

        pre = _flag(scene, PRE_JAMES_B_OBSERVABLE, "pre_james_b_observable")
        dynamic = _flag(scene, DYNAMIC_AFTER_JAMES_B, "dynamic_after_james_b_edge")
        exact_ref = _flag(scene, EXACT_REFR_BOUND, "exact_refid_bound")
        lifecycle = _flag(scene, LIFECYCLE_BOUND, "lifecycle_bound")

        if pre:
            pre_b_observable.append(sid)
        if dynamic:
            dynamic_after_b.append(sid)
        if pre and not dynamic:
            temporal_candidates.append(sid)
            if exact_ref and lifecycle:
                source_bound_temporal_falsifiers.append(sid)

    all_scene_ids = [s.get("scene_id") or s.get("name") or "UNKNOWN_SCENE" for s in scenes]
    all_a_overlap = bool(all_scene_ids) and len(a_overlap) == len(all_scene_ids)
    all_b_overlap = bool(all_scene_ids) and len(b_overlap) == len(all_scene_ids)

    if explicit:
        bounded_subset = "SUPPORTED_FOR_EXPLICIT_EDGE_SCENES_ONLY"
    else:
        bounded_subset = "NOT_ESTABLISHED"

    # Route coverage never promotes authorship. Lack of explicit placement evidence
    # keeps the single-placer hypothesis unestablished even under 100% overlap.
    single_placer = "NOT_ESTABLISHED"

    if source_bound_temporal_falsifiers:
        h2 = "TEMPORALLY_FALSIFIED_IN_SOURCE_BOUND_TESTED_SCENES"
    elif temporal_candidates:
        h2 = "TEMPORAL_FALSIFIER_CANDIDATE_PENDING_EXACT_REFR_LIFECYCLE_BINDING"
    else:
        h2 = "CONDITIONALLY_TESTABLE_NOT_VANILLA_EVIDENCE"

    return {
        "schema": "janus.genesis.janus_bear.james_placer_evaluation.v2",
        "scene_count": len(scenes),
        "missing_location_key_count": len(missing_location),
        "james_a_route_overlap_count": len(a_overlap),
        "james_a_route_overlap_fraction": (len(a_overlap) / len(scenes)) if scenes else None,
        "james_b_experimental_overlap_count": len(b_overlap),
        "james_b_experimental_overlap_fraction": (len(b_overlap) / len(scenes)) if scenes else None,
        "all_scenes_on_james_a_route": all_a_overlap,
        "all_scenes_on_james_b_experimental_route": all_b_overlap,
        "offworld_scene_count": len(offworld),
        "cross_worldspace_scene_count": len(cross_world),
        "quest_gated_scene_count": len(quest_gated),
        "explicit_james_placement_edge_count": len(explicit),
        "explicit_james_placement_scenes": explicit,
        "pre_james_b_observable_scene_count": len(pre_b_observable),
        "dynamic_after_james_b_scene_count": len(dynamic_after_b),
        "temporal_falsifier_candidate_count": len(temporal_candidates),
        "source_bound_temporal_falsifier_count": len(source_bound_temporal_falsifiers),
        "single_placer_status": single_placer,
        "bounded_subset_status": bounded_subset,
        "hypothesis_status": {
            "H1_JAMES_A_ALL": "WEAK_NOT_SUPPORTED" if not explicit else "NOT_ESTABLISHED_DESPITE_BOUNDED_EDGE",
            "H2_JAMES_B_ALL": h2,
            "H3_JAMES_SUBSET": bounded_subset,
            "H0_DEVELOPER_GRAMMAR_PLUS_LOCAL_HISTORIES": "REMAINS_DEFAULT_UNLESS_STRONGER_INDEPENDENT_EVIDENCE"
        },
        "diagnostics": {
            "james_a_route_overlap_scenes": a_overlap,
            "james_b_experimental_overlap_scenes": b_overlap,
            "offworld_scenes": offworld,
            "cross_worldspace_scenes": cross_world,
            "quest_gated_scenes": quest_gated,
            "missing_location_scenes": missing_location,
            "pre_james_b_observable_scenes": pre_b_observable,
            "dynamic_after_james_b_scenes": dynamic_after_b,
            "temporal_falsifier_candidates": temporal_candidates,
            "source_bound_temporal_falsifiers": source_bound_temporal_falsifiers
        },
        "claim_ceiling": {
            "route_overlap_proves_placement": False,
            "semantic_fit_proves_placement": False,
            "james_b_route_is_vanilla_evidence": False,
            "offworld_access_is_free": False,
            "single_placer_proven": False,
            "bounded_positive_attribution_requires_explicit_edge": True,
            "pre_james_b_observable_alone_proves_static_lifecycle": False,
            "temporal_falsification_requires_exact_refid_and_lifecycle_binding": True,
            "dynamic_after_james_b_edge_can_defeat_preexistence_inference": True,
            "retrocausality_allowed": False
        }
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", type=Path, required=True)
    ap.add_argument("--james-a-route", type=Path, required=True)
    ap.add_argument("--james-b-route", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    result = evaluate(
        load_json(args.scenes),
        load_json(args.james_a_route),
        load_json(args.james_b_route) if args.james_b_route else None,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
