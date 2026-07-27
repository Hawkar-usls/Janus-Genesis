from __future__ import annotations

import json
import unittest
from pathlib import Path


class LegacyOriginsAndVocabMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_legacy_manifest_seals_nine_sources_without_public_secrets(self) -> None:
        path = self.root / "origins" / "2025-legacy-genesis-hypnos-sources" / "LEGACY_SOURCE_MANIFEST.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["sources"]), 9)
        self.assertFalse(data["policy"]["raw_sources_publicly_bundled"])
        self.assertFalse(data["policy"]["embedded_secrets_publicly_bundled"])
        self.assertFalse(data["policy"]["runtime_auto_import"])
        self.assertTrue(all(len(item["original_sha256"]) == 64 for item in data["sources"]))
        self.assertTrue(all(not item["public_source_code_bundled"] for item in data["sources"]))
        self.assertNotIn("AIza", path.read_text(encoding="utf-8"))

    def test_vocab_source_is_materialized_and_order_sealed(self) -> None:
        path = self.root / "lexicons" / "qatar_characterbert_mlm_en_v1.materialized.manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["token_count"], 100000)
        self.assertEqual(data["source_size_bytes"], 807732)
        self.assertEqual(data["source_sha256"], "7af5d55214b16be542f82c7f57cba838a1790c16284edbcb2f5bee9f8d98bec3")
        self.assertEqual(data["generated_sha256"], "083f631c906b36a64e3ef35412e9b0a1d388be2657b791eab3d636ecc5c3a1d3")
        self.assertEqual(data["first_tokens"][:5], ["the", ",", ".", "of", "and"])
        self.assertEqual(data["last_tokens"][-3:], ["jut", "kurth", "atocha"])
        self.assertEqual(data["empty_token_count"], 0)
        self.assertTrue(data["order_preserved"])
        self.assertFalse(data["redistribution"]["tokens_embedded_in_repository"])

    def test_receipt_no_longer_claims_source_is_missing(self) -> None:
        path = self.root / "lexicons" / "qatar_characterbert_mlm_en_v1.receipt.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "source_materialized_and_verified_redistribution_pending")
        self.assertEqual(data["verified_token_count"], 100000)
        self.assertFalse(data["vocad_replaced"])
        self.assertFalse(data["redistribution"]["source_file_bundled"])
        self.assertFalse(data["redistribution"]["generated_tokens_bundled"])


if __name__ == "__main__":
    unittest.main()
