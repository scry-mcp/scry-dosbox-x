"""A program's own pointer: read back where the map says it lives, and steer the driver until it
is where it was asked to be, however far a clamp let the two drift."""

from __future__ import annotations

import pytest
from scry_core.screen_map import Pointer

from scry_dosbox_x import pointer


class Program:
    """A program that integrates the driver's motion at `ratio` driver units a program unit,
    holding its pointer to `0..limit`, after starting `drift` away from the driver's."""

    def __init__(self, drift: tuple[int, int] = (3, -2), ratio: float = 2.0,
                 limit: tuple[int, int] = (319, 199)) -> None:
        self.at, self.ratio, self.limit = drift, ratio, limit
        self.nudges: list[tuple[int, int]] = []

    def seen(self) -> tuple[int, int]:
        return self.at

    def nudge(self, dx: int, dy: int) -> None:
        self.nudges.append((dx, dy))
        self.at = (min(max(self.at[0] + round(dx / self.ratio), 0), self.limit[0]),
                   min(max(self.at[1] + round(dy / self.ratio), 0), self.limit[1]))


def test_a_pointer_that_drifted_is_steered_onto_the_target() -> None:
    program = Program()
    got = pointer.steer((100, 50), program.seen, program.nudge, (2.0, 2.0))
    assert got.arrived and got.seen == (100, 50), got
    assert got.corrections == len(program.nudges) >= 1


def test_a_pointer_already_there_is_not_nudged() -> None:
    program = Program(drift=(100, 50))
    got = pointer.steer((100, 50), program.seen, program.nudge, (2.0, 2.0))
    assert got.arrived and got.corrections == 0 and program.nudges == []


def test_a_pointer_a_clamp_holds_is_given_up_on_and_said() -> None:
    program = Program(drift=(0, 0), limit=(0, 0))
    got = pointer.steer((100, 50), program.seen, program.nudge, (2.0, 2.0))
    assert not got.arrived and got.seen == (0, 0), got
    assert got.corrections <= pointer.CORRECTIONS


def test_a_ratio_that_was_guessed_wrong_is_learnt_from_the_first_nudge() -> None:
    program = Program(ratio=1.0, drift=(40, -30))
    got = pointer.steer((100, 50), program.seen, program.nudge, (2.0, 2.0))
    assert got.arrived, got


class Clamped:
    """A driver holding an absolute place in `0..max` and a program that integrates each move's
    motion at `ratio` driver units a program unit into a pointer of its own, held to `0..limit`:
    a driver at its edge loses the motion the program never sees, which is how the two drift."""

    def __init__(self, driver: int, program: int, ratio: float = 2.0, limit: int = 319) -> None:
        self.driver, self.program, self.ratio, self.limit = driver, program, ratio, limit
        self.max = int(limit * ratio) + 1

    def move(self, to: int) -> None:
        to = min(max(to, 0), self.max)
        moved = self.program + round((to - self.driver) / self.ratio)
        self.program = min(max(moved, 0), self.limit)
        self.driver = to

    def seen(self) -> tuple[int, int]:
        return self.program, 0

    def nudge(self, dx: int, _dy: int) -> None:
        self.move(self.driver + dx)

    def resync(self) -> tuple[tuple[int, int], tuple[int, int]]:
        self.move(0)
        low = self.seen()
        self.move(self.max)
        return low, self.seen()


def test_a_pointer_lagging_a_driver_at_its_edge_is_resynced_by_a_sweep_and_steered() -> None:
    """The driver is at its right edge, 55 units behind: no nudge can reach the aim."""
    world = Clamped(driver=639, program=264)
    got = pointer.steer((271, 0), world.seen, world.nudge, (2.0, 2.0), world.resync)
    assert got.arrived and got.seen == (271, 0), got


def test_a_pointer_the_sweep_cannot_help_is_still_given_up_on() -> None:
    world = Clamped(driver=0, program=0, limit=0)
    got = pointer.steer((100, 0), world.seen, world.nudge, (2.0, 2.0), world.resync)
    assert not got.arrived and got.corrections <= 2 * pointer.CORRECTIONS + 1, got


def test_an_aim_outside_the_window_the_driver_maps_to_is_given_up_on_with_that_window() -> None:
    """A program whose pointer stops at 219 cannot be aimed at 300: the sweep's two corners are
    the span the reply names, instead of only missing."""
    world = Clamped(driver=0, program=100, ratio=1.0, limit=219)
    got = pointer.steer((300, 0), world.seen, world.nudge, (1.0, 1.0), world.resync)
    assert not got.arrived and got.reach is not None, got
    assert pointer.shown(got)["reach"] == {"x": [0, 219], "y": [0, 0]}, pointer.shown(got)


