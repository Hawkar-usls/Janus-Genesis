import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CANONICAL = ROOT / ".janus" / "GENESIS_SCENE_INTENT_GRAPH_R0_4.json"
PUBLIC = ROOT / "contracts" / "GENESIS_SCENE_INTENT_GRAPH_R0_4.json"
EXECUTOR = ROOT / "site" / "genesis-scene-graph-executor-r0-4.js"
BRIDGE4 = ROOT / "site" / "genesis-command-bridge-v4.js"
BRIDGE3 = ROOT / "site" / "genesis-command-bridge-v3.js"
ROOT_HTML = ROOT / "index.html"
SITE_HTML = ROOT / "site" / "index.html"
CSS = ROOT / "site" / "scene-graph-r0-4.css"


class GenesisSceneIntentGraphR04Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.public = json.loads(PUBLIC.read_text(encoding="utf-8"))
        cls.executor = EXECUTOR.read_text(encoding="utf-8")
        cls.bridge4 = BRIDGE4.read_text(encoding="utf-8")
        cls.bridge3 = BRIDGE3.read_text(encoding="utf-8")
        cls.root_html = ROOT_HTML.read_text(encoding="utf-8")
        cls.site_html = SITE_HTML.read_text(encoding="utf-8")
        cls.css = CSS.read_text(encoding="utf-8")

    def test_public_contract_is_exact_mirror_and_r03_is_preserved(self):
        self.assertEqual(self.public, self.contract)
        self.assertEqual(self.contract["version"], "0.4.0")
        self.assertEqual(self.contract["status"], "IMPLEMENTED_CANDIDATE_R0_4")
        self.assertEqual(self.contract["supersedes_active_pages_runtime"], "GENESIS_COMMAND_RUNTIME_R0_3")
        self.assertTrue(self.contract["preserves_r0_3_as_lineage_and_fallback"])

    def test_graph_families_and_constitutional_limits_are_bounded(self):
        graph = self.contract["scene_graph"]
        self.assertEqual(
            set(graph["node_families"]),
            {"STRUCTURE", "ENTITY", "MATERIAL", "ATMOSPHERE", "TERRAIN", "SOUND", "EFFECT", "PRESENTATION", "RULE", "INSPECTION", "NAVIGATION"},
        )
        self.assertEqual(
            graph["limits"],
            {"max_nodes": 32, "max_edges": 64, "max_depth": 8, "max_resource_units": 128, "max_node_resource_units": 16, "cycles_allowed": False},
        )
        for token in ("max_nodes:32", "max_edges:64", "max_depth:8", "max_resource_units:128", "SCENE_GRAPH_CYCLE", "SCENE_GRAPH_DEPENDENCY_MISSING"):
            self.assertIn(token, self.executor)

    def test_whole_dag_is_validated_before_execution_and_partial_failure_is_visible(self):
        validation = self.contract["validation"]
        execution = self.contract["execution"]
        self.assertTrue(validation["validate_whole_graph_before_first_mutation"])
        self.assertTrue(validation["cycle_rejection_required"])
        self.assertEqual(execution["order"], "TOPOLOGICAL")
        self.assertEqual(set(execution["node_statuses"]), {"APPLIED", "FAILED", "SKIPPED_DEPENDENCY"})
        self.assertEqual(execution["failed_required_ancestor_policy"], "DEPENDENT_SKIPPED")
        self.assertTrue(execution["partial_failure_is_visible"])
        self.assertTrue(execution["node_receipt_required"])
        for token in ("validateGraph(graph)", "FAILED_REQUIRED_ANCESTOR", "SKIPPED_DEPENDENCY", "node_receipts", "partial_failure", "persistGraphReceipt"):
            self.assertIn(token, self.executor)

    def test_remote_graph_has_exact_byte_transport_proof_and_authority_gate(self):
        remote = self.contract["remote_nerve"]
        self.assertEqual(remote["preferred_route"], "POST /v1/genesis/scene-graph")
        self.assertEqual(remote["transport_proof"], "EXACT_UTF8_CANONICAL_GRAPH_JSON_SHA256")
        self.assertTrue(remote["live_claim_requires_real_https_health_pass"])
        self.assertFalse(remote["github_pages_is_persistent_post_host"])
        self.assertFalse(remote["github_actions_is_persistent_post_host"])
        for token in ("/v1/genesis/scene-graph", "verifyTransport", "canonical_graph_json", "canonical_graph_utf8_sha256", "SCENE_GRAPH_TRANSPORT_HASH_MISMATCH", "SCENE_GRAPH_AUTHORITY_BOUNDARY_INVALID"):
            self.assertIn(token, self.bridge4 + self.executor)

    def test_janus_graph_remains_proposal_and_genesis_validator_executes_nodes(self):
        authority = self.contract["authority"]
        self.assertFalse(authority["janus_graph_is_world_authority"])
        self.assertFalse(authority["model_output_is_command"])
        self.assertFalse(authority["player_text_is_direct_world_authority"])
        self.assertTrue(authority["genesis_validator_required"])
        self.assertFalse(authority["world_mutation_authorized_by_janus"])
        for token in ("janus_graph_is_world_authority!==false", "genesis_validator_required!==true", "runtime().executeIntent", "rt.executeIntent"):
            self.assertIn(token, self.executor + self.bridge4)

    def test_one_phrase_can_compile_to_many_scene_families_locally(self):
        example = self.contract["canonical_example"]
        self.assertEqual(example["root_subject"], "cathedral")
        self.assertTrue(example["ruined_tower_is_nested_detail"])
        self.assertTrue(example["organ_depends_on_cathedral"])
        self.assertTrue(example["organ_sound_depends_on_organ"])
        self.assertTrue(example["white_tree_grove_depends_on_cathedral"])
        for token in (
            "abandoned cathedral", "RUINED_TOWER", "pipe organ", "AUDIO_CUE", "white trees", "SPAWN_GROUP", "SPATIAL_RELATION", "scene hill", "weathered stone"
        ):
            self.assertIn(token, self.bridge4)

    def test_unresolved_semantics_become_visible_failure_not_arbitrary_code(self):
        local = self.contract["local_degraded_graph"]
        self.assertTrue(local["unresolved_becomes_visible_failure_node"])
        self.assertFalse(local["may_execute_arbitrary_user_code"])
        self.assertIn("VISIBLE_FAILURE", self.bridge4)
        self.assertIn("LOCAL_DEGRADED_NEEDS_JANUS_SEMANTIC_COMPILER", self.bridge4)
        surface = self.bridge4 + self.executor
        self.assertNotIn("eval(", surface)
        self.assertNotIn("new Function", surface)
        self.assertNotIn("Function(", surface)

    def test_sound_effect_material_and_rights_nodes_are_explicit(self):
        self.assertTrue(self.contract["audio_and_effect_policy"]["sound_is_graph_node"])
        self.assertTrue(self.contract["audio_and_effect_policy"]["effects_are_graph_nodes"])
        self.assertTrue(self.contract["audio_and_effect_policy"]["audio_disabled_is_visible_node_failure"])
        self.assertTrue(self.contract["asset_and_material_policy"]["rights_gate_before_external_asset_reference"])
        self.assertEqual(self.contract["asset_and_material_policy"]["required_rights"], "CC0")
        for token in ("AUDIO_DISABLED", "RUINED_TOWER", "RESOLVE_MATERIAL", "PROCEDURAL_KRR_FALLBACK", "rights_required", "PROVIDER_WIDE_CC0_ASSETS"):
            self.assertIn(token, self.bridge4 + self.executor)

    def test_active_pages_load_r03_lineage_before_r04_executor_and_bridge(self):
        for html in (self.root_html, self.site_html):
            self.assertIn("SCENE INTENT GRAPH R0.4", html)
            self.assertNotIn('id="mirror-panel"', html)
            self.assertIn('id="action-input"', html)
            pos_v3 = html.index("genesis-command-bridge-v3.js")
            pos_executor = html.index("genesis-scene-graph-executor-r0-4.js")
            pos_v4 = html.index("genesis-command-bridge-v4.js")
            self.assertLess(pos_v3, pos_executor)
            self.assertLess(pos_executor, pos_v4)
            self.assertIn("scene-graph-r0-4.css", html)

    def test_v4_capture_listener_prevents_r03_double_execution(self):
        # v3 stays loaded for lexical fallback and endpoint state. v4 must own submit first.
        for token in ("addEventListener('submit'", "true);", "e.stopImmediatePropagation()", "e.preventDefault()"):
            self.assertIn(token, self.bridge4)
        self.assertIn("localCompile", self.bridge3)

    def test_receipt_hud_has_applied_failed_and_dependency_skipped_surfaces(self):
        for token in ("scene-graph-receipts", "node-applied", "node-failed", "node-skipped_dependency"):
            self.assertIn(token, self.css)
        self.assertIn("APPLIED", self.bridge4)
        self.assertIn("FAILED", self.bridge4)
        self.assertIn("SKIPPED", self.bridge4)

    def test_no_embedded_secret_markers_in_new_r04_surface(self):
        surface = self.bridge4 + self.executor + self.root_html + self.site_html + self.css
        for token in ("AIza", "ghp_", "github_pat_", "Bearer "):
            self.assertNotIn(token, surface)


if __name__ == "__main__":
    unittest.main()
