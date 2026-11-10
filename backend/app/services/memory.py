"""How much memory the container still has, so a model that will not fit is refused.

On 2026-11-10 the embedding model was switched on in a 512 MB container that
could not hold it next to the three speech voices, and Render killed the
process (``oomKilled``) three times in three minutes: a crash loop, which took
the whole site down, where the right outcome was to lose embeddings and say so.
Before loading a model the server now asks what is left.

Only memory the kernel cannot take back counts -- anonymous memory: the heap.
Pages of a mapped model file (scripts/map_weights.py) are reclaimed under
pressure and do not count against the limit in practice.

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
