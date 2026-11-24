"""The input route's own arithmetic and its failure halves, against lines a real stub wrote
(`STUB  . mouse ...` captured off a live run) and against the session double of the server's
tests: the report's parse, the screen units, the bounds on both axes, a reaction the stub's own
line cannot fake, and what a call says when its commands went in and the read-back did not."""

from __future__ import annotations

import contextlib
import dataclasses
import socket
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from channel_double import SilentChannel
from dosbox_x_server_support import _guest, _names
from scry_core import judges, presence
from scry_core.reply_contract import unavailable
from scry_core.screen_map import Pointer

from scry_dosbox_x import control, inputs, running, server, stub_link
from scry_dosbox_x import launch as dlaunch
from scry_dosbox_x import pointer as dpointer
from scry_dosbox_x import session as ds
from scry_dosbox_x import state as dstate
from scry_dosbox_x.mcp import RECORDER

#: Authored in the format the stub's source prints:
#: text mode 3, then mode 13h with the left button held.
AUTHORED_TEXT = ("STUB  . mouse x=16 y=8 buttons=0 max=639,199 mode=3 screen=720x400 "
             "vbe=3 attr=0 res=0x0")
AUTHORED_13H = ("STUB  . mouse x=200 y=50 buttons=1 max=639,199 mode=19 screen=320x400 "
            "vbe=19 attr=0 res=0x0")
#: Captured off the stub on the mouse guest, VBE 103h and 108h.
REAL_VBE_103H = ("STUB  . mouse x=400 y=300 buttons=0 max=799,599 mode=107 screen=800x600 "
                 "vbe=259 attr=155 res=800x600")
REAL_VBE_108H = ("STUB  . mouse x=320 y=240 buttons=0 max=639,479 mode=112 screen=640x480 "
                 "vbe=264 attr=15 res=80x60")


def test_a_real_report_parses_into_its_fields() -> None:
    text, held = inputs.parse_report(AUTHORED_TEXT), inputs.parse_report(AUTHORED_13H)
    assert (text.x, text.y, text.buttons, text.max_x, text.max_y, text.mode) == (
        16, 8, 0, 639, 199, 3)
    assert text.drawn == (720, 400) and held.drawn == (320, 400)
    assert held.buttons == 1 and held.mode == 0x13 and held.units() == (320, 200)


@pytest.mark.parametrize(("unit", "size", "top", "driver"), [
    (0, 320, 639, 1), (1, 320, 639, 3), (319, 320, 639, 639),
    (0, 200, 199, 0), (199, 200, 199, 199),
    (79, 80, 639, 636), (24, 25, 199, 196), (49, 50, 399, 396)])
def test_a_screen_unit_maps_onto_the_driver_and_back(unit: int, size: int, top: int,
                                                    driver: int) -> None:
    assert inputs.to_driver(unit, size, top) == driver
    assert inputs.to_screen(driver, size, top) == unit


