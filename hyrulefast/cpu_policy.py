"""Hardware-aware CPU compilation policy for Hookshot's Vulkan backend."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import re
import statistics

_GPU_TIME = re.compile(r"vk: GPU time ([0-9]+(?:\.[0-9]+)?) ms a frame")


def automatic_worker_count(logical_threads: int, integrated_gpu: bool) -> int:
    """Choose a conservative background compile budget from CPU/GPU topology."""
    logical = max(1, int(logical_threads))
    divisor = 4 if integrated_gpu else 3
    ceiling = 4 if integrated_gpu else 6
    return min(ceiling, max(2, (logical + divisor - 1) // divisor))


def adaptive_worker_count(
    base_workers: int,
    gpu_ms: float,
    frame_ms: float,
    integrated_gpu: bool,
    current_workers: int | None = None,
) -> int:
    """Mirror the runtime governor's hysteresis and GPU-pressure thresholds."""
    base = max(1, min(8, int(base_workers)))
    current = base if current_workers is None else max(1, min(8, int(current_workers)))
    if not math.isfinite(gpu_ms) or not math.isfinite(frame_ms) or gpu_ms <= 0 or frame_ms <= 0:
        return current

    pressure = gpu_ms / frame_ms
    reduction = 2 if integrated_gpu else 1
    if pressure >= 0.92:
        return max(1, base - reduction)
    if pressure >= 0.80:
        return max(1, base - 1)
    if pressure <= 0.68:
        return base
    return current


def recommend_from_log(
    log_text: str,
    frame_ms: float,
    logical_threads: int,
    integrated_gpu: bool,
    current_workers: int | None = None,
) -> dict[str, float | int | str]:
    """Recommend the next run's worker override using Hookshot GPU timestamps."""
    samples = [float(m.group(1)) for m in _GPU_TIME.finditer(log_text)]
    base = automatic_worker_count(logical_threads, integrated_gpu)
    if not samples:
        return {
            "gpu_type": "integrated" if integrated_gpu else "discrete",
            "logical_threads": logical_threads,
            "base_workers": base,
            "recommended_workers": current_workers or base,
            "gpu_ms": float("nan"),
            "frame_ms": frame_ms,
            "gpu_pressure": float("nan"),
            "note": "No GPU timestamp sample found; use the hardware-aware default.",
        }
    gpu_ms = samples[-1]
    pressure = gpu_ms / frame_ms if frame_ms > 0 else float("nan")
    target = adaptive_worker_count(base, gpu_ms, frame_ms, integrated_gpu, current_workers)
    return {
        "gpu_type": "integrated" if integrated_gpu else "discrete",
        "logical_threads": logical_threads,
        "base_workers": base,
        "recommended_workers": target,
        "gpu_ms": gpu_ms,
        "frame_ms": frame_ms,
        "gpu_pressure": pressure,
        "note": "Approximate pressure estimate; confirm with alternating runs.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend Hookshot background compile workers from a GPU profile log.")
    parser.add_argument("log", type=Path, help="Hookshot hookshot_log.txt copied by run_gpu_profile.ps1")
    parser.add_argument("--frame-ms", type=float, help="median frame time in milliseconds")
    parser.add_argument("--frame-csv", type=Path, help="matching RX_VK_FRAME_LOG CSV; median is calculated after startup discard")
    parser.add_argument("--discard-seconds", type=float, default=15.0)
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 2, help="logical CPU thread count")
    parser.add_argument("--gpu-type", choices=("integrated", "discrete"), default="integrated")
    parser.add_argument("--current-workers", type=int, help="previous RX_VK_WORKERS value, if testing the hysteresis region")
    args = parser.parse_args()
    if args.frame_csv:
        from scripts.frame_report import load_times
        frame_ms = statistics.median(load_times(args.frame_csv, args.discard_seconds))
    elif args.frame_ms is not None:
        frame_ms = args.frame_ms
    else:
        parser.error("supply --frame-ms or --frame-csv")
    if frame_ms <= 0 or args.threads < 1:
        parser.error("frame time and --threads must be positive")
    result = recommend_from_log(
        args.log.read_text(encoding="utf-8", errors="replace"),
        frame_ms,
        args.threads,
        args.gpu_type == "integrated",
        args.current_workers,
    )
    for key, value in result.items():
        print(f"{key}: {value}")
    print(f"PowerShell: $env:RX_VK_WORKERS = '{result['recommended_workers']}'")
    print("Keep RX_VK_ADAPTIVE_WORKERS=1 to let runtime GPU timestamps throttle this value further.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
