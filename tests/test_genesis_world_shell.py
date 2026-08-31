import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CANONICAL_CONTRACT = ROOT / ".janus" / "GENESIS_WORLD_SHELL_R0.json"
PUBLIC_CONTRACT = ROOT / "contracts" / "GENESIS_WORLD_SHELL_R0.json"
WORLD_JS = ROOT / "site" / "genesis-world-shell.js"
WORLD_CSS = ROOT / "site" / "world-shell.css"
SITE_INDEX = ROOT / "site" / "index.html"
ROOT_INDEX = ROOT / "index.html"
ROOT_LAB = ROOT / "kernel-lab.html"
SITE_LAB = ROOT / "site" / "kernel-lab.html"


class GenesisWorldShellR0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CANONICAL_CONTRACT.read_text(encoding="utf-8"))
        cls.public_contract = json.loads(PUBLIC_CONTRACT.read_text(encoding="utf-8"))
        cls.js = WORLD_JS.read_text(encoding="utf-8")
        cls.css = WORLD_CSS.read_text(encoding="utf-8")
        cls.site_html = SITE_INDEX.read_text(encoding="utf-8")
        cls.root_html = ROOT_INDEX.read_text(encoding="utf-8")

    def test_contract_is_local_vertical_slice_not_fake_online_mmo(self):
        self.assertEqual(self.contract["schema"], "janus.genesis.world_shell.v1")
        self.assertEqual(self.contract["version"], "1.0.0")
        self.assertEqual(self.contract["status"], "IMPLEMENTED_LOCAL_VERTICAL_SLICE_R0")
        world = self.contract["world_model"]
        self.assertTrue(world["shared_world_invariant"])
        self.assertFalse(world["personal_mirror_changes_canonical_facts"])
        self.assertTrue(world["personal_mirror_changes_presentation"])
        self.assertEqual(world["browser_demo_authority"], "LOCAL_PROTOTYPE_ONLY")
        self.assertEqual(world["networked_mmo_authority"], "NOT_IMPLEMENTED")

    def test_vertical_slice_preserves_frozen_kernel_roadmap(self):
        overlay = self.contract["execution_overlay"]
        self.assertEqual(overlay["kind"], "VERTICAL_SLICE_OVERLAY")
        self.assertTrue(overlay["preserves_frozen_kernel_roadmap"])
        self.assertEqual(overlay["current_front"], "WORLD_SHELL_R0")

    def test_chunk_ring_freeze_matches_runtime(self):
        lifecycle = self.contract["chunk_lifecycle"]
        self.assertEqual(lifecycle["chunk_size_tiles"], 10)
        self.assertEqual(lifecycle["visible_radius_chunks"], 2)
        self.assertEqual(lifecycle["prewarm_radius_chunks"], 4)
        for state in ("VISIBLE_RENDERED", "PREWARM_PLAN_ONLY", "RECIPE_ONLY_FAR"):
            self.assertIn(state, lifecycle["states"])
        self.assertIn("chunk_size: 10", self.js)
        self.assertIn("visible_radius: 2", self.js)
        self.assertIn("prewarm_radius: 4", self.js)

    def test_public_contract_mirror_is_exact(self):
        self.assertEqual(self.public_contract, self.contract)

    def test_renderer_and_mirror_have_no_canonical_authority(self):
        boundary = self.contract["authority_boundary"]
        self.assertFalse(boundary["renderer_is_authority"])
        self.assertFalse(boundary["mirror_is_authority"])
        self.assertFalse(boundary["audio_is_authority"])
        self.assertFalse(boundary["local_demo_mutation_is_network_canonical"])
        self.assertFalse(boundary["hidden_human_telemetry"])
        self.assertFalse(boundary["arbitrary_code_execution"])
        self.assertFalse(boundary["runtime_cross_repo_network_dependency"])

    def test_canonical_chunk_plan_does_not_read_personal_mirror(self):
        canonical_segment = self.js.split("function canonicalChunkPlan", 1)[1].split("function defaultSave", 1)[0]
        self.assertNotIn("mirror()", canonical_segment)
        self.assertNotIn("mirror_profile", canonical_segment)
        self.assertIn("world_seed: CONFIG.world_seed", canonical_segment)
        self.assertIn("chunk: [cx, cy]", canonical_segment)
        self.assertIn("fact_hash", canonical_segment)

    def test_mirror_is_explicitly_presentation_side(self):
        mirror_segment = self.js.split("function mirrorMaterial", 1)[1].split("function drawTile", 1)[0]
        self.assertIn("mirror()", mirror_segment)
        self.assertIn("setMirror", self.js)
        self.assertIn("FACTS", self.js)
        for profile in ("ORIGIN", "NOCTURNE", "AETHER", "EMBER"):
            self.assertIn(profile, self.contract["personal_mirror"]["profiles"])
            self.assertIn(profile, self.js)

    def test_save_contract_is_causes_only(self):
        save = self.contract["save_contract"]
        self.assertTrue(save["stores_causes"])
        self.assertFalse(save["rendered_pixels_persisted"])
        self.assertFalse(save["generated_textures_persisted"])
        self.assertFalse(save["generated_mesh_buffers_persisted"])
        self.assertFalse(save["audio_pcm_persisted"])
        self.assertIn("localStorage.setItem(CONFIG.save_key", self.js)
        self.assertIn("explicit_world_mutations", self.js)
        self.assertIn("chronicle_hash_chain", self.js)

    def test_chronicle_prefers_sha256_and_is_hash_linked(self):
        self.assertTrue(self.contract["chronicle"]["event_chain"])
        self.assertEqual(self.contract["chronicle"]["preferred_hash"], "SHA-256")
        self.assertIn("crypto.subtle.digest('SHA-256'", self.js)
        self.assertIn("previous_hash", self.js)
        self.assertIn("CHUNK_DISCOVERED", self.js)
        self.assertIn("PLAYER_MARK_PLACED", self.js)

    def test_world_shell_has_no_dynamic_code_or_cross_repo_runtime_network(self):
        forbidden = ("eval(", "new Function(", "WebSocket(", "EventSource(", "http://", "https://")
        surface = self.js + self.site_html + self.root_html
        for token in forbidden:
            self.assertNotIn(token, surface)
        self.assertIn("fetch('./contracts/GENESIS_WORLD_SHELL_R0.json'", self.js)

    def test_pages_root_is_playable_world_and_lab_survives(self):
        for html in (self.site_html, self.root_html):
            self.assertIn("GENESIS // WORLD SHELL R0", html)
            self.assertIn("id=\"genesis-world\"", html)
            self.assertIn("THE WORLD BEGINS", html)
            self.assertIn("ONE WORLD // MANY MIRRORS", html)
            self.assertIn("MMO AUTHORITY", html)
            self.assertIn("NOT CONNECTED", html)
            self.assertIn("KERNEL LAB", html)
        self.assertTrue(ROOT_LAB.exists())
        self.assertTrue(SITE_LAB.exists())
        self.assertIn("GENESIS // KERNEL LAB", ROOT_LAB.read_text(encoding="utf-8"))
        self.assertIn("GENESIS // KERNEL LAB", SITE_LAB.read_text(encoding="utf-8"))

    def test_browser_slice_contains_material_mesh_architecture_audio_and_streaming(self):
        for token in (
            "canonicalTilePlan",
            "mirrorMaterial",
            "canonicalChunkPlan",
            "drawObject",
            "prewarmAround",
            "visibleChunkBounds",
            "deriveAudioState",
            "GENESIS_AUDIO_FORGE",
        ):
            self.assertIn(token, self.js)
        for forge in ("MATERIAL_FORGE", "MESH_FORGE", "ARCHITECTURE_GRAMMAR", "EFFECT_FORGE", "AUDIO_FORGE"):
            self.assertIn(forge, self.contract["generation"]["forges_in_vertical_slice"])

    def test_janus_organs_are_contractual_not_hidden_runtime_dependencies(self):
        organs = {item["repo"]: item for item in self.contract["janus_organs"]}
        self.assertIn("Hawkar-usls/Janus_Genesis", organs)
        self.assertIn("Hawkar-usls/Janus-HELIOS", organs)
        self.assertIn("Hawkar-usls/janus-lapis", organs)
        self.assertIn("Hawkar-usls/Janus-Demiurge", organs)
        self.assertFalse(organs["Hawkar-usls/Janus-HELIOS"]["runtime_dependency"])
        self.assertFalse(organs["Hawkar-usls/janus-lapis"]["runtime_dependency"])
        self.assertFalse(organs["Hawkar-usls/Janus-Demiurge"]["runtime_dependency"])


if __name__ == "__main__":
    unittest.main()
