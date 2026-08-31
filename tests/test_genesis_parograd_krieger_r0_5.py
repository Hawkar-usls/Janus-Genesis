import json
import pathlib
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / ".janus" / "GENESIS_PAROGRAD_KRIEGER_R0_5.json"
PUBLIC = ROOT / "contracts" / "GENESIS_PAROGRAD_KRIEGER_R0_5.json"
RUNTIME = ROOT / "site" / "genesis-world-runtime-v5.js"
HOTKEYS = ROOT / "site" / "genesis-hotkeys-v3.js"
LEXICON = ROOT / "site" / "genesis-command-lexicon-r0-5.js"
EXECUTOR = ROOT / "site" / "genesis-scene-graph-executor-r0-5.js"
BRIDGE = ROOT / "site" / "genesis-command-bridge-v5.js"
MECHANIC = ROOT / "site" / "genesis-mechanic-forge-r0-5.js"
TRUNK = ROOT / "site" / "genesis-asset-trunk-r0-5.js"
REGISTRY = ROOT / "asset_sources" / "ASSET_SOURCE_REGISTRY_R0_5.json"
MECHANIC_REGISTRY = ROOT / "asset_sources" / "MECHANIC_RECIPE_SOURCE_REGISTRY_R0_5.json"
HTMLS = [ROOT / "index.html", ROOT / "site" / "index.html"]


