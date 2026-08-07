#!/usr/bin/env python3
from __future__ import annotations
from collections import defaultdict, deque
from itertools import combinations, product
import json
import math

SCHEMA = "JANUS/genesis-causal-isolation-dsep-lab/v0.1.0"
T = "target_hard_secret"
R = "pre_return_hard_view"
M = "allowed_public_metadata"

def ancestors(nodes, edges):
    parents = defaultdict(set)
    for a, b in edges:
        parents[b].add(a)
    out = set(nodes)
    stack = list(nodes)
    while stack:
        x = stack.pop()
        for p in parents[x]:
            if p not in out:
                out.add(p)
                stack.append(p)
    return out

def directed_path_exists(src, dst, edges):
    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
    q = deque([src])
    seen = {src}
    while q:
        x = q.popleft()
        if x == dst:
            return True
        for y in adj[x]:
            if y not in seen:
                seen.add(y)
                q.append(y)
    return False

def d_separated(x, y, conditioned, edges):
    """D-separation by ancestral moralization."""
    Z = set(conditioned)
    anc = ancestors({x, y} | Z, edges)
    und = defaultdict(set)
    parents = defaultdict(set)
    for a, b in edges:
        if a in anc and b in anc:
            und[a].add(b)
            und[b].add(a)
            parents[b].add(a)
    for _, ps in parents.items():
        ps = list(ps)
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                und[ps[i]].add(ps[j])
                und[ps[j]].add(ps[i])
    q = deque([x])
    seen = {x}
    while q:
        n = q.popleft()
        if n == y:
            return False
        for z in und[n]:
            if z in Z or z in seen:
                continue
            seen.add(z)
            q.append(z)
    return True

def remove_nodes(edges, removed):
    removed = set(removed)
    return [(a, b) for a, b in edges if a not in removed and b not in removed]

def minimal_removal_cuts(edges, removable):
    if d_separated(T, R, {M}, edges):
        return [()]
    removable = list(removable)
    for k in range(1, len(removable) + 1):
        cuts = []
        for c in combinations(removable, k):
            if d_separated(T, R, {M}, remove_nodes(edges, c)):
                cuts.append(c)
        if cuts:
            return cuts
    return []

def base_edges():
    return [
        ("entropy_noise", T),
        ("pre_noise", R),
        (M, "pre_public_fields"),
        (M, "target_public_fields"),
    ]

def scenario(name):
    e = base_edges()
    removable = set()
    attack_class = "NONE"
    if name == "clean":
        pass
    elif name == "rng_prefetch":
        e += [("entropy_noise", "rng_prefetch_buffer"), ("rng_prefetch_buffer", R)]
        removable |= {"rng_prefetch_buffer"}
        attack_class = "INFORMATION_DEPENDENCE"
    elif name == "shared_seed":
        e += [("shared_seed_state", T), ("shared_seed_state", "seed_exposure"), ("seed_exposure", R)]
        removable |= {"seed_exposure"}
        attack_class = "COMMON_CAUSE_INFORMATION_DEPENDENCE"
    elif name == "shared_memory":
        e += [("precomputed_future_secret", T), ("precomputed_future_secret", "shared_memory"), ("shared_memory", R)]
        removable |= {"shared_memory"}
        attack_class = "INFORMATION_DEPENDENCE"
    elif name == "filesystem_cache":
        e += [("prefetched_entropy", T), ("prefetched_entropy", "filesystem_cache"), ("filesystem_cache", R)]
        removable |= {"filesystem_cache"}
        attack_class = "INFORMATION_DEPENDENCE"
    elif name == "bootstrap_derivation":
        e += [(R, "target_derivation"), ("target_derivation", T)]
        removable |= {"target_derivation"}
        attack_class = "BOOTSTRAP_DEPENDENCE"
    elif name == "network_sidechannel":
        e += [("entropy_noise", "network_metadata"), ("network_metadata", R)]
        removable |= {"network_metadata"}
        attack_class = "INFORMATION_DEPENDENCE"
    elif name == "colluding_anchor_entropy":
        e += [("collusion_state", T), ("collusion_state", "anchor_private_state"), ("anchor_private_state", R)]
        removable |= {"anchor_private_state"}
        attack_class = "COMMON_CAUSE_INFORMATION_DEPENDENCE"
    elif name == "replay_seed_reuse":
        e += [("archived_seed", T), ("archived_seed", "snapshot_cache"), ("snapshot_cache", R)]
        removable |= {"snapshot_cache"}
        attack_class = "REPLAY_DEPENDENCE"
    elif name == "precommitted_target_sideinfo":
        e += [("precommitted_target", T), ("precommitted_target", "target_commitment_sideinfo"), ("target_commitment_sideinfo", R)]
        removable |= {"target_commitment_sideinfo"}
        attack_class = "PREGENERATION_SIDE_INFORMATION"
    elif name == "clock_only":
        e += [("shared_clock", "pre_timestamp"), ("shared_clock", "target_timestamp")]
        attack_class = "ORDERING_ONLY"
    elif name == "anchor_backdating_only":
        e += [("anchor_clock", "anchor_timestamp")]
        attack_class = "PROVENANCE_ONLY"
    elif name == "selection_collider":
        e += [(R, "selected_for_analysis"), (T, "selected_for_analysis")]
        attack_class = "SELECTION_COLLIDER"
    elif name == "public_metadata_common":
        attack_class = "ALLOWED_PUBLIC_COMMON_CAUSE"
    else:
        raise ValueError(name)
    return e, removable, attack_class

