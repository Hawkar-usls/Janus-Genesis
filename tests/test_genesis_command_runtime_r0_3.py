import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".janus" / "GENESIS_COMMAND_RUNTIME_R0_3.json"
PUBLIC = ROOT / "contracts" / "GENESIS_COMMAND_RUNTIME_R0_3.json"
WORLD = ROOT / "site" / "genesis-world-runtime-v4.js"
BRIDGE = ROOT / "site" / "genesis-command-bridge-v3.js"
MATERIAL = ROOT / "site" / "genesis-asset-materializer-v2.js"
HOTKEYS = ROOT / "site" / "genesis-hotkeys-v2.js"
CSS = ROOT / "site" / "runtime-v4.css"
ROOT_HTML = ROOT / "index.html"
SITE_HTML = ROOT / "site" / "index.html"


class GenesisCommandRuntimeR03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.public = json.loads(PUBLIC.read_text(encoding="utf-8"))
        cls.world = WORLD.read_text(encoding="utf-8")
        cls.bridge = BRIDGE.read_text(encoding="utf-8")
        cls.material = MATERIAL.read_text(encoding="utf-8")
        cls.hotkeys = HOTKEYS.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")
        cls.root_html = ROOT_HTML.read_text(encoding="utf-8")
        cls.site_html = SITE_HTML.read_text(encoding="utf-8")

    def test_public_contract_is_exact_mirror(self):
        self.assertEqual(self.public, self.contract)
        self.assertEqual(self.contract["version"], "0.3.0")
        self.assertTrue(self.contract["command_console"]["primary_interface"])

    def test_r03_runtime_remains_loaded_as_lineage_under_active_r04_overlay(self):
        for html in (self.root_html, self.site_html):
            self.assertIn("SCENE INTENT GRAPH R0.4", html)
            self.assertIn("genesis-world-runtime-v4.js", html)
            self.assertIn("genesis-command-bridge-v3.js", html)
            self.assertIn("genesis-scene-graph-executor-r0-4.js", html)
            self.assertIn("genesis-command-bridge-v4.js", html)
            self.assertIn("genesis-asset-materializer-v2.js", html)
            self.assertIn("genesis-hotkeys-v2.js", html)
            self.assertIn("runtime-v4.css", html)
            self.assertNotIn('id="mirror-panel"', html)
            self.assertNotIn('id="mirror-toggle"', html)
            self.assertIn('id="action-input"', html)
            self.assertIn("<textarea", html)
        self.assertFalse(self.contract["command_console"]["mirror_modal_required"])

    def test_enter_focus_submit_escape_blur_and_hotkey_isolation(self):
        console = self.contract["command_console"]
        self.assertTrue(console["global_enter_focuses_console"])
        self.assertTrue(console["enter_submits_when_focused"])
        self.assertTrue(console["escape_blurs"])
        self.assertTrue(console["text_input_never_leaks_to_gameplay_hotkeys"])
        for token in (
            "e.key==='Enter'&&!textTarget(e.target)",
            "e.key==='Enter'&&!e.shiftKey",
            "e.key==='Escape'",
            "input.blur()",
            "e.stopPropagation()",
        ):
            self.assertIn(token, self.bridge)
        self.assertNotIn("mirror-panel", self.hotkeys)

    def test_generic_text_authoring_has_bounded_fallback(self):
        generic = self.contract["generic_authoring"]
        self.assertTrue(generic["unknown_build_nouns_use_generic_structure_recipe"])
        self.assertTrue(generic["unknown_spawn_nouns_use_generic_entity_recipe"])
        self.assertTrue(generic["unsupported_semantics_return_visible_reason"])
        for token in (
            "generic_structure", "SPAWN_ENTITY", "GENERATE_STRUCTURE", "SET_ATMOSPHERE",
            "WORLD_TRANSFORM", "INSPECT", "LOCAL_DEGRADED_NEEDS_JANUS_SEMANTIC_COMPILER",
            "Genesis did not mutate the world",
        ):
            self.assertIn(token, self.bridge)

    def test_spawn_castle_is_structure_not_generic_entity(self):
        self.assertIn("const STRUCTURES=", self.bridge)
        self.assertIn("(has(text,LEX.build)||has(text,LEX.spawn))&&sk", self.bridge)
        self.assertIn("kind:'GENERATE_STRUCTURE'", self.bridge)
        self.assertIn("structure_kind:sk", self.bridge)
        self.assertIn("castle:['castle'", self.bridge)

    def test_first_person_camera_is_centered_level_and_movement_uses_camera_forward(self):
        presentation = self.contract["presentation"]
        self.assertTrue(presentation["first_person_auto_level_horizon"])
        self.assertTrue(presentation["first_person_camera_centered_on_player_anchor"])
        self.assertTrue(presentation["movement_relative_to_camera_forward_on_ground_plane"])
        self.assertIn("function forwardVector", self.world)
        self.assertIn("x:-Math.sin(yaw),y:Math.cos(yaw)", self.world)
        self.assertIn("camera_mode==='FIRST_PERSON'", self.world)
        self.assertIn("roll:0", self.world)
        self.assertIn("const len=Math.hypot(f,s)||1,forward=forwardVector(),right=rightVector()", self.world)
        self.assertIn("save.camera_heading-=dx", self.world)
        self.assertIn("save.camera_pitch=clamp(save.camera_pitch-dy", self.world)

    def test_lighthouse_r2_has_real_parts_and_rotating_beam(self):
        structures = self.contract["structures"]
        self.assertEqual(structures["lighthouse_recipe"], "KRR_LIGHTHOUSE_R2")
        self.assertEqual(set(structures["lighthouse_required_parts"]), {"BASE", "TAPERED_TOWER", "DOOR", "WINDOWS", "GALLERY", "LANTERN_GLASS", "ROOF", "ROTATING_BEAM"})
        for token in ("function drawLighthouse", "primitiveFrustum", "function drawBeam", "performance.now()/1700", "KRR_LIGHTHOUSE_R2", "castle"):
            self.assertIn(token, self.world)

    def test_asset_materializer_is_visible_and_rights_gated(self):
        asset = self.contract["asset_trunk"]
        self.assertTrue(asset["rights_gate_before_external_asset_use"])
        self.assertTrue(asset["krr_material_dna_visible_on_world_geometry"])
        self.assertTrue(asset["procedural_fallback_when_offline"])
        for token in ("rights==='CC0'", "new Image()", "createPattern", "proceduralTile", "materialDNA", "external_binary_is_canonical:false"):
            self.assertIn(token, self.material)
        self.assertIn("materialFill", self.world)
        self.assertIn("terrainFill", self.world)
        self.assertIn("Powered by Poly Haven", self.bridge)

    def test_hud_is_collapsible_and_has_compact_responsive_breakpoints(self):
        responsive = self.contract["responsive_ui"]
        self.assertTrue(responsive["side_panels_collapsible"])
        self.assertTrue(responsive["hud_overlap_forbidden"])
        self.assertEqual(responsive["target_desktop_minimum"], "1366x768")
        for token in (".is-collapsed .panel-body", "@media (max-height: 760px)", "@media (max-width: 760px)", "@media (max-width: 430px)", ".action-bar { display:none !important; }"):
            self.assertIn(token, self.css)
        for html in (self.root_html, self.site_html):
            self.assertIn('data-collapse-target="world-status-panel"', html)
            self.assertIn('data-collapse-target="janus-nerve-panel"', html)
            self.assertNotIn('class="hud action-bar"', html)

    def test_janus_still_is_proposal_not_world_authority(self):
        authority = self.contract["authority"]
        self.assertFalse(authority["janus_response_is_world_authority"])
        self.assertFalse(authority["player_text_is_direct_world_authority"])
        self.assertTrue(authority["genesis_validator_required"])
        self.assertIn("janus_api_is_world_authority!==false", self.bridge)
        self.assertIn("genesis_validator_required!==true", self.bridge)
        self.assertIn("executeIntent", self.world)
        self.assertIn("INTENT_NOT_ALLOWLISTED", self.world)

    def test_no_embedded_secret_tokens_in_active_r03_browser_surface(self):
        surface = self.world + self.bridge + self.material + self.hotkeys + self.css + self.root_html + self.site_html
        for token in ("AIza", "sk-", "ghp_", "github_pat_", "Bearer "):
            self.assertNotIn(token, surface)


if __name__ == "__main__":
    unittest.main()
