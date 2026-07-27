from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from genesis_v18_6_playable import PlayableGenesisV186
from tools.build_external_lexicon import build_external_lexicon


class GenesisV186ExternalLexiconTests(unittest.TestCase):
    def _build(self, directory: str):
        root = Path(directory)
        source = root / "mlm_vocab.txt"
        source.write_text("the\n,\n.\nof\nand\nand\n", encoding="utf-8")
        return build_external_lexicon(
            source,
            root / "generated",
            lexicon_id="gift.qatar.character_bert.mlm.en.v1",
            name="Qatar CharacterBERT MLM Lexicon",
            provider="helboukkouri/character-bert",
            source_file="mlm_vocab.txt",
            received_as="Gift from Qatar",
            expected_count=6,
        )

    def test_converter_preserves_source_order_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lexicon_path, manifest_path, manifest = self._build(directory)
            lexicon = json.loads(lexicon_path.read_text(encoding="utf-8"))

            self.assertEqual(lexicon["tokens"], ["the", ",", ".", "of", "and", "and"])
            self.assertEqual(lexicon["tokens"][4], lexicon["tokens"][5])
            self.assertEqual(lexicon["token_count"], 6)
            self.assertTrue(manifest["order_preserved"])
            self.assertTrue(manifest["duplicates_preserved"])
            self.assertTrue(manifest_path.exists())

    def test_registration_creates_one_lexicon_node_not_one_node_per_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, manifest_path, _ = self._build(directory)
            world = PlayableGenesisV186(Path(directory) / "world")
            accepted = world.register_external_lexicon(manifest_path)
            graph = world._graph()

            self.assertEqual(accepted["token_count"], 6)
            self.assertFalse(accepted["vocad_replaced"])
            self.assertEqual(sum(node["type"] == "EXTERNAL_LEXICON" for node in graph["nodes"]), 1)
            self.assertEqual(sum(node["type"] == "TOKEN" for node in graph["nodes"]), 0)
            relations = {edge["relation"] for edge in graph["edges"]}
            self.assertIn("RECEIVED_FROM", relations)
            self.assertIn("SUPPLEMENTS", relations)

    def test_token_is_promoted_only_when_linked_to_a_vocad_concept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, manifest_path, _ = self._build(directory)
            world = PlayableGenesisV186(Path(directory) / "world")
            world.register_external_lexicon(manifest_path)
            result = world.promote_lexicon_token(
                lexicon_id="gift.qatar.character_bert.mlm.en.v1",
                token_id=4,
                token="and",
                concept_id="JANUS.CONNECTION",
                concept_label="Connection",
            )
            graph = world._graph()

            self.assertTrue(result["token_node_id"])
            self.assertEqual(sum(node["type"] == "TOKEN" for node in graph["nodes"]), 1)
            self.assertEqual(sum(node["type"] == "CONCEPT" for node in graph["nodes"]), 1)
            relations = {edge["relation"] for edge in graph["edges"]}
            self.assertIn("CONTAINS", relations)
            self.assertIn("EXPRESSES", relations)
            self.assertEqual(world.external_lexicon_state()["promoted_token_nodes"], 1)

    def test_sorting_or_deduplication_permission_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, manifest = self._build(directory)
            world = PlayableGenesisV186(Path(directory) / "world")
            manifest["indexing"]["sorting_allowed"] = True
            with self.assertRaises(ValueError):
                world.register_external_lexicon(manifest)

    def test_qatar_receipt_records_verified_source_without_public_payload(self) -> None:
        root = Path(__file__).resolve().parents[1]
        receipt = json.loads((root / "lexicons" / "qatar_characterbert_mlm_en_v1.receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "source_materialized_and_verified_redistribution_pending")
        self.assertEqual(receipt["verified_token_count"], 100000)
        self.assertEqual(receipt["source_sha256"], "7af5d55214b16be542f82c7f57cba838a1790c16284edbcb2f5bee9f8d98bec3")
        self.assertFalse(receipt["redistribution"]["source_file_bundled"])
        self.assertFalse(receipt["redistribution"]["generated_tokens_bundled"])


if __name__ == "__main__":
    unittest.main()
