import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".janus" / "GENESIS_PLAYER_MIRROR_R0_7.json"
PUBLIC = ROOT / "contracts" / "GENESIS_PLAYER_MIRROR_R0_7.json"
MIRROR_JS = ROOT / "site" / "genesis-player-mirror-r0-7.js"
WORLD_JS = ROOT / "site" / "genesis-world-runtime-v5.js"
ROOT_INDEX = ROOT / "index.html"
SITE_INDEX = ROOT / "site" / "index.html"


class GenesisPlayerMirrorR07Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.public = json.loads(PUBLIC.read_text(encoding="utf-8"))
        cls.js = MIRROR_JS.read_text(encoding="utf-8")
        cls.world = WORLD_JS.read_text(encoding="utf-8")
        cls.root_html = ROOT_INDEX.read_text(encoding="utf-8")
        cls.site_html = SITE_INDEX.read_text(encoding="utf-8")

    def test_contract_mirror_and_profiles_are_frozen(self):
        self.assertEqual(self.contract, self.public)
        self.assertEqual(self.contract["contract_id"], "GENESIS_PLAYER_MIRROR_R0_7")
        self.assertEqual(self.contract["version"], "0.7.0")
        self.assertEqual(
            list(self.contract["profiles"]),
            ["ORIGIN", "JANUS_16", "NOCTURNE", "AETHER", "EMBER"],
        )

    def test_inspiration_is_mechanism_only_and_independently_implemented(self):
        bad_pixels = self.contract["inspiration_provenance"][0]
        self.assertEqual(bad_pixels["source"], "Bad Pixels")
        self.assertEqual(bad_pixels["inheritance_policy"], "INDEPENDENT_IMPLEMENTATION_ONLY")
        self.assertFalse(bad_pixels["copied_assets"])
        self.assertFalse(bad_pixels["copied_source_code"])
        self.assertFalse(bad_pixels["copied_palette"])

    def test_janus16_is_exactly_sixteen_independent_colors(self):
        self.assertEqual(self.contract["profiles"]["JANUS_16"]["palette_budget"], 16)
        palette_block = self.js.split("const JANUS_16_HEX=Object.freeze([", 1)[1].split("]);", 1)[0]
        colors = re.findall(r"#[0-9a-fA-F]{6}", palette_block)
        self.assertEqual(len(colors), 16)
        self.assertEqual(len(set(colors)), 16)
        self.assertIn("palette_identity", json.dumps(self.contract["profiles"]["JANUS_16"]))

    def test_load_order_is_birth_then_world_then_player_mirror(self):
        for html, prefix in ((self.root_html, "./site/"), (self.site_html, "./")):
            birth = html.index(f'{prefix}genesis-birth-r0-6.js')
            world = html.index(f'{prefix}genesis-world-runtime-v5.js')
            mirror = html.index(f'{prefix}genesis-player-mirror-r0-7.js')
            self.assertLess(birth, world)
            self.assertLess(world, mirror)
            self.assertIn("GENESIS // BIRTH R0.6", html)
            self.assertIn("MIRROR R0.7", html)

    def test_root_and_site_active_script_lineages_match(self):
        pattern = re.compile(r'<script\s+src="([^"]+)"')
        root = [Path(src).name for src in pattern.findall(self.root_html)]
        site = [Path(src).name for src in pattern.findall(self.site_html)]
        self.assertEqual(root, site)
        self.assertIn("genesis-player-mirror-r0-7.js", root)

    def test_profile_selection_is_player_local_not_canonical_state(self):
        self.assertIn("janus.genesis.player_mirror_r0_7.v1", self.js)
        self.assertNotIn("janus.genesis.world_shell_r0.save.v1", self.js)
        canonical = self.world.split("getCanonicalState(){", 1)[1].split("getPresentationState(){", 1)[0]
        self.assertNotIn("mirror_profile", canonical)
        presentation = self.world.split("getPresentationState(){", 1)[1].split("getStreamingState(){", 1)[0]
        self.assertIn("mirror_profile", presentation)

    def test_canonical_invariance_proof_fails_closed(self):
        for token in (
            "runtime.getFactHash()",
            "runtime.getCanonicalState()",
            "canonicalEqual(before,after)",
            "CANONICAL_INVARIANCE_BREACH",
            "runtime.setMirror(previousPresentation)",
            "fact_hash_before",
            "fact_hash_after",
            "chronicle_tip_before",
            "chronicle_tip_after",
        ):
            self.assertIn(token, self.js)

    def test_janus16_is_low_resolution_palette_remap_not_world_rewrite(self):
        for token in (
            "logical_pixel_css:4",
            "frame_cap:20",
            "new Uint8Array(32768)",
            "getImageData",
            "putImageData",
            "imageSmoothingEnabled=false",
            "LUT[((data[i]>>3)<<10)",
        ):
            self.assertIn(token, self.js)
        self.assertFalse(self.contract["rendering"]["changes_geometry"])
        self.assertFalse(self.contract["rendering"]["changes_world_state"])
        self.assertFalse(self.contract["rendering"]["changes_chronicle"])
        self.assertFalse(self.contract["rendering"]["changes_fact_hash"])

    def test_unborn_birth_veil_remains_above_mirror_rendering(self):
        self.assertIn("GENESIS_BIRTH_R0_6?.isUnborn?.()", self.js)
        self.assertIn("if(current!=='JANUS_16'||!output||output.hidden)return", self.js)

    def test_no_network_dynamic_code_or_direct_chronicle_authority(self):
        for token in ("fetch(", "XMLHttpRequest", "WebSocket(", "EventSource(", "eval(", "new Function"):
            self.assertNotIn(token, self.js)
        self.assertNotIn("chronicle(", self.js)
        self.assertNotIn("explicit_world_mutations", self.js)
        self.assertNotIn("discovered_chunk_coordinates", self.js)

    def test_required_firewalls_exist(self):
        firewalls = set(self.contract["firewalls"])
        required = {
            "PLAYER_MIRROR != CANONICAL_WORLD",
            "MIRROR_SELECTION != CANONICAL_EVENT",
            "MIRROR_OUTPUT != CANONICAL_STATE",
            "DIFFERENT_PIXELS != DIFFERENT_FACTS",
            "FACT_HASH_BEFORE_MIRROR == FACT_HASH_AFTER_MIRROR",
            "CHRONICLE_TIP_BEFORE_MIRROR == CHRONICLE_TIP_AFTER_MIRROR",
        }
        self.assertTrue(required.issubset(firewalls))


if __name__ == "__main__":
    unittest.main()
