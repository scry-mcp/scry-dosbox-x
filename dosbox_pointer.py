"""A program's own pointer, read where its map says, and the driver steered onto the aim."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from scry_core.screen_map import Pointer

#: A pointer a clamp holds is not chased for ever.
CORRECTIONS = 4


@dataclass(frozen=True)
class Steered:
    """Where the program's pointer ended and the nudges it took."""

    seen: tuple[int, int]
    arrived: bool
    corrections: int


def program_at(read: Callable[[int, int, int], bytes], declared: Pointer,
               place: Callable[[str], tuple[int, int]]) -> tuple[int, int]:
    """The program's pointer in its own units, little-endian."""
    def axis(ref: str) -> int:
        seg, off = place(ref)
        return int.from_bytes(read(seg, off, declared.bytes), "little")
    return axis(declared.x), axis(declared.y)


def steer(aim: tuple[int, int], seen_now: Callable[[], tuple[int, int]],
          nudge: Callable[[int, int], None], ratio: tuple[float, float]) -> Steered:
    """Nudge the driver by the gap to `aim` until the pointer is on it or stops moving; `ratio` is
    driver units a program unit."""
    seen = seen_now()
    corrections = 0
    rx, ry = ratio
    while seen != aim and corrections < CORRECTIONS:
        dx, dy = round((aim[0] - seen[0]) * rx), round((aim[1] - seen[1]) * ry)
        nudge(dx, dy)
        corrections += 1
        moved = seen_now()
        if moved == seen:
            break
        rx = _learnt(rx, dx, moved[0] - seen[0])
        ry = _learnt(ry, dy, moved[1] - seen[1])
        seen = moved
    return Steered(seen, seen == aim, corrections)


def _learnt(ratio: float, nudged: int, moved: int) -> float:
    return abs(nudged / moved) if nudged and moved else ratio
