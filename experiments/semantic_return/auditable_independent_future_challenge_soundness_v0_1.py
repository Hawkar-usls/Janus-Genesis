#!/usr/bin/env python3
from __future__ import annotations
import itertools, json, math, random
from typing import Any

SCHEMA="AIFC/end-to-end-soundness-lab/v0.1.0"

def qmin(n:int,f:int)->int:
    return (n+f)//2+1

def grade(c:dict[str,Any])->dict[str,Any]:
    fail=[]
    gates=[
      ("PRE_RETURN_NOT_FROZEN", c["pre_frozen"]),
      ("TARGET_NOT_GENERATED_AFTER_FREEZE", c["target_after_freeze"]),
      ("ENTROPY_EVIDENCE_NOT_EXTERNAL", c["entropy_external"]),
      ("CAUSAL_ISOLATION_NOT_ESTABLISHED", c["dsep"]),
      ("TARGET_DERIVED_SIDEINFO_PRESENT", c["no_target_sideinfo"]),
      ("FRESHNESS_NOT_EXTERNAL", c["external_freshness"]),
      ("FAILURE_DOMAINS_NOT_INDEPENDENT", c["failure_domains_independent"]),
      ("POSTSELECTION_PRESENT", c["no_postselection"]),
    ]
    for name,ok in gates:
        if not ok: fail.append(name)
    if c["K"]<1: fail.append("INVALID_CANDIDATE_COUNT")
    if not (0<c["p"]<=1): fail.append("INVALID_PGUESS_CAP")
    qm=qmin(c["n"],c["f"])
    if c["q"]<qm: fail.append("UNSAFE_WITNESS_QUORUM")
    a=min(1.0,c["K"]*c["p"]) if c["K"]>=1 and c["p"]>0 else 1.0
    w=c.get("w",1.0)
    e=1.0+w*((1.0/a if c["hit"] else 0.0)-1.0)
    p_upper=min(1.0,1.0/e) if e>0 else 1.0
    admissible=(len(fail)==0)
    return {
      "admissible_forward_null_test":admissible,
      "failures":fail,
      "quorum_min":qm,
      "hit_cap":a,
      "e_value":e,
      "anytime_p_upper":p_upper,
      "forward_null_incompatibility_candidate": bool(admissible and c["hit"] and p_upper<=c["alpha"]),
      "physical_retrocausality_proved":False
    }

def base()->dict[str,Any]:
    return dict(
      pre_frozen=True,target_after_freeze=True,entropy_external=True,dsep=True,
      no_target_sideinfo=True,external_freshness=True,failure_domains_independent=True,
      no_postselection=True,K=1,p=2**-256,n=4,f=1,q=3,w=1.0,hit=False,alpha=0.05
    )