def binary_pguess(joint, condition_on_r=False, selection=None):
    rows = [(t,r,s,p) for t,r,s,p in joint if selection is None or s == selection]
    z = sum(p for *_, p in rows)
    rows = [(t,r,s,p/z) for t,r,s,p in rows] if z else []
    if not condition_on_r:
        probs = defaultdict(float)
        for t,r,s,p in rows:
            probs[t] += p
        return max(probs.values()) if probs else 0.0
    by_r = defaultdict(lambda: defaultdict(float))
    pr = defaultdict(float)
    for t,r,s,p in rows:
        by_r[r][t] += p
        pr[r] += p
    return sum(max(by_r[r].values()) for r in pr)

def exact_distribution_checks():
    indep = [(t,r,0,0.25) for t in (0,1) for r in (0,1)]
    shared = [(0,0,0,0.5),(1,1,0,0.5)]
    collider = [(t,r,int(t==r),0.25) for t in (0,1) for r in (0,1)]
    return {
        "clean_pguess_before_R": binary_pguess(indep, False),
        "clean_pguess_after_R": binary_pguess(indep, True),
        "shared_seed_pguess_before_R": binary_pguess(shared, False),
        "shared_seed_pguess_after_R": binary_pguess(shared, True),
        "selection_pguess_unconditioned": binary_pguess(collider, True),
        "selection_pguess_given_selected": binary_pguess(collider, True, selection=1),
    }

def parallel_cut_exhaustive():
    channels = [f"leak_{i}" for i in range(7)]
    checked = 0
    violations = 0
    cut_size_violations = 0
    max_paths = 0
    for bits in product([0,1], repeat=len(channels)):
        enabled = [c for c,b in zip(channels,bits) if b]
        e = base_edges()
        for c in enabled:
            root = f"latent_{c}"
            e += [(root,T),(root,c),(c,R)]
        iso = d_separated(T,R,{M},e)
        if iso != (len(enabled)==0):
            violations += 1
        cuts = minimal_removal_cuts(e, enabled)
        min_size = len(cuts[0]) if cuts else None
        expected = 0 if not enabled else len(enabled)
        if min_size != expected:
            cut_size_violations += 1
        checked += 1
        max_paths = max(max_paths, len(enabled))
    return {
        "subsets_checked": checked,
        "dseparation_classification_violations": violations,
        "minimum_channel_cut_size_violations": cut_size_violations,
        "max_parallel_leak_paths": max_paths,
        "pass": violations == 0 and cut_size_violations == 0,
    }

def parity_sideinfo_demo(bits=8):
    before = 1/(2**bits)
    after = 1/(2**(bits-1))
    return {
        "target_bits": bits,
        "pguess_before_sideinfo": before,
        "pguess_after_one_bit_sideinfo": after,
        "min_entropy_before_bits": bits,
        "min_entropy_after_bits": bits-1,
        "factor_increase_in_guessability": after/before,
    }

