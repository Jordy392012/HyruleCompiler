"""Parse Hookshot Vulkan/runtime logs into CPU/GPU sync and memory-traffic evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import re
from typing import Iterable

_FLOAT = r"([0-9]+(?:\.[0-9]+)?)"
_BATCH = re.compile(
    r"vk: batched submits: (?P<flushes>\d+) flushes, (?P<cbs>" + _FLOAT +
    r") command buffers each, over 120 presents; by reason: poll (?P<poll>\d+), "
    r"wait (?P<wait>\d+), slot (?P<slot>\d+), present (?P<present>\d+), "
    r"cap (?P<cap>\d+), value (?P<value>\d+), other (?P<other>\d+)"
)
_STATUS = re.compile(r"vk: status: (?P<frames>\d+) frames, the slowest (?P<slowest>" + _FLOAT + r") ms; (?P<rest>.*)")
_MIRROR = re.compile(
    r"vk: mirror syncs \(600 submits\): (?P<capture>-?\d+) dirty pages from their submits' captures, "
    r"(?P<old>-?\d+) from earlier ones', (?P<live>-?\d+) from guest memory .*?; "
    r"(?P<gpu>-?\d+) pages the GPU wrote copied over \((?P<gpu_live>-?\d+) live\)"
)
_WB = re.compile(
    r"vk: write-back diff \(600 submits\): (?P<runs>\d+) runs, (?P<mb>" + _FLOAT +
    r") MB compared; (?P<pages>\d+) pages read into the shadows; (?P<shadow_mb>" + _FLOAT +
    r") MB of shadows; pages the shadows knew that the CPU wrote: (?P<game>\d+) in captures, "
    r"(?P<collected>\d+) only in the collection, (?P<replay>\d+) only by the replay itself"
)
_MESH_SKIP = re.compile(r"vk: fallback: .*?(?:count buffer|count-buffer).*?(?:left out|skipped)", re.I)


@dataclass
class Profile:
    source: str
    batched_submit_state: str | None = None
    batch_reports: list[dict[str, int | float]] = field(default_factory=list)
    status_reports: list[dict[str, float | int | str]] = field(default_factory=list)
    fine_frame_ms: list[dict[str, float]] = field(default_factory=list)
    mirror_reports: list[dict[str, int]] = field(default_factory=list)
    writeback_reports: list[dict[str, int | float]] = field(default_factory=list)
    mesh_count_buffer_skips_logged: int = 0
    mesh_fallback_enabled: bool | None = None
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        batch = self.batch_reports
        mirror = self.mirror_reports
        wb = self.writeback_reports
        slow = [float(x["slowest_ms"]) for x in self.status_reports]

        def avg(items, key):
            vals = [float(x[key]) for x in items if key in x]
            return sum(vals) / len(vals) if vals else None

        return {
            "source": self.source,
            "batched_submit_state": self.batched_submit_state,
            "batch_reports": len(batch),
            "avg_flushes_per_120_presents": avg(batch, "flushes"),
            "avg_command_buffers_per_flush": avg(batch, "command_buffers_per_flush"),
            "avg_poll_flushes_per_120_presents": avg(batch, "poll"),
            "avg_slowest_frame_ms_reported": sum(slow) / len(slow) if slow else None,
            "fine_frame_ms_last": self.fine_frame_ms[-1] if self.fine_frame_ms else None,
            "mirror_reports": len(mirror),
            "avg_capture_dirty_pages_per_600_submits": avg(mirror, "capture"),
            "avg_old_dirty_pages_per_600_submits": avg(mirror, "old"),
            "avg_live_dirty_pages_per_600_submits": avg(mirror, "live"),
            "writeback_reports": len(wb),
            "avg_writeback_mb_compared_per_600_submits": avg(wb, "mb_compared"),
            "mesh_count_buffer_skip_messages": self.mesh_count_buffer_skips_logged,
            "mesh_fallback_enabled": self.mesh_fallback_enabled,
            "warnings": list(self.warnings),
        }


def parse_log_text(text: str, source: str = "<memory>") -> Profile:
    result = Profile(source=source)
    for line in text.splitlines():
        low = line.lower()
        if "vk: batched submits on" in low:
            result.batched_submit_state = "on"
        elif "vk: batched submits off" in low:
            result.batched_submit_state = "off"
        elif "no mesh shaders: task and mesh programs run as compute shaders" in low:
            result.mesh_fallback_enabled = True
        elif "mesh shader" in low and "not supported" in low:
            result.mesh_fallback_enabled = False

        m = _BATCH.search(line)
        if m:
            row: dict[str, int | float] = {k: int(v) for k, v in m.groupdict().items() if k != "cbs"}
            row["command_buffers_per_flush"] = float(m.group("cbs"))
            result.batch_reports.append(row)

        m = _STATUS.search(line)
        if m:
            result.status_reports.append({
                "frames": int(m.group("frames")),
                "slowest_ms": float(m.group("slowest")),
                "details": m.group("rest"),
            })

        if "vk: a frame (fine): ms:" in low:
            payload = line.split("ms:", 1)[1]
            values: dict[str, float] = {}
            for item in payload.split(","):
                pair = re.match(r"\s*([A-Za-z0-9_+./ -]+?)\s+(" + _FLOAT + r")\s*$", item)
                if pair:
                    values[pair.group(1).strip()] = float(pair.group(2))
            if values:
                result.fine_frame_ms.append(values)

        m = _MIRROR.search(line)
        if m:
            result.mirror_reports.append({k: int(v) for k, v in m.groupdict().items()})

        m = _WB.search(line)
        if m:
            g = m.groupdict()
            result.writeback_reports.append({
                "runs": int(g["runs"]), "mb_compared": float(g["mb"]),
                "pages_read": int(g["pages"]), "shadow_mb": float(g["shadow_mb"]),
                "cpu_write_pages_in_captures": int(g["game"]),
                "cpu_write_pages_only_in_collection": int(g["collected"]),
                "cpu_write_pages_only_in_replay": int(g["replay"]),
            })

        if _MESH_SKIP.search(line):
            result.mesh_count_buffer_skips_logged += 1

    if not result.batch_reports:
        result.warnings.append("No batched-submit summary found; enable/use RX_VK_BATCH and collect at least 120 presents.")
    if not result.mirror_reports and not result.writeback_reports:
        result.warnings.append("No mirror/write-back counters found; collect a longer run (the mirror counters report every 600 submits).")
    if result.mesh_count_buffer_skips_logged:
        result.warnings.append("This Hookshot build logged mesh fallback count-buffer draws being omitted; the GPU-side multi-draw path is not implemented by this overlay.")
    return result


def parse_log(path: str | Path) -> Profile:
    p = Path(path)
    return parse_log_text(p.read_text(encoding="utf-8", errors="replace"), str(p))


def compare_profiles(paths: Iterable[str | Path]) -> list[dict]:
    profiles = [parse_log(p) for p in paths]
    rows = [p.summary() for p in profiles]
    if rows and all(r["avg_slowest_frame_ms_reported"] is not None for r in rows):
        rows.sort(key=lambda r: float(r["avg_slowest_frame_ms_reported"]))
    return rows


def write_json(profiles: Iterable[Profile], destination: str | Path) -> None:
    payload = [p.summary() for p in profiles]
    Path(destination).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
