#!/usr/bin/env python3
"""Install Hyrule's compiler pass into an existing Hookshot source checkout."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from hyrulefast.integration import patch_hookshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Hyrule generated-code optimization into Hookshot.")
    parser.add_argument("hookshot_root", type=Path, help="path to the Hookshot source checkout")
    args = parser.parse_args()
    changed = patch_hookshot(args.hookshot_root)
    if changed:
        print(f"Installed into: {args.hookshot_root.resolve()}")
        print("Backups: nx2/poll.py.hyrule-backup and gpu/vk/*.hyrule-backup")
    else:
        print("Already installed and up to date.")
    print("Safe default: A64_POLL_INTERVAL=1 (same polling behavior as upstream).")
    print("Experimental: interval 2/4/8/16, applied only to profile-hot functions by default.")
    print("CPU governor: RX_VK_WORKERS=1..8; RX_VK_ADAPTIVE_WORKERS=0 disables GPU-pressure throttling.")
    print("AVX2 capture copy: build with a compatible CPU target, then A/B RX_VK_CAPTURE_NT=1.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