def run_suite():
    names = [
        "clean","rng_prefetch","shared_seed","shared_memory","filesystem_cache",
        "bootstrap_derivation","network_sidechannel","colluding_anchor_entropy",
        "replay_seed_reuse","precommitted_target_sideinfo",
        "clock_only","anchor_backdating_only","selection_collider","public_metadata_common"
    ]
    cases = {}
    for name in names:
        e, removable, attack_class = scenario(name)
        rec = {
            "attack_class": attack_class,
            "hard_target_dseparated_from_pre_return_given_public_metadata": d_separated(T,R,{M},e),
            "directed_target_to_pre_return_path": directed_path_exists(T,R,e),
            "directed_pre_return_to_target_path": directed_path_exists(R,T,e),
        }
        if removable:
            cuts = minimal_removal_cuts(e, removable)
            rec["minimal_declared_channel_cuts"] = [list(x) for x in cuts]
        if name == "selection_collider":
            rec["dseparated_without_selection"] = d_separated(T,R,{M},e)
            rec["dseparated_when_conditioning_on_selected_for_analysis"] = d_separated(T,R,{M,"selected_for_analysis"},e)
        cases[name] = rec

    distribution = exact_distribution_checks()
    parallel = parallel_cut_exhaustive()
    parity = parity_sideinfo_demo(8)

    checks = {
        "clean_is_dseparated": cases["clean"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "rng_prefetch_detected": not cases["rng_prefetch"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "shared_seed_detected_without_direct_target_to_return_path": (not cases["shared_seed"]["hard_target_dseparated_from_pre_return_given_public_metadata"] and not cases["shared_seed"]["directed_target_to_pre_return_path"]),
        "shared_memory_detected": not cases["shared_memory"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "filesystem_cache_detected": not cases["filesystem_cache"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "bootstrap_dependence_detected": not cases["bootstrap_derivation"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "network_sidechannel_detected": not cases["network_sidechannel"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "colluding_anchor_entropy_detected": not cases["colluding_anchor_entropy"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "replay_seed_reuse_detected": not cases["replay_seed_reuse"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "precommitted_target_sideinfo_detected": not cases["precommitted_target_sideinfo"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "clock_only_not_misclassified_as_bit_leak": cases["clock_only"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "anchor_backdating_not_misclassified_as_bit_leak": cases["anchor_backdating_only"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "selection_collider_opened_only_by_postselection": cases["selection_collider"]["dseparated_without_selection"] and not cases["selection_collider"]["dseparated_when_conditioning_on_selected_for_analysis"],
        "public_metadata_common_safe_for_hard_secret": cases["public_metadata_common"]["hard_target_dseparated_from_pre_return_given_public_metadata"],
        "clean_distribution_preserves_guessability": abs(distribution["clean_pguess_before_R"] - distribution["clean_pguess_after_R"]) < 1e-15,
        "shared_seed_doubles_binary_guessability_to_one": distribution["shared_seed_pguess_after_R"] == 1.0,
        "selection_can_raise_guessability_to_one": distribution["selection_pguess_given_selected"] == 1.0,
        "parallel_cut_exhaustive_pass": parallel["pass"],
        "one_bit_sideinfo_doubles_guessability": parity["factor_increase_in_guessability"] == 2.0,
    }
    all_pass = all(checks.values())

    return {
        "schema": SCHEMA,
        "status": "PASS" if all_pass else "FAIL",
        "checks_total": len(checks),
        "checks_passed": sum(bool(v) for v in checks.values()),
        "all_pass": all_pass,
        "checks": checks,
        "theorem": {
            "name": "JANUS Causal Isolation / D-Separation Gate",
            "statement": "In a correctly specified Markovian causal DAG, if the hard future target secret T is d-separated from the hard PRE_RETURN view R conditional on allowed public metadata M, then the global Markov property gives T independent of R given M. Consequently observing R cannot improve the optimal classical guessing probability of T beyond what M already permits, so p_guess(T|R,M)=p_guess(T|M) and H_min(T|R,M)=H_min(T|M).",
            "converse_boundary": "Failure of d-separation means structural independence is not certified; it does not by itself prove actual leakage because parameter cancellations may exist.",
            "model_boundary": "Passing d-separation proves isolation only inside the declared DAG plus its Markov/exogenous-independence assumptions. Software cannot prove that the physical DAG is complete.",
            "novelty_boundary": "D-separation and the global Markov property are established causal-inference mathematics. JANUS does not claim them as new. Their role here is protocol hardening of the independent-future witness."
        },
        "critical_corrections": {
            "directed_path_only_is_insufficient": "A shared latent seed can cause both T and PRE_RETURN without any directed T->R path.",
            "selection_collider": "Conditioning/reporting only selected runs can create dependence between otherwise independent T and R.",
            "clock_vs_information": "Shared clocks/backdating can attack ordering/provenance without carrying hard target bits; treat separately.",
            "precommitment": "Any target-derived commitment/side information present before PRE_RETURN can lower information-theoretic conditional min-entropy even if inversion is computationally difficult."
        },
        "cases": cases,
        "exact_distribution_checks": distribution,
        "parallel_leak_cut_exhaustive": parallel,
        "side_information_demo": parity,
        "protocol_upgrade": {
            "hard_target_layer": "payload+nonce only; public run metadata excluded from hard entropy claim",
            "required_before_external_bench": [
                "draw and freeze a causal DAG naming all pre-target state, latent/shared state and cross-device channels",
                "require T_hard d-separated from PRE_RETURN_hard_view conditional only on explicitly allowed public metadata",
                "ban target pre-generation/prefetch and target-derived commitments before PRE_RETURN freeze",
                "separate ordering/provenance attacks from information-dependence attacks",
                "pre-register inclusion/reporting so collider selection cannot be opened post hoc",
                "empirically audit H_min(T_hard | complete pre-target transcript), because graph completeness cannot be guaranteed by software"
            ]
        },
        "physical_boundary": "This is a causal-model/protocol test. It neither creates nor observes FTL, a physical CTC, retrocausality, or future-bit preexistence."
    }

def main():
    report = run_suite()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["all_pass"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