class Narrow:
    """A program whose pointer starts at `base` for a driver at 0 and follows it at `ratio` driver
    units a program unit, over a driver range that stops at `max`; widening the range is the only
    way past it."""

    def __init__(self, base: int = 352, ratio: float = 2.0, max_: int = 639) -> None:
        self.base, self.ratio, self.max, self.driver = base, ratio, max_, 320
        self.widened: list[int] = []

    def seen(self) -> tuple[int, int]:
        return self.base + round(self.driver / self.ratio), 0

    def nudge(self, dx: int, _dy: int) -> None:
        self.driver = min(max(self.driver + dx, 0), self.max)

    def resync(self) -> tuple[tuple[int, int], tuple[int, int]]:
        self.driver = 0
        low = self.seen()
        self.driver = self.max
        return low, self.seen()

    def widen(self, reach: tuple[tuple[int, int], tuple[int, int]]) -> tuple[float, float]:
        self.widened.append(reach[1][0] - reach[0][0])
        self.max = 2047
        return (self.ratio, self.ratio)


def test_an_aim_past_the_drivers_range_widens_it_and_is_steered_there() -> None:
    world = Narrow()
    got = pointer.steer((900, 0), world.seen, world.nudge, (2.0, 2.0), world.resync, world.widen)
    assert got.arrived and got.seen == (900, 0), got
    assert world.widened == [320], "the sweep's span reached the widening"


def test_an_aim_the_range_already_covers_widens_nothing() -> None:
    world = Narrow()
    got = pointer.steer((600, 0), world.seen, world.nudge, (2.0, 2.0), world.resync, world.widen)
    assert got.arrived and world.widened == [], (got, world.widened)


def test_a_widening_that_lets_the_program_fall_short_is_still_said_with_its_reach() -> None:
    world = Narrow()
    world.widen = lambda reach: (2.0, 2.0)               # type: ignore[method-assign]
    got = pointer.steer((900, 0), world.seen, world.nudge, (2.0, 2.0), world.resync, world.widen)
    assert not got.arrived and got.reach is not None, got


def test_a_pointer_that_arrived_carries_no_reach() -> None:
    steered = pointer.Steered((5, 6), True, 2, ((0, 0), (9, 9)))
    assert pointer.shown(steered) == {"x": 5, "y": 6, "corrections": 2}


def _place(ref: str) -> tuple[int, int]:
    seg, off = ref.split(":")
    return int(seg, 16), int(off, 16)


def test_the_declared_pointer_is_read_little_endian_from_its_refs() -> None:
    read = {(0x1000, 0x10): bytes([0x34, 0x01]), (0x1000, 0x12): bytes([0x07, 0x00])}
    declared = Pointer("1000:0010", "1000:0012", 2)
    places = pointer.locate(declared, _place)
    got = pointer.program_at(lambda seg, off, n: read[(seg, off)][:n], declared, places)
    assert got == (0x134, 7)


def test_a_pointer_held_as_a_signed_word_that_went_negative_reads_negative() -> None:
    declared = Pointer("1000:0010", "1000:0012", 2)
    read = {(0x1000, 0x10): bytes([0xFE, 0xFF]), (0x1000, 0x12): bytes([0x05, 0x00])}
    got = pointer.program_at(lambda seg, off, n: read[(seg, off)][:n], declared,
                             pointer.locate(declared, _place))
    assert got == (-2, 5)


def test_the_refs_are_resolved_before_anything_moves() -> None:
    def unknown(ref: str) -> tuple[int, int]:
        raise ValueError(f"no symbol {ref}")
    with pytest.raises(ValueError, match="no symbol nosuch"):
        pointer.locate(Pointer("nosuch", "nosuch"), unknown)


def test_a_gap_of_one_unit_is_nudged_at_least_one_driver_unit() -> None:
    program = Program(drift=(4, 4), ratio=1.0)
    got = pointer.steer((5, 5), program.seen, program.nudge, (0.4, 0.4))
    assert got.arrived and program.nudges[0] == (1, 1), (got, program.nudges)


@pytest.mark.parametrize(("steered", "driver", "drag", "want"), [
    (None, True, False, True), (None, False, False, False),
    (pointer.Steered((1, 1), True, 1), False, False, True),
    (pointer.Steered((1, 1), False, 4), True, False, False),
    (pointer.Steered((1, 1), True, 1), True, True, True),
    (pointer.Steered((1, 1), False, 4), True, True, False),
    (pointer.Steered((1, 1), True, 1), False, True, False),
])
def test_a_drag_arrives_only_where_its_start_was_steered_and_its_end_landed(
        steered: pointer.Steered | None, driver: bool, drag: bool, want: bool) -> None:
    assert pointer.arrived(steered, driver, drag) is want


@pytest.mark.parametrize(("parked", "moved", "units", "sized", "why"), [
    (True, True, "screen", True, None),
    (False, True, "screen", True, "guest runs"),
    (True, True, "mouse", True, "units"),
    (True, True, "screen", False, "size"),
    (True, False, "screen", True, None),
])
def test_a_declared_pointer_that_is_not_read_says_why(
        parked: bool, moved: bool, units: str, sized: bool, why: str | None) -> None:
    said = pointer.unsteered(parked, moved, units, sized)
    assert (said is None) if why is None else (said is not None and why in said), said
