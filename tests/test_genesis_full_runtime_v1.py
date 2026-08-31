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
R03 = ROOT / ".janus" / "GENESIS_COMMAND_RUNTIME_R0_3.json"


class GenesisFullRuntimeV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract=json.loads(CANONICAL.read_text(encoding="utf-8")); cls.public=json.loads(PUBLIC.read_text(encoding="utf-8")); cls.world=WORLD.read_text(encoding="utf-8"); cls.bridge=BRIDGE.read_text(encoding="utf-8"); cls.material=MATERIAL.read_text(encoding="utf-8"); cls.audio=AUDIO.read_text(encoding="utf-8"); cls.root_html=ROOT_HTML.read_text(encoding="utf-8"); cls.site_html=SITE_HTML.read_text(encoding="utf-8"); cls.r03=json.loads(R03.read_text(encoding="utf-8")) if R03.exists() else None
    def test_public_contract_is_exact_historical_mirror(self): self.assertEqual(self.public,self.contract); self.assertEqual(self.contract["schema"],"janus.genesis.full_runtime.v1")
    def test_r02_contract_remains_3d_only_history(self):
        self.assertEqual(self.contract["presentation"]["dimensions"],["3D"]); self.assertIn("2D_ACTIVE_RUNTIME_FORBIDDEN",self.contract["laws"])
        for camera in ("FIRST_PERSON","THIRD_PERSON","ISOMETRIC"): self.assertIn(camera,self.contract["presentation"]["camera_modes"]); self.assertIn(camera,self.world)
    def test_r02_browser_artifacts_survive_supersession(self):
        for path in (WORLD,BRIDGE,MATERIAL,AUDIO): self.assertTrue(path.exists())
        self.assertIn("GENESIS_WORLD_RUNTIME_V3",self.world); self.assertIn("/v1/genesis/intent",self.bridge); self.assertIn("GENESIS_AUDIO_FORGE",self.audio)
        if self.r03:
            self.assertEqual(self.r03["supersedes_active_pages_runtime"],"GENESIS_FULL_RUNTIME_V1_R0_2")
            for html in (self.root_html,self.site_html): self.assertIn("TEXT-NATIVE WORLD ENGINE",html); self.assertIn("genesis-world-runtime-v4.js",html); self.assertIn("genesis-command-bridge-v3.js",html)
        else:
            for html in (self.root_html,self.site_html): self.assertIn("GENESIS // FULL WORLD RUNTIME",html); self.assertIn("genesis-world-runtime-v3.js",html)
    def test_historical_camera_has_yaw_pitch_roll_and_wheel_distance(self):
        for token in ("camera_heading","camera_pitch","camera_roll","camera_distance"): self.assertIn(token,self.world)
        self.assertIn("addEventListener('wheel'",self.world); self.assertEqual(self.contract["presentation"]["full_camera_axes"],["YAW","PITCH","ROLL"]); self.assertEqual(self.contract["presentation"]["third_person_distance_control"],"MOUSE_WHEEL")
    def test_historical_movement_and_multilingual_janus_boundary_are_preserved(self):
        movement=self.contract["input"]["movement"]; self.assertTrue(movement["layout_independent"]); self.assertEqual(movement["browser_basis"],"KeyboardEvent.code")
        for code in ("KeyW","KeyA","KeyS","KeyD"): self.assertIn(code,self.world)
        text=self.contract["input"]["text"]; self.assertTrue(text["janus_preferred"]); self.assertEqual(set(text["local_degraded_lexical_languages_r0"]),{"en","ru","uk","pl","de","es","fr"}); self.assertIn("/v1/health",self.bridge); self.assertIn("LOCAL DEGRADED",self.bridge)
    def test_historical_janus_response_never_has_direct_world_authority(self):
        api=self.contract["janus_api"]; self.assertFalse(api["janus_response_is_command"]); self.assertFalse(api["janus_response_is_world_authority"]); self.assertTrue(api["genesis_side_validator_required"]); self.assertIn("janus_api_is_world_authority!==false",self.bridge); self.assertIn("genesis_validator_required!==true",self.bridge); self.assertIn("INTENT_NOT_ALLOWLISTED",self.world)
    def test_historical_asset_trunk_rights_and_binary_boundary_remain_frozen(self):
        trunk=self.contract["asset_trunk"]; self.assertEqual(trunk["first_live_runtime_adapter"],"poly_haven"); self.assertEqual(trunk["first_live_runtime_rights"],"CC0"); self.assertFalse(trunk["binary_asset_bytes_through_slime"]); self.assertEqual(trunk["binary_asset_transport"],"DIRECT_PROVIDER_CDN"); self.assertTrue(trunk["rights_gate_before_use"]); self.assertIn("/v1/genesis/assets/search",self.bridge); self.assertIn("/v1/genesis/assets/files/",self.bridge)
    def test_historical_krr_save_does_not_store_rendered_binary(self):
        krr=self.contract["asset_trunk"]["krr_distillation"]; self.assertTrue(krr["stores_asset_reference"]); self.assertFalse(krr["stores_binary_asset_in_world_save"]); self.assertTrue(krr["same_asset_ref_and_seed_same_material_dna"])
        for token in ("download_pointer","new Image()","KRR","materialDNA"): self.assertIn(token,self.material)
        self.assertIn("asset_refs",self.world); self.assertNotIn("data:image",self.world); self.assertNotIn("data:audio",self.world)
    def test_audio_remains_procedural_world_to_audio(self):
        audio=self.contract["audio"]; self.assertEqual(audio["procedural_primary"],"HELIOS_DERIVED_AUDIO_FORGE"); self.assertTrue(audio["world_to_audio_only"]); self.assertFalse(audio["audio_to_world_authority"]); self.assertIn("GENESIS_AUDIO_FORGE",self.audio); self.assertIn("setWorldState",self.audio)
    def test_no_embedded_secret_tokens_in_historical_browser_runtime(self):
        surface=self.world+self.bridge+self.material+self.audio
        for token in ("AIza","sk-","ghp_","github_pat_","Bearer "): self.assertNotIn(token,surface)


if __name__ == "__main__": unittest.main()
