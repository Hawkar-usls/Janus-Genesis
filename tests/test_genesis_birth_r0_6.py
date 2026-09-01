import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".janus" / "GENESIS_BIRTH_R0_6.json"
PUBLIC = ROOT / "contracts" / "GENESIS_BIRTH_R0_6.json"
BIRTH_JS = ROOT / "site" / "genesis-birth-r0-6.js"
ROOT_INDEX = ROOT / "index.html"
SITE_INDEX = ROOT / "site" / "index.html"


class GenesisBirthR06Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.public = json.loads(PUBLIC.read_text(encoding="utf-8"))
        cls.js = BIRTH_JS.read_text(encoding="utf-8")
        cls.root_html = ROOT_INDEX.read_text(encoding="utf-8")
        cls.site_html = SITE_INDEX.read_text(encoding="utf-8")

    def test_contract_mirror_is_exact(self):
        self.assertEqual(self.contract, self.public)
        self.assertEqual(self.contract["contract_id"], "GENESIS_BIRTH_R0_6")
        self.assertEqual(self.contract["version"], "0.6.0")

    def test_causal_order_is_frozen(self):
        self.assertEqual(
            self.contract["birth_event"]["chronicle_order"],
            ["GENESIS_BIRTH", "CHUNK_DISCOVERED", "FIRST_INTENT_MATERIALIZATION"],
        )
        self.assertTrue(self.contract["birth_event"]["exactly_once"])
        self.assertFalse(self.contract["boot_gate"]["canonical_fact"])
        self.assertTrue(self.contract["boot_gate"]["must_be_removed_before_birth_event"])

    def test_required_firewalls_exist(self):
        firewalls = set(self.contract["firewalls"])
        required = {
            "BIRTH_INTENT != CANONICAL_FACT_UNTIL_ACCEPTED",
            "UNBORN_BOOT_SENTINEL != CANONICAL_WORLD_FACT",
            "PLAYER_MIRROR != CANONICAL_WORLD",
            "FIRST_RENDER_AFTER_BIRTH_EVENT",
            "LEGACY_MIGRATION != WORLD_RESET",
            "ONE_FRESH_SAVE -> AT_MOST_ONE_GENESIS_BIRTH",
        }
        self.assertTrue(required.issubset(firewalls))

    def test_birth_overlay_loads_before_world_runtime_everywhere(self):
        root_birth = self.root_html.index("./site/genesis-birth-r0-6.js")
        root_world = self.root_html.index("./site/genesis-world-runtime-v5.js")
        site_birth = self.site_html.index("./genesis-birth-r0-6.js")
        site_world = self.site_html.index("./genesis-world-runtime-v5.js")
        self.assertLess(root_birth, root_world)
        self.assertLess(site_birth, site_world)
        self.assertIn("GENESIS // BIRTH R0.6", self.root_html)
        self.assertIn("GENESIS // BIRTH R0.6", self.site_html)

    def test_root_and_site_script_lineages_match(self):
        pattern = re.compile(r'<script\s+src="([^"]+)"')
        root = [Path(src).name for src in pattern.findall(self.root_html)]
        site = [Path(src).name for src in pattern.findall(self.site_html)]
        self.assertEqual(root, site)
        self.assertIn("genesis-birth-r0-6.js", root)

    def test_runtime_uses_real_sha256_and_deterministic_birth_seed(self):
        self.assertIn("crypto.subtle.digest('SHA-256'", self.js)
        self.assertIn("GENESIS_BIRTH_R0_6|${WORLD_SEED}|${normalized}", self.js)
        self.assertIn("intent_sha256", self.js)
        self.assertNotIn("Math.random", self.js)

    def test_unborn_sentinel_is_non_chronicle_and_removed_on_birth(self):
        self.assertIn("birth_state:SENTINEL", self.js)
        self.assertIn("discovered_chunk_coordinates:[[0,0]]", self.js)
        self.assertIn("chronicle_hash_chain:[]", self.js)
        self.assertIn("delete born.birth_sentinel", self.js)
        self.assertIn("discovered_chunk_coordinates:[]", self.js)
        self.assertIn("chronicle_hash_chain:[{...core,event_hash}]", self.js)

    def test_birth_event_is_first_hash_linked_event(self):
        self.assertIn("const core={sequence:1,type:'GENESIS_BIRTH',data,prev:'GENESIS'}", self.js)
        self.assertIn("if(eventsOf(save).length)throw new Error('PRE_BIRTH_CHRONICLE_NOT_EMPTY')", self.js)
        self.assertIn("hasEvent(save,'GENESIS_BIRTH')", self.js)

    def test_first_intent_replay_waits_for_post_birth_discovery(self):
        self.assertIn("birthIndex===0&&chunkIndex>birthIndex", self.js)
        self.assertIn("sessionStorage.setItem(PENDING_KEY,normalized)", self.js)
        self.assertIn("form.requestSubmit()", self.js)
        self.assertIn("document.getElementById('enter-world')?.click()", self.js)

    def test_legacy_migration_is_non_destructive_and_not_retroactive(self):
        migration = self.contract["legacy_migration"]
        self.assertFalse(migration["destructive_reset"])
        self.assertFalse(migration["retroactive_birth_claim"])
        self.assertIn("BORN_LEGACY_R0_5", self.js)
        self.assertIn("retroactive_birth_claim:false", self.js)


if __name__ == "__main__":
    unittest.main()
