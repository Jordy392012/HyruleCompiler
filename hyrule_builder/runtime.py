"""Runtime paths and environment for the Hyrule Windows builder."""
from __future__ import annotations
import os, re, subprocess, sys
from pathlib import Path
from typing import Mapping

HOOKSHOT_TAG = "v2.1.0"
SUPPORTED_LANGUAGES = ("en-US", "en-GB", "fr", "fr-CA", "de", "it", "es", "es-419", "pt-BR", "nl", "pl", "ru", "ja", "ko", "zh-Hans", "zh-Hant")

def app_data_root(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    base = env.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "HyruleBuilder"

def configure_app_data() -> Path:
    base = app_data_root()
    base.mkdir(parents=True, exist_ok=True)
    os.environ["HOOKSHOT_SETUP_BASE"] = str(base)
    return base

def tools_root(base: Path | None = None, tag: str = HOOKSHOT_TAG) -> Path:
    return (base or app_data_root()) / "versions" / tag / "HookshotBuilder" / "tools"

def cpu_target_from_name(cpu_name: str) -> str | None:
    if re.search(r"(?i)Ryzen.*(6600H|6600HS|6600U|6800H|6800HS|6800U|6900HS|6900HX|6980HX|5600H|5600HS|5600X|5700G|5800H|5800HS|5800X|5900HX|5900X|5950X)", cpu_name or ""):
        return "znver3"
    return None

def detected_cpu_target() -> str | None:
    if os.name != "nt":
        return None
    try:
        r = subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command","(Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8, check=False, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    except (OSError, subprocess.TimeoutExpired):
        return None
    return cpu_target_from_name(r.stdout.strip())

def build_environment(tool_root: Path, launcher_exe: str | Path | None = None, environ: Mapping[str, str] | None = None, cpu_target: str | None = None) -> dict[str, str]:
    env = dict(os.environ if environ is None else environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["A64_POLL_INTERVAL"] = "1"
    env["A64_POLL_HOT_ONLY"] = "1"
    env["RX_HOT_OPT"] = "O2"
    env["HOOKSHOT_SETUP_BASE"] = str(app_data_root(env))
    if launcher_exe:
        env["HOOKSHOT_BUILDER_EXE"] = str(launcher_exe)
        env["HOOKSHOT_BUILDER_ARGS"] = "" if getattr(sys,"frozen",False) else subprocess.list2cmdline(["-m","hyrule_builder"])
    for variable, folder in (("EMSDK","emsdk"),("RX_CPM","cpm"),("WGPU_NATIVE","wgpu-native")):
        candidate = tool_root / folder
        if candidate.is_dir():
            env[variable] = str(candidate)
    target = cpu_target if cpu_target is not None else detected_cpu_target()
    if target:
        env["RX_MARCH"] = target
    else:
        env.pop("RX_MARCH",None)
    return env

def source_arguments(*, nup=None, romfs=None, exefs=None, output, language="en-US", prepare_shaders=True) -> list[str]:
    args: list[str] = []
    if nup:
        args += ["--nup",str(Path(nup).resolve())]
    elif romfs and exefs:
        args += ["--romfs",str(Path(romfs).resolve()),"--exefs",str(Path(exefs).resolve())]
    else:
        raise ValueError("Choose a supported .nup dump or both romfs and exefs folders.")
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported language code.")
    args += ["--out",str(Path(output).resolve()),"--language",language]
    if not prepare_shaders:
        args.append("--no-prepare-shaders")
    return args

def check_arguments(*, nup=None, exefs=None) -> list[str]:
    if nup:
        return ["--check","--nup",str(Path(nup).resolve())]
    if exefs:
        return ["--check","--exefs",str(Path(exefs).resolve())]
    raise ValueError("No game dump was selected.")
