"""How much memory the container still has, so a model that will not fit is refused.

On 2026-11-10 the embedding model was switched on in a 512 MB container that
could not hold it next to the three speech voices, and Render killed the
process (``oomKilled``) three times in three minutes: a crash loop, which took
the whole site down, where the right outcome was to lose embeddings and say so.
Before loading a model the server now asks what is left.

Only the heap is counted here (anonymous memory), which is a floor, not the
whole story: Render's graph also counts the pages of a mapped model file once
the model has touched them, and on 2026-11-10 killed the server at 529 MB of
that graph with only 324 MB of it heap. So ``working_set_bytes`` is also read,
and ``/health`` reports both, but the guard below uses the heap only: a figure
that is known to be unreadable somewhere should not be able to refuse a model
on a guess.

Reads the container's cgroup (v2, then v1). Anywhere that is unreadable -- a
laptop, a CI runner, a platform without one -- the answer is "unknown", and
callers must carry on as if there were room.
"""

from __future__ import annotations

from pathlib import Path

MB = 1024 * 1024
CGROUP_V2 = Path("/sys/fs/cgroup")
CGROUP_V1 = Path("/sys/fs/cgroup/memory")

# v1 reports "no limit" as a number near 2**63.
_UNLIMITED = 1 << 50


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _stat(path: Path, *keys: str) -> int | None:
    text = _text(path)
    if text is None:
        return None
    found = {}
    for line in text.splitlines():
        name, _, value = line.partition(" ")
        if name in keys and value.strip().isdigit():
            found[name] = int(value)
    for key in keys:
        if key in found:
            return found[key]
    return None


def limit_bytes() -> int | None:
    """The container's memory limit, or None if there is none or it is unknown."""
    for path in (CGROUP_V2 / "memory.max", CGROUP_V1 / "memory.limit_in_bytes"):
        text = _text(path)
        if text and text.isdigit() and int(text) < _UNLIMITED:
            return int(text)
    return None


def anon_bytes() -> int | None:
    """Memory in use that cannot be given back: the heap of every process."""
    found = _stat(CGROUP_V2 / "memory.stat", "anon")
    if found is None:
        found = _stat(CGROUP_V1 / "memory.stat", "total_rss", "rss")
    return found


def headroom_mb() -> float | None:
    """What the heap may still grow by before the limit, or None if unknown."""
    limit, used = limit_bytes(), anon_bytes()
    if limit is None or used is None:
        return None
    return (limit - used) / MB


def working_set_bytes() -> int | None:
    """What the container is really holding on to: heap plus the file pages in
    active use (a mapped model's weights), without the cache the kernel is
    free to drop. The figure a platform's memory graph is likely to show."""
    usage = _stat(CGROUP_V2 / "memory.stat", "anon")  # probe: is this v2?
    if usage is not None:
        current = _text(CGROUP_V2 / "memory.current")
        inactive = _stat(CGROUP_V2 / "memory.stat", "inactive_file") or 0
        if current and current.isdigit():
            return max(0, int(current) - inactive)
        return None
    current = _text(CGROUP_V1 / "memory.usage_in_bytes")
    inactive = _stat(CGROUP_V1 / "memory.stat", "total_inactive_file") or 0
    if current and current.isdigit():
        return max(0, int(current) - inactive)
    return None


def snapshot() -> dict[str, float | None]:
    """For /health: the limit, the heap and the working set, in MB (None if unknown)."""

    def mb(value: int | None) -> float | None:
        return None if value is None else round(value / MB, 1)

    return {
        "limit_mb": mb(limit_bytes()),
        "heap_mb": mb(anon_bytes()),
        "working_set_mb": mb(working_set_bytes()),
    }
