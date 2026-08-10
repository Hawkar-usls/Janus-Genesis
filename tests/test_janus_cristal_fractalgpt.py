#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "experiments" / "janus_cristal_fractalgpt" / "fractal_crystal_probe.py"
spec = importlib.util.spec_from_file_location("fcp", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FractalCrystalTests(unittest.TestCase):
    def test_trajectory_is_deterministic(self):
        a = m.fractal_trajectory("seed", 20, [0.5, 0.3, 0.2])
        b = m.fractal_trajectory("seed", 20, [0.5, 0.3, 0.2])
        self.assertEqual(a, b)

    def test_trajectory_is_bounded(self):
        rows = m.fractal_trajectory("seed", 100, [0.55, 0.4, 0.2])
        self.assertEqual(len(rows), 100)
        for r in rows:
            self.assertGreater(r["cx"], 0)
            self.assertLess(r["cx"], 1)
            self.assertGreater(r["cy"], 0)
            self.assertLess(r["cy"], 1)
            self.assertIn(r["scale"], [0.55, 0.4, 0.2])

    def test_crop_window_stays_valid(self):
        img = np.zeros((100, 160, 3), dtype=np.uint8)
        for row in m.fractal_trajectory("crop", 20, [0.55, 0.2]):
            crop = m.crop_window(img, row)
            self.assertGreater(crop.size, 0)
            self.assertLessEqual(crop.shape[0], 100)
            self.assertLessEqual(crop.shape[1], 160)

    def test_shuffle_is_deterministic_but_changes_layout(self):
        img = np.arange(128 * 128 * 3, dtype=np.uint8).reshape(128, 128, 3)
        a = m.block_shuffle(img, "x", block=32)
        b = m.block_shuffle(img, "x", block=32)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, img))

    def test_classification_boundary(self):
        self.assertEqual(m.classify_token("HELLO"), "WORD_LIKE")
        self.assertEqual(m.classify_token("A1+B2=3"), "FORMULA_LIKE")
        self.assertEqual(m.classify_token("IF(X)"), "CODE_LIKE")
        self.assertEqual(m.classify_token("A3"), "SYMBOL_SEQUENCE")

    def test_same_trajectory_can_be_reused_for_control(self):
        rows = m.fractal_trajectory("same", 10, [0.5, 0.25])
        img = np.zeros((120, 120, 3), dtype=np.uint8)
        ctrl = m.block_shuffle(img, "ctrl", block=24)
        shapes_real = [m.crop_window(img, r).shape for r in rows]
        shapes_ctrl = [m.crop_window(ctrl, r).shape for r in rows]
        self.assertEqual(shapes_real, shapes_ctrl)


if __name__ == "__main__":
    unittest.main()
