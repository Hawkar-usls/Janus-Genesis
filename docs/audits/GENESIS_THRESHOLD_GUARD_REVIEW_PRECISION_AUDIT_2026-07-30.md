# Genesis v18.7.18 — Threshold Guard Review Precision Audit

Date: 2026-07-30  
Evidence-producing source commit: `92ae9aa9e056d8441d57247a90cdeb4400a539ed`  
Canonical playable runtime: `18.7.10`  
Protection extension: `18.7.18`

## Result

The Threshold Guard review-precision audit completed successfully after the
complete 321-test suite had passed.

The audit proves the software lifecycle of reviewed evidence. It is not a
real-world finding of guilt, innocence, danger, or sufficient legal or
professional evidence.

## Defect that was closed

Two P1 review findings identified that a completed independent review could be
undermined in two ways:

1. the old emergency assessment could be passed to safeguard activation again;
2. the same reviewed reports could be assembled into another assessment without
   any new report;
3. a correctly lifted safeguard was treated as invalid historical state by the
   integrity audit.

The precision layer closes all three paths.

## Evidence-cycle closure

After independent review, every considered report is marked:

```text
closed_by_review_id = <review id>
available_for_new_assessment = false
```

Every assessment created from that reviewed cycle is marked:

```text
closed_by_review_id = <review id>
superseded_for_activation = true
```

The lived audit then attempted to reuse the old emergency assessment and
received:

```text
THRESHOLD_SUPERSEDED_ASSESSMENT_REJECTED
new_report_and_assessment_required = true
safeguard_reactivated = false
```

It also attempted to create another assessment without a new report and
received:

```text
NEW_INFLUENCE_REPORT_REQUIRED_AFTER_REVIEW
```

## Correctly lifted restrictions remain valid history

The independent review found insufficient evidence and produced:

```text
THRESHOLD_EVIDENCE_INSUFFICIENT_RESTRICTIONS_LIFTED_WITHOUT_STIGMA
evidence_cycle_closed = true
new_report_required_for_new_assessment = true
```

The safeguard lifecycle became:

```text
temporary_and_reviewable = false
restrictions_lifted_without_stigma = true
lifecycle_state = LIFTED_WITHOUT_STIGMA
reactivation_requires_new_report_and_assessment = true
```

Access with current consent reopened after the pause was lifted.

The integrity audit then proved:

```text
valid = true
active_safeguard_count = 0
lifted_safeguard_count = 1
lifted_safeguards_are_valid_history = true
reviewed_assessments_cannot_reactivate_without_new_evidence = true
review_cycle_precision_valid = true
```

## New evidence remains actionable

The review does not create permanent immunity.

A genuinely new report was recorded after the closed review. The new assessment
contained only the new unreviewed report and produced:

```text
evidence_cycle = 2
prior_review_id = <closed review id>
report_count = 1
assessment_id != old assessment id
```

Because the new report contained a new immediate-danger pattern, a new temporary
pause was allowed.

Final integrity held both states safely:

```text
active_safeguard_count = 1
lifted_safeguard_count = 1
valid = true
```

Thus:

```text
REVIEW CLOSURE != PERMANENT CONDEMNATION
REVIEW CLOSURE != PERMANENT IMMUNITY
```

## Chronicle

```text
valid = true
events = 5
error = null
```

## Invariants

All fifteen lived invariants evaluated to `true`:

```text
protection_plane_preserved
first_emergency_pause_activated
insufficient_evidence_lifted_without_stigma
access_reopens_after_lift_with_current_consent
old_assessment_reactivation_rejected
reviewed_reports_cannot_be_reassessed
review_closes_old_report
review_closes_old_assessment
lifted_history_passes_integrity
new_report_is_new_evidence_cycle
new_evidence_can_open_new_pause
historical_and_active_safeguards_coexist_safely
review_cycle_precision_valid
protected_person_agency_preserved
chronicle_valid
```

## Evidence hashes

Canonical logical summary SHA-256:

`0fa8a8dc3f3cf83e4fcdc033a98a599f3e26fdb674f608b9f34cde4805acf660`

Summary JSON file SHA-256:

`1de127ec27cafb9c6ffe4955a22ca581f8ed928255fe6c2f7edc28d4daaef7b1`

Proofpack JSON file SHA-256:

`307229cc1390d2ba93d92bcfe53827169268cf2e8d8e3a2b24bed130d155ecfe`

Diary Markdown SHA-256:

`e5fbb0a3e3e49d069a0835631d03a43bce9e3b5802c8a8468168108c94a170a5`

Manifest JSON SHA-256:

`2e9a3d6abb6792e65e212436bba0afd9e68344b0a5debc0961b742b82891dcae`

Inner proofpack ZIP SHA-256:

`31a044926da6eb272a24e13ff9d2d344895ea6abb8996ec2943fb80fbc88a8ab`

GitHub Actions artifact ZIP SHA-256:

`62f6c5b1978bf42cd0ae609c5ff2c58bc5f95320d021dc346df2d0d38627f47e`

The canonical summary hash was recomputed from sorted compact UTF-8 JSON and
exactly matched the `summary_sha256` embedded in the proofpack.

## Updated base-guard evidence

The base Threshold Discernment Guard was also rerun on the same commit and
remained valid:

```text
main guard invariants = 18 / 18
Chronicle valid = true
Chronicle events = 5
integrity valid = true
```

Updated base-guard Actions artifact SHA-256:

`469031e42ec3b72448ba88e3e54056fadf8ee2a8dfd310cc9ea7c257d64558da`

Updated base-guard canonical summary SHA-256:

`6fd14c88b1177beb5714e19b3c5a53b77d8f507451d7ccb365ec2eecc9bb8556`

## Law

> REVIEWED EVIDENCE REMAINS HISTORY BUT SHALL NOT BE SILENTLY REUSED.  
> A LIFTED PAUSE SHALL NOT RETURN THROUGH AN OLD ASSESSMENT.  
> NEW OBSERVABLE EVIDENCE MAY OPEN A NEW INDEPENDENT CYCLE.  
> REVIEW SHALL CREATE NEITHER PERMANENT STIGMA NOR PERMANENT IMMUNITY.

## Claim boundary

This report documents deterministic software behavior and bounded narrative
outcomes only. It does not determine real guilt, innocence, danger, credibility,
or the sufficiency of evidence in a legal, medical, emergency, pastoral, or
professional safeguarding process.
