from __future__ import annotations
import unittest
from hyrulefast.cpu_policy import automatic_worker_count, adaptive_worker_count, recommend_from_log


class CpuPolicyTests(unittest.TestCase):
    def test_hardware_aware_defaults(self):
        self.assertEqual(automatic_worker_count(16, True), 4)
        self.assertEqual(automatic_worker_count(16, False), 6)
        self.assertEqual(automatic_worker_count(8, True), 2)
        self.assertEqual(automatic_worker_count(1, False), 2)

    def test_gpu_pressure_throttles_and_recovers(self):
        self.assertEqual(adaptive_worker_count(4, 30.0, 30.0, True), 2)
        self.assertEqual(adaptive_worker_count(4, 25.0, 30.0, True), 3)
        self.assertEqual(adaptive_worker_count(4, 22.0, 30.0, True, current_workers=2), 2)
        self.assertEqual(adaptive_worker_count(4, 18.0, 30.0, True, current_workers=2), 4)
        self.assertEqual(adaptive_worker_count(5, 30.0, 30.0, False), 4)

    def test_log_recommendation_uses_latest_gpu_sample(self):
        log = "vk: GPU time 21.0 ms a frame (the longest submission 7.0 ms)\n"
        log += "vk: GPU time 29.0 ms a frame (the longest submission 8.0 ms)\n"
        result = recommend_from_log(log, 30.0, 16, True)
        self.assertEqual(result["gpu_ms"], 29.0)
        self.assertEqual(result["base_workers"], 4)
        self.assertEqual(result["recommended_workers"], 2)
        self.assertAlmostEqual(result["gpu_pressure"], 29.0 / 30.0)

    def test_missing_gpu_timing_keeps_safe_default(self):
        result = recommend_from_log("no timestamp support", 30.0, 16, True)
        self.assertEqual(result["recommended_workers"], 4)
        self.assertIn("No GPU timestamp", result["note"])


if __name__ == "__main__":
    unittest.main()
