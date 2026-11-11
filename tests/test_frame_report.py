from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from scripts.frame_report import report


class FrameReportTests(unittest.TestCase):
    def test_discards_startup_and_computes_fps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frames.csv"
            path.write_text(
                "frame,seconds,frame_ms\n"
                "1,0,100\n"
                "2,1,16.0\n"
                "3,2,16.0\n"
                "4,3,20.0\n",
                encoding="utf-8",
            )
            result = report(path, 1.0)
            self.assertEqual(result["frames"], 3)
            self.assertAlmostEqual(result["median_fps"], 62.5)
            self.assertAlmostEqual(result["one_percent_low_fps"], 50.0)


if __name__ == "__main__":
    unittest.main()
