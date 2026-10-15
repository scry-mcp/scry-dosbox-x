"""The input route's own arithmetic and its failure halves, against lines a real stub wrote
(`STUB  . mouse ...` captured off a live run) and against the session double of the server's
tests: the report's parse, the screen units, the bounds on both axes, a reaction the stub's own
line cannot fake, and what a call says when its commands went in and the read-back did not."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, cast

import pytest
from test_dosbox_x_server import _guest, _names

import dosbox_inputs as inputs
import dosbox_session as ds
import dosbox_x_server as server

#: Captured off section P's live run: text mode 3, then mode 13h with the left button held.
REAL_TEXT = "Bochs port E9h: STUB  . mouse x=16 y=8 buttons=0 max=639,199 mode=3 screen=720x400"
REAL_13H = "Bochs port E9h: STUB  . mouse x=200 y=50 buttons=1 max=639,199 mode=19 screen=320x400"


def test_a_real_report_parses_into_its_fields() -> None:
    text, held = inputs.parse_report(REAL_TEXT), inputs.parse_report(REAL_13H)
    assert (text.x, text.y, text.buttons, text.max_x, text.max_y, text.mode) == (
        16, 8, 0, 639, 199, 3)
    assert text.drawn == (720, 400) and held.drawn == (320, 400)
    assert held.buttons == 1 and held.mode == 0x13 and held.units() == (320, 200)


@pytest.mark.parametrize(("unit", "size", "top", "driver"), [
    (0, 320, 639, 0), (1, 320, 639, 2), (319, 320, 639, 638),
    (0, 200, 199, 0), (199, 200, 199, 199),
    (79, 80, 639, 632), (24, 25, 199, 192), (49, 50, 399, 392)])
def test_a_screen_unit_maps_onto_the_driver_and_back(unit: int, size: int, top: int,
                                                    driver: int) -> None:
    assert inputs.to_driver(unit, size, top) == driver
    assert inputs.to_screen(driver, size, top) == unit


def test_a_text_mode_s_rows_and_columns_come_from_the_driver_s_range() -> None:
    """Mode 3 is 80 x 25 or 80 x 50 by the font, and the BIOS mode byte is 3 for both: the
    driver's range says which, eight units a cell."""
    fifty = dataclasses.replace(inputs.parse_report(REAL_TEXT), max_y=399)
    assert fifty.units() == (80, 50)
    assert inputs.parse_report(REAL_TEXT).units() == (80, 25)


def test_both_axes_are_bounded_on_the_screen_and_in_the_driver(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    for kw, words in (({"x": 79, "y": 25}, "outside the screen"),
                      ({"x": 0, "y": 200, "units": "mouse"}, "outside the driver's range")):
        got = cast(dict[str, Any], server.send_mouse(**kw))
        assert got["status"] == "INVALID" and words in got["message"], (kw, got)
    edge = cast(dict[str, Any], server.send_mouse(x=79, y=24))
    assert edge["status"] == "ok" and edge["arrived"] is True, edge
    assert fake.commands_sent[-2] == [inputs.move_command(632, 192)]


def test_the_stub_s_own_report_is_never_the_program_s_reaction(tmp_path: Path) -> None:
    """The read-back lands after the mark `expect` waits from, so a pattern the stub's line
    matches would be served as the program having reacted. It is not: the program is silent,
    and that is a miss."""
    fake = _guest(tmp_path)
    fake.input_effect = None
    for pattern in ("buttons=1", r"x=\d+", "STUB", "(?i)mouse"):
        got = cast(dict[str, Any], server.send_mouse(button="left", action="down",
                                                     expect=pattern, seconds=0.5))
        assert got["status"] == "INVALID" and got["code"] == "wait_expired", (pattern, got)
    fake.input_effect = "Bochs port E9h: UI    . mouse down x=1"
    seen = cast(dict[str, Any], server.send_mouse(button="left", action="up",
                                                  expect="(?i)MOUSE DOWN", seconds=1))
    assert seen["status"] == "ok" and "UI" in seen["effect"]["line"], seen


def test_commands_that_went_in_are_said_when_the_read_back_fails(tmp_path: Path) -> None:
    """The move and the click are in the guest once sent; a read-back that then fails is the
    instrument's, and the reply still says what went in, so a caller does not click twice."""
    fake = _guest(tmp_path)
    calls = {"n": 0}
    real_wait = fake.e9_wait

    def second_report_silent(pattern: str, seconds: float, mark: int = 0,
                             **kw: Any) -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] == 2:
            raise ds.E9Expired("no line matched")
        return cast(dict[str, object], real_wait(pattern, seconds, mark=mark, **kw))
    fake.e9_wait = second_report_silent
    got = cast(dict[str, Any], server.send_mouse(x=10, y=5, button="left"))
    assert got["status"] == "INVALID" and got["code"] == "host_failed", got
    assert got["delivered"] is True and got["route"] == "guest", got
    assert "did not report the pointer" in got["message"], got
    acted = [c for c in fake.commands_sent if c != [inputs.OP_REPORT]]
    assert acted == [[inputs.move_command(80, 40), b"B\x80", b"B\x00"]], fake.commands_sent


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
    fake.log = ["Bochs port E9h: STUB  . inject device=present proto=3"]
    got = cast(dict[str, Any], server.send_keys(keys=["a"]))
    assert got["status"] == "INVALID" and "protocol 3" in got["message"], got
    assert fake.commands_sent == []


STUB_REPORT = "Bochs port E9h: STUB  . mouse x=1 y=2 buttons=1 max=639,199 mode=3 screen=720x400"


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
    rx = ds.compiled(inputs.program_reaction(pattern))
    assert bool(rx.search(program)) is hit, (pattern, program)
    assert rx.search(STUB_REPORT) is None, pattern


def test_a_reaction_pattern_that_cannot_be_composed_is_refused_before_anything_is_sent(
        tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    for bad in ("(?x) (", "a(?i)b"):
        got = cast(dict[str, Any], server.send_keys(keys=["a"], expect=bad))
        assert got["status"] == "INVALID" and got["code"] == "bad_argument", (bad, got)
    assert fake.commands_sent == []


def test_a_forty_column_text_mode_has_forty_cells_whatever_the_driver_s_range() -> None:
    forty = dataclasses.replace(inputs.parse_report(REAL_TEXT), mode=1)
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


def test_a_first_report_that_fails_delivered_nothing(tmp_path: Path) -> None:
    fake = _guest(tmp_path)

    def silent(pattern: str, seconds: float, mark: int = 0, **_: Any) -> dict[str, object]:
        raise ds.E9Expired("no line matched")
    fake.e9_wait = silent
    got = cast(dict[str, Any], server.send_mouse(button="left"))
    assert got["status"] == "INVALID" and "delivered" not in got, got
    assert all(c == [inputs.OP_REPORT] for c in fake.commands_sent), fake.commands_sent


def test_drive_at_a_stop_never_takes_the_stub_s_line_for_the_program_s() -> None:
    """The verify of an act that ended stopped reads the log since the mark once: the stub's
    read-back of a mouse step sits there, and it is not the program reacting."""
    import dosbox_sequence as sequence

    class Since:
        def e9_since_mark(self, mark: int) -> list[str]:
            return [STUB_REPORT, "Bochs port E9h: UI    . clicked"]
    stub_only = sequence._verify_at_a_stop(cast(ds.Session, Since()), "buttons=1", 0)
    assert stub_only["seen"] is False, stub_only
    program = sequence._verify_at_a_stop(cast(ds.Session, Since()), "clicked|buttons", 0)
    assert program["seen"] is True and "UI" in program["line"], program
