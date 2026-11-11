#!/usr/bin/env python3
"""Recommend RX_VK_WORKERS from a Hookshot log and matching frame-time CSV."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import statistics
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from hyrulefast.cpu_policy import recommend_from_log
from scripts.frame_report import load_times


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path, help="Hookshot log copied by run_gpu_profile.ps1")
    parser.add_argument("--frame-ms", type=float, help="median frame time in ms")
    parser.add_argument("--frame-csv", type=Path, help="matching RX_VK_FRAME_LOG CSV")
    parser.add_argument("--discard-seconds", type=float, default=15.0)
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--gpu-type", choices=("integrated", "discrete"), default="integrated")
    parser.add_argument("--current-workers", type=int)
    args = parser.parse_args()

    if args.frame_csv:
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
    print(f"PowerShell override: $env:RX_VK_WORKERS = '{result['recommended_workers']}'")
    print("The runtime governor remains enabled unless RX_VK_ADAPTIVE_WORKERS=0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
