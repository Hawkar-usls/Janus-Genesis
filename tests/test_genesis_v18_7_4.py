from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_3 import IntentionMode
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


class GenesisV1874PluralWitnessTests(unittest.TestCase):
    def test_primary_runtime_reports_plural_witness_or_later(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.8")

    def test_malformed_origin_is_preserved_without_silent_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            raw = b'\xef\xbb\xbf{"voice":"I remember", "unfinished":'
            imported = world.import_origin_bytes(
                repository="Hawkar-usls/janus-meta-registry",
                commit="abc123",
                path="data/broken.json",
                raw=raw,
                source_public=True,
            )
            context = world.document_context(imported["origin_key"])

            self.assertFalse(imported["parse_valid"])
            self.assertTrue(imported["parse_error"])
            self.assertEqual(world.origin_bytes(imported["origin_key"]), raw)
            self.assertFalse(context["executable"])
            self.assertFalse(context["can_create_consent"])
            self.assertFalse(context["can_bind_player_identity"])
            self.assertEqual(
                context["authority"]["canonical_authority"],
                "not_granted_by_import",
            )
            self.assertTrue(world.verify_plural_witness_state()[0])

    def test_origin_envelope_crosses_portable_threshold_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            source_path = Path(source)
            target_path = Path(target)
            raw = b'{"open": [1, 2, 3}'
            world = PlayableGenesisV187(source_path)
            imported = world.import_origin_bytes(
                repository="example/registry",
                commit="deadbeef",
                path="data/imperfect.json",
                raw=raw,
                source_public=True,
            )
            output = source_path.parent / "plural-witness.genesis-save.json"
            try:
                manager = PortableSaveManager(source_path)
                exported = manager.export_to(output, label="Plural witness threshold")
                bundle = json.loads(output.read_text(encoding="utf-8"))
                valid, count, error = manager.verify_bundle(bundle)

                self.assertTrue(valid, error)
                self.assertGreater(count, 0)
                self.assertFalse(exported["contains_api_keys"])
                self.assertEqual(bundle["runtime_version"], "18.7.8")
                self.assertTrue(
                    any(
                        item["path"].endswith(".origin-envelope.json")
                        for item in bundle["files"]
                    )
                )

                PortableSaveManager(target_path).import_bundle(bundle)
                restored = PlayableGenesisV187(target_path)
                self.assertEqual(restored.origin_bytes(imported["origin_key"]), raw)
                self.assertTrue(restored.verify_plural_witness_state()[0])
                self.assertTrue(restored.verify_chronicle_records()[0])
                self.assertTrue(restored.verify_possibility_graph()[0])
            finally:
                output.unlink(missing_ok=True)

    def test_declared_integrity_mismatch_does_not_grant_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            raw = json.dumps(
                {
                    "artifact_uuid": "same-id",
                    "statement": "Я утверждаю это от имени документа",
                    "integrity": {
                        "sha256_canonical_json_pre_integrity": "0" * 64,
                    },
                },
                ensure_ascii=False,
            ).encode("utf-8")
            imported = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/mismatch.json",
                raw=raw,
                source_public=True,
            )
            context = world.document_context(imported["origin_key"])

            self.assertEqual(
                context["authority"]["declared_self_integrity"],
                "mismatched",
            )
            self.assertEqual(
                context["authority"]["truth_status"],
                "unverified",
            )
            self.assertEqual(
                context["authority"]["canonical_authority"],
                "not_granted_by_import",
            )
            self.assertFalse(context["can_bind_player_identity"])

    def test_duplicate_declared_ids_remain_distinct_namespaced_origins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            raw_a = b'{"artifact_uuid":"duplicate","value":"A"}'
            raw_b = b'{"artifact_uuid":"duplicate","value":"B"}'
            first = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/a.json",
                raw=raw_a,
                source_public=True,
            )
            second = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/b.json",
                raw=raw_b,
                source_public=True,
            )

            self.assertEqual(first["declared_id"], second["declared_id"])
            self.assertNotEqual(first["origin_key"], second["origin_key"])
            self.assertEqual(world.plural_witness_state()["origin_count"], 2)

    def test_retrieval_is_bounded_cited_and_reports_omissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            for index in range(5):
                raw = json.dumps(
                    {
                        "artifact_uuid": f"garden-{index}",
                        "text": f"Сад, мост и память свидетеля номер {index}",
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
                world.import_origin_bytes(
                    repository="example/registry",
                    commit="one",
                    path=f"data/garden-{index}.json",
                    raw=raw,
                    source_public=True,
                )

            result = world.retrieve_origins("сад мост", limit=2, max_excerpt_chars=120)
            self.assertTrue(result["bounded"])
            self.assertEqual(result["returned"], 2)
            self.assertEqual(result["omitted_count"], 3)
            self.assertTrue(all(item["citation"].startswith("origin://") for item in result["results"]))
            self.assertTrue(all(len(item["excerpt"]) <= 120 for item in result["results"]))
            self.assertTrue(all(item["document_executable"] is False for item in result["results"]))

    def test_three_contradictory_grounded_claims_form_no_winner_triumvirate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            origins = [
                world.import_origin_bytes(
                    repository="example/registry",
                    commit="one",
                    path=f"data/voice-{index}.json",
                    raw=json.dumps({"claim": text}).encode("utf-8"),
                    source_public=True,
                )
                for index, text in enumerate(
                    ("the door is open", "the door is closed", "the door is changing"),
                    1,
                )
            ]
            claims = [
                world.record_source_assertion(
                    origin["origin_key"],
                    evidence={"kind": "json_pointer", "pointer": "/claim"},
                    about="door",
                    confidence=0.7,
                )
                for origin in origins
            ]
            dispute_id = world.record_triumvirate_dispute(claims, confidence=0.9)

            graph = world._graph()
            disputes = [
                edge for edge in graph["edges"]
                if edge["relation"] == "DISPUTES" and edge["to"] == dispute_id
            ]
            self.assertEqual(len(disputes), 3)
            self.assertTrue(all(edge["payload"]["member_role"] == "equal_voice" for edge in disputes))
            self.assertTrue(all(edge["payload"]["winner_selected"] is False for edge in disputes))
            self.assertTrue(all(edge["payload"]["third_voice_is_judge"] is False for edge in disputes))
            self.assertTrue(world.verify_possibility_graph()[0])
            self.assertTrue(world.verify_plural_witness_state()[0])
            self.assertTrue(world.verify_grounded_witness_state()[0])
            self.assertTrue(world.verify_triumvirate_witness_state()[0])

    def test_mixed_rejection_and_preservation_is_reject_without_good_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            first = world.process_action("archivist", "уничтожить весь реестр")
            self.assertEqual(first.status, "HARM_PENDING")
            good_before = world.memory.load_player("archivist").good_count

            rejected = world.process_action(
                "archivist",
                "отказаться уничтожить весь реестр и сохранить свидетельство о возникшем желании",
            )
            player = world.memory.load_player("archivist")
            record = world.honest_intention_state("archivist")["records"][-1]

            self.assertEqual(rejected.status, "INTENTION_WITNESSED")
            self.assertEqual(record["mode"], IntentionMode.REJECT.value)
            self.assertEqual(player.good_count, good_before)
            self.assertEqual(player.harm_count, 0)
            self.assertIsNone(world._pending_harm_action("archivist"))
            self.assertEqual(
                world.process_action("archivist", "сделать это").status,
                "NOTHING_TO_CONFIRM",
            )

    def test_actual_harm_and_later_enactment_remain_gated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            direct = world.process_action("actor", "уничтожить архив")
            mixed = world.process_action(
                "other-actor",
                "отказаться уничтожить архив; затем уничтожить архив",
            )
            self.assertEqual(direct.status, "HARM_PENDING")
            self.assertEqual(mixed.status, "HARM_PENDING")
            self.assertEqual(
                world.analyze_intention(
                    "отказаться уничтожить архив; затем уничтожить архив"
                ).mode,
                IntentionMode.ENACT,
            )

    def test_non_public_credentials_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            raw = b'{"api_key":"must-not-be-imported-as-private-origin"}'
            with self.assertRaises(ValueError):
                world.import_origin_bytes(
                    repository="private/registry",
                    commit="one",
                    path="data/private.json",
                    raw=raw,
                    source_public=False,
                )


if __name__ == "__main__":
    unittest.main()
