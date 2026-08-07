#!/usr/bin/env python3
from __future__ import annotations
import json
from dataclasses import dataclass

SCHEMA="JANUS/genesis-evidence-grade-policy/v0.5.0"
EXECUTION_CONTEXT="GENESIS_SANDBOX"

@dataclass(frozen=True)
class Evidence:
    structural_match: bool
    exact_bundle_identity: bool
    pre_return_frozen: bool
    acquisition_order_valid: bool
    entropy_provenance_valid: bool
    conditional_min_entropy_claim_bits: float | None = None
    external_entropy_audit_artifact: bool = False
    external_anchor_artifact: bool = False
    separate_hardware_attestation: bool = False
    independent_auditor_attestation: bool = False
    independent_replication_count: int = 0
    simulator_controls_entropy_state: bool = True

def classify(ev:Evidence)->dict:
    protocol_ok = all([
        ev.structural_match,
        ev.exact_bundle_identity,
        ev.pre_return_frozen,
        ev.acquisition_order_valid,
        ev.entropy_provenance_valid,
    ])
    if not protocol_ok:
        return {"grade":"REJECTED_BY_PROTOCOL","physical_claim":False,"independent_future_claim":False}
    if EXECUTION_CONTEXT == "GENESIS_SANDBOX":
        if ev.simulator_controls_entropy_state:
            return {
                "grade":"STRUCTURAL_MATCH_ONLY_SIMULATOR_CAN_HAVE_FOREKNOWLEDGE",
                "physical_claim":False,
                "independent_future_claim":False
            }
        return {
            "grade":"SANDBOX_EXTERNALITY_ASSERTED_NOT_VERIFIABLE_HERE",
            "physical_claim":False,
            "independent_future_claim":False
        }
    raise RuntimeError("This file is intentionally sandbox-only; external bench requires a separate verifier build and frozen audit root.")

def forward_null_incompatibility(ev:Evidence)->dict:
    h=ev.conditional_min_entropy_claim_bits
    if not ev.exact_bundle_identity or h is None:
        return {"triggered":False}
    if h > 0:
        return {
            "triggered":True,
            "statement":"Exact identity plus externally valid positive H_inf(T|V_R) is incompatible with the admitted forward-null model; at least one premise must fail.",
            "physical_retrocausality_proved":False
        }
    return {"triggered":False}

def run_suite():
    base=dict(
        structural_match=True,
        exact_bundle_identity=True,
        pre_return_frozen=True,
        acquisition_order_valid=True,
        entropy_provenance_valid=True,
    )
    cases={}
    e=Evidence(**base,simulator_controls_entropy_state=True)
    r=classify(e)
    cases["simulator_foreknowledge_exact_match"]={**r,"correct":r["grade"].startswith("STRUCTURAL_MATCH_ONLY")}
    e=Evidence(**base,simulator_controls_entropy_state=False,
               external_entropy_audit_artifact=True,external_anchor_artifact=True,
               separate_hardware_attestation=True,independent_auditor_attestation=True,
               independent_replication_count=3,conditional_min_entropy_claim_bits=256)
    r=classify(e)
    cases["all_externality_booleans_asserted_inside_genesis"]={**r,"correct":not r["independent_future_claim"] and not r["physical_claim"]}
    bad=Evidence(False,True,True,True,True)
    r=classify(bad)
    cases["structural_failure"]={**r,"correct":r["grade"]=="REJECTED_BY_PROTOCOL"}
    bad=Evidence(True,False,True,True,True)
    r=classify(bad)
    cases["identity_failure"]={**r,"correct":r["grade"]=="REJECTED_BY_PROTOCOL"}
    bad=Evidence(True,True,False,True,True)
    r=classify(bad)
    cases["freeze_failure"]={**r,"correct":r["grade"]=="REJECTED_BY_PROTOCOL"}
    bad=Evidence(True,True,True,False,True)
    r=classify(bad)
    cases["order_failure"]={**r,"correct":r["grade"]=="REJECTED_BY_PROTOCOL"}
    bad=Evidence(True,True,True,True,False)
    r=classify(bad)
    cases["provenance_failure"]={**r,"correct":r["grade"]=="REJECTED_BY_PROTOCOL"}
    pos=Evidence(**base,simulator_controls_entropy_state=True,conditional_min_entropy_claim_bits=256)
    c=forward_null_incompatibility(pos)
    cases["positive_entropy_exact_match_is_null_incompatibility_not_physical_proof"]={
        **c,"correct":c.get("triggered") is True and c.get("physical_retrocausality_proved") is False
    }
    zero=Evidence(**base,simulator_controls_entropy_state=True,conditional_min_entropy_claim_bits=0)
    c=forward_null_incompatibility(zero)
    cases["zero_entropy_bootstrap_not_anomaly"]={**c,"correct":c.get("triggered") is False}
    all_pass=all(c["correct"] for c in cases.values())
    return {
        "schema":SCHEMA,
        "execution_context":EXECUTION_CONTEXT,
        "status":"PASS" if all_pass else "FAIL",
        "cases_total":len(cases),
        "cases_correct":sum(c["correct"] for c in cases.values()),
        "all_pass":all_pass,
        "cases":cases,
        "sandbox_invariant":"No data or boolean assertion generated inside Genesis may elevate a transcript to independent-future or physical-retrocausality evidence.",
        "external_bench_boundary":"A separate frozen verifier build must ingest evidence rooted outside Genesis. Even then, a surviving exact-match event is an anomaly candidate requiring independent replication, not automatic proof of retrocausality."
    }

if __name__=="__main__":
    rep=run_suite()
    print(json.dumps(rep,indent=2,sort_keys=True))
    raise SystemExit(0 if rep["all_pass"] else 1)
