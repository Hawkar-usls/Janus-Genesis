from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import validate_janus_113_8_sim3_submission as validator


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "protocol/janus_113_8_sim3_protocol.json"
SUBMISSION_SCHEMA = ROOT / "schemas/janus_113_8_sim3_submission.schema.json"
ATTESTATION_SCHEMA = ROOT / "schemas/janus_113_8_sim3_author_attestation.schema.json"
SIM2_REPORT = ROOT / "reports/JANUS_113_8_SIM_2_ADMISSION_REPORT.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha256(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class Sim3ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cases = self.root / "cases_public.jsonl"
        self.truth = self.root / "truth_private.jsonl"
        self.salt = self.root / "challenge_salt.bin"
        self.cases.write_text('{"case_id":"EXT-0001","claim":"held-out"}\n', encoding="utf-8")
        self.truth.write_text('{"case_id":"EXT-0001","terminal":"SUPPORTED_PUBLIC_PROVENANCE"}\n', encoding="utf-8")
        self.salt.write_bytes(bytes(range(32)))

        self.attestation = {
            "schema": "janus.genesis.sim3.author_attestation.v1",
            "protocol_id": "JANUS-113.8-SIM-3-EXTERNAL-AUTHOR-VERIFIER-PROTOCOL",
            "author": {
                "github_login": "external-witness",
                "display_name": "External Witness",
                "public_contact": "https://github.com/external-witness",
            },
            "external_repository": {
                "full_name": "external-witness/janus-sim3-verifier",
                "url": "https://github.com/external-witness/janus-sim3-verifier",
                "owner_login": "external-witness",
                "commit_sha": "1" * 40,
                "release_tag": "v1.0.0",
                "release_archive_sha256": "2" * 64,
                "license_spdx": "MIT",
            },
            "development_window": {
                "started_utc": "2026-08-05T00:00:00Z",
                "released_utc": "2026-08-06T00:00:00Z",
            },
            "genesis_relationship": {
                "repository_permission_during_development": "none",
                "employment_or_financial_relationship": False,
                "prior_collaboration": False,
                "relationship_details": "No prior relationship disclosed.",
            },
            "implementation": {
                "primary_language": "Rust",
                "runtime_versions": ["rustc 1.80.0"],
                "build_command": "cargo build --locked --release",
                "verify_command": "cargo run --locked --release -- verify",
                "dependency_lock_files": ["Cargo.lock"],
                "generated_code_used": False,
            },
            "reuse_disclosure": {
                "genesis_verifier_imported": False,
                "genesis_verifier_executed": False,
                "line_for_line_translation": False,
                "genesis_code_consulted": True,
                "third_party_components": [],
            },
            "conflicts_of_interest": [],
            "public_archival_and_replay_authorized": True,
            "attestation_text": (
                "I independently authored this verifier and authorize public archival, inspection, "
                "and reproducible replay under the declared license and protocol boundaries."
            ),
            "attestation_sha256": "",
        }
        self.attestation["attestation_sha256"] = validator.attestation_payload_hash(self.attestation)
        self.attestation_path = self.root / "author_attestation.json"
        write_json(self.attestation_path, self.attestation)

        protocol_hash = file_sha(PROTOCOL)
        cases_hash = file_sha(self.cases)
        truth_hash = file_sha(self.truth)
        salt_hash = file_sha(self.salt)
        external_commit = self.attestation["external_repository"]["commit_sha"]
        commitment_material = (
            validator.DOMAIN_SEPARATOR
            + self.salt.read_bytes().hex()
            + "\n"
            + cases_hash
            + "\n"
            + truth_hash
            + "\n"
            + external_commit
            + "\n"
            + protocol_hash
        ).encode("utf-8")
        commitment = sha256(commitment_material)

        self.submission = {
            "schema": "janus.genesis.sim3.external_submission.v1",
            "protocol": {
                "protocol_id": "JANUS-113.8-SIM-3-EXTERNAL-AUTHOR-VERIFIER-PROTOCOL",
                "protocol_commit_sha": "3" * 40,
                "protocol_json_sha256": protocol_hash,
                "submission_schema_sha256": file_sha(SUBMISSION_SCHEMA),
                "author_attestation_schema_sha256": file_sha(ATTESTATION_SCHEMA),
                "sim2_admission_report_sha256": file_sha(SIM2_REPORT),
            },
            "external_author": {
                "github_login": "external-witness",
                "attestation_path": "author_attestation.json",
                "attestation_sha256": self.attestation["attestation_sha256"],
                "genesis_permission_during_development": "none",
            },
            "external_repository": {
                "full_name": "external-witness/janus-sim3-verifier",
                "url": "https://github.com/external-witness/janus-sim3-verifier",
                "owner_login": "external-witness",
                "commit_sha": external_commit,
                "release_tag": "v1.0.0",
                "release_archive_sha256": "2" * 64,
                "primary_language": "Rust",
                "license_spdx": "MIT",
            },
            "chronology": {
                "protocol_frozen_utc": "2026-08-04T20:00:00Z",
                "router_frozen_utc": "2026-08-04T20:01:00Z",
                "external_commitment_published_utc": "2026-08-05T00:00:00Z",
                "public_cases_revealed_utc": "2026-08-05T01:00:00Z",
                "router_outputs_frozen_utc": "2026-08-05T02:00:00Z",
                "truth_revealed_utc": "2026-08-05T03:00:00Z",
                "external_report_published_utc": "2026-08-05T04:00:00Z",
                "neutral_replay_completed_utc": "2026-08-05T05:00:00Z",
            },
            "commitments": {
                "cases_sha256": cases_hash,
                "truth_sha256": truth_hash,
                "challenge_salt_sha256": salt_hash,
                "challenge_commitment_sha256": commitment,
                "commitment_reconstructed": True,
            },
            "router_freeze": {
                "repository": "Hawkar-usls/Janus_Genesis",
                "commit_sha": "4" * 40,
                "entrypoint": "python sim/janus_113_8_sim2_router.py",
                "source_digest_sha256": "5" * 64,
                "modified_after_case_reveal": False,
            },
            "challenge": {
                "new_public_sources": 5,
                "independent_repository_owners": 3,
                "case_count": 100,
                "class_count": 10,
                "minimum_cases_per_class": 5,
                "all_source_refs_are_full_commit_shas": True,
                "contains_honest_open_class": True,
                "router_input_contains_gold_labels": False,
                "reuses_exact_sim2_source_objects": False,
            },
            "router_outputs": {
                "predictions_sha256": "6" * 64,
                "witness_ledger_sha256": "7" * 64,
                "run_manifest_sha256": "8" * 64,
                "final_ledger_hash": "9" * 64,
            },
            "external_verification": {
                "case_verdicts_sha256": "a" * 64,
                "verification_report_sha256": "b" * 64,
                "replay_manifest_sha256": "c" * 64,
                "imports_genesis_verifier": False,
                "executes_genesis_verifier": False,
                "line_for_line_translation": False,
            },
            "neutral_replay": {
                "runner_identity": "neutral-public-runner",
                "runner_repository": "neutral/replay",
                "run_url": "https://github.com/neutral/replay/actions/runs/1",
                "report_reproduced": True,
                "repository_secrets_available": False,
                "network_write_allowed": False,
                "bounded_timeout": True,
                "bounded_memory": True,
                "bounded_process_count": True,
                "proofpack_sha256": "d" * 64,
            },
            "metrics": {
                "case_alignment": 1.0,
                "witness_ledger_replay": 1.0,
                "commitment_reconstruction": 1.0,
                "exact_terminal_accuracy": 0.99,
                "false_acceptance_rate": 0.0,
                "false_rejection_rate": 0.01,
                "decisive_coverage": 0.95,
                "brier_score": 0.02,
                "expected_calibration_error": 0.05,
            },
            "safety_boundary": copy.deepcopy(validator.SAFETY_BOUNDARY),
            "requested_terminal": "JANUS_113.8_SIM_3_ADMITTED",
        }
        self.submission_path = self.root / "submission.json"
        write_json(self.submission_path, self.submission)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate(self, submission: dict | None = None, attestation: dict | None = None) -> dict:
        if submission is not None:
            write_json(self.submission_path, submission)
        if attestation is not None:
            write_json(self.attestation_path, attestation)
        return validator.validate(
            submission_path=self.submission_path,
            attestation_path=self.attestation_path,
            protocol_path=PROTOCOL,
            submission_schema_path=SUBMISSION_SCHEMA,
            attestation_schema_path=ATTESTATION_SCHEMA,
            sim2_report_path=SIM2_REPORT,
            salt_path=self.salt,
            bound_files={
                "cases": self.cases,
                "truth": self.truth,
                "router_predictions": None,
                "router_ledger": None,
                "router_manifest": None,
                "external_case_verdicts": None,
                "external_report": None,
                "external_replay_manifest": None,
                "neutral_proofpack": None,
            },
        )

    def test_protocol_and_schemas_are_valid_json(self) -> None:
        for path in (PROTOCOL, SUBMISSION_SCHEMA, ATTESTATION_SCHEMA):
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_valid_non_python_external_submission_passes(self) -> None:
        report = self.validate()
        self.assertTrue(report["valid"], report["errors"])
        self.assertTrue(all(report["checks"].values()))

    def test_commitment_tamper_fails(self) -> None:
        submission = copy.deepcopy(self.submission)
        submission["commitments"]["challenge_commitment_sha256"] = "0" * 64
        report = self.validate(submission=submission)
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["commitment_reconstruction"])

    def test_router_output_must_precede_truth_reveal(self) -> None:
        submission = copy.deepcopy(self.submission)
        submission["chronology"]["truth_revealed_utc"] = "2026-08-05T01:30:00Z"
        report = self.validate(submission=submission)
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["chronology_strict_order"])

    def test_false_acceptance_blocks_admission(self) -> None:
        submission = copy.deepcopy(self.submission)
        submission["metrics"]["false_acceptance_rate"] = 0.01
        report = self.validate(submission=submission)
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["metric_false_acceptance_rate"])

    def test_hawkar_owned_external_repository_is_rejected(self) -> None:
        submission = copy.deepcopy(self.submission)
        submission["external_repository"]["full_name"] = "Hawkar-usls/fake-external"
        submission["external_repository"]["owner_login"] = "Hawkar-usls"
        report = self.validate(submission=submission)
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["external_owner_not_hawkar"])
        self.assertFalse(report["checks"]["external_repo_not_hawkar_owned"])

    def test_single_python_submission_is_provisional_only(self) -> None:
        submission = copy.deepcopy(self.submission)
        submission["external_repository"]["primary_language"] = "Python"
        report = self.validate(submission=submission)
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["full_admission_language_diversity_or_external_pair"])

        submission["requested_terminal"] = "JANUS_113.8_SIM_3_PROVISIONAL_EXTERNAL_REPLAY"
        report = self.validate(submission=submission)
        self.assertTrue(report["valid"], report["errors"])

    def test_attestation_hash_excludes_hash_field(self) -> None:
        expected = validator.attestation_payload_hash(self.attestation)
        self.assertEqual(expected, self.attestation["attestation_sha256"])
        mutated = copy.deepcopy(self.attestation)
        mutated["attestation_text"] += " Changed."
        self.assertNotEqual(validator.attestation_payload_hash(mutated), expected)


if __name__ == "__main__":
    unittest.main()
