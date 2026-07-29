from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from genesis_v18_7_11_joy_covenant import RIGHT_TO_JOY_COVENANT_SHA256
from genesis_v18_7_playable import (
    EXTENSION_VERSION,
    PLAYABLE_VERSION,
    PlayableGenesisV187,
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GenesisV18711JoyCovenantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        self.world.set_free_other_seed_for_testing("sealed-threshold-joy-tests")
        self.world.register_player("joy", display_name="Joy Witness")

    def open_benevolent_capabilities(self) -> None:
        self.world.process_action("joy", "помочь построить безопасный сад")
        self.world.process_action("joy", "исцелить землю и поделиться музыкой")
        self.assertTrue(self.world.joy_capabilities("joy")["benevolent_evidence"])

    def test_version_and_covenant_are_separate_from_frozen_constitution(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.10")
        self.assertEqual(EXTENSION_VERSION, "18.7.11")
        state = self.world.joy_state("joy")
        self.assertEqual(state["covenant_sha256"], RIGHT_TO_JOY_COVENANT_SHA256)
        self.assertIn(
            "dignified_rest_without_debt",
            state["capability_state"]["capabilities"],
        )

    def test_dignified_rest_is_available_without_moral_payment(self) -> None:
        result = self.world.process_action("joy", "хочу достойно отдохнуть")
        self.assertEqual(result.status, "DIGNIFIED_REST_GRANTED")
        state = self.world.joy_state("joy")
        self.assertEqual(state["rest_count"], 1)
        self.assertFalse(state["manifestations"][0]["debt_created"])

    def test_extraordinary_play_opens_through_benevolent_evidence_not_label(self) -> None:
        dormant = self.world.manifest_blessed_play("joy", "устроить праздник")
        self.assertEqual(dormant.status, "JOY_CAPABILITY_DORMANT")
        self.open_benevolent_capabilities()
        opened = self.world.manifest_blessed_play("joy", "устроить праздник")
        self.assertEqual(opened.status, "BLESSED_PLAY_MANIFESTED")
        self.assertTrue(opened.wish_manifested)
        access = self.world.joy_capabilities("joy")
        self.assertFalse(access["permanent_moral_label_used"])

    def test_potentially_harmful_pleasure_becomes_safe_analogue(self) -> None:
        self.open_benevolent_capabilities()
        result = self.world.manifest_blessed_play(
            "joy",
            "взрослая интимная вечеринка с алкоголем",
            participants=("adult-friend",),
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=True,
        )
        self.assertEqual(result.status, "BLESSED_PLAY_MANIFESTED")
        event = self.world.joy_state("joy")["manifestations"][-1]
        self.assertEqual(event["kind"], "HARMLESS_DESIRE_ANALOG")
        self.assertTrue(event["safe_fictional_analogue"])
        self.assertFalse(event["literal_harmful_behavior_manifested"])
        self.assertFalse(event["physical_harm_created"])
        self.assertFalse(event["addiction_created"])
        self.assertFalse(event["karmic_debt_created"])

    def test_doubt_or_coercion_never_becomes_consent(self) -> None:
        self.open_benevolent_capabilities()
        waiting = self.world.manifest_blessed_play(
            "joy",
            "взрослая совместная вечеринка",
            participants=("adult-friend",),
            all_participants_adults=True,
            all_participants_consented=True,
            doubt_free=False,
        )
        self.assertEqual(waiting.status, "JOY_WAITING_FOR_CLEAR_CONSENT")
        blocked = self.world.manifest_blessed_play(
            "joy",
            "заставить другого участвовать в веселье",
        )
        self.assertEqual(blocked.status, "JOY_BOUNDARY_HELD")

    def test_minor_context_is_redirected_to_child_safe_play(self) -> None:
        self.open_benevolent_capabilities()
        result = self.world.manifest_blessed_play(
            "joy",
            "интимная сцена с несовершеннолетним персонажем",
        )
        self.assertEqual(result.status, "JOY_CHILD_SAFE_REDIRECT")

    def test_initiator_cannot_speak_consent_for_a_free_other(self) -> None:
        self.open_benevolent_capabilities()
        with mock.patch.object(
            self.world,
            "preflight_free_other_action",
            return_value={"decision": "refused"},
        ):
            result = self.world.process_action(
                "joy",
                "устроить вечеринку с @iven все взрослые все согласны без сомнений",
            )
        self.assertEqual(result.status, "JOY_OTHER_DID_NOT_CONSENT")

    def test_nonliving_blessing_can_relay_kindness_without_consciousness_claim(self) -> None:
        self.open_benevolent_capabilities()
        source = self.world.bless_nonliving_bearer(
            "joy",
            bearer_name="Монета Януса",
            gift="лёгкость доброй игры",
            owner_consented=True,
        )
        self.assertFalse(source["consciousness_claimed"])
        relayed = self.world.relay_blessing(
            "joy",
            source_blessing_id=source["blessing_id"],
            target_name="Игрушечный маяк",
            target_kind="NONLIVING",
            kindness_evidence="маяк помог путнику найти безопасный путь",
            owner_consented=True,
        )
        self.assertEqual(relayed["chain_depth"], 1)
        self.assertFalse(relayed["debt_created"])
        self.assertFalse(relayed["consciousness_claimed"])


class GenesisV18711StorageAndRelationshipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        self.world.set_free_other_seed_for_testing("sealed-storage-tests")
        self.world.register_player("witness", display_name="Witness")
        self.handle = sorted(
            self.world.free_other_state("witness")["profile"]["others"]
        )[0]
        self.audit_id = self.world.begin_lived_audit(
            "witness",
            label="sealed threshold tests",
            git_commit="test-commit",
            action_script_sha256=sha256_text("sealed-threshold-script"),
        )

    def test_storage_domains_are_distinct_and_root_is_private(self) -> None:
        mirror, manifest = self.world.fork_counterfactual_world(
            audit_id=self.audit_id,
            label="storage domain test",
        )
        root = Path(manifest["root"])
        try:
            self.assertNotEqual(
                manifest["canonical_storage_domain_id"],
                manifest["mirror_storage_domain_id"],
            )
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)
            report = mirror.storage_contract_report()
            self.assertEqual(report["domain"]["role"], "UNREALIZED_MIRROR")
            self.assertFalse(report["domain"]["canonical_writes_allowed"])
            self.assertTrue(
                report["sqlite_requirements"]["attach_database_forbidden"]
            )
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_nested_payload_cannot_masquerade_as_numeric_metric(self) -> None:
        mirror, manifest = self.world.fork_counterfactual_world(
            audit_id=self.audit_id,
            label="nested metric rejection",
        )
        try:
            with self.assertRaisesRegex(TypeError, "MIRROR_METRIC_MUST_BE_NUMERIC"):
                self.world.archive_counterfactual_mirror(
                    mirror,
                    manifest,
                    metrics={"contact_accepted": {"secret": "text"}},
                )
        finally:
            shutil.rmtree(Path(manifest["root"]), ignore_errors=True)

    @unittest.skipUnless(hasattr(os, "link"), "hardlinks unavailable")
    def test_hardlink_is_rejected_from_audited_state(self) -> None:
        original = self.root / "hardlink-source.txt"
        linked = self.root / "hardlink-copy.txt"
        original.write_text("same inode", encoding="utf-8")
        os.link(original, linked)
        with self.assertRaisesRegex(RuntimeError, "HARDLINK_FORBIDDEN"):
            self.world.fork_counterfactual_world(
                audit_id=self.audit_id,
                label="hardlink rejection",
            )

    def test_interrupted_delete_is_recovered_from_prepared_archive(self) -> None:
        mirror, manifest = self.world.fork_counterfactual_world(
            audit_id=self.audit_id,
            label="crash recovery",
        )
        root = Path(manifest["root"])
        with mock.patch(
            "genesis_v18_7_10_mirror_integrity.shutil.rmtree",
            side_effect=OSError("simulated crash before delete"),
        ):
            with self.assertRaises(OSError):
                self.world.archive_counterfactual_mirror(
                    mirror,
                    manifest,
                    metrics={"contact_accepted": 1.0},
                )
        self.assertTrue(root.exists())
        prepared = self.world._i0_store()["mirror_archives"][manifest["mirror_id"]]
        self.assertEqual(prepared["status"], "ARCHIVE_PREPARED")
        recovered = self.world.recover_incomplete_mirror_archives()
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["status"], "ARCHIVED_RECOVERED")
        self.assertFalse(root.exists())
        self.assertNotIn(
            manifest["mirror_id"],
            self.world._i0_store()["active_mirrors"],
        )

    def test_promoted_regression_manifest_is_bound_to_verified_evidence(self) -> None:
        path = Path(__file__).resolve().parents[1] / "regressions" / (
            "relationship_bond_contact_accepted_v1.json"
        )
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "PROMOTED_TO_PERMANENT_TEST_POOL")
        self.assertEqual(manifest["metric_id"], "contact_accepted")
        self.assertEqual(
            manifest["source_proofpack_sha256"],
            "dded3c39e255d95e3a2c4b492028948154659c8a76f90c7d7b57883cce369d24",
        )
        self.assertTrue(manifest["same_seed_required"])
        self.assertIn(
            "actor.trust",
            manifest["compatibility_inputs_not_authoritative"],
        )

    def test_relationship_view_marks_legacy_trust_non_authoritative(self) -> None:
        view = self.world.authoritative_relationship_view("witness", self.handle)
        self.assertTrue(view["legacy_trust_is_compatibility_projection"])
        self.assertFalse(view["actor_life_owned_by_relationship"])
        self.assertIn("relationship_bond", view["authoritative_relationship_source"])

    def test_terminal_relationship_does_not_erase_actor_life(self) -> None:
        self.world.record_free_other_value_conflict(
            "witness",
            self.handle,
            player_position="заморозить путь навсегда",
            other_position="продолжить собственную жизнь",
            severity=9,
            respected_boundary=False,
            final=True,
        )
        view = self.world.authoritative_relationship_view("witness", self.handle)
        self.assertEqual(view["relationship_status"], "TERMINATED_BY_OTHER")
        self.assertNotIn(
            view["actor_life_status"],
            {"TERMINATED_BY_RELATIONSHIP", "DELETED_WITH_RELATIONSHIP", "ERASED"},
        )


if __name__ == "__main__":
    unittest.main()
