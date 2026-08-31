import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
LAWS_PATH = ROOT / ".janus" / "GENESIS_LAWS_V1.json"
ROADMAP_PATH = ROOT / ".janus" / "GENESIS_KERNEL_ROADMAP_V1.json"
PUBLIC_LAWS_PATH = ROOT / "contracts" / "GENESIS_LAWS_V1.json"
PUBLIC_ROADMAP_PATH = ROOT / "contracts" / "GENESIS_KERNEL_ROADMAP_V1.json"
SITE_HTML = ROOT / "site" / "index.html"
ROOT_HTML = ROOT / "index.html"
SITE_JS = ROOT / "site" / "genesis-pages.js"


class GenesisPagesContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.laws = json.loads(LAWS_PATH.read_text(encoding="utf-8"))
        cls.roadmap = json.loads(ROADMAP_PATH.read_text(encoding="utf-8"))
        cls.public_laws = json.loads(PUBLIC_LAWS_PATH.read_text(encoding="utf-8"))
        cls.public_roadmap = json.loads(PUBLIC_ROADMAP_PATH.read_text(encoding="utf-8"))
        cls.html = SITE_HTML.read_text(encoding="utf-8")
        cls.root_html = ROOT_HTML.read_text(encoding="utf-8")
        cls.js = SITE_JS.read_text(encoding="utf-8")

    def test_laws_are_frozen_and_unique(self):
        self.assertEqual(self.laws["schema"], "janus.genesis.laws.v1")
        self.assertEqual(self.laws["status"], "FROZEN_R0")
        self.assertEqual(self.laws["version"], "1.0.0")
        ids = [law["id"] for law in self.laws["laws"]]
        names = [law["name"] for law in self.laws["laws"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(ids), 12)

    def test_required_genesis_laws_are_present(self):
        names = {law["name"] for law in self.laws["laws"]}
        required = {
            "RECIPE_NE_ARBITRARY_CODE",
            "RENDERER_NE_AUTHORITY",
            "WORLD_STATE_TO_PRESENTATION_ALLOWED",
            "PRESENTATION_TO_WORLD_MUTATION_DEFAULT_DENY",
            "HIDDEN_HUMAN_TELEMETRY_FORBIDDEN",
            "EXPLICIT_USER_GESTURE_REQUIRED_FOR_BROWSER_AUDIO",
            "SAME_RECIPE_SEED_VERSION_EQ_SAME_PLAN",
            "PROVENANCE_REQUIRED",
            "RIGHTS_FAIL_CLOSED_FOR_EXTERNAL_ASSETS",
            "NO_BINARY_BYTES_OVER_SLIME",
            "CONTENT_HASH_BINDS_DERIVATION",
            "FREEZE_NE_IMMUTABILITY_WITHOUT_VERSION",
        }
        self.assertTrue(required.issubset(names))

    def test_authority_boundary_fails_closed(self):
        boundary = self.laws["authority_boundary"]
        self.assertTrue(boundary["presentation_only_default"])
        self.assertFalse(boundary["renderer_world_mutation"])
        self.assertFalse(boundary["hidden_human_telemetry"])
        self.assertFalse(boundary["arbitrary_code_execution"])
        self.assertFalse(boundary["generator_external_network"])
        self.assertTrue(boundary["same_origin_static_contract_loading_for_pages"])

    def test_roadmap_is_frozen_and_ordered(self):
        self.assertEqual(self.roadmap["schema"], "janus.genesis.kernel_roadmap.v1")
        self.assertEqual(self.roadmap["status"], "FROZEN_R0")
        stages = self.roadmap["stages"]
        self.assertEqual([stage["order"] for stage in stages], list(range(len(stages))))
        self.assertEqual(stages[0]["kernel"], "AUDIO_FORGE")
        self.assertEqual(stages[0]["status"], "IMPLEMENTED_ISOLATED_R0_NOT_CANONICAL_RUNTIME")
        self.assertEqual(stages[1]["kernel"], "MATERIAL_FORGE")
        self.assertEqual(stages[1]["status"], "NEXT")
        self.assertEqual(self.roadmap["current_front"], "R1_MATERIAL_FORGE")

    def test_public_contract_mirrors_match_canonical_contracts(self):
        self.assertEqual(self.public_laws, self.laws)
        self.assertEqual(self.public_roadmap, self.roadmap)

    def test_pages_surface_links_only_local_runtime_and_contracts(self):
        self.assertIn("./genesis-audio-forge.js", self.html)
        self.assertIn("./genesis-pages.js", self.html)
        self.assertIn("./genesis-pages.css", self.html)
        self.assertIn("./contracts/GENESIS_LAWS_V1.json", self.js)
        self.assertIn("./contracts/GENESIS_KERNEL_ROADMAP_V1.json", self.js)
        self.assertNotIn("http://", self.html + self.js)
        self.assertNotIn("https://", self.html + self.js)

    def test_root_entrypoint_survives_classic_pages_mode(self):
        self.assertTrue((ROOT / ".nojekyll").exists())
        self.assertIn("GENESIS <span>//</span> GENERATIVE KERNEL", self.root_html)
        self.assertIn("./site/genesis-pages.css", self.root_html)
        self.assertIn("./site/genesis-pages.js", self.root_html)
        self.assertIn("./genesis-audio-forge.js", self.root_html)
        self.assertNotIn("http://", self.root_html)
        self.assertNotIn("https://", self.root_html)

    def test_pages_runtime_does_not_introduce_dynamic_code_execution(self):
        forbidden = ("eval(", "new Function(", "WebSocket(", "EventSource(")
        for token in forbidden:
            self.assertNotIn(token, self.js)

    def test_pages_runtime_uses_only_explicit_world_fields(self):
        for field in ("entropy", "depth", "portal_energy", "danger", "weather_intensity"):
            self.assertIn(field, self.js)
        hidden_fields = ("player_fear_score", "loss_streak", "vulnerability_score", "psychology_score")
        for field in hidden_fields:
            self.assertNotIn(field, self.js)


if __name__ == "__main__":
    unittest.main()