@pytest.mark.parametrize(("size", "top", "snap"), [(320, 2552, 0xFFFE), (200, 1592, 0xFFFF)])
def test_a_program_s_own_range_lands_on_the_pixel_asked(size: int, top: int, snap: int) -> None:
    """Deluxe Paint sets 0..2552 x 0..1592, eight units a pixel that it divides back out, and
    the driver keeps x even in mode 13h, so the aim has to sit inside the span, past its first
    coordinate."""
    for unit in range(size):
        landed = inputs.to_driver(unit, size, top) & snap
        assert (landed // 8, inputs.to_screen(landed, size, top)) == (unit, unit), unit


@pytest.mark.parametrize(("size", "top"), [(320, 351), (320, 399), (320, 479), (200, 1592),
                                          (80, 639), (350, 399)])
def test_every_unit_maps_back_to_itself_on_a_range_at_least_as_fine(size: int, top: int) -> None:
    """A range that does not divide the screen evenly still has a coordinate inside every unit;
    the aim has to land in it, not in the unit before."""
    assert [u for u in range(size)
            if inputs.to_screen(inputs.to_driver(u, size, top), size, top) != u] == []


def test_no_screen_unit_maps_past_the_driver_s_top() -> None:
    """A range the program set needs not divide the screen evenly; the last unit still lands at
    or below the driver's top, never past it."""
    for size, top in ((350, 199), (320, 255), (640, 479), (25, 199)):
        assert max(inputs.to_driver(u, size, top) for u in range(size)) <= top, (size, top)


@pytest.mark.parametrize(("line", "units", "kind"), [
    (REAL_VBE_103H, (800, 600), "pixel"),
    (REAL_VBE_108H, (80, 60), "text")])
def test_a_vbe_mode_s_units_are_its_own_resolution(line: str, units: tuple[int, int],
                                                   kind: str) -> None:
    """The BIOS mode byte under a VBE mode is the emulated card's own number, which no table
    maps; the units are the resolution VBE itself reports for the mode, in pixels or cells."""
    report = inputs.parse_report(line)
    assert (report.units(), report.kind()) == (units, kind)


def test_a_report_cut_short_is_never_read_for_the_whole_one_after_it() -> None:
    """A report whose line lost its end runs into the next acknowledgement and report; the cut
    number must not parse, so the whole report after it is the one read."""
    cut = REAL_VBE_103H.rsplit("600", 1)[0] + "6"
    joined = cut + "Z\x01R\x01" + REAL_VBE_103H
    assert inputs.parse_report(joined).resolution == (800, 600)


def test_a_vbe_mode_whose_size_vbe_did_not_say_maps_no_units() -> None:
    """4F01h failing leaves `res=0x0`; the BIOS byte is then the card's own number, which a
    table of BIOS modes could misread, so the screen's units are unknown."""
    report = inputs.parse_report(AUTHORED_TEXT.replace("vbe=3 attr=0", "vbe=259 attr=0"))
    assert report.units() is None


@pytest.mark.parametrize(("screen", "max_", "span", "wanted"), [
    (1024, 639, 319, 2050),     # ReChip!'s x: 320 program units over 640 driver ones
    (768, 199, 199, 767),       # its y: one for one
    (1024, 639, 0, 639),        # a sweep that measured nothing leaves the range alone
    (2**20, 639, 1, inputs.MAX_COORD),
])
def test_the_range_that_spans_a_screen_comes_from_what_a_sweep_measured(
        screen: int, max_: int, span: int, wanted: int) -> None:
    assert inputs._range_for(screen, max_, span) == wanted


class _World:
    """The stub's driver and a program that follows its motion: the program's pointer is `base`
    plus the driver's position over `per` driver units a program unit, whatever the range, and
    held on the program's own screen when `edge` is given. The stub takes each command at a
    retrace, and the program shows the driver as it was `lag` retraces ago, as one that reads
    the mouse once a pass of its own loop does."""

    def __init__(self, max_: tuple[int, int] = (639, 199), per: tuple[float, float] = (2.0, 1.0),
                 base: tuple[int, int] = (352, 284), edge: tuple[int, int] | None = None,
                 lag: int = 0) -> None:
        self.driver, self.max, self.per, self.base = [320, 100], list(max_), per, base
        self.edge = edge
        self.ranges: list[bytes] = []
        self.driver_range: dict[str, int] | None = None
        self.driver_range_seen: tuple[int, int] | None = None
        self.altered = False
        self.lag, self.retraces, self.commands = lag, 0, 0
        self.history = [(-lag, list(self.driver))]

    def __call__(self) -> float:
        """One retrace of the parked post."""
        self.retraces += 1
        return float(self.retraces)

    def program(self) -> tuple[int, int]:
        driver = next(d for at, d in reversed(self.history) if self.retraces - at >= self.lag)
        x = self.base[0] + round(driver[0] / self.per[0])
        y = self.base[1] + round(driver[1] / self.per[1])
        return (x, y) if self.edge is None else (min(x, self.edge[0]), min(y, self.edge[1]))

    def line(self) -> str:
        return (f"STUB  . mouse x={self.driver[0]} y={self.driver[1]} buttons=0 "
                f"max={self.max[0]},{self.max[1]} mode=0 screen=720x400 vbe=261 attr=155 "
                f"res=1024x768")

    def send_commands(self, commands: list[bytes], advance: Any = None) -> list[str]:
        out = []
        for c in commands:
            if advance is not None:
                advance()
            self.commands += 1
            if c[:1] == b"M":
                self.driver = [min(int.from_bytes(c[1:3], "little"), self.max[0]),
                               min(int.from_bytes(c[3:5], "little"), self.max[1])]
            elif c[:1] == b"W":
                self.ranges.append(c)
                self.max = [int.from_bytes(c[1:3], "little"), int.from_bytes(c[3:5], "little")]
                self.driver = [min(self.driver[0], self.max[0]), min(self.driver[1], self.max[1])]
            elif c[:1] == b"R":
                out.append(self.line())
            self.history.append((self.retraces, list(self.driver)))
        return out


def _steered(world: _World, aim: tuple[int, int], monkeypatch: pytest.MonkeyPatch,
             target: tuple[int, int] | None = None,
             parked: Callable[[], float] | None = None) -> Any:
    """`_steer` from the call's own move to `target`, by default where the driver already is."""
    monkeypatch.setattr(inputs, "program_reader", lambda _s, _p: world.program)
    before = inputs.parse_report(world.line())
    return inputs._steer(cast(Any, world), cast(Any, parked or world), Pointer("a", "b", 2), aim,
                         target or (world.driver[0], world.driver[1]), before,
                         world.program())[:2]


@pytest.mark.parametrize("lag", [0, 6])
def test_an_aim_past_the_drivers_range_widens_it_once_and_the_pointer_arrives(
        lag: int, monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World(lag=lag)
    _report, steered = _steered(world, (900, 600), monkeypatch)
    assert steered is not None and steered.arrived and steered.seen == (900, 600), steered
    assert world.ranges == [inputs.range_command(2043, 767)], world.ranges
    assert world.driver_range == {"x": 2043, "y": 767} and world.altered
    _report, again = _steered(world, (600, 650), monkeypatch)
    assert again is not None and again.arrived and len(world.ranges) == 1, world.ranges


def test_a_sweep_that_a_screen_edge_clamped_still_widens_to_the_whole_screen(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The pointer starts at x=900 and the sweep's far end is pinned at the screen's last unit:
    the span between the corners is 123, and the range asked for was 5315 instead of 2043."""
    world = _World(base=(900, 284), edge=(1023, 767))
    _steered(world, (1000, 600), monkeypatch)
    wide = int.from_bytes(world.ranges[0][1:3], "little")
    assert len(world.ranges) == 1 and 2030 <= wide <= 2060, world.ranges


def test_a_range_the_program_reset_is_widened_again(monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World()
    _steered(world, (900, 600), monkeypatch)
    world.max = [639, 199]                         # INT 33h AX=0 put the default range back
    _report, steered = _steered(world, (950, 650), monkeypatch)
    assert steered is not None and steered.arrived, steered
    assert len(world.ranges) == 2, "a reset range is not the one the server remembers"


def test_a_widening_never_narrows_an_axis_the_range_already_covers(
        monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World(max_=(639, 1500))
    _steered(world, (900, 600), monkeypatch)
    assert world.max[1] == 1500 and world.max[0] >= 2043, world.max


def test_a_program_that_takes_each_move_retraces_late_is_steered_on_with_no_sweep(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Read at once, its pointer still shows the move before: a nudge seems to move nothing, the
    steering gives up on it and sweeps the corners."""
    world = _World(base=(0, 0), lag=6)
    target = (inputs.to_driver(100, 1024, 639), inputs.to_driver(50, 768, 199))
    _report, steered = _steered(world, (100, 50), monkeypatch, target)
    assert steered.arrived and steered.seen == (100, 50) and steered.reach is None, steered


def test_a_program_pointer_already_on_the_aim_is_left_where_it_is(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A move to the middle of the aim's unit would carry the program's pointer off the aim."""
    world = _World(base=(0, 0))
    _report, steered = _steered(world, (160, 100), monkeypatch, (322, 100))
    assert steered == dpointer.Steered((160, 100), True, 0), steered
    assert {tuple(d) for _at, d in world.history} == {(320, 100)}, world.history


@pytest.mark.parametrize(("aim", "target"), [((161, 100), (322, 100)), ((160, 101), (320, 101))])
def test_a_program_pointer_off_the_aim_on_one_axis_is_moved(
        aim: tuple[int, int], target: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World(base=(0, 0))
    _report, steered = _steered(world, aim, monkeypatch, target)
    assert steered.arrived and world.history[1][1] == list(target), world.history


def test_a_sweep_reads_each_corner_once_the_program_took_the_move_there(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Two program units a driver unit leave an odd aim between two of them, so the steering
    fails and sweeps; each corner is the pointer at that corner, not the one before the move."""
    world = _World(per=(0.5, 1.0), lag=6)
    _report, steered = _steered(world, (501, 300), monkeypatch, (60, 10))
    assert not steered.arrived, steered
    assert steered.reach == ((352, 284), (352 + 639 * 2, 284 + 199)), steered


def test_a_pointer_a_clamp_holds_is_read_at_the_bound_and_given_up_on_with_its_span(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Every move is waited on in vain: each read after one ends at the bound and takes the
    pointer as it reads, and the steering gives up with the span it found. The last nudge, at
    the driver's top already, moves nothing and is not waited on."""
    world = _World(edge=(352, 284))
    _report, steered = _steered(world, (400, 300), monkeypatch, (60, 10))
    assert steered == dpointer.Steered((352, 284), False, 2, ((352, 284), (352, 284))), steered
    assert world.retraces - world.commands == 4 * inputs.TAKE_RETRACES, (
        world.retraces, world.commands)


def test_a_breakpoint_that_stops_the_wait_for_the_program_is_the_session_s_stop(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The retraces waited on run the machine as a send's do, so a stop there is observed too."""
    world = _World(base=(0, 0), lag=6)
    stops: list[object] = []
    monkeypatch.setattr(running, "observe_stop", stops.append)

    def parked() -> float:
        if world.retraces == 2:                   # the move and its report are in
            raise ds.Invalid("wait_stopped", "a declared breakpoint stopped the machine")
        return world()
    with pytest.raises(ds.Invalid, match="breakpoint"):
        _steered(world, (100, 50), monkeypatch, (62, 50), parked)
    assert stops == [world], stops


def test_a_widened_range_is_in_every_session_block_while_it_holds(
        monkeypatch: pytest.MonkeyPatch) -> None:
    facts: dict[str, Any] = {"alive": True, "running": False, "altered": True, "pid": 1,
                             "range_widened": None}
    monkeypatch.setattr(dstate.STATE, "session", SimpleNamespace(state=lambda **_: dict(facts)))
    assert "range_widened" not in dstate.session_block(), dstate.session_block()
    facts["range_widened"] = {"x": 2050, "y": 767}
    assert dstate.session_block()["range_widened"] == {"x": 2050, "y": 767}
    assert "range_widened" not in dstate.process_facts()


def test_a_vbe_mode_s_pixel_lands_one_to_one_and_is_said(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.video_mode, fake.vbe = 0x6B, (0x103, 0x9B, 800, 600)
    fake.mouse_max = (799, 599)
    got = cast(dict[str, Any], server.send_mouse(x=799, y=599))
    assert got["status"] == "ok" and got["driver_arrived"] is True, got
    assert fake.commands_sent[-2] == [inputs.move_command(799, 599)]
    assert got["pointer"]["screen"] == {"x": 799, "y": 599, "width": 800, "height": 600}, got
    assert got["pointer"]["vbe_mode"] == "0x103", got
    off = cast(dict[str, Any], server.send_mouse(x=800, y=0))
    assert off["status"] == "INVALID" and "800 x 600" in off["message"], off


def test_a_text_mode_s_rows_and_columns_come_from_the_driver_s_range() -> None:
    """Mode 3 is 80 x 25 or 80 x 50 by the font, and the BIOS mode byte is 3 for both: the
    driver's range says which, eight units a cell."""
    fifty = dataclasses.replace(inputs.parse_report(AUTHORED_TEXT), max_y=399)
    assert fifty.units() == (80, 50)
    assert inputs.parse_report(AUTHORED_TEXT).units() == (80, 25)


@pytest.mark.parametrize(("top", "rows"), [(199, 25), (192, 25), (399, 50), (392, 50)])
def test_a_text_mode_s_rows_are_read_off_a_range_set_either_way(top: int, rows: int) -> None:
    """A program sets the range as `rows * 8 - 1`, or as `(rows - 1) * 8` the way Deluxe Paint
    does for pixels: both name the same rows."""
    report = dataclasses.replace(inputs.parse_report(AUTHORED_TEXT), max_y=top)
    assert report.units() == (80, rows)


def test_both_axes_are_bounded_on_the_screen_and_in_the_driver(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    for kw, words in (({"x": 79, "y": 25}, "outside the screen"),
                      ({"x": 0, "y": 200, "units": "mouse"}, "outside the driver's range")):
        got = cast(dict[str, Any], server.send_mouse(**kw))
        assert got["status"] == "INVALID" and words in got["message"], (kw, got)
    edge = cast(dict[str, Any], server.send_mouse(x=79, y=24))
    assert edge["status"] == "ok" and edge["driver_arrived"] is True, edge
    assert fake.commands_sent[-2] == [inputs.move_command(636, 196)]


def _program_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                     program: Callable[[Any], tuple[int, int]]) -> Any:
    """A parked guest in mode 13h whose map declares the pointer `program` reads."""
    from scry_core import screen_map
    fake = _guest(tmp_path)
    fake.running = False                       # parked, so the move is steered
    fake.video_mode = 0x13                     # 320x200 graphics
    dstate.STATE.maps = screen_map.Maps()
    dstate.STATE.maps.pointer = Pointer("1000:0010", "1000:0012", 2)
    monkeypatch.setattr(inputs, "program_reader", lambda _s, _p: lambda: program(fake))
    return fake


def test_a_program_pointer_on_target_arrives_wherever_the_driver_sits(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A program that integrates the driver's motion takes a click where its own pointer is."""
    fake = _program_pointer(tmp_path, monkeypatch, lambda f: (f.pointer[0] // 3, f.pointer[1]))
    fake.pointer = (0, 0)
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok", got
    assert got["pointer"]["screen"]["x"] != 100, got
    assert got["arrived"] is True and "note" not in got and "asked" not in got, got


def _moved(fake: Any) -> bool:
    return any(c[:1] == b"M" for sent in fake.commands_sent for c in sent)


@pytest.mark.parametrize(("start", "reset", "seen"), [
    ((639, 199), (319, 199), None),
    ((639, 199), (639, 99), None),
    ((319, 199), (639, 199), (639, 199)),     # a widening of an earlier call, reset since
])
def test_a_driver_range_that_changed_under_the_steering_is_not_called_arrived(
        start: tuple[int, int], reset: tuple[int, int], seen: tuple[int, int] | None,
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The program sets the driver's range (INT 33h AX=07h/08h) once the move is under way, even
    to one the steering widened to in an earlier call."""
    def resetting(f: Any) -> tuple[int, int]:
        if _moved(f):
            f.mouse_max = reset
        return f.pointer[0] // 3, f.pointer[1]
    fake = _program_pointer(tmp_path, monkeypatch, resetting)
    fake.pointer, fake.mouse_max = (0, 0), start
    if seen is not None:
        fake.driver_range, fake.driver_range_seen = {"x": seen[0], "y": seen[1]}, seen
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok", got
    assert got["arrived"] is False and "asked" in got, got
    assert got["note"] == inputs.POINTER_DRIVER_DISAGREE, got


def test_a_changed_range_with_the_driver_on_the_unit_asked_is_no_disagreement(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A program that reads the driver's position agrees with it whatever the range."""
    def reading(f: Any) -> tuple[int, int]:
        if _moved(f):
            f.mouse_max = (1279, 199)
        return inputs.to_screen(f.pointer[0], 320, f.mouse_max[0]), f.pointer[1]
    fake = _program_pointer(tmp_path, monkeypatch, reading)
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok" and fake.mouse_max == (1279, 199), got
    assert got["arrived"] is True and "note" not in got, got


def test_a_pointer_that_never_arrives_is_not_blamed_on_a_changed_range(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def held(f: Any) -> tuple[int, int]:
        if _moved(f):
            f.mouse_max = (319, 199)
        return min(f.pointer[0] // 3, 50), f.pointer[1]
    _program_pointer(tmp_path, monkeypatch, held)
    monkeypatch.setattr(inputs, "TAKE_RETRACES", 0)    # the double runs no retraces
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok", got
    assert got["arrived"] is False and "note" not in got, got


def test_a_range_a_click_sets_is_not_the_move_s(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A range the program sets on the click (a menu that opens) is not the move's."""
    fake = _program_pointer(tmp_path, monkeypatch, lambda f: (f.pointer[0] // 3, f.pointer[1]))
    fake.pointer = (0, 0)
    send = fake.send_commands

    def clicked(commands: list[bytes], advance: Any = None) -> list[str]:
        if any(c[:1] == b"B" for c in commands):
            fake.mouse_max = (319, 199)
        return cast(list[str], send(commands, advance))
    fake.send_commands = clicked
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50, button="left"))
    assert got["status"] == "ok" and fake.mouse_max == (319, 199), got
    assert got["arrived"] is True and "note" not in got, got


def test_a_program_pointer_on_the_aim_before_the_call_sends_no_move(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing moved, so nothing reached the motion counters either."""
    fake = _program_pointer(tmp_path, monkeypatch, lambda f: (f.pointer[0] // 2, f.pointer[1]))
    fake.pointer, fake.stub_motion = (201, 50), True
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok" and not _moved(fake), fake.commands_sent
    assert got["arrived"] is True and "motion" not in got, got


LAG = 3


def _lagging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A parked guest whose program takes each driver move `LAG` retraces after it went in, at
    two driver units a program unit; `fake.retraces` counts the retraces the server ran."""
    history: list[tuple[int, tuple[int, int]]] = []

    def program(f: Any) -> tuple[int, int]:
        driver = next(d for at, d in reversed(history) if f.retraces - at >= LAG)
        return driver[0] // 2, driver[1]
    fake = _program_pointer(tmp_path, monkeypatch, program)
    fake.pointer, fake.retraces = (200, 50), 0
    fake.program_now = lambda: program(fake)
    history.append((-LAG, fake.pointer))
    send = fake.send_commands

    def sent(commands: list[bytes], advance: Any = None) -> list[str]:
        out = cast(list[str], send(commands, advance))
        history.append((fake.retraces, fake.pointer))
        return out
    fake.send_commands = sent

    def retrace(_self: Any) -> float:
        fake.retraces += 1
        return float(fake.retraces)
    monkeypatch.setattr(inputs.Retraces, "__call__", retrace)
    return fake


@pytest.mark.parametrize("owing", ["mouse units", "running guest", "drag end"])
def test_a_move_the_steering_did_not_send_is_taken_before_the_next_steered_read(
        owing: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The program still shows the pointer before that move, which here is on the next aim: read
    then, the steered call would send nothing and leave the pointer where the move takes it."""
    fake = _lagging(tmp_path, monkeypatch)
    if owing == "mouse units":
        first = server.send_mouse(x=300, y=50, units="mouse")
    elif owing == "running guest":
        fake.running = True
        first = server.send_mouse(x=150, y=50)
        fake.running = False
    else:
        first = server.send_mouse(x=100, y=50, button="left", action="drag", to_x=150, to_y=50)
    assert cast(dict[str, Any], first)["status"] == "ok", first
    fake.commands_sent.clear()
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok" and _moved(fake), (got, fake.commands_sent)
    assert got["arrived"] is True, got
    fake.retraces += LAG                            # every move that went in is taken
    assert fake.program_now() == (100, 50)


def test_a_steered_move_a_mode_switch_left_unsteered_is_owed_to_the_next(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _lagging(tmp_path, monkeypatch)
    send = fake.send_commands

    def switching(commands: list[bytes], advance: Any = None) -> list[str]:
        out = cast(list[str], send(commands, advance))
        if any(c[:1] == b"M" for c in commands):
            fake.video_mode = 0x6A                  # a mode this server does not map
        return out
    fake.send_commands = switching
    first = cast(dict[str, Any], server.send_mouse(x=150, y=50))
    assert first["status"] == "ok" and "x" not in first["pointer"]["program"], first
    fake.send_commands, fake.video_mode = send, 0x13
    fake.commands_sent.clear()
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok" and _moved(fake), (got, fake.commands_sent)
    fake.retraces += LAG
    assert fake.program_now() == (100, 50)


def test_the_driver_s_range_is_read_after_the_wait_for_an_owed_move(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The program sets the driver's range while it takes the owed move; a range read before
    the wait would make the steering's own moves look like a change it did not make."""
    fake = _lagging(tmp_path, monkeypatch)
    assert cast(dict[str, Any], server.send_mouse(x=300, y=50, units="mouse"))["status"] == "ok"
    taking = inputs.Retraces.__call__

    def resetting(self: Any) -> float:
        fake.mouse_max = (319, 199)
        return taking(self)
    monkeypatch.setattr(inputs.Retraces, "__call__", resetting)
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok" and got["arrived"] is True and "note" not in got, got


def test_an_owed_move_is_waited_for_once(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _lagging(tmp_path, monkeypatch)
    server.send_mouse(x=300, y=50, units="mouse")
    assert fake.pointer_owed is not None
    server.send_mouse(x=100, y=50)
    assert fake.pointer_owed is None


def test_a_drag_s_end_already_taken_is_not_waited_for(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The steering knows the program's pointer the end left, so a pointer already off it is
    read at once."""
    fake = _lagging(tmp_path, monkeypatch)
    server.send_mouse(x=100, y=50, button="left", action="drag", to_x=150, to_y=50)
    fake.retraces += LAG
    before = fake.retraces
    got = cast(dict[str, Any], server.send_mouse(x=150, y=50))
    assert got["status"] == "ok" and got["arrived"] is True, got
    assert fake.retraces - before < inputs.TAKE_RETRACES, fake.retraces - before


def test_with_no_move_owed_the_first_steered_read_waits_for_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _lagging(tmp_path, monkeypatch)
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok" and got["arrived"] is True, got
    assert fake.retraces == 0 and not _moved(fake), (fake.retraces, fake.commands_sent)


def test_a_range_the_steering_widened_itself_is_no_disagreement(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An aim past what the driver's range lets the program reach widens the range."""
    fake = _program_pointer(tmp_path, monkeypatch,
                            lambda f: (f.pointer[0] // 3 + 20, f.pointer[1]))
    got = cast(dict[str, Any], server.send_mouse(x=300, y=50))
    assert got["status"] == "ok", got
    assert fake.mouse_max != (639, 199), fake.mouse_max
    assert got["pointer"]["screen"]["x"] != 300, got
    assert got["arrived"] is True and "note" not in got, got


def test_a_mode_the_move_left_unsized_says_why_the_program_s_pointer_was_not_steered(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The program switches to a mode this server does not map while the move goes in, so there
    is no ratio to nudge by: the reply still carries `pointer.program`, saying why."""
    fake = _program_pointer(tmp_path, monkeypatch, lambda f: (f.pointer[0] // 3, f.pointer[1]))
    fake.pointer = (0, 0)
    send = fake.send_commands

    def switching(commands: list[bytes], advance: Any = None) -> list[str]:
        out = cast(list[str], send(commands, advance))
        if any(c[:1] == b"M" for c in commands):
            fake.video_mode = 0x6A
        return out
    fake.send_commands = switching
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "ok" and got["driver_arrived"] is False, got
    assert got["pointer"]["program"] == unavailable(dpointer.NO_RATIO), got["pointer"]


def test_a_program_s_pointer_that_cannot_be_read_before_the_move_is_refused_unsent(
        tmp_path: Path) -> None:
    """The steering reads the program's pointer before its first move; a read that fails there
    sent nothing, so the call is refused as one that can be made again."""
    from scry_core import screen_map
    fake = _guest(tmp_path)
    fake.running = False
    fake.video_mode = 0x13
    dstate.STATE.maps = screen_map.Maps()
    dstate.STATE.maps.pointer = Pointer("1000:0010", "1000:0012", 2)

    def unreadable(*_a: object, **_k: object) -> bytes:
        raise ds.Invalid("unexpected_answer", "the memory read did not come")
    fake.read_bytes = unreadable
    got = cast(dict[str, Any], server.send_mouse(x=100, y=50))
    assert got["status"] == "INVALID" and "delivered" not in got, got
    assert [c for c in fake.commands_sent if c != [inputs.OP_REPORT]] == [], fake.commands_sent


def test_the_stub_s_own_line_is_never_the_program_s_reaction(tmp_path: Path) -> None:
    """The stub still writes on the program's channel (a second copy saying it stays out), and
    such a line can land after the mark `expect` waits from: a pattern it matches would be
    served as the program having reacted. It is not: the program is silent, and that is a
    miss."""
    fake = _guest(tmp_path)
    fake.input_effect = "Bochs port E9h: STUB  . scry already resident"
    for pattern in ("already", "STUB", "(?i)scry", "resident$"):
        got = cast(dict[str, Any], server.send_mouse(button="left", action="down",
                                                     expect=pattern, seconds=0.5))
        assert got["status"] == "ok" and got["verify"]["verdict"] == "TIMEOUT", (pattern, got)
    fake.input_effect = "Bochs port E9h: UI    . mouse down x=1"
    seen = cast(dict[str, Any], server.send_mouse(button="left", action="up",
                                                  expect="(?i)MOUSE DOWN", seconds=1))
    assert seen["status"] == "ok" and "UI" in seen["verify"]["line"], seen


def test_commands_that_went_in_are_said_when_the_read_back_fails(tmp_path: Path) -> None:
    """The move and the click are in the guest once sent; a read-back that then fails is the
    instrument's, and the reply still says what went in, so a caller does not click twice."""
    fake = _guest(tmp_path)
    fake.reports_lost = {2}
    got = cast(dict[str, Any], server.send_mouse(x=10, y=5, button="left"))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert got["delivered"] is True and got["route"] == "guest", got
    assert "no acknowledgement" in got["message"], got
    acted = [c for c in fake.commands_sent if c != [inputs.OP_REPORT]]
    assert acted == [[inputs.move_command(84, 44), b"B\x80", b"B\x00"]], fake.commands_sent


def test_a_drag_presses_at_its_start_moves_and_releases_at_its_end(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    got = cast(dict[str, Any], server.send_mouse(x=10, y=5, button="left", action="drag",
                                                 to_x=40, to_y=10))
    assert got["status"] == "ok" and got["driver_arrived"] is True, got
    acted = [c for c in fake.commands_sent if c != [inputs.OP_REPORT]]
    end = (inputs.to_driver(40, 80, 639), inputs.to_driver(10, 25, 199))
    assert acted == [[inputs.move_command(84, 44), b"B\x80", inputs.move_command(*end),
                      b"B\x00"]], acted
    assert fake.pointer == end and fake.buttons == 0, (fake.pointer, fake.buttons)


@pytest.mark.parametrize(("kw", "words"), [
    ({"x": 10, "y": 5, "button": "left", "action": "drag"}, "`to_x` and `to_y`"),
    ({"x": 10, "y": 5, "button": "left", "action": "drag", "to_x": 3}, "BOTH `to_x` and `to_y`"),
    ({"button": "left", "action": "drag", "to_x": 3, "to_y": 4}, "starts at"),
    ({"x": 10, "y": 5, "button": "left", "to_x": 3, "to_y": 4}, "action='drag'"),
    ({"x": 10, "y": 5, "button": "left", "action": "drag", "to_x": 99999, "to_y": 4},
     "`to_x` is a whole number"),
])
def test_a_drag_is_refused_without_both_ends_and_the_ends_without_a_drag(
        tmp_path: Path, kw: dict[str, Any], words: str) -> None:
    fake = _guest(tmp_path)
    got = cast(dict[str, Any], server.send_mouse(**kw))
    assert got["status"] == "INVALID" and got["code"] == "bad_argument", got
    assert words in got["message"], got["message"]
    assert not [c for c in fake.commands_sent if c != [inputs.OP_REPORT]], fake.commands_sent


def test_without_a_log_the_keys_go_out_on_the_conf_s_word(tmp_path: Path) -> None:
    fake = _names(tmp_path, watched=False)
    fake.running = True
    fake.stub_protocol = ""
    fake.log = None
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["status"] == "ok" and fake.scancodes_sent == [bytes([0x1E, 0x9E])], got


def test_a_stub_of_a_newer_protocol_is_refused_too(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.stub_protocol = ""
    newer = int(inputs.STUB_PROTOCOL) + 1
    fake.log = [f"Bochs port E9h: STUB  . scry device=present proto={newer}"]
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["status"] == "INVALID" and f"protocol {newer}" in got["message"], got
    assert "delivered" not in got, got
    assert fake.commands_sent == []


#: A line on the program's channel from the stub, carrying every word the patterns below look
#: for, so only its being the stub's keeps it out.
STUB_ON_E9 = "Bochs port E9h: STUB  . scry cue MENU open aa UI x mouse down # the click"


@pytest.mark.parametrize(("pattern", "program", "hit"), [
    ("cue|MENU", "Bochs port E9h: UI    . MENU open", True),
    (r"(a)\1", "Bochs port E9h: UI    . aa", True),
    (r"Bochs port E9h: UI", "Bochs port E9h: UI    . x", True),
    ("(?x) mouse", "Bochs port E9h: UI    . mouse down", True),
    ("(?x) mouse # the click", "Bochs port E9h: UI    . mouse down", True),
    ("(?i)(?m)menu", "Bochs port E9h: UI    . MENU", True),
    ("(?i)stub  . x", "Bochs port E9h: stub  . x", True),
    ("nothing", "Bochs port E9h: UI    . MENU", False),
])
def test_the_reaction_keeps_the_caller_s_pattern_and_never_takes_the_stub_s_line(
        pattern: str, program: str, hit: bool) -> None:
    rx = judges.regex("pattern", inputs.program_reaction(pattern))
    assert bool(rx.search(program)) is hit, (pattern, program)
    assert rx.search(STUB_ON_E9) is None, pattern


def test_a_reaction_pattern_that_cannot_be_composed_is_refused_before_anything_is_sent(
        tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    for bad in ("(?x) (", "a(?i)b"):
        got = cast(dict[str, Any], server.send_keys(keys=["a"], expect=bad))
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", (bad, got)
    assert fake.commands_sent == []


def test_a_forty_column_text_mode_has_forty_cells_whatever_the_driver_s_range() -> None:
    forty = dataclasses.replace(inputs.parse_report(AUTHORED_TEXT), mode=1)
    assert forty.units() == (40, 25)


def test_x_is_bounded_too_and_the_driver_s_top_is_accepted(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    for kw, words in (({"x": 80, "y": 0}, "outside the screen"),
                      ({"x": 640, "y": 0, "units": "mouse"}, "outside the driver's range")):
        got = cast(dict[str, Any], server.send_mouse(**kw))
        assert got["status"] == "INVALID" and words in got["message"], (kw, got)
    top = cast(dict[str, Any], server.send_mouse(x=639, y=199, units="mouse"))
    assert top["status"] == "ok", top
    assert fake.commands_sent[-2] == [inputs.move_command(639, 199)]


def test_a_snapshot_with_no_log_is_refused_as_nothing_could_tell_a_stub_from_a_keyboard(
        tmp_path: Path) -> None:
    """`S` is also the scan code of the Delete key: an old stub would press it. Without a log
    nothing can say which stub is resident, so the command is not sent."""
    fake = _names(tmp_path, watched=False)
    fake.running = True
    fake.stub_protocol = ""
    got = cast(dict[str, Any], server.snapshot())
    assert got["status"] == "INVALID" and got["code"] == "no_channel", got
    assert "logfile" in got["message"]


def test_a_send_that_failed_part_way_says_some_of_it_may_have_gone_in(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    real = fake.send_commands
    calls = {"n": 0}

    def dies_on_the_click(commands: list[bytes]) -> int:
        calls["n"] += 1
        if calls["n"] == 2:
            raise ds.Invalid("session_broken", "the input socket is gone after 1 of 3 commands")
        return cast(int, real(commands))
    fake.send_commands = dies_on_the_click
    got = cast(dict[str, Any], server.send_mouse(x=1, y=1, button="left"))
    assert got["status"] == "INVALID" and got["delivered"] is True, got
    assert got["code"] == "session_broken", got
    assert got["verify"] == {"checked": False, "why": "the send failed part-way"}, got
    assert (got["x"], got["y"], got["units"]) == (1, 1, "screen"), got


def test_keys_that_failed_part_way_say_some_of_them_may_have_gone_in(tmp_path: Path) -> None:
    fake = _guest(tmp_path)

    def dies(commands: list[bytes]) -> int:
        raise ds.Invalid("session_broken", "the input socket is gone after 2 of 6 commands")
    fake.send_commands = dies
    got = cast(dict[str, Any], server.send_keys(keys=["a", "b", "c"]))
    assert got["status"] == "INVALID" and got["delivered"] is True, got
    assert got["code"] == "session_broken", got


@pytest.fixture
def silent() -> Iterator[SilentChannel]:
    channel = SilentChannel(0.2)
    yield channel
    channel.close()


@pytest.mark.parametrize(("tool", "kw", "echoed"), [
    ("send_keys", {"keys": ["c", "d"]}, {"keys": ["c", "d"], "modifiers": []}),
    ("send_mouse", {"x": 200, "y": 80, "units": "mouse"}, {"x": 200, "y": 80, "units": "mouse"})])
def test_an_input_sent_while_the_channel_is_silent_says_nothing_went_in(
        tmp_path: Path, silent: SilentChannel, tool: str, kw: dict[str, Any],
        echoed: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """The run-state question every input asks first gets no reply and no frame is written, so
    the same input sent again goes in once: the reply says it was not sent, how to learn the
    host call ended, and asks the silent channel only once."""
    fake = _guest(tmp_path)
    fake.at_debugger = silent.ask
    # A call recorder an earlier case left on reads `parked`, a flag on the real session that
    # this double answers by asking.
    monkeypatch.setattr(RECORDER, "recording", None)
    got = cast(dict[str, Any], getattr(server, tool)(**kw))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert got.get("delivered") is False, got
    assert {k: got.get(k) for k in echoed} == echoed, got
    assert got["verify"] == {"checked": False, "why": "nothing was sent"}, got
    message = got["message"]
    assert "NOT sent" in message and "`status`" in message, message
    assert "whether it acted is unknown" not in message, message
    assert fake.commands_sent == [] and silent.asked == 1, (fake.commands_sent, silent.asked)


class _PresenceSpy:
    """The overlay writer's input side: every key, pointer and button it was told about."""

    def __init__(self) -> None:
        self.events: list[tuple[Any, ...]] = []

    def key(self, name: str, down: bool) -> None:
        self.events.append(("key", name, down))

    def moved(self, x: int, y: int) -> None:
        self.events.append(("moved", x, y))

    def button(self, name: str, down: bool) -> None:
        self.events.append(("button", name, down))

    def paused(self, stopped: bool) -> None: ...

    def recording(self, kind: str, on: bool) -> None: ...

    def began(self, call: Any) -> None: ...

    def ended(self, call: Any, outcome: Any) -> None: ...

    def keys_marked(self) -> dict[str, Any]:
        return {"before": len(self.events)}

    def keys_restore(self, state: dict[str, Any]) -> None:
        self.events.append(("restored",))

    def close(self) -> None: ...


def _spied(fake: Any) -> _PresenceSpy:
    spy = _PresenceSpy()
    fake.presence = presence.Shown(held=cast(Any, spy))
    return spy


def test_a_key_the_channel_wrote_none_of_is_not_left_marked(tmp_path: Path) -> None:
    """The mark rises when the call is accepted, and the channel then writes none of its keys:
    nothing of the key went in, so its mark is taken back."""
    fake = _guest(tmp_path)
    spy = _spied(fake)

    def unwritten(commands: list[bytes]) -> int:
        raise control.ChannelSilent("EXEC K", 0.2)
    fake.send_commands = unwritten
    got = cast(dict[str, Any], server.send_keys(keys=["c"], action="down"))
    assert got["status"] == "INVALID" and got.get("delivered") is False, got
    assert spy.events == [("key", "c", True), ("restored",)], spy.events


def test_a_performed_key_whose_action_does_not_parse_is_not_marked(tmp_path: Path) -> None:
    """`perform` judges no action, so the key reaches the route and is refused there: a key
    that was never built into a sequence leaves no mark."""
    fake = _guest(tmp_path)
    spy = _spied(fake)
    got = cast(dict[str, Any], server.perform(
        steps=[{"op": "send_keys", "keys": ["a"], "action": "hold"}]))
    assert got["status"] == "INVALID", got
    assert spy.events == [], spy.events


def test_a_mouse_event_cut_before_its_pointer_was_read_does_not_move_the_mark(
        tmp_path: Path) -> None:
    """A click whose send failed part-way has no pointer in its reply; the overlay must not read
    that as the top-left corner and jump the pointer there."""
    fake = _guest(tmp_path)
    spy = _spied(fake)
    real = fake.send_commands
    calls = {"n": 0}

    def dies_on_the_click(commands: list[bytes]) -> int:
        calls["n"] += 1
        if calls["n"] == 2:      # the report is read first; the click is what is lost
            raise ds.Invalid("session_broken", "the input socket is gone after the report")
        return cast(int, real(commands))
    fake.send_commands = dies_on_the_click
    got = cast(dict[str, Any], server.send_mouse(button="left"))
    assert got["status"] == "INVALID" and got.get("delivered") is True, got
    assert not [e for e in spy.events if e[0] == "moved"], spy.events


#: Each opcode's whole frame on the line: SYNC, sequence, the command, the check.
FRAME_LENGTHS = {b"K": 5, b"B": 5, b"M": 8, b"W": 8, b"R": 4}


def _stub(guest: socket.socket, carried: list[bytes], reports: int = 99) -> threading.Thread:
    """The stub on the other end of a real link: it takes each frame on its line, acknowledged
    as carried, and answers the first `reports` reports with a line; a report past them gets no
    answer, as from a guest that stopped running."""
    def run() -> None:
        buf, answered = b"", 0
        with contextlib.suppress(OSError):
            while got := guest.recv(64):
                buf += got
                while len(buf) >= 3 and len(buf) >= FRAME_LENGTHS[buf[2:3]]:
                    length = FRAME_LENGTHS[buf[2:3]]
                    frame, buf = buf[:length], buf[length:]
                    if frame[2:3] == b"R":
                        if answered == reports:
                            continue
                        answered += 1
                        guest.sendall(bytes((stub_link.ACK, frame[1], frame[2], 1))
                                      + AUTHORED_TEXT.encode() + b"\r\n")
                        continue
                    carried.append(frame[2:-1])
                    guest.sendall(bytes((stub_link.ACK, frame[1], frame[2], 1)))
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _linked(fake: Any, silent: SilentChannel) -> tuple[dict[str, bool], socket.socket,
                                                        socket.socket]:
    """A real link behind the double's route, whose parked check is the silent channel while
    `stalled` says so."""
    host, guest = socket.socketpair()
    stalled = {"yes": True}

    def parked() -> bool:
        return silent.ask() if stalled["yes"] else False
    link = stub_link.Link(host, parked=parked)
    fake.send_commands, fake._link = link.send, link
    return stalled, host, guest


def test_a_key_cut_by_a_silent_channel_says_what_went_in_and_is_released_by_the_next(
        tmp_path: Path, silent: SilentChannel) -> None:
    """A key whose press went out and whose acknowledgement waited on a silent channel: its
    release was never written, so the key is down and the same key sent again goes in twice.
    The reply says what was written and that the key is held; a send while the channel is still
    silent writes nothing and says the key is still held; the first send after it releases the
    key first and says so."""
    fake = _guest(tmp_path)
    stalled, host, guest = _linked(fake, silent)
    carried: list[bytes] = []
    try:
        got = cast(dict[str, Any], server.send_keys(keys=["z"]))
        still = cast(dict[str, Any], server.send_keys(keys=["c"]))
        stalled["yes"] = False
        stub = _stub(guest, carried)
        later = cast(dict[str, Any], server.send_keys(keys=["c"]))
    finally:
        host.close()
        guest.close()
    stub.join(timeout=5)
    assert got["status"] == "INVALID" and got.get("delivered") is True, got
    message = got["message"]
    assert "1 input command of this call went to the guest and 1 was not written" in message, (
        message)
    assert "1 key is left pressed" in message and "again" in message, message
    assert "whether it acted is unknown" not in message, message
    assert "may have gone in" not in message, message
    assert still.get("delivered") is False and "NOT sent" in still["message"], still
    assert "1 key is left pressed" in still["message"], still["message"]
    assert carried[0] == b"K\x2c" and carried[-3:] == [b"K\xac", b"K\x2e", b"K\xae"], carried
    assert later["status"] == "ok" and "released" in later.get("note", ""), later


def test_a_click_whose_read_back_waited_on_a_silent_channel_counts_the_click(
        tmp_path: Path, silent: SilentChannel) -> None:
    """The move and the click went in and the report after them is what the silence cut: the
    reply counts the three input commands, never the report."""
    fake = _guest(tmp_path)
    _, host, guest = _linked(fake, silent)
    carried: list[bytes] = []
    stub = _stub(guest, carried, reports=1)
    try:
        got = cast(dict[str, Any], server.send_mouse(x=10, y=5, button="left"))
    finally:
        host.close()
        guest.close()
    stub.join(timeout=5)
    assert carried == [inputs.move_command(84, 44), b"B\x80", b"B\x00"], carried
    assert got["status"] == "INVALID" and got.get("delivered") is True, got
    message = got["message"]
    assert "3 input commands of this call went to the guest" in message, message
    assert "were not written" not in message and "left pressed" not in message, message


def test_a_mouse_event_whose_first_report_waited_on_a_silent_channel_was_not_sent(
        tmp_path: Path, silent: SilentChannel) -> None:
    """The report read before any move is the one the silence cut: no input went in."""
    fake = _guest(tmp_path)
    _, host, guest = _linked(fake, silent)
    carried: list[bytes] = []
    stub = _stub(guest, carried, reports=0)
    try:
        got = cast(dict[str, Any], server.send_mouse(x=10, y=5, button="left"))
    finally:
        host.close()
        guest.close()
    stub.join(timeout=5)
    assert carried == [], carried
    assert got["status"] == "INVALID" and got.get("delivered") is False, got
    assert (got["x"], got["y"], got["units"]) == (10, 5, "screen"), got
    assert "NOT sent" in got["message"], got["message"]


def test_a_first_report_that_fails_delivered_nothing(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.reports_lost = {1}
    got = cast(dict[str, Any], server.send_mouse(button="left"))
    assert got["status"] == "INVALID" and "delivered" not in got, got
    assert all(c == [inputs.OP_REPORT] for c in fake.commands_sent), fake.commands_sent


def test_drive_at_a_stop_never_takes_the_stub_s_line_for_the_program_s() -> None:
    """The verify of an act that ended stopped reads the log since the mark once: a line of the
    stub's can sit there, and it is not the program reacting."""
    from scry_dosbox_x import sequence

    class Since:
        def e9_since_mark(self, mark: int) -> list[str]:
            return ["Bochs port E9h: STUB  . scry already resident",
                    "Bochs port E9h: UI    . clicked"]
    stub_only = sequence._verify_at_a_stop(cast(ds.Session, Since()), "resident", 0)
    assert stub_only["seen"] is False, stub_only
    program = sequence._verify_at_a_stop(cast(ds.Session, Since()), "clicked|resident", 0)
    assert program["seen"] is True and "UI" in program["line"], program


def test_a_target_is_held_to_the_screen_the_guest_shows_before_anything_is_sent(
        tmp_path: Path) -> None:
    """The guest double is in text mode 3, 80x25: a control of a 13h screen is refused with the
    commands unsent, and one of an 80x25 text screen goes to its centre's cell."""
    from scry_core import screen_map
    fake = _guest(tmp_path)
    maps = dstate.STATE.maps = screen_map.Maps()
    court = screen_map.Control("court", (200, 80, 80, 40))
    maps.found = screen_map.Found(screen_map.Screen("play", "pixel", (320, 200),
                                                    (((0, 0, 8, 8), "0" * 16),), (court,)),
                                  "file", 3)
    sent = len(fake.commands_sent)
    got = cast(dict[str, Any], server.send_mouse(target="court", button="left"))
    assert got["code"] == "needs_call" and "a text 80x25 screen now" in got["message"], got
    assert fake.commands_sent[sent:] == [[b"R"]], "the pointer asked about, nothing sent"
    prompt = screen_map.Control("prompt", (0, 3, 4, 1))
    maps.found = screen_map.Found(screen_map.Screen("dos", "text", (80, 25),
                                                    (((0, 0, 8, 1), "0" * 16),), (prompt,)),
                                  "file", 3)
    got = cast(dict[str, Any], server.send_mouse(target="prompt"))
    assert got["status"] == "ok" and got["identified_at_stop"] == 3, got
    assert fake.commands_sent[-2] == [inputs.move_command(20, 28)]


def test_a_program_session_whose_stub_never_announced_names_the_drive_it_used(
        tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    conf = tmp_path / "g.conf"
    conf.write_text("[autoexec]\nmount y .\n", encoding="utf-8")
    fake.launch = dataclasses.replace(fake.launch, conf=conf, program="APP.EXE",
                                      stub_drive=dlaunch.stub_drive(conf))
    conf.write_text("[autoexec]\n" + "\n".join(f"mount {d} ." for d in dlaunch.STUB_DRIVES))
    fake.stub_protocol = ""
    fake.log = ["Bochs port E9h: BOOT  . start"]
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["code"] == "no_channel" and "mounted it on X:" in got["message"], got
    assert fake.commands_sent == []


def test_expect_on_a_session_with_no_log_is_refused_before_anything_reaches_the_guest(
        tmp_path: Path) -> None:
    """The mouse's first report goes to the guest before the post, so `expect` with no E9 to
    check it on is refused ahead of it, as the keys are."""
    fake = _guest(tmp_path)
    fake.launch = dataclasses.replace(fake.launch, logfile=None)

    def no_log() -> int:
        raise ds.Invalid("no_channel", "this session was started without a logfile")
    fake.e9_mark = no_log
    for got in (server.send_mouse(button="left", expect="CLICK"),
                server.send_keys(keys=["a"], expect="KEY")):
        got = cast(dict[str, Any], got)
        assert got["code"] == "bad_argument" and "cannot be checked" in got["message"], got
    assert fake.commands_sent == []


def test_a_machine_that_stopped_under_a_send_has_its_stop_recorded_and_the_send_said(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _guest(tmp_path)
    seen: list[object] = []
    raised = {"yes": False}
    # ONLY A STOP RECORDED AFTER THE SEND MET IT COUNTS: `live()` records any stop first.
    monkeypatch.setattr(running, "observe_stop",
                        lambda ses: seen.append(ses) if raised["yes"] else None)

    def stopped(commands: list[bytes]) -> list[str]:
        raised["yes"] = True
        raise ds.Invalid("wait_stopped", "the machine stopped at the debugger")
    fake.send_commands = stopped
    calls: list[Callable[[], object]] = [lambda: server.send_keys(keys=["a"]),
                                         lambda: server.send_mouse(button="left")]
    for call in calls:
        seen.clear()
        raised["yes"] = False
        got = cast(dict[str, Any], call())
        assert got["code"] == "wait_stopped" and fake in seen, (got, seen)
