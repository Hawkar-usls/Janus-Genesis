import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".janus" / "GENESIS_FULL_RUNTIME_V1.json"
PUBLIC = ROOT / "contracts" / "GENESIS_FULL_RUNTIME_V1.json"
WORLD = ROOT / "site" / "genesis-world-runtime-v3.js"
BRIDGE = ROOT / "site" / "genesis-janus-bridge-v1.js"
MATERIAL = ROOT / "site" / "genesis-asset-materializer-v1.js"
AUDIO = ROOT / "site" / "genesis-audio-runtime-v1.js"
ROOT_HTML = ROOT / "index.html"
SITE_HTML = ROOT / "site" / "index.html"


class GenesisFullRuntimeV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.public = json.loads(PUBLIC.read_text(encoding="utf-8"))
        cls.world = WORLD.read_text(encoding="utf-8")
        cls.bridge = BRIDGE.read_text(encoding="utf-8")
        cls.material = MATERIAL.read_text(encoding="utf-8")
        cls.audio = AUDIO.read_text(encoding="utf-8")
        cls.root_html = ROOT_HTML.read_text(encoding="utf-8")
        cls.site_html = SITE_HTML.read_text(encoding="utf-8")

    def test_public_contract_is_exact_mirror(self):
        self.assertEqual(self.public, self.contract)

    def test_active_runtime_is_3d_only(self):
        self.assertEqual(self.contract["presentation"]["dimensions"], ["3D"])
        self.assertIn("2D_ACTIVE_RUNTIME_FORBIDDEN", self.contract["laws"])
        for camera in ("FIRST_PERSON", "THIRD_PERSON", "ISOMETRIC"):
            self.assertIn(camera, self.contract["presentation"]["camera_modes"])
            self.assertIn(camera, self.world)
        for html in (self.root_html, self.site_html):
            self.assertIn("GENESIS // FULL WORLD RUNTIME", html)
            self.assertNotIn("2D/3D", html)
            self.assertNotIn("Choosing 2D", html)
            self.assertIn("3D CAMERA", html)
            self.assertIn("genesis-world-runtime-v3.js", html)

    def test_camera_has_yaw_pitch_roll_and_wheel_distance(self):
        for token in ("camera_heading", "camera_pitch", "camera_roll", "camera_distance"):
            self.assertIn(token, self.world)
        self.assertIn("addEventListener('wheel'", self.world)
        self.assertIn("e.altKey", self.world)
        self.assertIn("e.button===1", self.world)
        self.assertIn("save.camera_roll=0", self.world)
        self.assertEqual(self.contract["presentation"]["full_camera_axes"], ["YAW", "PITCH", "ROLL"])
        self.assertEqual(self.contract["presentation"]["third_person_distance_control"], "MOUSE_WHEEL")

    def test_movement_is_keyboard_layout_independent_and_text_is_isolated(self):
        movement = self.contract["input"]["movement"]
        self.assertTrue(movement["layout_independent"])
        self.assertEqual(movement["browser_basis"], "KeyboardEvent.code")
        for code in ("KeyW", "KeyA", "KeyS", "KeyD"):
            self.assertIn(code, self.world)
        for code in ("ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight"):
            self.assertIn(code, self.world)
        self.assertIn("e.target instanceof HTMLInputElement", self.world)
        self.assertIn("e.stopPropagation()", self.bridge)

    def test_multilingual_text_routes_to_janus_preferred_with_visible_degraded_mode(self):
        text = self.contract["input"]["text"]
        self.assertTrue(text["janus_preferred"])
        self.assertEqual(set(text["local_degraded_lexical_languages_r0"]), {"en", "ru", "uk", "pl", "de", "es", "fr"})
        self.assertIn("/v1/health", self.bridge)
        self.assertIn("/v1/genesis/intent", self.bridge)
        self.assertIn("JANUS HOME", self.bridge)
        self.assertIn("LOCAL DEGRADED", self.bridge)
        for sample in ("построй", "побудуй", "zbuduj", "baue", "construye", "construis", "build"):
            self.assertIn(sample, self.bridge)
        for html in (self.root_html, self.site_html):
            self.assertIn('id="janus-api-status"', html)
            self.assertIn('id="janus-api-endpoint"', html)
            self.assertIn("Hawkar-usls/Hawkar-usls", html)

    def test_janus_response_never_has_direct_world_authority(self):
        api = self.contract["janus_api"]
        self.assertFalse(api["janus_response_is_command"])
        self.assertFalse(api["janus_response_is_world_authority"])
        self.assertTrue(api["genesis_side_validator_required"])
        self.assertIn("janus_api_is_world_authority!==false", self.bridge)
        self.assertIn("genesis_validator_required!==true", self.bridge)
        self.assertIn("executeIntent", self.world)
        self.assertIn("INTENT_NOT_ALLOWLISTED", self.world)

    def test_command_materializes_or_returns_visible_reason(self):
        self.assertTrue(self.contract["command_materialization"]["requested_effect_must_not_silently_disappear"])
        self.assertIn("GENERATE_STRUCTURE", self.bridge)
        self.assertIn("MATERIALIZED:", self.bridge)
        self.assertIn("UNRESOLVED", self.bridge)
        self.assertIn("REJECTED / DEGRADED", self.bridge)
        self.assertIn("STRUCTURE_MATERIALIZED", self.world)
        for html in (self.root_html, self.site_html):
            self.assertIn('id="action-result"', html)
            self.assertIn("MATERIALIZE", html)

    def test_asset_trunk_is_live_reference_path_with_rights_and_direct_binary_transport(self):
        trunk = self.contract["asset_trunk"]
        self.assertEqual(trunk["first_live_runtime_adapter"], "poly_haven")
        self.assertEqual(trunk["first_live_runtime_rights"], "CC0")
        self.assertFalse(trunk["binary_asset_bytes_through_slime"])
        self.assertEqual(trunk["binary_asset_transport"], "DIRECT_PROVIDER_CDN")
        self.assertTrue(trunk["rights_gate_before_use"])
        self.assertIn("/v1/genesis/assets/search", self.bridge)
        self.assertIn("/v1/genesis/assets/files/", self.bridge)
        self.assertIn("rights!=='CC0'", self.bridge)
        self.assertIn("DIRECT", trunk["binary_asset_transport"])
        for html in (self.root_html, self.site_html):
            self.assertIn('id="asset-trunk-results"', html)
            self.assertIn("Powered by Poly Haven", html)

    def test_krr_materializer_streams_asset_pointer_but_does_not_store_binary_world_asset(self):
        krr = self.contract["asset_trunk"]["krr_distillation"]
        self.assertTrue(krr["stores_asset_reference"])
        self.assertFalse(krr["stores_binary_asset_in_world_save"])
        self.assertTrue(krr["same_asset_ref_and_seed_same_material_dna"])
        for token in ("download_pointer", "new Image()", "crossOrigin='anonymous'", "KRR", "materialDNA"):
            self.assertIn(token, self.material)
        self.assertIn("asset_refs", self.world)
        self.assertNotIn("data:image", self.world)
        self.assertNotIn("data:audio", self.world)

    def test_audio_remains_procedural_world_to_audio(self):
        audio = self.contract["audio"]
        self.assertEqual(audio["procedural_primary"], "HELIOS_DERIVED_AUDIO_FORGE")
        self.assertTrue(audio["world_to_audio_only"])
        self.assertFalse(audio["audio_to_world_authority"])
        self.assertIn("GENESIS_AUDIO_FORGE", self.audio)
        self.assertIn("setWorldState", self.audio)
        self.assertIn("portal_open", self.audio)

    def test_pages_no_longer_load_historical_ru_only_or_local_action_r0_as_active_runtime(self):
        for html in (self.root_html, self.site_html):
            self.assertNotIn("genesis-action-input-ru.js", html)
            self.assertNotIn("genesis-action-forge.js", html)
            self.assertIn("genesis-janus-bridge-v1.js", html)
            self.assertIn("genesis-asset-materializer-v1.js", html)
            self.assertIn("genesis-audio-runtime-v1.js", html)

    def test_no_embedded_secret_tokens_in_active_browser_runtime(self):
        surface = self.world + self.bridge + self.material + self.audio + self.root_html + self.site_html
        for token in ("AIza", "sk-", "ghp_", "github_pat_", "Bearer "):
            self.assertNotIn(token, surface)


if __name__ == "__main__":
    unittest.main()
