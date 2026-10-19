"""The input route against a REAL guest: send_keys puts a key into a running program and the
program acts on it, and send_mouse puts the guest's pointer somewhere and clicks there, the
program reporting where. All of it HEADLESS: the route is inside the guest, so these open no
window, take no focus and never touch the host's pointer.

They run on the package's DPMI guest (`dpmi_guest`), whose marks `dpmi.c` writes itself: the
cue key's answer, every key's arrival, a button press with the driver's position, and a periodic
line once its INPUT LOOP is up, which every case waits for before its first key or click (the
boot line is written in the program's first instant, and a key posted before the loop reads
input is swallowed without a trace). The conf runs the package's stub, and `start` loads its own
before the program too, so every case also proves the second copy stays out.

  DOSBOX_X_WALK_MAX            ceiling on the resume-walk to the client (see the entry routes)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import dpmi_guest as guest
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

import dosbox_x_server as server

pytestmark = pytest.mark.live

KEY_MARK, ARRIVAL_MARK, MOUSE_MARK = guest.KEY_MARK, guest.ARRIVAL_MARK, guest.MOUSE_MARK
BOOT_MARK, SETTLED_MARK = guest.BOOT_MARK, guest.SETTLED_MARK
LOOK_LINES = 400          # the drive case's look, wide enough to hold a short act's lines
#: Two driver positions on the 8-unit cell a text mode keeps, so either mode lands them exactly.
CLICKS = ((200, 96), (400, 160))
BOOT_WAIT_S = 60
SETTLED_WAIT_S = 90


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seconds: int = 180) -> Path:
    """ONE headless session on the DPMI build, the store isolated, the log in tmp_path, the
    guest released to run until `close`. Every input case shares this boot exactly."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    log = tmp_path / "guest.log"
    r = cast(dict[str, Any], server.start(
        conf=str(guest.CONF), cwd=str(guest.GUEST), seconds=seconds, logfile=str(log),
        program=guest.PROGRAM))
    assert r["status"] == "ok", r
    assert "cpu integration device=true" in r["argv"], r["argv"]
    return log


def _input_loop_live() -> None:
    """Wait, on the guest's OWN log, until its input loop is up: the boot line, then the
    settled mark. Shared by every case that posts a key or a click, on either route, so none of
    them can post into the gap between the program starting and the program listening."""
    boot = cast(dict[str, Any], server.log_wait(channel="guest", pattern=BOOT_MARK,
                                                seconds=BOOT_WAIT_S))
    assert boot["status"] == "ok", boot
    settled = cast(dict[str, Any], server.log_wait(channel="guest", pattern=SETTLED_MARK,
                                                  seconds=SETTLED_WAIT_S))
    assert settled["status"] == "ok", settled


def test_send_keys_reaches_the_running_guest_and_it_acts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1's CUE A half: let the guest run, send the cue key, and confirm the PROGRAM acted on
    it -- the E9 mark the app writes only from that key's handler. The key goes to a RUNNING
    guest (no breakpoint), which is the route AUTOTYPE and the console cannot serve."""
    _start(tmp_path, monkeypatch)
    server.resume()
    _input_loop_live()

    # THE KEY, to the running guest, WITH ITS EXPECTATION: `a` is the guest's cue key and the
    # mark is written only by the app's own handler for it. The tool marks the log, posts,
    # and confirms a NEW matching line -- the program ACTED, in the same reply.
    sent = cast(dict[str, Any], server.send_keys(keys=["a"], expect=KEY_MARK, seconds=30))
    assert sent["status"] == "ok", (
        f"the guest did not act on the key ({KEY_MARK} never logged): the host event did not "
        f"reach the running program. {sent.get('message')}")
    assert sent["posted"] == 1 and sent["route"] == "guest", sent
    assert sent["effect"]["seen"] is True and re.search(KEY_MARK, sent["effect"]["line"]), sent

    # THE CONTROL, through the same route on the same run, and it is the MARK that it pins:
    # the cue line now sits in the log, so a key the program IGNORES (F11 is bound to
    # nothing) posted with the SAME expectation must come back a MISS. A wait from byte 0
    # would find the stale cue line and pass; only a wait from the mark misses. Without this
    # red beside the green, "verified" and "the verifier never looked" print the same thing.
    missed = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=KEY_MARK, seconds=3))
    assert missed["status"] == "INVALID" and "did not react" in missed["message"], missed
    assert missed["posted"] == 1 and missed["effect"]["seen"] is False, missed
    # AND THE MISS IS THE PROGRAM'S, NOT THE ROUTE'S: when the guest announces every key it
    # receives (its `key down <NAME>` arrival line), the ignored key is shown to have
    # ARRIVED -- so "did not react" above means "took it and did nothing", which is the two
    # facts this tool exists to keep apart.
    arrived = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=ARRIVAL_MARK, seconds=5))
    assert arrived["status"] == "ok" and arrived["effect"]["seen"] is True, arrived


def test_a_sequence_sends_a_verified_key_to_the_running_guest(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1 as ONE `perform`: resume the fresh session, wait for the program to be up, send
    the cue key with its expectation, and read the log after it. `resume` leaves the guest
    running and every later step is a running-OK op, so the sequence runs to the end without
    a stop -- and the key step's reply carries the program's own reaction. This is the
    `[resume, send_keys]` shape the contract tier models with a double; here it is real."""
    _start(tmp_path, monkeypatch)
    # THE SAME "INPUT LOOP IS LIVE" WAIT AS THE OTHER CASES, spelled as sequence steps: the
    # boot line, then the settled mark.
    steps: list[dict[str, Any]] = [
        {"op": "resume"},
        {"op": "log_wait", "pattern": BOOT_MARK, "channel": "guest", "seconds": BOOT_WAIT_S},
        {"op": "log_wait", "pattern": SETTLED_MARK, "channel": "guest",
         "seconds": SETTLED_WAIT_S}]
    key_step = len(steps)
    steps += [
        {"op": "send_keys", "keys": ["a"], "expect": KEY_MARK, "seconds": 30},
        {"op": "log", "pattern": KEY_MARK, "channel": "guest"}]
    out = cast(dict[str, Any], server.perform(steps=steps, wait=5.0))
    assert out["status"] == "ok" and out["completed"] == len(steps), out
    assert out["ran"][key_step]["reply"]["effect"]["seen"] is True, out["ran"][key_step]
    # WHAT THE TAIL SAYS IS `resume`'S READING OF `halted`, not this case's subject: a boot
    # repaint can read as a halt (the open card on resume's two-step boot), in which case
    # the executor takes the machine as stopped and writes no tail. Either shape is
    # accepted here; the four steps ran and the key was seen, which is what this proves.
    assert out.get("still_running") is True or out["ran"][0]["reply"].get("halted"), out


