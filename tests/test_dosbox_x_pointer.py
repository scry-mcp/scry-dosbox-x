"""A program's own pointer: read back where the map says it lives, and steer the driver until it
is where it was asked to be, however far a clamp let the two drift."""

from __future__ import annotations

from scry_core.screen_map import Pointer

import dosbox_pointer as pointer


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


def test_the_declared_pointer_is_read_little_endian_from_its_refs() -> None:
    read = {(0x1000, 0x10): bytes([0x34, 0x01]), (0x1000, 0x12): bytes([0x07, 0x00])}
    def place(ref: str) -> tuple[int, int]:
        seg, off = ref.split(":")
        return int(seg, 16), int(off, 16)
    got = pointer.program_at(lambda seg, off, n: read[(seg, off)][:n],
                             Pointer("1000:0010", "1000:0012", 2), place)
    assert got == (0x134, 7)
