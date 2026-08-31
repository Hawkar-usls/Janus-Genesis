import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".janus" / "GENESIS_ACTION_FORGE_R0.json"
PUBLIC = ROOT / "contracts" / "GENESIS_ACTION_FORGE_R0.json"
RUNTIME = ROOT / "site" / "genesis-action-forge.js"
SITE_INDEX = ROOT / "site" / "index.html"
ROOT_INDEX = ROOT / "index.html"
CSS = ROOT / "site" / "action-forge.css"


class GenesisActionForgeR0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.public = json.loads(PUBLIC.read_text(encoding="utf-8"))
        cls.js = RUNTIME.read_text(encoding="utf-8")
        cls.site_html = SITE_INDEX.read_text(encoding="utf-8")
        cls.root_html = ROOT_INDEX.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")

    def test_public_contract_is_exact_mirror(self):
        self.assertEqual(self.public, self.contract)

    def test_pipeline_is_explicit_text_to_bounded_ir(self):
        self.assertEqual(self.contract["schema"], "janus.genesis.action_forge.v1")
        self.assertIn("PLAYER_EXPLICIT_TEXT", self.contract["pipeline"])
        self.assertIn("BOUNDED_INTENT_IR", self.contract["pipeline"])
        self.assertIn("VALIDATE", self.contract["pipeline"])
        self.assertTrue(self.contract["authority_boundary"]["player_text_is_explicit_input"])
        self.assertFalse(self.contract["authority_boundary"]["text_is_direct_world_authority"])
        self.assertTrue(self.contract["authority_boundary"]["intent_ir_requires_allowlist"])

    def test_world_state_is_seed_and_presentation_is_excluded(self):
        seed = self.contract["seed_contract"]
        self.assertEqual(seed["formula"], "ACTION_SEED = H(CANONICAL_WORLD_STATE || NORMALIZED_PLAYER_TEXT)")
        self.assertTrue(seed["same_state_same_text_same_plan"])
        self.assertFalse(seed["hidden_human_telemetry"])
        for field in (
            "world_id",
            "world_seed",
            "generator_version",
            "player_position",
            "discovered_chunk_coordinates",
            "explicit_world_mutations",
            "chronicle_tip_hash",
        ):
            self.assertIn(field, seed["canonical_world_state_fields"])
            self.assertIn(field, self.js)
        canonical_segment = self.js.split("function canonicalSeedState", 1)[1].split("function worldStateHash", 1)[0]
        for field in ("mirror_profile", "presentation_dimension", "camera_mode", "camera_heading"):
            self.assertIn(field, seed["excluded_presentation_fields"])
            self.assertNotIn(field, canonical_segment)

    def test_intent_vocabulary_is_bounded(self):
        vocabulary = self.contract["intent_vocabulary"]
        for intent in (
            "MOVE",
            "PLACE_MARK",
            "PLACE_ACTION_ANCHOR",
            "RETURN_TO_HEARTH",
            "TURN_CAMERA",
            "SET_MIRROR",
            "SET_DIMENSION",
            "SET_CAMERA",
        ):
            self.assertTrue(
                intent in vocabulary["canonical_or_local_world_actions"]
                or intent in vocabulary["presentation_actions"]
            )
            self.assertIn(intent, self.js)
        self.assertEqual(vocabulary["unknown_text_policy"], "FAIL_CLOSED_WITH_EXAMPLES")
        self.assertIn("UNKNOWN ACTION", self.js)
        self.assertIn("INTENT NOT ALLOWLISTED", self.js)

    def test_action_anchor_is_honest_r0_placeholder(self):
        semantics = self.contract["r0_semantics"]
        self.assertIn("PLAYER_MARK-compatible action anchor", semantics["action_anchor"])
        self.assertIn("does not claim arbitrary nouns", semantics["action_anchor"])
        self.assertIn("GENESIS_ACTION_ANCHOR_", self.js)
        self.assertIn("type: 'PLAYER_MARK'", self.js)
        self.assertIn("ACTION_ANCHOR_NE_BESPOKE_GENERATED_ASSET", self.contract["laws"])

    def test_runtime_has_no_arbitrary_code_or_external_network(self):
        for token in ("eval(", "new Function(", "WebSocket(", "EventSource(", "http://", "https://"):
            self.assertNotIn(token, self.js)
        boundary = self.contract["authority_boundary"]
        self.assertFalse(boundary["arbitrary_code_execution"])
        self.assertFalse(boundary["external_network_access"])
        self.assertFalse(boundary["hidden_psychological_inference"])
        self.assertFalse(boundary["local_r0_mutation_is_network_canonical"])

    def test_bounds_match_runtime(self):
        bounds = self.contract["bounds"]
        self.assertEqual(bounds["max_text_chars"], 280)
        self.assertEqual(bounds["max_move_steps"], 40)
        self.assertEqual(bounds["max_concept_chars"], 64)
        self.assertIn("max_text_chars: 280", self.js)
        self.assertIn("max_move_steps: 40", self.js)
        self.assertIn("max_concept_chars: 64", self.js)
        self.assertIn("clamp(Number(match[1]), 1, CONFIG.max_move_steps)", self.js)

    def test_pages_expose_action_console_in_both_publish_modes(self):
        for html in (self.site_html, self.root_html):
            self.assertIn('id="action-form"', html)
            self.assertIn('id="action-input"', html)
            self.assertIn('id="action-state-hash"', html)
            self.assertIn('id="action-plan"', html)
            self.assertIn("WORLD STATE → SEED", html)
            self.assertIn("genesis-action-forge.js", html)
            self.assertIn("action-forge.css", html)
        self.assertIn(".action-forge", self.css)

    def test_legacy_lineage_is_adopted_without_old_authority(self):
        lineage = {item["name"]: item for item in self.contract["legacy_lineage"]}
        self.assertIn("JANUS_GENESIS_TEXT_ACTION_LOOP", lineage)
        self.assertIn("HYPNOS_VOICE_OF_CREATOR", lineage)
        self.assertIn("TD_ACTION_VOCABULARY", lineage)
        self.assertIn("bounded intent IR", lineage["JANUS_GENESIS_TEXT_ACTION_LOOP"]["reinterpretation"])
        self.assertIn("explicit input only", lineage["HYPNOS_VOICE_OF_CREATOR"]["reinterpretation"])


if __name__ == "__main__":
    unittest.main()
