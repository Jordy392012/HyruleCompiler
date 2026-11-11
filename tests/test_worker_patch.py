from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from hyrulefast.worker_patch import patch_cpu_governor


JOBS_CPP = """#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>
#include <vector>
namespace mkwvk {
std::mutex mu;
std::condition_variable work_cv, done_cv;
struct Entry { std::function<void()> fn; const std::atomic<bool>* flag; };
std::deque<Entry> queue;
std::atomic<int> pending{0};
bool started = false;
void run_guarded(std::function<void()>& fn) { fn(); }
void worker() {
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL);
    for (;;) {
        std::function<void()> fn;
        {
            std::unique_lock lk(mu);
            work_cv.wait(lk, [] { return !queue.empty(); });
            fn = std::move(queue.front().fn);
            queue.pop_front();
        }
        run_guarded(fn);
        pending--;
        jobs_notify();
    }
}
void start() {
    const unsigned n = std::clamp(std::thread::hardware_concurrency() / 3, 2u, 4u);
    for (unsigned i = 0; i < n; i++) std::thread(worker).detach();
    started = true;
}
void jobs_notify() {
    std::lock_guard lk(mu);
    done_cv.notify_all();
}
}
"""

JOBS_H = """namespace mkwvk {
void jobs_notify();
}
"""

REPLAY_CPP = "\n".join((
    "void report() {",
    '        logf("vk: GPU time %.1f ms a frame (the longest submission %.1f ms); %.1f textures made a frame",',
    "             (st_gpu_ns - l_gpu) / 120.0 / 1e6, st_gpu_max_ns / 1e6, (texture_made() - l_made) / 120.0);",
    "    {",
    "            const double gpu_ms = (st_gpu_ns - l_gpu) / 120.0 / 1e6, draws = (d - l_d) / 120.0;",
    "    }",
    "}",
)) + "\n"


class WorkerPatchTests(unittest.TestCase):
    def _fixture(self, root: Path):
        (root / "gpu" / "vk").mkdir(parents=True)
        (root / "gpu" / "vk" / "vk_jobs.cpp").write_text(JOBS_CPP, encoding="utf-8")
        (root / "gpu" / "vk" / "vk_jobs.h").write_text(JOBS_H, encoding="utf-8")
        (root / "gpu" / "vk" / "vk_replay.cpp").write_text(REPLAY_CPP, encoding="utf-8")

    def test_patch_is_checked_backed_up_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            self.assertTrue(patch_cpu_governor(root))
            jobs = (root / "gpu" / "vk" / "vk_jobs.cpp").read_text(encoding="utf-8")
            replay = (root / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8")
            self.assertIn("HYRULE_ADAPTIVE_WORKERS_V1", jobs)
            self.assertIn("active_workers < target_workers.load", jobs)
            self.assertNotIn(chr(0), jobs)
            self.assertIn("*end == '" + chr(92) + "0'", jobs)
            self.assertIn("jobs_set_gpu_pressure(gpu_ms, secs * 1000.0 / 120.0);", replay)
            self.assertTrue((root / "gpu" / "vk" / "vk_jobs.cpp.hyrule-backup").is_file())
            self.assertFalse(patch_cpu_governor(root))

    def test_source_drift_fails_before_writing_any_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fixture(root)
            path = root / "gpu" / "vk" / "vk_jobs.cpp"
            path.write_text("// unknown upstream\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                patch_cpu_governor(root)
            self.assertEqual(path.read_text(encoding="utf-8"), "// unknown upstream\n")
            self.assertFalse((root / "gpu" / "vk" / "vk_jobs.h.hyrule-backup").exists())


if __name__ == "__main__":
    unittest.main()
