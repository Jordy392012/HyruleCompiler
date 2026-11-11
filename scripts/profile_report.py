from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hyrulefast.profile_report import compare_profiles
from hyrulefast.mesh_fallback import inspect_source


def main() -> int:
    p = argparse.ArgumentParser(description="Analyze Hookshot CPU/GPU synchronization and memory-traffic logs.")
    p.add_argument("logs", nargs="+", help="Hookshot log files from comparable runs")
    p.add_argument("--json", dest="json_path", help="write machine-readable comparison JSON")
    p.add_argument("--hookshot-root", help="also inspect the local Hookshot mesh-fallback source")
    args = p.parse_args()
    rows = compare_profiles(args.logs)
    print("Hyrule Native Compiler — runtime profile comparison")
    print("Rank is based only on reported slowest-frame samples; repeat runs before selecting a winner.\n")
    for i, r in enumerate(rows, 1):
        print(f"{i}. {Path(r['source']).name}")
        print(f"   batching: {r['batched_submit_state'] or 'unknown'}; flushes/120 presents: {r['avg_flushes_per_120_presents']}")
        print(f"   poll flushes/120 presents: {r['avg_poll_flushes_per_120_presents']}; avg command buffers/flush: {r['avg_command_buffers_per_flush']}")
        print(f"   mean of logged slowest-frame samples: {r['avg_slowest_frame_ms_reported']}")
        print(f"   write-back MB compared/600 submits: {r['avg_writeback_mb_compared_per_600_submits']}")
        print(f"   mesh count-buffer skip messages: {r['mesh_count_buffer_skip_messages']}")
        for warning in r['warnings']:
            print(f"   NOTE: {warning}")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote {args.json_path}")
    if args.hookshot_root:
        m = inspect_source(args.hookshot_root)
        print("\nMesh fallback source inspection:")
        print(f"   {m.verdict}")
        print(f"   {m.detail}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
