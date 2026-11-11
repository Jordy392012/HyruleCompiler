#!/usr/bin/env python3
"""Summarize Hookshot RX_VK_FRAME_LOG CSVs for repeatable A/B comparisons."""
from __future__ import annotations
import argparse
import csv
import math
import statistics
from pathlib import Path


def load_times(path: Path, discard_seconds: float) -> list[float]:
    rows: list[tuple[float, float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if len(row) < 3:
                continue
            try:
                elapsed = float(row[1])
                frame_ms = float(row[2])
            except (ValueError, TypeError):
                continue
            if math.isfinite(elapsed) and math.isfinite(frame_ms) and frame_ms > 0:
                rows.append((elapsed, frame_ms))
    if not rows:
        raise ValueError(f"No valid frame timing rows found in {path}")
    start = rows[0][0] + discard_seconds
    return [ms for seconds, ms in rows if seconds >= start]


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    index = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


def report(path: Path, discard_seconds: float) -> dict[str, float | int]:
    ms = load_times(path, discard_seconds)
    median_ms = statistics.median(ms)
    p95_ms = percentile(ms, 0.95)
    p99_ms = percentile(ms, 0.99)
    return {
        "frames": len(ms),
        "median_fps": 1000.0 / median_ms,
        "median_frame_ms": median_ms,
        "one_percent_low_fps": 1000.0 / p99_ms,
        "p95_frame_ms": p95_ms,
        "p99_frame_ms": p99_ms,
        "mean_frame_ms": statistics.fmean(ms),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("log", type=Path)
    p.add_argument("--discard-seconds", type=float, default=15.0, help="ignore startup/shader warm-up (default: 15s)")
    p.add_argument("--compare", type=Path, help="baseline CSV to compare against this optimized run")
    a = p.parse_args()
    result = report(a.log, a.discard_seconds)
    print(f"Log: {a.log}")
    print(f"Frames analyzed: {result['frames']}")
    print(f"Median FPS: {result['median_fps']:.2f}")
    print(f"Median frame time: {result['median_frame_ms']:.2f} ms")
    print(f"1% low FPS (from p99 frame time): {result['one_percent_low_fps']:.2f}")
    print(f"P95 / P99 frame time: {result['p95_frame_ms']:.2f} / {result['p99_frame_ms']:.2f} ms")
    print(f"Mean frame time: {result['mean_frame_ms']:.2f} ms")
    if a.compare:
        baseline = report(a.compare, a.discard_seconds)
        for key, label in (("median_fps", "Median FPS"), ("one_percent_low_fps", "1% low FPS")):
            delta = (result[key] / baseline[key] - 1.0) * 100.0 if baseline[key] else float("nan")
            print(f"{label}: {baseline[key]:.2f} -> {result[key]:.2f} ({delta:+.2f}%)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
