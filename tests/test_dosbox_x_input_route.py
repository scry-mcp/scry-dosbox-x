"""The input route's own arithmetic and its failure halves, against lines a real stub wrote
(`STUB  . mouse ...` captured off a live run) and against the session double of the server's
tests: the report's parse, the screen units, the bounds on both axes, a reaction the stub's own
line cannot fake, and what a call says when its commands went in and the read-back did not."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from dosbox_x_server_support import _guest, _names

import dosbox_inputs as inputs
import dosbox_launch as dlaunch
import dosbox_logs as dlogs
import dosbox_running as running
import dosbox_session as ds
import dosbox_state as dstate
import dosbox_x_server as server

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


def test_a_vbe_mode_s_pixel_lands_one_to_one_and_is_said(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.video_mode, fake.vbe = 0x6B, (0x103, 0x9B, 800, 600)
    fake.mouse_max = (799, 599)
    got = cast(dict[str, Any], server.send_mouse(x=799, y=599))
    assert got["status"] == "ok" and got["arrived"] is True, got
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


def test_both_axes_are_bounded_on_the_screen_and_in_the_driver(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    for kw, words in (({"x": 79, "y": 25}, "outside the screen"),
                      ({"x": 0, "y": 200, "units": "mouse"}, "outside the driver's range")):
        got = cast(dict[str, Any], server.send_mouse(**kw))
        assert got["status"] == "INVALID" and words in got["message"], (kw, got)
    edge = cast(dict[str, Any], server.send_mouse(x=79, y=24))
    assert edge["status"] == "ok" and edge["arrived"] is True, edge
    assert fake.commands_sent[-2] == [inputs.move_command(636, 196)]


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
    rx = dlogs.compiled(inputs.program_reaction(pattern))
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


def test_a_first_report_that_fails_delivered_nothing(tmp_path: Path) -> None:
    fake = _guest(tmp_path)
    fake.reports_lost = {1}
    got = cast(dict[str, Any], server.send_mouse(button="left"))
    assert got["status"] == "INVALID" and "delivered" not in got, got
    assert all(c == [inputs.OP_REPORT] for c in fake.commands_sent), fake.commands_sent


def test_drive_at_a_stop_never_takes_the_stub_s_line_for_the_program_s() -> None:
    """The verify of an act that ended stopped reads the log since the mark once: a line of the
    stub's can sit there, and it is not the program reacting."""
    import dosbox_sequence as sequence

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
