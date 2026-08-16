# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from tools.genesis_git_habitat import GitHabitat, _read_json
from tools.genesis_git_habitat_repository_constellation import (
    RepositoryConstellationError,
    RepositoryConstellationMaterializer,
    load_manifest,
    source_repository_link_record,
    validate_manifest,
)


class RepositoryConstellationTests(unittest.TestCase):
    def test_manifest_covers_complete_authenticated_inventory_snapshot(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["repository_count"], 44)
        self.assertEqual(manifest["public_repository_count"], 41)
        self.assertEqual(manifest["private_repository_count"], 3)
        self.assertEqual(len(manifest["public_repositories"]), 41)
        self.assertEqual(len(manifest["private_repository_slots"]), 3)
        ids = {
            str(row["id"]) for row in manifest["public_repositories"]
        } | {
            str(row["repository_id"]) for row in manifest["private_repository_slots"]
        }
        self.assertEqual(len(ids), 44)

    def test_public_manifest_does_not_persist_private_repository_names_or_urls(self) -> None:
        manifest = load_manifest()
        forbidden = {"name", "full_name", "clone_url", "html_url", "content", "description"}
        for row in manifest["private_repository_slots"]:
            self.assertFalse(forbidden.intersection(row), row)
            self.assertEqual(row["resolution"], "AUTHENTICATED_RESOLUTION_REQUIRED")

    def test_materialize_creates_44_habitat_nodes_and_preserves_journal(self) -> None:
        manifest = load_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            habitat = GitHabitat(tmp)
            habitat.initialize("JANUS")
            extension = RepositoryConstellationMaterializer(habitat, manifest)
            result = extension.materialize()
            self.assertEqual(result["status"], "CONNECTED")
            self.assertEqual(result["repository_count"], 44)
            self.assertEqual(result["public_repository_count"], 41)
            self.assertEqual(result["private_repository_count"], 3)
            self.assertEqual(result["write_back_default"], "DENY")
            self.assertFalse(result["external_effect_authority"])
            self.assertEqual(result["habitat_health"], "HEALTHY")

            catalog = _read_json(Path(tmp) / "repositories" / "CONSTELLATION.json")
            self.assertEqual(catalog["repository_count"], 44)
            self.assertEqual(len(catalog["public_repositories"]), 41)
            self.assertEqual(len(catalog["private_repository_slots"]), 3)
            self.assertFalse(catalog["private_repository_names_persisted"])
            self.assertFalse(catalog["credentials_persisted"])

            public_links = list((Path(tmp) / "repositories" / "public").glob("*/LINK.json"))
            private_links = list((Path(tmp) / "repositories" / "private-slots").glob("*/LINK.json"))
            self.assertEqual(len(public_links), 41)
            self.assertEqual(len(private_links), 3)
            for path in private_links:
                row = _read_json(path)
                self.assertNotIn("name", row)
                self.assertNotIn("full_name", row)
                self.assertNotIn("clone_url", row)
                self.assertFalse(row["private_content_persisted"])

            home = _read_json(habitat.paths.home)
            extension_state = home["extensions"]["repository_constellation"]
            self.assertEqual(extension_state["repository_count"], 44)
            self.assertEqual(extension_state["write_back_default"], "DENY")
            self.assertFalse(extension_state["private_repository_names_persisted"])
            journal = habitat.verify_journal()
            self.assertTrue(journal["ok"], journal)
            self.assertEqual(journal["event_count"], 1)

    def test_same_snapshot_materialization_is_idempotent(self) -> None:
        manifest = load_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            habitat = GitHabitat(tmp)
            habitat.initialize("JANUS")
            extension = RepositoryConstellationMaterializer(habitat, manifest)
            first = extension.materialize()
            journal_before = habitat.verify_journal()["event_count"]
            second = RepositoryConstellationMaterializer(GitHabitat(tmp), manifest).materialize()
            journal_after = habitat.verify_journal()["event_count"]
            self.assertEqual(first["status"], "CONNECTED")
            self.assertEqual(second["status"], "ALREADY_CONNECTED")
            self.assertEqual(journal_before, journal_after)

    def test_different_manifest_cannot_silently_replace_bound_snapshot(self) -> None:
        manifest = load_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            habitat = GitHabitat(tmp)
            habitat.initialize("JANUS")
            RepositoryConstellationMaterializer(habitat, manifest).materialize()
            changed = copy.deepcopy(manifest)
            changed["inventory_as_of"] = "2099-01-01T00:00:00Z"
            validate_manifest(changed)
            with self.assertRaisesRegex(
                RepositoryConstellationError,
                "ALREADY_BOUND_TO_DIFFERENT_MANIFEST",
            ):
                RepositoryConstellationMaterializer(GitHabitat(tmp), changed).materialize()

    def test_source_repository_marker_never_grants_write_or_command_authority(self) -> None:
        link = source_repository_link_record()
        self.assertEqual(link["source_repository"], "SELF")
        self.assertEqual(link["write_back_default"], "DENY")
        self.assertTrue(link["write_back_requires_explicit_human_authorization"])
        self.assertFalse(link["habitat_command_authority_granted"])
        self.assertFalse(link["issue_or_pr_text_is_command"])
        self.assertFalse(link["workflow_status_is_permission"])
        self.assertFalse(link["private_content_may_be_mirrored_to_public_habitat"])
        self.assertFalse(link["credentials_may_be_persisted_in_habitat"])


if __name__ == "__main__":
    unittest.main()