def test_drive_looks_acts_and_verifies_in_one_call(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The loop an autonomous session runs: ONE `drive` sends the cue key, verifies the
    program's reaction from a mark taken before the act, and hands back what the guest wrote
    since -- the cue line among them, and nothing from before the mark."""
    _start(tmp_path, monkeypatch)
    server.resume()
    _input_loop_live()
    out = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"]}], expect=KEY_MARK, seconds=30,
        pattern=".", limit=LOOK_LINES))
    assert out["status"] == "ok", out
    verify = out["verify"]
    assert verify["seen"] is True and re.search(KEY_MARK, verify["line"]), verify
    e9 = out["looked"]["e9"]
    assert e9["available"] is True and e9["written"] >= 1, e9
    assert any(re.search(KEY_MARK, ln) for ln in e9["lines"]), e9
    # THE CONTROL ON THE MARK, with the filter wide open: the boot line was written before
    # the mark, so a look that reached before it would carry it. `lines` is wide enough that
    # the cut cannot be what hides it (the boot line sits first, the cut keeps the last).
    assert e9["written"] <= LOOK_LINES, "raise LOOK_LINES: the cut would hide the control"
    assert not any(re.search(BOOT_MARK, ln) for ln in e9["lines"]), \
        "the look reached before the mark"


def test_the_stub_announces_itself_once_and_ignored_keys_arrive(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The conf runs the stub and `start` loads its own before the program: the first announces
    the device and its protocol, the second says it is already resident, and a key the program
    ignores still ARRIVES (its arrival line) while the cue's line does not, so "did not react"
    means "took it and did nothing"."""
    _start(tmp_path, monkeypatch)
    server.resume()
    stub = cast(dict[str, Any], server.log_wait(channel="guest", pattern="STUB  . inject device=",
                                                seconds=60))
    assert stub["status"] == "ok" and "device=present proto=2" in stub["line"], stub
    twice = cast(dict[str, Any], server.log_wait(channel="guest",
                                                 pattern="STUB  . inject already resident",
                                                 seconds=30))
    assert twice["status"] == "ok", twice
    _input_loop_live()
    ignored = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=ARRIVAL_MARK,
                                                    seconds=10))
    assert ignored["status"] == "ok" and ignored["effect"]["seen"] is True, ignored
    missed = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=KEY_MARK, seconds=3))
    assert missed["status"] == "INVALID" and "did not react" in missed["message"], missed


def test_send_mouse_puts_the_pointer_where_asked_and_the_program_clicks_there(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE MOUSE, END TO END, as the guest sees it: the pointer set at a driver position and a
    click there, which the program announces with the position the driver gave IT. Two places,
    so a pointer that did not move cannot pass, and the reply's read-back agrees with the
    program's own line each time."""
    _start(tmp_path, monkeypatch)
    server.resume()
    _input_loop_live()
    for x, y in CLICKS:
        got = cast(dict[str, Any], server.send_mouse(x=x, y=y, units="mouse", button="left",
                                                     expect=MOUSE_MARK, seconds=10))
        assert got["status"] == "ok" and got["arrived"] is True, got
        assert got["pointer"]["mouse"]["x"] == x and got["pointer"]["mouse"]["y"] == y, got
        assert _guest_xy(got["effect"]["line"]) == (x, y), got["effect"]
    # A CONTROL BY NAME IS HELD TO THE SCREEN THE STUB REPORTS: this program runs a VESA mode
    # this server does not map, so a control of any mapped screen is refused before anything
    # is sent, and the pointer stays where the last click left it.
    from scry_core import screen_map

    import dosbox_state as dstate
    maps = dstate.STATE.maps = screen_map.Maps()
    for kind, size in (("text", (80, 25)), ("pixel", (320, 200))):
        maps.found = screen_map.Found(screen_map.Screen(
            "s", kind, size, (((0, 0, 1, 1), "0" * 16),),
            (screen_map.Control("c", (20, 10, 4, 2)),)), "file", None)
        aimed = cast(dict[str, Any], server.send_mouse(target="c", button="left"))
        assert aimed["code"] == "needs_call", aimed
        assert "a mode this server does not map now" in aimed["message"], aimed
    after = cast(dict[str, Any], server.send_mouse(x=0, y=0, units="mouse"))
    assert after["status"] == "ok", after

def _guest_xy(line: str) -> tuple[int, int]:
    m = re.search(r"x=(\d+) y=(\d+)", line)
    assert m, f"the mouse line carries no x=/y=: {line!r}"
    return int(m.group(1)), int(m.group(2))