class GenesisParogradKriegerR05Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.public = json.loads(PUBLIC.read_text(encoding="utf-8"))
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.hotkeys = HOTKEYS.read_text(encoding="utf-8")
        cls.lexicon = LEXICON.read_text(encoding="utf-8")
        cls.executor = EXECUTOR.read_text(encoding="utf-8")
        cls.bridge = BRIDGE.read_text(encoding="utf-8")
        cls.mechanic = MECHANIC.read_text(encoding="utf-8")
        cls.trunk = TRUNK.read_text(encoding="utf-8")
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.mechanic_registry = json.loads(MECHANIC_REGISTRY.read_text(encoding="utf-8"))

    def run_node(self, source):
        node = shutil.which("node")
        self.assertIsNotNone(node)
        p = subprocess.run([node, "-e", source], cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 0, p.stdout + "\n" + p.stderr)
        return p.stdout

    def test_contract_mirror_and_generator_version_preservation(self):
        self.assertEqual(self.contract, self.public)
        self.assertEqual(self.contract["version"], "0.5.0")
        self.assertEqual(self.contract["runtime"]["generator_version_preserved"], "GENESIS_COMMAND_RUNTIME_R0.3.0")
        self.assertIn("generator_version:'GENESIS_COMMAND_RUNTIME_R0.3.0'", self.runtime)

    def test_jump_is_layout_independent_transient_locomotion(self):
        jump = self.contract["jump"]
        self.assertEqual(jump["keyboard_code"], "Space")
        self.assertFalse(jump["canonical_world_mutation"])
        self.assertFalse(jump["persisted_in_world_save"])
        self.assertIn("event.code==='Space'", self.hotkeys)
        self.assertIn("kind==='JUMP'", self.runtime)
        self.assertIn("JUMP_AIRBORNE_OR_REARM", self.runtime)
        self.assertIn("JUMP", self.executor)
        self.assertIn("JUMP:'NAVIGATION'", self.bridge)
        for token in ("прыгни", "стрибни", "skocz", "springe", "salta", "saute"):
            self.assertIn(token, self.lexicon)
        canonical_method = self.runtime.split("getCanonicalState(){", 1)[1].split("getPresentationState(){", 1)[0]
        self.assertNotIn("motion.offset", canonical_method)
        self.assertNotIn("vertical", canonical_method)

    def test_distance_is_adaptive_lod_not_single_giant_full_detail_radius(self):
        streaming = self.contract["distance_streaming"]
        self.assertFalse(streaming["lod_changes_canonical_facts"])
        for profile in streaming["profiles"].values():
            self.assertLess(profile["full_detail"], profile["coarse_lod"])
            self.assertLess(profile["coarse_lod"], profile["horizon"])
        for token in ("terrainBand", "terrainLOD", "horizon_step", "recipe_only_beyond", "drawDistantMutation", "performanceClass"):
            self.assertIn(token, self.runtime)
        self.assertNotIn("render_radius: 64", self.runtime)
        self.assertNotIn("render_radius:64", self.runtime)

    def test_pages_activate_v5_and_keep_old_runtime_out_of_active_script_chain(self):
        for path in HTMLS:
            html = path.read_text(encoding="utf-8")
            self.assertIn("PAROGRAD × KRIEGER R0.5", html)
            self.assertIn("genesis-world-runtime-v5.js", html)
            self.assertIn("genesis-hotkeys-v3.js", html)
            self.assertIn("genesis-command-lexicon-r0-5.js", html)
            self.assertIn("genesis-asset-trunk-r0-5.js", html)
            self.assertIn("genesis-scene-graph-executor-r0-5.js", html)
            self.assertIn("genesis-command-bridge-v5.js", html)
            self.assertNotIn('src="./site/genesis-world-runtime-v4.js"', html)
            self.assertNotIn('src="./genesis-world-runtime-v4.js"', html)
            self.assertIn('data-action="jump"', html)
            self.assertIn('id="horizon-count"', html)

    def test_typed_asset_trunks_are_honest_about_live_vs_registered(self):
        providers = {p["provider_id"]: p for p in self.registry["providers"]}
        self.assertEqual(providers["poly_haven"]["runtime_status"], "LIVE_ADAPTER")
        self.assertIn("AUDIO", providers["wikimedia_commons"]["channels"])
        self.assertEqual(providers["openverse"]["runtime_status"], "DISCOVERY_ONLY")
        self.assertIn("DISABLED_CONDITIONAL", providers["freesound"]["runtime_status"])
        self.assertIn("ADAPTER_PENDING", providers["ambientcg"]["runtime_status"])
        self.assertIn("REGISTERED_SOURCE_NE_LIVE_ADAPTER", self.registry["laws"])
        self.assertIn("material", self.trunk)
        self.assertIn("mesh", self.trunk)
        self.assertIn("audio", self.trunk)
        self.assertIn("mechanic", self.trunk)
        self.assertIn("binary_bytes_through_slime:false", self.trunk)

    def test_mechanic_forge_is_allowlisted_and_never_executes_foreign_code(self):
        self.assertFalse(self.contract["mechanic_forge"]["foreign_code_execution"])
        self.assertIn("FOREIGN_MECHANIC_CODE_NE_EXECUTABLE_AUTHORITY", self.mechanic_registry["laws"])
        self.assertNotIn("eval(", self.mechanic)
        self.assertNotIn("new Function", self.mechanic)
        mechanic_path = json.dumps(str(MECHANIC))
        out = self.run_node(f"""
const fs=require('fs'),vm=require('vm');vm.runInThisContext(fs.readFileSync({mechanic_path},'utf8'));
const f=globalThis.GENESIS_MECHANIC_FORGE_R0_5;
const lighthouse=f.forStructure('lighthouse','abcdef12');
const portal=f.forStructure('portal','abcdef12');
if(!lighthouse.some(x=>x.kind==='ROTATOR'))throw new Error('no lighthouse rotator');
if(!portal.some(x=>x.kind==='OSCILLATOR'))throw new Error('no portal oscillator');
let rejected=false;try{{f.recipe('REMOTE_SCRIPT',{{code:'x'}})}}catch(e){{rejected=true}}if(!rejected)throw new Error('foreign mechanic accepted');
console.log('MECHANIC_FORGE_PASS');
""")
        self.assertIn("MECHANIC_FORGE_PASS", out)

    def test_cause_first_and_authority_laws_are_frozen(self):
        laws = set(self.contract["laws"])
        for law in (
            "JUMP_NE_WORLD_MUTATION",
            "DISTANCE_LOD_DOES_NOT_CHANGE_CANONICAL_FACTS",
            "STREAM_WHEN_NECESSARY",
            "GENERATE_WHEN_CHEAPER",
            "STORE_CAUSES_NOT_RENDERED_CONSEQUENCES",
            "SLIME_CONTROL_PLANE_NE_ASSET_BYTES",
            "FOREIGN_MECHANIC_CODE_NE_EXECUTABLE_AUTHORITY",
        ):
            self.assertIn(law, laws)
        self.assertFalse(self.contract["authority"]["janus_graph_is_world_authority"])
        self.assertTrue(self.contract["authority"]["genesis_validator_required"])


if __name__ == "__main__":
    unittest.main()
