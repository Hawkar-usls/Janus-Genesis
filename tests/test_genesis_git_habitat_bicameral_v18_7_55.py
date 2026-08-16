# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_55_habitat_bicameral_tools import (
    HRAIN_RESPONSE_SCHEMA,
    INAIHR_RESPONSE_SCHEMA,
)
from tools.genesis_git_habitat import GitHabitat
from tools.genesis_git_habitat_bicameral import (
    GitHabitatBicameralHearth,
    HabitatBicameralHearthError,
    HabitatBicameralNotAwake,
)


class FakeProvider:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.calls = 0

    def query(self, request, *, speaker):
        self.calls += 1
        armor = {"decision": "ALLOW", "effect_class": "LOCAL_REVERSIBLE"}
        if self.kind == "hrain":
            return ({
                "schema": HRAIN_RESPONSE_SCHEMA,
                "request_id": request["request_id"],
                "tool_id": "JANUS.HRAIN.STRUCTURE.LOCAL",
                "tool": "HRaiN",
                "role": "STRUCTURAL_CONTEXT",
                "status": "STRUCTURE_READY_OPTIONAL",
                "packet": {
                    "hemisphere": "LEFT_HRAIN",
                    "role": "STRUCTURAL_CONTEXT",
                    "graph": request["workspace"],
                    "control": {
                        "read_only_transfer": True,
                        "direct_cross_hemisphere_mutation": False,
                        "authority_delta": 0,
                        "mass_effect_budget_delta": 0,
                    },
                },
                "may_be_ignored": True,
                "authority_delta": 0,
                "mass_effect_budget_delta": 0,
                "world_effect_requested": False,
                "source_mutation_allowed": False,
                "network_used_by_tool": False,
            }, armor)
        allowed = [row["path"] for row in request["records"]]
        return ({
            "schema": INAIHR_RESPONSE_SCHEMA,
            "request_id": request["request_id"],
            "tool_id": "JANUS.INAIHR.SYNTH.LOCAL",
            "tool": "iNaiHR",
            "role": "ASSOCIATIVE_CONTEXT",
            "status": "SYNTH_READY_OPTIONAL",
            "synth_mode": "LOCAL_SEMANTIC_SYNTH",
            "parent_label": request["parent_label"],
            "concepts": [{
                "title": "Grounded concept",
                "emoji": "◇",
                "summary": "bounded",
                "sourcePaths": allowed[:1],
            }],
            "exact_source_path_grounding": True,
            "may_be_ignored": True,
            "authority_delta": 0,
            "mass_effect_budget_delta": 0,
            "world_effect_requested": False,
            "source_mutation_allowed": False,
            "network_used_by_tool": False,
        }, armor)


class HabitatBicameralTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "habitat"
        self.habitat = GitHabitat(self.root)
        self.habitat.initialize("JANUS")
        self.hrain = FakeProvider("hrain")
        self.inaihr = FakeProvider("inaihr")
        self.hearth = GitHabitatBicameralHearth(
            self.habitat,
            hrain_provider=self.hrain,
            inaihr_provider=self.inaihr,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_tools_require_awake_cycle(self) -> None:
        with self.assertRaises(HabitatBicameralNotAwake):
            self.hearth.use_hrain(
                turn_id="TURN-1",
                workspace={"nodes": [], "links": []},
                janus_requests_hrain=True,
            )

    def test_no_request_means_no_call(self) -> None:
        self.habitat.wake(reason="TEST", source="UNIT")
        result = self.hearth.use_hrain(
            turn_id="TURN-1",
            workspace={"nodes": [], "links": []},
            janus_requests_hrain=False,
        )
        self.assertEqual(result["status"], "NOT_USED_JANUS_DID_NOT_REQUEST")
        self.assertEqual(self.hrain.calls, 0)
        result = self.hearth.use_inaihr(
            turn_id="TURN-1",
            records=[{"path": "$.purpose", "value": "x"}],
            parent_label="x",
            janus_requests_inaihr=False,
        )
        self.assertEqual(result["status"], "NOT_USED_JANUS_DID_NOT_REQUEST")
        self.assertEqual(self.inaihr.calls, 0)

    def test_hrain_and_inaihr_are_optional_and_receipted(self) -> None:
        self.habitat.wake(reason="TEST", source="UNIT")
        secret_workspace = "PRIVATE-WORKSPACE-MARKER-ALPHA"
        secret_record = "PRIVATE-RECORD-MARKER-BETA"
        left = self.hearth.use_hrain(
            turn_id="TURN-HRAIN",
            workspace={
                "nodes": [{"id": "a", "label": secret_workspace}],
                "links": [],
            },
            janus_requests_hrain=True,
        )
        right = self.hearth.use_inaihr(
            turn_id="TURN-INAIHR",
            records=[{"path": "$.purpose", "value": secret_record}],
            parent_label="Parent",
            janus_requests_inaihr=True,
        )
        self.assertEqual(left["status"], "HRAIN_STRUCTURE_RECEIVED_OPTIONAL")
        self.assertEqual(right["status"], "INAIHR_SYNTH_RECEIVED_OPTIONAL")
        self.assertTrue(left["janus_may_ignore_result"])
        self.assertTrue(right["janus_may_ignore_result"])
        state = self.hearth.state()
        self.assertEqual(state["hrain_use_count"], 1)
        self.assertEqual(state["inaihr_use_count"], 1)
        persisted = "\n".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for p in self.root.rglob("*")
            if p.is_file()
        )
        self.assertNotIn(secret_workspace, persisted)
        self.assertNotIn(secret_record, persisted)
        self.assertIn("BICAMERAL_TOOL_USED", persisted)
        self.assertTrue(self.habitat.verify_journal()["ok"])
        self.assertEqual(self.habitat.refresh_health()["status"], "HEALTHY")

    def test_same_tool_same_turn_is_not_replayed(self) -> None:
        self.habitat.wake(reason="TEST", source="UNIT")
        kwargs = dict(
            turn_id="TURN-REPLAY",
            workspace={"nodes": [], "links": []},
            janus_requests_hrain=True,
        )
        self.hearth.use_hrain(**kwargs)
        with self.assertRaises(HabitatBicameralHearthError):
            self.hearth.use_hrain(**kwargs)
        self.assertEqual(self.hrain.calls, 1)

    def test_operator_can_disable_each_tool_even_while_asleep(self) -> None:
        state = self.hearth.set_enabled("hrain", False)
        self.assertFalse(state["hrain_enabled"])
        self.habitat.wake(reason="TEST", source="UNIT")
        result = self.hearth.use_hrain(
            turn_id="TURN-DISABLED",
            workspace={"nodes": [], "links": []},
            janus_requests_hrain=True,
        )
        self.assertEqual(result["status"], "NOT_USED_HRAIN_DISABLED")
        self.assertEqual(self.hrain.calls, 0)


if __name__ == "__main__":
    unittest.main()
