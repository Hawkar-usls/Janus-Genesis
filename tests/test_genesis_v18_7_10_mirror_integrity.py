from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class GenesisV18710MirrorIsolationIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = PlayableGenesisV187(self.root)
        self.world.set_free_other_seed_for_testing("mirror-integrity-tests")
        self.world.register_player("witness", display_name="Witness")
        self.handle = sorted(
            self.world.free_other_state("witness")["profile"]["others"]
        )[0]
        self.audit_id = self.world.begin_lived_audit(
            "witness",
            label="mirror integrity tests",
            git_commit="test-commit",
            action_script_sha256=sha256_text("mirror-integrity-script"),
        )

    def test_mirror_root_must_be_disjoint_from_canonical_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "MIRROR_ROOT_MUST_BE_DISJOINT"):
            self.world.fork_counterfactual_world(
                audit_id=self.audit_id,
                label="invalid nested mirror",
                mirror_root=self.root / "nested-mirror",
            )

    def test_counterfactual_trust_intervention_is_forbidden_in_canon(self) -> None:
        with self.assertRaisesRegex(PermissionError, "REQUIRES_MIRROR"):
            self.world.set_counterfactual_actor_trust_for_probe(
                "witness",
                self.handle,
                trust_percent=95,
                reason_code="CANON_MUST_REJECT",
            )

    def test_verified_mirror_archives_numeric_metrics_and_removes_working_copy(self) -> None:
        mirror, manifest = self.world.fork_counterfactual_world(
            audit_id=self.audit_id,
            label="verified branch",
        )
        root = Path(manifest["root"])
        intervention = mirror.set_counterfactual_actor_trust_for_probe(
            "witness",
            self.handle,
            trust_percent=95,
            reason_code="TEST_MATCHED_TRUST",
        )
        self.assertEqual(intervention["after"], 0.95)
        mirror.process_action(
            "witness",
            f"предложить @{self.handle} пройти один проверочный мост",
        )
        archive = self.world.archive_counterfactual_mirror(
            mirror,
            manifest,
            metrics={"contact_realized": 1.0, "boundary_preserved": True},
        )
        self.assertTrue(archive["isolation_verified"])
        self.assertTrue(archive["working_copy_removed"])
        self.assertFalse(root.exists())
        self.assertEqual(archive["metric_contract"], "flat_finite_numeric_v1")
        self.assertEqual(archive["metrics"]["boundary_preserved"], 1.0)
        self.assertNotIn(manifest["mirror_id"], self.world._i0_store()["active_mirrors"])

    def test_raw_text_cannot_enter_canonical_mirror_metrics(self) -> None:
        mirror, manifest = self.world.fork_counterfactual_world(
            audit_id=self.audit_id,
            label="privacy rejection branch",
        )
        try:
            with self.assertRaisesRegex(TypeError, "MIRROR_METRIC_MUST_BE_NUMERIC"):
                self.world.archive_counterfactual_mirror(
                    mirror,
                    manifest,
                    metrics={"raw_dialogue": "private branch text"},
                )
        finally:
            shutil.rmtree(Path(manifest["root"]), ignore_errors=True)

    def test_canonical_progress_during_probe_fails_closed(self) -> None:
        mirror, manifest = self.world.fork_counterfactual_world(
            audit_id=self.audit_id,
            label="contamination detector branch",
        )
        try:
            self.world.process_action(
                "witness", "изменить канонический мир пока зеркало ещё открыто"
            )
            with self.assertRaisesRegex(
                RuntimeError, "CANONICAL_STATE_CHANGED_DURING_MIRROR_PROBE"
            ):
                self.world.archive_counterfactual_mirror(
                    mirror,
                    manifest,
                    metrics={"contact_realized": 0.0},
                )
            failed = self.world._i0_store()["mirror_archives"][manifest["mirror_id"]]
            self.assertEqual(failed["status"], "FAIL_CLOSED_CANONICAL_CONTAMINATION")
            self.assertFalse(failed["isolation_verified"])
        finally:
            shutil.rmtree(Path(manifest["root"]), ignore_errors=True)

    def test_butterfly_witness_requires_repeated_directional_delta(self) -> None:
        stable = self.world.butterfly_witness(
            audit_id=self.audit_id,
            subject="stable matched delta",
            canonical_metrics={"contact_realized": 0.0},
            mirror_metrics=[
                {"contact_realized": 1.0},
                {"contact_realized": 1.0},
                {"contact_realized": 1.0},
            ],
            repeated_windows=3,
        )
        self.assertEqual(stable["verdict"], "PROMOTE_TO_REGRESSION")
        self.assertEqual(stable["stable_metric_keys"], ["contact_realized"])

        unstable = self.world.butterfly_witness(
            audit_id=self.audit_id,
            subject="direction changes",
            canonical_metrics={"effect": 0.0},
            mirror_metrics=[{"effect": 1.0}, {"effect": -1.0}],
            repeated_windows=2,
        )
        self.assertEqual(unstable["verdict"], "ANECDOTE_ONLY")
        self.assertEqual(unstable["stable_metric_keys"], [])


if __name__ == "__main__":
    unittest.main()
