"""Install Hyrule's adaptive background-worker governor into Hookshot."""
from __future__ import annotations

import shutil
from pathlib import Path

MARKER = "HYRULE_ADAPTIVE_WORKERS_V1"


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one supported Hookshot anchor, found {count}")
    return source.replace(old, new, 1)


def patch_cpu_governor(root: Path) -> bool:
    """Patch the Vulkan worker pool and GPU timestamp hook; fail before writing on source drift."""
    root = root.expanduser().resolve()
    jobs_path = root / "gpu" / "vk" / "vk_jobs.cpp"
    header_path = root / "gpu" / "vk" / "vk_jobs.h"
    replay_path = root / "gpu" / "vk" / "vk_replay.cpp"
    for path in (jobs_path, header_path, replay_path):
        if not path.is_file():
            raise FileNotFoundError(f"{path} is missing; expected a Hookshot source root")

    jobs = jobs_path.read_text(encoding="utf-8")
    header = header_path.read_text(encoding="utf-8")
    replay = replay_path.read_text(encoding="utf-8")
    states = [MARKER in jobs, MARKER in header, MARKER in replay]
    if all(states):
        if "jobs_set_gpu_pressure" in jobs and "jobs_set_gpu_pressure" in header and "jobs_set_gpu_pressure" in replay:
            return False
        raise RuntimeError("Hyrule worker markers exist but the integration is incomplete; restore the three .hyrule-backup files first")
    if any(states):
        raise RuntimeError("Partial Hyrule worker integration detected; no files were changed")

    jobs2 = _replace_once(
        jobs,
        "#include <condition_variable>\n",
        "#include <condition_variable>\n#include <cmath>\n#include <cstdlib>\n",
        "worker includes",
    )
    jobs2 = _replace_once(
        jobs2,
        "std::atomic<int> pending{0};\nbool started = false;\n",
        """std::atomic<int> pending{0};
std::atomic<unsigned> base_workers{0};
std::atomic<unsigned> target_workers{0};
unsigned active_workers = 0;   // (mu held)
bool started = false;

// HYRULE_ADAPTIVE_WORKERS_V1: background compilation stays asynchronous, but
// concurrency follows measured GPU pressure rather than a fixed worker count.
bool integrated_gpu() {
    return dev.props.deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU;
}

unsigned configured_worker_count() {
    static const unsigned count = [] {
        if (const char* raw = std::getenv("RX_VK_WORKERS")) {
            char* end = nullptr;
            const unsigned long requested = std::strtoul(raw, &end, 10);
            if (end != raw && end && *end == '\\0' && requested >= 1 && requested <= 8)
                return static_cast<unsigned>(requested);
            logf("vk: RX_VK_WORKERS='%s' is invalid (use 1..8); automatic worker budget selected", raw);
        }
        const unsigned logical = std::max(1u, std::thread::hardware_concurrency());
        const bool igpu = integrated_gpu();
        const unsigned divisor = igpu ? 4u : 3u;
        const unsigned ceiling = igpu ? 4u : 6u;
        return std::clamp((logical + divisor - 1u) / divisor, 2u, ceiling);
    }();
    return count;
}

""",
        "worker state",
    )
    jobs2 = _replace_once(
        jobs2,
        """            work_cv.wait(lk, [] { return !queue.empty(); });
            fn = std::move(queue.front().fn);
            queue.pop_front();
        }
        run_guarded(fn);
        pending--;
        jobs_notify();
""",
        """            work_cv.wait(lk, [] {
                return !queue.empty() &&
                       active_workers < target_workers.load(std::memory_order_relaxed);
            });
            fn = std::move(queue.front().fn);
            queue.pop_front();
            active_workers++;
        }
        run_guarded(fn);
        {
            std::lock_guard lk(mu);
            active_workers--;
            pending--;
        }
        work_cv.notify_all();
        jobs_notify();
""",
        "worker dispatch gating",
    )
    jobs2 = _replace_once(
        jobs2,
        """void start() {
    const unsigned n = std::clamp(std::thread::hardware_concurrency() / 3, 2u, 4u);
    for (unsigned i = 0; i < n; i++) std::thread(worker).detach();
""",
        """void start() {
    const unsigned n = configured_worker_count();
    base_workers.store(n, std::memory_order_relaxed);
    target_workers.store(n, std::memory_order_relaxed);
    for (unsigned i = 0; i < n; i++) std::thread(worker).detach();
""",
        "worker startup",
    )
    jobs2 = _replace_once(
        jobs2,
        "void jobs_notify() {\n",
        """// HYRULE_ADAPTIVE_WORKERS_V1: GPU timestamps throttle shader/pipeline work when rendering is saturated.
void jobs_set_gpu_pressure(double gpu_ms, double frame_ms) {
    static const bool adaptive = [] {
        const char* value = std::getenv("RX_VK_ADAPTIVE_WORKERS");
        return !value || std::atoi(value) != 0;
    }();
    if (!adaptive || !std::isfinite(gpu_ms) || !std::isfinite(frame_ms) ||
        gpu_ms <= 0.0 || frame_ms <= 0.0)
        return;

    const unsigned base = base_workers.load(std::memory_order_relaxed);
    if (!base) return;
    const double pressure = gpu_ms / frame_ms;
    const unsigned previous = target_workers.load(std::memory_order_relaxed);
    unsigned desired = previous ? previous : base;
    const unsigned reduction = integrated_gpu() ? 2u : 1u;

    // Hysteresis prevents rapid worker-count oscillation.
    if (pressure >= 0.92)
        desired = std::max(1u, base > reduction ? base - reduction : 1u);
    else if (pressure >= 0.80)
        desired = std::max(1u, base - 1u);
    else if (pressure <= 0.68)
        desired = base;

    if (desired != previous) {
        target_workers.store(desired, std::memory_order_relaxed);
        logf("vk: adaptive compiler workers %u -> %u (GPU busy estimate %.0f%%, RX_VK_ADAPTIVE_WORKERS=0 disables)",
             previous, desired, pressure * 100.0);
        work_cv.notify_all();
    }
}

void jobs_notify() {
""",
        "adaptive worker controller",
    )
    header2 = _replace_once(
        header,
        "void jobs_notify();\n",
        "void jobs_notify();\n/// HYRULE_ADAPTIVE_WORKERS_V1: throttle background builds from Vulkan GPU timestamps.\nvoid jobs_set_gpu_pressure(double gpu_ms, double frame_ms);\n",
        "worker API declaration",
    )
    anchor = '             (st_gpu_ns - l_gpu) / 120.0 / 1e6, st_gpu_max_ns / 1e6, (texture_made() - l_made) / 120.0);'
    replay2 = _replace_once(
        replay,
        anchor,
        anchor + chr(10) + '        // HYRULE_ADAPTIVE_WORKERS_V1: feed the measured GPU/frame ratio to the worker pool.' + chr(10)
        + '        const double gpu_ms = (st_gpu_ns - l_gpu) / 120.0 / 1e6;' + chr(10)
        + '        jobs_set_gpu_pressure(gpu_ms, secs * 1000.0 / 120.0);',
        "GPU timing hook",
    )
    replay2 = _replace_once(
        replay2,
        "            const double gpu_ms = (st_gpu_ns - l_gpu) / 120.0 / 1e6, draws = (d - l_d) / 120.0;\n",
        "            const double draws = (d - l_d) / 120.0;\n",
        "duplicate GPU time declaration",
    )

    # Validate all replacement points before changing any source file.
    if "active_workers < target_workers.load" not in jobs2:
        raise RuntimeError("worker gating verification failed; no files were changed")
    if "jobs_set_gpu_pressure(gpu_ms, secs * 1000.0 / 120.0);" not in replay2:
        raise RuntimeError("GPU timing hook verification failed; no files were changed")

    for path, original in ((jobs_path, jobs), (header_path, header), (replay_path, replay)):
        backup = path.with_name(path.name + ".hyrule-backup")
        if not backup.exists():
            shutil.copy2(path, backup)
    jobs_path.write_text(jobs2, encoding="utf-8", newline="\n")
    header_path.write_text(header2, encoding="utf-8", newline="\n")
    replay_path.write_text(replay2, encoding="utf-8", newline="\n")
    return True
