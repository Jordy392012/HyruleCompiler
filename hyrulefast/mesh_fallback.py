"""Source/log diagnostics for Hookshot's mesh-shader compute fallback.

The existing fallback supports ordinary direct and indirect mesh commands, but
currently returns false when DrawArgs.count_addr is non-zero. Supporting that
case correctly requires a GPU-side multi-draw/indirect-count execution path;
a CPU readback would add a queue wait and is deliberately not used here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class MeshFallbackStatus:
    source_file_found: bool
    fallback_function_found: bool
    count_buffer_rejected: bool
    gpu_indirect_path_present: bool
    verdict: str
    detail: str


def inspect_source(hookshot_root: str | Path) -> MeshFallbackStatus:
    source = Path(hookshot_root) / "gpu" / "vk" / "vk_draw.cpp"
    if not source.is_file():
        return MeshFallbackStatus(False, False, False, False, "unknown", f"Missing {source}")
    text = source.read_text(encoding="utf-8", errors="replace")
    marker = "bool fallback_record(VkCommandBuffer cmd, Program& p, const DrawArgs& d)"
    start = text.find(marker)
    if start < 0:
        return MeshFallbackStatus(True, False, False, False, "unknown", "fallback_record() not found; upstream source layout changed")
    brace = text.find("{", start)
    depth, end = 1, brace + 1
    while depth and end < len(text):
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    body = text[brace:end]
    rejected = bool(re.search(r"if\s*\(\s*d\.count_addr\s*\).*?return\s+false\s*;", body, re.S))
    indirect = "vkCmdDispatchIndirect" in body and "mesh_conv_buf" in body
    if rejected:
        verdict = "count-buffer mesh draws unsupported"
        detail = (
            "fallback_record() rejects d.count_addr. The regular mesh path can issue Vulkan indirect-count draws, "
            "but the compute fallback currently cannot reproduce that GPU-side multi-draw sequence."
        )
    elif "d.count_addr" in body and indirect:
        verdict = "count-buffer path changed; needs runtime validation"
        detail = "The source references count_addr and the indirect dispatch path. This source check cannot prove correctness."
    else:
        verdict = "unknown / source moved"
        detail = "The known count-buffer rejection pattern was not found; inspect the current fallback implementation."
    return MeshFallbackStatus(True, True, rejected, indirect, verdict, detail)


def analyze_log(text: str) -> dict[str, int | bool]:
    return {
        "fallback_enabled": "no mesh shaders: task and mesh programs run as compute shaders" in text.lower(),
        "count_buffer_skip_messages": len(re.findall(r"vk: fallback: .*?(?:count buffer|count-buffer).*?(?:left out|skipped)", text, re.I)),
        "indirect_mesh_reports": len(re.findall(r"vk: mesh indirect prog", text, re.I)),
    }
