from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import janus_physical_gate_receipt_join as gate

GENESIS = "227d42d6848790031916cac53d39961a19c35d08"
SWARM = "b0bb07418cb1c0e1bc2da8ae443977825c0b19d1"


def owner_receipt():
    return {
        "schema": gate.SCHEMA,
        "kind": gate.OWNER_KIND,
        "view": {"genesis_main_sha": GENESIS, "swarm_main_sha": SWARM},
        "markers": copy.deepcopy(gate.OWNER_MARKERS),
        "privacy": copy.deepcopy(gate.OWNER_PRIVACY),
    }


def nas_receipt():
    return {
        "schema": gate.SCHEMA,
        "kind": gate.NAS_KIND,
        "view": {"genesis_main_sha": GENESIS, "swarm_main_sha": SWARM},
        "markers": copy.deepcopy(gate.NAS_MARKERS),
        "live": copy.deepcopy(gate.NAS_LIVE),
    }


class PhysicalGateJoinTests(unittest.TestCase):
    def test_positive_join_stops_below_final_acceptance(self):
        result = gate.join(owner_receipt(), nas_receipt(), GENESIS, SWARM)
        self.assertEqual(result["markers"]["REAL_OWNER44_SOURCE_REPLAY"], "PASS")
        self.assertEqual(result["markers"]["LIVE_NAS_164_HR1_HR10"], "PASS")
        self.assertTrue(result["markers"]["READY_FOR_FINAL_162_GAUNTLET"])
        self.assertFalse(result["markers"]["FULL_ISSUE_162_ACCEPTANCE"])
        self.assertEqual(result["markers"]["AUTHORITY_DELTA"], 0)

    def test_genesis_view_drift_fails_closed(self):
        value = owner_receipt()
        value["view"]["genesis_main_sha"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "GENESIS_SHA_DRIFT"):
            gate.join(value, nas_receipt(), GENESIS, SWARM)

    def test_private_exact_pin_disclosure_fails_closed(self):
        value = owner_receipt()
        value["privacy"]["private_exact_pins_disclosed"] = True
        with self.assertRaises(ValueError):
            gate.join(value, nas_receipt(), GENESIS, SWARM)

    def test_reference_only_nas_cannot_pass_as_live(self):
        value = nas_receipt()
        value["live"]["reference_only"] = True
        with self.assertRaises(ValueError):
            gate.join(owner_receipt(), value, GENESIS, SWARM)

    def test_missing_hr_gate_fails_closed(self):
        value = nas_receipt()
        del value["markers"]["HR7"]
        with self.assertRaisesRegex(ValueError, "KEYSET_MISMATCH"):
            gate.join(owner_receipt(), value, GENESIS, SWARM)

    def test_unknown_field_rejected_to_reduce_public_leak_surface(self):
        value = owner_receipt()
        value["private_repo"] = "must-not-be-accepted"
        with self.assertRaisesRegex(ValueError, "KEYSET_MISMATCH"):
            gate.join(value, nas_receipt(), GENESIS, SWARM)

    def test_output_is_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "join.json"
            gate._write_private_no_overwrite(target, {"ok": True})
            self.assertTrue(target.exists())
            with self.assertRaises(FileExistsError):
                gate._write_private_no_overwrite(target, {"ok": False})


if __name__ == "__main__":
    unittest.main()
