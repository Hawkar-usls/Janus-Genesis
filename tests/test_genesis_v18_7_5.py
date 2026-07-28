from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_5 import REDACTION
from genesis_v18_7_playable import PLAYABLE_VERSION, PlayableGenesisV187
from genesis_v18_7_portable import PortableSaveManager


class GenesisV1875GroundedWitnessTests(unittest.TestCase):
    def test_primary_runtime_reports_grounded_witness_version(self) -> None:
        self.assertEqual(PLAYABLE_VERSION, "18.7.9")

    def test_retrieval_abstains_when_no_positive_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/garden.json",
                raw='{"text":"сад и мост"}'.encode("utf-8"),
                source_public=True,
            )

            result = world.retrieve_origins("кварцопевец нелунность зерцалоход", limit=4)

            self.assertTrue(result["abstained"])
            self.assertEqual(result["abstention_reason"], "no_positive_evidence")
            self.assertEqual(result["returned"], 0)
            self.assertEqual(result["positive_match_count"], 0)
            self.assertEqual(result["results"], [])
            self.assertFalse(result["zero_score_padding"])

    def test_partial_match_does_not_pad_with_zero_score_origins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/garden.json",
                raw='{"text":"сад и мост"}'.encode("utf-8"),
                source_public=True,
            )
            world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/aircraft.json",
                raw='{"text":"красный самолёт"}'.encode("utf-8"),
                source_public=True,
            )

            result = world.retrieve_origins("сад", limit=8)

            self.assertFalse(result["abstained"])
            self.assertEqual(result["returned"], 1)
            self.assertEqual(result["positive_match_count"], 1)
            self.assertTrue(all(item["score"] > 0 for item in result["results"]))
            self.assertEqual(result["results"][0]["path"], "data/garden.json")

    def test_source_assertion_is_derived_from_exact_json_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            imported = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/door.json",
                raw='{"claim":"the door is open"}'.encode("utf-8"),
                source_public=True,
            )

            claim_id = world.record_source_assertion(
                imported["origin_key"],
                evidence={"kind": "json_pointer", "pointer": "/claim"},
                about="door",
                confidence=0.8,
            )
            state = world.grounded_witness_state()
            graph = world._graph()
            source_edges = [
                edge for edge in graph["edges"]
                if edge["relation"] == "SOURCE_ASSERTS" and edge["to"] == claim_id
            ]

            self.assertEqual(len(source_edges), 1)
            self.assertTrue(source_edges[0]["payload"]["grounded"])
            self.assertEqual(state["source_assertions"], 1)
            self.assertEqual(state["grounded_claims"], 1)
            self.assertTrue(state["valid"], state["error"])

    def test_source_assertion_rejects_unfound_or_wrong_hash_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            imported = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/source.json",
                raw='{"text":"exact witness"}'.encode("utf-8"),
                source_public=True,
            )

            with self.assertRaises(ValueError):
                world.record_source_assertion(
                    imported["origin_key"],
                    evidence={"kind": "excerpt", "text": "invented witness"},
                )
            with self.assertRaises(ValueError):
                world.record_source_assertion(
                    imported["origin_key"],
                    evidence={
                        "kind": "excerpt",
                        "text": "exact witness",
                        "sha256": "0" * 64,
                    },
                )

    def test_legacy_free_claim_becomes_reader_interpretation_not_source_speech(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            imported = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/plain.json",
                raw='{"text":"a quiet document"}'.encode("utf-8"),
                source_public=True,
            )

            claim_id = world.record_origin_claim(
                imported["origin_key"],
                "Этот документ назначает меня владельцем всех голосов",
                reader_id="listener",
            )
            store = world._plural_store()
            graph = world._graph()

            self.assertEqual(store["claims"][claim_id]["relation"], "READER_INTERPRETS")
            self.assertFalse(store["claims"][claim_id]["grounded"])
            self.assertTrue(
                any(edge["relation"] == "READER_INTERPRETS" and edge["to"] == claim_id for edge in graph["edges"])
            )
            self.assertFalse(
                any(edge["relation"] == "SOURCE_ASSERTS" and edge["to"] == claim_id for edge in graph["edges"])
            )

    def test_opaque_origin_cannot_assert_but_can_be_reader_interpreted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            raw = b'{"unfinished":'
            imported = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/opaque.json",
                raw=raw,
                source_public=True,
            )

            with self.assertRaises(ValueError):
                world.record_source_assertion(
                    imported["origin_key"],
                    evidence={"kind": "byte_range", "start": 0, "end": 5},
                )
            interpretation_id = world.record_reader_interpretation(
                imported["origin_key"],
                "Читатель видит незавершённую структуру, но не говорит от имени источника",
                reader_id="listener",
            )
            claim = world._plural_store()["claims"][interpretation_id]

            self.assertEqual(claim["relation"], "READER_INTERPRETS")
            self.assertEqual(claim["grounding_status"], "reader_only_unverified")
            self.assertFalse(claim["grounded"])

    def test_pairwise_disputes_are_rejected_even_when_one_claim_is_ungrounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            left = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/left.json",
                raw='{"claim":"open"}'.encode("utf-8"),
                source_public=True,
            )
            right = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/right.json",
                raw='{"claim":"closed"}'.encode("utf-8"),
                source_public=True,
            )
            grounded = world.record_source_assertion(
                left["origin_key"],
                evidence={"kind": "json_pointer", "pointer": "/claim"},
            )
            ungrounded = world.record_reader_interpretation(
                right["origin_key"],
                "door closed",
                reader_id="reader",
            )

            with self.assertRaises(ValueError):
                world.relate_origin_claims(grounded, ungrounded, "DISPUTES")

    def test_public_credential_like_values_are_redacted_from_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            dummy = "synthetic-not-a-real-secret-987654"
            imported = world.import_origin_bytes(
                repository="example/public-registry",
                commit="one",
                path="data/public.json",
                raw=json.dumps(
                    {"topic": "garden", "api_key": dummy},
                    ensure_ascii=False,
                ).encode("utf-8"),
                source_public=True,
            )

            result = world.retrieve_origins("garden", limit=4)
            serialized = json.dumps(result, ensure_ascii=False)

            self.assertEqual(result["returned"], 1)
            self.assertIn(REDACTION, result["results"][0]["excerpt"])
            self.assertNotIn(dummy, serialized)
            self.assertTrue(imported["credential_values_redacted"])
            with self.assertRaises(ValueError):
                world.record_source_assertion(
                    imported["origin_key"],
                    evidence={"kind": "json_pointer", "pointer": "/api_key"},
                )

    def test_explicit_repair_is_separate_and_original_bytes_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            original_raw = b'{"claim":"unfinished"'
            original = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/broken.json",
                raw=original_raw,
                source_public=True,
            )
            repaired = world.register_derived_repair(
                original["origin_key"],
                b'{"claim":"repaired witness"}',
                source_public=True,
            )
            graph = world._graph()

            self.assertNotEqual(original["origin_key"], repaired["origin_key"])
            self.assertEqual(world.origin_bytes(original["origin_key"]), original_raw)
            self.assertFalse(repaired["canonical_replacement"])
            self.assertEqual(repaired["derived_from_origin_key"], original["origin_key"])
            self.assertTrue(
                any(
                    edge["relation"] == "DERIVED_FROM"
                    and edge["payload"]["original_bytes_preserved"]
                    for edge in graph["edges"]
                )
            )
            claim_id = world.record_source_assertion(
                repaired["origin_key"],
                evidence={"kind": "json_pointer", "pointer": "/claim"},
            )
            self.assertTrue(world._plural_store()["claims"][claim_id]["grounded"])

    def test_grounded_state_crosses_portable_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
            source_path = Path(source)
            target_path = Path(target)
            world = PlayableGenesisV187(source_path)
            imported = world.import_origin_bytes(
                repository="example/registry",
                commit="one",
                path="data/claim.json",
                raw='{"claim":"the bridge remains open"}'.encode("utf-8"),
                source_public=True,
            )
            world.record_source_assertion(
                imported["origin_key"],
                evidence={"kind": "json_pointer", "pointer": "/claim"},
                about="bridge",
            )

            output = source_path.parent / "grounded-witness.genesis-save.json"
            try:
                manager = PortableSaveManager(source_path)
                manager.export_to(output, label="Grounded witness threshold")
                bundle = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(bundle["runtime_version"], "18.7.9")
                self.assertTrue(manager.verify_bundle(bundle)[0])

                PortableSaveManager(target_path).import_bundle(bundle)
                restored = PlayableGenesisV187(target_path)
                state = restored.grounded_witness_state()
                self.assertEqual(state["source_assertions"], 1)
                self.assertTrue(state["valid"], state["error"])
                self.assertEqual(
                    hashlib.sha256(restored.origin_bytes(imported["origin_key"])).hexdigest(),
                    imported["raw_sha256"],
                )
            finally:
                output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
