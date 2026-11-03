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
    reach: tuple[tuple[int, int], tuple[int, int]] | None = None


def locate(declared: Pointer, place: Callable[[str], tuple[int, int]]) -> tuple[
        tuple[int, int], tuple[int, int]]:
    """Both refs resolved, before anything is sent."""
    return place(declared.x), place(declared.y)


def program_at(read: Callable[[int, int, int], bytes], declared: Pointer,
               places: tuple[tuple[int, int], tuple[int, int]]) -> tuple[int, int]:
    """The program's pointer in its own units, a signed little-endian word."""
    def axis(at: tuple[int, int]) -> int:
        return int.from_bytes(read(at[0], at[1], declared.bytes), "little", signed=True)
    return axis(places[0]), axis(places[1])


def shown(steered: Steered) -> dict[str, object]:
    """The reply's `pointer.program`; `reach` is the span at the driver's corners if it missed."""
    reply: dict[str, object] = {"x": steered.seen[0], "y": steered.seen[1],
                                "corrections": steered.corrections}
    if steered.reach is not None and not steered.arrived:
        (x0, y0), (x1, y1) = steered.reach
        reply["reach"] = {"x": sorted((x0, x1)), "y": sorted((y0, y1))}
    return reply


def arrived(steered: Steered | None, driver_landed: bool, drag: bool) -> bool:
    """A steered move arrives where the program's pointer is; a drag also where its end landed."""
    if steered is None:
        return driver_landed
    return steered.arrived and (driver_landed or not drag)


def unsteered(parked: bool, moved: bool, units: str, sized: bool) -> str | None:
    """Why a map's declared pointer was not read for this move, or None when it was."""
    if not moved:
        return None
    if not parked:
        return "the guest runs, and a running guest's memory cannot be read"
    if units != "screen":
        return "units='mouse' aims at the driver, not the program"
    return None if sized else "the mode's size is unknown, so there is no ratio to nudge by"


def steer(aim: tuple[int, int], seen_now: Callable[[], tuple[int, int]],
          nudge: Callable[[int, int], None], ratio: tuple[float, float],
          resync: Callable[[], tuple[tuple[int, int], tuple[int, int]]] | None = None,
          widen: Callable[[tuple[tuple[int, int], tuple[int, int]]], tuple[float, float] | None]
          | None = None) -> Steered:
    """Nudge the driver by the gap to `aim` until the pointer is on it or stops moving; `ratio` is
    driver units a program unit. A driver at its edge loses the motion its program never sees, so
    when the nudges fail `resync` (a sweep to both edges, where each clamps; it returns the
    program's pointer at each) runs once and the steering starts again. An aim outside the span
    that sweep found is past the driver's range: `widen` (given the span) widens the range and
    returns the new ratio, or None when it left the range alone, and the sweep is made again."""
    steered, ratio = _chase(aim, seen_now, nudge, ratio)
    if steered.arrived or resync is None:
        return steered
    reach = resync()
    if widen is not None and not _inside(aim, reach):
        widened = widen(reach)
        if widened is not None:
            ratio = widened
            reach = resync()
    again, _ = _chase(aim, seen_now, nudge, ratio)
    return Steered(again.seen, again.arrived, steered.corrections + again.corrections, reach)


def _inside(aim: tuple[int, int], reach: tuple[tuple[int, int], tuple[int, int]]) -> bool:
    (x0, y0), (x1, y1) = reach
    return min(x0, x1) <= aim[0] <= max(x0, x1) and min(y0, y1) <= aim[1] <= max(y0, y1)


def _chase(aim: tuple[int, int], seen_now: Callable[[], tuple[int, int]],
           nudge: Callable[[int, int], None], ratio: tuple[float, float]
           ) -> tuple[Steered, tuple[float, float]]:
    seen = seen_now()
    corrections = 0
    rx, ry = ratio
    while seen != aim and corrections < CORRECTIONS:
        dx, dy = _nudge(aim[0] - seen[0], rx), _nudge(aim[1] - seen[1], ry)
        nudge(dx, dy)
        corrections += 1
        moved = seen_now()
        if moved == seen:
            break
        rx = _learnt(rx, dx, moved[0] - seen[0])
        ry = _learnt(ry, dy, moved[1] - seen[1])
        seen = moved
    return Steered(seen, seen == aim, corrections), (rx, ry)


def _nudge(gap: int, ratio: float) -> int:
    """`gap` in driver units, at least one when there is a gap."""
    return round(gap * ratio) or (gap > 0) - (gap < 0)


def _learnt(ratio: float, nudged: int, moved: int) -> float:
    return abs(nudged / moved) if nudged and moved else ratio
