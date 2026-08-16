from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from audit_armor_effect_drift_v18_7_50 import classification  # noqa: E402


MATERIALIZER = ROOT / "tools" / "janus_nexus_materializer.py"
EXPECTED_CLASSIFICATION = "LOCAL_READ_ONLY_GIT_OBJECT_QUERY_SUBPROCESS"
ALLOWED_GIT_QUERY_SUBCOMMANDS = frozenset({"rev-parse", "ls-tree", "cat-file"})
FORBIDDEN_GIT_EFFECT_SUBCOMMANDS = frozenset(
    {"clone", "fetch", "push", "pull", "remote", "ls-remote", "send-pack", "receive-pack"}
)


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


class NexusMaterializerArmorInventoryTests(unittest.TestCase):
    def test_materializer_surface_has_explicit_inventory_classification(self):
        self.assertEqual(
            classification("tools/janus_nexus_materializer.py"),
            EXPECTED_CLASSIFICATION,
        )

    def test_materializer_git_helper_is_read_only_query_shape_when_present(self):
        if not MATERIALIZER.is_file():
            self.skipTest("materializer source is supplied by the integration head")

        tree = ast.parse(MATERIALIZER.read_text(encoding="utf-8"), filename=str(MATERIALIZER))
        helper = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "_git"
            ),
            None,
        )
        self.assertIsNotNone(helper, "materializer must retain one reviewed _git query helper")
        assert helper is not None

        process_calls = [
            node
            for node in ast.walk(helper)
            if isinstance(node, ast.Call) and dotted(node.func) == "subprocess.check_output"
        ]
        self.assertEqual(len(process_calls), 1)
        argv = process_calls[0].args[0]
        self.assertIsInstance(argv, ast.List)
        assert isinstance(argv, ast.List)
        self.assertGreaterEqual(len(argv.elts), 4)
        self.assertIsInstance(argv.elts[0], ast.Constant)
        self.assertEqual(argv.elts[0].value, "git")
        self.assertIsInstance(argv.elts[1], ast.Constant)
        self.assertEqual(argv.elts[1].value, "-C")
        self.assertTrue(
            any(isinstance(item, ast.Starred) for item in argv.elts),
            "reviewed helper must forward only explicitly supplied query args after git -C <repo>",
        )

        query_subcommands: set[str] = set()
        dynamic_query_calls: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or dotted(node.func) != "_git":
                continue
            if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
                dynamic_query_calls.append(int(getattr(node, "lineno", 0)))
                continue
            command = node.args[1].value
            if not isinstance(command, str):
                dynamic_query_calls.append(int(getattr(node, "lineno", 0)))
                continue
            query_subcommands.add(command)

        self.assertFalse(
            dynamic_query_calls,
            f"dynamic Git subcommand selection is not admitted: {dynamic_query_calls}",
        )
        self.assertTrue(query_subcommands)
        self.assertTrue(query_subcommands <= ALLOWED_GIT_QUERY_SUBCOMMANDS)
        self.assertFalse(query_subcommands & FORBIDDEN_GIT_EFFECT_SUBCOMMANDS)

    def test_classification_is_inventory_not_authority(self):
        source = (ROOT / "tools" / "audit_armor_effect_drift_v18_7_50.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Classification is deliberately NOT admission", source)
        self.assertIn("classification_is_security_certification", source)
        self.assertIn("repository_wide_complete_routing_coverage_proven", source)


if __name__ == "__main__":
    unittest.main()
