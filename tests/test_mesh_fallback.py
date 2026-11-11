from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from hyrulefast.mesh_fallback import analyze_log, inspect_source


class MeshFallbackTests(unittest.TestCase):
    def test_detects_known_upstream_count_buffer_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draw = root / "gpu" / "vk" / "vk_draw.cpp"
            draw.parent.mkdir(parents=True)
            draw.write_text("""bool fallback_record(VkCommandBuffer cmd, Program& p, const DrawArgs& d) {
    if (d.count_addr) {
        return false;
    }
    if (d.indirect) vkCmdDispatchIndirect(cmd, mesh_conv_buf, mesh_conv_off);
    return true;
}
""", encoding="utf-8")
            r = inspect_source(root)
            self.assertTrue(r.count_buffer_rejected)
            self.assertTrue(r.gpu_indirect_path_present)
            self.assertEqual(r.verdict, "count-buffer mesh draws unsupported")

    def test_does_not_claim_support_on_source_layout_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draw = root / "gpu" / "vk" / "vk_draw.cpp"
            draw.parent.mkdir(parents=True)
            draw.write_text("// changed upstream file\n", encoding="utf-8")
            self.assertEqual(inspect_source(root).verdict, "unknown")

    def test_log_detection(self):
        r = analyze_log("vk: no mesh shaders: task and mesh programs run as compute shaders\nvk: fallback: a mesh draw with a count buffer is left out (issue 640)")
        self.assertTrue(r["fallback_enabled"])
        self.assertEqual(r["count_buffer_skip_messages"], 1)


if __name__ == "__main__":
    unittest.main()
