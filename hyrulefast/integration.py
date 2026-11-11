"""Install Hyrule's compiler pass and adaptive worker governor into Hookshot.

The integration is a checked source patch rather than copying or redistributing
Hookshot. It fails closed when upstream has moved an expected hook and saves
backups before changing the local checkout.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from . import __version__
from .worker_patch import patch_cpu_governor

MARKER = "HYRULE_POLL_DECIMATION_V1"

IMPORT_ANCHOR = "import re\n\nimport a64_lift\n"
CALL_ANCHOR = "        text, n = add_polls(text)\n"
INSTALL_ANCHOR = "    base = a64_lift.Lifter.emit_function\n"
SETUP_ANCHOR = "_installed = False\nstats ="

INTEGRATION_IMPORT = (
    "import os\n"
    "import re\n\n"
    "import a64_lift\n"
    "from hyrule_pollpass import add_polls as _hyrule_add_polls\n"
)

INTEGRATION_SETUP = '''# HYRULE_POLL_DECIMATION_V1: profile-scoped experimental poll pass.
def _hyrule_load_hot_functions():
    path = os.environ.get("A64_HOT_FUNCS", "")
    hot = set()
    if not path:
        return hot
    try:
        with open(path, encoding="ascii", errors="ignore") as f:
            for line in f:
                item = line.strip()
                if item.startswith("f_") and len(item) == 10:
                    try:
                        hot.add(int(item[2:], 16))
                    except ValueError:
                        pass
    except OSError:
        pass
    return hot


def _hyrule_poll_configuration():
    try:
        interval = int(os.environ.get("A64_POLL_INTERVAL", "1"))
    except ValueError as exc:
        raise SystemExit("A64_POLL_INTERVAL must be one of 1, 2, 4, 8, 16") from exc
    if interval not in (1, 2, 4, 8, 16):
        raise SystemExit("A64_POLL_INTERVAL must be one of 1, 2, 4, 8, 16")
    hot_only = os.environ.get("A64_POLL_HOT_ONLY", "1").strip().lower() not in ("0", "false", "no", "off")
    hot = _hyrule_load_hot_functions()
    if interval > 1 and hot_only and not hot:
        print("hyrule: poll decimation requested, but no A64_HOT_FUNCS profile exists; baseline polling retained", flush=True)
    return interval, hot_only, hot


'''


def patch_hookshot(root: Path) -> bool:
    """Patch a Hookshot checkout. Returns True when a change was made."""
    root = root.expanduser().resolve()
    poll_path = root / "nx2" / "poll.py"
    if not poll_path.is_file():
        raise FileNotFoundError(f"{poll_path} does not exist; select the Hookshot source root")

    source = poll_path.read_text(encoding="utf-8")
    helper_src = Path(__file__).with_name("pollpass.py").read_text(encoding="utf-8")
    helper_path = root / "nx2" / "hyrule_pollpass.py"

    if MARKER in source:
        worker_changed = patch_cpu_governor(root) if (root / "gpu" / "vk" / "vk_jobs.cpp").is_file() else False
        helper_changed = not helper_path.is_file() or helper_path.read_text(encoding="utf-8") != helper_src
        if helper_changed:
            helper_path.write_text(helper_src, encoding="utf-8", newline="\\n")
        return helper_changed or worker_changed

    if source.count(IMPORT_ANCHOR) != 1:
        raise RuntimeError("nx2/poll.py import block differs from the supported Hookshot source; no files were changed")
    if source.count(CALL_ANCHOR) != 1:
        raise RuntimeError("nx2/poll.py emitter hook differs from the supported Hookshot source; no files were changed")
    if source.count(INSTALL_ANCHOR) != 1:
        raise RuntimeError("nx2/poll.py install hook differs from the supported Hookshot source; no files were changed")
    if source.count(SETUP_ANCHOR) != 1:
        raise RuntimeError("nx2/poll.py setup block differs from the supported Hookshot source; no files were changed")

    patched = source.replace(IMPORT_ANCHOR, INTEGRATION_IMPORT, 1)
    patched = patched.replace(SETUP_ANCHOR, INTEGRATION_SETUP + SETUP_ANCHOR, 1)
    patched = patched.replace(
        INSTALL_ANCHOR,
        INSTALL_ANCHOR + "    poll_interval, poll_hot_only, poll_hot_functions = _hyrule_poll_configuration()\n",
        1,
    )
    patched = patched.replace(
        CALL_ANCHOR,
        "        active_interval = poll_interval if (not poll_hot_only or e in poll_hot_functions) else 1\n"
        "        text, n = _hyrule_add_polls(text, active_interval)\n",
        1,
    )
    if (MARKER not in patched or patched.count("_hyrule_add_polls(text, active_interval)") != 1
            or patched.count("def _hyrule_poll_configuration()") != 1
            or patched.count("poll_interval, poll_hot_only, poll_hot_functions = _hyrule_poll_configuration()") != 1):
        raise RuntimeError("internal patch verification failed; no files were changed")

    # Validate and patch the Vulkan worker pool before changing nx2/poll.py.
    if (root / "gpu" / "vk" / "vk_jobs.cpp").is_file():
        patch_cpu_governor(root)
    helper_path.write_text(helper_src, encoding="utf-8", newline="\n")
    backup = poll_path.with_suffix(".py.hyrule-backup")
    if not backup.exists():
        shutil.copy2(poll_path, backup)
    poll_path.write_text(patched, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Hyrule's experimental compiler pass into Hookshot.")
    parser.add_argument("hookshot_root", type=Path, help="path to a Hookshot source checkout")
    args = parser.parse_args()
    changed = patch_hookshot(args.hookshot_root)
    if changed:
        print(f"Hyrule optimizer {__version__} installed in {args.hookshot_root.resolve()}")
        print("A backup was saved as nx2/poll.py.hyrule-backup")
    else:
        print("Hyrule optimizer is already installed and up to date")
    print("Default A64_POLL_INTERVAL=1 keeps upstream behaviour unchanged.")
    print("For an experiment, set A64_POLL_INTERVAL=4 or 8; it applies only to profiled hot functions by default.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
