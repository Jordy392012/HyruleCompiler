"""Profile-scoped loop-poll decimation for Hookshot's generated C.

The upstream poll pass inserts A64_POLL(c) at every backward goto. This
module preserves that exact behaviour at interval=1. For larger intervals,
it emits a function-local countdown so the generated code only reads the
interrupt flag every N taken loop back-edges.

This is deliberately opt-in: it trades scheduler responsiveness for fewer
poll checks. Only profile-hot functions are changed by the integration layer
unless A64_POLL_HOT_ONLY=0 is explicitly requested.
"""
from __future__ import annotations

import re
from typing import Final

LABEL: Final[re.Pattern[str]] = re.compile(r"^L_([0-9a-f]{8}):;", re.M)
GOTO: Final[re.Pattern[str]] = re.compile(r"goto L_([0-9a-f]{8});")
ALLOWED_INTERVALS: Final[frozenset[int]] = frozenset({1, 2, 4, 8, 16})


def validate_interval(interval: int) -> int:
    """Validate supported intervals; keeping this finite bounds yield delay."""
    if isinstance(interval, bool) or not isinstance(interval, int):
        raise TypeError("poll interval must be an integer")
    if interval not in ALLOWED_INTERVALS:
        allowed = ", ".join(str(v) for v in sorted(ALLOWED_INTERVALS))
        raise ValueError(f"poll interval must be one of: {allowed}")
    return interval


def add_polls(text: str, interval: int = 1) -> tuple[str, int]:
    """Insert polling before every backward goto.

    interval=1 is byte-for-byte equivalent to Hookshot's current pass.
    interval>1 adds one local countdown per function and performs A64_POLL
    once every N backward edges across all loops in that function.

    Returns (rewritten_text, number_of_backward_edges_instrumented).
    """
    interval = validate_interval(interval)
    labels = {m.group(1): m.end() for m in LABEL.finditer(text)}
    matches: list[re.Match[str]] = []
    for match in GOTO.finditer(text):
        label_at = labels.get(match.group(1))
        if label_at is not None and label_at < match.start():
            matches.append(match)

    if not matches:
        return text, 0

    out: list[str] = []
    last = 0
    if interval == 1:
        for match in matches:
            out.append(text[last:match.start()])
            out.append("{ A64_POLL(c); " + match.group(0) + " }")
            last = match.end()
        out.append(text[last:])
        return "".join(out), len(matches)

    open_brace = text.find("{")
    if open_brace < 0:
        raise ValueError("lifted function has no opening brace")

    budget_name = "hyrule_poll_budget"
    suffix = 0
    while re.search(r"\b" + re.escape(budget_name) + r"\b", text):
        suffix += 1
        budget_name = f"hyrule_poll_budget_{suffix}"

    for match in matches:
        out.append(text[last:match.start()])
        out.append(
            "{ if (__builtin_expect(--" + budget_name + " == 0u, 0)) { "
            f"{budget_name} = {interval}u; A64_POLL(c); "
            "} " + match.group(0) + " }"
        )
        last = match.end()
    out.append(text[last:])
    rewritten = "".join(out)
    rewritten = (
        rewritten[: open_brace + 1]
        + f"\n    unsigned int {budget_name} = {interval}u;\n"
        + rewritten[open_brace + 1 :]
    )
    return rewritten, len(matches)
