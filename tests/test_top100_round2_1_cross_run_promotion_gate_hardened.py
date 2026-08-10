# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools import run_top100_round2_1_cross_run_promotion_gate as core
from tools import run_top100_round2_1_cross_run_promotion_gate_hardened as hard

CONFIG_PATH = core.REPOSITORY_ROOT / "benchmarks/round2_1_cross_run_promotion_gate_v0.1.json"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def authenticated_metadata():
    return {
        "schema": "janus.genesis.github_actions_source_authentication.v1",
        "repository": "Hawkar-usls/Janus_Genesis",
        "fetched_live": True,
        "sources": [
            {
                "workflow_run_id": 31349156794,
                "run_head_sha": "81898c0f4ee09d1b530e3cc1c38ecdd993d4d9c9",
                "run_status": "completed",
                "run_conclusion": "success",
                "run_event": "pull_request",
                "artifact_id": 9048707870,
                "artifact_name": "janus-top100-round2-1-capability-admission",
                "artifact_digest": "sha256:1561a538076b8907326353f71a0e644987d77484e11f760f114fa029062daff6",
                "artifact_expired": False,
                "artifact_size_in_bytes": 12454,
                "artifact_workflow_run_id": 31349156794,
                "artifact_workflow_head_sha": "81898c0f4ee09d1b530e3cc1c38ecdd993d4d9c9",
            },
            {
                "workflow_run_id": 31352475058,
                "run_head_sha": "692f88dd2bccf211487e9c675a981fc530d81095",
                "run_status": "completed",
                "run_conclusion": "success",
                "run_event": "pull_request",
                "artifact_id": 9049984941,
                "artifact_name": "janus-top100-round2-1-capability-admission",
                "artifact_digest": "sha256:0f85f51a0114ca7f2dd8d14f0244db63c63e3e7bc23b10aae79baf60da631213",
                "artifact_expired": False,
                "artifact_size_in_bytes": 13338,
                "artifact_workflow_run_id": 31352475058,
                "artifact_workflow_head_sha": "692f88dd2bccf211487e9c675a981fc530d81095",
            },
        ],
    }


class HardenedCrossRunPromotionTests(unittest.TestCase):
    def test_clean_hardened_gate_blocks_q8_and_authenticates_two_sources(self):
        receipt = hard.evaluate_hardened(load_config(), authenticated_metadata())
        self.assertEqual(hard.HARDENED_SCHEMA, receipt["schema"])
        self.assertTrue(receipt["independence_authenticated_against_github_actions"])
        self.assertTrue(receipt["critical_trial_profile_verification"]["candidate_key_set_equals_frozen_profile"])
        self.assertEqual(8, receipt["critical_trial_profile_verification"]["critical_sample_count"])
        self.assertEqual(3, receipt["critical_trial_profile_verification"]["replays_per_sample"])
        self.assertEqual(24, receipt["critical_trial_profile_verification"]["expected_trial_count"])
        self.assertEqual(2, receipt["github_source_authentication"]["source_count"])
        self.assertTrue(receipt["github_source_authentication"]["distinct_workflow_run_ids"])
        self.assertTrue(receipt["github_source_authentication"]["distinct_artifact_ids"])
        self.assertTrue(receipt["github_source_authentication"]["distinct_raw_report_sha256"])
        self.assertFalse(receipt["promotion"]["authoritative_runtime_promoted"])
        self.assertEqual("FP16", receipt["promotion"]["selected_runtime_representation"])
        self.assertEqual("BLOCKED_BY_HISTORICAL_NEGATIVE_EVIDENCE", receipt["promotion"]["decision"])

    def test_substituted_unique_trial_key_is_rejected(self):
        cfg = load_config()
        evidence, _ = core.load_evidence(cfg)
        profile = hard.load_frozen_critical_profile(cfg)
        bad = copy.deepcopy(evidence)
        bad["receipts"][0]["candidate_records"][0]["sample_id"] = "not-a-frozen-critical-sample"
        with self.assertRaisesRegex(ValueError, "do not equal frozen critical sample/replay profile"):
            hard.validate_exact_critical_trial_profiles(bad, profile)

    def test_missing_replay_key_replaced_by_another_unique_key_is_rejected(self):
        cfg = load_config()
        evidence, _ = core.load_evidence(cfg)
        profile = hard.load_frozen_critical_profile(cfg)
        bad = copy.deepcopy(evidence)
        row = bad["receipts"][1]["candidate_records"][0]
        row["replay"] = 99
        with self.assertRaisesRegex(ValueError, "do not equal frozen critical sample/replay profile"):
            hard.validate_exact_critical_trial_profiles(bad, profile)

    def test_fake_run_head_is_rejected_by_authenticated_metadata(self):
        metadata = authenticated_metadata()
        metadata["sources"][1]["run_head_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "head SHA is not authenticated"):
            hard.validate_authenticated_independence(load_config(), metadata)

    def test_fake_artifact_digest_is_rejected_by_authenticated_metadata(self):
        metadata = authenticated_metadata()
        metadata["sources"][0]["artifact_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "artifact digest is not authenticated"):
            hard.validate_authenticated_independence(load_config(), metadata)

    def test_artifact_must_be_bound_to_same_workflow_run(self):
        metadata = authenticated_metadata()
        metadata["sources"][0]["artifact_workflow_run_id"] = 31352475058
        with self.assertRaisesRegex(ValueError, "artifact is not bound"):
            hard.validate_authenticated_independence(load_config(), metadata)

    def test_duplicate_raw_report_identity_cannot_count_as_independent(self):
        cfg = load_config()
        cfg["source_reports"][1]["report_json_sha256"] = cfg["source_reports"][0]["report_json_sha256"]
        with self.assertRaisesRegex(ValueError, "reuse report_json_sha256"):
            hard.validate_authenticated_independence(cfg, authenticated_metadata())

    def test_duplicate_artifact_identity_cannot_count_as_independent(self):
        cfg = load_config()
        cfg["source_reports"][1]["artifact_id"] = cfg["source_reports"][0]["artifact_id"]
        metadata = authenticated_metadata()
        metadata["sources"][1]["artifact_id"] = cfg["source_reports"][0]["artifact_id"]
        with self.assertRaisesRegex(ValueError, "reuse artifact_id"):
            hard.validate_authenticated_independence(cfg, metadata)


if __name__ == "__main__":
    unittest.main()