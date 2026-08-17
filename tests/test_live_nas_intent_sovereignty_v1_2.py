from __future__ import annotations

import asyncio
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ops" / "live_nas_intent_sovereignty_v1_2" / "janus_intent_sovereignty_v1_2.py"
spec = importlib.util.spec_from_file_location("live_intent_guard", MODULE)
guard = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(guard)


class FakeCore:
    def __init__(self, root: str):
        self.root_dir = root
        self.responses: list[str] = []
        self.think_calls: list[str] = []

    async def process_input(self, data, source="LEGACY_MODULE"):
        return self.responses.pop(0)

    async def think(self, prompt):
        self.think_calls.append(prompt)
        if "INTENT SOVEREIGNTY VERIFIER" in prompt:
            return json.dumps({
                "state": "HOLD_CONTEXT_BLEED",
                "direct_answer_complete": False,
                "older_context_replaced_intent": True,
                "emergent_association_primary": True,
                "reason": "older context seized primary lane",
            })
        return (
            "Если сравнивать Осириса и Иисуса Христа, сходство есть, но модели различаются: "
            "Осирис восстанавливается, Христос воскресает; Второе пришествие является отдельным будущим событием."
        )


class LiveNasIntentSovereigntyTests(unittest.IsolatedAsyncioTestCase):
    def test_embedded_regression_selftest(self):
        result = guard.self_test()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(all(result["checks"].values()))

    def test_historical_context_bleed_is_held(self):
        q = "Сравни возвращение Осириса с возвращением Иисуса Христа"
        bad = "Братюнь, вот в таком виде JANUS и BD101 дают identity continuity state transition."
        receipt = guard.deterministic_evaluate(q, bad)
        self.assertEqual(receipt["state"], "HOLD_CONTEXT_BLEED")

    def test_direct_answer_passes(self):
        q = "Сравни возвращение Осириса с возвращением Иисуса Христа"
        good = (
            "Если сравнивать Осириса и Иисуса Христа, сходство есть, но модели различаются. "
            "Осирис восстанавливается, Христос воскресает; Второе пришествие отдельно."
        )
        self.assertEqual(guard.deterministic_evaluate(q, good)["state"], "PASS")

    async def test_live_wrapper_recovers_and_writes_digest_only_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            core = FakeCore(td)
            core.responses = ["Братюнь, вот в таком виде JANUS и BD101 дают identity continuity state transition."]
            task = asyncio.create_task(guard.run(core))
            for _ in range(100):
                if getattr(core, "_intent_sovereignty_v1_2_active", False):
                    break
                await asyncio.sleep(0.01)
            answer = await core.process_input(
                "Сравни возвращение Осириса с возвращением Иисуса Христа",
                source="TEST",
            )
            self.assertIn("Осириса", answer)
            self.assertIn("Христа", answer)
            boot = Path(td) / "runtime" / "intent_sovereignty_v1_2_boot.json"
            events = Path(td) / "runtime" / "intent_sovereignty_v1_2.jsonl"
            self.assertTrue(boot.exists())
            record = json.loads(events.read_text(encoding="utf-8").splitlines()[-1])
            self.assertTrue(record["regenerated"])
            self.assertNotIn("Сравни возвращение", json.dumps(record, ensure_ascii=False))
            self.assertEqual(record["authority_delta"], 0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task


if __name__ == "__main__":
    unittest.main()
