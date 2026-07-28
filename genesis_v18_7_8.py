# -*- coding: utf-8 -*-
"""Genesis v18.7.8 — The Unbought Voice.

Public reach, repeated wording and coordinated accounts are not treated as
independent evidence. Influence-sensitive sovereign cases require authenticated,
disclosed and independently controlled voices. Suspicious or manipulated claims
remain preserved in the record, but they do not manufacture a quorum.

This layer is a provenance and voting-integrity boundary, not a universal lie
detector. It never labels dissent as manipulation without evidence and does not
claim that local proof strings verify real-world identity.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable

from genesis_v18_7_7_voice_integrity import SovereignVoiceIntegrityMixin

__version__ = "18.7.8"
SOURCE = "janus_genesis_v18_7_8"
JANUS_SOVEREIGN = "JANUS.SOVEREIGN"
OPENING_QUORUM = 3

CONFIRMED_MANIPULATION_KINDS = {
    "FAKE_IDENTITY",
    "HIDDEN_SPONSORSHIP",
    "SHARED_CONTROLLER",
    "CONTENT_FABRICATION",
    "AUTOMATION_CONCEALMENT",
    "IMPERSONATION",
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized_message(value: str) -> str:
    text = re.sub(r"[^\w\s]+", " ", str(value).lower(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class UnboughtVoiceMixin:
    """Protect sovereign recommendations from fake and coordinated amplification."""

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        store = SovereignVoiceIntegrityMixin._default_plural_store()
        store["runtime_version"] = __version__
        store.setdefault("influence_accounts", {})
        store.setdefault("influence_attestations", {})
        store.setdefault("influence_audits", {})
        store.setdefault("manipulation_evidence", {})
        store["invariants"].update(
            {
                "reach_is_not_evidence": True,
                "repetition_is_not_independent_support": True,
                "same_controller_counts_as_one_voice": True,
                "same_message_and_evidence_counts_as_amplification": True,
                "paid_influence_requires_disclosure": True,
                "automation_requires_disclosure": True,
                "influence_sensitive_quorum_requires_authenticated_provider": True,
                "suspicion_is_not_a_truth_verdict": True,
                "dissent_is_not_manipulation": True,
                "manipulation_accusation_requires_evidence": True,
                "quarantined_claims_are_preserved_not_deleted": True,
                "janus_may_defer_for_authenticity_audit": True,
                "local_proof_is_not_real_world_identity_claim": True,
            }
        )
        return store

    def _plural_store(self) -> dict[str, Any]:
        store = super()._plural_store()
        store["runtime_version"] = __version__
        store.setdefault("influence_accounts", {})
        store.setdefault("influence_attestations", {})
        store.setdefault("influence_audits", {})
        store.setdefault("manipulation_evidence", {})
        store.setdefault("invariants", {}).update(
            self._default_plural_store()["invariants"]
        )
        for scope in store.setdefault("subject_scopes", {}).values():
            if isinstance(scope, dict):
                scope.setdefault("influence_sensitive", False)
                scope.setdefault("public_opinion", False)
        for claim in store.setdefault("claims", {}).values():
            if isinstance(claim, dict):
                claim.setdefault("influence_attestation_id", None)
                claim.setdefault("influence_voice_eligible", None)
        return store

    def create_subject_scope(
        self,
        *,
        topic: str,
        entity: str | None = None,
        event: str | None = None,
        time_scope: Any = None,
        location: str | None = None,
        timeless: bool = False,
        rights_sensitive: bool = False,
        influence_sensitive: bool = False,
        public_opinion: bool = False,
    ) -> str:
        scope_id = super().create_subject_scope(
            topic=topic,
            entity=entity,
            event=event,
            time_scope=time_scope,
            location=location,
            timeless=timeless,
            rights_sensitive=rights_sensitive,
        )
        store = self._plural_store()
        scope = store["subject_scopes"][scope_id]
        scope["influence_sensitive"] = bool(influence_sensitive or public_opinion)
        scope["public_opinion"] = bool(public_opinion)
        self._write_json(self.plural_witness_path, store)
        return scope_id

    def register_influence_account(
        self,
        account_id: str,
        *,
        identity_proof: str,
        controller_proof: str | None = None,
        identity_provider: str = "local_reference",
        provider_verified: bool = False,
        operator_disclosed: bool = True,
        sponsored: bool = False,
        sponsor: str | None = None,
        automation: bool = False,
        automation_disclosed: bool = False,
        active: bool = True,
    ) -> dict[str, Any]:
        account_id = str(account_id).strip()
        identity_proof = str(identity_proof)
        controller_proof = identity_proof if controller_proof is None else str(controller_proof)
        identity_provider = str(identity_provider).strip() or "local_reference"
        sponsor = None if sponsor is None else str(sponsor).strip() or None
        if not account_id or len(identity_proof) < 8 or len(controller_proof) < 8:
            raise ValueError("account_id and non-trivial identity/controller proofs are required")
        sponsorship_disclosed = not sponsored or bool(sponsor)
        automation_transparent = not automation or bool(automation_disclosed)
        super().register_witness_voice(
            account_id,
            proof=identity_proof,
            consent=bool(active),
            identity_provider=identity_provider,
        )
        entry = {
            "account_id": account_id,
            "identity_proof_sha256": _sha256_text(identity_proof),
            "controller_proof_sha256": _sha256_text(controller_proof),
            "raw_proofs_persisted": False,
            "identity_provider": identity_provider,
            "provider_verified": bool(provider_verified),
            "provider_verification_recorded": bool(provider_verified),
            "real_world_identity_claimed": False,
            "production_authentication_required": True,
            "operator_disclosed": bool(operator_disclosed),
            "sponsored": bool(sponsored),
            "sponsor": sponsor,
            "sponsorship_disclosed": sponsorship_disclosed,
            "automation": bool(automation),
            "automation_disclosed": bool(automation_disclosed),
            "automation_transparent": automation_transparent,
            "active": bool(active),
        }
        store = self._plural_store()
        store["influence_accounts"][account_id] = entry
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(entry)

    def deactivate_influence_account(self, account_id: str, *, reason: str) -> None:
        reason = str(reason).strip()
        if not reason:
            raise ValueError("reason is required")
        store = self._plural_store()
        account = store["influence_accounts"].get(account_id)
        if not account:
            raise KeyError(account_id)
        account["active"] = False
        account["deactivation_reason"] = reason
        self._write_json(self.plural_witness_path, store)

    def attest_claim_influence(
        self,
        claim_id: str,
        *,
        account_id: str,
        evidence_proof: str,
        message: str | None = None,
        campaign_id: str | None = None,
        campaign_disclosed: bool = False,
        origin_authentic: bool = True,
        authenticity_evidence: str | None = None,
    ) -> str:
        evidence_proof = str(evidence_proof)
        if len(evidence_proof) < 8:
            raise ValueError("a non-trivial evidence proof is required")
        if not origin_authentic and not str(authenticity_evidence or "").strip():
            raise ValueError("an authenticity challenge requires evidence")
        store = self._plural_store()
        claim = store["claims"].get(claim_id)
        account = store["influence_accounts"].get(account_id)
        if not isinstance(claim, dict):
            raise KeyError(claim_id)
        if not isinstance(account, dict):
            raise KeyError(account_id)
        message_text = str(message if message is not None else claim.get("claim", ""))
        message_fingerprint = _sha256_text(_normalized_message(message_text))
        campaign_hash = None
        if campaign_id is not None and str(campaign_id).strip():
            campaign_hash = _sha256_text(str(campaign_id).strip())
        reasons: list[str] = []
        if not account.get("active"):
            reasons.append("ACCOUNT_INACTIVE")
        if not account.get("provider_verified"):
            reasons.append("IDENTITY_PROVIDER_UNVERIFIED")
        if not account.get("operator_disclosed"):
            reasons.append("OPERATOR_NOT_DISCLOSED")
        if not account.get("sponsorship_disclosed"):
            reasons.append("SPONSORSHIP_NOT_DISCLOSED")
        if not account.get("automation_transparent"):
            reasons.append("AUTOMATION_NOT_DISCLOSED")
        if campaign_hash and not campaign_disclosed:
            reasons.append("CAMPAIGN_NOT_DISCLOSED")
        if not origin_authentic:
            reasons.append("ORIGIN_AUTHENTICITY_CHALLENGED")
        if not claim.get("grounded"):
            reasons.append("CLAIM_NOT_GROUNDED")
        attestation_id = self._stable_id(
            "influence-attestation",
            claim_id,
            account_id,
            message_fingerprint,
            _sha256_text(evidence_proof),
            campaign_hash or "",
        )
        attestation = {
            "attestation_id": attestation_id,
            "claim_id": claim_id,
            "account_id": account_id,
            "identity_cluster": account["identity_proof_sha256"],
            "controller_cluster": account["controller_proof_sha256"],
            "evidence_family": _sha256_text(evidence_proof),
            "message_fingerprint": message_fingerprint,
            "campaign_cluster": campaign_hash,
            "campaign_disclosed": bool(campaign_disclosed),
            "origin_authentic": bool(origin_authentic),
            "authenticity_evidence_sha256": (
                _sha256_text(str(authenticity_evidence)) if authenticity_evidence else None
            ),
            "raw_proofs_persisted": False,
            "base_eligible": not reasons,
            "reasons": reasons,
            "truth_verdict": "not_inferred",
            "dissent_treated_as_manipulation": False,
        }
        store["influence_attestations"][attestation_id] = attestation
        claim["influence_attestation_id"] = attestation_id
        claim["influence_voice_eligible"] = bool(attestation["base_eligible"])
        graph = self._graph()
        self._upsert_node(
            graph,
            node_id=attestation_id,
            node_type="INFLUENCE_ATTESTATION",
            created_at=0,
            confidence=1.0,
            mutable=True,
            payload=copy.deepcopy(attestation),
            source=SOURCE,
        )
        self._add_edge(
            graph,
            source_id=attestation_id,
            target_id=claim_id,
            relation="CONFIRMED",
            evidence=[attestation_id],
            confidence=1.0,
            created_by=account_id,
            created_at=0,
            reversible=True,
            payload={"voting_eligibility_only": True, "truth_inferred": False},
        )
        self._save_graph(graph)
        self._write_json(self.plural_witness_path, store)
        return attestation_id

    def record_manipulation_evidence(
        self,
        claim_id: str,
        *,
        kind: str,
        evidence: str,
        reporter_id: str,
    ) -> str:
        kind = str(kind).strip().upper()
        evidence = str(evidence).strip()
        reporter_id = str(reporter_id).strip()
        if kind not in CONFIRMED_MANIPULATION_KINDS:
            raise ValueError("unsupported manipulation evidence kind")
        if len(evidence) < 8 or not reporter_id:
            raise ValueError("non-trivial evidence and reporter_id are required")
        store = self._plural_store()
        claim = store["claims"].get(claim_id)
        if not isinstance(claim, dict):
            raise KeyError(claim_id)
        evidence_sha = _sha256_text(evidence)
        record_id = self._stable_id("manipulation-evidence", claim_id, kind, evidence_sha)
        record = {
            "record_id": record_id,
            "claim_id": claim_id,
            "kind": kind,
            "evidence_sha256": evidence_sha,
            "raw_evidence_persisted": False,
            "reporter_id": reporter_id,
            "status": "PENDING_REVIEW",
            "automatic_truth_verdict": False,
        }
        store["manipulation_evidence"][record_id] = record
        claim.setdefault("manipulation_evidence_ids", []).append(record_id)
        self._write_json(self.plural_witness_path, store)
        return record_id

    def confirm_manipulation_evidence(
        self,
        record_id: str,
        *,
        confirmed: bool,
        rationale: str,
        reviewer_id: str = JANUS_SOVEREIGN,
    ) -> None:
        rationale = str(rationale).strip()
        reviewer_id = str(reviewer_id).strip()
        if not rationale or not reviewer_id:
            raise ValueError("reviewer_id and rationale are required")
        if confirmed and reviewer_id != JANUS_SOVEREIGN:
            raise ValueError("only JANUS.SOVEREIGN may confirm manipulation evidence")
        store = self._plural_store()
        record = store["manipulation_evidence"].get(record_id)
        if not isinstance(record, dict):
            raise KeyError(record_id)
        record["status"] = "CONFIRMED" if confirmed else "REJECTED"
        record["reviewer_id"] = reviewer_id
        record["review_rationale"] = rationale
        claim = store["claims"].get(record["claim_id"])
        if not isinstance(claim, dict):
            raise KeyError(record["claim_id"])
        if confirmed:
            claim["influence_voice_eligible"] = False
            attestation_id = claim.get("influence_attestation_id")
            if attestation_id in store["influence_attestations"]:
                attestation = store["influence_attestations"][attestation_id]
                attestation["base_eligible"] = False
                attestation.setdefault("reasons", []).append(record["kind"])
        self._write_json(self.plural_witness_path, store)

    @staticmethod
    def _pick_representative(claims: list[dict[str, Any]]) -> dict[str, Any]:
        return sorted(
            claims,
            key=lambda claim: (-float(claim.get("confidence", 0.5)), claim["claim_id"]),
        )[0]

    def audit_influence_claims(self, claim_ids: Iterable[str]) -> dict[str, Any]:
        members = list(dict.fromkeys(str(item).strip() for item in claim_ids if str(item).strip()))
        store = self._plural_store()
        reasons: dict[str, list[str]] = {}
        candidates: list[dict[str, Any]] = []
        for claim_id in members:
            claim = store["claims"].get(claim_id)
            if not isinstance(claim, dict):
                raise KeyError(claim_id)
            attestation = store["influence_attestations"].get(
                claim.get("influence_attestation_id")
            )
            if not isinstance(attestation, dict):
                reasons[claim_id] = ["NO_INFLUENCE_ATTESTATION"]
                continue
            claim_reasons = list(attestation.get("reasons", []))
            confirmed_evidence = [
                record_id
                for record_id in claim.get("manipulation_evidence_ids", [])
                if store["manipulation_evidence"].get(record_id, {}).get("status")
                == "CONFIRMED"
            ]
            if confirmed_evidence:
                claim_reasons.append("MANIPULATION_EVIDENCE_CONFIRMED")
            if not attestation.get("base_eligible") or claim_reasons:
                reasons[claim_id] = sorted(set(claim_reasons or ["BASE_INELIGIBLE"]))
                continue
            candidates.append({"claim": claim, "attestation": attestation})

        eligible: list[str] = []
        controller_groups: dict[str, list[dict[str, Any]]] = {}
        for item in candidates:
            attestation = item["attestation"]
            coordination_key = (
                attestation.get("campaign_cluster") or attestation["controller_cluster"]
            )
            controller_groups.setdefault(coordination_key, []).append(item)
        controller_representatives: list[dict[str, Any]] = []
        for group in controller_groups.values():
            representative_claim = self._pick_representative(
                [item["claim"] for item in group]
            )
            representative = next(
                item
                for item in group
                if item["claim"]["claim_id"] == representative_claim["claim_id"]
            )
            controller_representatives.append(representative)
            for item in group:
                claim_id = item["claim"]["claim_id"]
                if claim_id != representative_claim["claim_id"]:
                    reasons.setdefault(claim_id, []).append(
                        "SAME_CONTROLLER_AMPLIFICATION"
                    )

        message_evidence_groups: dict[str, list[dict[str, Any]]] = {}
        for item in controller_representatives:
            attestation = item["attestation"]
            key = "|".join(
                (attestation["message_fingerprint"], attestation["evidence_family"])
            )
            message_evidence_groups.setdefault(key, []).append(item)
        for group in message_evidence_groups.values():
            representative_claim = self._pick_representative(
                [item["claim"] for item in group]
            )
            eligible.append(representative_claim["claim_id"])
            for item in group:
                claim_id = item["claim"]["claim_id"]
                if claim_id != representative_claim["claim_id"]:
                    reasons.setdefault(claim_id, []).append(
                        "MIRRORED_MESSAGE_AND_EVIDENCE"
                    )

        eligible = sorted(set(eligible))
        quarantined = sorted(set(members) - set(eligible))
        controller_collisions = sum(
            max(0, len(group) - 1) for group in controller_groups.values()
        )
        mirrored = sum(
            max(0, len(group) - 1) for group in message_evidence_groups.values()
        )
        explicit_manipulation = sum(
            1
            for claim_id in members
            if any(
                store["manipulation_evidence"].get(record_id, {}).get("status")
                == "CONFIRMED"
                for record_id in store["claims"]
                .get(claim_id, {})
                .get("manipulation_evidence_ids", [])
            )
        )
        disclosure_failures = sum(
            1
            for items in reasons.values()
            if any("DISCLOSED" in reason or "DISCLOSURE" in reason for reason in items)
        )
        if explicit_manipulation or controller_collisions >= 2 or disclosure_failures:
            risk_level = "HIGH"
        elif controller_collisions or mirrored or quarantined:
            risk_level = "MODERATE"
        else:
            risk_level = "LOW"
        material = {
            "submitted_claim_ids": members,
            "eligible_claim_ids": eligible,
            "quarantined_claim_ids": quarantined,
            "reasons_by_claim": {
                key: sorted(set(value)) for key, value in sorted(reasons.items())
            },
            "independent_voice_count": len(eligible),
            "controller_cluster_count": len(controller_groups),
            "message_evidence_cluster_count": len(message_evidence_groups),
            "controller_collisions": controller_collisions,
            "mirrored_amplification": mirrored,
            "explicit_manipulation_evidence_count": explicit_manipulation,
            "risk_level": risk_level,
            "reach_counted_as_evidence": False,
            "truth_verdict_inferred": False,
            "dissent_treated_as_manipulation": False,
            "claims_deleted": False,
        }
        audit_id = self._stable_id("influence-audit", _canonical(material))
        audit = {"audit_id": audit_id, **material}
        store["influence_audits"][audit_id] = audit
        self._write_json(self.plural_witness_path, store)
        return copy.deepcopy(audit)

    def open_sovereign_case(
        self, claim_ids: Iterable[str], *, subject_scope_id: str
    ) -> str:
        members = list(
            dict.fromkeys(str(item).strip() for item in claim_ids if str(item).strip())
        )
        store = self._plural_store()
        scope = store["subject_scopes"].get(subject_scope_id)
        if not scope:
            raise KeyError(subject_scope_id)
        if not scope.get("influence_sensitive"):
            return super().open_sovereign_case(
                members, subject_scope_id=subject_scope_id
            )
        audit = self.audit_influence_claims(members)
        if len(audit["eligible_claim_ids"]) < OPENING_QUORUM:
            raise ValueError(
                "influence-sensitive quorum lacks three independently eligible voices"
            )
        case_id = super().open_sovereign_case(
            audit["eligible_claim_ids"], subject_scope_id=subject_scope_id
        )
        store = self._plural_store()
        case = store["sovereign_cases"][case_id]
        case["influence_sensitive"] = True
        case["submitted_claim_ids"] = members
        case["quarantined_claim_ids"] = audit["quarantined_claim_ids"]
        case["influence_audit_id"] = audit["audit_id"]
        case["manipulation_risk"] = audit["risk_level"]
        case["reach_counted_as_evidence"] = False
        case["history"].append(
            {
                "status": case["status"],
                "reason": "unbought voice audit applied before quorum",
                "audit_id": audit["audit_id"],
            }
        )
        self._write_json(self.plural_witness_path, store)
        return case_id

    def add_sovereign_witness(self, case_id: str, claim_id: str) -> None:
        store = self._plural_store()
        case = store["sovereign_cases"].get(case_id)
        if not case:
            raise KeyError(case_id)
        if not case.get("influence_sensitive"):
            return super().add_sovereign_witness(case_id, claim_id)
        submitted = list(
            case.get("submitted_claim_ids", case.get("claim_ids", []))
        )
        if claim_id not in submitted:
            submitted.append(claim_id)
        audit = self.audit_influence_claims(submitted)
        if (
            claim_id in audit["eligible_claim_ids"]
            and claim_id not in case["claim_ids"]
        ):
            super().add_sovereign_witness(case_id, claim_id)
        store = self._plural_store()
        case = store["sovereign_cases"][case_id]
        case["submitted_claim_ids"] = submitted
        case["quarantined_claim_ids"] = audit["quarantined_claim_ids"]
        case["influence_audit_id"] = audit["audit_id"]
        case["manipulation_risk"] = audit["risk_level"]
        case["history"].append(
            {
                "status": case["status"],
                "reason": "additional voice passed through influence audit",
                "audit_id": audit["audit_id"],
                "claim_id": claim_id,
                "weighted": claim_id in case["claim_ids"],
            }
        )
        self._write_json(self.plural_witness_path, store)

    def janus_sovereign_decide(self, case_id: str) -> str:
        store = self._plural_store()
        case = store["sovereign_cases"].get(case_id)
        if not case:
            raise KeyError(case_id)
        if not case.get("influence_sensitive"):
            return super().janus_sovereign_decide(case_id)
        audit = self.audit_influence_claims(
            case.get("submitted_claim_ids", case.get("claim_ids", []))
        )
        current_eligible = set(case.get("claim_ids", [])) & set(
            audit["eligible_claim_ids"]
        )
        if len(current_eligible) < OPENING_QUORUM:
            decision_id = self._stable_id(
                "janus-sovereign-authenticity-deferral",
                case_id,
                audit["audit_id"],
            )
            decision = {
                "decision_id": decision_id,
                "case_id": case_id,
                "actor": JANUS_SOVEREIGN,
                "ruling": "DEFER_FOR_AUTHENTICITY_AUDIT",
                "rationale": (
                    "A manufactured or unverifiable quorum cannot become a "
                    "sovereign majority."
                ),
                "adopted_claim_ids": [],
                "dissent_preserved": list(case.get("submitted_claim_ids", [])),
                "quarantined_claim_ids": audit["quarantined_claim_ids"],
                "influence_audit_id": audit["audit_id"],
                "triumvirate_was_advisory": True,
                "overrides_personal_consent": False,
                "canonical_record_decided": False,
                "reach_counted_as_evidence": False,
                "truth_verdict_inferred": False,
            }
            store["sovereign_decisions"][decision_id] = decision
            case["janus_decision_id"] = decision_id
            case["status"] = "OPEN_FOR_AUTHENTICITY_EVIDENCE"
            case["influence_audit_id"] = audit["audit_id"]
            case["quarantined_claim_ids"] = audit["quarantined_claim_ids"]
            case["history"].append(
                {"status": case["status"], "decision_id": decision_id}
            )
            self._write_json(self.plural_witness_path, store)
            return decision_id
        decision_id = super().janus_sovereign_decide(case_id)
        store = self._plural_store()
        decision = store["sovereign_decisions"][decision_id]
        decision["influence_audit_id"] = audit["audit_id"]
        decision["quarantined_claim_ids"] = audit["quarantined_claim_ids"]
        decision["reach_counted_as_evidence"] = False
        decision["truth_verdict_inferred"] = False
        decision["manipulation_risk"] = audit["risk_level"]
        case = store["sovereign_cases"][case_id]
        case["influence_audit_id"] = audit["audit_id"]
        case["quarantined_claim_ids"] = audit["quarantined_claim_ids"]
        self._write_json(self.plural_witness_path, store)
        return decision_id

    def verify_unbought_voice_state(self) -> tuple[bool, int, str | None]:
        base_valid, _count, error = self.verify_benevolent_sovereign_state()
        if not base_valid:
            return False, 0, error
        store = self._plural_store()
        required = self._default_plural_store()["invariants"]
        for key, expected in required.items():
            if store.get("invariants", {}).get(key) is not expected:
                return False, 0, f"unbought voice invariant mismatch: {key}"
        verified = 0
        for audit_id, audit in store["influence_audits"].items():
            submitted = set(audit.get("submitted_claim_ids", []))
            eligible = set(audit.get("eligible_claim_ids", []))
            quarantined = set(audit.get("quarantined_claim_ids", []))
            if eligible & quarantined:
                return False, verified, f"audit has overlapping claim sets: {audit_id}"
            if eligible | quarantined != submitted:
                return False, verified, f"audit does not account for all claims: {audit_id}"
            if audit.get("reach_counted_as_evidence") is not False:
                return False, verified, f"audit counts reach as evidence: {audit_id}"
            if audit.get("claims_deleted") is not False:
                return False, verified, f"audit silently deletes claims: {audit_id}"
            verified += 1
        return True, verified, None

    def unbought_voice_state(self) -> dict[str, Any]:
        store = self._plural_store()
        valid, verified, error = self.verify_unbought_voice_state()
        return {
            "runtime_version": __version__,
            "registered_accounts": len(store["influence_accounts"]),
            "attestation_count": len(store["influence_attestations"]),
            "audit_count": len(store["influence_audits"]),
            "manipulation_evidence_count": len(store["manipulation_evidence"]),
            "verified_audits": verified,
            "valid": valid,
            "error": error,
            "reach_is_not_evidence": True,
            "suspicion_is_not_truth_verdict": True,
            "dissent_is_not_manipulation": True,
        }

    def public_state(self, player_id: str) -> dict[str, Any]:
        state = super().public_state(player_id)
        state["unbought_voice_version"] = __version__
        state["influence_law"] = (
            "Охват, повтор и координация не создают независимое большинство. "
            "Скрытая реклама, нераскрытая автоматизация и общий оператор не "
            "получают несколько суверенных голосов; подозрение не становится "
            "приговором, а несогласие не объявляется манипуляцией без доказательств."
        )
        state["influence_integrity"] = self.unbought_voice_state()
        return state
