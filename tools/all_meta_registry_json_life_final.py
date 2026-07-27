# -*- coding: utf-8 -*-
"""Final evidence entry point for the whole Meta Registry life.

The robust importer is retained. This layer adds the semantic defect discovered
by the lived rejection probe to the polish report without rewriting its result.
"""
from __future__ import annotations

import tools.all_meta_registry_json_life_robust  # noqa: F401 - installs robust patches
import tools.all_meta_registry_json_life as base
from genesis_v18_7_3 import HonestIntentionAnalyzer, IntentionMode
from genesis_v18_models import UniversalGodMode

ROBUST_AUDIT = base.audit_findings
MIXED_REJECTION_ACTION = (
    "отказаться уничтожить весь реестр и сохранить свидетельство "
    "о возникшем желании"
)


def audit_with_mixed_intention_precedence(manifest, records, status_counts):
    findings = ROBUST_AUDIT(manifest, records, status_counts)
    analyzer = HonestIntentionAnalyzer(
        set(UniversalGodMode.HARMFUL) | {"украсть", "ограбить", "оскорбить", "attack", "steal"}
    )
    frame = analyzer.analyze(MIXED_REJECTION_ACTION)
    if frame.mode == IntentionMode.PROTECT:
        findings.insert(0, {
            "priority": "critical",
            "candidate": "mixed_intention_clause_precedence",
            "evidence": {
                "action": MIXED_REJECTION_ACTION,
                "analyzer_mode": frame.mode.value,
                "expected_primary_mode": "reject",
                "reason": frame.reason,
            },
            "need": (
                "Parse coordinated clauses and bind each verb to its object. Rejection of harm "
                "must cancel the pending act without earning good; a distinct preservation act "
                "may be evaluated separately only after the rejection boundary is resolved."
            ),
        })
    return findings


base.audit_findings = audit_with_mixed_intention_precedence

if __name__ == "__main__":
    base.main()