def run()->dict[str,Any]:
    cases={}
    b=base()
    cases["clean_null_no_hit"]=grade(b)

    h=dict(b);h["hit"]=True
    cases["forced_256bit_exact_hit_all_gates"]=grade(h)

    attacks={
      "prng_pregeneration":("target_after_freeze",False),
      "shared_seed_or_latent_common_cause":("dsep",False),
      "target_derived_commitment_before_freeze":("no_target_sideinfo",False),
      "entropy_self_attested":("entropy_external",False),
      "rollbackable_local_only_log":("external_freshness",False),
      "colluding_same_failure_domain_witnesses":("failure_domains_independent",False),
      "postselection":("no_postselection",False),
    }
    for name,(k,v) in attacks.items():
        c=dict(h);c[k]=v
        cases[name]=grade(c)

    c=dict(h);c["q"]=2
    cases["unsafe_2_of_4_quorum"]=grade(c)

    c=dict(h);c["K"]=4
    cases["four_candidate_multiplicity"]=grade(c)

    gate_keys=["pre_frozen","target_after_freeze","entropy_external","dsep",
               "no_target_sideinfo","external_freshness","failure_domains_independent","no_postselection"]
    single_gate_violations=0
    for k in gate_keys:
        c=dict(h);c[k]=False
        if grade(c)["admissible_forward_null_test"]:
            single_gate_violations+=1

    quorum_classification_violations=0
    configs=0
    for n in range(1,9):
        for f in range(0,n):
            for q in range(1,n+1):
                configs+=1
                comb=list(itertools.combinations(range(n),q))
                brute=True
                for A in comb:
                    A=set(A)
                    for B in comb:
                        if len(A.intersection(B))<=f:
                            brute=False;break
                    if not brute:break
                formula=(2*q>n+f)
                if brute!=formula: quorum_classification_violations+=1

    gate_assignments=0
    gate_assignment_admission_violations=0
    for bits in itertools.product([False,True], repeat=len(gate_keys)):
        c=dict(h)
        for k,v in zip(gate_keys,bits): c[k]=v
        g=grade(c)
        gate_assignments += 1
        expected=all(bits)
        if g["admissible_forward_null_test"] != expected:
            gate_assignment_admission_violations += 1

    checks={
      "clean_null_admitted":cases["clean_null_no_hit"]["admissible_forward_null_test"],
      "forced_exact_hit_is_forward_null_incompatibility_candidate":cases["forced_256bit_exact_hit_all_gates"]["forward_null_incompatibility_candidate"],
      "forced_exact_hit_is_not_physical_proof":not cases["forced_256bit_exact_hit_all_gates"]["physical_retrocausality_proved"],
      "all_single_gate_failures_fail_closed":single_gate_violations==0,
      "unsafe_quorum_rejected":"UNSAFE_WITNESS_QUORUM" in cases["unsafe_2_of_4_quorum"]["failures"],
      "candidate_multiplicity_counted":cases["four_candidate_multiplicity"]["hit_cap"]==4*(2**-256),
      "quorum_formula_exhaustive":quorum_classification_violations==0,
      "all_256_evidence_gate_assignments_fail_closed":gate_assignment_admission_violations==0,
    }
    return {
      "schema":SCHEMA,
      "status":"PASS" if all(checks.values()) else "FAIL",
      "all_pass":all(checks.values()),
      "checks":checks,
      "cases":cases,
      "exhaustive":{
        "single_gate_fail_closed_checks":len(gate_keys),
        "single_gate_admission_violations":single_gate_violations,
        "quorum_configurations":configs,
        "quorum_classification_violations":quorum_classification_violations,
        "evidence_gate_assignments":gate_assignments,
        "evidence_gate_assignment_admission_violations":gate_assignment_admission_violations
      },
      "theorem":{
        "name":"Auditable Independent-Future Challenge Soundness Theorem",
        "statement":"Let F_{i-1} be the complete pre-target information. Let C_i be fixed from F_{i-1}, |C_i|<=K_i, and let a_i=min(1,K_i p_i), where max_t P(T_i=t|F_{i-1})<=p_i under the admitted forward-causal null. If the evidence stack establishes post-freeze target generation, causal isolation, external entropy provenance, anti-rollback freshness, safe witness quorum, and no postselection, then any nonnegative test-supermartingale/e-process built from the hit indicators X_i=1[T_i in C_i] retains anytime-valid type-I control: P_0(sup_n E_n>=1/alpha)<=alpha.",
        "interpretation":"A threshold crossing rejects the specified forward-causal null-or-an-evidence-premise at level alpha. It is not by itself proof of retrocausality, FTL, a CTC, or a mechanism.",
        "novelty_boundary":"The component mathematics (conditional guessing bounds, d-separation, e-processes/Ville, secure logging and quorum intersection) is established. Candidate novelty is the end-to-end operational composition for auditable tests of pre-existing information about certified post-freeze random targets."
      }
    }

if __name__=="__main__":
    print(json.dumps(run(),indent=2,sort_keys=True))
