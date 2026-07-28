from __future__ import annotations

import copy
import re
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_playable import PlayableGenesisV187


class GenesisV18710CenturyRepairTests(unittest.TestCase):
    def test_mara_terminal_rupture_uses_stable_present_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.set_free_other_seed_for_testing(
                "century-absurd-post-irony-low-entropy-v1810"
            )
            world.register_player("century-witness", display_name="Witness")
            profile = world.free_other_state("century-witness")["profile"]
            self.assertIn("mara", profile["others"])

            result = world.record_free_other_value_conflict(
                "century-witness",
                "mara",
                player_position="превратить квартал в музей",
                other_position="сохранить живые дома и право жителей менять их",
                severity=7,
                respected_boundary=False,
                final=True,
            )
            reason = result["relationship"]["reason_text"]

            self.assertTrue(result["terminated"])
            self.assertIn("Мара сохраняет собственную позицию", reason)
            self.assertIn("и завершает связь", reason)
            self.assertNotRegex(
                reason,
                re.compile(r"\bМара\s+(?:сохранил|завершил|ушёл|выбрал)\b", re.I),
            )
            events = [
                event
                for event in world.memory.read_events("century-witness")
                if event["event_type"] == "free_other_relationship_terminated"
            ]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["payload"]["reason_text"], reason)
            self.assertTrue(world.verify_free_other_state()[0])
            self.assertTrue(world.memory.verify_chronicle()[0])
            self.assertTrue(world.verify_possibility_graph()[0])

    def test_proofpack_witnesses_completed_audit_and_has_verifiable_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            world = PlayableGenesisV187(Path(directory))
            world.register_player("proof-witness", display_name="Proof Witness")
            audit_id = world.begin_lived_audit(
                "proof-witness",
                label="completion-first proofpack",
                git_commit="test-commit",
                action_script_sha256="a" * 64,
            )
            world.process_action("proof-witness", "прожить один тихий проверочный день")
            proofpack = world.build_lived_audit_proofpack(
                audit_id,
                result={"status": "completed in test"},
            )

            self.assertEqual(proofpack["audit"]["status"], "COMPLETE")
            self.assertTrue(proofpack["audit"]["completed_at"])
            self.assertEqual(
                proofpack["audit"]["proofpack_sha256"],
                proofpack["proofpack_sha256"],
            )
            valid, error = world.verify_lived_audit_proofpack(proofpack)
            self.assertTrue(valid, error)
            stored = world._i0_store()["audits"][audit_id]
            self.assertEqual(stored["status"], "COMPLETE")
            self.assertEqual(stored["proofpack_sha256"], proofpack["proofpack_sha256"])

            tampered = copy.deepcopy(proofpack)
            tampered["result"]["status"] = "forged after sealing"
            valid, error = world.verify_lived_audit_proofpack(tampered)
            self.assertFalse(valid)
            self.assertEqual(error, "proofpack hash mismatch")


if __name__ == "__main__":
    unittest.main()
