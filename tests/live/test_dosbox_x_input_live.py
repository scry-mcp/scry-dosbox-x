"""Input route against a real headless guest (dpmi_guest): keys and clicks the program acts on.

  DOSBOX_X_WALK_MAX            ceiling on the resume-walk to the client
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import dpmi_guest as guest
import pytest
from _live_teardown import no_session_left_behind  # noqa: F401  (registers the autouse teardown)

import dosbox_inputs as inputs
import dosbox_x_server as server

pytestmark = pytest.mark.live

KEY_MARK, ARRIVAL_MARK, MOUSE_MARK = guest.KEY_MARK, guest.ARRIVAL_MARK, guest.MOUSE_MARK
BOOT_MARK, SETTLED_MARK = guest.BOOT_MARK, guest.SETTLED_MARK
LOOK_LINES = 400
#: On the 8-unit cell a text mode keeps, so either mode lands them exactly.
CLICKS = ((200, 96), (400, 160))
BOOT_WAIT_S = 60
SETTLED_WAIT_S = 90


def _start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seconds: int = 180) -> Path:
    """Start one headless DPMI session, store isolated, log in tmp_path."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    log = tmp_path / "guest.log"
    r = cast(dict[str, Any], server.start(
        conf=str(guest.CONF), cwd=str(guest.GUEST), session_seconds=seconds,
        logfile=str(log),
        program=guest.PROGRAM))
    assert r["status"] == "ok", r
    assert "cpu integration device=true" in r["argv"], r["argv"]
    return log


def _input_loop_live() -> None:
    """Wait until the guest's input loop is up; a key posted earlier is swallowed."""
    boot = cast(dict[str, Any], server.log_wait(channel="guest", pattern=BOOT_MARK,
                                                seconds=BOOT_WAIT_S))
    assert boot["status"] == "ok", boot
    settled = cast(dict[str, Any], server.log_wait(channel="guest", pattern=SETTLED_MARK,
                                                  seconds=SETTLED_WAIT_S))
    assert settled["status"] == "ok", settled


def test_send_keys_reaches_the_running_guest_and_it_acts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A key sent to the running guest makes the program act, and an ignored key does not."""
    _start(tmp_path, monkeypatch)
    server.resume()
    _input_loop_live()

    sent = cast(dict[str, Any], server.send_keys(keys=["a"], expect=KEY_MARK, seconds=30))
    assert sent["status"] == "ok", (
        f"the guest did not act on the key ({KEY_MARK} never logged): the host event did not "
        f"reach the running program. {sent.get('message')}")
    assert sent["posted"] == 1 and sent["route"] == "guest", sent
    assert sent["verify"]["seen"] is True and re.search(KEY_MARK, sent["verify"]["line"]), sent

    # Control: from byte 0 the stale cue line would match; from the mark it misses.
    missed = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=KEY_MARK, seconds=3))
    assert missed["status"] == "ok" and missed["verify"]["verdict"] == "TIMEOUT", missed
    assert "miss on the pattern" in missed["verify"]["note"], missed
    assert missed["posted"] == 1 and missed["verify"]["seen"] is False, missed
    # The ignored key arrived: "no reaction" means "took it and did nothing".
    arrived = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=ARRIVAL_MARK, seconds=5))
    assert arrived["status"] == "ok" and arrived["verify"]["seen"] is True, arrived


def test_a_sequence_sends_a_verified_key_to_the_running_guest(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One `perform` of resume, wait, verified key and log runs to the end without a stop."""
    _start(tmp_path, monkeypatch)
    steps: list[dict[str, Any]] = [
        {"op": "resume"},
        {"op": "log_wait", "pattern": BOOT_MARK, "channel": "guest", "seconds": BOOT_WAIT_S},
        {"op": "log_wait", "pattern": SETTLED_MARK, "channel": "guest",
         "seconds": SETTLED_WAIT_S}]
    key_step = len(steps)
    steps += [
        {"op": "send_keys", "keys": ["a"], "expect": KEY_MARK, "seconds": 30},
        {"op": "log", "pattern": KEY_MARK, "channel": "guest"}]
    out = cast(dict[str, Any], server.perform(steps=steps, settle_seconds=5.0))
    assert out["status"] == "ok" and out["steps_completed"] == len(steps), out
    assert out["ran"][key_step]["reply"]["verify"]["seen"] is True, out["ran"][key_step]
    # A boot repaint can read as a halt: then no tail is written.
    assert out.get("still_running") is True or "pc" in out["ran"][0]["reply"], out


