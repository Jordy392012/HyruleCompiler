from __future__ import annotations
import unittest
from hyrulefast.profile_report import parse_log_text

SAMPLE = """\
vk: batched submits on (RX_VK_BATCH)
vk: batched submits: 67 flushes, 3.1 command buffers each, over 120 presents; by reason: poll 12, wait 3, slot 4, present 20, cap 0, value 5, other 23
vk: status: 60 frames, the slowest 19.5 ms; VRAM: 2.1 / 8.0 GB
vk: a frame (fine): ms: banks 0.21, c1 0.03, storage buffers 0.87, hazards+pass 1.10, draw call 0.91
vk: mirror syncs (600 submits): 120 dirty pages from their submits' captures, 80 from earlier ones', 12 from guest memory as it was at the replay; 4 captures kept; 10 pages the GPU wrote copied over (3 live); 1 kept for the GPU (RX_VK_PROTECT_BARE)
vk: write-back diff (600 submits): 220 runs, 64.5 MB compared; 190 pages read into the shadows; 32.0 MB of shadows; pages the shadows knew that the CPU wrote: 20 in captures, 30 only in the collection, 40 only by the replay itself
vk: fallback: a mesh draw with a count buffer is left out (issue 640)
"""


class ProfileReportTests(unittest.TestCase):
    def test_extracts_sync_and_memory_stats(self):
        p = parse_log_text(SAMPLE)
        self.assertEqual(p.batched_submit_state, "on")
        self.assertEqual(p.batch_reports[0]["flushes"], 67)
        self.assertEqual(p.batch_reports[0]["poll"], 12)
        self.assertEqual(p.status_reports[0]["slowest_ms"], 19.5)
        self.assertEqual(p.fine_frame_ms[-1]["storage buffers"], 0.87)
        self.assertEqual(p.mirror_reports[0]["capture"], 120)
        self.assertEqual(p.writeback_reports[0]["mb_compared"], 64.5)
        self.assertEqual(p.mesh_count_buffer_skips_logged, 1)

    def test_empty_log_has_explicit_warnings(self):
        p = parse_log_text("", "empty.log")
        self.assertGreaterEqual(len(p.warnings), 2)
        self.assertIsNone(p.summary()["avg_flushes_per_120_presents"])


if __name__ == "__main__":
    unittest.main()
