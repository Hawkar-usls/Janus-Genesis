from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_9 import (
    build_provider_attestation,
    generate_ed25519_keypair,
    sign_payload,
)
from genesis_v18_7_10 import (
    DEFAULT_CONFIDENCE_POLICY,
    DEFAULT_POLICY_SHA256,
    FROZEN_CONSTITUTION_SHA256,
    PLAYABLE_SENTINEL,
    SIGNED_OBSERVATION_COMPONENTS,
    build_assessor_attestation,
    build_root_governance_manifest,
)
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


ISSUED = "2026-01-01T00:00:00Z"
EXPIRES = "2099-01-01T00:00:00Z"


def sha256_text(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GenesisV18710BoundAssessorI0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)

        self.root_private, self.root_public = generate_ed25519_keypair()
        self.provider_private, self.provider_public = generate_ed25519_keypair()
        self.sovereign_private, self.sovereign_public = generate_ed25519_keypair()
        self.assessor_private, self.assessor_public = generate_ed25519_keypair()

        old = os.environ.get("GENESIS_OFFLINE_ROOT_BOOTSTRAP")
        os.environ["GENESIS_OFFLINE_ROOT_BOOTSTRAP"] = "1"
        try:
            self.world.bootstrap_offline_root_key(
                "genesis-root",
                key_id="root-key-1",
                public_key_b64=self.root_public,
                valid_from=ISSUED,
                valid_until=EXPIRES,
                ceremony_receipt="offline ceremony receipt for v18.7.10",
            )
        finally:
            if old is None:
                os.environ.pop("GENESIS_OFFLINE_ROOT_BOOTSTRAP", None)
            else:
                os.environ["GENESIS_OFFLINE_ROOT_BOOTSTRAP"] = old

        operations = [
            {
                "operation": "TRUST_PROVIDER_KEY",
                "provider_id": "provider-alpha",
                "key_id": "provider-key-1",
                "public_key_b64": self.provider_public,
                "valid_from": ISSUED,
                "valid_until": EXPIRES,
            },
            {
                "operation": "TRUST_SOVEREIGN_KEY",
                "key_id": "sovereign-key-1",
                "public_key_b64": self.sovereign_public,
                "valid_from": ISSUED,
                "valid_until": EXPIRES,
            },
            {
                "operation": "TRUST_ASSESSOR_KEY",
                "assessor_id": "assessor-alpha",
                "key_id": "assessor-key-1",
                "public_key_b64": self.assessor_public,
                "valid_from": ISSUED,
                "valid_until": EXPIRES,
            },
            {
                "operation": "SET_ASSESSOR_CREDENTIAL",
                "credential_id": "assessor-alpha-general-v1",
                "assessor_id": "assessor-alpha",
                "controller_id": sha256_text("assessor-controller-independent"),
                "allowed_methods": ["triangulation-v2"],
                "allowed_subject_scopes": ["*"],
                "competence_by_scope": {"*": 0.82},
                "max_component_authority": {
                    name: 0.95 for name in SIGNED_OBSERVATION_COMPONENTS
                },
                "may_assess_own_sources": False,
                "valid_from": ISSUED,
                "valid_until": EXPIRES,
                "credential_version": "1",
            },
        ]
        manifest = build_root_governance_manifest(
            root_id="genesis-root",
            key_id="root-key-1",
            operations=operations,
            nonce="root-manifest-initial-1810",
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.root_private,
        )
        self.world.apply_root_governance_manifest(manifest)
        self.counter = 0

    def _scope(self, topic: str = "bound-assessor") -> str:
        return self.world.create_subject_scope(
            topic=topic,
            event="controlled hearing",
            time_scope={"date": "2026-07-28"},
            influence_sensitive=True,
            public_opinion=True,
        )

    def _claim(
        self,
        *,
        account_id: str = "reader-alpha",
        controller_proof: str | None = None,
        topic: str = "bound-assessor",
        text: str = "The bridge requires another inspection",
    ) -> tuple[str, str]:
        self.counter += 1
        identity = f"identity-proof-{account_id}-{self.counter}"
        controller = controller_proof or f"controller-proof-{account_id}-{self.counter}"
        _account_private, account_public = generate_ed25519_keypair()
        provider_attestation = build_provider_attestation(
            provider_id="provider-alpha",
            key_id="provider-key-1",
            account_id=account_id,
            identity_proof=identity,
            controller_proof=controller,
            account_public_key_b64=account_public,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            nonce=f"provider-{account_id}-{self.counter}",
            private_key_b64=self.provider_private,
        )
        self.world.register_influence_account(
            account_id,
            identity_proof=identity,
            controller_proof=controller,
            provider_attestation=provider_attestation,
            operator_disclosed=True,
        )
        scope_id = self._scope(topic)
        origin = self.world.import_origin_bytes(
            repository="bound/assessor",
            commit="18.7.10",
            path=f"claims/{self.counter}.json",
            raw=json.dumps({"statement": text}, ensure_ascii=False).encode("utf-8"),
            source_public=True,
        )
        claim_id = self.world.record_reader_interpretation(
            origin["origin_key"],
            text,
            reader_id=account_id,
            evidence={"kind": "json_pointer", "pointer": "/statement"},
            subject_scope_id=scope_id,
        )
        self.world.attest_claim_influence(
            claim_id,
            account_id=account_id,
            evidence_proof=f"evidence-proof-{self.counter}",
            message=text,
        )
        return claim_id, scope_id

    def _assessment(
        self,
        claim_id: str,
        scope_id: str,
        *,
        assessment_id: str,
        nonce: str,
        evidence: str,
        value: float = 0.9,
        method_id: str = "triangulation-v2",
        supersedes: str | None = None,
    ) -> dict:
        return build_assessor_attestation(
            assessment_id=assessment_id,
            assessor_id="assessor-alpha",
            key_id="assessor-key-1",
            claim_id=claim_id,
            subject_scope_id=scope_id,
            method_id=method_id,
            method_version="2",
            policy_id=DEFAULT_CONFIDENCE_POLICY["policy_id"],
            policy_version=DEFAULT_CONFIDENCE_POLICY["policy_version"],
            policy_sha256=DEFAULT_POLICY_SHA256,
            evidence_hashes=[sha256_text(evidence)],
            components={name: value for name in SIGNED_OBSERVATION_COMPONENTS},
            explanation="Bound observation over a controlled evidence set",
            nonce=nonce,
            issued_at=ISSUED,
            expires_at=EXPIRES,
            private_key_b64=self.assessor_private,
            supersedes_assessment_id=supersedes,
        )

    def test_version_constitution_and_ordinary_root_bootstrap_are_bound(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        constitution = self.world.frozen_constitution_state()
        self.assertTrue(constitution["valid"])
        self.assertEqual(constitution["sha256"], FROZEN_CONSTITUTION_SHA256)
        self.assertEqual(constitution["sentinel"], PLAYABLE_SENTINEL)
        with self.assertRaisesRegex(PermissionError, "ROOT_GOVERNANCE_MANIFEST_REQUIRED"):
            self.world.register_trusted_provider_key(
                "rogue-provider",
                key_id="rogue",
                public_key_b64=self.provider_public,
                valid_from=ISSUED,
                valid_until=EXPIRES,
            )
        with self.assertRaisesRegex(PermissionError, "ROOT_GOVERNANCE_MANIFEST_REQUIRED"):
            self.world.register_sovereign_key(
                key_id="rogue",
                public_key_b64=self.sovereign_public,
                valid_from=ISSUED,
                valid_until=EXPIRES,
            )

    def test_unsigned_tampered_and_self_competence_assessments_are_rejected(self) -> None:
        claim_id, scope_id = self._claim()
        with self.assertRaisesRegex(ValueError, "SIGNED_ASSESSOR_ATTESTATION_REQUIRED"):
            self.world.record_evidence_assessment(
                claim_id,
                components={name: 1.0 for name in SIGNED_OBSERVATION_COMPONENTS},
                assessor_id="self-appointed",
            )

        valid = self._assessment(
            claim_id,
            scope_id,
            assessment_id="assessment-valid-1",
            nonce="assessment-nonce-valid-1",
            evidence="evidence-valid-1",
        )
        tampered = copy.deepcopy(valid)
        tampered["components"]["source_reliability"] = 0.1
        with self.assertRaisesRegex(ValueError, "INVALID_ASSESSOR_SIGNATURE"):
            self.world.record_evidence_assessment(claim_id, assessment=tampered)

        forbidden = copy.deepcopy(valid)
        forbidden["assessment_id"] = "assessment-forbidden-self-competence"
        forbidden["nonce"] = "assessment-forbidden-nonce"
        forbidden["components"]["assessor_competence"] = 1.0
        forbidden = sign_payload(forbidden, self.assessor_private)
        with self.assertRaisesRegex(ValueError, "ASSESSOR_MAY_NOT_ASSIGN_SYSTEM_COMPONENTS"):
            self.world.record_evidence_assessment(claim_id, assessment=forbidden)
        events = self.world._plural_store()["security_events_v1810"]
        self.assertEqual(events[-1]["event_type"], "ASSESSOR_AUTHORITY_BREACH_ATTEMPT")

    def test_policy_computes_competence_and_corroboration(self) -> None:
        claim_id, scope_id = self._claim()
        assessment = self._assessment(
            claim_id,
            scope_id,
            assessment_id="assessment-computed",
            nonce="assessment-computed-nonce",
            evidence="evidence-computed",
            value=0.9,
        )
        assessment_id = self.world.record_evidence_assessment(
            claim_id, assessment=assessment
        )
        store = self.world._plural_store()
        record = store["signed_assessments_v1810"][assessment_id]
        self.assertEqual(record["assessor_competence"], 0.82)
        self.assertEqual(record["independent_corroboration"], 0.0)
        self.assertNotEqual(record["effective_confidence"], 0.9)
        self.assertEqual(record["policy_sha256"], DEFAULT_POLICY_SHA256)
        self.assertFalse(store["claims"][claim_id]["claimant_confidence_used"])
        self.assertTrue(record["signature_integrity"])

    def test_method_authority_component_cap_and_conflict_of_interest(self) -> None:
        claim_id, scope_id = self._claim(account_id="authority-reader")
        wrong_method = self._assessment(
            claim_id,
            scope_id,
            assessment_id="assessment-wrong-method",
            nonce="assessment-wrong-method-nonce",
            evidence="wrong-method",
            method_id="invented-magic-method",
        )
        with self.assertRaisesRegex(ValueError, "ASSESSOR_CREDENTIAL_NOT_AUTHORIZED"):
            self.world.record_evidence_assessment(claim_id, assessment=wrong_method)

        over_cap = self._assessment(
            claim_id,
            scope_id,
            assessment_id="assessment-over-cap",
            nonce="assessment-over-cap-nonce",
            evidence="over-cap",
            value=1.0,
        )
        with self.assertRaisesRegex(ValueError, "ASSESSOR_COMPONENT_AUTHORITY_EXCEEDED"):
            self.world.record_evidence_assessment(claim_id, assessment=over_cap)

        conflict_claim, conflict_scope = self._claim(
            account_id="controlled-source",
            controller_proof="assessor-controller-independent",
            topic="conflict-of-interest",
        )
        conflict = self._assessment(
            conflict_claim,
            conflict_scope,
            assessment_id="assessment-conflict",
            nonce="assessment-conflict-nonce",
            evidence="conflict",
        )
        with self.assertRaisesRegex(ValueError, "ASSESSOR_CONFLICT_OF_INTEREST"):
            self.world.record_evidence_assessment(conflict_claim, assessment=conflict)

    def test_nonce_replay_semantic_replay_and_explicit_supersession(self) -> None:
        claim_a, scope_a = self._claim(account_id="replay-a", topic="replay-a")
        first = self._assessment(
            claim_a,
            scope_a,
            assessment_id="assessment-first",
            nonce="shared-assessment-nonce",
            evidence="semantic-evidence",
        )
        self.world.record_evidence_assessment(claim_a, assessment=first)

        claim_b, scope_b = self._claim(account_id="replay-b", topic="replay-b")
        nonce_replay = self._assessment(
            claim_b,
            scope_b,
            assessment_id="assessment-replayed-nonce",
            nonce="shared-assessment-nonce",
            evidence="other-evidence",
        )
        with self.assertRaisesRegex(ValueError, "REPLAYED"):
            self.world.record_evidence_assessment(claim_b, assessment=nonce_replay)

        semantic_replay = self._assessment(
            claim_a,
            scope_a,
            assessment_id="assessment-semantic-replay",
            nonce="new-nonce-without-supersedes",
            evidence="semantic-evidence",
            value=0.8,
        )
        with self.assertRaisesRegex(ValueError, "SEMANTIC_REPLAY_REQUIRES_SUPERSEDES"):
            self.world.record_evidence_assessment(claim_a, assessment=semantic_replay)

        replacement = self._assessment(
            claim_a,
            scope_a,
            assessment_id="assessment-replacement",
            nonce="replacement-nonce",
            evidence="semantic-evidence",
            value=0.8,
            supersedes="assessment-first",
        )
        self.world.record_evidence_assessment(claim_a, assessment=replacement)
        store = self.world._plural_store()
        self.assertFalse(store["signed_assessments_v1810"]["assessment-first"]["current_authority"])
        self.assertEqual(
            store["signed_assessments_v1810"]["assessment-first"]["superseded_by"],
            "assessment-replacement",
        )

    def test_counterfactual_mirror_is_a_separate_instance(self) -> None:
        player_id = "mirror-citizen"
        self.world.register_player(player_id, display_name="Mirror Citizen")
        self.world.process_action(player_id, "Я завариваю чай и записываю исходную границу")
        valid_before, count_before, error_before = self.world.memory.verify_chronicle()
        self.assertTrue(valid_before, error_before)
        audit_id = self.world.begin_lived_audit(
            player_id,
            label="Counterfactual isolation",
            git_commit="test-v18.7.10",
            action_script_sha256=sha256_text("mirror-script"),
        )
        mirror, manifest = self.world.fork_counterfactual_world(
            audit_id=audit_id,
            label="trust-neutral-mirror",
        )
        mirror.process_action(player_id, "Я ломаю четвёртую стену только в зеркале")
        valid_after, count_after, error_after = self.world.memory.verify_chronicle()
        self.assertTrue(valid_after, error_after)
        self.assertEqual(count_before + 1, count_after)  # fresh-boundary event only
        mirror_valid, mirror_count, mirror_error = mirror.memory.verify_chronicle()
        self.assertTrue(mirror_valid, mirror_error)
        self.assertGreater(mirror_count, count_after)
        archive = self.world.archive_counterfactual_mirror(
            mirror,
            manifest,
            metrics={"boundary_persistence": 1.0},
        )
        self.assertEqual(archive["classification"], "UNREALIZED_MIRROR")
        self.assertFalse(archive["canonical_mutation_allowed"])
        self.assertFalse(archive["raw_dialogue_in_canonical_archive"])

    def test_social_rupture_ends_relationship_not_actor_life(self) -> None:
        player_id = "rupture-citizen"
        self.world.register_player(player_id, display_name="Rupture Citizen")
        profile = self.world.free_other_state(player_id)["profile"]
        handle = sorted(profile["others"])[0]
        for index in range(3):
            outcome = self.world.record_free_other_value_conflict(
                player_id,
                handle,
                player_position=f"Игрок требует путь {index}",
                other_position=f"Другой сохраняет собственный путь {index}",
                severity=10,
                respected_boundary=False,
                final=index == 2,
            )
        self.assertTrue(outcome["terminated"])
        self.assertEqual(
            outcome["relationship"]["status"], "TERMINATED_BY_OTHER"
        )
        result = self.world.process_action(
            player_id,
            f"Я прошу поговорить @{handle} и вернуть всё как было",
        )
        self.assertEqual(result.status, "OTHER_RELATIONSHIP_TERMINATED")
        for year in range(16):
            self.world.process_action(
                player_id,
                f"Я продолжаю собственную жизнь после разрыва, шаг {year}",
            )
        actor = self.world.free_other_state(player_id)["profile"]["others"][handle]
        self.assertEqual(actor["relationship_state_v1810"]["status"], "TERMINATED_BY_OTHER")
        self.assertGreaterEqual(actor["actor_life_v1810"]["offscreen_progress"], 17)
        self.assertGreaterEqual(len(actor["actor_life_v1810"]["offscreen_events"]), 2)
        graph = self.world._graph()
        types = {node["type"] for node in graph["nodes"]}
        relations = {edge["relation"] for edge in graph["edges"]}
        self.assertIn("SOCIAL_RUPTURE", types)
        self.assertTrue({"PROTECTS", "ENDS", "CONTINUES"}.issubset(relations))

    def test_century_professions_casting_and_trade_preserve_provenance(self) -> None:
        player = "century-player"
        merchant = "merchant-other"
        self.world.advance_sandbox_year(player, years=100)
        professions = [f"Профессия №{index}: постиронический ремесленник" for index in range(50)]
        for index, profession in enumerate(professions):
            self.world.change_profession(
                player,
                profession,
                moral_frame="fictional_amoral_role" if index % 7 == 0 else "fictional_role",
            )
        player_item = self.world.cast_item(
            player,
            name="Левая туфля для кентавра",
            description="Предмет спорит с интерфейсом о том, является ли он правым.",
            rarity=3,
        )
        player_listing = self.world.list_item_for_sale(
            player, player_item["item_id"], price=20
        )
        self.world.buy_market_listing(merchant, player_listing["listing_id"])

        merchant_item = self.world.cast_item(
            merchant,
            name="Квитанция о невозможности продать квитанцию",
            description="Постиронический документ с конечной рыночной стоимостью.",
            rarity=2,
        )
        merchant_listing = self.world.list_item_for_sale(
            merchant, merchant_item["item_id"], price=18
        )
        self.world.buy_market_listing(player, merchant_listing["listing_id"])

        state = self.world.sandbox_state(player)["actor"]
        self.assertEqual(state["age_years"], 118)
        self.assertEqual(len(state["profession_history"]), 50)
        self.assertEqual(state["trades_completed"], 2)
        valid, counts, error = self.world.verify_v1810_state()
        self.assertTrue(valid, error)
        self.assertEqual(counts["sandbox_items"], 2)

    def test_v1810_state_crosses_portable_save_without_private_keys(self) -> None:
        player = "portable-1810"
        self.world.register_player(player, display_name="Portable 1810")
        self.world.process_action(player, "Я проверяю переносимый порог")
        output = self.root.parent / "v1810.genesis-save.json"
        target = self.root.parent / "v1810-restored"
        try:
            result = PortableSaveManager(self.root).export_to(
                output, label="The Bound Assessor and I0 Discipline"
            )
            text = output.read_text(encoding="utf-8")
            self.assertFalse(result["contains_private_keys"])
            self.assertNotIn(self.root_private, text)
            self.assertNotIn(self.assessor_private, text)
            bundle = json.loads(text)
            valid_bundle, count, bundle_error = PortableSaveManager.verify_bundle(bundle)
            self.assertTrue(valid_bundle, bundle_error)
            self.assertGreater(count, 0)
            PortableSaveManager(target).import_bundle(bundle)
            restored = PlayableGenesisV187(target)
            valid, _counts, error = restored.verify_v1810_state()
            self.assertTrue(valid, error)
        finally:
            output.unlink(missing_ok=True)
            if target.exists():
                import shutil
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()
