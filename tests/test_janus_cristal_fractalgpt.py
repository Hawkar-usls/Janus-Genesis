#!/usr/bin/env python3
import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "janus_cristal_fractalgpt"
sys.path.insert(0, str(EXP))

P = EXP / "fractal_crystal_probe.py"
spec = importlib.util.spec_from_file_location("fcp", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

import fractalgpt_adapter as fga


class FractalCrystalTests(unittest.TestCase):
    def test_recovered_fractalgpt_exact_hash(self):
        got = hashlib.sha256((EXP / "recovered" / "FractalGPT.py").read_bytes()).hexdigest()
        self.assertEqual(got, fga.RECOVERED_SHA256)
        self.assertEqual(got, "11e6c97ae7169a0fae4e0ad17f2fb7fb23b10265b04b4b057e3c968d6d0a3662")

    def test_logistic_baseline_deterministic(self):
        a = m.logistic_trajectory("seed", 20, [0.5, 0.3, 0.2])
        b = m.logistic_trajectory("seed", 20, [0.5, 0.3, 0.2])
        self.assertEqual(a, b)

    def test_recovered_planners_are_deterministic(self):
        a, ra = fga.all_trajectories("seed", 10, [0.5, 0.3, 0.2])
        b, rb = fga.all_trajectories("seed", 10, [0.5, 0.3, 0.2])
        self.assertEqual(a, b)
        self.assertEqual(ra["trajectory_hashes"], rb["trajectory_hashes"])
        self.assertEqual(ra["model_receipt"], rb["model_receipt"])
        self.assertEqual(set(a), {"fractalgpt_koch", "fractalgpt_sierpinski", "fractalgpt_fbm", "fractalgpt_model"})

    def test_all_planners_are_bounded(self):
        recovered, _ = fga.all_trajectories("bounded", 12, [0.55, 0.4, 0.2])
        planners = {
            "logistic": m.logistic_trajectory("bounded", 12, [0.55, 0.4, 0.2]),
            **recovered,
        }
        for name, rows in planners.items():
            self.assertEqual(len(rows), 12, name)
            for r in rows:
                self.assertGreaterEqual(r["cx"], 0, name)
                self.assertLessEqual(r["cx"], 1, name)
                self.assertGreaterEqual(r["cy"], 0, name)
                self.assertLessEqual(r["cy"], 1, name)
                self.assertIn(r["scale"], [0.55, 0.4, 0.2], name)

    def test_recovered_model_actually_trains_and_generates(self):
        rows, receipt = fga.model_trajectory("model-test", 8, [0.5, 0.3])
        self.assertEqual(len(rows), 8)
        self.assertEqual(receipt["train_steps"], 8)
        self.assertGreater(receipt["generated_state_count"], 8)
        self.assertTrue(np.isfinite(receipt["initial_eval_mse"]))
        self.assertTrue(np.isfinite(receipt["final_eval_mse"]))

    def test_crop_window_stays_valid_for_every_planner(self):
        img = np.zeros((100, 160, 3), dtype=np.uint8)
        recovered, _ = fga.all_trajectories("crop", 8, [0.55, 0.2])
        planners = {"logistic": m.logistic_trajectory("crop", 8, [0.55, 0.2]), **recovered}
        for name, rows in planners.items():
            for row in rows:
                crop = m.crop_window(img, row)
                self.assertGreater(crop.size, 0, name)
                self.assertLessEqual(crop.shape[0], 100, name)
                self.assertLessEqual(crop.shape[1], 160, name)

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

    def test_same_windows_reused_for_control(self):
        rows = fga.koch_trajectory("same", 10, [0.5, 0.25])
        img = np.zeros((120, 120, 3), dtype=np.uint8)
        ctrl = m.block_shuffle(img, "ctrl", block=24)
        shapes_real = [m.crop_window(img, r).shape for r in rows]
        shapes_ctrl = [m.crop_window(ctrl, r).shape for r in rows]
        self.assertEqual(shapes_real, shapes_ctrl)


if __name__ == "__main__":
    unittest.main()
