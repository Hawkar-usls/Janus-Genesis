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
ROOT_LAB_HTML = ROOT / "kernel-lab.html"
SITE_LAB_HTML = ROOT / "site" / "kernel-lab.html"
LAB_JS = ROOT / "site" / "genesis-pages.js"
HISTORICAL_WORLD_JS = ROOT / "site" / "genesis-world-shell-v2.js"
R02_WORLD_JS = ROOT / "site" / "genesis-world-runtime-v3.js"
R02_BRIDGE_JS = ROOT / "site" / "genesis-janus-bridge-v1.js"
R03_WORLD_JS = ROOT / "site" / "genesis-world-runtime-v4.js"
R03_BRIDGE_JS = ROOT / "site" / "genesis-command-bridge-v3.js"
FULL_RUNTIME_CONTRACT = ROOT / ".janus" / "GENESIS_FULL_RUNTIME_V1.json"
COMMAND_RUNTIME_CONTRACT = ROOT / ".janus" / "GENESIS_COMMAND_RUNTIME_R0_3.json"


class GenesisPagesContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.laws = json.loads(LAWS_PATH.read_text(encoding="utf-8"))
        cls.roadmap = json.loads(ROADMAP_PATH.read_text(encoding="utf-8"))
        cls.public_laws = json.loads(PUBLIC_LAWS_PATH.read_text(encoding="utf-8"))
        cls.public_roadmap = json.loads(PUBLIC_ROADMAP_PATH.read_text(encoding="utf-8"))
        cls.site_html = SITE_HTML.read_text(encoding="utf-8")
        cls.root_html = ROOT_HTML.read_text(encoding="utf-8")
        cls.root_lab_html = ROOT_LAB_HTML.read_text(encoding="utf-8")
        cls.site_lab_html = SITE_LAB_HTML.read_text(encoding="utf-8")
        cls.lab_js = LAB_JS.read_text(encoding="utf-8")
        cls.historical_world_js = HISTORICAL_WORLD_JS.read_text(encoding="utf-8")
        cls.r02_world_js = R02_WORLD_JS.read_text(encoding="utf-8")
        cls.r02_bridge_js = R02_BRIDGE_JS.read_text(encoding="utf-8")
        cls.r03_world_js = R03_WORLD_JS.read_text(encoding="utf-8")
        cls.r03_bridge_js = R03_BRIDGE_JS.read_text(encoding="utf-8")
        cls.full_runtime = json.loads(FULL_RUNTIME_CONTRACT.read_text(encoding="utf-8"))
        cls.command_runtime = json.loads(COMMAND_RUNTIME_CONTRACT.read_text(encoding="utf-8"))

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
        required = {"RECIPE_NE_ARBITRARY_CODE", "RENDERER_NE_AUTHORITY", "WORLD_STATE_TO_PRESENTATION_ALLOWED", "PRESENTATION_TO_WORLD_MUTATION_DEFAULT_DENY", "HIDDEN_HUMAN_TELEMETRY_FORBIDDEN", "EXPLICIT_USER_GESTURE_REQUIRED_FOR_BROWSER_AUDIO", "SAME_RECIPE_SEED_VERSION_EQ_SAME_PLAN", "PROVENANCE_REQUIRED", "RIGHTS_FAIL_CLOSED_FOR_EXTERNAL_ASSETS", "NO_BINARY_BYTES_OVER_SLIME", "CONTENT_HASH_BINDS_DERIVATION", "FREEZE_NE_IMMUTABILITY_WITHOUT_VERSION"}
        self.assertTrue(required.issubset(names))

    def test_authority_boundary_fails_closed(self):
        boundary = self.laws["authority_boundary"]
        self.assertTrue(boundary["presentation_only_default"])
        self.assertFalse(boundary["renderer_world_mutation"])
        self.assertFalse(boundary["hidden_human_telemetry"])
        self.assertFalse(boundary["arbitrary_code_execution"])
        self.assertFalse(boundary["generator_external_network"])
        self.assertTrue(boundary["same_origin_static_contract_loading_for_pages"])

    def test_original_kernel_roadmap_remains_frozen(self):
        self.assertEqual(self.roadmap["schema"], "janus.genesis.kernel_roadmap.v1")
        self.assertEqual(self.roadmap["status"], "FROZEN_R0")
        stages = self.roadmap["stages"]
        self.assertEqual([stage["order"] for stage in stages], list(range(len(stages))))
        self.assertEqual(stages[0]["kernel"], "AUDIO_FORGE")
        self.assertEqual(stages[1]["kernel"], "MATERIAL_FORGE")
        self.assertEqual(self.roadmap["current_front"], "R1_MATERIAL_FORGE")

    def test_public_frozen_contract_mirrors_match_canonical_contracts(self):
        self.assertEqual(self.public_laws, self.laws)
        self.assertEqual(self.public_roadmap, self.roadmap)

    def test_root_and_actions_entrypoints_use_superseding_command_runtime(self):
        self.assertTrue((ROOT / ".nojekyll").exists())
        self.assertEqual(self.full_runtime["schema"], "janus.genesis.full_runtime.v1")
        self.assertEqual(self.command_runtime["schema"], "janus.genesis.command_runtime.v1")
        self.assertEqual(self.command_runtime["version"], "0.3.0")
        for html in (self.root_html, self.site_html):
            self.assertIn("TEXT-NATIVE WORLD ENGINE", html)
            self.assertIn("genesis-world-runtime-v4.js", html)
            self.assertIn("genesis-command-bridge-v3.js", html)
            self.assertIn("genesis-asset-materializer-v2.js", html)
            self.assertNotIn("genesis-world-shell-v2.js", html)
            self.assertNotIn("genesis-action-input-ru.js", html)
            self.assertNotIn('id="mirror-panel"', html)
        self.assertIn("./site/world-shell.css", self.root_html)
        self.assertIn("./world-shell.css", self.site_html)
        self.assertIn("./genesis-audio-forge.js", self.root_html)
        self.assertIn("./genesis-audio-forge.js", self.site_html)
        self.assertTrue(HISTORICAL_WORLD_JS.exists())
        self.assertTrue(R02_WORLD_JS.exists())
        self.assertTrue(R02_BRIDGE_JS.exists())

    def test_network_isolated_to_explicit_command_bridge_not_world_generator(self):
        for world in (self.r02_world_js, self.r03_world_js):
            self.assertNotIn("http://", world)
            self.assertNotIn("https://", world)
            self.assertNotIn("fetch(", world)
        self.assertIn("fetch(", self.r03_bridge_js)
        self.assertIn("/v1/health", self.r03_bridge_js)
        self.assertIn("/v1/genesis/intent", self.r03_bridge_js)
        self.assertFalse(self.command_runtime["authority"]["janus_response_is_world_authority"])
        self.assertTrue(self.command_runtime["authority"]["genesis_validator_required"])

    def test_kernel_lab_preserves_original_control_plane(self):
        self.assertIn("GENESIS // KERNEL LAB", self.root_lab_html)
        self.assertIn("GENESIS // KERNEL LAB", self.site_lab_html)
        self.assertIn("./site/genesis-pages.css", self.root_lab_html)
        self.assertIn("./site/genesis-pages.js", self.root_lab_html)
        self.assertIn("./genesis-pages.css", self.site_lab_html)
        self.assertIn("./genesis-pages.js", self.site_lab_html)

    def test_kernel_lab_loads_only_same_origin_frozen_contracts(self):
        self.assertIn("./contracts/GENESIS_LAWS_V1.json", self.lab_js)
        self.assertIn("./contracts/GENESIS_KERNEL_ROADMAP_V1.json", self.lab_js)
        self.assertNotIn("http://", self.lab_js)
        self.assertNotIn("https://", self.lab_js)

    def test_pages_runtimes_do_not_introduce_dynamic_code_execution(self):
        forbidden = ("eval(", "new Function(", "WebSocket(", "EventSource(")
        for token in forbidden:
            for surface in (self.lab_js, self.historical_world_js, self.r02_world_js, self.r02_bridge_js, self.r03_world_js, self.r03_bridge_js):
                self.assertNotIn(token, surface)

    def test_kernel_lab_uses_only_explicit_audio_world_fields(self):
        for field in ("entropy", "depth", "portal_energy", "danger", "weather_intensity"):
            self.assertIn(field, self.lab_js)


if __name__ == "__main__":
    unittest.main()
