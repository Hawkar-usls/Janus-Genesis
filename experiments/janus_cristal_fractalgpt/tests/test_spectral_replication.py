#!/usr/bin/env python3
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

P = EXP / "spectral_replication_probe.py"
spec = importlib.util.spec_from_file_location("srp", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SpectralReplicationTests(unittest.TestCase):
    def test_frozen_manifest_matches_runtime(self):
        manifest = json.loads((EXP / "spectral_replication_pairs.json").read_text(encoding="utf-8"))
        m.assert_frozen_protocol(manifest)
        self.assertEqual(m.EXPECTED_WEIGHTS, {"luminance": 0.40, "chromaticity": 0.40, "edge": 0.20})
        self.assertEqual(m.EXPECTED_HOTSPOT_QUANTILE, 0.95)
        self.assertEqual(m.EXPECTED_GAMMA, 0.72)

    def test_retuning_is_rejected(self):
        manifest = json.loads((EXP / "spectral_replication_pairs.json").read_text(encoding="utf-8"))
        manifest["frozen_protocol"]["difference_weights"]["edge"] = 0.21
        with self.assertRaises(AssertionError):
            m.assert_frozen_protocol(manifest)

    def test_candidate_provenance_is_not_silently_confirmed(self):
        manifest = json.loads((EXP / "spectral_replication_pairs.json").read_text(encoding="utf-8"))
        pair = next(p for p in manifest["pairs"] if p["id"].startswith("LUCASFASSARI"))
        status = pair["same_specimen_status"]
        self.assertTrue(status.startswith("PROBABLE"))
        self.assertNotEqual(status, "CONFIRMED_SAME_SPECIMEN")
        self.assertIn("NOT_EXPLICITLY_CONFIRMED", status)

    def test_anchor_is_explicitly_not_replication(self):
        manifest = json.loads((EXP / "spectral_replication_pairs.json").read_text(encoding="utf-8"))
        anchor = next(p for p in manifest["pairs"] if p["id"].startswith("ALATAY"))
        self.assertEqual(anchor["role"], "FROZEN_DISCOVERY_ANCHOR_NOT_REPLICATION")

    def test_geometry_corroboration_on_identical_textured_scene(self):
        rng = np.random.default_rng(1138)
        img = rng.integers(0, 256, (420, 620, 3), dtype=np.uint8)
        for i in range(25):
            x = 20 + (i * 23) % 560
            y = 20 + (i * 37) % 360
            cv2.circle(img, (x, y), 7 + i % 5, (255, 255, 255), 2)
        r = m.geometry_corroboration(img, img.copy())
        self.assertEqual(r["status"], "IMAGE_GEOMETRY_SUPPORTS_SAME_SCENE")
        self.assertGreaterEqual(r["homography_inliers"], 12)


if __name__ == "__main__":
    unittest.main()