def test_drive_looks_acts_and_verifies_in_one_call(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One `drive` sends the cue key, verifies it and returns the lines after the mark."""
    _start(tmp_path, monkeypatch)
    server.resume()
    _input_loop_live()
    out = cast(dict[str, Any], server.drive(
        act=[{"op": "send_keys", "keys": ["a"]}], expect=KEY_MARK, seconds=30,
        pattern=".", limit=LOOK_LINES))
    assert out["status"] == "ok", out
    verify = out["verify"]
    assert verify["seen"] is True and re.search(KEY_MARK, verify["line"]), verify
    e9 = out["looked"]["guest"]
    assert e9["available"] is True and e9["lines_written"] >= 1, e9
    assert any(re.search(KEY_MARK, ln) for ln in e9["lines"]), e9
    # Control: the boot line predates the mark.
    assert e9["lines_written"] <= LOOK_LINES, "raise LOOK_LINES: the cut would hide the control"
    assert not any(re.search(BOOT_MARK, ln) for ln in e9["lines"]), \
        "the look reached before the mark"


def test_the_stub_announces_itself_once_and_ignored_keys_arrive(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stub announces once, a second copy stays out, and an ignored key still arrives."""
    _start(tmp_path, monkeypatch)
    server.resume()
    stub = cast(dict[str, Any], server.log_wait(channel="guest", pattern="STUB  . scry device=",
                                                seconds=60))
    announce = f"device=present proto={inputs.STUB_PROTOCOL}"
    assert stub["status"] == "ok" and announce in stub["line"], stub
    twice = cast(dict[str, Any], server.log_wait(channel="guest",
                                                 pattern="STUB  . scry already resident",
                                                 seconds=30))
    assert twice["status"] == "ok", twice
    _input_loop_live()
    ignored = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=ARRIVAL_MARK,
                                                    seconds=10))
    assert ignored["status"] == "ok" and ignored["verify"]["seen"] is True, ignored
    missed = cast(dict[str, Any], server.send_keys(keys=["f11"], expect=KEY_MARK, seconds=3))
    assert missed["status"] == "ok" and missed["verify"]["verdict"] == "TIMEOUT", missed
    assert "miss on the pattern" in missed["verify"]["note"], missed


def test_send_mouse_puts_the_pointer_where_asked_and_the_program_clicks_there(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A click at two driver positions is announced by the program at the same positions."""
    _start(tmp_path, monkeypatch)
    server.resume()
    _input_loop_live()
    for x, y in CLICKS:
        got = cast(dict[str, Any], server.send_mouse(x=x, y=y, units="mouse", button="left",
                                                     expect=MOUSE_MARK, seconds=10))
        assert got["status"] == "ok" and got["arrived"] is True, got
        assert got["pointer"]["mouse"]["x"] == x and got["pointer"]["mouse"]["y"] == y, got
        assert _guest_xy(got["verify"]["line"]) == (x, y), got["verify"]
    # An unmapped VESA mode: a named control is refused before anything is sent.
    from scry_core import screen_map

    import dosbox_state as dstate
    maps = dstate.STATE.maps = screen_map.Maps()
    for kind, size in (("text", (80, 25)), ("pixel", (320, 200))):
        maps.found = screen_map.Found(screen_map.Screen(
            "s", kind, size, (((0, 0, 1, 1), "0" * 16),),
            (screen_map.Control("c", (20, 10, 4, 2)),)), "file", None)
        aimed = cast(dict[str, Any], server.send_mouse(target="c", button="left"))
        assert aimed["code"] == "needs_call", aimed
        assert f"a {kind} {size[0]}x{size[1]} screen" in aimed["message"], aimed
        assert "screen_map_find" in aimed["message"], aimed
    after = cast(dict[str, Any], server.send_mouse(x=0, y=0, units="mouse"))
    assert after["status"] == "ok", after
    # Reports ride the stub's line, not the program's.
    seen = cast(dict[str, Any], server.log(pattern=r"STUB  \. mouse", channel="guest"))
    assert seen["status"] == "ok" and seen["lines_total"] == 0, seen
    # Control: the stub's announce is found.
    said = cast(dict[str, Any], server.log(pattern=r"STUB  \. scry device=present",
                                           channel="guest"))
    assert said["status"] == "ok" and said["lines_total"] >= 1, said

def _guest_xy(line: str) -> tuple[int, int]:
    m = re.search(r"x=(\d+) y=(\d+)", line)
    assert m, f"the mouse line carries no x=/y=: {line!r}"
    return int(m.group(1)), int(m.group(2))
